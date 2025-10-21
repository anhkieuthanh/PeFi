
import json
import os
import sys
import logging
from typing import Optional
from pathlib import Path

from telegram import Update
from telegram.error import TimedOut
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from .image_processor import extract_text, process_image_from_url
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
    from database.db_operations import add_bill
except Exception:
    # Ensure database module is in path
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from database.db_operations import add_bill

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

    except Exception as e:
        logger.exception("Đã xảy ra lỗi trong text_handler")
        await context.bot.send_message(chat_id=chat_id, text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau.")