# Implementation Plan: 백테스트 / grid_results.csv 최적 파라미터 자동 로딩

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

**작성일**: 2026-02-16 22:30
**마지막 업데이트**: 2026-02-16 23:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `run_single_backtest.py` 실행 시 `grid_results.csv`에서 CAGR 1위 파라미터를 자동 로딩
- [x] 사용자가 필요 시 수동으로 파라미터를 오버라이드할 수 있는 폴백 체인 제공
- [x] 폴백 체인: `OVERRIDE 상수` → `grid_results.csv 최적값` → `DEFAULT 상수`

## 2) 비목표(Non-Goals)

- grid_results.csv의 정렬 기준 변경 (현재 CAGR 내림차순 유지)
- 명령행 인자(argparse) 추가 (프로젝트 CLI 규칙: 명령행 인자 최소화)
- `initial_capital`은 폴백 대상에서 제외 (모든 그리드 조합이 동일한 값 사용)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_single_backtest.py`는 `backtest/constants.py`의 DEFAULT 상수를 직접 사용
- 그리드 서치(`run_grid_search.py`)로 최적 파라미터를 탐색해도, 단일 백테스트에 수동으로 값을 변경해야 함
- 사용자가 grid_results.csv의 1위 파라미터를 자동으로 적용하면서, 필요 시 특정 파라미터만 오버라이드하고 싶음

### `or` 연산자 대신 `if is not None else` 패턴 사용 근거

- `hold_days=0`과 `recent_months=0`은 유효한 값 (0 = 비활성화)
- Python `or`는 `0`을 falsy로 취급: `0 or DEFAULT_VALUE` → `DEFAULT_VALUE` 반환 (의도와 다름)
- 안전한 대안: `OVERRIDE_X if OVERRIDE_X is not None else grid_value`

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `load_best_grid_params()` 함수 구현 및 `BestGridParams` TypedDict 정의
- [x] DISPLAY 상수 `backtest/constants.py`로 이동, `run_grid_search.py` 임포트 변경
- [x] `run_single_backtest.py`에 폴백 체인 로직 구현 (OVERRIDE → grid → DEFAULT)
- [x] `load_best_grid_params()` 테스트 추가 (정상/파일없음/빈CSV/컬럼누락/타입정확성)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/types.py` | `BestGridParams` TypedDict 추가 |
| `src/qbt/backtest/constants.py` | DISPLAY 상수 10개 추가 |
| `src/qbt/backtest/analysis.py` | `load_best_grid_params()` 함수 추가 |
| `src/qbt/backtest/__init__.py` | 새 함수/타입 export 추가 |
| `scripts/backtest/run_grid_search.py` | 로컬 DISPLAY 상수 제거, constants 임포트로 변경 |
| `scripts/backtest/run_single_backtest.py` | OVERRIDE 상수 + 폴백 체인 로직 추가 |
| `tests/test_analysis.py` | `TestLoadBestGridParams` 테스트 클래스 추가 |
| `src/qbt/backtest/CLAUDE.md` | 새 함수/타입 문서화 |

### 데이터/결과 영향

- 출력 스키마 변경 없음 (기존 동작과 동일, 파라미터 소스만 변경)
- grid_results.csv를 읽기 전용으로 사용 (기존 파일에 영향 없음)

## 6) 단계별 계획(Phases)

### Phase 1 — 타입/상수/함수 구현 + 테스트

**작업 내용**:

- [x] `src/qbt/backtest/types.py`: `BestGridParams` TypedDict 추가
- [x] `src/qbt/backtest/constants.py`: 그리드 서치 결과 DISPLAY 상수 10개 추가
- [x] `scripts/backtest/run_grid_search.py`: 로컬 DISPLAY 상수 제거, `from qbt.backtest.constants import ...` 변경
- [x] `src/qbt/backtest/analysis.py`: `load_best_grid_params(path: Path) -> BestGridParams | None` 구현
- [x] `src/qbt/backtest/__init__.py`: `load_best_grid_params`, `BestGridParams` export 추가
- [x] `tests/test_analysis.py`: `TestLoadBestGridParams` 클래스 추가

---

### Phase 2 — run_single_backtest.py 폴백 체인 적용

**작업 내용**:

- [x] 로컬 OVERRIDE 상수 추가 (파일 상단)
- [x] `main()` 내부에 폴백 체인 구현
- [x] `BufferStrategyParams` 생성 및 `add_single_moving_average` 호출에 폴백 결과 사용
- [x] 불필요해진 DEFAULT 상수 임포트 정리

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
- [x] `poetry run black .` 실행
- [x] 변경 기능 최종 검증
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / grid_results.csv 최적 파라미터 자동 로딩 기능 추가
2. 백테스트 / 단일 백테스트에 그리드 서치 최적값 폴백 체인 적용
3. 백테스트 / CAGR 1위 파라미터 자동 선택 및 수동 오버라이드 지원
4. 백테스트 / load_best_grid_params 함수 추가 및 run_single_backtest 연동
5. 백테스트 / 그리드 서치 결과 기반 파라미터 자동 설정 구현

## 7) 리스크(Risks)

- **grid_results.csv 미존재**: 그리드 서치 미실행 시 → `None` 반환 후 DEFAULT 폴백으로 대응 (기존 동작 보장)
- **CSV 포맷 변경**: 한글 컬럼명에 의존 → 컬럼명을 상수로 관리하여 한 곳에서 수정 가능
- **DISPLAY 상수 이동 시 run_grid_search.py 회귀**: 임포트 경로만 변경, 값은 동일하므로 위험 낮음

## 8) 메모(Notes)

- `or` 연산자 대신 `if is not None else` 패턴 사용 (0 값 안전 처리)
- DISPLAY 상수 10개 전부 `constants.py`로 이동 (4개만 2+ 파일에서 사용하나, 논리적 그룹 응집도 우선)
- `initial_capital`은 폴백 대상 제외 (그리드 서치에서 파라미터가 아닌 고정 설정)

### 진행 로그 (KST)

- 2026-02-16 22:30: 계획서 초안 작성
- 2026-02-16 23:00: 모든 Phase 구현 완료, validate_project.py 통과 (passed=284, failed=0, skipped=0)
