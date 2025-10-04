# bot_handlers.py
import os
import uuid
import logging
import re  # Import thư viện Regex
from telegram import Update
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from config import UPLOAD_DIR
from image_processor import process_image_and_extract_text
from text_parser import parse_text_for_info

# Hàm phụ trợ để chuyển đổi chuỗi số tiền có hậu tố 'k' hoặc 'm' thành số thực
def parse_amount_string(s: str) -> float | None:
    """
    Chuyển đổi chuỗi số tiền (hỗ trợ 'k', 'm') thành một con số.
    Ví dụ: '50k' -> 50000.0, '5m' -> 5000000.0, '5m2' -> 5200000.0
    Trả về None nếu định dạng không hợp lệ.
    """
    s = s.lower().strip()
    try:
        if 'm' in s:
            parts = s.split('m')
            millions = float(parts[0]) * 1_000_000
            if parts[1]: # Xử lý trường hợp '5m2'
                hundred_thousands = float(parts[1]) * 100_000
                return millions + hundred_thousands
            return millions # Xử lý trường hợp '5m'
        elif 'k' in s:
            num_part = s.replace('k', '')
            return float(num_part) * 1_000
        else:
            # Xử lý số thông thường, loại bỏ dấu chấm/phẩy
            return float(s.replace('.', '').replace(',', ''))
    except (ValueError, IndexError):
        # Trả về None nếu có lỗi xảy ra (vd: 'abc', '5m2k')
        return None
    
# --- PHOTO HANDLER ---
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
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        await photo_file.download_to_drive(file_path)

        detected_text = process_image_and_extract_text(file_path)
        
        if not detected_text.strip():
            await context.bot.send_message(chat_id=chat_id, text="Rất tiếc, tôi không tìm thấy văn bản nào trong ảnh của bạn hãy chụp hoá đơn rõ ràng hơn hoặc nhập bằng tay.")
        else:
            final_result = parse_text_for_info(detected_text)
            await context.bot.send_message(chat_id=chat_id, text=final_result)

    except Exception as e:
        logging.error(f"Đã xảy ra lỗi trong photo_handler: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"Đã có lỗi xảy ra: {e}")
    
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Đã xóa ảnh tạm thời: {file_path}")

# --- TEXT HANDLER ---
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn văn bản, hỗ trợ số tiền dạng chữ và số viết tắt."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    chat_id = update.message.chat_id

    if user_text.lower().startswith('bot '):
        pattern = re.compile(r'^bot\s+([tTcC])\s+(.+?)\s+(.+)$', re.IGNORECASE)
        match = pattern.match(user_text)

        if match:
            loai_gd_char = match.group(1).lower()
            so_tien_str = match.group(2).strip()
            ghi_chu = match.group(3).strip()
            
            # --- SỬ DỤNG HÀM MỚI ĐỂ CHUYỂN ĐỔI SỐ TIỀN ---
            numeric_amount = parse_amount_string(so_tien_str)

            # Kiểm tra nếu chuyển đổi thất bại
            if numeric_amount is None:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Tôi không hiểu số tiền: '{so_tien_str}'. Vui lòng nhập số hợp lệ (ví dụ: 50000, 50k, 5m, 5m2)\\."
                )
                return

            # Xử lý loại giao dịch
            if loai_gd_char == 't':
                loai_gd_full = "Thu nhập 📈"
            else:
                loai_gd_full = "Chi tiêu 📉"
  
            # Định dạng lại số tiền để hiển thị cho đẹp
            formatted_amount = f"{numeric_amount:,.0f}".replace(",", ".")

            # Tạo và gửi tin nhắn phản hồi
            response_message = (
                f"✅ Ghi nhận giao dịch thành công !\n\n"
                f"👀Loại: {loai_gd_full}\n"
                f"💵Số tiền: {formatted_amount}\n"
                f"📝Ghi chú: {ghi_chu}"
            )
            await context.bot.send_message(chat_id=chat_id, text=response_message)
        
        else:
            # Tin nhắn hướng dẫn giữ nguyên
            reminder_message = (
                "⚠️ Định dạng tin nhắn không đúng\\. Vui lòng sử dụng định dạng sau\\:\n\n"
                "`bot <t|c> <số tiền> <ghi chú>`\n\n"
                "Ví dụ\\:\n"
                "`bot t 50k Lương tháng 9`\\\n"
                "`bot c 5m2 Mua điện thoại`"
            )
            await context.bot.send_message(chat_id=chat_id, text=reminder_message, parse_mode='MarkdownV2') #type: ignore