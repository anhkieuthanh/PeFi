from PIL import Image
from config import client
from .text_processor import read_prompt_from_file
from .get_promt import get_prompt_path

def extract_text(file_path: str) -> str:

    image = Image.open(file_path)
    prompt = read_prompt_from_file(get_prompt_path("image_input.txt"))

    response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt, image])
    print("Extracted text from image:", response.text)
    return response.text # type: ignore