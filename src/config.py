import logging
from pathlib import Path

import google.generativeai as genai

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
            _ry = _RuamelYAML(typ="safe")
            return _ry.load(f)
        except Exception:
            _have_yaml = False
            raise

_ROOT = Path(__file__).resolve().parents[1]
_YAML_PATH = _ROOT / "config.yaml"

# Load YAML (if present) using whichever YAML implementation is installed
_yaml_conf = {}
if _YAML_PATH.exists():
    try:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            _yaml_conf = _load_yaml_from_fileobj(f) or {}
    except Exception:
        logging.exception("Không thể đọc config.yaml (no YAML parser available or file invalid)")


# Helper to get config values (env override YAML)
def _get(path, env_var=None, default=None):
    # path: list or dot-separated string
    # env_var is accepted for backward compatibility but is ignored; only YAML is used.
    keys = path.split(".") if isinstance(path, str) else list(path)
    val = _yaml_conf
    try:
        for k in keys:
            val = val.get(k, {})
    except Exception:
        val = {}
    if isinstance(val, dict) and not val:
        val = None
    # Only return values from YAML; do not override from environment variables.
    return val if val is not None else default


# --- TELEGRAM ---
TOKEN = _get("telegram.token")
if not TOKEN:
    raise ValueError("Vui lòng cấu hình 'telegram.token' trong config.yaml")

# --- UPLOADS ---
_upload_dir_val = _get("uploads.dir", env_var="UPLOAD_DIR", default="uploads")
UPLOAD_DIR = str(_upload_dir_val) if _upload_dir_val is not None else "uploads"


def initialize_directories():
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logging.info(f"Đã tạo/kiểm tra thư mục: {UPLOAD_DIR}")

# --- GOOGLE GEMINI ---
_gemini_key_val = _get("google.gemini_api_key")
GEMINI_API_KEY = str(_gemini_key_val) if _gemini_key_val is not None else None
if not GEMINI_API_KEY:
    raise ValueError("Vui lòng cấu hình 'google.gemini_api_key' trong config.yaml")
_genai_configured = False


def _ensure_genai_configured():
    """Configure google.generativeai lazily using the GEMINI_API_KEY from YAML."""
    global _genai_configured
    if _genai_configured:
        return
    genai.configure(api_key=str(GEMINI_API_KEY))
    _genai_configured = True


# ---- Gemini model helpers ----
def get_text_model(model_name: str = "gemini-2.5-flash"):
    """Return a configured text-capable GenerativeModel.

    Default model is fast and supports text I/O.
    """
    _ensure_genai_configured()
    return genai.GenerativeModel(model_name)


def get_vision_model(model_name: str = "gemini-2.5-flash"):
    """Return a configured multimodal GenerativeModel for image+text prompts."""
    _ensure_genai_configured()
    return genai.GenerativeModel(model_name)


# --- DATABASE ---
_db_url_val = _get("database.url")
DATABASE_URL = str(_db_url_val) if _db_url_val is not None else None
# Database pool sizing (configurable)
try:
    DB_POOL_MIN = int(_get("database.pool_min", default=1))
except Exception:
    DB_POOL_MIN = 1
try:
    DB_POOL_MAX = int(_get("database.pool_max", default=10))
except Exception:
    DB_POOL_MAX = 10

# HTTP and LLM timeouts
try:
    HTTP_TIMEOUT = int(_get("http.timeout", default=10))
except Exception:
    HTTP_TIMEOUT = 10
try:
    LLM_DEFAULT_TIMEOUT = int(_get("llm.default_timeout", default=120))
except Exception:
    LLM_DEFAULT_TIMEOUT = 120
