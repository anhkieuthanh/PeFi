import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from google import genai

_have_yaml = False
def _load_yaml_from_fileobj(f):
    global _have_yaml
    try:
        # Prefer PyYAML if available
        import yaml as _pyyaml
        _have_yaml = True
        return _pyyaml.safe_load(f)
    except Exception:
        try:
            from ruamel.yaml import YAML as _RuamelYAML
            _have_yaml = True
            _ry = _RuamelYAML(typ='safe')
            return _ry.load(f)
        except Exception:
            _have_yaml = False
            raise

load_dotenv()

_ROOT = Path(__file__).resolve().parents[1]
_YAML_PATH = _ROOT / 'config.yaml'

# Load YAML (if present) using whichever YAML implementation is installed
_yaml_conf = {}
if _YAML_PATH.exists():
    try:
        with open(_YAML_PATH, 'r', encoding='utf-8') as f:
            _yaml_conf = _load_yaml_from_fileobj(f) or {}
    except Exception:
        logging.exception('Không thể đọc config.yaml (no YAML parser available or file invalid)')

# Helper to get config values (env override YAML)
def _get(path, env_var=None, default=None):
    # path: list or dot-separated string
    keys = path.split('.') if isinstance(path, str) else list(path)
    val = _yaml_conf
    try:
        for k in keys:
            val = val.get(k, {})
    except Exception:
        val = {}
    if isinstance(val, dict) and not val:
        val = None
    # environment override
    if env_var and os.getenv(env_var) is not None:
        return os.getenv(env_var)
    return val if val is not None else default

# --- TELEGRAM ---
TOKEN = _get('telegram.token', env_var='TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError('Vui lòng đặt biến môi trường TELEGRAM_BOT_TOKEN hoặc cấu hình trong config.yaml')

# --- UPLOADS ---
_upload_dir_val = _get('uploads.dir', env_var='UPLOAD_DIR', default='uploads')
UPLOAD_DIR = str(_upload_dir_val) if _upload_dir_val is not None else 'uploads'

def initialize_directories():
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logging.info(f"Đã tạo/kiểm tra thư mục: {UPLOAD_DIR}")

# --- GOOGLE GEMINI ---
_gemini_key_val = _get('google.gemini_api_key', env_var='GEMINI_API_KEY')
GEMINI_API_KEY = str(_gemini_key_val) if _gemini_key_val is not None else None
if not GEMINI_API_KEY:
    raise ValueError('Vui lòng đặt biến môi trường GEMINI_API_KEY hoặc cấu hình trong config.yaml')
client = genai.Client(api_key=str(GEMINI_API_KEY))

# --- API URLs ---
API_BILLS_URL = _get('api.bills_url', env_var='BILLS_API_URL', default='http://127.0.0.1:5000/api/v1/bills')


# --- DATABASE ---
_db_url_val = _get('database.url', env_var='DATABASE_URL')
DATABASE_URL = str(_db_url_val) if _db_url_val is not None else None


def validate_config():
    """Basic runtime validation for required config values."""
    missing = []
    if not TOKEN:
        missing.append('TELEGRAM_BOT_TOKEN')
    if not GEMINI_API_KEY:
        missing.append('GEMINI_API_KEY')
    if missing:
        raise ValueError(f'Missing required configuration: {", ".join(missing)}')

