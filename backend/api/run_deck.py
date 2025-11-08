"""Utility wrapper for generating a deck from an arbitrary prompt."""

from __future__ import annotations

import argparse

import slide_create


def run_deck(prompt: str, author: str | None = None, include_images: bool = True) -> str:
    """Generate a Google Slides deck for the given prompt and return its URL."""
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    return slide_create.main(
        prompt.strip(),
        author=author,
        include_images=include_images,
        open_browser=False,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a deck from the provided prompt.")
    parser.add_argument("prompt", help="Startup idea or pitch description that drives the deck content.")
    parser.add_argument("--author", help="Presenter name to appear on the title slide.")
    parser.add_argument(
        "--no-images",
        dest="include_images",
        action="store_false",
        help="Skip image generation for content slides.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    url = run_deck(args.prompt, author=args.author, include_images=args.include_images)
    print(f"Presentation created: {url}")
