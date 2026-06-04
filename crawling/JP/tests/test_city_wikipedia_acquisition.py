"""Tests for Wikipedia-first city data acquisition."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from crawling.JP.city_wikipedia_acquisition import (
    acquire_city_data,
    build_city_record,
    detect_prefecture,
)
from crawling.JP.pipeline import PageTarget, collect_pages


class FakeWikipediaClient:
    def __init__(self) -> None:
        self.pages: dict[tuple[str, str], dict[str, Any]] = {
            ("ko", "가나자와시"): {
                "query": {
                    "pages": [
                        {
                            "title": "가나자와시",
                            "extract": "가나자와시는 일본 이시카와현의 도시이다. 기후는 겨울에 눈이 많다.",
                            "coordinates": [{"lat": 36.5613, "lon": 136.6562}],
                            "extlinks": [{"url": "https://www4.city.kanazawa.lg.jp/"}],
                            "langlinks": [
                                {"lang": "ja", "title": "金沢市"},
                                {"lang": "en", "title": "Kanazawa"},
                            ],
                        }
                    ]
                }
            },
            ("ja", "金沢市"): {
                "query": {
                    "pages": [
                        {
                            "title": "金沢市",
                            "extract": "金沢市は石川県の市である。",
                            "coordinates": [{"lat": 36.5613, "lon": 136.6562}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("en", "Kanazawa"): {
                "query": {
                    "pages": [
                        {
                            "title": "Kanazawa",
                            "extract": "Kanazawa is a city in Ishikawa Prefecture.",
                            "coordinates": [{"lat": 36.5613, "lon": 136.6562}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("ko", "하치오지시"): {
                "query": {
                    "pages": [
                        {
                            "title": "하치오지시",
                            "extract": "하치오지시는 일본 도쿄도 서부에 위치한 도시이다.",
                            "coordinates": [{"lat": 35.6664, "lon": 139.3160}],
                            "extlinks": [
                                {"url": "https://www.city.hachioji.tokyo.jp/"},
                                {"url": "https://www.hkc.or.jp/"},
                                {"url": "https://example.com/blog"},
                            ],
                            "langlinks": [
                                {"lang": "ja", "title": "八王子市"},
                                {"lang": "en", "title": "Hachioji"},
                            ],
                            "revisions": [
                                {
                                    "slots": {
                                        "main": {
                                            "content": "{| class=\"wikitable\"\n|+ 기후\n! 월 !! 1월 !! 2월\n|-\n! 평균 최고 기온\n| 9.2 || 10.0\n|}",
                                        }
                                    }
                                }
                            ],
                        }
                    ]
                }
            },
            ("ja", "八王子市"): {
                "query": {
                    "pages": [
                        {
                            "title": "八王子市",
                            "extract": "八王子市は東京都の市である。",
                            "coordinates": [{"lat": 35.6664, "lon": 139.3160}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("en", "Hachioji"): {
                "query": {
                    "pages": [
                        {
                            "title": "Hachiōji",
                            "extract": "Hachioji is a city in Tokyo Metropolis.",
                            "coordinates": [{"lat": 35.6664, "lon": 139.3160}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("ja", "千代田区"): {
                "query": {
                    "pages": [
                        {
                            "title": "千代田区",
                            "extract": "千代田区は東京都の特別区である。",
                            "coordinates": [{"lat": 35.694, "lon": 139.7536}],
                            "extlinks": [{"url": "https://www.city.chiyoda.lg.jp/"}],
                            "langlinks": [
                                {"lang": "ko", "title": "지요다구"},
                                {"lang": "en", "title": "Chiyoda, Tokyo"},
                            ],
                            "revisions": [
                                {
                                    "slots": {
                                        "main": {
                                            "content": "== 地理 ==\n東京都区部の中央部に位置する。\n\n皇居や官庁街を含む。\n\n== 気候 ==\n温暖湿潤気候に属する。\n\n冬は乾燥する。\n\n== 歴史 ==\n歴史本文",
                                        }
                                    }
                                }
                            ],
                        }
                    ]
                }
            },
            ("ko", "지요다구"): {
                "query": {
                    "pages": [
                        {
                            "title": "지요다구",
                            "extract": "지요다구는 일본 도쿄도의 특별구이다.\n\n행정기관과 상업지가 집중되어 있다.",
                            "coordinates": [{"lat": 35.694, "lon": 139.7536}],
                            "extlinks": [],
                            "langlinks": [],
                            "revisions": [
                                {
                                    "slots": {
                                        "main": {
                                            "content": "'''지요다구'''({{llang|ja|千代田区|지요다쿠}})는 일본 도쿄도의 특별구이다. 면적은 11.66km<sup>2</sup>이다.\n\n행정기관과 상업지가 집중되어 있다.",
                                        }
                                    }
                                }
                            ],
                        }
                    ]
                }
            },
            ("ko", "주오구 (도쿄도)"): {
                "query": {
                    "pages": [
                        {
                            "title": "주오구 (도쿄도)",
                            "extract": "주오구는 일본 도쿄도의 심장부에 있는 특별구 중 하나이다.",
                            "coordinates": [{"lat": 35.6706, "lon": 139.7720}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("ko", "시부야구"): {
                "query": {
                    "pages": [
                        {
                            "title": "시부야구",
                            "extract": "시부야구는 일본 도쿄도에 있는 특별구 중 하나이다.",
                            "extlinks": [],
                            "langlinks": [
                                {"lang": "ja", "title": "渋谷区"},
                                {"lang": "en", "title": "Shibuya"},
                            ],
                            "revisions": [
                                {
                                    "slots": {
                                        "main": {
                                            "content": "| 좌표 = \n'''시부야구'''는 일본 도쿄도에 있는 특별구 중 하나이다.",
                                        }
                                    }
                                }
                            ],
                        }
                    ]
                }
            },
            ("ja", "渋谷区"): {
                "query": {
                    "pages": [
                        {
                            "title": "渋谷区",
                            "extract": "渋谷区は東京都の特別区である。",
                            "coordinates": [{"lat": 35.66367, "lon": 139.69772}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
            ("en", "Chiyoda, Tokyo"): {
                "query": {
                    "pages": [
                        {
                            "title": "Chiyoda, Tokyo",
                            "extract": "Chiyoda is a special ward in Tokyo Metropolis.",
                            "coordinates": [{"lat": 35.694, "lon": 139.7536}],
                            "extlinks": [],
                            "langlinks": [],
                        }
                    ]
                }
            },
        }

    def fetch_page(self, lang: str, title: str) -> dict[str, Any]:
        return self.pages[(lang, title)]


class BatchExtractOmittingClient(FakeWikipediaClient):
    def fetch_page(self, lang: str, title: str) -> dict[str, Any]:
        raise AssertionError("Batch revision content should be enough when extract is missing.")

    def fetch_pages(self, lang: str, titles: list[str]) -> dict[str, dict[str, Any]]:
        payloads: dict[str, dict[str, Any]] = {}
        for title in titles:
            page = dict(self.pages[(lang, title)]["query"]["pages"][0])
            page.pop("extract", None)
            payloads[title] = {"query": {"pages": [page]}}
        return payloads


class BatchCoordinateAndLanglinkOmittingClient(FakeWikipediaClient):
    def fetch_pages(self, lang: str, titles: list[str]) -> dict[str, dict[str, Any]]:
        payloads: dict[str, dict[str, Any]] = {}
        for title in titles:
            page = dict(self.pages[(lang, title)]["query"]["pages"][0])
            page.pop("coordinates", None)
            page["langlinks"] = []
            page["revisions"] = [
                {
                    "slots": {
                        "main": {
                            "content": "| 좌표 = \n'''시부야구'''는 일본 도쿄도에 있는 특별구 중 하나이다.",
                        }
                    }
                }
            ]
            payloads[title] = {"query": {"pages": [page]}}
        return payloads


class CityWikipediaAcquisitionTest(unittest.TestCase):
    def test_detect_prefecture_from_korean_text(self) -> None:
        prefecture = detect_prefecture(["가나자와시는 일본 이시카와현의 도시이다."])

        self.assertIsNotNone(prefecture)
        self.assertEqual("JP-17", prefecture.prefecture_id)

    def test_acquire_city_data_rejects_non_tokyo_city(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "Tokyo"):
                acquire_city_data(
                    titles=["가나자와시"],
                    output_dir=Path(tmpdir),
                    client=FakeWikipediaClient(),
                )

    def test_tokyo_city_uses_english_romanization_climate_table_and_two_site_urls(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "ko": client.pages[("ko", "하치오지시")]["query"]["pages"][0],
            "ja": client.pages[("ja", "八王子市")]["query"]["pages"][0],
            "en": client.pages[("en", "Hachioji")]["query"]["pages"][0],
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00")

        self.assertEqual("JP-13-HACHIOJI", city.city_id)
        self.assertEqual("JP-13", city.prefecture_id)
        self.assertEqual(
            ["https://www.city.hachioji.tokyo.jp/", "https://www.hkc.or.jp/"],
            city.site_urls,
        )
        self.assertEqual("collected", city.field_status["climate_table"])
        self.assertEqual("기후", city.climate_table["caption"])
        self.assertIn("평균 최고 기온", city.climate_table["wikitext"])

    def test_build_city_record_from_wikipedia_pages(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "ko": client.pages[("ko", "가나자와시")]["query"]["pages"][0],
            "ja": client.pages[("ja", "金沢市")]["query"]["pages"][0],
            "en": client.pages[("en", "Kanazawa")]["query"]["pages"][0],
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00")

        self.assertEqual("JP-17-KANAZAWA", city.city_id)
        self.assertEqual("JP-17", city.prefecture_id)
        self.assertEqual(36.5613, city.latitude)
        self.assertEqual(136.6562, city.longitude)
        self.assertEqual(["https://www4.city.kanazawa.lg.jp/"], city.site_urls)
        self.assertEqual("needs_review", city.field_status["description"])

    def test_acquire_city_data_writes_separated_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            prefectures, cities = acquire_city_data(
                titles=["하치오지시"],
                output_dir=output_dir,
                client=FakeWikipediaClient(),
            )

            self.assertEqual(1, len(prefectures))
            self.assertEqual(1, len(cities))
            prefecture_payload = json.loads((output_dir / "prefectures.json").read_text(encoding="utf-8"))
            city_payload = json.loads((output_dir / "cities.json").read_text(encoding="utf-8"))
            self.assertEqual("JP-13", prefecture_payload[0]["prefecture_id"])
            self.assertEqual("JP-13", city_payload[0]["prefecture_id"])
            self.assertNotIn("prefecture", city_payload[0])

    def test_acquire_city_data_uses_revision_lead_when_batch_extract_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, cities = acquire_city_data(
                titles=[PageTarget(title="지요다구", lang="ko", prefecture_id="JP-13")],
                output_dir=Path(tmpdir),
                client=BatchExtractOmittingClient(),
            )

        self.assertEqual(
            "지요다구는 일본 도쿄도의 특별구이다. 면적은 11.66km2이다.\n\n행정기관과 상업지가 집중되어 있다.",
            cities[0].description,
        )

    def test_city_record_uses_revision_lead_when_extract_is_missing(self) -> None:
        client = BatchExtractOmittingClient()
        pages = {
            "source": client.fetch_pages("ko", ["지요다구"])["지요다구"]["query"]["pages"][0],
            "source_meta": {"lang": "ko", "title": "지요다구"},
            "ko": client.fetch_pages("ko", ["지요다구"])["지요다구"]["query"]["pages"][0],
            "ja": {},
            "en": {},
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual(
            "지요다구는 일본 도쿄도의 특별구이다. 면적은 11.66km2이다.\n\n행정기관과 상업지가 집중되어 있다.",
            city.description,
        )

    def test_city_record_uses_revision_coordinate_template_when_api_coordinates_are_missing(self) -> None:
        client = FakeWikipediaClient()
        page = dict(client.pages[("ko", "지요다구")]["query"]["pages"][0])
        page.pop("coordinates")
        page["revisions"] = [
            {
                "slots": {
                    "main": {
                        "content": "| 좌표 = {{small|{{좌표|35|41|38.2|N|139|45|13|E|region:JP-13_type:adm3rd|display=inline,title}}}}",
                    }
                }
            }
        ]
        pages = {"source": page, "source_meta": {"lang": "ko"}, "ko": page, "ja": {}, "en": {}}

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertAlmostEqual(35.693944, city.latitude or 0, places=6)
        self.assertAlmostEqual(139.753611, city.longitude or 0, places=6)
        self.assertEqual("collected", city.field_status["latitude"])
        self.assertEqual("collected", city.field_status["longitude"])

    def test_korean_source_uses_linked_japanese_coordinates_when_korean_coordinates_are_blank(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, cities = acquire_city_data(
                titles=[PageTarget(title="시부야구", lang="ko", prefecture_id="JP-13")],
                output_dir=Path(tmpdir),
                client=FakeWikipediaClient(),
            )

        self.assertEqual(35.66367, cities[0].latitude)
        self.assertEqual(139.69772, cities[0].longitude)
        self.assertEqual("collected", cities[0].field_status["latitude"])

    def test_korean_source_refetches_langlinks_for_coordinate_fallback_when_batch_langlinks_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, cities = acquire_city_data(
                titles=[PageTarget(title="시부야구", lang="ko", prefecture_id="JP-13")],
                output_dir=Path(tmpdir),
                client=BatchCoordinateAndLanglinkOmittingClient(),
            )

        self.assertEqual(35.66367, cities[0].latitude)
        self.assertEqual(139.69772, cities[0].longitude)

    def test_city_record_removes_tokyo_disambiguation_suffix_from_korean_name(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "source": client.pages[("ko", "주오구 (도쿄도)")]["query"]["pages"][0],
            "source_meta": {"lang": "ko", "title": "주오구 (도쿄도)"},
            "ko": client.pages[("ko", "주오구 (도쿄도)")]["query"]["pages"][0],
            "ja": {},
            "en": {},
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual("주오구", city.city_name_ko)
        self.assertIn("주오구는 일본 도쿄도", city.description)

    def test_collect_pages_supports_japanese_source_titles(self) -> None:
        pages = collect_pages(
            client=FakeWikipediaClient(),
            target=PageTarget(title="千代田区", lang="ja"),
        )

        self.assertEqual("千代田区", pages["ja"]["title"])
        self.assertEqual("지요다구", pages["ko"]["title"])
        self.assertEqual("지요다구는 일본 도쿄도의 특별구이다.\n\n행정기관과 상업지가 집중되어 있다.", pages["ko"]["extract"])
        self.assertEqual("Chiyoda, Tokyo", pages["en"]["title"])
        self.assertEqual("千代田区", pages["source"]["title"])

    def test_city_record_uses_korean_fallback_name_when_korean_page_is_missing(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "source": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "source_meta": {"lang": "ja"},
            "ko": {},
            "ja": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "en": client.pages[("en", "Chiyoda, Tokyo")]["query"]["pages"][0],
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual("지요다구", city.city_name_ko)
        self.assertEqual("needs_review", city.field_status["city_name_ko"])
        self.assertTrue(city.description.startswith("지요다구는 일본 도쿄도"))

    def test_city_record_collects_geography_description_and_marks_missing_climate_manual_required(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "source": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "source_meta": {"lang": "ja"},
            "ko": client.pages[("ko", "지요다구")]["query"]["pages"][0],
            "ja": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "en": client.pages[("en", "Chiyoda, Tokyo")]["query"]["pages"][0],
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual("지요다구는 일본 도쿄도의 특별구이다.\n\n행정기관과 상업지가 집중되어 있다.", city.description)
        self.assertEqual("東京都区部の中央部に位置する。\n\n皇居や官庁街を含む。", city.geography_description)
        self.assertEqual(35.694, city.latitude)
        self.assertEqual(139.7536, city.longitude)
        self.assertEqual("気候", city.climate_table["caption"])
        self.assertEqual("温暖湿潤気候に属する。\n\n冬は乾燥する。", city.climate_table["content"])
        self.assertEqual("collected", city.field_status["climate_table"])
        self.assertEqual("collected", city.field_status["geography_description"])

    def test_city_record_uses_korean_geography_fallback_when_korean_geography_section_is_missing(self) -> None:
        client = FakeWikipediaClient()
        pages = {
            "source": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "source_meta": {"lang": "ja"},
            "ko": client.pages[("ko", "지요다구")]["query"]["pages"][0],
            "ja": client.pages[("ja", "千代田区")]["query"]["pages"][0],
            "en": client.pages[("en", "Chiyoda, Tokyo")]["query"]["pages"][0],
        }
        pages["ko"]["revisions"] = []

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual("東京都区部の中央部に位置する。\n\n皇居や官庁街を含む。", city.geography_description)

    def test_korean_source_target_keeps_input_title_when_wikipedia_page_is_missing(self) -> None:
        pages = {
            "source": {},
            "source_meta": {"lang": "ko", "title": "주오구"},
            "ko": {},
            "ja": {},
            "en": {},
        }

        city = build_city_record(pages, "2026-06-04T00:00:00+09:00", fallback_prefecture_id="JP-13")

        self.assertEqual("주오구", city.city_name_ko)
        self.assertNotEqual("JP-13-UNKNOWN", city.city_id)
        self.assertEqual("needs_review", city.field_status["city_name_ko"])
        self.assertEqual("needs_review", city.field_status["climate_table"])


if __name__ == "__main__":
    unittest.main()


# File History
# 2026-06-04: Created tests for Wikipedia-first city acquisition.
