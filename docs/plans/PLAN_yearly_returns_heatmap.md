# Implementation Plan: 월별 수익률 히트맵에 연간 컬럼 추가 (single + portfolio)

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

**작성일**: 2026-04-14 15:34
**마지막 업데이트**: 2026-04-14 15:50
**관련 범위**: backtest, scripts
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md

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

- [x] 목표 1: `app_single_backtest.py`의 "월별/연도별 수익률 히트맵"에서 12월 오른쪽에 "연간" 컬럼을 추가한다.
- [x] 목표 2: 연간 수익률 연산은 비즈니스 로직(`src/qbt/backtest/analysis.py`)에 두고, CLI 스크립트(`run_single_backtest.py`, `run_portfolio_backtest.py`)에서 호출하여 `summary.json`에 저장한다. 대시보드 앱은 저장된 데이터를 읽기만 한다.
- [x] 목표 3: `app_portfolio_backtest.py`도 일관되게 변경한다. 현재 대시보드 앱이 직접 수행하는 월별/연간 수익률 연산을 비즈니스 로직으로 이동하고, `run_portfolio_backtest.py`에서 호출하여 `summary.json`에 저장한 뒤 앱은 이를 읽어 표시한다.

## 2) 비목표(Non-Goals)

- 히트맵의 색상/스케일/툴팁 등 기존 시각화 요소 변경
- `monthly_returns` 데이터 구조(year/month/return_pct) 변경
- run 스크립트의 명령행 인자 추가/변경
- 이 외의 대시보드 앱 리팩토링

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `app_single_backtest.py`의 월별 히트맵에는 연간 합계 열이 없어 한 해 전체 성과를 시각적으로 비교하기 어렵다.
- `app_portfolio_backtest.py`는 이미 연간 컬럼을 표시하지만, 월별/연간 연산을 **CLI 계층(대시보드 앱)** 에서 수행하고 있어 [scripts/CLAUDE.md](../../scripts/CLAUDE.md)의 "CLI 계층은 비즈니스 로직 호출만 담당, 도메인 로직 구현 금지" 원칙을 위반한다.
- `run_single_backtest.py`는 `calculate_monthly_returns()`를 호출하여 결과를 `summary.json`에 저장하지만, `run_portfolio_backtest.py`는 월별 수익률을 계산/저장하지 않는다. 두 스크립트의 처리 방식이 일관되지 않는다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md): 출력 데이터 반올림 규칙(백분율 2자리), 비율 표기 규칙, 타입 힌트 규칙
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md): 계층 분리 원칙, 상수 관리 규칙, 데이터 처리 규칙
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): `analysis.py` 모듈 책임, 대시보드 앱 아키텍처
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): CLI 계층 책임 분리, 메타데이터 관리, Streamlit 앱 규칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `analysis.py`에 `calculate_yearly_returns()` 함수 추가 (월별 수익률 → 연간 복리 수익률 계산)
- [x] `run_single_backtest.py`가 `yearly_returns`를 계산하여 `summary.json`에 저장
- [x] `run_portfolio_backtest.py`가 `monthly_returns` + `yearly_returns`를 계산하여 `summary.json`에 저장
- [x] `app_single_backtest.py` 월별 히트맵에 12월 오른쪽 "연간" 컬럼 표시 (저장된 데이터 사용, 자체 연산 없음)
- [x] `app_portfolio_backtest.py`가 더 이상 월별/연간 수익률을 직접 연산하지 않고 `summary.json`에서 읽어 표시
- [x] `calculate_yearly_returns()` 단위 테스트 추가 (정상/엣지케이스)
- [x] `poetry run python validate_project.py` 통과 (passed=917, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (`src/qbt/backtest/CLAUDE.md` + `src/qbt/CLAUDE.md` 모듈 책임/summary.json 설명 갱신, README는 변경 없음)
- [ ] 사용자 직접 실행 검증: `run_single_backtest.py` + `run_portfolio_backtest.py` 재실행 후 대시보드에서 연간 컬럼 확인
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py`: `calculate_yearly_returns()` 신규 함수 추가
- `src/qbt/backtest/__init__.py`: 신규 함수 export
- `scripts/backtest/run_single_backtest.py`: `yearly_returns` 계산 및 `summary.json` 저장
- `scripts/backtest/run_portfolio_backtest.py`: `calculate_monthly_returns()` + `calculate_yearly_returns()` 호출 및 `summary.json` 저장
- `scripts/backtest/app_single_backtest.py`: `_render_monthly_heatmap()` 시그니처에 `yearly_returns` 추가, 12월 오른쪽 "연간" 컬럼 렌더링
- `scripts/backtest/app_portfolio_backtest.py`: `_render_monthly_returns_section()`을 `summary_data`에서 `monthly_returns` + `yearly_returns`를 읽도록 변경, 자체 연산 코드 제거
- `tests/qbt/test_analysis.py`: `calculate_yearly_returns()` 단위 테스트 추가
- `src/qbt/backtest/CLAUDE.md`: `analysis.py` 주요 함수 목록에 `calculate_yearly_returns` 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- **출력 스키마 변경**:
  - `storage/results/backtest/{strategy_name}/summary.json`: 신규 필드 `yearly_returns: list[{year: int, return_pct: float}]` 추가 (기존 `monthly_returns` 유지)
  - `storage/results/portfolio/{experiment_name}/summary.json`: 신규 필드 `monthly_returns`, `yearly_returns` 추가
- **기존 결과 비교**: 기존 결과 파일은 사용자가 `run_*.py`를 재실행해야 신규 필드가 채워진다. 재실행 전에는 대시보드가 이전 포맷도 호환할 수 있도록 fallback 처리(빈 리스트 등) 필요
- 백분율 반올림 2자리 규칙 적용 (`return_pct` 값)

## 6) 단계별 계획(Phases)

### Phase 1 — 비즈니스 로직 추가 + 단위 테스트

**작업 내용**:

- [x] `src/qbt/backtest/analysis.py`에 `calculate_yearly_returns(monthly_returns: list[dict[str, object]]) -> list[dict[str, object]]` 추가
  - 입력: `calculate_monthly_returns()`의 반환값과 동일한 구조
  - 처리: 같은 year끼리 묶어 월별 복리 누적 `prod(1 + monthly_pct/100) - 1` 후 *100, 백분율 2자리 반올림
  - 출력: `[{"year": int, "return_pct": float}, ...]` (year 오름차순)
  - 빈 입력 시 빈 리스트 반환
- [x] `src/qbt/backtest/__init__.py`의 `__all__`에 `calculate_yearly_returns` 추가
- [x] `tests/qbt/test_analysis.py`에 `calculate_yearly_returns()` 단위 테스트 6건 추가
  - 정상: 12개월 모두 있는 경우 (월별 1% → 연간 약 12.68%)
  - 부분 데이터: 한 해 일부 월만 있는 경우
  - 다년도: 2개 이상 연도 처리 (정렬 검증)
  - 빈 입력
  - 음수 + 양수 수익률 혼합
  - `calculate_monthly_returns` → `calculate_yearly_returns` 일관성 검증

---

### Phase 2 — run 스크립트 및 summary.json 저장 통합

**작업 내용**:

- [x] `scripts/backtest/run_single_backtest.py`
  - `_save_summary_json()`에 `yearly_returns` 파라미터 추가
  - `summary_data["yearly_returns"]` 저장
  - 호출부에서 `calculate_yearly_returns(monthly_returns)` 계산 후 전달
- [x] `scripts/backtest/run_portfolio_backtest.py`
  - `_save_portfolio_results()`에서 `calculate_monthly_returns(result.equity_df)` + `calculate_yearly_returns(monthly_returns)` 호출
  - `summary_data["monthly_returns"]`, `summary_data["yearly_returns"]` 저장
  - import 추가 완료

---

### Phase 3 — 대시보드 앱 변경 (single + portfolio)

**작업 내용**:

- [x] `scripts/backtest/app_single_backtest.py` `_render_monthly_heatmap()`
  - 시그니처를 `(monthly_returns, yearly_returns, *, chart_key)`로 변경
  - z_values 13번째 열에 "연간" 컬럼 추가, x_labels에 "연간" 추가
  - text도 yearly_returns 값으로 채움, max_abs 계산 시 yearly 값 포함
  - 호출부 `_render_strategy_tab()`에서 `summary_data.get("yearly_returns", [])` 전달
- [x] `scripts/backtest/app_portfolio_backtest.py` `_render_monthly_returns_section()`
  - `equity_df`에서 직접 계산하던 로직 제거
  - `exp.summary.get("monthly_returns", [])` + `exp.summary.get("yearly_returns", [])` 사용
  - 데이터가 없으면 재실행 안내 메시지 표시 (이전 포맷 호환)
  - `import numpy as np` 제거 (유일한 사용처였음)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md`의 `analysis.py` 주요 함수 목록에 `calculate_yearly_returns` 추가
- [x] `src/qbt/CLAUDE.md`의 summary.json 설명을 "월별/연간 수익률" 로 갱신
- [x] `README.md` 변경 없음 확인
- [x] `poetry run black .` 실행 완료 (146 files unchanged)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [ ] 사용자에게 `run_single_backtest.py` + `run_portfolio_backtest.py` 재실행 요청 안내 (다음 메시지에서 안내)
- [ ] 사용자가 대시보드에서 12월 오른쪽 "연간" 컬럼 표시를 확인 (사용자 직접 검증)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=917, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 월별 히트맵에 연간 컬럼 추가 + yearly_returns 산출을 비즈니스 로직으로 이동
2. 백테스트 / calculate_yearly_returns 추가 및 single/portfolio summary.json에 연간 수익률 저장
3. 백테스트 / 대시보드 자체 연산 제거, 연간 수익률 계산을 run 스크립트로 통합
4. 백테스트 / 월별/연간 수익률 처리 일관화 (single + portfolio 동일 패턴)
5. 백테스트 / app_single_backtest 월별 히트맵 12월 오른쪽 연간 컬럼 추가 (analysis 계층 분리)

## 7) 리스크(Risks)

- **기존 결과 파일 호환성**: 사용자가 run 스크립트를 재실행하기 전까지 기존 `summary.json`에는 `yearly_returns` 필드가 없다. 대시보드는 fallback(빈 리스트)으로 처리하여 크래시를 방지한다.
- **portfolio 대시보드 회귀**: `app_portfolio_backtest.py`의 자체 연산 로직을 제거하면서 데이터 정합성이 깨질 수 있다. run 스크립트가 저장한 값과 기존 앱이 계산하던 값이 동일한지 단위 테스트로 검증한다.
- **반올림 차이**: 기존 portfolio 앱은 `monthly_return.values`를 그대로 사용하지만 이번에는 `calculate_monthly_returns()`가 2자리로 반올림한 값을 사용한다. 표시 자릿수가 동일하므로 시각적으로는 차이가 없지만, 누적 곱셈 시 소수점 차이가 발생할 수 있다. 결과 비교 시 허용 오차를 명시한다.

## 8) 메모(Notes)

- `calculate_yearly_returns()`의 입력은 `calculate_monthly_returns()`의 출력과 동일 구조. 서로 독립 함수로 분리하여 단일 책임 유지.
- `app_portfolio_backtest.py`의 `numpy` import는 다른 섹션(`np.prod` 등)에서 제거 후 사용처가 없으면 함께 제거.

### 진행 로그 (KST)

- 2026-04-14 15:34: plan 초안 작성
- 2026-04-14 15:42: Phase 1 완료 — `calculate_yearly_returns()` 추가, 단위 테스트 6건 통과
- 2026-04-14 15:46: Phase 2 완료 — single/portfolio run 스크립트 통합
- 2026-04-14 15:48: Phase 3 완료 — single/portfolio 대시보드 앱 변경 (numpy 의존 제거)
- 2026-04-14 15:50: 마지막 Phase 완료 — black 통과, validate_project.py 통과 (passed=917)

---
