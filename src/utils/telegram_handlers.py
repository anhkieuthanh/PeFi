import asyncio
import logging
import os
import sys
import re
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.error import TimedOut
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from .image_processor import extract_text
from .text_processor import (
    parse_text_for_info,
    generate_user_response,
    extract_period_and_type,
    build_report_text,
    generate_report_from_gemini_and_db,
)
from .text_processor import preprocess_text
# Import reporting module (DB-first reporting + LLM for language)
try:
    from src.reporting.reporting import get_summary, generate_report
except Exception:
    # ensure repo root on path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.reporting.reporting import get_summary, generate_report

# Standardize imports across run contexts
try:
    import config  # when running from src/
except Exception:  # ensure repo root is on sys.path then retry
    from .path_setup import setup_project_root

    setup_project_root(__file__)
    from src import config

# Import database operations
try:
    from database.db_operations import add_bill, get_transactions_summary
except Exception:
    # Ensure database module is in path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from database.db_operations import add_bill, get_transactions_summary

UPLOAD_DIR = config.UPLOAD_DIR

config.initialize_directories()
logger = logging.getLogger(__name__)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages: download, process, save to database, and reply."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.message.chat_id
    file_path: Optional[str] = None
    
    import time
    start_time = time.time()

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được thông tin đang xử lý...")
        # Thêm retry 1 lần nếu get_file bị timeout
        try:
            photo_file = await update.message.photo[-1].get_file()
        except TimedOut:
            logger.warning("get_file timed out, retrying once...")
            photo_file = await update.message.photo[-1].get_file()
        # Lấy link ảnh trực tiếp để xử lý
        file_path = photo_file.file_path
        if not file_path:
            await context.bot.send_message(chat_id=chat_id, text="Không thể tải ảnh. Vui lòng thử lại.")
            return

        # Extract transaction data from image
        payload = extract_text(file_path)
        if payload == {"raw": "Invalid"}:
            await context.bot.send_message(chat_id=chat_id, text="Ảnh không chứa thông tin giao dịch hợp lệ.")
            return

        # Ensure payload contains a user_id; fall back to default configured user
        try:
            import config as _cfg
        except Exception:
            # config is usually importable; if not, default to 2
            _cfg = None

        if "user_id" not in payload or not payload.get("user_id"):
            payload["user_id"] = getattr(_cfg, "DEFAULT_USER_ID", 2)

        # Save directly to database
        result = add_bill(payload)

        elapsed_time = time.time() - start_time
        logger.info(f"✅ Image processing completed in {elapsed_time:.2f}s")

        if result.get("success"):
            transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
            await context.bot.send_message(chat_id=chat_id, text=transaction_info)
        else:
            error_msg = result.get("error", "Không thể lưu giao dịch")
            logger.error("Lỗi khi lưu bill từ ảnh: %s", error_msg)
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {error_msg}")

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Image processing failed after {elapsed_time:.2f}s")
        logger.exception("Lỗi trong photo_handler")
        await context.bot.send_message(chat_id=chat_id, text=f"Đã có lỗi xảy ra: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("Đã xóa ảnh tạm thời: %s", file_path)
            except Exception:
                logger.exception("Không thể xóa file tạm: %s", file_path)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages: parse transaction info, save to database, and reply."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    chat_id = update.message.chat_id
    
    import time
    start_time = time.time()

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được thông tin đang xử lý...")
        
        # Preprocess text once and reuse
        norm = preprocess_text(user_text).lower()
        
        # Use heuristic detection for reports (faster than LLM classification)
        is_report_heuristic = False
        if (
            "tổng chi" in norm
            or "tổng thu" in norm
            or "tổng hợp" in norm
            or "báo cáo" in norm
            or re.search(r"tháng\s*\d{1,2}", norm)
            or re.search(r"\d+\s*ngày", norm)
        ):
            is_report_heuristic = True

        if is_report_heuristic:
            resp = {"loai_yeu_cau": "Báo cáo", "reply_text": "Đang tạo báo cáo...", "classification": {}}
        else:
            # Classify the user's intent and generate an appropriate reply
            resp = generate_user_response(user_text)
        
        loai = resp.get("loai_yeu_cau")
        reply_text = resp.get("reply_text", "")
        classification = resp.get("classification")

        logger.info("User intent classified as: %s; details: %s", loai, classification)

        if loai == "Báo cáo":
                # For reports, always use the configured DEFAULT_USER_ID (user_id=2 by default)
                # This avoids mismatches between Telegram user mapping and DB test data.
                try:
                    import config as _cfg
                    user_id = getattr(_cfg, "DEFAULT_USER_ID", 2)
                except Exception:
                    user_id = 2

                # Use deterministic extraction (no LLM fallback for better performance)
                report_req = extract_period_and_type(user_text)
                if not report_req:
                    await context.bot.send_message(
                        chat_id=chat_id, 
                        text="Không thể hiểu yêu cầu báo cáo. Vui lòng thử:\n• 'tổng hợp tháng 11'\n• 'báo cáo 30 ngày'\n• 'tổng chi tháng này'"
                    )
                    return

                # We have start/end/type from deterministic parser; query DB (in thread)
                start = report_req.get("start_date")
                end = report_req.get("end_date")
                typ = report_req.get("type", "both")

                summary = await asyncio.to_thread(get_summary, user_id, start, end, typ)
                if not summary or summary.get("error"):
                    err_text = "Lỗi khi truy vấn dữ liệu"
                    if isinstance(summary, dict) and summary.get("error"):
                        err_text = str(summary.get("error"))
                    await context.bot.send_message(chat_id=chat_id, text=err_text)
                    return

                # Generate natural language report via LLM (in thread)
                period_text = report_req.get("raw_period_text") or f"{start} đến {end}"
                report_resp = await asyncio.to_thread(generate_report, summary, period_text, typ, start, end)
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ Report generation completed in {elapsed_time:.2f}s")
                
                # report_resp is a dict {text, used_fallback}
                if isinstance(report_resp, dict):
                    text = str(report_resp.get("text") or "")
                    # Send as Markdown so the LLM's formatting is rendered
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                    except Exception:
                        # Fallback if the parse mode is unsupported or markup invalid
                        await context.bot.send_message(chat_id=chat_id, text=text)
                    if report_resp.get("used_fallback"):
                        # Notify user that LLM formatting was unavailable and a deterministic report was used
                        await context.bot.send_message(chat_id=chat_id, text="(Lưu ý: báo cáo được gửi ở dạng văn bản cơ bản vì trình tạo ngôn ngữ hiện không phản hồi.)")
                else:
                    # backward compatibility: plain string
                    rpt = str(report_resp)
                    await context.bot.send_message(chat_id=chat_id, text=rpt)
                return

        if loai == "Ghi nhận giao dịch":
            # Try to parse and save transaction
            payload = parse_text_for_info(user_text)
            if payload == {"raw": "Invalid"}:
                await context.bot.send_message(chat_id=chat_id, text="Vui lòng nhập thông tin giao dịch hợp lệ.")
                return

            # Ensure payload has user_id (parsers may not set it); use default if missing
            try:
                import config as _cfg
            except Exception:
                _cfg = None

            if "user_id" not in payload or not payload.get("user_id"):
                payload["user_id"] = getattr(_cfg, "DEFAULT_USER_ID", 2)

            result = add_bill(payload)
            
            elapsed_time = time.time() - start_time
            logger.info(f"✅ Text processing completed in {elapsed_time:.2f}s")
            
            if result.get("success"):
                transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
                await context.bot.send_message(chat_id=chat_id, text=transaction_info)
            else:
                error_msg = result.get("error", "Không thể lưu giao dịch")
                logger.error("Lỗi khi lưu bill từ text: %s", error_msg)
                await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {error_msg}")
            return

        # Otherwise, invalid request
        await context.bot.send_message(chat_id=chat_id, text=reply_text)

    except Exception:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Text processing failed after {elapsed_time:.2f}s")
        logger.exception("Đã xảy ra lỗi trong text_handler")
        await context.bot.send_message(
            chat_id=chat_id, text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau."
        )
