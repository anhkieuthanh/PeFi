# config.py
import os
import logging
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# --- CẤU HÌNH BOT ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Vui lòng đặt biến môi trường TELEGRAM_BOT_TOKEN.")

# --- CẤU HÌNH THƯ MỤC ---
UPLOAD_DIR = "uploads"

# --- CẤU HÌNH LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- CẤU HÌNH TESSERACT ---
TESSERACT_CONFIG = r'--oem 3 --psm 6'
TESSERACT_LANG = 'vie+eng'  # Ngôn ngữ tiếng Việt và tiếng Anh

# Hàm khởi tạo các thư mục cần thiết
def initialize_directories():
    """Tạo các thư mục cần thiết nếu chúng chưa tồn tại."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        logging.info(f"Đã tạo thư mục: {UPLOAD_DIR}")