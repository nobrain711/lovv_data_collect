# Spec: KR Raw 전처리 및 DynamoDB 도메인별 적재 계약

> Source: `data/KR/details/*.json`, `s3://<bucket>/raw/KR/details/{ingest_date}/*.json`
> Status: Draft for implementation planning
> Created: 2026-06-10
> Owner role: Spec Agent
> Execution mode: Sequential Mode

## Summary

현재 KR 상세 Raw 데이터는 `attractions` 배열 안에 관광지, 음식점, 기타 콘텐츠가 섞여 있고 `festivals` 배열은 축제 항목을 별도로 가진다. 기존 Transform/Load 흐름은 이 혼합 데이터를 `attraction` 또는 `festival` 중심으로 적재하면서 음식점 컬럼과 관광지 컬럼이 섞일 가능성이 있다.

본 Spec은 Raw 데이터를 DynamoDB에 적재하기 전에 `restaurant`, `attraction`, `festival` 3개 도메인으로 명확히 분류하고, 각 도메인에 필요한 컬럼만 남긴 뒤 `TourKoreaData`에 적재하는 전처리 계약을 정의한다.

## Goals

1. Raw record를 DynamoDB item으로 바로 변환하지 않고 도메인 분류 단계를 반드시 거친다.
2. 음식점, 관광지, 축제 item은 각자 허용된 컬럼만 가진다.
3. 분류 불가 또는 제외 대상 콘텐츠는 DynamoDB 적재 대상에서 제외하고 review/failed 산출물로 보낸다.
4. `PK`, `SK`, `entity_id`, `entity_type`, `quality_status`는 모든 적재 item에서 일관되게 유지한다.
5. 기존 S3 Raw 보관 계약은 유지하고, 전처리/적재 단계만 보정한다.

## Non-Goals

- Raw JSON 원본 수정
- TourAPI 신규 호출 또는 재크롤링
- 음식점 상세 메뉴 정규화 고도화
- tel 보정 JSON 도입
- 방문통계 외부 보정 또는 별도 통계 수집
- 추천 알고리즘 또는 검색 API 구현

## Problem Statement

현재 구조의 위험은 다음과 같다.

- `attractions` 배열 안에 `contenttypeid=39` 음식점이 포함될 수 있다.
- 음식점 전용 필드(`treatmenu`, `opentimefood`, `restdatefood`, `parkingfood`)와 관광지 전용 필드(`usetime`, `expguide`, `heritage*`)가 같은 item contract에 섞일 수 있다.
- 축제 전용 날짜 필드(`eventstartdate`, `eventenddate`)가 일반 관광지 item에 남거나, 반대로 축제 item에서 누락될 수 있다.
- DynamoDB item이 너무 넓어지고 entity별 필드 의미가 불명확해진다.

따라서 적재 전 Transform은 반드시 "분류 -> 도메인별 컬럼 projection -> 품질 판정 -> DynamoDB item 생성" 순서로 실행해야 한다.

## Input Contract

### Raw City File

- 위치:
  - local: `data/KR/details/{city}.json`
  - S3: `raw/KR/details/{ingest_date}/{city}.json`
- 루트 필드:
  - `meta`
  - `attractions`
  - `festivals`
  - `visitor_statistics` optional

### Raw Content Fields

Raw record는 다음 후보 필드를 가질 수 있다.

- 공통 후보:
  - `contentid`
  - `contenttypeid`
  - `title`
  - `addr1`
  - `mapx`
  - `mapy`
  - `firstimage`
  - `firstimage2`
  - `tel`
  - `_assigned_theme`
  - `detail.common`
  - `detail.intro`
- 음식점 후보:
  - `detail.intro.infocenterfood`
  - `detail.intro.opentimefood`
  - `detail.intro.restdatefood`
  - `detail.intro.treatmenu`
  - `detail.intro.parkingfood`
- 관광지 후보:
  - `detail.intro.infocenter`
  - `detail.intro.usetime`
  - `detail.intro.restdate`
  - `detail.intro.parking`
  - `detail.intro.expguide`
- 축제 후보:
  - `detail.intro.eventstartdate`
  - `detail.intro.eventenddate`
  - `detail.intro.eventplace`
  - `detail.intro.sponsor1`
  - `detail.intro.sponsor1tel`
  - `detail.intro.playtime`
  - `detail.intro.usetimefestival`

## Domain Classification Contract

### Classification Rules

1. `contenttypeid == "39"`이면 `entity_type = restaurant`.
2. `contenttypeid == "15"` 또는 Raw의 `festivals` 배열에서 온 항목이면 `entity_type = festival`.
3. `contenttypeid`가 `"12"`, `"14"`, `"28"` 중 하나이면 `entity_type = attraction`.
4. 위 규칙에 포함되지 않는 콘텐츠는 DynamoDB 적재 대상에서 제외하고 `review/source_review.jsonl`에 기록한다.
5. `contentid` 또는 `title`이 없으면 도메인 분류와 관계없이 `failed/invalid_records.jsonl`로 보낸다.

### Content Type Policy

| contenttypeid | 의미 | 적재 entity_type | 처리 |
| --- | --- | --- | --- |
| `12` | 관광지 | `attraction` | 적재 |
| `14` | 문화시설 | `attraction` | 적재 |
| `15` | 축제/공연/행사 | `festival` | 적재 |
| `28` | 레포츠 | `attraction` | 적재 |
| `39` | 음식점 | `restaurant` | 적재 |
| 기타 | 숙박/쇼핑/코스/불명 | none | review 제외 |

## DynamoDB Item Contract

### Common Columns

모든 적재 item은 아래 공통 컬럼만 공유한다.

| column | required | note |
| --- | --- | --- |
| `PK` | yes | `CITY#{city_name_en}` |
| `SK` | yes | 도메인별 SK |
| `entity_id` | yes | 도메인별 안정 ID |
| `entity_type` | yes | `restaurant`, `attraction`, `festival`, `city_metadata`, `visitor_statistics` 중 하나 |
| `content_id` | yes | TourAPI `contentid` |
| `contenttypeid` | yes | 원천 content type |
| `city_id` | yes | KR city id |
| `city_name_en` | yes | city partition name |
| `city_name_ko` | no | 표시용 |
| `province` | no | 표시/필터용 |
| `title` | yes | 표시명 |
| `address` | no | `addr1` 기반 |
| `longitude` | no | `mapx` numeric |
| `latitude` | no | `mapy` numeric |
| `image_url` | no | 대표 이미지 |
| `description` | no | `detail.common.overview` 정제값 |
| `quality_status` | yes | `passed`, `review`, `failed` |
| `review_queues` | yes | review reason list |
| `source_key` | yes | S3 raw key 또는 local source |

공통 컬럼 외 도메인별 허용 컬럼만 남긴다.

### City Metadata Item

- Key:
  - `PK = CITY#{city_name_en}`
  - `SK = METADATA#city`
  - `entity_id = CITY-{city_id}`
- Allowed columns:
  - `city_id`
  - `city_name_en`
  - `city_name_ko`
  - `province`
  - `province_key`
  - `city_key`
  - `domain_sort_key`
  - `sigungus_included`
  - `scraped_at`

### Visitor Statistics Item

- Key:
  - `PK = CITY#{city_name_en}`
  - `SK = STAT#{yyyymm}`
  - `entity_id = STAT-{city_id}-{yyyymm}`
- Allowed columns:
  - `year`
  - `month`
  - `days`
  - `locals_total`
  - `locals_daily_avg`
  - `out_of_town_total`
  - `out_of_town_daily_avg`
  - `foreigners_total`
  - `foreigners_daily_avg`
  - `total_visitors`
  - `total_daily_avg`
  - `annual_totals`
  - `annual_daily_averages`

### Restaurant Item

- Key:
  - `PK = CITY#{city_name_en}`
  - `SK = RESTAURANT#{contentid}`
  - `entity_id = REST-{contentid}`
- Allowed columns:
  - common columns
  - `restaurant_category`
  - `cuisine_tags`
  - `phone`
  - `opening_hours`
  - `closed_days`
  - `signature_menu`
  - `parking`
- Source mapping:
  - `phone`: `tel` -> `detail.common.tel` -> `detail.intro.infocenterfood`
  - `opening_hours`: `detail.intro.opentimefood`
  - `closed_days`: `detail.intro.restdatefood`
  - `signature_menu`: `detail.intro.treatmenu`
  - `parking`: `detail.intro.parkingfood`
  - `restaurant_category`: `_assigned_theme` 또는 `cat3`

Restaurant item에는 축제 날짜 컬럼(`eventstartdate`, `eventenddate`, `season`)을 남기지 않는다.

### Attraction Item

- Key:
  - `PK = CITY#{city_name_en}`
  - `SK = ATTRACTION#{contentid}`
  - `entity_id = ATT-{contentid}`
- Allowed columns:
  - common columns
  - `theme`
  - `theme_tags`
  - `phone`
  - `opening_hours`
  - `closed_days`
  - `experience_guide`
  - `parking`
  - `season_tags`
- Source mapping:
  - `theme`: `_assigned_theme` -> `detail.intro.cat3` -> `cat3`
  - `phone`: `tel` -> `detail.common.tel` -> `detail.intro.infocenter`
  - `opening_hours`: `detail.intro.usetime`
  - `closed_days`: `detail.intro.restdate`
  - `experience_guide`: `detail.intro.expguide`
  - `parking`: `detail.intro.parking`

Attraction item에는 음식점 메뉴 컬럼(`signature_menu`)과 축제 전용 날짜 컬럼을 남기지 않는다.

### Festival Item

- Key:
  - `PK = CITY#{city_name_en}`
  - `SK = FESTIVAL#{contentid}`
  - `entity_id = FEST-{contentid}`
- Allowed columns:
  - common columns
  - `event_start_date`
  - `event_end_date`
  - `month`
  - `season`
  - `season_tags`
  - `visit_months`
  - `venue`
  - `organizer`
  - `organizer_phone`
  - `playtime`
  - `fee_text`
- Source mapping:
  - `event_start_date`: `detail.intro.eventstartdate` -> ISO date
  - `event_end_date`: `detail.intro.eventenddate` -> ISO date
  - `month`: `event_start_date` month
  - `season`: `event_start_date` season
  - `visit_months`: start/end range month list
  - `venue`: `detail.intro.eventplace` -> `addr1`
  - `organizer`: `detail.intro.sponsor1`
  - `organizer_phone`: `detail.intro.sponsor1tel`
  - `playtime`: `detail.intro.playtime`
  - `fee_text`: `detail.intro.usetimefestival`

Festival item에는 음식점 운영시간/메뉴 컬럼과 관광지 체험 안내 컬럼을 남기지 않는다.

## Output Contract

### Local Transform Output

```text
data/KR/elt/
├── normalized/
│   ├── restaurants.jsonl
│   ├── attractions.jsonl
│   ├── festivals.jsonl
│   ├── city_metadata.jsonl
│   └── visitor_statistics.jsonl
├── load/
│   └── tour_korea_data_items.jsonl
├── quality/
│   ├── summary.json
│   └── issues.jsonl
├── review/
│   ├── source_review.jsonl
│   ├── location_review.jsonl
│   ├── theme_review.jsonl
│   └── contact_review.jsonl
└── failed/
    └── invalid_records.jsonl
```

### S3 Processed Output

```text
processed/KR/details/{ingest_date}/restaurants/{city}.json
processed/KR/details/{ingest_date}/attractions/{city}.json
processed/KR/details/{ingest_date}/festivals/{city}.json
processed/KR/details/{ingest_date}/review/{queue}/{city}.json
processed/KR/details/{ingest_date}/failed/{city}.json
```

## Functional Requirements

- FR-PRE-001: Transform는 Raw record를 먼저 `restaurant`, `attraction`, `festival`, `excluded`, `failed` 중 하나로 분류해야 한다.
- FR-PRE-002: DynamoDB load item은 도메인별 allowlist 컬럼만 포함해야 한다.
- FR-PRE-003: 음식점 item은 `SK = RESTAURANT#{contentid}`, `entity_id = REST-{contentid}`를 사용해야 한다.
- FR-PRE-004: 관광지 item은 `SK = ATTRACTION#{contentid}`, `entity_id = ATT-{contentid}`를 사용해야 한다.
- FR-PRE-005: 축제 item은 `SK = FESTIVAL#{contentid}`, `entity_id = FEST-{contentid}`를 사용해야 한다.
- FR-PRE-006: 분류 불가 contenttypeid는 DynamoDB 적재 대상에서 제외하고 review payload에 남겨야 한다.
- FR-PRE-007: `contentid`, `title` 누락은 failed로 분류해야 한다.
- FR-PRE-008: 좌표가 없거나 한국 범위를 벗어나면 `location_review`를 추가해야 한다.
- FR-PRE-009: 연락처 후보가 전혀 없으면 `contact_review`를 추가하되, 현재 단계에서 tel 보정 JSON은 사용하지 않는다.
- FR-PRE-010: 동일 Raw 입력은 동일한 정렬 순서와 동일한 DynamoDB key를 생성해야 한다.
- FR-PRE-011: 도시 메타는 `METADATA#city` item으로 생성해야 한다.
- FR-PRE-012: 방문통계는 월별 `STAT#yyyymm` item으로 생성해야 한다.

## Acceptance Criteria

- AC-PRE-001: `contenttypeid=39`는 `restaurant`로 분리되고 `RESTAURANT#` SK를 가진다.
- AC-PRE-002: `contenttypeid=15`와 `festivals` 배열 항목은 `festival`로 분리되고 `FESTIVAL#` SK를 가진다.
- AC-PRE-003: `contenttypeid=12`, `14`, `28`은 `attraction`으로 분리되고 `ATTRACTION#` SK를 가진다.
- AC-PRE-004: Restaurant item에는 `event_start_date`, `event_end_date`, `experience_guide`가 없어야 한다.
- AC-PRE-005: Attraction item에는 `signature_menu`, `event_start_date`, `event_end_date`가 없어야 한다.
- AC-PRE-006: Festival item에는 `signature_menu`, `opening_hours`, `experience_guide`가 없어야 한다.
- AC-PRE-007: `load/tour_korea_data_items.jsonl`의 모든 item이 도메인별 allowlist 검증을 통과한다.
- AC-PRE-008: review/failed로 분기된 record는 원천 `source_key`, `contentid`, `reason`을 포함한다.
- AC-PRE-009: `visitor_statistics.monthly_statistics[]` 12건은 `STAT#yyyymm` item으로 생성된다.
- AC-PRE-010: `meta.sigungus_included`와 `meta.scraped_at`은 `METADATA#city` item에 보존된다.

## Task Breakdown

### Task: 도메인 분류 규칙 구현

- Purpose: Raw record가 음식점/관광지/축제 중 어디에 속하는지 먼저 결정한다.
- Scope: contenttypeid 기반 classifier, source array fallback, excluded/review 분기.
- Dependencies: 기존 Raw ingest 완료.
- Context Budget:
  - Must read: 본 Spec의 Domain Classification Contract.
  - Must inspect: `src/kr_details_pipeline/transform.py`.
  - Do not read: `.env`, AWS credential 파일.
- Acceptance Criteria:
  - contenttypeid별 분류 테스트가 존재한다.
  - 분류 불가 콘텐츠가 DynamoDB item으로 생성되지 않는다.
- Verification:
  - unit test: `39`, `15`, `12`, unknown contenttypeid 케이스.

### Task: 도메인별 projection 구현

- Purpose: DynamoDB item에 도메인별 필요한 컬럼만 남긴다.
- Scope: restaurant/attraction/festival projection 함수, allowlist validator.
- Dependencies: 도메인 분류 규칙 구현.
- Context Budget:
  - Must read: 본 Spec의 DynamoDB Item Contract.
  - Conditional read: `src/kr_details_pipeline/load.py`.
- Acceptance Criteria:
  - 각 entity item이 허용 컬럼 외 필드를 포함하지 않는다.
  - 공통 컬럼은 모든 item에 포함된다.
- Verification:
  - unit test: entity별 forbidden field 검증.

### Task: Load contract 보정

- Purpose: `TourKoreaData`에 적재되는 key와 entity_id를 도메인별로 안정화한다.
- Scope: `RESTAURANT#`, `ATTRACTION#`, `FESTIVAL#` SK 생성 및 `REST-`, `ATT-`, `FEST-` entity_id 생성.
- Dependencies: projection 구현.
- Context Budget:
  - Must read: 본 Spec의 Common Columns, Restaurant/Attraction/Festival Item.
- Acceptance Criteria:
  - 동일 contentid 재실행 시 동일 PK/SK/entity_id가 생성된다.
  - restaurant와 attraction이 같은 contentid를 공유해도 SK prefix로 충돌하지 않는다.
- Verification:
  - unit test: key generation contract.

### Task: 품질/리뷰 라우팅 보정

- Purpose: 적재 제외와 검수 필요를 명확히 분리한다.
- Scope: missing key, unknown contenttypeid, 좌표 오류, 연락처 누락, 테마 누락 라우팅.
- Dependencies: 도메인별 projection 구현.
- Context Budget:
  - Must read: 본 Spec의 Functional Requirements, Acceptance Criteria.
- Acceptance Criteria:
  - failed와 review가 item 단위로 분리된다.
  - review/failed 산출물이 source 추적 정보를 가진다.
- Verification:
  - unit test: failed/review reason별 라우팅.

## Verification Plan

- Unit:
  - classifier: `contenttypeid`별 entity 분류
  - projection: 도메인별 allowlist/forbidden field 검증
  - key generation: PK/SK/entity_id 규칙
  - quality routing: failed/review/excluded 분기
- Integration:
  - 샘플 도시 1개 Raw -> restaurants/attractions/festivals JSONL 생성
  - `tour_korea_data_items.jsonl` 전체 allowlist 검증
- Manual:
  - 현재 `data/KR/details` 기준 실행 후 restaurant/attraction/festival 수량 확인
  - DynamoDB 적재 전 샘플 item 10개를 눈으로 검수

## Risks

- TourAPI `contenttypeid` 정책이 원천 데이터에서 누락되면 source array 기반 fallback이 필요하다.
- `contenttypeid=14`, `28`을 관광지로 포함하는 정책은 서비스 기획에서 조정될 수 있다.
- 음식점 데이터를 별도 `restaurant`로 분리하면 기존 `GSI1`, `GSI2` 조회 문서와 테스트도 함께 갱신해야 한다.
- `geohash_prefix`가 아직 `UNKNOWN`이면 위치 기반 GSI 검색 품질은 개선되지 않는다.

## Open Questions

1. `contenttypeid=14` 문화시설과 `28` 레포츠를 관광지로 유지할지, 별도 subtype을 둘지 확인 필요.
2. 음식점의 `cuisine_tags`를 현재 `_assigned_theme` 기반으로 둘지, 별도 메뉴/카테고리 매핑을 만들지 결정 필요.
3. `visitor_statistics`의 장기 저장 위치를 본 도메인 테이블에 유지할지 별도 통계 테이블로 분리할지 결정 필요.
