# Implementation Plan: 타입 안전성 + 불변조건 강제

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

**작성일**: 2026-04-02 17:00
**마지막 업데이트**: 2026-04-02 17:30
**관련 범위**: backtest, tqqq, utils, 루트 CLAUDE.md
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `# type: ignore` 4곳 전부 제거 (근본 해결)
- [x] 내부 import 3곳 전부 제거 (최상위로 이동 또는 순환 의존성 해소)
- [x] 불가능 분기처리 7곳을 RuntimeError로 변경 (조용한 처리 → 즉시 중단)
- [x] "불가능 조건 처리" 원칙을 루트 CLAUDE.md에 문서화

## 2) 비목표(Non-Goals)

- `app_*` 파일 및 `tests/` 내부의 `# type: ignore` 수정
- 이미 ValueError를 발생시키는 파라미터 검증 코드 변경 (initial_capital, leverage, spread 등)
- 유효한 방어 코드 변경 (shares=0 매수 불가, WFE 분모=0, profit concentration 등)
- 새로운 테스트 추가 (불가능 조건은 정상 실행에서 도달 불가)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**# type: ignore (4곳)**:
1. `analysis.py:93`, `csv_export.py:62` — `pd.Series` 반환 시 제네릭 인자 누락
2. `portfolio_data.py:72` — `set.add()` 반환값을 boolean context에서 사용하는 트릭
3. `portfolio_execution.py:120` — `e_date: date | None`을 `TradeRecord.entry_date: date`에 할당

**내부 import (3곳)**:
1. `portfolio_planning.py:18-19` — `TYPE_CHECKING` 가드 (`AssetState` 순환 의존성)
2. `portfolio_execution.py:169` — `EPSILON` 함수 내부 import (순환 의존성 아님)
3. `analysis.py:285` — `date` 함수 내부 import (순환 의존성 아님)

**불가능 분기처리 (7곳)**: 로직상 절대 발생할 수 없는 조건을 조용히 처리 (기본값 반환, continue 등)하여 문제 발생 시 사용자가 인지할 수 없음.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` (특히 "구현 원칙", "코딩 표준" 섹션)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `# type: ignore` 0곳 (app_*/tests 제외)
- [x] 내부 import 0곳 (TYPE_CHECKING 포함)
- [x] 불가능 분기처리 7곳 → RuntimeError 변경 완료
- [x] 루트 CLAUDE.md에 "불가능 조건 처리" 원칙 추가
- [x] `poetry run python validate_project.py` 통과 (passed=465, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**# type: ignore 제거:**
- `src/qbt/backtest/analysis.py` — `pd.Series` → `pd.Series[float]`
- `src/qbt/backtest/csv_export.py` — `pd.Series` → `pd.Series[float]`
- `src/qbt/backtest/engines/portfolio_data.py` — 리스트 컴프리헨션 → 명시적 루프
- `src/qbt/backtest/engines/portfolio_execution.py` — `e_date` None 가드 추가

**내부 import 제거:**
- `src/qbt/backtest/portfolio_types.py` — `AssetState` 추가 (portfolio_execution.py에서 이동)
- `src/qbt/backtest/engines/portfolio_planning.py` — TYPE_CHECKING 제거, portfolio_types.py에서 import
- `src/qbt/backtest/engines/portfolio_execution.py` — `AssetState` 정의 제거, portfolio_types.py에서 import + `EPSILON` 최상단 이동
- `src/qbt/backtest/engines/portfolio_engine.py` — `AssetState` import 경로 변경
- `src/qbt/backtest/engines/__init__.py` — docstring 업데이트
- `src/qbt/backtest/analysis.py` — `from datetime import date` 최상단 추가

**불가능 분기처리 변경:**
- `src/qbt/backtest/analysis.py` — peak=0 EPSILON 대체 → RuntimeError (2곳) + final_capital<=0 → RuntimeError (1곳)
- `src/qbt/backtest/engines/portfolio_execution.py` — position<=0 continue → RuntimeError + delta_amount<=0 continue → RuntimeError
- `src/qbt/backtest/engines/portfolio_rebalance.py` — total_equity<EPSILON return → RuntimeError (2곳)

**문서:**
- `CLAUDE.md` (루트) — "불가능 조건 처리" 원칙 추가

**변경 없음:**
- `README.md` 변경 없음
- `tests/test_analysis.py` — 정책 변경에 따라 3개 테스트 업데이트 (조용한 처리 → RuntimeError 검증)

### 데이터/결과 영향

- 출력 스키마 변경 없음
- 기존 결과 비교 불필요
- 정상 실행 시 동작 변화 없음 (불가능 조건 도달 시에만 차이: 조용한 처리 → RuntimeError)

## 6) 단계별 계획(Phases)

### Phase 1 — `# type: ignore` 제거 + 내부 import 제거

**작업 내용**:

- [x] `analysis.py:93` — 반환 타입 `pd.Series` → `pd.Series[float]` + `from __future__ import annotations` 추가
- [x] `csv_export.py:62` — 반환 타입 `pd.Series` → `pd.Series[float]` + `from __future__ import annotations` 추가
- [x] `portfolio_data.py:72` — `set.add()` 트릭 → 명시적 루프로 교체
- [x] `portfolio_execution.py:120` — `e_date` None 가드 추가 (assert 사용)
- [x] `portfolio_types.py` — `AssetState` dataclass 추가 (portfolio_execution.py에서 이동)
- [x] `portfolio_execution.py` — `AssetState` 정의 제거 + `EPSILON` 최상단 이동
- [x] `portfolio_planning.py` — `TYPE_CHECKING` 블록 및 `__future__` import 제거, `portfolio_types.py`에서 `AssetState` import
- [x] `portfolio_engine.py` — `AssetState` import 경로를 `portfolio_types.py`로 변경
- [x] `engines/__init__.py` — docstring에서 AssetState 위치 설명 업데이트
- [x] `analysis.py:285` — `from datetime import date` 최상단 추가, 함수 내부 import 제거

---

### Phase 2 — 불가능 분기처리 → RuntimeError

**변경 대상 (7곳)**:

| # | 파일 | 라인 | 현재 처리 | 변경 |
|---|------|------|-----------|------|
| 1 | analysis.py | 105-107 | peak.replace(0, EPSILON) | RuntimeError |
| 2 | analysis.py | 186-188 | peak.replace(0, EPSILON) | RuntimeError |
| 3 | analysis.py | 176-178 | cagr = -100.0 | RuntimeError |
| 4 | portfolio_execution.py | 99-100 | continue | RuntimeError |
| 5 | portfolio_execution.py | 159-160 | continue | RuntimeError |
| 6 | portfolio_rebalance.py | 55-56 | return False | RuntimeError |
| 7 | portfolio_rebalance.py | 93-94 | return {} | RuntimeError |

**작업 내용**:

- [x] #1: `calculate_drawdown_pct_series` — peak에 0이 존재하면 RuntimeError, 아니면 peak 직접 사용 (EPSILON 대체 제거)
- [x] #2: `calculate_summary` MDD 계산 — 동일하게 peak 0 검증 후 직접 사용
- [x] #3: `calculate_summary` CAGR 계산 — `final_capital <= 0` 분기를 RuntimeError로 변경
- [x] #4: `execute_orders` SELL 단계 — `position <= 0` 시 RuntimeError
- [x] #5: `execute_orders` BUY 단계 — `delta_amount <= 0` 시 RuntimeError
- [x] #6: `should_rebalance` — `total_equity_projected < EPSILON` 시 RuntimeError
- [x] #7: `build_rebalance_intents` — `total_equity_projected < EPSILON` 시 RuntimeError

**RuntimeError 메시지 형식**: `"내부 불변조건 위반: {조건 설명} ({변수}={값})"`

**변경하지 않는 항목** (유효한 방어 코드):
- `engine_common.py:113` shares <= 0 — shares=0은 소액 매수 시 정상 발생
- `walkforward.py:374-383` WFE 분모 ~0 — IS 그리드 서치에서 calmar/cagr=0 이론적으로 가능
- `walkforward.py:535` profit concentration — 전체 손실 시 정상 발생
- `simulation.py` spread/leverage/initial_price — 이미 ValueError 발생 (변경 불필요)

---

### Phase 3 (마지막) — 문서화 + 최종 검증

**작업 내용**:

- [x] 루트 `CLAUDE.md` "구현 원칙" 섹션에 "불가능 조건 처리" 원칙 추가
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**추가할 원칙 내용 (루트 CLAUDE.md)**:

```
#### 불가능 조건 처리

내부 불변조건이 보장하는 "로직상 절대 발생할 수 없는 조건"에 대한 방어 코드 규칙:

- 조용히 기본값을 반환하거나 건너뛰지 않는다 (return, continue, 0 대체 금지)
- RuntimeError를 발생시켜 사용자가 즉시 인지할 수 있도록 한다
- 메시지에 "내부 불변조건 위반" 접두사를 포함한다

구분 기준:
- 입력 파라미터 검증 (외부에서 잘못된 값 전달 가능) → ValueError
- 내부 로직 불변조건 (코드 흐름상 절대 도달 불가) → RuntimeError
```

**Validation**:

- [x] `poetry run python validate_project.py` (passed=465, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 타입 안전성 강화 + 불변조건 RuntimeError 전환
2. 백테스트 / type: ignore 제거 + 내부 import 해소 + 불가능 분기 즉시 중단
3. 백테스트 / 타입 억제 전부 제거 + 불변조건 위반 시 즉시 예외 발생
4. 전체 / 타입 안전성 + 불가능 조건 RuntimeError 강제 + 원칙 문서화
5. 전체 / type: ignore 근본 해결 + 내부 import 제거 + 불변조건 원칙 수립

## 7) 리스크(Risks)

- `pd.Series[float]` 변경 시 pandas-stubs 버전에 따라 새로운 타입 오류 가능 → validate_project.py로 즉시 확인
- `AssetState` 이동 시 import 경로 누락 → grep으로 전수 확인
- 불가능 분기 RuntimeError 전환 시 숨어있던 버그가 표면화될 수 있음 → 이것이 목적이므로 리스크가 아닌 이득

## 8) 메모(Notes)

- 이미 ValueError를 발생시키는 파라미터 검증 코드 (6곳)는 현 상태 유지 (이미 중단됨)
- `engine_common.py:113` shares <= 0 가드는 유효한 비즈니스 로직 (소액 매수 불가)이므로 변경 불필요
- WFE 분모=0, profit concentration 음수는 이론적으로 발생 가능하여 현 상태 유지

### 진행 로그 (KST)

- 2026-04-02 17:00: 계획서 작성 (Draft)
- 2026-04-02 17:30: Phase 1~3 완료, 전체 검증 통과 (passed=465, failed=0, skipped=0)
