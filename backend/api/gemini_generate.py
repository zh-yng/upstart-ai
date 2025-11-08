import os
import json
import re
from pathlib import Path
import prompt

from dotenv import load_dotenv
from google import genai

load_dotenv()


def runGenerator(inputPrompt, author=""):
    api_key = os.getenv("VITE_GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your environment or .env file."
        )

    client = genai.Client(api_key=api_key)

    user_prompt = inputPrompt
    author_name = (author or "").strip()

    instruction_block = prompt.givePrompt()
    contents = f"USER PROMPT:\n{user_prompt}\n\n" + instruction_block

    if author_name:
        contents += (
            f"\nPresenter name: {author_name}. Use this exact value only for title_slide.author."
        )
    else:
        contents += "\nNo presenter name provided; omit the author field entirely."

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=contents
    )

    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if not json_match:
        raise ValueError("No valid JSON found in Gemini response:\n" + response.text)

    try:
        presentation_json = json.loads(json_match.group(0), strict=False)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from Gemini response:\n{response.text}\nError: {e}")

    if author_name:
        presentation_json["title_slide"]["author"] = author_name
    else:
        presentation_json["title_slide"].pop("author", None)

    output_path = Path(__file__).resolve().parent / "slides.json"
    if output_path.exists():
        output_path.unlink()
    output_path.write_text(json.dumps(presentation_json, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"Presentation JSON saved successfully to: {output_path}")
