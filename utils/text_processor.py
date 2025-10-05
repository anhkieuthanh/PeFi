from src.config import client

prompt ="Extract all text fields from the uploaded string. The ouput must be in a single JSON object with the following keys: 1. Transaction  (Thu hoặc Chi), 2. Amount, 3. Date (Lấy ngày gửi tin), 4. Category(ăn uống/xăng xe,.....). Ensure the extracted numeric values are in plain numbers (without commas or currency symbols) where appropriate, and text is accurately transcribed."

def parse_text_for_info(raw_text: str) -> str:
    contents_given = [prompt, raw_text]
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=contents_given) # type: ignore
    result_str = response.text # type: ignore
    return result_str # type: ignore

def read_prompt_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()