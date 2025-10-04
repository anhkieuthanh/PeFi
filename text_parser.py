from pydoc import text
import re

def parse_text_for_info(raw_text: str) -> str:
    cleaned_text = re.sub(r'[^\w]', ' ', raw_text, flags=re.UNICODE)
    # Bước 2: Thay thế một hoặc nhiều dấu cách liên tiếp bằng một dấu cách duy nhất.
    # Biểu thức chính quy '\s+' sẽ tìm một hoặc nhiều ký tự khoảng trắng.
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    result_str = "Đây là văn bản đã trích xuất:\n\n" + cleaned_text
    return result_str