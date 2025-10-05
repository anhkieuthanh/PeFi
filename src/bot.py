from utils.telegram_handlers import photo_handler
from telegram.ext import Application, MessageHandler, filters
from config import TOKEN, initialize_directories

def main() -> None:
    # Khởi tạo các thư mục cần thiết
    initialize_directories()
    
    # Tạo đối tượng Application
    application = Application.builder().token(TOKEN).build() #type: ignore

    # Thêm trình xử lý cho tin nhắn ảnh
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    # Trình xử lí cho tin nhắn văn bản
    #application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    # Bắt đầu chạy bot
    print("Bot đang chạy...")
    application.run_polling()

if __name__ == '__main__':
    main()