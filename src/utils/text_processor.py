from .get_promt import get_prompt_path

# Robust config import (support running as package or running from src/)
try:
    from src import config
except Exception:
    try:
        import config
    except Exception:
        import sys
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src import config
client = config.client

def read_prompt_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def parse_text_for_info(raw_text: str) -> str:
    prompt = read_prompt_from_file(get_prompt_path("text_input.txt"))
    contents_given = [prompt, raw_text]
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=contents_given) # type: ignore
    result_str = response.text[8:-4] # type: ignore
    return result_str # type: ignore
