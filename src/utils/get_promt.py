from pathlib import Path  
def get_project_root() -> Path: #type: ignore
    return Path(__file__).parent.parent.parent #type: ignore

def get_prompt_path(file_name: str) -> Path: #type: ignore
    """Lấy đường dẫn đầy đủ đến một file trong thư mục prompts."""
    project_root = get_project_root()
    # Dùng toán tử / để nối đường dẫn một cách an toàn
    return project_root / "prompts" / file_name #type: ignore