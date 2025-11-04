import sys
from pathlib import Path
import psycopg2
from psycopg2 import OperationalError
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

# Module-level connection pool (initialized lazily)
_POOL = None

@contextmanager
def connect_to_heroku_db():
    """Context manager that yields a pooled DB connection and returns it to the pool on exit."""
    try:
        # Ensure repo root on sys.path so `from src import config` works when CWD is database/
        repo_root = Path(__file__).resolve().parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src import config as app_config  # type: ignore

        # Read DATABASE_URL only from the YAML-backed config module
        database_url = getattr(app_config, "DATABASE_URL", None)
        if not database_url:
            raise ValueError("Vui lòng cấu hình 'database.url' trong config.yaml")

        # Get pool sizing from config if available
        pool_min = getattr(app_config, "DB_POOL_MIN", 1)
        pool_max = getattr(app_config, "DB_POOL_MAX", 10)

        # Initialize pool lazily
        global _POOL
        if _POOL is None:
            try:
                _POOL = SimpleConnectionPool(int(pool_min), int(pool_max), database_url)
            except Exception as exc:
                raise ValueError("Không thể khởi tạo connection pool cho database") from exc

        # Get a connection from the pool
        conn = _POOL.getconn()
        try:
            yield conn
        finally:
            try:
                _POOL.putconn(conn)
            except Exception:
                # If returning to pool fails, close connection to avoid leaks
                try:
                    conn.close()
                except Exception:
                    pass

    except (OperationalError, ValueError) as e:
        print(f"❌ Lỗi: Không thể kết nối. '{e}'")
        # Re-raise so callers can handle the exception if they want
        raise
