# Spec: KR Details JSON S3 Raw 적재 및 ELT 라인

> Source: `data/KR/details/*.json`
> Status: Draft for implementation planning
> Created: 2026-06-09
> Owner role: Spec Agent

## Summary

본 Spec은 `data/KR/details`에 적재된 강원특별자치도·경상북도 도시별 상세 JSON을 source of truth로 사용해, 원본 데이터를 AWS S3 Raw 영역에 먼저 적재하고 이후 ELT 변환으로 확장하기 위한 요구사항을 정의한다.

현재 단계의 핵심 목표는 추가 TourAPI 호출이나 크롤링을 수행하지 않고, 이미 수집된 도시별 상세 JSON 원본을 변경 없이 S3 Raw Prefix에 적재해 재처리 가능한 기준 데이터를 확보하는 것이다. 정규화, 품질 분류, DynamoDB 적재 후보 생성은 S3 Raw 적재 완료 후 다음 Phase에서 수행한다.

## Current Input Snapshot

- 입력 경로: `data/KR/details/*.json`
- 현재 확인된 도시 파일 수: 40
- 현재 포함 엔티티:
  - `meta`: 도시 메타데이터
  - `attractions`: 관광지/음식점/명소 등 상세 항목
  - `festivals`: 축제 항목
  - `visitor_statistics`: 방문자 통계가 있는 경우 포함
- 항목 공통 구조:
  - 기본 필드: `contentid`, `contenttypeid`, `title`, `addr1`, `mapx`, `mapy`, `firstimage`, `tel`, `_assigned_theme`
  - 상세 필드: `detail.common`, `detail.intro`
  - 품질 필드: `field_status`

## Goals

### Phase 1 Goals: S3 Raw 적재 우선

1. `data/KR/details`의 도시별 JSON을 일괄 읽고 raw ingest manifest를 생성한다.
2. 원본 JSON을 변형하지 않고 `s3://<pipeline-bucket>/raw/KR/details/{ingest_date}/...` Prefix에 업로드한다.
3. 입력 파일별 SHA-256 checksum, byte size, city metadata, S3 bucket/key, 업로드 상태를 기록한다.
4. 동일 파일 재실행 시 checksum 기준으로 중복 업로드를 피하거나 동일 key에 대해 멱등적으로 처리한다.
5. 업로드 실패 파일은 전체 배치를 중단하지 않고 failed manifest에 기록한다.

### Phase 2 Goals: ELT Transform 확장

1. S3 Raw 또는 로컬 `data/KR/details`를 입력으로 City, Content, VisitorStatistics 정규화 산출물을 생성한다.
2. `contentid` 기반의 안정적인 entity id와 DynamoDB 적재 후보 item을 생성한다.
3. 좌표, 필수 텍스트, 이미지, 연락처, 테마, 상세 필드 품질을 검증하고 review/failed 후보를 분리한다.
4. 재실행해도 동일 입력에서 동일 산출물이 생성되는 멱등 로컬 ELT를 제공한다.

## Non-Goals

- TourAPI 신규 호출 또는 누락 도시 재수집
- `data/KR/details` 원본 JSON 직접 수정
- DynamoDB 실제 write, Lambda 배포
- S3 Raw 적재 후 자동 Transform 트리거 구성
- 프론트엔드/API 서비스 구현
- JP 데이터 변환

## User Flow

1. 사용자는 `data/KR/details`에 도시별 상세 JSON 파일을 준비한다.
2. Raw ingest CLI를 실행한다.
3. Extract 단계가 입력 파일 목록, 도시 수, 항목 수, source checksum을 manifest로 기록한다.
4. Upload 단계가 원본 JSON을 S3 Raw Prefix에 업로드한다.
5. Upload 결과 manifest가 S3 key, checksum, 업로드 상태, 실패 사유를 기록한다.
6. 사용자는 S3 Raw 적재 결과를 확인한 뒤 Transform/DB 적재 단계로 넘긴다.

## Input Contract

### City Detail File

- 파일명: `{city_name_en}.json` 또는 `{CityName}.json`
- 위치: `data/KR/details`
- 루트 필드:
  - `meta` object 필수
  - `attractions` array 필수
  - `festivals` array 필수
  - `visitor_statistics` object 또는 array 선택
  - `attractions_count_filtered`, `festivals_count_filtered` 선택

### Required Meta Fields

- `city_name_ko`
- `city_name_en`
- `province`
- `lDongRegnCd`
- `lDongSignguCd`

### Required Content Fields

- `contentid`
- `contenttypeid`
- `title`
- `addr1`
- `mapx`
- `mapy`
- `_assigned_theme`
- `detail.common`
- `detail.intro`

필수 필드가 없다고 즉시 전체 배치를 실패시키지 않는다. 항목 단위로 `review` 또는 `failed` 산출물에 분리한다.

## Output Contract

### Phase 1: S3 Raw Ingest Output

기본 로컬 출력 경로는 `data/KR/ingest`로 한다. 이 경로에는 S3 업로드 결과와 재실행 기준 manifest만 저장한다.

```text
data/KR/ingest/
├── raw_manifest.json
├── upload_results.jsonl
└── failed_uploads.jsonl
```

S3 Raw key 형식:

```text
s3://<pipeline-bucket>/raw/KR/details/{ingest_date}/{city_name_en}.json
```

권장 metadata:

- `country = KR`
- `entity = details`
- `city_name_en`
- `city_name_ko`
- `source_checksum_sha256`
- `source_byte_size`
- `ingest_date`

### Phase 2: ELT Output

기본 출력 경로는 `data/KR/elt`로 한다.

```text
data/KR/elt/
├── manifest.json
├── normalized/
│   ├── cities.json
│   ├── contents.jsonl
│   └── visitor_statistics.jsonl
├── load/
│   └── tour_korea_data_items.jsonl
├── quality/
│   ├── summary.json
│   └── issues.jsonl
├── review/
│   ├── location_review.jsonl
│   ├── source_review.jsonl
│   ├── contact_review.jsonl
│   └── theme_review.jsonl
└── failed/
    └── invalid_records.jsonl
```

## Development Environment

- 개발 언어: Python 3.12
- 로컬 가상환경: 프로젝트 루트의 `.venv`
- 의존성 설치:
  - 개발/테스트: `.venv\Scripts\python.exe -m pip install -r requirements.txt`
  - AWS Lambda 패키징용 runtime 의존성은 Task 구현 시 별도 `requirements.txt` 또는 `src/requirements.txt`로 고정한다.
- 실행 기준:
  - 로컬 CLI와 테스트는 항상 `.venv\Scripts\python.exe`를 기준으로 실행한다.
  - 실제 secret은 `.env`에 둘 수 있지만, Raw ingest/ELT 구현은 `.env`를 직접 읽지 않는다.
  - AWS 인증은 `AWS_PROFILE` 또는 CLI 인자 `--profile skn26_final`처럼 AWS SDK 기본 credential chain을 사용한다.

## Source Layout

AWS Lambda/SAM에서 재사용하기 쉬운 `src/` 기반 구조를 사용한다. 기존 `crawling/KR`의 수집 코드는 유지하되, S3 Raw ingest와 ELT 라인은 AWS 배포 가능한 소스 경계로 분리한다.

권장 구조:

```text
src/
└── kr_details_pipeline/
    ├── __init__.py
    ├── raw_ingest.py          # S3 Raw upload service
    ├── manifest.py            # checksum, manifest, upload result records
    ├── s3_keys.py             # deterministic S3 key builder
    ├── cli.py                 # local CLI entrypoint
    ├── handlers/
    │   ├── __init__.py
    │   └── raw_ingest_handler.py  # Lambda-compatible handler
    └── tests/
        ├── test_manifest.py
        ├── test_s3_keys.py
        └── test_raw_ingest.py
```

패키징 원칙:

- Lambda handler는 `src/kr_details_pipeline/handlers/raw_ingest_handler.py`에 둔다.
- 비즈니스 로직은 handler가 아니라 `raw_ingest.py`, `manifest.py`, `s3_keys.py`에 둔다.
- handler는 event parsing과 service 호출만 담당한다.
- 로컬 CLI는 Lambda handler와 같은 service 모듈을 사용한다.
- `data/KR/details`와 `data/KR/ingest`는 runtime input/output artifact이며 소스 패키지에 포함하지 않는다.
- AWS SDK(`boto3`)는 Lambda runtime에 포함되어 있으나, 로컬 테스트를 위해 개발 의존성에는 명시한다.

## Functional Requirements

- FR-RAW-001: `data/KR/details/*.json` 파일을 모두 스캔하고 raw ingest manifest를 생성해야 한다.
- FR-RAW-002: 입력 파일별 SHA-256 checksum, byte size, city name, attraction count, festival count, visitor statistics count를 기록해야 한다.
- FR-RAW-003: 원본 JSON 파일 내용은 업로드 전후에 수정하지 않아야 한다.
- FR-RAW-004: S3 key는 `raw/KR/details/{ingest_date}/{city_name_en}.json` 규칙으로 생성해야 한다.
- FR-RAW-005: S3 object metadata에 country/entity/city/checksum/byte size를 포함해야 한다.
- FR-RAW-006: 같은 checksum의 파일을 같은 ingest date로 재실행할 때 중복 업로드 부작용이 없어야 한다.
- FR-RAW-007: 업로드 실패 파일은 `failed_uploads.jsonl`에 기록하고 나머지 파일 업로드는 계속해야 한다.
- FR-RAW-008: 실행 결과는 `upload_results.jsonl`에 file path, S3 key, checksum, status, error를 기록해야 한다.
- FR-RAW-009: AWS profile, bucket, ingest date, input dir, output dir은 CLI 인자로 주입 가능해야 한다.
- FR-RAW-010: 실제 secret 값은 로그, manifest, metadata에 기록하지 않아야 한다.

Phase 2 Transform 요구사항:

- FR-ELT-001: City 엔티티는 `city_id`, `city_name_ko`, `city_name_en`, `province`, `region_code`, `sigungu_code`를 포함해야 한다.
- FR-ELT-002: Content 엔티티는 `contentid`를 기준으로 `entity_id = KR-CONTENT-{contentid}`를 생성해야 한다.
- FR-ELT-003: `contenttypeid == 15` 또는 festival input array 항목은 `entity_type = festival`로 분류해야 한다.
- FR-ELT-004: 그 외 attraction input array 항목은 `entity_type = attraction`으로 분류해야 한다.
- FR-ELT-005: 좌표는 `mapx`를 longitude, `mapy`를 latitude로 변환하고 한국 범위 밖이면 `location_review`로 분리해야 한다.
- FR-ELT-006: `detail.common.overview`는 description 후보로 사용하고 HTML/제어문자/중복 공백을 정리해야 한다.
- FR-ELT-007: 전화번호는 현재 코드 보정 대상이 아니며, 원본 `tel`, `detail.common.tel`, `detail.intro.infocenter*` 계열을 우선순위로 선택하되 누락 시 `contact_review`로 분리해야 한다.
- FR-ELT-008: `_assigned_theme`가 없거나 허용 테마가 아니면 `theme_review`로 분리해야 한다.
- FR-ELT-009: 이미지 URL은 `firstimage`, `detail.common.firstimage`, `firstimage2` 순으로 선택해야 한다.
- FR-ELT-010: 축제 날짜 필드(`eventstartdate`, `eventenddate`)가 있으면 ISO 날짜, month, season 파생 필드를 생성해야 한다.
- FR-ELT-011: `visitor_statistics`가 있으면 city/month 단위 JSONL로 un-nest해야 한다.
- FR-ELT-012: Transform 결과는 동일 입력에서 항상 동일 순서와 동일 key로 생성되어야 한다.
- FR-ELT-013: 항목 단위 오류는 전체 도시 파일 실패로 전파하지 않고 `failed/invalid_records.jsonl`에 기록해야 한다.

## DynamoDB Candidate Contract

`load/tour_korea_data_items.jsonl`은 실제 DB write 전 후보 산출물이다.

- City metadata item:
  - `PK = CITY#{city_name_en}`
  - `SK = METADATA#city`
- Content item:
  - `PK = CITY#{city_name_en}`
  - `SK = ATTRACTION#{contentid}` 또는 `FESTIVAL#{contentid}`
  - `entity_id = KR-CONTENT-{contentid}`
- Visitor statistics item:
  - `PK = CITY#{city_name_en}`
  - `SK = STAT#{yyyymm}`
  - `entity_id = KR-STAT-{city_name_en}-{yyyymm}`

DB 설계 문서와 최종 테이블명이 다를 수 있으므로, 본 산출물은 "load candidate"로 유지한다. 실제 write adapter는 별도 Task에서 연결한다.

## Quality Rules

- `quality_status = passed`
  - 필수 ID, 제목, 주소, 좌표, 테마, 상세 설명 중 핵심 필드가 유효한 경우
- `quality_status = review`
  - 서비스 노출은 가능하나 검수 필요 필드가 있는 경우
- `quality_status = failed`
  - `contentid`, `title`, city mapping 등 핵심 식별이 불가능한 경우

Review queue:

- `location_review`: 좌표 누락, 0/0, 한국 범위 밖, city와 주소 불일치 의심
- `source_review`: `detail.common`/`detail.intro` 누락 또는 원천 구조 이상
- `contact_review`: tel/infocenter 계열 필드 전체 누락
- `theme_review`: `_assigned_theme` 누락 또는 미허용 테마

## Constraints

- Python 3.12 기준으로 구현한다.
- 프로젝트 로컬 가상환경은 `.venv`를 사용한다.
- S3 Raw ingest/ELT 소스는 AWS 배포 가능한 `src/kr_details_pipeline` 패키지에 둔다.
- 입력 원본 `data/KR/details/*.json`은 수정하지 않는다.
- S3 Raw 적재 단계는 AWS 인증을 AWS profile 또는 환경 인증 체인으로 사용한다.
- `.env` 키나 TourAPI secret은 읽을 필요가 없으며 Raw ingest/ELT 단계에서는 사용하지 않는다.
- Phase 1은 S3 업로드 외 네트워크 호출을 수행하지 않는다.
- Phase 2 ELT는 네트워크 없이 로컬 파일 또는 S3 Raw 객체만으로 실행되어야 한다.
- 재실행 시 기존 출력은 `--overwrite` 또는 run-id 정책으로 명확히 처리한다.
- 대용량 JSON을 다룰 수 있도록 JSONL streaming write를 우선한다.

## Acceptance Criteria

- AC-RAW-001: `data/KR/details` 40개 도시 파일 기준 `raw_manifest.json`이 생성된다.
- AC-RAW-002: 40개 원본 JSON 파일이 S3 Raw Prefix에 업로드된다.
- AC-RAW-003: `upload_results.jsonl`의 성공 record 수가 업로드 성공 파일 수와 일치한다.
- AC-RAW-004: 각 upload result는 local path, S3 bucket, S3 key, checksum, byte size, status를 포함한다.
- AC-RAW-005: 업로드 실패가 발생해도 나머지 파일은 계속 처리되고 실패 파일은 `failed_uploads.jsonl`에 기록된다.
- AC-RAW-006: 동일 입력을 재실행했을 때 checksum 기준으로 멱등 동작한다.
- AC-RAW-007: 로그와 manifest에 AWS secret 또는 TourAPI key가 포함되지 않는다.

Phase 2 Acceptance Criteria:

- AC-ELT-001: `normalized/cities.json`에 40개 city record가 생성된다.
- AC-ELT-002: `normalized/contents.jsonl`의 record 수가 attractions + festivals 입력 수와 일치한다.
- AC-ELT-003: `quality/summary.json`에 city count, attraction count, festival count, passed/review/failed count가 기록된다.
- AC-ELT-004: `load/tour_korea_data_items.jsonl`의 모든 record가 `PK`, `SK`, `entity_id`, `entity_type`, `quality_status`를 가진다.
- AC-ELT-005: 좌표 오류/테마 누락/연락처 누락/상세 누락 샘플이 각 review queue로 분리되는 단위 테스트가 있다.
- AC-ELT-006: 동일 입력으로 2회 실행했을 때 manifest checksum과 normalized output checksum이 동일하다.

## Task Breakdown

### Task: S3 Raw Ingest 구현

- Purpose: `data/KR/details` 원본 JSON을 S3 Raw Prefix에 안전하게 적재한다.
- Scope: `src/kr_details_pipeline` 패키지 생성, 입력 파일 탐색, checksum 계산, S3 key 생성, S3 upload, raw manifest/upload result/failed upload 기록, CLI와 Lambda handler 골격 작성.
- Dependencies: Terraform Phase 0 S3 bucket 구성 완료, AWS profile 설정.
- Context Budget:
  - Must read: 본 Spec의 Phase 1 Goals, Output Contract, Functional Requirements.
  - Must inspect: `data/KR/details` 샘플 1~2개.
  - Do not read: `.env`, 실제 secret 파일.
- Acceptance Criteria:
  - Python 3.12 `.venv`에서 테스트가 실행된다.
  - AWS 배포 가능한 `src/kr_details_pipeline` 구조가 생성된다.
  - 40개 도시 JSON이 S3 Raw Prefix에 업로드된다.
  - 실패 파일이 있어도 나머지 업로드는 계속된다.
  - manifest와 upload result가 재실행 기준으로 사용할 수 있을 만큼 충분한 정보를 가진다.
- Verification:
  - unit test: checksum, S3 key 생성, manifest record 생성
  - integration test: boto3 S3 client mock 기반 upload 검증
  - manual smoke: `.venv\Scripts\python.exe -m kr_details_pipeline.cli raw-ingest --input-dir data/KR/details --bucket <bucket> --profile skn26_final`

### Task: ELT Extract 구현

- Purpose: `data/KR/details` 입력을 안정적으로 스캔하고 배치 manifest를 만든다.
- Scope: 입력 파일 탐색, JSON 로딩, checksum 계산, 도시별 입력 수량 집계.
- Dependencies: S3 Raw Ingest 완료. 로컬 fallback으로 `data/KR/details` 직접 입력도 허용.
- Context Budget:
  - Must read: `data/KR/details` 샘플 1~2개, 본 Spec.
  - Do not read: `.env`, 실제 secret 파일.
- Acceptance Criteria:
  - 40개 도시 파일이 manifest에 기록된다.
  - JSON 파싱 실패 파일은 failed manifest에 남고 전체 실행을 중단하지 않는다.
- Verification:
  - unit test: 정상 파일, 깨진 JSON, 빈 디렉터리
  - CLI smoke: `python -m crawling.KR.elt_cli extract`

### Task: ELT Transform 구현

- Purpose: 도시 상세 JSON을 city/content/statistics 정규화 모델로 변환한다.
- Scope: 필드 정제, ID 생성, 좌표/테마/상세/연락처 품질 판정, 축제 날짜 파생.
- Dependencies: Extract manifest.
- Context Budget:
  - Must read: 본 Spec의 Input/Output Contract, `data/KR/details/chuncheon.json`.
  - Conditional read: `docs/specs/data_pipeline_spec.md`의 DynamoDB 후보 계약.
- Acceptance Criteria:
  - City, Content, VisitorStatistics 정규화 산출물이 생성된다.
  - 항목별 review/failed 분기가 동작한다.
- Verification:
  - unit test: field parser, coordinate validator, theme validator, date parser
  - snapshot test: 춘천 또는 원주 1개 도시 변환 결과

### Task: Load Candidate 생성

- Purpose: 정규화 결과를 DB write 전 JSONL 후보 item으로 변환한다.
- Scope: PK/SK/entity_id/entity_type/quality_status 생성, JSONL streaming write.
- Dependencies: Transform 완료.
- Context Budget:
  - Must read: 본 Spec의 DynamoDB Candidate Contract.
  - Do not read: AWS credentials, `.env`.
- Acceptance Criteria:
  - 모든 load candidate record가 필수 key를 포함한다.
  - 동일 contentid 재실행 시 동일 PK/SK가 생성된다.
- Verification:
  - unit test: City/Attraction/Festival/Statistic item key 생성
  - contract test: JSONL record 필수 키 검증

### Task: Quality Report 및 CLI

- Purpose: 사용자가 ELT 결과를 빠르게 검수할 수 있게 summary와 실행 명령을 제공한다.
- Scope: `quality/summary.json`, `quality/issues.jsonl`, review queue 파일, CLI 통합.
- Dependencies: Extract/Transform/Load candidate 생성.
- Context Budget:
  - Must read: 본 Spec의 Quality Rules.
- Acceptance Criteria:
  - passed/review/failed 수량이 summary에 기록된다.
  - review queue별 파일이 생성된다.
  - CLI 한 번으로 end-to-end 로컬 ELT가 실행된다.
- Verification:
  - end-to-end test: fixture directory -> `data/KR/elt` style output
  - manual smoke: 현재 `data/KR/details` 기준 실행 후 수량 확인

## Verification Plan

- Unit:
  - S3 key builder/checksum/upload manifest 생성
  - JSON loader/checksum
  - content id/entity id 생성
  - 좌표 parser/range validator
  - theme validator
  - phone fallback selector
  - festival date parser
- Integration:
  - S3 mock: 40개 파일 업로드 요청과 결과 manifest 생성
  - fixture 도시 1개 입력 → manifest/normalized/load/quality/review/failed 생성
- Contract:
  - `raw_manifest.json`, `upload_results.jsonl` 필수 key 검증
  - `load/tour_korea_data_items.jsonl` 필수 key 검증
  - `contents.jsonl` 수량이 입력 attractions+festivals와 일치하는지 검증
- Manual:
  - `data/KR/details` 40개 도시 대상으로 S3 Raw 업로드 실행
  - `data/KR/details` 40개 도시 대상으로 ELT 실행
  - `quality/summary.json`에서 실패/검수 수량 확인

## Risks

- 현재 `data/KR/details`는 일부 항목의 `field_status` key가 기존 샘플과 다를 수 있다.
- `contenttypeid`가 관광지/축제 외 음식점 등 다른 타입을 포함하므로 entity subtype 정책이 필요할 수 있다.
- 전화번호 보정 JSON은 아직 도입하지 않으므로 contact quality는 낮게 나올 수 있다.
- DB 설계 문서와 `TourKoreaData` 후보 계약이 최종 불일치할 수 있어 실제 DB write 전 adapter 조정이 필요하다.

## Open Questions

1. `contenttypeid=39` 음식점 항목을 `attraction` 하위 subtype으로 둘지, 별도 `restaurant` entity type으로 분리할지 결정 필요.
2. `visitor_statistics` 최종 저장 schema는 DB 설계 문서 기준으로 별도 테이블/단일테이블 중 하나를 확정해야 한다.
3. tel 보정 JSON의 위치와 schema는 추후 별도 Spec 또는 Task에서 정의한다.
4. ELT 산출물을 Git 추적 대상에 포함할지, 로컬/generated artifact로 둘지 결정 필요.
