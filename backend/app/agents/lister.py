"""Lister. Person B (@srivatsav-kannan) owns this file.

Replace stub_draft_from_photo. Keep draft_from_photo(photo, filename).
"""

from __future__ import annotations

from backend.app.agents.appraiser import ANCHORS
from backend.app.agents.llm import complete
from backend.app.schemas import Draft

_BY_FILENAME: tuple[tuple[str, str, str, str], ...] = (
    ("bike", "bikes", "City bike", "Everyday bike drafted from the uploaded photo. Edit the details before publishing."),
    ("laptop", "computers", "Laptop", "Laptop drafted from the uploaded photo. Edit the details before publishing."),
    ("computer", "computers", "Desktop computer", "Computer drafted from the uploaded photo. Edit the details before publishing."),
    ("desk", "furniture", "Oak desk", "Small writing desk drafted from the uploaded photo. Visible wear may need a note."),
    ("sofa", "furniture", "Sofa", "Sofa drafted from the uploaded photo. Edit the details before publishing."),
)


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
    complete("Write a classifieds listing from this photo.", image=photo)
    return stub_draft_from_photo(photo, filename)
