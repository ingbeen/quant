# Implementation Plan: WFO 윈도우별 상세 캔들차트 시각화

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

**작성일**: 2026-04-01 21:00
**마지막 업데이트**: 2026-04-01 21:00
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

- [x] `run_walkforward.py` 실행 시 WFO 11개 윈도우별 signal/equity/trades CSV 사전 저장
- [x] `app_walkforward.py`에 Selectbox 기반 윈도우별 IS+OOS 결합 캔들차트 섹션 추가
- [x] 4개 지표(QQQ Dynamic, QQQ Fixed, TQQQ Dynamic, TQQQ Fixed) 모두 지원
- [x] 캔들차트에 MA선, 밴드, Buy/Sell 마커, 에쿼티, 드로우다운 표시

## 2) 비목표(Non-Goals)

- 기존 `app_walkforward.py` 5개 섹션(모드 요약 / Stitched Equity / IS vs OOS / 파라미터 추이 / WFE 분포)의 동작·레이아웃 변경
- 비즈니스 로직 (`walkforward.py`, `backtest_engine.py`, `analysis.py` 등) 변경
- IS와 OOS를 별도 차트로 분리 (하나의 차트에 IS+OOS 결합, 경계 마커로 구분)
- 대시보드 로딩 시 실시간 계산/연산 (모든 데이터는 `run_walkforward.py`에서 사전 저장)
- `app_single_backtest.py`와 차트 유틸 함수 공유 모듈 추출 (향후 리팩토링 대상)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 WFO 대시보드는 요약 지표(CAGR, MDD, Calmar, WFE)만 제공하며, 윈도우별 실제 매수/매도 시점을 시각적으로 확인할 수 없음
- 사용자가 전략의 동작 정합성을 판단하려면, 각 윈도우에서 가격 차트 위에 Buy/Sell 마커를 직접 확인해야 함
- 현재 저장되는 데이터: 윈도우별 요약 지표 CSV + Stitched Equity CSV (Date, equity, position만)
- 현재 저장되지 않는 데이터: 윈도우별 signal(OHLC+MA), equity(밴드+드로우다운), trades(매수/매도 내역)
- Dynamic 모드는 윈도우마다 파라미터(MA window 등)가 다르므로, 기존 전체기간 signal.csv를 그대로 슬라이싱할 수 없음

### 데이터 생성 방식

각 윈도우에 대해 해당 윈도우의 best params로 IS_start → OOS_end 전체 기간의 단일 백테스트를 실행한다.
이를 통해 IS 구간에서의 전략 동작과 OOS 구간에서의 전략 동작을 하나의 연속 차트로 확인할 수 있다.

기존 함수 재활용:
- `run_backtest()` — 백테스트 실행 (backtest_engine.py)
- `BufferZoneStrategy()` — 전략 객체 생성 (build_params_schedule 패턴 참고)
- `add_single_moving_average()` — MA 컬럼 추가 (analysis.py)
- `_enrich_equity_with_bands()` — 밴드 컬럼 추가 (runners.py)
- drawdown_pct 계산 — run_single_backtest.py:135 패턴 참고

### 차트 UI 설계

Selectbox 네비게이션:
1. 첫 번째 selectbox: 지표 선택 (QQQ Dynamic / QQQ Fixed / TQQQ Dynamic / TQQQ Fixed)
2. 두 번째 selectbox: 윈도우 선택 (W0 ~ W10, IS/OOS 날짜 범위 표시)

선택한 1개 윈도우의 차트를 렌더링:
- 캔들스틱 + MA 오버레이 + 상단/하단 밴드 + Buy/Sell 마커
- OOS 시작일에 경계 마커 (다이아몬드 형태)
- 에쿼티 곡선 pane
- 드로우다운 pane
- 윈도우 파라미터 + 성과 요약 정보 (차트 상단)

`app_single_backtest.py`의 lightweight-charts 렌더링 패턴을 참고한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인)
- `scripts/CLAUDE.md` (스크립트 계층)
- `tests/CLAUDE.md` (테스트)
- `src/qbt/utils/CLAUDE.md` (유틸리티)

## 4) 완료 조건(Definition of Done)

- [x] `run_walkforward.py` 실행 시 윈도우별 CSV (signal, equity, trades) 자동 저장
- [x] `app_walkforward.py`에 Selectbox 네비게이션 기반 윈도우별 상세 차트 섹션 추가
- [x] 4개 지표 × 11개 윈도우 모든 조합에서 차트가 정상 렌더링
- [x] IS→OOS 경계가 차트에서 시각적으로 구분 가능
- [x] 테스트: CLI/UI 계층 변경이므로 신규 테스트 불필요 (기존 테스트 회귀 확인)
- [x] `poetry run python validate_project.py` 통과 (passed=432, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (scripts/CLAUDE.md 업데이트 완료)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/constants.py` — 윈도우별 CSV 디렉토리명 상수 2개 추가
- `scripts/backtest/run_walkforward.py` — 윈도우별 CSV 저장 함수 + 호출 통합
- `scripts/backtest/app_walkforward.py` — 새 섹션 (데이터 로딩 + Selectbox UI + 차트 렌더링)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 새로운 디렉토리 및 CSV 파일 생성 (기존 결과에 영향 없음):

```
storage/results/backtest/{strategy}/
├── wfo_windows_dynamic/
│   ├── w00_signal.csv    # OHLC + MA + change_pct (IS_start ~ OOS_end)
│   ├── w00_equity.csv    # equity + position + bands + drawdown_pct
│   ├── w00_trades.csv    # 완료 거래 내역 + holding_days
│   ├── w01_signal.csv
│   ├── w01_equity.csv
│   ├── w01_trades.csv
│   └── ... (w10까지)
└── wfo_windows_fully_fixed/
    ├── w00_signal.csv
    ├── w00_equity.csv
    ├── w00_trades.csv
    └── ... (w10까지)
```

- 파일 수: 11 윈도우 × 3 파일 × 2 모드 × 2 전략 = 132 파일
- 기존 출력 파일(walkforward_dynamic.csv, walkforward_equity_*.csv 등) 스키마 변경 없음

### CSV 컬럼 및 반올림 규칙

**w{idx}_signal.csv** (run_single_backtest.py의 signal 저장 패턴 준용):

| 컬럼 | 반올림 | 설명 |
|------|--------|------|
| Date | - | 날짜 |
| Open, High, Low, Close | 6자리 | OHLC 가격 |
| ma_{window} | 6자리 | 해당 윈도우의 MA 값 |
| change_pct | 2자리 | 전일대비 변동률 |

**w{idx}_equity.csv** (run_single_backtest.py의 equity 저장 패턴 준용):

| 컬럼 | 반올림 | 설명 |
|------|--------|------|
| Date | - | 날짜 |
| equity | 정수 | 자본금 |
| position | - | 보유 수량 |
| upper_band | 6자리 | 매수 상단 밴드 |
| lower_band | 6자리 | 매도 하단 밴드 |
| buy_buffer_pct | 4자리 | 매수 버퍼존 비율 |
| sell_buffer_pct | 4자리 | 매도 버퍼존 비율 |
| drawdown_pct | 2자리 | 드로우다운 (%) |

**w{idx}_trades.csv** (run_single_backtest.py의 trades 저장 패턴 준용):

| 컬럼 | 반올림 | 설명 |
|------|--------|------|
| entry_date | - | 진입일 |
| exit_date | - | 청산일 |
| entry_price | 6자리 | 진입가 |
| exit_price | 6자리 | 청산가 |
| shares | - | 수량 |
| pnl | 정수 | 손익금액 |
| pnl_pct | 4자리 | 손익률 |
| buy_buffer_pct | 4자리 | 매수 버퍼존 |
| hold_days_used | - | 유지일 |
| holding_days | - | 보유기간(일) |

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 추가 + 윈도우별 CSV 저장 (run_walkforward.py)

**작업 내용**:

- [x] `src/qbt/backtest/constants.py`에 디렉토리명 상수 추가
  - `WFO_WINDOWS_DYNAMIC_DIR = "wfo_windows_dynamic"`
  - `WFO_WINDOWS_FULLY_FIXED_DIR = "wfo_windows_fully_fixed"`
- [x] `scripts/backtest/run_walkforward.py`에 윈도우별 CSV 저장 함수 추가
  - `_save_window_detail_csvs(window_results, signal_df, trade_df, result_dir, mode_dir_name)` 함수 구현
  - 각 윈도우에 대해:
    1. `WfoWindowResultDict`의 best params로 `BufferZoneStrategy` 생성 (build_params_schedule 패턴)
    2. `add_single_moving_average()`로 signal_df에 해당 MA 컬럼 추가
    3. signal_df를 IS_start ~ OOS_end로 슬라이싱
    4. `run_backtest(strategy, sliced_signal, sliced_trade, initial_capital)` 실행
    5. `_enrich_equity_with_bands()`로 equity_df에 밴드 추가
    6. drawdown_pct 계산 (run_single_backtest.py:131-135 패턴)
    7. 반올림 규칙 적용 후 signal.csv, equity.csv, trades.csv 저장
  - 파일명: `w{idx:02d}_signal.csv`, `w{idx:02d}_equity.csv`, `w{idx:02d}_trades.csv`
- [x] `_save_results()` 호출부에서 Dynamic/Fully Fixed 양 모드 모두 `_save_window_detail_csvs()` 호출
- [x] 필요한 import 추가: `BufferZoneStrategy`, `compute_bands`, `EPSILON`, 상수 2개

---

### Phase 2 — app_walkforward.py 상세 차트 섹션 추가

**작업 내용**:

- [x] `lightweight_charts_v5` import 추가
- [x] 로컬 상수 추가 (차트 높이, 색상, 지표 옵션 매핑)
- [x] 윈도우별 CSV 로딩 함수 추가 (`st.cache_data` 적용)
- [x] 차트 데이터 빌드 함수 구현 (app_single_backtest.py 패턴 참고)
- [x] IS→OOS 경계 마커 구현: OOS 시작일에 square 마커 추가 ("OOS Start")
- [x] Selectbox UI 구현 (지표 4개 + 윈도우 W0~W10)
- [x] 윈도우 파라미터 + 성과 요약 정보 표시 (차트 상단 metric 카드)
- [x] `_render_window_detail()` 렌더링 함수 구현 (3-pane lightweight-charts)
- [x] `main()` 함수에서 기존 5개 섹션 이후 새 섹션 호출 추가

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `scripts/CLAUDE.md`에 새 기능 반영 (app_walkforward.py 섹션 업데이트)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=432, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFO 윈도우별 IS+OOS 캔들차트 시각화 추가
2. 백테스트 / WFO 윈도우별 signal·equity·trades CSV 저장 + 상세 차트 섹션 추가
3. 백테스트 / WFO 대시보드에 윈도우별 Buy/Sell 마커 차트 신규 추가
4. 백테스트 / run_walkforward 윈도우별 CSV 사전 저장 + app 상세 차트
5. 백테스트 / WFO 윈도우 상세 시각화 — 4개 지표 × 11개 윈도우 캔들차트

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| `run_walkforward.py` 실행 시간 증가 | 44회 추가 backtest (11W × 2모드 × 2전략). 기존 그리드 서치(수백 회) 대비 미미하나 총 시간 약간 증가 | 각 윈도우의 backtest는 기존 인프라 재활용, 추가 최적화 불필요 |
| 저장 공간 증가 | 132개 CSV 추가. 각 파일 수 KB~수 MB, 총 ~50MB 이하 예상 | 무시 가능한 수준 |
| lightweight-charts + Plotly 공존 | app_walkforward.py에서 처음 lightweight-charts 사용 | app_single_backtest.py에서 검증된 vendor fork 사용, Streamlit 컴포넌트 공존 문제 없음 |
| 차트 빌드 함수 중복 | app_single_backtest.py와 유사 함수 중복 작성 | Non-Goals에 명시. 향후 공유 모듈 추출 리팩토링으로 해결 가능 |

## 8) 메모(Notes)

- `build_params_schedule()` (walkforward.py:404-444)에서 `BufferZoneStrategy` 생성 패턴을 그대로 재활용
- IS+OOS 결합 차트: 각 윈도우의 IS_start ~ OOS_end 전체 기간에 대해 해당 best params로 단일 backtest 실행
- drawdown_pct 계산: `(equity - peak) / safe_peak * 100` (run_single_backtest.py:131-135 패턴)
- `_enrich_equity_with_bands()` (runners.py)로 equity_df에 upper_band, lower_band, buy_buffer_pct, sell_buffer_pct 추가
- 윈도우별 데이터의 MA 컬럼은 `add_single_moving_average()`로 전체 signal_df에 사전 계산 후 슬라이싱 (EMA 연속성 보장, _run_stitched_equity 패턴)

### 진행 로그 (KST)

- 2026-04-01 21:00: Plan 초안 작성
- 2026-04-01 21:30: Phase 1~3 구현 완료, validate_project.py 통과 (432 passed, 0 failed, 0 skipped)
