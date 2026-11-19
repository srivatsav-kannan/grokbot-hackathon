"""Lister. Person B (@srivatsav-kannan) owns this file.

Replace stub_draft_from_photo. Keep draft_from_photo(photo, filename).
Claude vision writes the draft. A missing model reply keeps the stub.
"""

from __future__ import annotations

from backend.app.agents.appraiser import ANCHORS
from backend.app.agents.llm import complete, parse_json_reply
from backend.app.schemas import CATEGORIES, Draft

_BY_FILENAME: tuple[tuple[str, str, str, str], ...] = (
    ("bike", "bikes", "City bike", "Everyday bike drafted from the uploaded photo. Edit the details before publishing."),
    ("laptop", "computers", "Laptop", "Laptop drafted from the uploaded photo. Edit the details before publishing."),
    ("computer", "computers", "Desktop computer", "Computer drafted from the uploaded photo. Edit the details before publishing."),
    ("desk", "furniture", "Oak desk", "Small writing desk drafted from the uploaded photo. Visible wear may need a note."),
    ("sofa", "furniture", "Sofa", "Sofa drafted from the uploaded photo. Edit the details before publishing."),
)

_MAX_DOLLARS = 500_000


def stub_draft_from_photo(photo: bytes, filename: str | None = None) -> Draft:
    name = (filename or "").lower()
    category = "furniture"
    title = "Furniture item"
    description = "Drafted from the uploaded photo. Edit the title and condition before publishing."
    for needle, cat, draft_title, draft_description in _BY_FILENAME:
        if needle in name:
            category = cat
            title = draft_title
            description = draft_description
            break
    suggested = ANCHORS.get(category, 100)
    if len(photo) > 200_000:
        suggested += 40
    return Draft(
        category=category,  # type: ignore[arg-type]
        title=title,
        description=description,
        suggested_price=suggested,
    )


def draft_from_photo(photo: bytes, filename: str | None = None) -> Draft:
    parsed = parse_json_reply(complete(_draft_prompt(filename), image=photo))
    if isinstance(parsed, dict):
        draft = _draft_from_payload(parsed)
        if draft is not None:
            return draft
    return stub_draft_from_photo(photo, filename)


def _draft_prompt(filename: str | None) -> str:
    hint = filename or "upload"
    return (
        "Write a classifieds draft from this photo of an item for sale in the SF Bay Area. "
        "Reply with one JSON object only: "
        '{"category": "furniture", "title": "Oak desk", '
        '"description": "One or two sentences about condition.", "suggested_price": 90}. '
        "category is bikes, computers, or furniture. "
        "suggested_price is an integer US dollar price. "
        "Do not include a buyer maximum or a seller minimum.\n"
        f"Filename hint: {hint}"
    )


def _draft_from_payload(payload: dict) -> Draft | None:
    category = payload.get("category")
    title = payload.get("title")
    description = payload.get("description")
    price = _dollars(payload.get("suggested_price"))
    if category not in CATEGORIES or price is None:
        return None
    if not isinstance(title, str) or not isinstance(description, str):
        return None
    title = " ".join(title.split())
    description = " ".join(description.split())
    if not title or not description or len(title) > 120 or len(description) > 2000:
        return None
    return Draft(
        category=category,
        title=title,
        description=description,
        suggested_price=price,
    )


def _dollars(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if not cleaned.isdigit():
            return None
        number = int(cleaned)
    else:
        return None
    if number < 1 or number > _MAX_DOLLARS:
        return None
    return number
