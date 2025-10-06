from config import client
from .get_promt import get_prompt_path

def read_prompt_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def parse_text_for_info(raw_text: str) -> str:
    prompt = read_prompt_from_file(get_prompt_path("text_input.txt"))
    contents_given = [prompt, raw_text]
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=contents_given) # type: ignore
    result_str = response.text # type: ignore
    return result_str # type: ignore
