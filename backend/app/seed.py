"""Sample Fairlot listings (origin=seed) with stock photos and server-only limits.

Each sample has a seller bot that answers offers inside the private floor below.
Private floors live only in `_ROWS` and the price_limits table. Never return them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.agents.inspector import stub_inspect
from backend.app.db import connect
from backend.app.repository import Limits, ListingRecord, insert_listing
from backend.app.schemas import Appraisal, Comp


def _img(photo_id: str) -> str:
    return f"https://images.unsplash.com/photo-{photo_id}?w=900&q=70&auto=format&fit=crop"


# id, category, title, description, price, photo, neighborhood, hours_ago, (low, est, high), seller_min
_ROWS: tuple[tuple, ...] = (
    ("lst_01", "bikes", "Fixed-gear city bike, 54 cm", "Flip-flop hub, new chain and bar tape. Light and quick for commuting.", 320, "1485965120184-e220f721d03e", "Mission, San Francisco", 1, (260, 300, 360), 270),
    ("lst_02", "bikes", "Single-speed with orange rims, 56 cm", "Steel frame, front brake, rides smooth. Small scuff on the top tube.", 240, "1507035895480-2b3156c31fc8", "Temescal, Oakland", 2, (200, 250, 300), 200),
    ("lst_03", "bikes", "Touring bike with racks and bags", "Steel touring frame with front and rear racks. Bags included. Ready for a weekend trip.", 650, "1511994298241-608e28f14fde", "Berkeley", 3, (520, 640, 760), 560),
    ("lst_04", "bikes", "Carbon road bike, 105 groupset", "Full carbon, 22 speed Shimano 105. Serviced last month. 56 cm.", 1150, "1532298229144-0ec0c57515c7", "Palo Alto", 4, (950, 1200, 1400), 1000),
    ("lst_05", "bikes", "White step-through city bike", "Upright position, fenders, and a kickstand. Great for errands.", 280, "1571068316344-75bc76f77890", "Noe Valley, San Francisco", 5, (220, 270, 320), 230),
    ("lst_06", "bikes", "Aluminum road bike, 54 cm", "Drop bars, Sora shifters, tires with plenty of tread left.", 380, "1576435728678-68d0fbf94e91", "Inner Sunset, San Francisco", 7, (340, 410, 480), 330),
    ("lst_07", "computers", "MacBook Air M1, 8 GB, 256 GB", "Battery at 91 percent. Charger included. No dents.", 520, "1496181133206-80ce9b88a853", "Stanford", 1, (480, 550, 620), 470),
    ("lst_08", "computers", "MacBook Pro 13, M2, 16 GB", "Space gray, 512 GB. Light use, always in a sleeve. Box included.", 900, "1517336714731-489689fd1ca8", "Menlo Park", 2, (820, 950, 1080), 820),
    ("lst_09", "computers", "MacBook Pro 14, M1 Pro", "16 GB, 512 GB. Small mark on the lid. Battery cycle count 210.", 1100, "1525547719571-a2d4ac8945e2", "Downtown Berkeley", 3, (1000, 1150, 1300), 980),
    ("lst_10", "computers", "Windows ultrabook, 14 inch", "Core i7, 16 GB, 512 GB SSD. Backlit keyboard. Fresh Windows install.", 480, "1588872657578-7efd1f1555ed", "Sunnyvale", 6, (400, 470, 560), 410),
    ("lst_11", "computers", "iMac 24 inch, M1, with keyboard", "Blue, 8 GB, 256 GB. Keyboard and mouse included.", 750, "1547082299-de196ea013d6", "SoMa, San Francisco", 8, (680, 800, 920), 660),
    ("lst_12", "computers", "iMac 27 inch, 5K display", "2019 model, 16 GB RAM, 1 TB fusion drive. Great screen for photo work.", 600, "1593642632559-0c6d3fc62b89", "Redwood City", 10, (500, 620, 740), 520),
    ("lst_14", "furniture", "Green velvet sofa, three seats", "Deep seats, no stains or pet hair. You pick up, two people needed.", 650, "1555041469-a586c61ea9bc", "Rockridge, Oakland", 1, (500, 640, 800), 540),
    ("lst_15", "furniture", "Yellow armchair", "Mid-century style, solid legs. Sat in a reading corner.", 180, "1586023492125-27b2c045efd7", "Hayes Valley, San Francisco", 2, (140, 190, 240), 150),
    ("lst_16", "furniture", "Desk with office chair", "White desk, 120 cm wide, plus an adjustable chair. Sold together.", 220, "1518455027359-f3f8164ba6bd", "Mission, San Francisco", 3, (180, 230, 290), 185),
    ("lst_17", "furniture", "Dining table with four chairs", "Light wood table seats four. Chairs are sturdy. Moving sale.", 400, "1617806118233-18e1de247200", "Fremont", 4, (320, 420, 520), 340),
    ("lst_18", "furniture", "Two wooden bar stools", "Natural wood, 75 cm seat height. Sold as a pair.", 95, "1503602642458-232111445657", "Berkeley", 5, (80, 100, 120), 77),
    ("lst_19", "furniture", "Vintage wooden chair", "Solid wood dining chair with a woven back. Very sturdy.", 90, "1506439773649-6e0eb8cfb237", "Alameda", 6, (70, 95, 120), 71),
    ("lst_20", "furniture", "Gray designer desk lamp", "Adjustable arm, LED bulb included. Works perfectly.", 85, "1507473885765-e6ed057f782c", "Mountain View", 7, (70, 90, 110), 68),
    ("lst_21", "furniture", "Beige lounge chair", "Curved shell on a swivel base. Comfortable for reading.", 160, "1580480055273-228ff5388ef8", "Bernal Heights, San Francisco", 9, (120, 170, 220), 130),
    ("lst_22", "furniture", "Black dining chairs, set of 4", "Molded seats with wooden legs. Easy to wipe clean.", 140, "1592078615290-033ee584e267", "San Jose", 11, (110, 150, 190), 115),
    ("lst_23", "furniture", "Living room set, two chairs and table", "Two accent chairs and a round coffee table. Moving out this month.", 300, "1524758631624-e2822e304c36", "Oakland", 13, (240, 320, 400), 250),
    ("lst_24", "furniture", "Lounge set with sofa and chairs", "Gray sofa, two armchairs, and a coffee table. Great for a shared house.", 850, "1538688525198-9b88f6f53126", "Palo Alto", 15, (700, 880, 1050), 720),
)


def _verdict(price: int, low: int, high: int) -> str:
    if price < low:
        return "good_deal"
    if price > high:
        return "overpriced"
    return "fair"


def _hidden(value: int, public: set[int]) -> int:
    """Private numbers must never equal a number the site shows."""

    value = value + 3 if value % 10 == 0 else value
    while value in public:
        value += 1
    return value


def load_seed() -> None:
    """Insert missing samples and refresh existing sample rows in place. Safe to run on every boot."""

    now = datetime.now(timezone.utc)
    public_all = {n for row in _ROWS for n in (row[4], *row[8])}
    taken: set[int] = set()
    for row in _ROWS:
        lid, category, title, description, price, photo, area, hours, (low, est, high), floor = row
        posted = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        listing = ListingRecord(
            id=lid,
            category=category,
            title=title,
            description=description,
            price=price,
            photos=[_img(photo)],
            neighborhood=area,
            source_url=None,
            posted_at=posted,
            origin="seed",
        )
        floor = _hidden(floor, public_all | taken)
        taken.add(floor)
        ceiling = _hidden(high + 7, public_all | taken)
        taken.add(ceiling)
        label = category[:-1] if category.endswith("s") else category
        appraisal = Appraisal(
            estimated_value=est,
            low=low,
            high=high,
            comps=[
                Comp(title=f"Similar {label} sold nearby", price=low),
                Comp(title=f"Comparable {label} listed this week", price=est),
                Comp(title=f"Higher-end {label} listing", price=high),
            ],
            verdict=_verdict(price, low, high),  # type: ignore[arg-type]
        )
        insert_listing(listing, appraisal, stub_inspect(listing, appraisal), Limits(buyer_max=ceiling, seller_min=floor))
        with connect() as conn:
            conn.execute(
                """
                UPDATE listings SET category = ?, title = ?, description = ?, price = ?, photos = ?,
                    neighborhood = ?, posted_at = CASE WHEN status = 'sold' THEN posted_at ELSE ? END
                WHERE id = ? AND origin = 'seed'
                """,
                (category, title, description, price, f'["{_img(photo)}"]', area, posted, lid),
            )
            conn.execute(
                "UPDATE appraisals SET estimated_value = ?, low = ?, high = ?, comps = ?, verdict = ? WHERE listing_id = ?",
                (
                    est,
                    low,
                    high,
                    '[' + ",".join(c.model_dump_json() for c in appraisal.comps) + ']',
                    appraisal.verdict,
                    lid,
                ),
            )
            conn.execute(
                "UPDATE price_limits SET buyer_max = ?, seller_min = ? WHERE listing_id = ? AND want_id IS NULL",
                (ceiling, floor, lid),
            )
