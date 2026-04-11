# Implementation Plan: QBT Live - Step 5 데이터 수집 + CSV (data_fetcher.py)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-11 13:20
**마지막 업데이트**: 2026-04-11 13:20
**관련 범위**: live (신규 도메인)
**관련 문서**:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (2장, 부록 A)
- [docs/TODO_QBT_LIVE.md](../TODO_QBT_LIVE.md) (Step 5)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [src/qbt/utils/data_loader.py](../../src/qbt/utils/data_loader.py) (재사용 대상: `load_stock_data`)
- [src/qbt/utils/stock_downloader.py](../../src/qbt/utils/stock_downloader.py) (참고: `validate_stock_data`, `download_stock_data` 패턴)
- [src/qbt/common_constants.py](../../src/qbt/common_constants.py) (컬럼 상수)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `fetch_recent_ohlc(ticker, days=5)` — yfinance 에서 최근 N 일 OHLCV 를 QBT 표준 포맷(Date, Open, High, Low, Close, Volume)으로 반환
- [x] 목표 2: `append_today_to_csv(csv_path, today_row)` — 기존 CSV 에 1 행 append, 동일 날짜 중복 방지, 빈/없는 파일 대응
- [x] 목표 3: `rebuild_full_csv(ticker, csv_path, period="max")` — yfinance 전체 기간 다운로드 후 CSV 완전 재작성 (스플릿 대응)
- [x] 목표 4: `load_csv(csv_path)` — QBT `load_stock_data` 재사용 (live 전용 wrapper)
- [x] 목표 5: 테스트 전체에서 yfinance 실제 호출 없음 (mock 필수)
- [x] 목표 6: TODO T-5.1 ~ T-5.4 전체 통과

## 2) 비목표(Non-Goals)

- 데이터 검증 3종 (OHLC 논리 / 종가 연속성 / 날짜 누락) — Step 6 `data_validator.py` 소관
- yfinance 실제 호출 (테스트에서 mock)
- init-data / rebuild-data CLI 명령어 (Step 10 `cli.py`)
- QBT `download_stock_data` 확장 / 수정 — live 는 다른 저장 경로와 다른 필터링 정책이 필요하므로 별도 함수

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- live 환경은 매일 GitHub Actions 에서 실행되어 1 행씩 CSV 에 누적 append 하는 패턴 (설계서 2.2)
- QBT 본체의 `download_stock_data` 는 전체 기간 일괄 다운로드 + "오늘 포함 최근 2일 제외" 필터가 하드코딩되어 있어 매일 실행 모드에 부적합
- QBT 본체의 `load_stock_data` 는 그대로 재사용 가능 (포맷 호환)
- yfinance 는 외부 네트워크 호출이므로 테스트에서는 반드시 mock 처리

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [live/CLAUDE.md](../../live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 외부 네트워크 금지 / mock 사용
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) (2장 주가 데이터 CSV 누적)
- [src/qbt/utils/CLAUDE.md](../../src/qbt/utils/CLAUDE.md)

### 설계 결정

#### D1. QBT 본체 재사용 — **`load_stock_data` 재사용, `download_stock_data` 는 재사용 안 함**

- `load_csv` 는 내부적으로 `qbt.utils.data_loader.load_stock_data` 를 호출하여 live 경로에 대해서도 동일한 파싱 / 정렬 / 중복 제거 / 필수 컬럼 검증을 적용. live 에서 보조 wrapper 를 제공하는 이유: live 경로 인자(`DEFAULT_LIVE_STATE_DIR` 하위)를 편리하게 전달하고, 후속 리팩터 시 내부 구현을 바꿀 수 있는 일관된 인터페이스 확보.
- `download_stock_data` 는 재사용 **안 함**. 이유:
  1. "최근 2일 필터링" 이 하드코딩되어 live 매일 실행 모드와 충돌 (live 는 어제/오늘 데이터가 필요)
  2. CSV 저장 경로가 `STOCK_DIR` 로 고정되어 live 의 `DEFAULT_LIVE_STATE_DIR / data/stock/` 경로와 다름
  3. 파일명 규칙이 달라짐 (QBT: `{TICKER}_max.csv`, live: `{TICKER}.csv` — 설계서 1.3)
- 대신 live 는 `yfinance.Ticker(ticker).history(period=...)` 를 직접 호출하고 QBT 표준 컬럼 포맷으로 변환하는 얇은 래퍼를 자체 구현.

#### D2. 함수 시그니처 (부록 A 준수)

```python
def fetch_recent_ohlc(ticker: str, days: int = 5) -> pd.DataFrame
def append_today_to_csv(csv_path: Path, today_row: pd.DataFrame) -> None
def rebuild_full_csv(ticker: str, csv_path: Path, period: str = "max") -> None
def load_csv(csv_path: Path) -> pd.DataFrame
```

- `fetch_recent_ohlc` 는 "오늘 포함 최근 N 일" 을 반환 (QBT 와 달리 오늘 제외하지 않음 — 매일 실행 시 당일 필요)
- `append_today_to_csv` 의 `today_row` 는 **1 행 DataFrame**. 호출자가 `fetch_recent_ohlc` 결과에서 마지막 행을 추출해 전달.
- `append_today_to_csv` 는 다음 규칙:
  - 파일 없음 → 부모 디렉토리 생성 + 헤더 + 1 행 저장
  - 파일 있고 해당 날짜 미존재 → 기존 CSV 로드 → `pd.concat` → 저장
  - 파일 있고 해당 날짜 존재 → 변경 없음 (DEBUG 로그 후 return)
  - 가격 컬럼 6 자리 반올림 (CLAUDE.md 출력 데이터 규칙)
- `rebuild_full_csv` 는 기존 파일을 덮어쓰기. 부모 디렉토리 자동 생성.

#### D3. 파일 I/O 규칙

- 부모 디렉토리 없으면 `path.parent.mkdir(parents=True, exist_ok=True)` 로 자동 생성
- CSV 저장은 `df.to_csv(path, index=False)` (QBT 와 동일 패턴)
- 가격 컬럼(Open/High/Low/Close) 6 자리 반올림
- 정렬: Date 오름차순 (load 시 정렬 보장)

#### D4. 검증 범위 — **Step 5 에서는 검증하지 않는다**

- OHLC 논리 (High < Low), 종가 연속성, 날짜 누락 검증은 **Step 6 `data_validator.py` 소관**
- `fetch_recent_ohlc` 는 yfinance 가 빈 DataFrame 을 반환하면 즉시 `ValueError("yfinance 데이터 없음: {ticker}")` 만 확인 (단순 입력 검증)
- 가격/날짜 이상 검증은 호출자(CLI) 가 `data_validator` 를 거쳐 수행

#### D5. yfinance mock 전략

- 테스트에서는 `yfinance.Ticker` 를 `monkeypatch` 로 대체하거나 `unittest.mock.patch` 사용
- mock 이 반환하는 객체는 `history(period=..., start=..., end=...)` 메서드가 pandas DataFrame 을 돌려주는 형태
- DataFrame 은 `DatetimeIndex` + `Open/High/Low/Close/Volume` 컬럼 (실제 yfinance 반환 포맷)

## 4) 완료 조건(Definition of Done)

- [x] `live/src/live/data_fetcher.py` 에 4 개 함수 모두 구현
- [x] `live/tests/test_data_fetcher.py` 작성 및 통과 (T-5.1 ~ T-5.4 포함 + mock yfinance, 22개 테스트)
- [x] 테스트에서 **실제 yfinance 호출 없음** (`_FakeYfTicker` + monkeypatch)
- [x] QBT 본체(`src/qbt/`) 수정 없음 (`git status src/qbt/` clean)
- [x] `poetry run black .` 실행 완료
- [x] `poetry run python validate_project.py` 통과 (passed=628, failed=0, skipped=0)
- [x] `docs/TODO_QBT_LIVE.md` Step 5 체크박스 체크
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

#### 신규 작성 (내용 채우기)

- `live/src/live/data_fetcher.py` (현재 docstring 만 있음)

#### 신규 생성 (테스트)

- `live/tests/test_data_fetcher.py`

#### 수정

- `docs/TODO_QBT_LIVE.md` (Step 5 체크박스)
- `live/CLAUDE.md` (모듈별 역할 요약에 data_fetcher 책임 구체화 — 필요 시)

#### README 변경 여부

- `README.md`: **변경 없음**

### 데이터/결과 영향

- 없음 (외부 호출은 모두 mock)
- QBT 본체 `tests/` 결과에 영향 없음

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 테스트 선작성 (레드 허용)

**작업 내용**:

- [x] `live/tests/test_data_fetcher.py` 작성:

  - `TestFetchRecentOhlc` (yfinance mock):
    - `test_returns_dataframe_with_required_columns` — 컬럼이 `Date, Open, High, Low, Close, Volume`
    - `test_date_column_is_date_objects` — Date 는 `datetime.date`
    - `test_empty_yfinance_response_raises` — mock 이 빈 DF 반환 시 `ValueError`
    - `test_prices_rounded_to_6_decimals`
    - `test_does_not_filter_recent_two_days` — QBT download_stock_data 와 다르게 오늘 포함

  - `TestAppendTodayToCsv`:
    - `test_append_to_csv_with_3_rows_results_in_4_t_5_1` — T-5.1
    - `test_append_same_date_is_noop_t_5_2` — T-5.2
    - `test_append_to_empty_csv_t_5_4` — T-5.4 (파일 없음 / 빈 파일)
    - `test_append_creates_parent_directory` — 부모 디렉토리 자동 생성
    - `test_append_sorts_by_date` — 기존 데이터와 새 행이 날짜 역순이어도 정렬 유지
    - `test_append_rounds_prices` — 가격 6자리 반올림

  - `TestLoadCsv`:
    - `test_load_csv_compatible_with_qbt_load_stock_data_t_5_3` — T-5.3: live `load_csv` 결과와 QBT `load_stock_data` 결과가 동일
    - `test_load_csv_missing_file_raises`
    - `test_load_csv_missing_column_raises`

  - `TestRebuildFullCsv` (yfinance mock):
    - `test_rebuild_overwrites_existing_file` — 기존 파일 덮어쓰기
    - `test_rebuild_creates_parent_directory`
    - `test_rebuild_uses_period_max_by_default`
    - `test_rebuild_saves_required_columns`

### Phase 1 — data_fetcher.py 구현 (그린 유지)

**작업 내용**:

- [x] `live/src/live/data_fetcher.py` 구현:
  - 모듈 상단: `import yfinance as yf`, `from qbt.common_constants import COL_DATE, PRICE_COLUMNS, REQUIRED_COLUMNS`, `from qbt.utils.data_loader import load_stock_data`
  - 공통 헬퍼 `_yf_history_to_qbt_df(raw_df) -> pd.DataFrame`:
    - index → Date 컬럼 변환 (`datetime.date`)
    - `REQUIRED_COLUMNS` 만 선택
    - 가격 컬럼 6 자리 반올림
    - Date 오름차순 정렬
  - `fetch_recent_ohlc(ticker, days=5)`:
    - `yf.Ticker(ticker).history(period=f"{days}d")` 호출
    - 빈 DF → `ValueError`
    - `_yf_history_to_qbt_df` 변환 후 반환
  - `append_today_to_csv(csv_path, today_row)`:
    - `today_row` 는 1 행 DataFrame 이어야 함 (검증)
    - 파일 없음 → 부모 디렉토리 생성 + 헤더 + 저장
    - 파일 있으면 load → 해당 날짜 중복 체크 → concat → 정렬 → 저장
  - `rebuild_full_csv(ticker, csv_path, period="max")`:
    - `yf.Ticker(ticker).history(period=period)` 호출
    - 빈 DF → `ValueError`
    - `_yf_history_to_qbt_df` 변환 후 CSV 덮어쓰기
  - `load_csv(csv_path)`:
    - `return load_stock_data(csv_path)` (QBT 재사용)
- [x] Phase 0 테스트 전체 통과 확인 (22개 테스트 통과)

### Phase 2 — 문서 동기화

**작업 내용**:

- [x] `docs/TODO_QBT_LIVE.md` Step 5 체크박스 체크
- [x] `live/CLAUDE.md` 의 data_fetcher 책임 — 기존 요약이 충분히 일치하여 추가 수정 없음

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행 및 결과 기록
- [x] DoD 체크리스트 최종 업데이트
- [x] plan 상태 Done 으로 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=628, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `live / yfinance 수집 + CSV 누적 append (Step 5)`
2. `live / data_fetcher.py 신설 — fetch/append/rebuild/load`
3. `live / 매일 1행 CSV 누적 모드 + 중복 날짜 방지`
4. `live / QBT load_stock_data 재사용 + live 전용 fetch 어댑터`
5. `live / Step 5 data_fetcher + mock yfinance 테스트`

## 7) 리스크(Risks)

- **yfinance 응답 포맷 변경**: `Ticker.history()` 반환 컬럼/인덱스 구조가 바뀌면 `_yf_history_to_qbt_df` 변환이 깨질 수 있음.
  - 완화책: mock 테스트는 QBT `download_stock_data` 가 검증한 실제 구조와 동일 형태를 재현. 실제 변경 시 mock 테스트 실패로 즉시 감지.
- **append 시 동시 쓰기 레이스**: GitHub Actions 는 단일 job 이므로 레이스 없음. 가정 유지.
- **부동소수점 반올림 정책**: 6 자리 반올림은 CLAUDE.md 의 공통 규칙. 검증은 테스트에서 assert.
- **QBT `load_stock_data` 의존성**: live 의 `load_csv` 가 실패하면 QBT 쪽 변경을 먼저 의심해야 함. 재사용 경고 주석 포함.

## 8) 메모(Notes)

### 주요 결정 사항

- D1: `load_stock_data` 재사용, `download_stock_data` 는 재사용 안 함
- D2: 부록 A 시그니처 유지, `append_today_to_csv(csv_path, today_row)` — 1 행 DataFrame 입력
- D3: Path 객체, 부모 디렉토리 자동 생성, 가격 6 자리 반올림
- D4: 검증 3종은 Step 6 소관
- D5: 테스트는 `yfinance.Ticker` monkeypatch

### 진행 로그 (KST)

- 2026-04-11 13:20: 계획서 초안 작성, 설계 결정 D1~D5 확정
- 2026-04-11 13:25: Phase 0 test_data_fetcher.py 22개 테스트 선작성 (fetch/append/load/rebuild + mock yfinance)
- 2026-04-11 13:28: Phase 1 data_fetcher.py 구현 — 4개 함수 + `_yf_history_to_qbt_df` 헬퍼
- 2026-04-11 13:30: 22개 테스트 통과, TODO Step 5 체크박스 체크
- 2026-04-11 13:32: Ruff I001 수정 후 black + validate_project 통과 (passed=628, failed=0, skipped=0)

---
