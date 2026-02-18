# Implementation Plan: 백테스트 대시보드 표시 전용 리팩토링

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

**작성일**: 2026-02-17 01:30
**마지막 업데이트**: 2026-02-17 02:00
**관련 범위**: backtest, scripts, common_constants
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`

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

- [x] `app_single_backtest.py`에서 모든 연산 로직을 제거하고, 미리 계산된 결과 파일만 로드하여 표시하는 구조로 전환
- [x] `run_single_backtest.py`에서 trades, equity, signal, summary 데이터를 CSV/JSON으로 저장하도록 수정
- [x] 사이드바 파라미터 조정 기능 제거 (단일 결과 표시)
- [x] `README.md` 업데이트 (대시보드 실행 방법 및 선행 스크립트 명시)

## 2) 비목표(Non-Goals)

- 새로운 비즈니스 로직 추가 (기존 `src/qbt/backtest/` 모듈만 호출)
- 테스트 코드 추가 (기존 앱과 동일하게 Streamlit 앱은 테스트 비대상)
- Buy & Hold 벤치마크 결과 저장/표시 (기존 대시보드에도 미포함)
- 차트 디자인/레이아웃 변경 (기존 시각화 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `app_single_backtest.py`가 직접 `run_buffer_strategy()`, `add_single_moving_average()` 등을 호출하여 연산을 수행함
- 사용자 요구: 앱은 이미 계산된 결과만 표시해야 함 (연산 제거)
- 기존 `app_daily_comparison.py` 패턴 (CSV 로드 → 시각화)과 일관성 필요
- `run_single_backtest.py`는 현재 콘솔 로그만 출력하고 결과를 파일로 저장하지 않음

### "연산" vs "표시 변환" 경계

| 구분 | 예시 | 수행 위치 |
|------|------|-----------|
| 연산 (비즈니스 로직) | `run_buffer_strategy()`, `add_single_moving_average()`, `pct_change()`, drawdown 계산, 월별 리샘플링, 보유기간 계산 | `run_single_backtest.py` |
| 표시 변환 (렌더링) | DataFrame→dict 변환, date→str 포맷, 한글 rename, 색상 할당, NaN 필터링, Plotly/lightweight-charts 데이터 구조 변환, pivot table 재배치 | `app_single_backtest.py` |

### 저장 파일 구조

| 파일 | 형식 | 용도 | 핵심 컬럼/키 |
|------|------|------|-------------|
| `single_backtest_signal.csv` | CSV | 캔들차트 + MA + 전일대비% | Date, Open, High, Low, Close, Volume, ma_{window}, change_pct |
| `single_backtest_equity.csv` | CSV | 에쿼티 + 드로우다운 + 밴드 | Date, equity, position, buffer_zone_pct, upper_band, lower_band, drawdown_pct |
| `single_backtest_trades.csv` | CSV | 거래 내역 + 보유기간 | entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, exit_reason, buffer_zone_pct, hold_days_used, recent_buy_count, holding_days |
| `single_backtest_summary.json` | JSON | 요약 지표 + 파라미터 + 월별 수익률 | (아래 참조) |

#### summary.json 구조

```json
{
  "summary": {
    "initial_capital": 10000000.0,
    "final_capital": "...",
    "total_return_pct": "...",
    "cagr": "...",
    "mdd": "...",
    "total_trades": "...",
    "winning_trades": "...",
    "losing_trades": "...",
    "win_rate": "...",
    "start_date": "...",
    "end_date": "..."
  },
  "params": {
    "ma_window": 200,
    "ma_type": "ema",
    "buffer_zone_pct": 0.03,
    "hold_days": 0,
    "recent_months": 0,
    "initial_capital": 10000000.0,
    "param_source": {
      "ma_window": "grid_best",
      "buffer_zone_pct": "grid_best",
      "hold_days": "grid_best",
      "recent_months": "grid_best"
    }
  },
  "monthly_returns": [
    {"year": 2010, "month": 1, "return_pct": 3.45},
    {"year": 2010, "month": 2, "return_pct": -1.23}
  ],
  "data_info": {
    "signal_path": "storage/stock/QQQ_max.csv",
    "trade_path": "storage/stock/TQQQ_synthetic_max.csv"
  }
}
```

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 공통 규칙
- `scripts/CLAUDE.md`: CLI 계층 규칙 (Streamlit width 규칙, 예외 처리 등)
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `src/qbt/utils/CLAUDE.md`: 유틸리티 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족 (아래 상세)
  - [x] `run_single_backtest.py`가 4개 결과 파일을 저장 (signal CSV, equity CSV, trades CSV, summary JSON)
  - [x] `app_single_backtest.py`가 결과 파일만 로드하여 표시 (연산 제거)
  - [x] 사이드바 파라미터 조정 기능 제거
  - [x] 기존 차트/지표 모두 동일하게 표시 (캔들, MA, 밴드, 마커, 에쿼티, 드로우다운, 히트맵, 히스토그램, 요약, 거래 상세)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (README.md, scripts/CLAUDE.md, CLAUDE.md 루트)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- (수정) `src/qbt/common_constants.py`: 결과 파일 경로 상수 4개 추가
- (수정) `src/qbt/utils/meta_manager.py`: `VALID_CSV_TYPES`에 `"single_backtest"` 추가
- (수정) `scripts/backtest/run_single_backtest.py`: CSV/JSON 저장 + 메타데이터 저장 추가
- (수정) `scripts/backtest/app_single_backtest.py`: 연산 제거, 표시 전용 리팩토링
- (수정) `README.md`: 워크플로우 1에 대시보드 실행 방법 추가
- (수정) `scripts/CLAUDE.md`: 앱 설명 업데이트
- (수정) `CLAUDE.md` (루트): 디렉토리 구조에 결과 파일 추가

### 데이터/결과 영향

- 새로운 결과 파일 4개 생성 (`storage/results/single_backtest_*.csv`, `single_backtest_summary.json`)
- 기존 결과 파일 변경 없음
- `meta.json`에 `"single_backtest"` 타입 이력 추가

## 6) 단계별 계획(Phases)

> Phase 0 생략: 인바리언트/정책 변경 없음 (데이터 저장 추가 + 앱 리팩토링)

---

### Phase 1 — 상수 추가 + run_single_backtest.py 결과 저장

**작업 내용**:

- [x] `src/qbt/common_constants.py`에 경로 상수 추가
- [x] `src/qbt/utils/meta_manager.py`의 `VALID_CSV_TYPES`에 `"single_backtest"` 추가
- [x] `scripts/backtest/run_single_backtest.py`에 결과 저장 로직 추가

---

### Phase 2 — app_single_backtest.py 표시 전용 리팩토링

**작업 내용**:

- [x] `app_single_backtest.py`에서 연산 제거, 결과 파일 로드 + 표시 전용으로 전환

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` 업데이트
- [x] `scripts/CLAUDE.md` 업데이트
- [x] `CLAUDE.md` (루트) 업데이트
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 대시보드를 표시 전용으로 리팩토링 (연산 분리)
2. 백테스트 / run_single_backtest 결과 저장 + 대시보드 연산 제거
3. 백테스트 / 앱 연산 분리: CLI에서 결과 저장, 앱은 표시만
4. 백테스트 / 대시보드 표시 전용 전환 및 결과 파일 저장 추가
5. 백테스트 / CLI-앱 역할 분리: 결과 CSV/JSON 저장 + 앱 표시 전용화

## 7) 리스크(Risks)

- **결과 파일 미존재 시 앱 실행 불가**: `st.warning` + `st.stop()`으로 사용자에게 선행 스크립트 안내
- **signal CSV 크기**: QQQ 전체 기간 OHLC 데이터이므로 수천 행 수준, 용량 문제 없음
- **summary JSON의 monthly_returns 크기**: 수백 개 항목, JSON으로 충분

## 8) 메모(Notes)

- 기존 `app_daily_comparison.py` 패턴 참고: CSV 로드 → 시각화 (연산 없음)
- `run_single_backtest.py`의 기존 기능 (콘솔 출력, Buy & Hold 비교)은 그대로 유지
- 실행 순서: `run_single_backtest.py` → `app_single_backtest.py`
- `run_single_backtest.py`는 항상 EMA를 기본 MA 유형으로 사용 (grid_search와 동일)

### 진행 로그 (KST)

- 2026-02-17 01:30: Plan 작성 완료 (Draft)
- 2026-02-17 02:00: Phase 1~3 완료, validate_project.py 통과 (passed=284, failed=0, skipped=0), Done
