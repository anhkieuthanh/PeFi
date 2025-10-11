from pathlib import Path

def get_project_root() -> Path:  # type: ignore
    return Path(__file__).parent.parent.parent  # type: ignore


def get_prompt_path(file_name: str) -> Path:  # type: ignore
    """Lấy đường dẫn đầy đủ đến một file trong thư mục prompts."""
    project_root = get_project_root()
    return project_root / "prompts" / file_name  # type: ignore


def read_promt_file(filepath: Path) -> str:
    """Đọc nội dung file prompt với UTF-8."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()
