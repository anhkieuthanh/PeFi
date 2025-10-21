from .promt import get_prompt_path, read_promt_file
import json
import logging
from datetime import date
from typing import Any, Dict
from .path_setup import setup_project_root

# Standardize import of config across run contexts
try:
    import config  # when running from src/
except Exception:
    setup_project_root(__file__)
    from src import config  # when running from repo root

logger = logging.getLogger(__name__)

def parse_text_for_info(raw_text: str) -> Dict[str, Any]:
    try:
        prompt = read_promt_file(get_prompt_path("text_input.txt"))
        model = config.get_text_model()
        
        # Use generation_config to enforce JSON output
        generation_config = {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
        
        response = model.generate_content(
            [prompt, raw_text],
            generation_config=generation_config,
            request_options={"timeout": 60}
        )
        result_str = response.text if response.text else ""
        logger.info(f"Gemini text response: {result_str[:500]}")  # Log first 500 chars
        
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
        
        # For testing, set a fixed user_id; in real use get from context/session
        data["user_id"] = 2
        if not data.get("bill_date"):
            data["bill_date"] = date.today().isoformat()
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.error(f"Raw response was: {result_str[:500]}")
        return {"raw": "Invalid"}
    except Exception as e:
        logger.exception(f"Error in parse_text_for_info: {e}")
        return {"raw": "Invalid"}
