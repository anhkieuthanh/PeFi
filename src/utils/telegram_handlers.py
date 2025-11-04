import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.error import TimedOut
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from .image_processor import extract_text
from .text_processor import parse_text_for_info

# Standardize imports across run contexts
try:
    import config  # when running from src/
except Exception:  # ensure repo root is on sys.path then retry
    from .path_setup import setup_project_root

    setup_project_root(__file__)
    from src import config

# Import database operations
try:
    from database.db_operations import add_bill, create_user, get_user_by_name
except Exception:
    # Ensure database module is in path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from database.db_operations import add_bill, create_user, get_user_by_name

# Import Local LLM agent for insights
try:
    from llm.llm import create_llm_db_agent
except Exception:
    # Ensure llm module is importable from repo root
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from llm.llm import create_llm_db_agent

UPLOAD_DIR = config.UPLOAD_DIR

config.initialize_directories()
logger = logging.getLogger(__name__)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages: download, process, save to database, and reply."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.message.chat_id
    file_path: Optional[str] = None

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

        # Save directly to database
        result = add_bill(payload)

        if result.get("success"):
            transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
            await context.bot.send_message(chat_id=chat_id, text=transaction_info)
        else:
            error_msg = result.get("error", "Không thể lưu giao dịch")
            logger.error("Lỗi khi lưu bill từ ảnh: %s", error_msg)
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {error_msg}")

    except Exception as e:
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

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được thông tin đang xử lý...")
        payload = parse_text_for_info(user_text)
        if payload == {"raw": "Invalid"}:
            await context.bot.send_message(chat_id=chat_id, text="Vui lòng nhập thông tin giao dịch hợp lệ.")
            return

        # Save directly to database
        result = add_bill(payload)

        if result.get("success"):
            transaction_info = result.get("transaction_info", "Đã lưu giao dịch thành công")
            await context.bot.send_message(chat_id=chat_id, text=transaction_info)
        else:
            error_msg = result.get("error", "Không thể lưu giao dịch")
            logger.error("Lỗi khi lưu bill từ text: %s", error_msg)
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {error_msg}")

    except Exception:
        logger.exception("Đã xảy ra lỗi trong text_handler")
        await context.bot.send_message(
            chat_id=chat_id, text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau."
        )


async def _ensure_user_and_get_id(update: Update) -> Optional[int]:
    """Map Telegram user to DB user and return user_id (create if missing)."""
    try:
        tg_user = update.effective_user
        if tg_user is None:
            return None
        tg_id = getattr(tg_user, "id", None)
        username = getattr(tg_user, "username", None)
        user_name = username or (f"tg_{tg_id}" if tg_id is not None else "tg_unknown")
        # Try to find existing user
        user = get_user_by_name(user_name)
        if not user:
            res = create_user(user_name)
            if not isinstance(res, dict) or not res.get("success"):
                return None
            user = res.get("user")
        if isinstance(user, dict):
            uid = user.get("user_id") or user.get("id")
            return int(uid) if uid is not None else None
        return None
    except Exception:
        logger.exception("Failed to ensure user in database")
        return None


async def insights_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate AI insights using local LLM; fallback to quick summary on failure."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id=chat_id, text="🔎 Đang tạo insights, có thể mất 1-2 phút...")
    try:
        user_id = await _ensure_user_and_get_id(update)
        if not user_id:
            await context.bot.send_message(chat_id=chat_id, text="❌ Không xác định được người dùng trong hệ thống.")
            return
        # Create agent in a thread to avoid blocking
        agent = await asyncio.to_thread(create_llm_db_agent)
        if not agent:
            await context.bot.send_message(
                chat_id=chat_id, text="❌ Không kết nối được LLM local. Hãy bật server tại http://localhost:1234."
            )
            return
        # Try AI insights with longer timeout (inside agent implementation)
        insights_text = await asyncio.to_thread(agent.get_spending_insights, user_id, 30)
        if not insights_text or "Không thể tạo insights" in insights_text:
            # Fallback to quick summary
            summary = await asyncio.to_thread(agent.get_quick_summary, user_id, 30)
            await context.bot.send_message(chat_id=chat_id, text=summary)
            return
        await context.bot.send_message(chat_id=chat_id, text=insights_text)
    except Exception:
        logger.exception("Error in insights_handler")
        await context.bot.send_message(
            chat_id=chat_id, text="❌ Lỗi khi tạo insights. Thử lại sau hoặc dùng /summary để xem tóm tắt nhanh."
        )


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a quick spending summary without using LLM."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    try:
        user_id = await _ensure_user_and_get_id(update)
        if not user_id:
            await context.bot.send_message(chat_id=chat_id, text="❌ Không xác định được người dùng trong hệ thống.")
            return
        agent = await asyncio.to_thread(create_llm_db_agent)
        if not agent:
            await context.bot.send_message(chat_id=chat_id, text="❌ Không kết nối được database để tạo tóm tắt.")
            return
        summary = await asyncio.to_thread(agent.get_quick_summary, user_id, 30)
        await context.bot.send_message(chat_id=chat_id, text=summary)
    except Exception:
        logger.exception("Error in summary_handler")
        await context.bot.send_message(chat_id=chat_id, text="❌ Lỗi khi tạo tóm tắt. Vui lòng thử lại sau.")
