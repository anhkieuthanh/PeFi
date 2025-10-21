import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

def connect_to_heroku_db():
    conn = None
    try:
        # Try yaml-configured value first, then environment
        database_url = None
        try:
            # Ensure repo root on sys.path so `from src import config` works when CWD is database/
            repo_root = Path(__file__).resolve().parents[1]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            from src import config as app_config  # type: ignore
            database_url = getattr(app_config, 'DATABASE_URL', None) or os.environ.get('DATABASE_URL')
        except Exception:
            database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("Biến môi trường DATABASE_URL không được thiết lập.")
        conn = psycopg2.connect(database_url)
        return conn
    except (OperationalError, ValueError) as e:
        print(f"❌ Lỗi: Không thể kết nối. '{e}'")
        return None
