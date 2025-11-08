import os
import json
import re
import uuid
import webbrowser
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import gemini_generate
import image_generate



# Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive.file",
]


LAYOUT_MAP = {
    "TITLE": "TITLE",
    "TITLE_AND_BODY": "TITLE_AND_BODY",
    "TITLE_AND_TWO_COLUMNS": "TITLE_AND_TWO_COLUMNS",
    "SECTION_TITLE_AND_DESCRIPTION": "SECTION_TITLE_AND_DESCRIPTION",
    "SECTION_HEADER": "SECTION_HEADER",
    "MAIN_POINT": "MAIN_POINT",
    "MAIN_POINT_AND_DETAILS": "MAIN_POINT_AND_DETAILS",
    "BIG_NUMBER": "BIG_NUMBER",
    "ONE_COLUMN_TEXT": "TITLE_AND_BODY",
    "COMPARISON": "TITLE_AND_TWO_COLUMNS",
}


def resolve_layout(layout_name: str) -> str:
    normalized = (layout_name or "TITLE_AND_BODY").upper()
    layout = LAYOUT_MAP.get(normalized)
    if not layout:
        print(f"Warning: layout '{layout_name}' not recognized. Using TITLE_AND_BODY layout.")
        layout = "TITLE_AND_BODY"
    return layout


def determine_font_size(text: str, base_size: int, min_size: int = 12) -> int:
    if not text:
        return base_size
    cleaned = text.strip()
    if not cleaned:
        return base_size
    lines = cleaned.count("\n") + 1
    words = len(cleaned.split())
    chars = len(cleaned)
    size = base_size
    if lines > 6 or words > 120 or chars > 600:
        size -= 4
    if lines > 10 or words > 200 or chars > 900:
        size -= 4
    if lines > 14 or words > 260 or chars > 1100:
        size -= 4
    return max(size, min_size)


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return text

    def heading_replacement(match: re.Match) -> str:
        heading = match.group(1).strip()
        return f"{heading} - "

    cleaned = re.sub(r"\*\*(.+?)\*\*:\s*", heading_replacement, text)
    cleaned = re.sub(r"\*\*(.+?)\*\*", lambda m: m.group(1).strip(), cleaned)
    cleaned = cleaned.replace(" -  - ", " - ")
    return cleaned


def load_slides_data(json_path):
    """Load presentation data from a JSON file."""
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "slides" not in data or not isinstance(data["slides"], list):
        raise ValueError("JSON must contain a 'slides' list")
    return data


def hex_to_rgb_color(hex_value):
    hex_value = (hex_value or "").strip().lstrip("#")
    if len(hex_value) != 6:
        return None
    try:
        red = int(hex_value[0:2], 16) / 255.0
        green = int(hex_value[2:4], 16) / 255.0
        blue = int(hex_value[4:6], 16) / 255.0
    except ValueError:
        return None
    return {"red": red, "green": green, "blue": blue}


def solid_fill(hex_value, opacity=None):
    rgb = hex_to_rgb_color(hex_value)
    if not rgb:
        return None
    fill = {"color": {"rgbColor": rgb}}
    if opacity is not None:
        try:
            alpha = float(opacity)
        except (TypeError, ValueError):
            alpha = None
        if alpha is not None:
            fill["alpha"] = max(0.0, min(1.0, alpha))
    return fill


def to_float(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_positive_float(value, default=None):
    result = to_float(value, default)
    if result is None:
        return default
    return result if result >= 0 else default


def alignment_to_paragraph_value(alignment, fallback="START"):
    mapping = {
        "LEFT": "START",
        "START": "START",
        "CENTER": "CENTER",
        "MIDDLE": "CENTER",
        "RIGHT": "END",
        "END": "END",
        "JUSTIFIED": "JUSTIFIED",
        "JUSTIFY": "JUSTIFIED",
    }
    key = (alignment or "").upper().strip()
    return mapping.get(key, fallback)




def get_credentials():
    #Authenticate and return Google API credentials.
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        stored_scopes = set(creds.scopes or [])
        if not stored_scopes.issuperset(set(SCOPES)):
            creds = None
            try:
                os.remove("token.json")
            except OSError:
                pass
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def create_presentation(service, title):
    #Create a new Google Slides presentation.
    presentation = service.presentations().create(body={"title": title}).execute()
    presentation_id = presentation.get("presentationId")
    return presentation_id


def prepare_body_text_segment(text_value):
    if not isinstance(text_value, str):
        return "", False

    stripped = text_value.strip("\n")
    if not stripped:
        return text_value, False

    lines = [line for line in stripped.splitlines() if line.strip()]
    bullet_pattern = re.compile(r"^(?:[-\u2022*\u2013]\s+|\d+[.)]\s+)")

    if lines and all(bullet_pattern.match(line.strip()) for line in lines):
        cleaned_lines = [bullet_pattern.sub("", line.strip()) for line in stripped.splitlines()]
        processed = "\n".join(cleaned_lines)
        return processed, True

    return text_value, False


def apply_accent_elements(slide_id, slide_style, page_size, deck_theme=None):
    accent_source = None
    if isinstance(slide_style, dict) and slide_style.get("accent_band"):
        accent_source = slide_style.get("accent_band")
    elif isinstance(deck_theme, dict) and deck_theme.get("accent_band"):
        accent_source = deck_theme.get("accent_band")

    if not isinstance(accent_source, dict):
        return []

    color_value = accent_source.get("color")
    if not color_value:
        fallback_color = None
        if isinstance(slide_style, dict):
            fallback_color = slide_style.get("accent_color") or slide_style.get("title_color")
        if not fallback_color and isinstance(deck_theme, dict):
            fallback_color = deck_theme.get("accent_color") or deck_theme.get("palette", {}).get("accent") if isinstance(deck_theme.get("palette"), dict) else None
        color_value = fallback_color

    solid_color = solid_fill(color_value) if color_value else None
    if not solid_color:
        return []

    if not isinstance(page_size, dict):
        return []

    width_info = page_size.get("width") or {}
    height_info = page_size.get("height") or {}
    page_width = width_info.get("magnitude")
    page_height = height_info.get("magnitude")
    unit = width_info.get("unit") or height_info.get("unit") or "PT"

    if not page_width or not page_height:
        return []

    position = (accent_source.get("position") or "TOP").upper()
    thickness_value = accent_source.get("thickness")

    def compute_thickness(value, total):
        numeric = to_positive_float(value, None)
        if numeric is None:
            return None
        if numeric < 1:
            return total * numeric
        return numeric

    default_thickness = page_height * 0.025 if position in ("TOP", "BOTTOM") else page_width * 0.02
    band_thickness = compute_thickness(thickness_value, page_height if position in ("TOP", "BOTTOM") else page_width)
    thickness = band_thickness if band_thickness else default_thickness

    if thickness <= 0:
        return []

    band_id = f"Accent_{uuid.uuid4().hex[:12]}"

    element_properties = {
        "pageObjectId": slide_id,
        "size": {
            "width": {"magnitude": page_width if position in ("TOP", "BOTTOM") else thickness, "unit": unit},
            "height": {"magnitude": thickness if position in ("TOP", "BOTTOM") else page_height, "unit": unit},
        },
        "transform": {
            "scaleX": 1,
            "scaleY": 1,
            "shearX": 0,
            "shearY": 0,
            "translateX": 0,
            "translateY": 0,
            "unit": unit,
        },
    }

    if position == "BOTTOM":
        element_properties["transform"]["translateY"] = page_height - thickness
    elif position == "RIGHT":
        element_properties["transform"]["translateX"] = page_width - thickness
    elif position == "CENTER":
        element_properties["transform"]["translateY"] = (page_height - thickness) / 2 if position in ("TOP", "BOTTOM", "CENTER") else element_properties["transform"]["translateY"]

    create_shape_request = {
        "createShape": {
            "objectId": band_id,
            "shapeType": "RECTANGLE",
            "elementProperties": element_properties,
        }
    }

    update_fill_request = {
        "updateShapeProperties": {
            "objectId": band_id,
            "shapeProperties": {
                "shapeBackgroundFill": {
                    "solidFill": solid_color
                }
            },
            "fields": "shapeBackgroundFill.solidFill"
        }
    }

    return [create_shape_request, update_fill_request]


def fill_slide(service, presentation_id, slide_id, title_text, body_text, slide_style=None, is_title_slide=False, image_info=None, deck_theme=None, page_size=None):
    #Fill an existing slide (by ID) with title/body text.
    slide = service.presentations().pages().get(
        presentationId=presentation_id, pageObjectId=slide_id
    ).execute()

    title_id = None
    title_has_text = False
    title_placeholder = None
    body_placeholders = []

    for element in slide.get("pageElements", []):
        shape = element.get("shape")
        if not shape:
            continue
        placeholder = shape.get("placeholder")
        placeholder_type = placeholder.get("type") if placeholder else None
        if placeholder_type in ("TITLE", "CENTERED_TITLE"):
            title_id = element["objectId"]
            title_placeholder = element
            if shape.get("text") and shape["text"].get("textElements"):
                title_has_text = True
        elif placeholder_type in ("SUBTITLE", "BODY", "CENTERED_SUBTITLE"):
            has_text = bool(shape.get("text") and shape["text"].get("textElements"))
            body_placeholders.append({
                "objectId": element["objectId"],
                "has_text": has_text,
                "size": element.get("size"),
                "transform": element.get("transform"),
                "placeholder_type": placeholder_type,
            })

    text_requests = []

    if deck_theme and isinstance(deck_theme, dict):
        theme_style = {}
        defaults = deck_theme.get("defaults") or {}
        if isinstance(defaults, dict):
            theme_style.update(defaults)

        palette = deck_theme.get("palette") or {}
        if isinstance(palette, dict):
            theme_style.setdefault("background_color", palette.get("background") or palette.get("surface"))
            theme_style.setdefault("title_color", palette.get("text_on_light") or palette.get("primary_text"))
            theme_style.setdefault("body_color", palette.get("body_text") or palette.get("text_on_light"))
            theme_style.setdefault("accent_color", palette.get("accent") or palette.get("primary"))

        typography = deck_theme.get("typography") or {}
        if isinstance(typography, dict):
            theme_style.setdefault("title_font", typography.get("title_font") or typography.get("display_font"))
            theme_style.setdefault("body_font", typography.get("body_font"))
            theme_style.setdefault("subtitle_font", typography.get("subtitle_font") or typography.get("body_font"))

        if deck_theme.get("background_style") and isinstance(deck_theme.get("background_style"), dict):
            theme_style.setdefault("background_style", deck_theme.get("background_style"))

        if deck_theme.get("text_alignment"):
            theme_style.setdefault("text_alignment", deck_theme.get("text_alignment"))

        if deck_theme.get("body_line_spacing"):
            theme_style.setdefault("body_line_spacing", deck_theme.get("body_line_spacing"))

        if slide_style:
            combined_style = dict(theme_style)
            combined_style.update(slide_style)
            slide_style = combined_style
        elif theme_style:
            slide_style = dict(theme_style)

    if isinstance(title_text, str):
        normalized_title = normalize_text(title_text) or ""
        title_text_to_apply = normalized_title.strip()
    else:
        title_text_to_apply = ""

    if isinstance(body_text, list):
        raw_segments = [normalize_text(str(part)) if part is not None else "" for part in body_text]
    else:
        raw_segments = [normalize_text(str(body_text)) if body_text is not None else ""]

    if title_text_to_apply and len(title_text_to_apply) > 30 and raw_segments:
        for idx, segment in enumerate(raw_segments):
            if segment:
                raw_segments[idx] = segment if segment.startswith("\n") else f"\n{segment}"
                break
        else:
            raw_segments[0] = "\n"

    image_placeholder = None
    text_placeholders = list(body_placeholders)

    if image_info and len(body_placeholders) >= 2:
        orientation = (image_info.get("position") or "RIGHT").upper()
        sorted_by_x = sorted(
            body_placeholders,
            key=lambda item: item.get("transform", {}).get("translateX", 0.0)
        )
        sorted_body_only = [p for p in sorted_by_x if p.get("placeholder_type") == "BODY"]
        candidate = None
        if len(sorted_body_only) >= 2:
            candidate = sorted_body_only[0] if orientation == "LEFT" else sorted_body_only[-1]

        if candidate:
            remaining = [p for p in body_placeholders if p is not candidate]
            if remaining:
                image_placeholder = candidate
                text_placeholders = remaining
        # if no BODY placeholder was suitable, skip image insertion
        if not image_placeholder:
            image_info = None

    text_assignments = {}
    if text_placeholders:
        body_only_placeholders = [p for p in text_placeholders if p.get("placeholder_type") == "BODY"]
        target_placeholders = body_only_placeholders if body_only_placeholders else list(text_placeholders)
        text_slot_count = len(target_placeholders)
        if text_slot_count > 0:
            if len(raw_segments) > text_slot_count:
                keep = text_slot_count - 1
                if keep < 0:
                    keep = 0
                front = raw_segments[:keep]
                overflow = raw_segments[keep:]
                prepared_segments = front + ["\n\n".join(overflow)]
            else:
                prepared_segments = list(raw_segments)
            while len(prepared_segments) < text_slot_count:
                prepared_segments.append("")
            ordered_targets = sorted(
                target_placeholders,
                key=lambda item: item.get("transform", {}).get("translateX", 0.0),
                reverse=True,
            )
            for idx, placeholder in enumerate(ordered_targets):
                processed_text, needs_bullet = prepare_body_text_segment(prepared_segments[idx])
                text_assignments[placeholder["objectId"]] = {
                    "text": processed_text,
                    "needs_bullet": needs_bullet,
                }
        for placeholder in text_placeholders:
            text_assignments.setdefault(placeholder["objectId"], {"text": "", "needs_bullet": False})

    if title_id:
        if title_has_text:
            text_requests.append({
                "deleteText": {
                    "objectId": title_id,
                    "textRange": {"type": "ALL"}
                }
            })
        if title_text_to_apply:
            text_requests.append({
                "insertText": {
                    "objectId": title_id,
                    "insertionIndex": 0,
                    "text": title_text_to_apply
                }
            })

    for placeholder in body_placeholders:
        obj_id = placeholder["objectId"]
        has_text = placeholder["has_text"]
        assignment = text_assignments.get(obj_id) or {"text": "", "needs_bullet": False}
        text_value = assignment.get("text", "")
        trimmed_value = text_value.strip()

        if has_text:
            text_requests.append({
                "deleteText": {
                    "objectId": obj_id,
                    "textRange": {"type": "ALL"}
                }
            })
        if trimmed_value:
            text_requests.append({
                "insertText": {
                    "objectId": obj_id,
                    "insertionIndex": 0,
                    "text": text_value
                }
            })

    style_requests = []
    bullet_requests = []

    if slide_style:
        background_style = slide_style.get("background_style") if isinstance(slide_style.get("background_style"), dict) else None
        if background_style and background_style.get("type", "").upper() == "GRADIENT":
            colors = background_style.get("colors") or []
            solid_color = None
            for candidate in colors:
                solid_color = solid_fill(candidate, background_style.get("opacity"))
                if solid_color:
                    break
            if solid_color:
                style_requests.append({
                    "updatePageProperties": {
                        "objectId": slide_id,
                        "pageProperties": {
                            "pageBackgroundFill": {
                                "solidFill": solid_color
                            }
                        },
                        "fields": "pageBackgroundFill.solidFill"
                    }
                })
        else:
            background_color = slide_style.get("background_color")
            rgb_background = hex_to_rgb_color(background_color)
            if rgb_background:
                style_requests.append({
                    "updatePageProperties": {
                        "objectId": slide_id,
                        "pageProperties": {
                            "pageBackgroundFill": {
                                "solidFill": {
                                    "color": {"rgbColor": rgb_background}
                                }
                            }
                        },
                        "fields": "pageBackgroundFill.solidFill.color"
                    }
                })

        title_font = slide_style.get("title_font")
        title_color = slide_style.get("title_color") or slide_style.get("accent_color")
        body_font_key = "subtitle_font" if is_title_slide else "body_font"
        body_color_key = "subtitle_color" if is_title_slide else "body_color"
        body_font = slide_style.get(body_font_key)
        body_color = slide_style.get(body_color_key) or slide_style.get("accent_color")
        title_alignment = slide_style.get("title_alignment") or slide_style.get("text_alignment")
        body_alignment = slide_style.get("body_alignment") or slide_style.get("text_alignment")
        body_line_spacing = to_float(slide_style.get("body_line_spacing"))

        if title_id and title_text_to_apply:
            title_style = {}
            fields = []
            if title_font:
                title_style["fontFamily"] = title_font
                fields.append("fontFamily")
            rgb_title = hex_to_rgb_color(title_color)
            if rgb_title:
                title_style["foregroundColor"] = {"opaqueColor": {"rgbColor": rgb_title}}
                fields.append("foregroundColor")
            title_font_size = determine_font_size(title_text_to_apply, 36, 18)
            title_style["fontSize"] = {"magnitude": title_font_size, "unit": "PT"}
            fields.append("fontSize")
            style_requests.append({
                "updateTextStyle": {
                    "objectId": title_id,
                    "textRange": {"type": "ALL"},
                    "style": title_style,
                    "fields": ",".join(fields)
                }
            })
            alignment_value = alignment_to_paragraph_value(title_alignment)
            style_requests.append({
                "updateParagraphStyle": {
                    "objectId": title_id,
                    "textRange": {"type": "ALL"},
                    "style": {"alignment": alignment_value},
                    "fields": "alignment"
                }
            })

        for placeholder in body_placeholders:
            obj_id = placeholder["objectId"]
            assignment = text_assignments.get(obj_id) or {"text": "", "needs_bullet": False}
            text_value = assignment.get("text", "")
            if not text_value.strip():
                continue

            body_style = {}
            fields = []
            if body_font:
                body_style["fontFamily"] = body_font
                fields.append("fontFamily")
            rgb_body = hex_to_rgb_color(body_color)
            if rgb_body:
                body_style["foregroundColor"] = {"opaqueColor": {"rgbColor": rgb_body}}
                fields.append("foregroundColor")
            body_font_size = determine_font_size(text_value, 20 if not is_title_slide else 18, 12)
            body_style["fontSize"] = {"magnitude": body_font_size, "unit": "PT"}
            fields.append("fontSize")
            style_requests.append({
                "updateTextStyle": {
                    "objectId": obj_id,
                    "textRange": {"type": "ALL"},
                    "style": body_style,
                    "fields": ",".join(fields)
                }
            })
            alignment_value = alignment_to_paragraph_value(body_alignment)
            paragraph_fields = ["alignment"]
            paragraph_style = {"alignment": alignment_value}
            if body_line_spacing:
                paragraph_style["lineSpacing"] = body_line_spacing
                paragraph_fields.append("lineSpacing")
            style_requests.append({
                "updateParagraphStyle": {
                    "objectId": obj_id,
                    "textRange": {"type": "ALL"},
                    "style": paragraph_style,
                    "fields": ",".join(sorted(set(paragraph_fields)))
                }
            })

            if assignment.get("needs_bullet"):
                bullet_requests.append({
                    "createParagraphBullets": {
                        "objectId": obj_id,
                        "textRange": {"type": "ALL"},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
                    }
                })


    adjustment = 0.0
    if title_placeholder and body_placeholders and title_text_to_apply:
        line_count = title_text_to_apply.count("\n") + 1
        extra_lines = max(0, line_count - 1)
        over_length = max(0, len(title_text_to_apply.strip()) - 30)
        adjustment = max(extra_lines * 36.0, over_length * 1.2)

    if adjustment > 0:
        for placeholder in body_placeholders:
            transform = placeholder.get("transform") or {}
            transform_copy = transform.copy() if transform else {}
            current_y = transform.get("translateY", 0)
            transform_copy["translateY"] = current_y + adjustment
            transform_copy.setdefault("unit", transform.get("unit", "PT"))
            placeholder["transform"] = transform_copy
            text_requests.append({
                "updatePageElementTransform": {
                    "objectId": placeholder["objectId"],
                    "applyMode": "RELATIVE",
                    "transform": {
                        "scaleX": 1,
                        "shearX": 0,
                        "translateX": 0,
                        "shearY": 0,
                        "scaleY": 1,
                        "translateY": adjustment,
                        "unit": transform.get("unit", "PT"),
                    }
                }
            })

    accent_requests = apply_accent_elements(slide_id, slide_style, page_size, deck_theme=deck_theme)

    all_requests = text_requests + style_requests + bullet_requests + accent_requests

    if all_requests:
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": all_requests}
        ).execute()

    return image_placeholder


def insert_image_on_slide(service, presentation_id, slide_id, placeholder_info, image_spec):
    # Insert an image on the slide using the geometry from a predefined placeholder only.
    image_prompt = (image_spec or {}).get("prompt") if isinstance(image_spec, dict) else image_spec
    if not image_prompt:
        return False

    if not placeholder_info:
        print(f"Warning: no image placeholder available for prompt '{image_prompt}'. Skipping image placement to avoid overlapping text.")
        return False

    image_data = image_generate.get_image_info(image_prompt)
    if not image_data or not image_data.get("url"):
        print(f"Warning: unable to locate image for prompt '{image_prompt}'.")
        return False

    image_url = image_data["url"]
    img_width = image_data.get("width")
    img_height = image_data.get("height")

    element_properties = {"pageObjectId": slide_id}
    placeholder_size = placeholder_info.get("size") if placeholder_info else None
    placeholder_transform = placeholder_info.get("transform") if placeholder_info else None
    placeholder_id = placeholder_info.get("objectId") if placeholder_info else None

    width_info = (placeholder_size or {}).get("width", {})
    height_info = (placeholder_size or {}).get("height", {})
    placeholder_width = width_info.get("magnitude")
    placeholder_height = height_info.get("magnitude")
    width_unit = width_info.get("unit") or height_info.get("unit") or "PT"
    height_unit = height_info.get("unit") or width_info.get("unit") or "PT"

    adjusted_width = placeholder_width
    adjusted_height = placeholder_height
    aspect_ratio = None

    if img_width and img_height and img_width > 0 and img_height > 0:
        aspect_ratio = img_height / img_width
        if placeholder_width and placeholder_height:
            adjusted_width = placeholder_width
            adjusted_height = adjusted_width * aspect_ratio
            if adjusted_height and placeholder_height and adjusted_height > placeholder_height:
                adjusted_height = placeholder_height
                adjusted_width = adjusted_height / aspect_ratio
    size_properties = {}
    if adjusted_width:
        size_properties["width"] = {"magnitude": adjusted_width, "unit": width_unit}
    if adjusted_height:
        size_properties["height"] = {"magnitude": adjusted_height, "unit": height_unit}
    if size_properties:
        element_properties["size"] = size_properties

    transform_copy = placeholder_transform.copy() if placeholder_transform else {}
    if (
        placeholder_width
        and placeholder_height
        and adjusted_width
        and adjusted_height
        and placeholder_transform
        and placeholder_transform.get("translateX") is not None
        and placeholder_transform.get("translateY") is not None
    ):
        delta_x = (placeholder_width - adjusted_width) / 2
        delta_y = (placeholder_height - adjusted_height) / 2
        transform_copy["translateX"] = (placeholder_transform.get("translateX") or 0) + delta_x
        transform_copy["translateY"] = (placeholder_transform.get("translateY") or 0) + delta_y
    element_properties["transform"] = transform_copy

    image_object_id = f"Image_{uuid.uuid4().hex[:12]}"

    requests = [{
        "createImage": {
            "objectId": image_object_id,
            "url": image_url,
            "elementProperties": element_properties
        }
    }]

    if placeholder_id:
        requests.append({"deleteObject": {"objectId": placeholder_id}})

    try:
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests}
        ).execute()
        return True
    except HttpError as err:
        print(f"Warning: failed to insert image for prompt '{image_prompt}': {err}")
        return False


def add_slide(service, presentation_id, slide_data, fallback_index, deck_theme=None, page_size=None):
    #Add a new slide and insert title/body text.
    layout = resolve_layout(slide_data.get("layout"))

    requests = [{
        "createSlide": {
            "slideLayoutReference": {"predefinedLayout": layout},
        }
    }]

    create_response = service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}).execute()

    slide_id = create_response["replies"][0]["createSlide"]["objectId"]

    slide_title = slide_data.get("title", f"Slide {fallback_index}")
    slide_body = slide_data.get("body", "")
    slide_style = slide_data.get("style")
    image_prompt = slide_data.get("image_prompt")
    image_position = slide_data.get("image_position") or "RIGHT"
    image_spec = {"prompt": image_prompt, "position": image_position} if image_prompt else None

    image_placeholder = fill_slide(
        service,
        presentation_id,
        slide_id,
        slide_title,
        slide_body,
        slide_style=slide_style,
        is_title_slide=False,
        image_info=image_spec,
        deck_theme=deck_theme,
        page_size=page_size,
    )

    if image_spec:
        if image_placeholder:
            inserted = insert_image_on_slide(
                service,
                presentation_id,
                slide_id,
                image_placeholder,
                image_spec,
            )
            if not inserted:
                print(f"Warning: unable to place image on slide '{slide_title}'.")
        else:
            print(f"Warning: layout for slide '{slide_title}' does not expose an image placeholder; skipping image to keep text clear.")


def main(inputPrompt):
    gemini_generate(inputPrompt)
    # Main function to create presentation from JSON file.
    json_path = Path(__file__).with_name("slides.json")
    slides_data = load_slides_data(json_path)

    deck_theme = (
        slides_data.get("design_language")
        or slides_data.get("design_theme")
        or slides_data.get("style_guide")
    )

    creds = get_credentials()
    service = build("slides", "v1", credentials=creds)

    presentation_title = slides_data.get("presentation_title", "Untitled Presentation")
    presentation_id = create_presentation(service, presentation_title)

    # --- Handle the title slide ---
    title_slide_data = slides_data.get("title_slide", {})
    title_text = title_slide_data.get("title", "Title Slide")
    author_text = title_slide_data.get("author", "")
    # Google Slides first slide is already created by default
    presentation = service.presentations().get(presentationId=presentation_id).execute()
    page_size = presentation.get("pageSize")
    first_slide_id = presentation["slides"][0]["objectId"]

    # Fill first slide with title and author (author goes in subtitle/body placeholder)
    fill_slide(
        service,
        presentation_id,
        first_slide_id,
        title_text,
        author_text,
        slide_style=title_slide_data.get("style"),
        is_title_slide=True,
        deck_theme=deck_theme,
        page_size=page_size,
    )

    # --- Add the rest of the content slides ---
    for i, slide in enumerate(slides_data.get("slides", []), start=1):
        add_slide(service, presentation_id, slide, i, deck_theme=deck_theme, page_size=page_size)

    # Open presentation in browser
    presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    webbrowser.open(presentation_url)


if __name__ == "__main__":
    try:
        main()
    except HttpError as err:
        print(f"API error: {err}")
