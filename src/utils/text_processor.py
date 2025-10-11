from .promt import get_prompt_path, read_promt_file
import json
from datetime import date
from typing import Any, Dict, Union
from .path_setup import setup_project_root

# Standardize import of config across run contexts
try:
    from src import config
except Exception:
    setup_project_root(__file__)
    from src import config
client = config.client

def parse_text_for_info(raw_text: str) -> Union[Dict[str, Any], str]:
    prompt = read_promt_file(get_prompt_path("text_input.txt"))
    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, raw_text], config={"response_mime_type": "application/json"})
    result_str = response.text
    data = json.loads(result_str)  # Convert JSON string to dictionary
    print(data)
    if data["total_amount"] is None:
        return {"raw": "Invalid"}
    # For testing, set a fixed user_id; in real use get from context/session
    data["user_id"] = 2
    if not data["bill_date"]:
        data["bill_date"] = date.today().isoformat()
    return data
