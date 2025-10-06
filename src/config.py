# config.py
import os
import logging
from dotenv import load_dotenv
from google import genai
load_dotenv()

# --- CẤU HÌNH BOT TELEGRAM ---
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Vui lòng đặt biến môi trường TELEGRAM_BOT_TOKEN.")

# --- CẤU HÌNH THƯ MỤC ---
UPLOAD_DIR = os.getenv('UPLOAD_DIR', 'uploads')

def initialize_directories():
    """Tạo các thư mục cần thiết nếu chúng chưa tồn tại."""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        logging.info(f"Đã tạo thư mục: {UPLOAD_DIR}")
        
# --- CẤU HÌNH GOOGLE GEMINI API ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Vui lòng đặt biến môi trường GEMINI_API_KEY.")
client = genai.Client(api_key=GEMINI_API_KEY)