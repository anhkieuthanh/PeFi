import re

def parse_text_for_info(raw_text: str) -> str:
    """Phân tích văn bản thô để trích xuất thông tin giao dịch."""
    # Hiện tại, hàm này chỉ trả về văn bản thô đã trích xuất 
    result_str = "Đây là văn bản đã trích xuất:\n\n" + raw_text
    return result_str