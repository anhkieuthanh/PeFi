from pathlib import Path

# Cache for prompt files to avoid repeated I/O
_PROMPT_CACHE = {}


def get_project_root() -> Path:  # type: ignore
    return Path(__file__).parent.parent.parent  # type: ignore


def get_prompt_path(file_name: str) -> Path:  # type: ignore
    """Lấy đường dẫn đầy đủ đến một file trong thư mục prompts."""
    project_root = get_project_root()
    return project_root / "prompts" / file_name  # type: ignore


def read_promt_file(filepath: Path) -> str:
    """Đọc nội dung file prompt với UTF-8 và caching để tránh I/O lặp lại."""
    filepath_str = str(filepath)
    if filepath_str not in _PROMPT_CACHE:
        with open(filepath, "r", encoding="utf-8") as f:
            _PROMPT_CACHE[filepath_str] = f.read()
    return _PROMPT_CACHE[filepath_str]


def clear_prompt_cache():
    """Clear the prompt cache (useful for development/testing)."""
    global _PROMPT_CACHE
    _PROMPT_CACHE = {}
