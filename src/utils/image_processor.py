from PIL import Image
from .text_processor import read_prompt_from_file
from .get_promt import get_prompt_path

# Import config/client in a robust way (package vs script-run). Prefer package import.
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
import json
def extract_text(file_path: str) -> str:

    image = Image.open(file_path)
    prompt = read_prompt_from_file(get_prompt_path("image_input.txt"))
    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, image])
    processed_text = response.text
    data = json.loads(processed_text[8:-4])
    data["user_id"] = 2
    print("Extracted text from image:", data)
    return data