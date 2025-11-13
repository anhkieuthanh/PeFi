import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from config import TOKEN, initialize_directories
from utils.telegram_handlers import photo_handler, text_handler
from utils.voice_handlers import voice_handler

# Configure logging to see debug output
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def main() -> None:
    # Khởi tạo các thư mục cần thiết
    initialize_directories()

    # Tạo đối tượng Application với timeout cao hơn để tránh TimedOut
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=30,
        pool_timeout=30,
    )
    application = Application.builder().token(TOKEN).request(request).build()  # type: ignore

    # Thêm trình xử lý cho tin nhắn ảnh
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Trình xử lí cho tin nhắn văn bản
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))

    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    # Bắt đầu chạy bot
    print("Bot đang chạy...")
    application.run_polling()


if __name__ == "__main__":
    main()
