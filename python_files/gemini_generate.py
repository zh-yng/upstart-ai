import os
import json
import re
from pathlib import Path
from typing import Optional

import prompt
from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY is not set. Add it to your environment or .env file."
    )

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

client = genai.Client(api_key=API_KEY)


def _normalize_quotes(value: str) -> str:
    if not isinstance(value, str):
        return value
    return (
        value.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )


def _escape_inner_quotes(json_text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False

    for idx, char in enumerate(json_text):
        if char == '"' and not escape:
            if in_string:
                look_ahead_index = idx + 1
                while look_ahead_index < len(json_text) and json_text[look_ahead_index].isspace():
                    look_ahead_index += 1
                next_char = json_text[look_ahead_index] if look_ahead_index < len(json_text) else ""
                if next_char and next_char not in ",}]":
                    result.append('\\"')
                    escape = False
                    continue
                in_string = False
                result.append(char)
            else:
                in_string = True
                result.append(char)
        else:
            result.append(char)

        if char == "\\" and not escape:
            escape = True
        elif escape:
            escape = False

    return "".join(result)


def _extract_json_block(response_text: str) -> str:
    match = _JSON_BLOCK_PATTERN.search(response_text)
    if not match:
        raise ValueError("No valid JSON found in Gemini response:\n" + response_text)
    return match.group(0)


def _parse_response_json(response_text: str) -> dict:
    json_text = _extract_json_block(response_text)
    normalized = _normalize_quotes(json_text)

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        repaired = _escape_inner_quotes(normalized)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as err:
            raise ValueError(
                "Failed to parse JSON from Gemini response."\
                f"\nError: {err}"\
                f"\nResponse snippet:\n{response_text}"
            ) from err


def generate_presentation_json(user_prompt: str, author_name: Optional[str] = None) -> dict:
    if not user_prompt:
        raise ValueError("user_prompt must not be empty")

    instruction_block = prompt.givePrompt()

    contents = f"USER PROMPT:\n{user_prompt}\n\n" + instruction_block

    if author_name:
        contents += (
            f"\nPresenter name: {author_name}. Use this exact value only for title_slide.author."
        )
    else:
        contents += "\nNo presenter name provided; omit the author field entirely."

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    presentation_json = _parse_response_json(response.text)

    title_slide = presentation_json.setdefault("title_slide", {})
    if author_name:
        title_slide["author"] = author_name
    else:
        title_slide.pop("author", None)

    if "presentation_title" not in presentation_json:
        presentation_json["presentation_title"] = user_prompt.strip() or "Untitled Presentation"

    return presentation_json


def save_presentation_json(presentation_json: dict, output_path: Optional[Path] = None) -> Path:
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "slides.json"
    output_path.write_text(
        json.dumps(presentation_json, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def generate_and_save_via_prompt(output_path: Optional[Path] = None) -> Path:
    user_prompt = input("Enter your startup idea: ")
    author_name = input("Enter the author/presenter name (optional): ")
    presentation_json = generate_presentation_json(user_prompt, author_name or None)
    path = save_presentation_json(presentation_json, output_path=output_path)
    print(f"Presentation JSON saved successfully to: {path}")
    return path


if __name__ == "__main__":
    generate_and_save_via_prompt()
