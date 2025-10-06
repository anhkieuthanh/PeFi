# bot_handlers.py
import os
import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from .image_processor import extract_text
from .text_processor import parse_text_for_info
# --- PHOTO HANDLER (Giữ nguyên) ---
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn chứa ảnh nhận được."""
    if not update.message or not update.message.photo:
        return
        
    chat_id = update.message.chat_id
    file_path = None

    try:
        await context.bot.send_message(chat_id=chat_id, text="Đã nhận được ảnh, đang xử lý...")
        
        photo_file = await update.message.photo[-1].get_file()
        unique_filename = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join("uploads", unique_filename)
        await photo_file.download_to_drive(file_path)

        detected_text = extract_text(file_path)
        await context.bot.send_message(chat_id=chat_id, text=detected_text)

    except Exception as e:
        logging.error(f"Đã xảy ra lỗi trong photo_handler: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"Đã có lỗi xảy ra: {e}")
    
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Đã xóa ảnh tạm thời: {file_path}")


# --- TEXT HANDLER  ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn văn bản và trả về thông tin giao dịch đã được định dạng."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    chat_id = update.message.chat_id
    
    try:
        # Bước 1: Phân tích văn bản để lấy chuỗi JSON
        result= parse_text_for_info(user_text)
        print("Parsed transaction info:", result)
        # Bước 2: Xây dựng tin nhắn phản hồi
        message_parts = ["✅ **Ghi nhận giao dịch thành công!**\n"]
        
        # Bước 3: Gửi tin nhắn với parse_mode là HTML để hiển thị định dạng
        await context.bot.send_message(
            chat_id=chat_id, 
            text=result
        )

    except Exception as e:
        logging.error(f"Đã xảy ra lỗi trong text_handler: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau."
        )