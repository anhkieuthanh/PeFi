
import json
import os
import uuid
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
import httpx

# Import các hàm chức năng từ các module khác
from .image_processor import extract_text
from .text_processor import parse_text_for_info

# Import config in a way that works both when running as a package (project root on PYTHONPATH)
# and when running scripts from the `src/` directory directly.
try:
    # Preferred: when project root is on PYTHONPATH
    from src import config
except Exception:
    try:
        # Fallback: when current working directory is `src/`
        import config
    except Exception:
        # As a last resort, add project root to sys.path and retry package import
        import sys
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src import config

UPLOAD_DIR = config.UPLOAD_DIR
API_BILLS_URL = config.API_BILLS_URL

config.initialize_directories()
logger = logging.getLogger(__name__)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages: download, process, send to API, and reply."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.message.chat_id
    file_path: Optional[str] = None

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được ảnh, đang xử lý...")

        photo_file = await update.message.photo[-1].get_file()
        unique_filename = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        await photo_file.download_to_drive(file_path)

        # extract_text returns a dict (parsed data)
        parsed = extract_text(file_path)
        # send a readable preview to the user
        pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        await context.bot.send_message(chat_id=chat_id, text=f"Kết quả trích xuất:\n{pretty}")

        # send parsed payload to API as JSON (not a JSON string)
        async with httpx.AsyncClient() as client:
            response = await client.post(API_BILLS_URL, json=parsed, timeout=30.0)

        logger.debug("API response status: %s", response.status_code)
        logger.debug("API response text: %s", response.text)

        if 200 <= response.status_code < 300:
            try:
                body = response.json()
                transaction_info = body.get("transaction_info") or body.get("message")
                if transaction_info:
                    await context.bot.send_message(chat_id=chat_id, text=str(transaction_info))
                else:
                    # If API returns success but no friendly message, show the raw response for debugging
                    await context.bot.send_message(chat_id=chat_id, text=f"Đã gửi dữ liệu. API trả về: {body}")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text="Đã gửi dữ liệu, nhưng không nhận được phản hồi JSON từ API.")
        else:
            logger.error("API responded with status %s: %s", response.status_code, response.text)
            # Show the API body (or text) to help debugging
            try:
                body = response.json()
                await context.bot.send_message(chat_id=chat_id, text=f"Lỗi khi gửi dữ liệu lên API: {body}")
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=f"Lỗi khi gửi dữ liệu lên API: {response.text}")

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
    """Handle text messages: parse transaction info and reply.

    The `parse_text_for_info` should return a string or a dict-like object. We ensure
    to send a readable string back to the user.
    """
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    chat_id = update.message.chat_id

    try:
        result = parse_text_for_info(user_text)
        # normalize output to string for user
        if isinstance(result, (dict, list)):
            result_text = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            result_text = str(result)

        logger.debug("Parsed transaction info: %s", result_text)

        await context.bot.send_message(chat_id=chat_id, text=result_text)

    except Exception:
        logger.exception("Đã xảy ra lỗi trong text_handler")
        await context.bot.send_message(
            chat_id=chat_id,
            text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau."
        )