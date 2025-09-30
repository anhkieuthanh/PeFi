import cv2
import numpy as np
from PIL import Image
import pytesseract
from config import TESSERACT_CONFIG, TESSERACT_LANG

def process_image_and_extract_text(file_path: str) -> str:

    image_cv = cv2.imread(file_path)
    if image_cv is None:
        raise ValueError(f"Không thể đọc được file ảnh tại: {file_path}")

    # 1. Phóng to ảnh để tăng độ chi tiết
    scale_percent = 200  # Giảm xuống 200% để cân bằng hiệu năng và độ chính xác
    width = int(image_cv.shape[1] * scale_percent / 100)
    height = int(image_cv.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized_image = cv2.resize(image_cv, dim, interpolation=cv2.INTER_CUBIC)
    
    # 2. Chuyển sang ảnh xám và ảnh nhị phân
    gray_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)
    _, binary_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 3. Phép Erosion để làm dày nét chữ (có thể thử nghiệm với các kernel khác nhau)
    kernel = np.ones((2,2), np.uint8)
    eroded_image = cv2.erode(binary_image, kernel, iterations=1)
    Image.fromarray(eroded_image).show()
    # Chuyển ảnh đã xử lý về dạng PIL để Tesseract đọc
    final_image = Image.fromarray(eroded_image)

    # 4. Trích xuất văn bản bằng Tesseract
    detected_text = pytesseract.image_to_string(
        final_image, 
        lang=TESSERACT_LANG, 
        config=TESSERACT_CONFIG
    )
    
    return detected_text