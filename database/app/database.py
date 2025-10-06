import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

def connect_to_heroku_db():
    conn = None
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("Biến môi trường DATABASE_URL không được thiết lập.")
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(database_url)
        return conn
    except (OperationalError, ValueError) as e:
        print(f"❌ Lỗi: Không thể kết nối. '{e}'")
        return None