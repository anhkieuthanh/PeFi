import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv
import logging

load_dotenv()

def connect_to_heroku_db():
    conn = None
    try:
        # Try yaml-configured value first, then environment
        try:
            from src import config as app_config
            database_url = app_config.DATABASE_URL or os.environ.get('DATABASE_URL')
        except Exception:
            database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("Biến môi trường DATABASE_URL không được thiết lập.")
        conn = psycopg2.connect(database_url)
        return conn
    except (OperationalError, ValueError) as e:
        print(f"❌ Lỗi: Không thể kết nối. '{e}'")
        return None