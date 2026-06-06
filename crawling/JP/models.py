"""
Shared data models for Japan city acquisition.

This file defines reusable record structures used by the Wikipedia client,
normalizer, and pipeline layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


STATUS_COLLECTED = "collected"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_MISSING = "missing"


@dataclass(frozen=True)
class PrefectureReference:
    prefecture_id: str
    name_ko: str
    name_ja: str
    name_en: str
    region: str


@dataclass
class NormalizedRecord:
    source_name: str
    source_url: str
    collected_at: str
    field_status: dict[str, str]
    data_confidence: str = "medium"
    verified_at: str | None = None
    verified_source_url: str | None = None
    verification_note: str | None = None


@dataclass
class PrefectureRecord(NormalizedRecord):
    prefecture_id: str = ""
    name_ko: str = ""
    name_ja: str = ""
    name_en: str = ""
    region: str = ""


@dataclass
class CityRecord(NormalizedRecord):
    city_id: str = ""
    city_name_ko: str = ""
    city_name_ja: str = ""
    city_name_en: str = ""
    prefecture_id: str = ""
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    description: str = ""
    geography_description: str = ""
    climate_table: dict[str, str] | None = None
    site_urls: list[str] = field(default_factory=list)


# File History
# 2026-06-04: Split shared acquisition models from the CLI module.
