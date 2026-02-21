# Implementation Plan: CLI 계층 비즈니스 로직 분리 (C-1, C-3)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-21 14:00
**마지막 업데이트**: 2026-02-21 15:00
**관련 범위**: utils, tqqq, scripts/data, scripts/tqqq
**관련 문서**: `PROJECT_ANALYSIS_REPORT.md` (C-1, C-3)

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

- [x] C-1: `scripts/data/download_data.py`의 비즈니스 로직(`validate_stock_data`, `download_stock_data`)을 `src/qbt/utils/stock_downloader.py`로 이동
- [x] C-3: `scripts/tqqq/generate_synthetic.py`의 비즈니스 로직(`_build_extended_expense_dict`)을 `src/qbt/tqqq/data_loader.py`로 이동
- [x] 이동한 함수에 대한 테스트 추가

## 2) 비목표(Non-Goals)

- `download_stock_data()` 내부의 yfinance 호출 로직 변경 또는 리팩토링
- `generate_synthetic.py`의 `main()` 함수 내부 비즈니스 로직 추출 (main 내부는 데이터 로드 → 시뮬레이션 호출 → 결과 저장 흐름으로, CLI 역할에 해당)
- D-3 (워크포워드 스크립트 통합), D-5 (app_rate_spread_lab.py 분할) 등 다른 향후 과제

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

프로젝트의 계층 분리 원칙에 따르면 CLI 계층(`scripts/`)은 사용자 인터페이스만 제공하고, 비즈니스 로직은 `src/qbt/`에 위치해야 한다. 현재 두 스크립트가 이 원칙을 위반하고 있다:

- **C-1**: `scripts/data/download_data.py:35-172` — `validate_stock_data()`(데이터 검증 로직)과 `download_stock_data()`(다운로드 + 전처리 + 검증 + 저장)가 CLI 계층에 구현됨
- **C-3**: `scripts/tqqq/generate_synthetic.py:53-92` — `_build_extended_expense_dict()`(운용비율 딕셔너리 확장 로직)가 CLI 계층에 구현됨

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 계층 분리 원칙, 상수 관리, 코딩 표준
- `scripts/CLAUDE.md`: CLI 계층 책임, 비즈니스 로직 분리 규칙
- `src/qbt/utils/CLAUDE.md`: 유틸리티 패키지 설계 원칙
- `src/qbt/tqqq/CLAUDE.md`: TQQQ 도메인 모듈 구성
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `validate_stock_data`, `download_stock_data`가 `src/qbt/utils/stock_downloader.py`로 이동됨
- [x] `_build_extended_expense_dict`가 `src/qbt/tqqq/data_loader.py`로 이동되어 `build_extended_expense_dict`로 공개됨
- [x] CLI 스크립트가 이동된 함수를 import하여 기존과 동일하게 동작함
- [x] 이동한 함수에 대한 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=317, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md, PROJECT_ANALYSIS_REPORT.md)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

신규 생성:
- `src/qbt/utils/stock_downloader.py` — `validate_stock_data`, `download_stock_data` 이동 대상

수정:
- `scripts/data/download_data.py` — 비즈니스 로직 제거, import 변경
- `scripts/tqqq/generate_synthetic.py` — `_build_extended_expense_dict` 제거, import 변경
- `src/qbt/tqqq/data_loader.py` — `build_extended_expense_dict` 추가
- `tests/test_stock_downloader.py` — 신규 테스트 파일
- `tests/test_tqqq_data_loader.py` — `build_extended_expense_dict` 테스트 추가
- `src/qbt/utils/CLAUDE.md` — `stock_downloader.py` 모듈 설명 추가
- `src/qbt/tqqq/CLAUDE.md` — `build_extended_expense_dict` 함수 설명 추가
- `PROJECT_ANALYSIS_REPORT.md` — C-1, C-3 상태를 "해결됨"으로 업데이트

### 데이터/결과 영향

- 출력 스키마 변경 없음 — 순수 코드 이동(동작 동일성 보장)
- 기존 결과 비교 불필요

## 6) 단계별 계획(Phases)

### Phase 1 — C-1: stock_downloader.py 생성 및 download_data.py 정리

**작업 내용**:

- [x] `src/qbt/utils/stock_downloader.py` 생성
  - `DEFAULT_PRICE_CHANGE_THRESHOLD` 상수 이동
  - `validate_stock_data(df: pd.DataFrame) -> None` 이동 (변경 없이 그대로)
  - `download_stock_data(ticker, start_date, end_date) -> Path` 이동 (변경 없이 그대로)
  - 모듈 docstring 작성
  - 필요한 import 정리 (pandas, yfinance, datetime, pathlib, common_constants)
- [x] `scripts/data/download_data.py` 수정
  - `validate_stock_data`, `download_stock_data`, `DEFAULT_PRICE_CHANGE_THRESHOLD` 제거
  - `from qbt.utils.stock_downloader import download_stock_data` 추가
  - 불필요해진 import 정리 (`pandas`, `yfinance`, `timedelta` 등 — `parse_args`와 `main`에서 불필요한 것만)
  - `main()` 함수는 그대로 유지 (CLI 역할: argparse + download_stock_data 호출)
- [x] `tests/test_stock_downloader.py` 생성
  - `TestValidateStockData` 클래스:
    - 정상 데이터 통과 테스트
    - 결측치(NaN) 검출 테스트
    - 0값 검출 테스트
    - 음수값 검출 테스트
    - 급등락 검출 테스트 (DEFAULT_PRICE_CHANGE_THRESHOLD 초과)
  - `TestDownloadStockData` 클래스:
    - yfinance 모킹 후 정상 다운로드 테스트 (tmp_path + monkeypatch)
    - 빈 데이터 반환 시 ValueError 테스트
    - 최근 2일 필터링 검증

---

### Phase 2 — C-3: build_extended_expense_dict 이동

**작업 내용**:

- [x] `src/qbt/tqqq/data_loader.py` 수정
  - `build_extended_expense_dict(expense_df: pd.DataFrame) -> dict[str, float]` 추가
    - `_build_extended_expense_dict`에서 선행 언더스코어 제거 (public 함수로 전환)
    - 함수 본문은 변경 없이 그대로 이동
  - 필요한 import 추가 (`DEFAULT_PRE_LISTING_EXPENSE_RATIO` from constants)
- [x] `scripts/tqqq/generate_synthetic.py` 수정
  - `_build_extended_expense_dict` 함수 제거
  - `from qbt.tqqq.data_loader import build_extended_expense_dict` 추가 (기존 import 블록에 병합)
  - `main()` 내부 호출을 `build_extended_expense_dict(expense_df)`로 변경
  - 불필요해진 import 정리 (`DEFAULT_PRE_LISTING_EXPENSE_RATIO` — generate_synthetic에서 더 이상 직접 사용하지 않으므로)
- [x] `tests/test_tqqq_data_loader.py` 수정
  - `TestBuildExtendedExpenseDict` 클래스 추가:
    - 정상 확장 테스트 (2010-02 시작 → 1999-01부터 채워지는지)
    - 기존 expense_dict 값이 보존되는지 테스트
    - 확장 범위의 값이 `DEFAULT_PRE_LISTING_EXPENSE_RATIO`인지 테스트
    - 경계 조건: expense_df가 1999-01부터 시작하면 확장 없이 그대로 반환

---

### Phase 3 (Final) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/utils/CLAUDE.md` 업데이트
  - `stock_downloader.py` 모듈 설명 추가 (목적, 주요 함수)
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - `data_loader.py` 함수 목록에 `build_extended_expense_dict` 추가
- [x] `PROJECT_ANALYSIS_REPORT.md` 업데이트
  - C-1: `[향후 과제]` → `[해결됨 - Plan CLI_BUSINESS_LOGIC_EXTRACTION]`
  - C-3: `[향후 과제]` → `[해결됨 - Plan CLI_BUSINESS_LOGIC_EXTRACTION]`
  - 요약 테이블의 C 카테고리 해결 상태: `2/3 해결` → `3/3 해결`
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=317, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 리팩토링 / CLI 계층 비즈니스 로직 분리 (C-1, C-3) + 테스트 추가
2. 유틸 / stock_downloader.py 신설 + tqqq/data_loader 확장 (CLI 로직 추출)
3. 리팩토링 / download_data, generate_synthetic 비즈니스 로직 src 계층으로 이동
4. 정리 / CLI-비즈니스 계층 분리 (validate_stock_data, build_extended_expense_dict)
5. 구조개선 / scripts → src/qbt 비즈니스 로직 이동 + 단위 테스트 보강

## 7) 리스크(Risks)

- **낮음**: 순수 코드 이동이므로 동작 변경 위험 없음
- **낮음**: `download_stock_data`는 yfinance 의존성이 있어 테스트 시 모킹 필요 — monkeypatch로 해결
- **낮음**: `generate_synthetic.py`에서 `DEFAULT_PRE_LISTING_EXPENSE_RATIO` import 제거 시 다른 곳에서 사용 중인지 확인 필요 — grep 확인 완료, `_build_extended_expense_dict` 내부에서만 사용

## 8) 메모(Notes)

### 설계 결정

1. **`stock_downloader.py` 위치**: `src/qbt/utils/`에 배치. 주식 데이터 다운로드는 도메인(backtest, tqqq)에 독립적인 범용 기능이므로 유틸리티 패키지에 적합.
2. **`build_extended_expense_dict` 위치**: `src/qbt/tqqq/data_loader.py`에 배치. TQQQ 도메인 전용 함수이며, 이미 같은 모듈에 `create_expense_dict`가 존재하여 자연스러운 확장.
3. **함수명 변경**: `_build_extended_expense_dict` → `build_extended_expense_dict` (선행 언더스코어 제거). CLI 내부 함수에서 공개 API로 전환.
4. **`download_stock_data` 내부의 logger 사용**: 비즈니스 로직에서 DEBUG 로그만 사용하므로 규칙 위반 없음 (ERROR 로그는 CLI에서만 사용하는 규칙).

### 진행 로그 (KST)

- 2026-02-21 14:00: Plan 작성 완료
- 2026-02-21 15:00: 전체 구현 완료, validate_project.py 통과 (passed=317, failed=0, skipped=0)

---
