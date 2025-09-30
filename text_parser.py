# text_parser.py
import re

def parse_text_for_info(raw_text: str) -> str:
    """
    Sử dụng Regex để trích xuất ngày tháng và giá tiền từ văn bản thô.
    
    Args:
        raw_text: Chuỗi văn bản từ Tesseract.
        
    Returns:
        Chuỗi kết quả đã được định dạng.
    """
    print(f"Văn bản gốc từ Tesseract:\n----------------\n{raw_text}\n----------------")
    
    date_pattern = r"\b\d{2}[/.-]\d{2}[/.-]\d{4}\b"
    price_pattern = r"[\d.,]+\s*(?:VNĐ|VND|đ|d)"
    
    dates_found = re.findall(date_pattern, raw_text)
    prices_found = re.findall(price_pattern, raw_text)
    
    if not dates_found and not prices_found:
        return "Tôi đã đọc văn bản nhưng không tìm thấy thông tin giá tiền hoặc ngày tháng rõ ràng."

    # Xây dựng chuỗi kết quả
    result_str = "Tôi đã tìm thấy các thông tin sau:\n\n"
    
    if dates_found:
        result_str += f"📅 **Ngày tháng:** {dates_found[0]}\n"
    else:
        result_str += "   (Không tìm thấy ngày tháng)\n"
        
    if prices_found:
        result_str += "💰 **Giá tiền:**\n"
        for price in prices_found:
            result_str += f"   - {price.strip()}\n"
    else:
        result_str += "   (Không tìm thấy giá tiền)\n"
        
    return result_str