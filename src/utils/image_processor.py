from PIL import Image
from .promt import get_prompt_path, read_promt_file
from .path_setup import setup_project_root
import json
# Ensure consistent config import across run contexts
try:
    from src import config
except Exception:
    setup_project_root(__file__)
    from src import config
client = config.client
from datetime import date

def extract_text(file_path: str):

    image = Image.open(file_path)
    prompt = read_promt_file(get_prompt_path("image_input.txt"))
    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, image], config={"response_mime_type": "application/json"})
    data= response.text or "{}"
    data = json.loads(data)  # Convert JSON string to dictionary
    if data["total_amount"] is None:
        return {"raw": "Invalid"}

    # For testing, we set a fixed user_id; in real use this should come from the context
    data["user_id"] = 2
    if not data["bill_date"]:
        data["bill_date"] = date.today().isoformat()
    return data