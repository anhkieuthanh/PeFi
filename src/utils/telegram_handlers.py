
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

# Standardize imports across run contexts
try:
    from src import config
except Exception:  # ensure repo root is on sys.path then retry
    from .path_setup import setup_project_root
    setup_project_root(__file__)
    from src import config

UPLOAD_DIR = config.UPLOAD_DIR
API_BILLS_URL = str(getattr(config, 'API_BILLS_URL', ''))

config.initialize_directories()
logger = logging.getLogger(__name__)


def _idempotency_key(update: Update) -> str:
    msg_id = getattr(update.message, 'message_id', None)
    chat = getattr(update, 'effective_chat', None)
    chat_id = getattr(chat, 'id', None)
    return f"{chat_id}:{msg_id}"


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages: download, process, send to API, and reply."""
    if not update.message or not update.message.photo:
        return

    chat_id = update.message.chat_id
    file_path: Optional[str] = None

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được thông tin đang xử lý...")
        photo_file = await update.message.photo[-1].get_file()
        unique_filename = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        await photo_file.download_to_drive(file_path)

        payload = extract_text(file_path)
        if payload == {"raw": "Invalid"}:
            await context.bot.send_message(chat_id=chat_id, text="Ảnh không chứa thông tin giao dịch hợp lệ.")
            return
        # Send parsed payload to API as JSON (not a JSON string)
        payload = json.dumps(payload)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    API_BILLS_URL,
                    json=payload,
                    headers={"Idempotency-Key": _idempotency_key(update)},
                    timeout=30.0,
                )
        except httpx.RequestError as e:
            logger.exception("Không thể kết nối API trong photo_handler")
            print(f"Không thể kết nối tới API: {e}")
            return

        if 200 <= response.status_code < 300:
            try:
                body = response.json()
                transaction_info = body.get("transaction_info") or body.get("message")
                if transaction_info:
                    await context.bot.send_message(chat_id=chat_id, text=str(transaction_info))
                else:
                    # If API returns success but no friendly message, show the raw response for debugging
                    print(f"Đã gửi dữ liệu. API trả về: {body}")
            except Exception:
                print("Đã gửi dữ liệu, nhưng không nhận được phản hồi JSON từ API.")
        else:
            logger.error("API responded with status %s: %s", response.status_code, response.text)
            # Show the API body (or text) to help debugging
            try:
                body = response.json()
                print(f"Lỗi khi gửi dữ liệu lên API: {body}")
            except Exception:
                print(f"Lỗi khi gửi dữ liệu lên API: {response.text}")

    except Exception as e:
        logger.exception("Lỗi trong photo_handler")
        print(f"Đã có lỗi xảy ra: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("Đã xóa ảnh tạm thời: %s", file_path)
            except Exception:
                logger.exception("Không thể xóa file tạm: %s", file_path)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages: parse transaction info and reply."""
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
        payload = json.dumps(payload)
        # Send parsed payload to API as JSON (not a JSON string)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    API_BILLS_URL,
                    json=payload,
                    headers={"Idempotency-Key": _idempotency_key(update)},
                    timeout=30.0,
                )
        except httpx.RequestError as e:
            logger.exception("Không thể kết nối API trong text_handler")
            print(f"Không thể kết nối tới API: {e}")
            return

        logger.debug("API response status: %s", response.status_code)
        logger.debug("API response text: %s", response.text)
        if 200 <= response.status_code < 300:
            try:
                body = response.json()
                transaction_info = body.get("transaction_info") or body.get("message")
                if transaction_info:
                    await context.bot.send_message(chat_id=chat_id, text=str(transaction_info))
                else:
                    print(f"Đã lưu giao dịch. API trả về: {body}")
            except Exception:
                print("Đã lưu giao dịch, nhưng không nhận được phản hồi JSON từ API.")
        else:
            logger.error("API responded with status %s: %s", response.status_code, response.text)
            try:
                body = response.json()
                print(f"Lỗi khi lưu giao dịch: {body}")
            except Exception:
                print(f"Lỗi khi lưu giao dịch: {response.text}")

    except Exception:
        logger.exception("Đã xảy ra lỗi trong text_handler")
        print("🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau.")