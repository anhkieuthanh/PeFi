import json
import logging
import time
from io import BytesIO
from typing import Any, Dict, Optional

import requests

from .http_session import get_session
from PIL import Image
from google.api_core.exceptions import DeadlineExceeded

from .path_setup import setup_project_root
from .promt import get_prompt_path, read_promt_file

# Ensure consistent config import across run contexts
try:
    import config  # when running from src/
except Exception:
    setup_project_root(__file__)
    from src import config  # when running from repo root

from datetime import date

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> Dict[str, Any]:
    payload = process_image_from_url(file_path)
    if payload is None:
        return {"raw": "Invalid"}
    prompt = read_promt_file(get_prompt_path("image_input.txt"))

    try:
        model = config.get_vision_model()

        # Use generation_config to enforce JSON output
        generation_config = {"temperature": 0.1, "response_mime_type": "application/json"}

        # Call Gemini with retries on DeadlineExceeded (504)
        def _call_generate():
            return model.generate_content(
                [
                    prompt,
                    {"mime_type": "image/jpeg", "data": payload},
                ],
                generation_config=generation_config,
                request_options={"timeout": 60},
            )

        max_retries = 3
        backoff = 1
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = _call_generate()
                break
            except DeadlineExceeded as e:
                logger.warning(f"Gemini DeadlineExceeded (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    logger.error("Gemini requests timed out after retries")
                    return {"raw": "Invalid"}
                time.sleep(backoff)
                backoff *= 2
        if response is None:
            logger.error("No response from Gemini after retries")
            return {"raw": "Invalid"}
        result_str = response.text if response.text else ""
        logger.info(f"Gemini vision response: {result_str[:500]}")  # Log first 500 chars

        if not result_str or not result_str.strip():
            logger.warning("Gemini returned empty response")
            return {"raw": "Invalid"}

        # Try to extract JSON if wrapped in markdown code blocks
        cleaned_str = result_str.strip()
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]  # Remove ```json
        if cleaned_str.startswith("```"):
            cleaned_str = cleaned_str[3:]  # Remove ```
        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]  # Remove trailing ```
        cleaned_str = cleaned_str.strip()

        data = json.loads(cleaned_str)

        if not isinstance(data, dict):
            logger.warning(f"Gemini response is not a dict: {type(data)}")
            return {"raw": "Invalid"}

        if data.get("total_amount") is None:
            logger.warning("Gemini response missing total_amount")
            return {"raw": "Invalid"}

        # For testing, we set a fixed user_id; in real use this should come from the context
        data["user_id"] = 2
        if not data.get("bill_date"):
            data["bill_date"] = date.today().isoformat()
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.error(f"Raw response was: {result_str[:500]}")
        return {"raw": "Invalid"}
    except Exception as e:
        logger.exception(f"Error in extract_text: {e}")
        return {"raw": "Invalid"}


def process_image_from_url(image_url: str, max_size: int = 1024, quality: int = 70) -> Optional[bytes]:
    """
    :param image_url: Đường link (URL) đến tệp ảnh (thường là link từ Telegram file_path).
    :param max_size: Kích thước tối đa cho cạnh dài nhất của ảnh (pixel). Mặc định là 1024px.
    :param quality: Chất lượng ảnh JPEG/WEBP (1-100). Mặc định là 70.
    :return: Dữ liệu ảnh đã xử lý dưới dạng bytes, hoặc None nếu lỗi.
    """
    try:
        # 1. Tải ảnh từ URL vào bộ nhớ
        session = get_session()
        timeout = getattr(config, "HTTP_TIMEOUT", 10)
        response = session.get(image_url, timeout=timeout)
        response.raise_for_status()

        # 2. Mở ảnh trực tiếp từ dữ liệu nhị phân đã tải
        image_data = BytesIO(response.content)
        img = Image.open(image_data)

        print(f"Kích thước gốc: {img.width}x{img.height}")

        # 3. Tính toán và Thay đổi Kích thước (nếu cần)
        width, height = img.size

        if max(width, height) > max_size:
            ratio = max_size / max(width, height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # Thay đổi kích thước
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"Kích thước mới: {img.width}x{img.height}")
        else:
            print("Ảnh đã có kích thước phù hợp.")

        # 4. Lưu ảnh đã thay đổi kích thước vào một đối tượng BytesIO mới trong bộ nhớ
        output_buffer = BytesIO()

        # Luôn chuyển sang JPEG để tối ưu hóa chất lượng và dung lượng
        # Đây là định dạng tốt nhất để gửi cho các mô hình đa phương thức
        file_format = "JPEG"
        save_params = {"quality": quality, "optimize": True}

        # Lưu vào bộ nhớ
        img.save(output_buffer, format=file_format, **save_params)

        # Đặt con trỏ về đầu để đọc toàn bộ dữ liệu (bytes)
        output_buffer.seek(0)
        processed_bytes = output_buffer.read()

        original_size = len(response.content)
        new_size = len(processed_bytes)

        print(f"Dung lượng gốc: {original_size / 1024:.2f} KB")
        print(
            f"Dung lượng mới: {new_size / 1024:.2f} KB (Giảm {(original_size - new_size) / original_size * 100:.2f}%)"
        )
        print("Đã hoàn tất xử lý ảnh trong bộ nhớ.")

        return processed_bytes

    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi tải ảnh từ URL: {e}")
        return None
    except Exception as e:
        print(f"Đã xảy ra lỗi khi xử lý ảnh: {e}")
        return None
