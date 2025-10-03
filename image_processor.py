import cv2
import numpy as np
import easyocr

# Khởi tạo EasyOCR reader một lần để tái sử dụng
reader = easyocr.Reader(['ch_sim','en'], gpu=False)
def process_image_and_extract_text(file_path: str) -> str:

    image_cv = cv2.imread(file_path)
    if image_cv is None:
        raise ValueError(f"Không thể đọc được file ảnh tại: {file_path}")
    # Xoay ảnh nếu ảnh nằm ngang
    if image_cv.shape[0] < image_cv.shape[1]:
        image_cv = cv2.rotate(image_cv, cv2.ROTATE_90_CLOCKWISE)

    # Trích xuất văn bản
    result = reader.readtext(np.array(image_cv))
    detected_text = ' '.join([text[1] for text in result])
    print("Detected text:", detected_text)
    return detected_text