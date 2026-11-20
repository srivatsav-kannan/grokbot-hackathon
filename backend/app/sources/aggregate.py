"""Run every marketplace and dedupe by source plus that source's item id."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.sources import craigslist, ebay, facebook, mercari, nextdoor, offerup
from backend.app.sources.fetch import PageFetcher
from backend.app.sources.listing import ScoutedListing, dedupe

SOURCES = (craigslist, ebay, offerup, mercari, facebook, nextdoor)
# Facebook Marketplace and Nextdoor need an account, so a free-text query skips them.
QUERY_SOURCES = (craigslist, ebay, offerup, mercari)


@dataclass
class SourceBatch:
    listings: list[ScoutedListing] = field(default_factory=list)
    stopped: bool = False
    skipped: bool = False
    reason: str | None = None
    message: str = ""


@dataclass
class SourceReport:
    source: str
    fetched: int = 0
    listings: int = 0
    stopped: bool = False
    skipped: bool = False
    reason: str | None = None
    message: str = ""


def collect_all(
    categories: list[str],
    fetcher: PageFetcher,
    posted_at: str,
) -> tuple[list[ScoutedListing], list[SourceReport]]:
    """Ask each source for the categories. One source stopping does not cancel the others."""

    combined: list[ScoutedListing] = []
    reports: list[SourceReport] = []
    for module in SOURCES:
        batch = module.collect(categories, fetcher, posted_at)
        combined.extend(batch.listings)
        reports.append(
            SourceReport(
                source=module.NAME,
                fetched=fetcher.counts.get(module.NAME, 0),
                listings=len(batch.listings),
                stopped=batch.stopped,
                skipped=batch.skipped,
                reason=batch.reason,
                message=batch.message,
            )
        )
    return dedupe(combined), reports
