import sys
import pathlib
import json
import os
import re
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from google import genai

try:
    from ddgs import DDGS  # type: ignore
    from ddgs.exceptions import RatelimitException  # type: ignore
except ImportError:  # pragma: no cover - fallback for older package name
    from duckduckgo_search import DDGS  # type: ignore
    from duckduckgo_search.exceptions import RatelimitException  # type: ignore


DOWNLOAD_DIR = pathlib.Path("downloaded_images")
DEFAULT_PROMPT = "Robot holding a red skateboard"
_URL_CACHE: Dict[str, Optional[str]] = {}
_IMAGE_INFO_CACHE: Dict[str, Optional[Dict[str, object]]] = {}
_RANKED_URL_CACHE: Dict[str, List[str]] = {}
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}

load_dotenv()
_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
_GEMINI_CLIENT: Optional[genai.Client] = None
if _API_KEY:
    try:
        _GEMINI_CLIENT = genai.Client(api_key=_API_KEY)
    except Exception as err:  # pragma: no cover - defensive guard
        print(f"Warning: failed to initialize Gemini client: {err}")
        _GEMINI_CLIENT = None


def _extract_json_object(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _is_image_url(url: str) -> bool:
    try:
        response = requests.head(url, allow_redirects=True, timeout=10, headers=_REQUEST_HEADERS)
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code < 400 and "image/" in content_type:
            return True
        # Some CDNs block HEAD requests; fall back to a lightweight GET probe.
        if response.status_code in (403, 405) or not content_type:
            with requests.get(url, timeout=10, headers=_REQUEST_HEADERS, stream=True) as probe:
                probe.raise_for_status()
                return "image/" in probe.headers.get("Content-Type", "").lower()
        return False
    except requests.RequestException:
        return False


_RELEVANCE_CACHE: Dict[Tuple[str, str], float] = {}


def _normalize_score_value(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"([01](?:\.\d+)?)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(1.0, value))


def _score_image_candidate(prompt: str, description: str) -> Optional[float]:
    if not description:
        return None
    if not _GEMINI_CLIENT:
        return None

    key = (prompt.strip().lower(), description.strip().lower())
    if key in _RELEVANCE_CACHE:
        return _RELEVANCE_CACHE[key]

    instruction = (
        "You evaluate stock imagery for venture pitch decks. Score how well the described image aligns with the request. "
        "Return only JSON like {\"score\": 0.0-1.0}. High scores mean a precise, professional match."
    )
    contents = f"REQUEST:\n{prompt}\n\nIMAGE_DESCRIPTION:\n{description}\n\n{instruction}"

    try:
        response = _GEMINI_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )
    except Exception as err:  # pragma: no cover - defensive guard
        print(f"Warning: failed to score image candidate: {err}")
        return None

    text_response = getattr(response, "text", "")
    payload = _extract_json_object(text_response)
    score = None
    if isinstance(payload, dict):
        candidate = payload.get("score")
        if isinstance(candidate, (int, float)):
            score = float(candidate)
        elif isinstance(candidate, str):
            score = _normalize_score_value(candidate)
    if score is None:
        score = _normalize_score_value(text_response)

    if score is None:
        return None

    clamped = max(0.0, min(1.0, score))
    _RELEVANCE_CACHE[key] = clamped
    return clamped


def _keyword_overlap_score(prompt: str, text: str) -> float:
    if not prompt or not text:
        return 0.0
    prompt_terms = {token for token in re.findall(r"[A-Za-z0-9]+", prompt.lower()) if len(token) > 3}
    if not prompt_terms:
        return 0.0
    text_terms = {token for token in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(token) > 3}
    if not text_terms:
        return 0.0
    overlap = prompt_terms & text_terms
    return len(overlap) / len(prompt_terms)


def gemini_select_image_candidates(prompt: str, max_candidates: int = 6) -> List[Dict[str, object]]:
    if not _GEMINI_CLIENT:
        return []

    instruction = (
        "You curate premium stock photography for venture capital pitch decks. "
        "Return polished, business-ready imagery that would appear in an investor presentation. "
        "Favor horizontal 16:9 shots, clean compositions, modern lighting, and diverse teams. "
        "Only respond with JSON containing an 'images' array of objects with 'url' and 'description'. "
        "Each URL must be a direct HTTPS image link from professional-stock providers (Unsplash, Pexels, Pixabay). "
        "Avoid watermarks, illustrations, memes, or casual snapshots. If uncertain, return an empty array."
    )

    response = _GEMINI_CLIENT.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"PROMPT:\n{prompt}\n\n{instruction}"
    )

    text_response = getattr(response, "text", None)
    if not text_response:
        return []

    payload = _extract_json_object(text_response)
    if not payload:
        return []

    images = payload.get("images") if isinstance(payload, dict) else None
    if not isinstance(images, list):
        return []

    candidates: List[Dict[str, object]] = []
    for candidate in images[:max_candidates]:
        if not isinstance(candidate, dict):
            continue
        url = candidate.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        description = candidate.get("description") or candidate.get("caption") or ""
        candidates.append({"url": url, "description": description})
    return candidates


def gemini_select_image_url(prompt: str, max_candidates: int = 6) -> Optional[str]:
    candidates = gemini_select_image_candidates(prompt, max_candidates=max_candidates)
    if not candidates:
        return None

    scored: List[Tuple[float, str]] = []
    for candidate in candidates:
        url = candidate.get("url")
        if not isinstance(url, str):
            continue
        description = candidate.get("description") or ""
        score = _score_image_candidate(prompt, description)
        if score is None:
            score = _keyword_overlap_score(prompt, description or url)
        scored.append((score or 0.0, url))

    scored.sort(key=lambda item: item[0], reverse=True)

    for _, url in scored:
        if _is_image_url(url):
            return url
    return scored[0][1] if scored else None


def search_image_urls(prompt: str, max_results: int = 6) -> Iterable[Dict[str, str]]:
    # Yield direct image URLs and context returned by DuckDuckGo/ddgs for the prompt
    try:
        with DDGS() as ddgs:
            for result in ddgs.images(prompt, max_results=max_results):
                if not isinstance(result, dict):
                    continue
                url = result.get("image")
                if not url:
                    continue
                title = result.get("title") or ""
                source = result.get("source") or ""
                yield {"url": url, "title": title, "source": source}
    except RatelimitException as err:
        print(f"Image search rate-limited for prompt '{prompt}': {err}")


def download_image(url: str, dest_folder: pathlib.Path) -> Optional[pathlib.Path]:
    # Download an image from URL and return the saved path if successful
    try:
        response = requests.get(url, timeout=15, headers=_REQUEST_HEADERS)
        response.raise_for_status()
    except requests.RequestException as err:
        print(f"Failed to download {url}: {err}")
        return None

    content_type = response.headers.get("Content-Type", "").lower()
    if not content_type.startswith("image/"):
        print(f"Skipping non-image content from {url}")
        return None

    dest_folder.mkdir(parents=True, exist_ok=True)
    file_ext = content_type.split("/")[-1] or "jpg"
    file_path = dest_folder / f"image_{hash(url) & 0xFFFFFFFF:08x}.{file_ext}"

    try:
        with open(file_path, "wb") as f:
            f.write(response.content)
        Image.open(file_path).verify()  # Validate the downloaded file
    except (OSError, UnidentifiedImageError) as err:
        print(f"Downloaded file from {url} is not a valid image: {err}")
        file_path.unlink(missing_ok=True)
        return None

    return file_path


def _select_ranked_image_urls(prompt: str, max_results: int = 6) -> List[str]:
    cache_key = prompt.strip().lower()
    if cache_key in _RANKED_URL_CACHE:
        return _RANKED_URL_CACHE[cache_key]

    candidates: List[Tuple[float, str]] = []
    seen: set[str] = set()

    gemini_candidates = gemini_select_image_candidates(prompt, max_candidates=max_results)
    for candidate in gemini_candidates:
        url = candidate.get("url") if isinstance(candidate, dict) else None
        if not isinstance(url, str):
            continue
        if url in seen:
            continue
        description = candidate.get("description") if isinstance(candidate, dict) else ""
        score = _score_image_candidate(prompt, description or "")
        if score is None:
            score = _keyword_overlap_score(prompt, description or url)
        candidates.append((score or 0.0, url))
        seen.add(url)

    augmented_prompt = f"{prompt} professional business photography, investor pitch deck"
    ddg_seen = 0
    for result in search_image_urls(augmented_prompt, max_results=max_results * 2):
        url = result.get("url")
        if not url or url in seen:
            continue
        title = result.get("title") or ""
        source = result.get("source") or ""
        overlap_score = _keyword_overlap_score(prompt, f"{title} {source}")
        score = overlap_score
        if overlap_score >= 0.25:
            relevance = _score_image_candidate(prompt, title or source)
            if relevance is not None:
                score = max(score, relevance)
        candidates.append((score, url))
        seen.add(url)
        ddg_seen += 1
        if ddg_seen >= max_results:
            break

    candidates.sort(key=lambda item: item[0], reverse=True)
    ranked = [url for _, url in candidates]
    _RANKED_URL_CACHE[cache_key] = ranked
    return ranked


def find_image_url(prompt: str, max_results: int = 6) -> Optional[str]:
    # Return the first direct image URL that matches the prompt (with caching)
    cache_key = prompt.strip().lower()
    if cache_key in _URL_CACHE:
        return _URL_CACHE[cache_key]
    ranked = _select_ranked_image_urls(prompt, max_results=max_results)
    first_url = ranked[0] if ranked else None
    _URL_CACHE[cache_key] = first_url
    return first_url


def get_image_info(prompt: str) -> Optional[Dict[str, object]]:
    # Return image URL and intrinsic size data for the prompt.
    cache_key = prompt.strip().lower()
    cached = _IMAGE_INFO_CACHE.get(cache_key)
    if cached is not None:
        return cached

    ranked = _select_ranked_image_urls(prompt, max_results=8)
    if not ranked:
        _IMAGE_INFO_CACHE[cache_key] = None
        return None

    best_info: Optional[Dict[str, object]] = None
    for url in ranked:
        try:
            response = requests.get(url, timeout=15, headers=_REQUEST_HEADERS)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as img:
                width, height = img.size
        except (requests.RequestException, OSError, UnidentifiedImageError) as err:
            print(f"Failed to inspect image for prompt '{prompt}': {err}")
            continue

        info = {"url": url, "width": width, "height": height}
        aspect_ratio = (width / height) if height else None
        if best_info is None:
            best_info = info
        if aspect_ratio and aspect_ratio >= 1.25:
            best_info = info
            break

    if best_info:
        _IMAGE_INFO_CACHE[cache_key] = best_info
        _URL_CACHE[cache_key] = best_info["url"]
        return best_info

    _IMAGE_INFO_CACHE[cache_key] = None
    return None


def find_image_for_prompt(prompt: str) -> Optional[pathlib.Path]:
    # Search and download the first valid image matching the prompt
    print(f"Searching for images matching: '{prompt}'")
    ranked_urls = _select_ranked_image_urls(prompt, max_results=8)
    for url in ranked_urls:
        print(f"Trying image: {url}")
        saved_path = download_image(url, DOWNLOAD_DIR)
        if saved_path:
            print(f"Saved image to {saved_path}")
            return saved_path

    print("No suitable image found.")
    return None


def main(argv: list[str]) -> None:
    prompt = " ".join(argv) if argv else DEFAULT_PROMPT
    first_url = find_image_url(prompt)
    if first_url:
        print(f"First image URL: {first_url}")
    else:
        print("No image URL found (possibly rate-limited).")
    result = find_image_for_prompt(prompt)
    if result:
        print(f"Image available at: {result.resolve()}")
    else:
        print("Could not locate an image. Try a different prompt.")


if __name__ == "__main__":
    main(sys.argv[1:])
