# Implementation Plan: 버퍼존 전략 리팩토링 (helpers 추출 + TQQQ/QQQ 분리)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-20 18:00
**마지막 업데이트**: 2026-02-20 18:00
**관련 범위**: backtest, strategies, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [ ] 기존 `buffer_zone.py`의 공통 로직을 `buffer_zone_helpers.py`로 추출
- [ ] 기존 `buffer_zone.py`를 `buffer_zone_tqqq.py`로 이름 변경 (QQQ 시그널 + TQQQ 매매)
- [ ] 새로운 `buffer_zone_qqq.py` 전략 생성 (QQQ 시그널 + QQQ 매매)
- [ ] 그리드 서치 스크립트(`run_grid_search.py`)를 두 전략 모두 지원하도록 범용화
- [ ] 모든 임포트 경로, 테스트, 문서를 최신 구조에 맞게 업데이트

## 2) 비목표(Non-Goals)

- 버퍼존 전략 로직 자체의 변경 (시그널 감지, 체결 규칙, 동적 조정 등)
- 대시보드 앱(`app_single_backtest.py`) 수정 (Feature Detection 기반이므로 자동 호환)
- 기존 `storage/results/backtest/buffer_zone/` 디렉토리의 데이터 마이그레이션
- Buy & Hold 전략 변경 (이미 팩토리 패턴으로 리팩토링 완료)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `buffer_zone.py`는 시그널=QQQ, 매매=TQQQ(합성)로 고정되어 있음
- 시그널과 매매 모두 QQQ인 버퍼존 전략이 필요
- `buffer_zone.py`의 핵심 로직(`run_buffer_strategy`, 9개 헬퍼, 타입, 예외)은 데이터 소스에 비종속적
- 전략별 차이는 데이터 경로, `STRATEGY_NAME`, `run_single()`, `resolve_params()`뿐
- CLAUDE.md에 이미 설계 결정 기록: "향후 버퍼존 계열 전략 추가 시 공통 헬퍼를 추출하여 helpers.py 생성 예정"
- 사용자 요청: helpers 파일명에 buffer_zone 관련임을 명시, 기존 buffer_zone을 buffer_zone_tqqq로 변경

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] `buffer_zone_helpers.py` 생성 (공통 로직 추출)
- [ ] `buffer_zone_tqqq.py` 생성 (기존 buffer_zone 이름 변경 + helpers 임포트)
- [ ] `buffer_zone_qqq.py` 생성 (QQQ 전용 전략)
- [ ] `buffer_zone.py` 삭제
- [ ] `common_constants.py` 경로 상수 업데이트
- [ ] `strategies/__init__.py`, `backtest/__init__.py` 임포트 경로 업데이트
- [ ] `run_single_backtest.py` 전략 레지스트리 업데이트
- [ ] `run_grid_search.py` 범용화 (`--strategy` 인자 추가)
- [ ] 기존 테스트 임포트 경로 업데이트 (`test_strategy.py`, `test_integration.py`)
- [ ] `buffer_zone_qqq` 전략의 `run_single` 테스트 추가
- [ ] `conftest.py` 경로 상수 패치 업데이트
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (`src/qbt/backtest/CLAUDE.md`)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성:**
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` - 공통 로직
- `src/qbt/backtest/strategies/buffer_zone_tqqq.py` - TQQQ 전략
- `src/qbt/backtest/strategies/buffer_zone_qqq.py` - QQQ 전략

**삭제:**
- `src/qbt/backtest/strategies/buffer_zone.py`

**수정:**
- `src/qbt/common_constants.py` - 경로 상수 변경
- `src/qbt/backtest/strategies/__init__.py` - 임포트 경로
- `src/qbt/backtest/__init__.py` - 임포트 경로
- `scripts/backtest/run_single_backtest.py` - 전략 레지스트리
- `scripts/backtest/run_grid_search.py` - 범용화
- `tests/test_strategy.py` - 임포트 경로 + QQQ 테스트 추가
- `tests/test_integration.py` - 임포트 경로
- `tests/conftest.py` - mock 경로 상수
- `src/qbt/backtest/CLAUDE.md` - 문서 업데이트

### 데이터/결과 영향

- 새 결과 디렉토리: `storage/results/backtest/buffer_zone_tqqq/`, `storage/results/backtest/buffer_zone_qqq/`
- 기존 `storage/results/backtest/buffer_zone/` 디렉토리는 수동 정리 필요 (이 plan 범위 밖)
- `STRATEGY_NAME` 변경: `"buffer_zone"` → `"buffer_zone_tqqq"` (기존 결과의 strategy 필드와 불일치 발생)

## 6) 단계별 계획(Phases)

### Phase 1 — 핵심 리팩토링: helpers 추출 + 전략 분리 (그린 유지)

**작업 내용:**

**1-1. `buffer_zone_helpers.py` 생성**

기존 `buffer_zone.py`에서 데이터 소스에 비종속적인 공통 로직을 추출한다.

포함 내용:
- [ ] TypedDicts: `BufferStrategyResultDict`, `EquityRecord`, `TradeRecord`, `HoldState`, `GridSearchResult`
- [ ] DataClasses: `BaseStrategyParams`, `BufferStrategyParams`, `PendingOrder`
- [ ] 예외: `PendingOrderConflictError`
- [ ] 동적 조정 상수: `DEFAULT_BUFFER_INCREMENT_PER_BUY`, `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY`, `DEFAULT_DAYS_PER_MONTH`
- [ ] 헬퍼 함수 9개: `_validate_buffer_strategy_inputs`, `_compute_bands`, `_check_pending_conflict`, `_record_equity`, `_execute_buy_order`, `_execute_sell_order`, `_detect_buy_signal`, `_detect_sell_signal`, `_calculate_recent_buy_count`
- [ ] 핵심 함수: `run_buffer_strategy`, `run_grid_search`, `_run_buffer_strategy_for_grid`

**1-2. `buffer_zone_tqqq.py` 생성**

기존 `buffer_zone.py`의 전략별 코드만 유지하고, helpers를 임포트한다.

포함 내용:
- [ ] `STRATEGY_NAME = "buffer_zone_tqqq"`
- [ ] `DISPLAY_NAME = "버퍼존 전략 (TQQQ)"`
- [ ] `SIGNAL_DATA_PATH = QQQ_DATA_PATH`
- [ ] `TRADE_DATA_PATH = TQQQ_SYNTHETIC_DATA_PATH`
- [ ] `GRID_RESULTS_PATH` (전략 모듈 내 정의)
- [ ] OVERRIDE 상수 4개 + `MA_TYPE`
- [ ] `resolve_params()` 함수
- [ ] `run_single()` 함수

**1-3. `buffer_zone_qqq.py` 생성**

QQQ 전용 버퍼존 전략을 생성한다.

포함 내용:
- [ ] `STRATEGY_NAME = "buffer_zone_qqq"`
- [ ] `DISPLAY_NAME = "버퍼존 전략 (QQQ)"`
- [ ] `SIGNAL_DATA_PATH = QQQ_DATA_PATH`
- [ ] `TRADE_DATA_PATH = QQQ_DATA_PATH`
- [ ] `GRID_RESULTS_PATH` (전략 모듈 내 정의)
- [ ] OVERRIDE 상수 4개 + `MA_TYPE`
- [ ] `resolve_params()` 함수
- [ ] `run_single()` 함수 (signal과 trade가 동일하므로 `extract_overlap_period` 불필요)

**1-4. `common_constants.py` 업데이트**
- [ ] `BUFFER_ZONE_RESULTS_DIR` → `BUFFER_ZONE_TQQQ_RESULTS_DIR` 이름 변경
- [ ] `BUFFER_ZONE_QQQ_RESULTS_DIR` 추가
- [ ] `GRID_RESULTS_PATH` 제거 (각 전략 모듈로 이동)

**1-5. `buffer_zone.py` 삭제**
- [ ] 원본 파일 삭제

**1-6. 임포트 경로 업데이트**
- [ ] `strategies/__init__.py`: `buffer_zone` → `buffer_zone_helpers` + `buffer_zone_tqqq` + `buffer_zone_qqq`
- [ ] `backtest/__init__.py`: `buffer_zone` → `buffer_zone_helpers`

---

### Phase 2 — 스크립트 + 테스트 업데이트 (그린 유지)

**작업 내용:**

**2-1. `run_single_backtest.py` 업데이트**
- [ ] `buffer_zone` 임포트 → `buffer_zone_tqqq` + `buffer_zone_qqq`
- [ ] `STRATEGY_RUNNERS`에 `buffer_zone_tqqq`, `buffer_zone_qqq` 등록

**2-2. `run_grid_search.py` 범용화**
- [ ] `--strategy` 인자 추가 (choices: `buffer_zone_tqqq`, `buffer_zone_qqq`, 기본값: `buffer_zone_tqqq`)
- [ ] 전략별 데이터 경로, 결과 경로를 동적으로 결정
- [ ] `buffer_zone_tqqq`: signal=QQQ + trade=TQQQ합성 + `extract_overlap_period`
- [ ] `buffer_zone_qqq`: signal=trade=QQQ (overlap 불필요)
- [ ] `GRID_RESULTS_PATH`를 전략 모듈에서 임포트

**2-3. `tests/test_strategy.py` 업데이트**
- [ ] 모든 `from qbt.backtest.strategies.buffer_zone import ...` → `buffer_zone_helpers` 또는 `buffer_zone_tqqq`로 변경
  - `run_buffer_strategy`, `BufferStrategyParams`, `PendingOrderConflictError`, `_calculate_recent_buy_count`, `_check_pending_conflict`, `PendingOrder`, `run_grid_search` → `buffer_zone_helpers`
  - `resolve_params`, `run_single`, OVERRIDE 상수, `GRID_RESULTS_PATH`, `BUFFER_ZONE_RESULTS_DIR` → `buffer_zone_tqqq`
- [ ] `TestResolveParams.test_buffer_zone_resolve_params_*`: `buffer_zone` → `buffer_zone_tqqq` monkeypatch 대상 업데이트
- [ ] `TestRunSingle.test_buffer_zone_run_single_returns_result`: monkeypatch 대상 업데이트
  - `strategy_name` 검증: `"buffer_zone"` → `"buffer_zone_tqqq"`
  - `display_name` 검증: `"버퍼존 전략"` → `"버퍼존 전략 (TQQQ)"`
- [ ] `buffer_zone_qqq`용 `test_buffer_zone_qqq_run_single_returns_result` 추가

**2-4. `tests/test_integration.py` 업데이트**
- [ ] `from qbt.backtest.strategies.buffer_zone import ...` → `buffer_zone_helpers`

**2-5. `tests/conftest.py` 업데이트**
- [ ] `BUFFER_ZONE_RESULTS_DIR` → `BUFFER_ZONE_TQQQ_RESULTS_DIR`
- [ ] `BUFFER_ZONE_QQQ_RESULTS_DIR` 추가 (디렉토리 생성 + monkeypatch)
- [ ] `GRID_RESULTS_PATH` 패치 제거 (common_constants에서 삭제됨)
  - 각 전략 모듈의 `GRID_RESULTS_PATH`를 별도 패치 필요 여부 확인

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용:**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트
  - `buffer_zone.py` → `buffer_zone_helpers.py` + `buffer_zone_tqqq.py` + `buffer_zone_qqq.py`
  - 전략 식별 상수, 데이터 소스 경로, 모듈 설명 갱신
  - `helpers.py 미생성` 설계 결정 제거 (이제 생성됨)
- [ ] 루트 `CLAUDE.md` 디렉토리 구조 업데이트 (전략 모듈명 변경 반영)
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 버퍼존 전략 helpers 추출 + TQQQ/QQQ 분리 + 그리드 서치 범용화
2. 백테스트 / buffer_zone 리팩토링: 공통 로직 분리 및 QQQ 전략 추가
3. 백테스트 / 버퍼존 계열 전략 모듈 분리 (helpers + tqqq + qqq)
4. 백테스트 / buffer_zone → buffer_zone_tqqq 이름 변경 + buffer_zone_qqq 신규 전략
5. 백테스트 / 버퍼존 전략 구조 개편: helpers 추출, 듀얼 전략 지원, 그리드 서치 범용화

## 7) 리스크(Risks)

- **기존 결과 비호환**: `STRATEGY_NAME`이 `"buffer_zone"` → `"buffer_zone_tqqq"`로 변경되어 기존 `summary.json`의 strategy 필드와 불일치. 대시보드 앱은 Feature Detection 기반이므로 영향 없음. 기존 결과 디렉토리(`buffer_zone/`)는 수동 정리 필요.
- **임포트 경로 누락**: 많은 파일에서 `buffer_zone` 모듈을 참조하므로, 누락 시 런타임 에러 발생. → `validate_project.py`의 PyRight 타입 체크로 사전 감지.
- **conftest GRID_RESULTS_PATH 패치**: `GRID_RESULTS_PATH`가 common_constants에서 제거되므로, 기존 conftest의 패치 로직 업데이트 필요. 전략별 모듈의 `GRID_RESULTS_PATH`를 별도로 패치해야 할 수 있음.

## 8) 메모(Notes)

- `buy_and_hold.py`는 이미 팩토리 패턴(`BuyAndHoldConfig` + `CONFIGS` + `create_runner()`)으로 리팩토링 완료된 상태
- 버퍼존 전략은 팩토리 패턴 대신 개별 모듈 방식 채택 (이유: 각 전략별 OVERRIDE 상수, `resolve_params` 폴백 체인, 그리드 서치 등 전략별 커스터마이징이 많아 팩토리보다 명시적 모듈이 적합)
- `app_single_backtest.py`는 Feature Detection 기반으로 전략명 분기 없이 동작하므로, 새 전략 결과 폴더만 생성되면 자동으로 탭이 추가됨

### 진행 로그 (KST)

- 2026-02-20 18:00: 계획서 초안 작성

---
