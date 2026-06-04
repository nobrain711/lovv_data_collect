# Spec: 도시 정보 취득

> 기준 계획서: `docs/japan_data_acquisition_plan.md` v0.4
> 문서 상태: 검토용 초안
> 작성일: 2026-06-04
> 담당 역할: Spec Agent

## 요약

이 문서는 Lovv 여행 추천 서비스에서 사용할 도시 단위 데이터를 취득, 정규화, 검증, 저장하는 기준을 정의한다.

범위는 도시 정보 취득으로만 제한한다. 관광지, 축제, 숙박, 맛집 같은 다른 목적지 엔티티의 수집 요구사항은 이 문서에서 정의하지 않는다.

## 전제

- 이 Spec의 대상 국가는 일본이다.
- 첫 구현 대상은 도쿄도로 제한한다.
- 도시 단위는 일본의 시, 정, 촌, 구 또는 이에 준하는 소도시 목적지 단위를 의미한다.
- 초기 기준 문서는 `docs/japan_data_acquisition_plan.md`이다.
- 이 Spec은 구현 요구사항을 준비하는 문서이며, 크롤러 구현 자체는 포함하지 않는다.
- 도시 데이터는 서비스에서 사용할 표준 목적지 목록으로 안정적으로 관리되어야 한다.

## 목표

- 현재 데이터 취득 계획에서 정의한 City 필드를 모두 취득한다.
- 목적지마다 하나의 정규화된 도시 레코드를 만든다.
- 모든 레코드에 출처와 취득 메타데이터를 기록한다.
- 누락되거나 불확실한 값을 후속 보정할 수 있도록 필드별 수집 상태를 기록한다.
- 공식 또는 공공 출처를 우선 사용하고, 저작권 민감 정보는 추적 가능하게 관리한다.
- 수집된 각 도시에 안정적인 `city_id`를 부여한다.
- `city_id` 생성 시 영어 로마자 표기를 우선 사용한다.

## 비목표

- 도시가 아닌 목적지 상세 데이터는 이 Spec에서 크롤링하지 않는다.
- City 요구사항을 넘어서는 최종 Production DB 전체 설계는 이 문서에서 다루지 않는다.
- Wikipedia 원문 설명을 최종 서비스 문구로 길게 복사해 저장하지 않는다.
- 상업 플랫폼의 호텔, 맛집, 예약 데이터는 수집하지 않는다.
- 추천 점수 계산, 랭킹, 일정 생성 로직은 정의하지 않는다.

## 사용자와 행위자

- Data Acquisition Agent: 도시 수집 워크플로를 실행하고 raw output과 normalized output을 작성한다.
- Web Search Worker: 1차 출처로 부족한 누락값이나 오래된 값을 보정한다.
- Human Reviewer: 모호한 값, 출처 사용, 저작권 민감 내용을 검수한다.
- Downstream Recommendation Service: 안정적인 `city_id`를 기준으로 정규화된 도시 레코드를 사용한다.

## 출처 우선순위

| 우선순위 | 출처 | 주요 용도 | 비고 |
| --- | --- | --- | --- |
| 1 | Wikipedia | 도시명, 개요, 위치, 기후 표, 공식 링크 | 모든 도시 필드의 1차 취득 출처로 사용한다. 출처 URL과 라이선스 관련 출처 정보를 보존해야 한다. |
| 2 | Wikidata | 좌표, 다국어 이름, 식별자 | Wikipedia 값이 없거나 모호할 때만 보조 출처로 사용한다. |
| 3 | e-Stat / Statistical LOD | 행정구역 메타데이터와 코드 | Wikipedia만으로 도시 정규화와 동명이역 구분이 부족할 때만 사용한다. |
| 4 | 지자체 또는 공식 관광 사이트 | 공식 사이트 URL과 수동 검증 | 검증 또는 fallback으로 사용한다. 공식 또는 관광 사이트 URL이 2개 있으면 최대 2개까지 저장한다. |

## 데이터 요구사항

### City 필드

| 필드 | 필수 여부 | 수집 방식 | 설명 |
| --- | --- | --- | --- |
| `city_id` | 필수 | 내부 생성 | 영어 로마자 표기를 우선 사용해 생성하는 안정적인 내부 도시 식별자. 예: `JP-13-HACHIOJI` |
| `city_name_ko` | 필수 | Wikipedia / 수동 정규화 | 한국어 UI와 검색에 사용할 한국어 도시명 |
| `city_name_ja` | 필수 | Wikipedia / Wikidata | 일본어 원문 도시명 |
| `city_name_en` | 권장 | Wikipedia / Wikidata | ID, 검색 fallback, 출처 간 매칭에 사용할 영어 도시명 |
| `prefecture_id` | 필수 | Wikipedia / e-Stat / Wikidata | 별도 도도부현 레코드를 참조하는 외래키형 식별자 |
| `location` | 필수 | Wikipedia / Wikidata / e-Stat | 사람이 읽을 수 있는 행정 위치 |
| `latitude` | 필수 | Wikidata / Wikipedia | 대표 위도 |
| `longitude` | 필수 | Wikidata / Wikipedia | 대표 경도 |
| `description` | 필수 | Wikipedia 기반 내부 요약 | 원문 장문 복사가 아닌 내부 한국어 요약 |
| `climate_table` | 권장 | Wikipedia | Wikipedia 페이지에 기후 표가 있으면 해당 표를 저장 |
| `site_urls` | 필수 | Wikipedia 외부 링크 / 공식 사이트 | 지자체 또는 공식 관광 사이트 URL 1-2개 |

### Prefecture 필드

도도부현 데이터는 City 데이터와 분리해서 저장한다. City 레코드는 `prefecture_id`로 도도부현 레코드를 참조해야 한다.

| 필드 | 필수 여부 | 수집 방식 | 설명 |
| --- | --- | --- | --- |
| `prefecture_id` | 필수 | 내부 생성 / e-Stat | `JP-17` 같은 안정적인 도도부현 식별자 |
| `name_ko` | 필수 | Wikipedia / 수동 정규화 | 한국어 도도부현명 |
| `name_ja` | 필수 | Wikipedia / e-Stat / Wikidata | 일본어 도도부현명 |
| `name_en` | 권장 | Wikipedia / Wikidata | 영어 도도부현명 |
| `region` | 권장 | Wikipedia / 수동 정규화 | `Chubu`, `Kansai`, `Kyushu` 같은 일본 지역 구분 |

### 메타데이터 필드

| 필드 | 필수 여부 | 설명 |
| --- | --- | --- |
| `source_name` | 필수 | 레코드 또는 필드의 주 출처명 |
| `source_url` | 필수 | 출처 페이지 또는 API endpoint URL |
| `collected_at` | 필수 | 값을 수집한 시각 |
| `field_status` | 필수 | 필드별 상태: `collected`, `needs_review`, `missing`, `blocked` |
| `data_confidence` | 권장 | `high`, `medium`, `low` 같은 신뢰도 라벨 |
| `verified_at` | 조건부 | 사람 또는 공식 사이트 검증이 발생한 경우 필요 |
| `verified_source_url` | 조건부 | 검증 출처가 수집 출처와 다른 경우 필요 |
| `verification_note` | 조건부 | 값이 모호하거나 수동 정규화되었거나 차단된 경우 필요 |

## 기능 요구사항

- FR-CITY-001: 취득 워크플로는 대상 도시마다 하나의 정규화된 City 레코드를 생성해야 한다.
- FR-CITY-002: 각 City 레코드는 안정적인 `city_id`를 포함해야 한다.
- FR-CITY-003: 각 City 레코드는 `city_name_ko`, `city_name_ja`, `prefecture_id`, `latitude`, `longitude`, `description`, `site_urls`를 포함해야 한다.
- FR-CITY-004: Wikipedia에서 충분한 정보를 제공하는 경우 `city_name_en`, `location`, `climate_table` 수집도 시도해야 한다.
- FR-CITY-005: 모든 필드는 필드 단위 수집 상태를 가져야 한다.
- FR-CITY-006: 누락값은 조용히 버리면 안 되며 `missing`, `needs_review`, `blocked` 중 하나로 표시해야 한다.
- FR-CITY-007: 설명문은 원문 장문 복사가 아니라 출처를 가진 내부 요약문으로 저장해야 한다.
- FR-CITY-008: 좌표는 숫자여야 하며 출처 정보를 포함해야 한다.
- FR-CITY-009: 공식 사이트 URL은 블로그, SNS, 상업 aggregation 사이트보다 지자체 또는 공식 관광 도메인을 우선해야 한다.
- FR-CITY-010: 워크플로는 City 레코드를 감사, 재적재, 보정할 수 있는 충분한 메타데이터를 출력해야 한다.
- FR-CITY-011: 출력은 JSON 파일로 저장하며, 도도부현 데이터와 도시 데이터를 분리 저장해야 한다.
- FR-CITY-012: City 레코드는 `prefecture_id`로 도도부현 레코드를 참조해야 하며, 도도부현 전체 객체를 City 안에 중첩 저장하면 안 된다.
- FR-CITY-013: 첫 구현은 도쿄도 외 도시 레코드를 거부해야 한다.
- FR-CITY-014: `city_id` 생성은 영어 로마자 도시명을 우선해야 한다.
- FR-CITY-015: Wikipedia에서 공식 또는 관광 사이트 URL 2개를 확인할 수 있으면 둘 다 `site_urls`에 저장해야 한다.

## 사용자 흐름

1. Data Acquisition Agent가 대상 도시 목록 또는 승인된 출처 쿼리를 받는다.
2. Agent가 Wikipedia와 Wikidata에서 도시 후보 데이터를 수집한다.
3. Agent가 도도부현 레코드, 도시명, 도시-도도부현 참조, 좌표, 공식 사이트 URL을 정규화한다.
4. Agent가 첫 구현 범위에 맞지 않는 도쿄도 외 레코드를 거부한다.
5. Agent가 국가, 도도부현, 영어 로마자 도시명을 기준으로 `city_id`를 생성한다.
6. Agent가 raw source evidence와 normalized City output을 작성한다.
7. Agent가 각 필드의 상태를 기록한다.
8. Web Search Worker 또는 Human Reviewer가 `missing`, `needs_review`, `blocked` 필드를 처리한다.
9. 승인된 City 레코드는 표준 도시 데이터셋이 된다.

## 출력 계약

초기 구현은 나중에 DB에 적재할 수 있도록 분리된 JSON 파일을 생성해야 한다.

권장 출력 파일:

- `data/normalized/prefectures.json`
- `data/normalized/cities.json`

권장 `prefectures.json` 구조:

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

권장 `cities.json` 구조:

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

## 제약사항

- 사용자 제공, Task 승인, 또는 public index 기반으로 승인된 대상 URL만 수집한다.
- robots.txt, 이용약관, rate limit, 저작권, privacy를 준수한다.
- 개인정보는 수집하지 않는다.
- 비공식 블로그나 SNS를 최종 도시 정보의 authoritative source로 사용하지 않는다.
- 이 Spec에서 승인하지 않은 필드는 Spec 업데이트 전까지 생성하지 않는다.
- 라이선스와 검증 추적을 위해 출처 provenance를 저장한다.

## 위험과 가정

- 일본 행정구역명은 지역에 따라 충돌하거나 한국어, 일본어, 영어 표기가 서로 다를 수 있다.
- Wikipedia 설명은 라이선스 처리가 필요하므로 내부 요약문으로 재작성해야 한다.
- Wikipedia 기후 표는 도시 페이지마다 없거나 형식이 서로 다를 수 있다.
- 공식 사이트 URL은 관광 사이트가 아니라 시청 또는 구청 사이트일 수 있다.
- Wikipedia 기후 표는 wikitext 형태로 저장될 수 있으며, 월별 구조화 값은 후속 정규화가 필요할 수 있다.
- 좌표는 출처에 따라 시청 위치, 행정 중심점, 지리적 중심점 중 하나를 의미할 수 있다.

## 승인 기준

- AC-CITY-001: 승인된 각 대상 도시마다 City 레코드를 생성할 수 있다.
- AC-CITY-002: 모든 City 레코드는 `city_id`, 도시명, `prefecture_id`, 좌표, 설명, 사이트 URLs, 출처 URL, 수집 시각을 가진다.
- AC-CITY-003: 정의된 모든 필드는 `field_status` 값을 가진다.
- AC-CITY-004: 누락되거나 불확실한 필드는 출력에서 확인 가능해야 하며 버려지면 안 된다.
- AC-CITY-005: `city_id`는 출력 내에서 안정적이고 유일해야 한다.
- AC-CITY-006: 설명문은 출처를 가진 짧은 내부 요약문이어야 하며, 출처 원문을 장문으로 그대로 복사하면 안 된다.
- AC-CITY-007: 출력은 표준 도시 key set으로 사용할 수 있어야 한다.
- AC-CITY-008: 출력은 도도부현과 도시를 분리한 JSON 파일로 저장해야 한다.
- AC-CITY-009: 모든 `cities.json` 레코드는 `prefecture_id`로 `prefectures.json`에 존재하는 레코드를 참조해야 한다.
- AC-CITY-010: 첫 구현 출력은 도쿄도 도시 레코드만 포함해야 한다.
- AC-CITY-011: `city_id` 값은 한국어 또는 일본어 fallback보다 영어 로마자명을 우선 사용해야 한다.
- AC-CITY-012: Wikipedia 기후 표가 있으면 `climate_table`에 저장해야 한다.
- AC-CITY-013: 공식 또는 관광 사이트 URL은 최대 2개까지 `site_urls`에 저장해야 한다.

## 작업 분해

### Task: 도시 출처와 대상 정의

- Purpose: 도시 수집 대상과 허용 출처를 먼저 확정해 이후 크롤러가 임의 범위로 확장되지 않게 한다.
- Scope: target city list, allowed source list, source priority policy.
- Dependencies: `docs/japan_data_acquisition_plan.md`
- Context Budget: 이 Spec과 계획서의 City 섹션을 반드시 읽는다. 도시 범위가 불명확한 경우가 아니면 도시 외 데이터 취득 섹션은 읽지 않는다.
- Acceptance Criteria: target city input format과 source priority가 문서화되어 있다.
- Verification: 대상 목록 sample과 source URL을 수동으로 검토한다.

### Task: 도시 raw 데이터 취득

- Purpose: Wikipedia를 우선 사용하고, 필요한 경우에만 Wikidata와 e-Stat에서 City 후보 값을 보조 수집한다.
- Scope: raw data fetch와 raw evidence output만 포함한다.
- Dependencies: 도시 출처와 대상 정의.
- Context Budget: source priority와 data requirements 섹션을 반드시 읽는다.
- Acceptance Criteria: raw output에 source name, source URL, collected timestamp, original values가 포함되어 있다.
- Verification: 승인된 1-3개 도시 sample로 실행하고 raw record를 검토한다.

### Task: 도시 정규화

- Purpose: 수집된 원천 값을 서비스에서 사용할 수 있는 City 레코드로 정규화한다.
- Scope: prefecture JSON records, `city_id`, multilingual city names, `prefecture_id`, location, coordinates, description summary, climate table, site URLs.
- Dependencies: 도시 raw 데이터 취득.
- Context Budget: data requirements, output contract, constraints를 반드시 읽는다.
- Acceptance Criteria: normalized output이 JSON contract를 따른다.
- Verification: required fields, unique `city_id`, unique `prefecture_id`, city-to-prefecture references, coordinate numeric format, status values를 검증한다.

### Task: 도시 검증과 보정 큐

- Purpose: 누락, 모호, 차단 값을 후속 Web Search Worker 또는 수동 검수 대상으로 분류한다.
- Scope: field status assignment, confidence labeling, verification metadata.
- Dependencies: 도시 정규화.
- Context Budget: acceptance criteria와 risks를 반드시 읽는다.
- Acceptance Criteria: 모든 필드는 `collected`, `needs_review`, `missing`, `blocked` 중 하나의 상태를 가진다.
- Verification: missing 또는 low-confidence record를 검토하고 보정 note가 실행 가능한지 확인한다.

## 검증

- 정적 문서 확인: 이 Spec이 실제 존재하는 프로젝트 경로 또는 계획된 경로만 참조하는지 확인한다.
- 데이터 계약 확인: normalized sample record가 required fields를 만족하는지 검증한다.
- 정합성 확인: City 필드가 `docs/japan_data_acquisition_plan.md`의 City 섹션과 일치하는지 확인한다.
- 수동 검토: 구현 전 source priority와 법적 제약이 수용 가능한지 확인한다.

## 열린 질문

- 첫 구현 대상 도시 목록은 무엇인가?
- Wikipedia 기후 표 wikitext를 후속 단계에서 월별 구조화 값으로 정규화할 것인가?
- 첫 batch에 사용할 정확한 도쿄도 도시 목록은 무엇인가?
