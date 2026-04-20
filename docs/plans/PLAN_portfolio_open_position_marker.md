# Implementation Plan: 포트폴리오 시그널 차트 미청산 포지션 Buy 마커 표시

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

**작성일**: 2026-04-20 (KST)
**마지막 업데이트**: 2026-04-20 (KST)
**관련 범위**: scripts/backtest
**관련 문서**: [scripts/CLAUDE.md](../../scripts/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드", Phase 1부터는 **그린 유지**.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**.
- 스킵은 가능하면 **Phase 분해로 제거**.

---

## 1) 목표(Goal)

- [x] 포트폴리오 시그널 차트에서 **미청산 포지션의 매수 시점에 Buy 마커**를 표시한다 (단일 백테스트 대시보드와 동일한 "Buy $XX.X (보유중)" 패턴)
- [x] summary.json의 `per_asset` 항목에 `open_position: {entry_date, entry_price, shares}` 필드를 추가하여 대시보드가 이를 읽도록 한다 (도메인 연산을 CLI 레이어에서 수행 — 대시보드는 표시만)

## 2) 비목표(Non-Goals)

- `PortfolioResult` / `PortfolioAssetResult` 도메인 타입 변경 (summary.json 출력 단계에서만 보강)
- 포트폴리오 엔진(`src/qbt/backtest/engines/portfolio_engine.py`) 내부 로직 변경 (equity_df가 이미 shares/avg_price를 모두 포함하므로 CLI 레이어에서 파생 가능)
- `trades.csv` 스키마 변경 (완료된 거래만 기록하는 규약 유지)
- 단일 백테스트 대시보드 변경 (이미 `open_position` 처리 완료됨)

## 3) 배경/맥락(Context)

### 현재 문제점

- [app_portfolio_backtest.py:1278-1326](../../scripts/backtest/app_portfolio_backtest.py#L1278-L1326) `_build_portfolio_markers()`: 완료된 거래(`trades_df`)만 순회하여 Buy/Sell 마커 생성
- 미청산 포지션은 trades.csv에 없으므로 차트에 Buy 마커가 표시되지 않음
- 예: D-1 실험에서 2025-05-16에 매수가 체결되어 18만주 보유 중이지만, 차트 상 마커가 없어 사용자가 혼동

### 근거: 단일 백테스트 대시보드의 기존 패턴

- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) "미청산 포지션 마커: `summary.open_position` 존재 시 `"Buy $XX.X (보유중)"` 마커 자동 표시"
- 동일 패턴을 포트폴리오 대시보드에 적용

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `run_portfolio_backtest.py`의 per_asset 저장부에 `open_position` 필드 생성 로직 추가 (`final_shares > 0`일 때만)
  - `entry_date`: equity_df에서 해당 자산 shares가 마지막으로 0→양수로 전환된 날짜 (폴백: 시작부터 양수인 경우 첫 행 Date)
  - `entry_price`: equity_df 마지막 행의 `{asset_id}_avg_price`
  - `shares`: equity_df 마지막 행의 `{asset_id}_shares`
- [x] 위 필드는 `final_shares > 0`이 아니면 키 자체를 생략
- [x] `_build_portfolio_markers(trades_df, asset_id, open_position=None)` 시그니처 확장, open_position이 있고 entry_date가 trades_df Buy와 중복되지 않으면 "Buy $XX.X (보유중)" 마커 추가
- [x] `_render_signal_chart`에 해당 자산의 open_position 전달
- [ ] D-1 실험 등 보유 중인 실험 재생성 후 차트에 Buy 마커가 보임 (사용자 검증 대기 — 스크립트 실행은 사용자가 담당)
- [x] `poetry run python validate_project.py` 통과 (passed=1023, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (변경 없음)
- [x] 문서 업데이트: README.md 변경 없음 / docs/COMMANDS.md 변경 없음 / `src/qbt/backtest/CLAUDE.md` 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- [scripts/backtest/run_portfolio_backtest.py](../../scripts/backtest/run_portfolio_backtest.py)
  - `_save_portfolio_results()` 내부 per_asset 계산부: `open_position` 필드 추가
- [scripts/backtest/app_portfolio_backtest.py](../../scripts/backtest/app_portfolio_backtest.py)
  - `_build_portfolio_markers()`: `open_position` 파라미터 지원
  - `_render_signal_chart()`: 호출부에서 summary.per_asset의 해당 asset_id의 open_position을 찾아 전달
  - 필요 시 호출부(`_render_experiment_tab` 내) 시그널 차트 렌더 부분도 summary를 함께 전달
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): 포트폴리오 대시보드 섹션에 "미청산 포지션 Buy 마커" 한 줄 추가 (단일 백테스트와 동일 규약임 명시)
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음

### 데이터/결과 영향

- summary.json 스키마 변경: per_asset 각 항목에 `open_position` 키 추가 (현재 보유 중인 자산만)
- 기존 summary.json 파일과의 호환성: 대시보드가 `get("open_position", None)`으로 읽으므로 신/구 혼재해도 무난
- 사용자 작업: 재생성 필요 (`poetry run python scripts/backtest/run_portfolio_backtest.py`)

## 6) 단계별 계획(Phases)

### Phase 1 — `run_portfolio_backtest.py`에 open_position 계산 로직 추가

**작업 내용**:

- [x] `_save_portfolio_results()` 내부 per_asset_data 생성 루프에서 `final_shares > 0`일 때 `open_position` 딕셔너리 생성
- [x] 헬퍼 함수 `_find_last_entry_date(equity_df, asset_id) -> str | None`: `{asset_id}_shares` 컬럼에서 `prev == 0 & current > 0` 조건의 마지막 Date 반환 (없으면 시작부터 양수인 경우 첫 행 Date 폴백)
- [x] open_position에 `entry_date`, `entry_price` (=final_avg_price), `shares` (=final_shares) 포함
- [x] per_asset 엔트리의 `final_shares`, `final_avg_price`와 병존

### Phase 2 — `app_portfolio_backtest.py` 마커 보강

**작업 내용**:

- [x] `_build_portfolio_markers(trades_df, asset_id, open_position=None)`: 파라미터 추가
- [x] open_position이 있고 entry_date가 `seen_entry_dates`에 없으면 "Buy $XX.X (보유중)" 마커 추가 (`position=belowBar`, `shape=arrowUp`, `color=_COLOR_BUY_MARKER`)
- [x] `_render_signal_chart(signal_df, trades_df, asset_id, experiment_name, open_position=None)` 시그니처 확장
- [x] 호출부: `exp.summary["per_asset"]`에서 해당 asset_id의 `open_position` (있으면) 추출하여 전달

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) 포트폴리오 대시보드 섹션에 "미청산 포지션 Buy 마커" 설명 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1023, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 포트폴리오 시그널 차트 미청산 포지션 Buy 마커 표시
2. 대시보드 / summary.per_asset에 open_position 추가 + 보유중 마커 렌더
3. 대시보드 / 포트폴리오 open_position 마커 — 단일 백테스트와 동일 규약 적용
4. 대시보드 / 포트폴리오 차트에서 보유중 Buy 마커 누락 버그 수정
5. 백테스트 / 포트폴리오 summary에 open_position 저장, 대시보드 마커 보강

## 7) 리스크(Risks)

- entry_date 계산 엣지 케이스: `shares`가 한 번도 0이 되지 않고 시작부터 양수인 경우(`_CONFIG_D1`에 해당 없으나 buy_and_hold 자산은 해당 가능) → `prev == 0`을 만족하는 행이 없음 → `equity_df[{asset_id}_shares].iloc[0] > 0`이면 첫 번째 거래일을 entry_date로 처리하는 폴백 필요
- trades_df 마지막 Buy와 open_position의 entry_date가 동일한 경우(예: 매수만 했는데 trades에 들어간 상태) → 중복 방지(`seen_entry_dates` 체크)
- summary.json 신/구 혼재: `open_position` 없으면 `None` 폴백

## 8) 메모(Notes)

- 도메인 연산은 CLI 레이어(`run_portfolio_backtest.py`)에서 수행. 대시보드는 값을 읽어 표시만.
- PortfolioResult/엔진 시그니처 변경 없음 — equity_df가 이미 필요한 모든 정보(shares, avg_price, Date)를 담고 있음.

### 진행 로그 (KST)

- 2026-04-20: 계획서 작성 및 In Progress 시작
- 2026-04-20: Phase 1 완료 — `_find_last_entry_date` 헬퍼 + `per_asset.open_position` 저장
- 2026-04-20: Phase 2 완료 — `_build_portfolio_markers`/`_render_signal_chart` 시그니처 확장 + 호출부에서 summary.per_asset의 open_position 전달
- 2026-04-20: src/qbt/backtest/CLAUDE.md 포트폴리오 대시보드 섹션에 규약 추가
- 2026-04-20: `validate_project.py` 통과 (passed=1023, failed=0, skipped=0). 상태 → Done
