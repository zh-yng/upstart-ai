import slide_create


PROMPT = "A greenhouse tree store that sells saplings"
AUTHOR = None  # Replace with a presenter name or keep None
INCLUDE_IMAGES = True  # Set to False to skip image lookup


if __name__ == "__main__":
    slide_create.main(PROMPT, author=AUTHOR, include_images=INCLUDE_IMAGES)
