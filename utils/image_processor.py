from PIL import Image
from src.config import client
from utils.text_processor import read_prompt_from_file

def extract_text(file_path: str) -> str:

    image = Image.open(file_path)
    prompt = read_prompt_from_file("promt/image_input.txt")

    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, image])
    print("Extracted text from image:", response.text)
    return response.text # type: ignore