# Spec: City Data Acquisition

> Source plan: `docs/japan_data_acquisition_plan.md` v0.4
> Status: Draft for review
> Created: 2026-06-04
> Owner role: Spec Agent

## Summary

This spec defines how to acquire, normalize, verify, and store city-level data for the Lovv travel recommendation service.

The scope is limited to City acquisition only. It does not define collection requirements for other destination entities.

## Assumptions

- Target country for this spec is Japan.
- The first implementation target is limited to Tokyo Metropolis.
- The crawler runtime target is Python 3.12.
- City unit means Japanese municipality-level destination data, mainly city, town, village, ward, or comparable small destination unit.
- The initial source of truth is `docs/japan_data_acquisition_plan.md`.
- This spec prepares implementation requirements only. It does not implement a crawler.
- City data must be stable enough to serve as the canonical destination list.

## Goals

- Acquire all required City fields defined by the current data acquisition plan.
- Produce one normalized city record per destination.
- Record source and acquisition metadata for every record.
- Classify every field into a collection status so missing or uncertain values can be repaired later.
- Prefer official or public sources and keep copyright-sensitive content traceable.
- Provide a stable `city_id` for each collected city.
- Prefer English romanization when generating `city_id`.

## Non-Goals

- Do not crawl non-city destination detail data in this spec.
- Do not design the final production database schema beyond City requirements.
- Do not store full copied Wikipedia prose as final service copy.
- Do not collect commercial hotel, restaurant, or booking platform data.
- Do not define ranking, recommendation scoring, or itinerary generation logic.

## Users And Actors

- Data Acquisition Agent: runs the city collection workflow and writes raw and normalized outputs.
- Web Search Worker: repairs missing or stale values when primary sources are insufficient.
- Human Reviewer: validates ambiguous values, source usage, and copyright-sensitive content.
- Downstream Recommendation Service: consumes normalized city records through stable `city_id` values.

## Source Priority

| Priority | Source | Primary Use | Notes |
| --- | --- | --- | --- |
| 1 | Wikipedia | City names, overview, location, climate table, official links | Primary acquisition source for all city fields. Must preserve source URL and license-sensitive provenance. |
| 2 | Wikidata | Coordinates, multilingual names, identifiers | Use only as a secondary source when Wikipedia is missing or ambiguous. |
| 3 | e-Stat / Statistical LOD | Administrative area metadata and codes | Use only for city normalization and disambiguation when Wikipedia is insufficient. |
| 4 | Official municipality or tourism site | Official site URL and manual verification | Use as verification or fallback. Store up to two official or tourism site URLs when available. |

## Collection Method

- Large or repeated collection runs should use HTML parsing with `requests` and `BeautifulSoup(bs4)` as the default method.
- The MediaWiki API should be used selectively for small repairs, linked-page checks, or precise lookups such as coordinates and multilingual names when HTML parsing is insufficient.
- API timeouts, rate limits, or missing batch fields must not stop the full collection run. The workflow should normalize HTML results first and mark only insufficient fields for later repair.

## Data Requirements

### City Fields

| Field | Required | Collection Method | Description |
| --- | --- | --- | --- |
| `city_id` | Yes | Internal generation | Stable internal identifier generated with English romanization first, such as `JP-13-HACHIOJI`. |
| `city_name_ko` | Yes | Wikipedia / manual normalization | Korean city name for Korean UI and search. |
| `city_name_ja` | Yes | Wikipedia / Wikidata | Japanese source name. |
| `city_name_en` | Recommended | Wikipedia / Wikidata | English name for IDs, fallback search, and cross-source matching. |
| `prefecture_id` | Yes | Wikipedia / e-Stat / Wikidata | Foreign key-style reference to a separated prefecture record. |
| `location` | Yes | Wikipedia / Wikidata / e-Stat | Human-readable administrative location. |
| `latitude` | Yes | Wikidata / Wikipedia | Representative latitude. |
| `longitude` | Yes | Wikidata / Wikipedia | Representative longitude. |
| `description` | Yes | Wikipedia-based internal summary | Internal Korean summary, not direct long-form copied text. |
| `climate_table` | Recommended | Wikipedia | Climate table extracted from the Wikipedia page when present. |
| `site_urls` | Yes | Wikipedia external links / official site | One or two municipality or official tourism site URLs. |

### Prefecture Fields

Prefecture data must be stored separately from City data. City records must reference prefecture records through `prefecture_id`.

| Field | Required | Collection Method | Description |
| --- | --- | --- | --- |
| `prefecture_id` | Yes | Internal generation / e-Stat | Stable prefecture identifier, such as `JP-17`. |
| `name_ko` | Yes | Wikipedia / manual normalization | Korean prefecture name. |
| `name_ja` | Yes | Wikipedia / e-Stat / Wikidata | Japanese prefecture name. |
| `name_en` | Recommended | Wikipedia / Wikidata | English prefecture name. |
| `region` | Recommended | Wikipedia / manual normalization | Japanese region such as `Chubu`, `Kansai`, or `Kyushu`. |

### Metadata Fields

| Field | Required | Description |
| --- | --- | --- |
| `source_name` | Yes | Primary source used for the record or field. |
| `source_url` | Yes | URL for the source page or API endpoint. |
| `collected_at` | Yes | Timestamp when the value was collected. |
| `field_status` | Yes | Per-field status: `collected`, `needs_review`, `missing`, or `blocked`. |
| `data_confidence` | Recommended | Confidence label such as `high`, `medium`, or `low`. |
| `verified_at` | Conditional | Required when a human or official-site verification occurs. |
| `verified_source_url` | Conditional | Required when verification uses a different source. |
| `verification_note` | Conditional | Required when the value is ambiguous, manually normalized, or blocked. |

## Functional Requirements

- FR-CITY-001: The acquisition workflow must create one normalized City record per target destination.
- FR-CITY-002: Each City record must include a stable `city_id`.
- FR-CITY-003: Each City record must include `city_name_ko`, `city_name_ja`, `prefecture_id`, `latitude`, `longitude`, `description`, and `site_urls`.
- FR-CITY-004: The workflow must attempt `city_name_en`, `location`, and `climate_table` collection when Wikipedia provides enough information.
- FR-CITY-005: Every field must have a field-level collection status.
- FR-CITY-006: Missing values must not be silently dropped; they must be marked `missing`, `needs_review`, or `blocked`.
- FR-CITY-007: Descriptions must be stored as internal summaries with source provenance, not raw copied long-form text.
- FR-CITY-008: Coordinates must be numeric and must include source provenance.
- FR-CITY-009: Official site URLs must prefer municipality or official tourism domains over blogs, social media, or commercial aggregators.
- FR-CITY-010: The workflow must emit enough metadata to audit, reload, and repair City records.
- FR-CITY-011: Output must be saved as JSON files, with prefecture data and city data stored separately.
- FR-CITY-012: City records must reference prefecture records by `prefecture_id`; they must not embed the full prefecture object.
- FR-CITY-013: The first implementation must reject non-Tokyo Metropolis city records.
- FR-CITY-014: `city_id` generation must prefer English romanized city names.
- FR-CITY-015: If Wikipedia exposes two official or tourism site URLs, both must be stored in `site_urls`.

## User Flow

1. Data Acquisition Agent receives a target city list or approved source query.
2. Agent collects candidate city data from Wikipedia and Wikidata.
3. Agent normalizes prefecture records, city names, city-to-prefecture references, coordinates, and official site URL.
4. Agent rejects records outside Tokyo Metropolis for the first implementation.
5. Agent creates `city_id` from country, prefecture, and English romanized city name.
6. Agent writes raw source evidence and normalized City output.
7. Agent marks each field status.
8. Web Search Worker or Human Reviewer handles `missing`, `needs_review`, and `blocked` fields.
9. Approved City records become the canonical city dataset.

## Output Contract

The initial implementation should produce separate JSON files that can be loaded into the database later.

Recommended output files:

- `data/normalized/prefectures.json`
- `data/normalized/cities.json`

Recommended `prefectures.json` shape:

```json
[
  {
    "prefecture_id": "JP-17",
    "name_ko": "이시카와현",
    "name_ja": "石川県",
    "name_en": "Ishikawa",
    "region": "Chubu",
    "source_name": "Wikipedia/Wikidata",
    "source_url": "https://www.wikidata.org/wiki/Q131281",
    "collected_at": "2026-06-04T00:00:00+09:00",
    "field_status": {
      "prefecture_id": "collected",
      "name_ko": "collected",
      "name_ja": "collected",
      "name_en": "collected",
      "region": "collected"
    },
    "data_confidence": "medium",
    "verified_at": null,
    "verified_source_url": null,
    "verification_note": null
  }
]
```

Recommended `cities.json` shape:

```json
[
  {
    "city_id": "JP-13-HACHIOJI",
    "city_name_ko": "하치오지시",
    "city_name_ja": "八王子市",
    "city_name_en": "Hachioji",
    "prefecture_id": "JP-13",
    "location": "일본 도쿄도",
    "latitude": 35.6664,
    "longitude": 139.316,
    "description": "하치오지시는 일본 도쿄도 서부에 위치한 도시",
    "climate_table": {
      "caption": "기후",
      "wikitext": "{| class=\"wikitable\" ... |}"
    },
    "site_urls": [
      "https://www.city.hachioji.tokyo.jp/",
      "https://www.hkc.or.jp/"
    ],
    "source_name": "Wikipedia/Wikidata",
    "source_url": "https://www.wikidata.org/wiki/Q200832",
    "collected_at": "2026-06-04T00:00:00+09:00",
    "field_status": {
      "city_name_ko": "collected",
      "city_name_ja": "collected",
      "city_name_en": "collected",
      "prefecture_id": "collected",
      "location": "collected",
      "latitude": "collected",
      "longitude": "collected",
      "description": "needs_review",
      "climate_table": "collected",
      "site_urls": "collected"
    },
    "data_confidence": "medium",
    "verified_at": null,
    "verified_source_url": null,
    "verification_note": null
  }
]
```

## Constraints

- Crawl only user-provided, Task-approved, or public index-derived target URLs.
- Respect robots.txt, terms, rate limits, copyright, and privacy.
- Do not collect personal data.
- Do not use unofficial blogs or social media as authoritative sources for final city facts.
- Do not generate fields that are not approved by this spec unless the spec is updated first.
- Store source provenance for license and verification tracking.

## Risks

- Japanese municipality names can collide across regions or differ across Korean, Japanese, and English naming conventions.
- Wikipedia descriptions may require license handling and should be summarized internally.
- Wikipedia climate tables may be absent or inconsistent across city pages.
- Official site URLs may point to city hall pages rather than tourism pages.
- Wikipedia climate tables can be represented as wikitext and may require later table normalization.
- Coordinates can refer to city hall, administrative center, or geographic centroid depending on the source.

## Acceptance Criteria

- AC-CITY-001: A City record can be produced for each approved target city.
- AC-CITY-002: Every produced city record has `city_id`, names, `prefecture_id`, coordinates, description, site URLs, source URL, and collection timestamp.
- AC-CITY-003: Every defined field has a `field_status` value.
- AC-CITY-004: Missing or uncertain fields are visible in the output and are not discarded.
- AC-CITY-005: `city_id` values are stable and unique within the output.
- AC-CITY-006: Description values are short internal summaries with source attribution, not unbounded copied source text.
- AC-CITY-007: Output can be used as the canonical city key set.
- AC-CITY-008: Output is saved as separate JSON files for prefectures and cities.
- AC-CITY-009: Every `cities.json` record references an existing `prefectures.json` record by `prefecture_id`.
- AC-CITY-010: The first implementation outputs only Tokyo Metropolis city records.
- AC-CITY-011: `city_id` values use English romanized names before Korean or Japanese fallback.
- AC-CITY-012: Wikipedia climate tables are stored in `climate_table` when available.
- AC-CITY-013: Up to two official or tourism site URLs are stored in `site_urls`.

## Task Breakdown

### Task: City source and target definition

- Purpose: 도시 수집 대상과 허용 출처를 먼저 확정해 이후 크롤러가 임의 범위로 확장되지 않게 한다.
- Scope: target city list, allowed source list, source priority policy.
- Dependencies: `docs/japan_data_acquisition_plan.md`
- Context Budget: Must read this spec and the City sections of the plan. Do not read non-city data acquisition sections unless city scope is unclear.
- Acceptance Criteria: target city input format and source priority are documented.
- Verification: Review target list sample and source URLs manually.

### Task: City raw acquisition

- Purpose: Wikipedia first, then Wikidata and e-Stat only when needed, to collect City candidate values.
- Scope: raw data fetch and raw evidence output only.
- Dependencies: City source and target definition.
- Context Budget: Must read source priority and data requirements sections.
- Acceptance Criteria: raw output includes source name, source URL, collected timestamp, and original values.
- Verification: Run a small sample against 1-3 approved cities and inspect raw records.

### Task: City normalization

- Purpose: 수집된 원천 값을 서비스에서 사용할 수 있는 City 레코드로 정규화한다.
- Scope: prefecture JSON records, `city_id`, multilingual city names, `prefecture_id`, location, coordinates, description summary, climate table, site URLs.
- Dependencies: City raw acquisition.
- Context Budget: Must read data requirements, output contract, and constraints.
- Acceptance Criteria: normalized output follows the JSON contract.
- Verification: Validate required fields, unique `city_id`, unique `prefecture_id`, city-to-prefecture references, coordinate numeric format, and status values.

### Task: City verification and repair queue

- Purpose: 누락·모호·차단 값을 후속 Web Search Worker 또는 수동 검수 대상으로 분류한다.
- Scope: field status assignment, confidence labeling, verification metadata.
- Dependencies: City normalization.
- Context Budget: Must read acceptance criteria and risks.
- Acceptance Criteria: all fields have one of `collected`, `needs_review`, `missing`, or `blocked`.
- Verification: Inspect records with missing or low-confidence values and confirm repair notes are actionable.

## Verification

- Static document check: confirm this spec references only existing project paths or planned paths.
- Data contract check: validate normalized sample records against required fields.
- Consistency check: confirm City fields match `docs/japan_data_acquisition_plan.md` City section.
- Manual review: confirm source priority and legal constraints are acceptable before implementation.

## Open Questions

- Should Wikipedia climate table wikitext later be normalized into monthly structured values?
- Which exact Tokyo Metropolis city list should be used for the first batch?
