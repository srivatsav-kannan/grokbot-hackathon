"""SF Bay Area place checks for marketplace locations.

Sources that are already scoped to the Bay (Craigslist SF Bay, eBay local
pickup around 94102) keep a listing unless the location names somewhere else.
Sources that are not scoped (OfferUp, Mercari) keep a listing only when the
location positively matches the Bay.
"""

from __future__ import annotations

import re

# Longer names first so "south san francisco" is matched as itself.
BAY_CITIES: tuple[str, ...] = (
    "south san francisco",
    "san francisco",
    "daly city",
    "san mateo",
    "redwood city",
    "palo alto",
    "east palo alto",
    "mountain view",
    "sunnyvale",
    "santa clara",
    "san jose",
    "cupertino",
    "campbell",
    "los gatos",
    "saratoga",
    "milpitas",
    "fremont",
    "hayward",
    "union city",
    "newark",
    "castro valley",
    "san leandro",
    "alameda",
    "oakland",
    "berkeley",
    "emeryville",
    "piedmont",
    "albany",
    "el cerrito",
    "richmond",
    "san pablo",
    "el sobrante",
    "pinole",
    "hercules",
    "san rafael",
    "mill valley",
    "sausalito",
    "tiburon",
    "corte madera",
    "larkspur",
    "novato",
    "san anselmo",
    "fairfax",
    "walnut creek",
    "pleasant hill",
    "lafayette",
    "orinda",
    "moraga",
    "concord",
    "martinez",
    "danville",
    "san ramon",
    "dublin",
    "pleasanton",
    "livermore",
    "vallejo",
    "benicia",
    "american canyon",
    "napa",
    "sonoma",
    "petaluma",
    "antioch",
    "pittsburg",
    "pacifica",
    "half moon bay",
    "san bruno",
    "millbrae",
    "burlingame",
    "foster city",
    "belmont",
    "san carlos",
    "menlo park",
    "atherton",
    "brisbane",
    "colma",
    "contra costa",
    "marin",
)

FAR_CALIFORNIA: tuple[str, ...] = (
    "los angeles",
    "san diego",
    "sacramento",
    "fresno",
    "bakersfield",
    "long beach",
    "anaheim",
    "riverside",
    "irvine",
    "stockton",
    "modesto",
    "santa barbara",
    "santa cruz",
    "monterey",
    "salinas",
    "chico",
    "redding",
    "eureka",
    "santa rosa",
)

# Two-letter codes are case-sensitive so the word "in" is not Indiana.
_ABBREV_RE = re.compile(
    r"\b(AL|AK|AZ|AR|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
    r"MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b"
)
_STATE_NAME_RE = re.compile(
    r"\b(alabama|alaska|arizona|arkansas|colorado|connecticut|delaware|florida|georgia|"
    r"hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    r"massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    r"new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|"
    r"oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|"
    r"texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b",
    re.I,
)
_CA_RE = re.compile(r"\b(ca|california)\b", re.I)
_FAR_RE = re.compile("|".join(re.escape(city) for city in FAR_CALIFORNIA), re.I)
_BAY_RE = re.compile("|".join(rf"\b{re.escape(city)}\b" for city in BAY_CITIES), re.I)


def location_is_bay(text: str) -> bool:
    """True when the text names a Bay Area place and not some other state."""

    if _outside_state(text) and not _CA_RE.search(text):
        return False
    lowered = text.lower()
    if "bay area" in lowered or "sf bay" in lowered:
        return True
    return _BAY_RE.search(text) is not None


def location_is_outside(text: str) -> bool:
    """True when the text clearly names a place outside the SF Bay Area."""

    if not text.strip() or location_is_bay(text):
        return False
    if _FAR_RE.search(text):
        return True
    return _outside_state(text)


def _outside_state(text: str) -> bool:
    return _ABBREV_RE.search(text) is not None or _STATE_NAME_RE.search(text) is not None
