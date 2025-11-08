import sys
import io
import pathlib
from typing import Dict, Iterable, Optional

import requests
from PIL import Image, UnidentifiedImageError

try:
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover - alternate package name
    from duckduckgo_search import DDGS  # type: ignore

DOWNLOAD_DIR = pathlib.Path("downloaded_images")
DEFAULT_PROMPT = "Modern business meeting"
_URL_CACHE: Dict[str, Optional[str]] = {}
_IMAGE_INFO_CACHE: Dict[str, Optional[Dict[str, object]]] = {}
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    )
}


def search_image_urls(prompt: str, max_results: int = 6) -> Iterable[str]:
    with DDGS() as ddgs:
        for result in ddgs.images(prompt, max_results=max_results):
            if not isinstance(result, dict):
                continue
            url = result.get("image")
            if isinstance(url, str) and url.startswith("http"):
                yield url


def _download_bytes(url: str) -> Optional[bytes]:
    try:
        response = requests.get(url, timeout=10, headers=_REQUEST_HEADERS)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def _validate_image(payload: bytes) -> Optional[tuple[int, int]]:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            return image.size
    except (OSError, UnidentifiedImageError):
        return None


def find_image_url(prompt: str) -> Optional[str]:
    key = prompt.strip().lower()
    if key in _URL_CACHE:
        return _URL_CACHE[key]

    for url in search_image_urls(prompt, max_results=6):
        payload = _download_bytes(url)
        if not payload:
            continue
        if _validate_image(payload):
            _URL_CACHE[key] = url
            return url

    _URL_CACHE[key] = None
    return None


def get_image_info(prompt: str) -> Optional[Dict[str, object]]:
    key = prompt.strip().lower()
    cached = _IMAGE_INFO_CACHE.get(key)
    if cached is not None:
        return cached

    url = find_image_url(prompt)
    if not url:
        _IMAGE_INFO_CACHE[key] = None
        return None

    payload = _download_bytes(url)
    if not payload:
        _IMAGE_INFO_CACHE[key] = None
        return None

    size = _validate_image(payload)
    if not size:
        _IMAGE_INFO_CACHE[key] = None
        return None

    width, height = size
    info = {"url": url, "width": width, "height": height}
    _IMAGE_INFO_CACHE[key] = info
    return info


def download_image(url: str, dest_folder: pathlib.Path) -> Optional[pathlib.Path]:
    payload = _download_bytes(url)
    if not payload or not _validate_image(payload):
        return None

    dest_folder.mkdir(parents=True, exist_ok=True)
    file_path = dest_folder / f"image_{hash(url) & 0xFFFFFFFF:08x}.jpg"
    file_path.write_bytes(payload)
    return file_path


def main(argv: list[str]) -> None:
    prompt = " ".join(argv) if argv else DEFAULT_PROMPT
    url = find_image_url(prompt)
    if url:
        print(f"Found image URL: {url}")
        saved = download_image(url, DOWNLOAD_DIR)
        if saved:
            print(f"Saved image to {saved.resolve()}")
        else:
            print("Failed to download the image.")
    else:
        print("No image URL found.")


if __name__ == "__main__":
    main(sys.argv[1:])
