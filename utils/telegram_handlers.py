# bot_handlers.py
import os
import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

# Import các hàm chức năng từ các module khác
from image_processor import extract_text

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


# --- TEXT HANDLER (Phiên bản cập nhật) ---
# async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Xử lý tin nhắn văn bản và trả về thông tin giao dịch đã được định dạng."""
#     if not update.message or not update.message.text:
#         return

#     user_text = update.message.text
#     chat_id = update.message.chat_id
    
#     try:
#         # Bước 1: Phân tích văn bản để lấy chuỗi JSON
#         # Giả sử `parse_text_for_info` trả về một chuỗi JSON
#         parsed_json_str = parse_text_for_info(user_text)
#         result = json.loads(parsed_json_str)

#         # Bước 2: Xây dựng tin nhắn phản hồi
#         message_parts = ["✅ **Ghi nhận giao dịch thành công!**\n"]
        
#         # Định nghĩa các trường thông tin muốn hiển thị và emoji tương ứng
#         key_map = {
#             "Date": "🗓 Ngày giao dịch",
#             "Amount": "💰 Số tiền",
#             "Transaction": "🔄 Loại giao dịch",
#             "Category": "🏷️ Danh mục",
#             "Description": "📝 Ghi chú"
#         }

#         # Duyệt qua các trường và chỉ thêm vào tin nhắn nếu có dữ liệu
#         for key, label in key_map.items():
#             value = result.get(key)
#             if value:
#                 # Xử lý định dạng đặc biệt cho 'Amount'
#                 if key == 'Amount':
#                     try:
#                         # Thử chuyển đổi thành số và định dạng với dấu phẩy
#                         display_value = f"{int(value):,} VND"
#                     except (ValueError, TypeError):
#                         # Nếu không chuyển đổi được, giữ nguyên giá trị gốc
#                         display_value = value
#                 else:
#                     display_value = value
                
#                 message_parts.append(f"{label}: <b>{display_value}</b>")
        
#         # Nối các phần lại với nhau
#         response_message = "\n".join(message_parts)

#         # (Tùy chọn) Thêm phần chi tiết JSON để xem đầy đủ
#         # Sử dụng thẻ pre và code để Telegram hiển thị đẹp hơn
#         pretty_json = json.dumps(result, indent=2, ensure_ascii=False)
#         response_message += f"\n\n🔍 <b>Chi tiết (JSON):</b>\n<pre><code>{pretty_json}</code></pre>"

#         # Bước 3: Gửi tin nhắn với parse_mode là HTML để hiển thị định dạng
#         await context.bot.send_message(
#             chat_id=chat_id, 
#             text=response_message,
#             parse_mode=ParseMode.HTML
#         )

#     except json.JSONDecodeError:
#         logging.error(f"Lỗi giải mã JSON từ chuỗi: '{parsed_json_str}'")
#         await context.bot.send_message(
#             chat_id=chat_id,
#             text="🙁 Rất tiếc, tôi không thể hiểu được thông tin bạn cung cấp. Vui lòng thử lại."
#         )
#     except Exception as e:
#         logging.error(f"Đã xảy ra lỗi trong text_handler: {e}")
#         await context.bot.send_message(
#             chat_id=chat_id,
#             text="🙁 Đã có lỗi xảy ra trong quá trình xử lý. Vui lòng thử lại sau."
#         )