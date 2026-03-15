# Implementation Plan: 분할 매수매도 시각화 대시보드

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

**작성일**: 2026-03-15
**마지막 업데이트**: 2026-03-15
**관련 범위**: scripts, backtest, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/tranche_architecture.md`

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

- [x]`run_split_backtest.py`에 signal.csv 저장 기능 추가 (3개 MA + 6개 밴드 포함)
- [x]`app_split_backtest.py` 신규 생성 (분할 매수매도 시각화 대시보드)
- [x]캔들스틱 차트에 MA/밴드/매매 마커를 표시하여 매매 근거를 시각적으로 확인 가능
- [x]트랜치별 매매 타임라인 및 포지션 변화(보유수량, 평균단가) 추적 가능
- [x]합산 에쿼티 + 트랜치별 에쿼티 오버레이 차트

## 2) 비목표(Non-Goals)

- 기존 `app_single_backtest.py` 수정 (별도 앱으로 분리)
- 리밸런싱 시각화 (추후 별도 계획서)
- 분할 전략의 비즈니스 로직 변경 (`split_strategy.py` 로직 무변경)
- WFO 시각화 (분할 전략에는 WFO 미적용)
- 시장 구간별 분석 (단일 전략 앱에만 존재)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_split_backtest.py`가 실행되어 결과(equity.csv, trades.csv, summary.json)가 저장되지만, 시각화 대시보드가 없어 결과를 시각적으로 확인할 수 없음
- 기존 `app_single_backtest.py`에 추가하기 어려움:
  - 기존 앱은 `signal.csv` 필수인데 분할 전략은 미생성
  - `summary.json` 구조가 다름 (`summary.params` vs `split_summary.tranches`)
  - `_discover_strategies()`가 `signal.csv` 없으면 스킵
- 사용자 핵심 요구: "어떤 조건(sell buffer 하회 등)으로 매매가 발생했는지 시각적으로 확인" → signal.csv(OHLC + MA + 밴드) 필요
- 사용자 핵심 요구: "실제 주식매매처럼 평균단가, 보유수량 변화를 추적" → equity.csv에 이미 `avg_entry_price`, `active_tranches`, `{tranche_id}_position` 존재

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 전반 규칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙 (대시보드 앱 아키텍처 섹션 포함)
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (Streamlit 앱 규칙 포함)
- `docs/tranche_architecture.md`: 데이터 흐름/출력 구조 설계

## 4) 완료 조건(Definition of Done)

- [x]`run_split_backtest.py`에 signal.csv 저장 추가 (Date, OHLCV, ma_250/200/150, upper/lower_band_250/200/150, change_pct)
- [x]`app_split_backtest.py` 신규 생성
- [x]Section 1: 요약 지표 (합산 레벨 + 트랜치별 비교 테이블)
- [x]Section 2: 메인 캔들스틱 차트 (OHLC + MA + 밴드 + 매매 마커, 트랜치 포커스 선택)
- [x]Section 3: 합산 에쿼티 차트 (합산 + 트랜치별 오버레이)
- [x]Section 4: 포지션 추적 차트 (active_tranches 서브차트 + avg_entry_price 오버레이)
- [x]Section 5: 드로우다운 차트
- [x]Section 6: 거래 상세 테이블 (트랜치별 색상 구분, 손익 표시)
- [x]Section 7: 사용 파라미터 (JSON 표시)
- [x]`poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x]`poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x]관련 문서 업데이트 (`scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`)
- [x]plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 파일

| 파일 | 변경 내용 |
|---|---|
| `scripts/backtest/run_split_backtest.py` | signal.csv 저장 기능 추가 (`_save_signal_csv` 함수) |
| `scripts/CLAUDE.md` | `app_split_backtest.py` 설명 추가 |
| `src/qbt/backtest/CLAUDE.md` | 분할 대시보드 아키텍처 설명 추가 |

### 신규 파일

| 파일 | 목적 |
|---|---|
| `scripts/backtest/app_split_backtest.py` | 분할 매수매도 시각화 대시보드 (Streamlit) |

### 변경하지 않는 파일 (절대 규칙)

| 파일 | 이유 |
|---|---|
| `src/qbt/backtest/split_strategy.py` | 비즈니스 로직 무변경 |
| `scripts/backtest/app_single_backtest.py` | 기존 단일 전략 대시보드 유지 |
| `src/qbt/backtest/strategies/buffer_zone_helpers.py` | 기존 코드 무변경 원칙 |

### 데이터/결과 영향

- `storage/results/backtest/split_buffer_zone_tqqq/signal.csv` 신규 생성
- `storage/results/backtest/split_buffer_zone_qqq/signal.csv` 신규 생성
- 기존 equity.csv, trades.csv, summary.json에는 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — signal.csv 저장 기능 추가 (그린)

> `run_split_backtest.py`에 signal.csv 저장 로직을 추가한다.
> 기존 `run_single_backtest.py`의 `_save_signal_csv` 패턴을 참고한다.

**작업 내용**:

- [x]`run_split_backtest.py`에 `_save_signal_csv` 함수 추가

signal.csv 저장 로직:

```python
def _save_signal_csv(result: SplitStrategyResult) -> None:
    """분할 전략의 시그널 데이터를 CSV로 저장한다.

    3개 MA(ma_250/200/150) + 6개 밴드(upper/lower × 3) + 전일종가대비%를 포함한다.
    밴드 계산: upper = ma * (1 + buy_buffer_zone_pct), lower = ma * (1 - sell_buffer_zone_pct)
    """
```

signal.csv 컬럼:

| 컬럼 | 타입 | 설명 | 반올림 |
|---|---|---|---|
| `Date` | date | 날짜 | - |
| `Open` | float | 시가 | 6자리 |
| `High` | float | 고가 | 6자리 |
| `Low` | float | 저가 | 6자리 |
| `Close` | float | 종가 | 6자리 |
| `Volume` | int | 거래량 | - |
| `ma_250` | float | EMA 250 | 6자리 |
| `ma_200` | float | EMA 200 | 6자리 |
| `ma_150` | float | EMA 150 | 6자리 |
| `upper_band_250` | float | ma_250 × (1 + buy_buffer_zone_pct) | 6자리 |
| `lower_band_250` | float | ma_250 × (1 - sell_buffer_zone_pct) | 6자리 |
| `upper_band_200` | float | ma_200 × (1 + buy_buffer_zone_pct) | 6자리 |
| `lower_band_200` | float | ma_200 × (1 - sell_buffer_zone_pct) | 6자리 |
| `upper_band_150` | float | ma_150 × (1 + buy_buffer_zone_pct) | 6자리 |
| `lower_band_150` | float | ma_150 × (1 - sell_buffer_zone_pct) | 6자리 |
| `change_pct` | float | 전일종가대비(%) | 2자리 |

데이터 소스:

- OHLCV: `run_split_backtest()` 실행 전에 로딩되는 signal_df (QQQ 데이터)
- MA: signal_df에 이미 `add_single_moving_average()`로 계산됨 (split_strategy.py 472~475행)
- 밴드: `base_config`의 `buy_buffer_zone_pct`/`sell_buffer_zone_pct`로 계산

**구현 방법**: `SplitStrategyResult`에는 signal_df가 포함되어 있지 않으므로, 두 가지 방안 중 하나를 선택한다.

방안 A — `_save_split_results()` 내에서 signal_df를 별도 로딩:
- 장점: `split_strategy.py` 무변경
- 단점: 데이터 중복 로딩, MA 재계산 필요

방안 B — `SplitStrategyResult`에 `signal_df` 필드 추가:
- 장점: 데이터 1회 로딩, MA 사전 계산 재활용
- 단점: `split_strategy.py` 수정 필요 (dataclass 필드 추가 + run_split_backtest 반환값 변경)

**선택: 방안 B** — `SplitStrategyResult`에 `signal_df: pd.DataFrame` 필드를 추가한다.
이유: signal_df는 이미 `run_split_backtest()` 내부에서 로딩 + MA 계산이 완료되어 있다. 이를 반환하면 중복 로딩/재계산 없이 signal.csv를 저장할 수 있다.
단, 이는 dataclass에 필드 1개 추가 + 반환 시 할당 1줄 추가일 뿐이며, 비즈니스 로직 자체는 변경하지 않는다.

- [x]`SplitStrategyResult`에 `signal_df: pd.DataFrame` 필드 추가 (split_strategy.py)
- [x]`run_split_backtest()`에서 signal_df를 결과에 포함 (split_strategy.py)
- [x]`_save_split_results()` 내에서 `_save_signal_csv()` 호출
- [x]밴드 계산: `ma * (1 + buy_buffer_zone_pct)` / `ma * (1 - sell_buffer_zone_pct)`

---

### Phase 2 — 대시보드 앱 구현: 데이터 로딩 + 요약 + 캔들스틱 (그린)

> 대시보드의 뼈대와 핵심 차트(캔들스틱 + MA + 밴드 + 마커)를 구현한다.

**작업 내용**:

- [x]`scripts/backtest/app_split_backtest.py` 신규 생성

앱 구조:

```
app_split_backtest.py
├── 로컬 상수 (차트 높이, 색상, 트랜치별 색상 매핑)
├── SplitStrategyData (TypedDict): 전략 데이터 컨테이너
├── _load_csv / _load_json: CSV/JSON 로더 (st.cache_data)
├── _discover_split_strategies(): 분할 전략 자동 탐색
│     BACKTEST_RESULTS_DIR에서 split_* 디렉토리 + summary.json에 "split_summary" 키 존재 여부로 판별
├── Section 1: 요약 지표
│     합산 레벨 metric 카드 + 트랜치별 비교 테이블
├── Section 2: 메인 캔들스틱 차트
│     OHLC + 포커스 트랜치 선택 + MA/밴드/마커
├── (Phase 3에서 추가되는 섹션들)
└── main()
```

- [x]전략 자동 탐색 (`_discover_split_strategies`)
  - `BACKTEST_RESULTS_DIR` 하위에서 `split_` 접두사 디렉토리 탐색
  - `summary.json`에 `split_summary` 키가 있으면 분할 전략으로 판별
  - 필수 파일: `summary.json`, `signal.csv`, `equity.csv`, `trades.csv`

- [x]Section 1: 요약 지표
  - 합산 레벨: 수익률, CAGR, MDD, Calmar, 총 거래수 (metric 카드)
  - 트랜치별 비교 테이블: tranche_id, MA, 가중치, 수익률, CAGR, MDD, Calmar, 거래수

- [x]Section 2: 메인 캔들스틱 차트

  포커스 트랜치 선택 UI (Streamlit selectbox):
  ```
  "전체 보기"  → MA 3개 라인만 (밴드 없음) + 모든 트랜치 마커
  "ma250 포커스" → ma_250 + upper/lower_band_250 + ma250 마커만
  "ma200 포커스" → ma_200 + upper/lower_band_200 + ma200 마커만
  "ma150 포커스" → ma_150 + upper/lower_band_150 + ma150 마커만
  ```

  차트 구성 (lightweight-charts):
  - Pane 1: 캔들스틱 + MA 라인(선택에 따라 1~3개) + 밴드(포커스 시 2개) + 매매 마커
  - 마커 텍스트: `"ma250-Buy $102.5"`, `"ma200-Sell +5.3%"` 형식 (tranche_id 포함)
  - 마커 색상: 트랜치별 고유 색상 (3색 구분)
  - customValues: OHLC 가격, 전일대비%, MA값, 밴드값
  - 미청산 포지션: `"ma250-Buy $35.5 (보유중)"` 마커

  트랜치별 색상 체계:
  ```
  ma250: 파랑 계열 (긴 추세 = 차분)
  ma200: 주황 계열 (기준 = 기존 MA 색상 유지)
  ma150: 초록 계열 (빠른 반응 = 활발)
  ```

---

### Phase 3 — 대시보드 앱 구현: 에쿼티 + 포지션 추적 + 거래 테이블 (그린)

> 나머지 섹션들을 구현한다.

**작업 내용**:

- [x]Section 3: 합산 에쿼티 차트

  lightweight-charts 멀티페인:
  - Area 시리즈: 합산 equity (메인)
  - Line 시리즈: ma250_equity, ma200_equity, ma150_equity (트랜치별 오버레이, 각 트랜치 색상)

- [x]Section 4: 포지션 추적 차트

  실제 주식매매처럼 보유 상태 변화를 추적하는 차트:

  Pane 1: 보유 트랜치 수 (`active_tranches`)
  - Histogram/Bar 스타일: 0~3 범위, 날짜별 보유 트랜치 수
  - "매수 분산이 어떻게 이루어지는지" 한눈에 확인

  Pane 2: 가중 평균 진입가 (`avg_entry_price`)
  - Line 시리즈: 보유 중일 때만 표시 (None인 구간은 빈칸)
  - 종가(Close) 라인 오버레이로 현재가 대비 평단 위치 확인

  Pane 3: 트랜치별 보유수량 변화
  - 3개 Line 시리즈: ma250_position, ma200_position, ma150_position
  - 트랜치별 색상 적용
  - "어느 트랜치가 언제 들어가고 나오는지" 시각적 확인

- [x]Section 5: 드로우다운 차트
  - Area 시리즈: equity 기준 drawdown_pct (기존 패턴 재사용)
  - invertFilledArea + fixedMaxValue=0

- [x]Section 6: 거래 상세 테이블

  trades.csv 기반 데이터프레임:
  - 컬럼: 트랜치, MA, 진입일, 청산일, 진입가, 청산가, 수량, 손익금액, 손익률, 보유기간
  - 트랜치별 배경색 구분 (ma250=파랑 연하게, ma200=주황 연하게, ma150=초록 연하게)
  - 손익 기반 행 스타일: 수익=초록 배경, 손실=빨강 배경 (기존 `_style_pnl_rows` 패턴)

- [x]Section 7: 사용 파라미터
  - `summary.json`의 `split_config` JSON 표시

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x]`scripts/CLAUDE.md` 업데이트 (app_split_backtest.py 설명 추가)
- [x]`src/qbt/backtest/CLAUDE.md` 업데이트 (분할 대시보드 아키텍처 설명 추가)
- [x]`poetry run black .` 실행 (자동 포맷 적용)
- [x]변경 기능 및 전체 플로우 최종 검증
- [x]DoD 체크리스트 최종 업데이트 및 체크 완료
- [x]전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=351, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 분할 매수매도 시각화 대시보드 신규 구현 + signal.csv 저장 추가
2. 대시보드 / app_split_backtest.py 신규 — 트랜치별 캔들·에쿼티·포지션 추적 시각화
3. 백테스트 / 분할 전략 시각화 대시보드 구현 (캔들스틱 + 포지션 변화 + 거래 테이블)
4. 대시보드 / 분할 매수매도 결과 시각화 + run_split_backtest signal.csv 저장
5. 백테스트 / 분할 전략 대시보드 + signal.csv 생성 기능 추가

## 7) 리스크(Risks)

- **signal.csv 데이터 정합성**: `run_split_backtest()`에서 로딩하는 signal_df와 동일한 데이터가 signal.csv에 저장되어야 함 → Phase 1에서 `SplitStrategyResult`에 signal_df를 포함하여 동일 데이터 보장
- **캔들스틱 차트에 3개 밴드 동시 표시 시 복잡성**: 6개 밴드 라인이 겹쳐서 가독성 저하 → "포커스 트랜치 선택" UI로 해결 (전체 보기 시 MA 라인만, 포커스 시 해당 밴드만)
- **lightweight-charts 멀티페인 높이**: 여러 Pane이 한 화면에 표시되면 스크롤이 길어짐 → 포지션 추적 Pane을 expander로 감싸는 것 고려
- **SplitStrategyResult 필드 추가**: dataclass 변경 시 기존 테스트 영향 → signal_df 필드는 Optional이 아닌 필수로 추가하되, 기존 테스트에서 생성하는 SplitStrategyResult에도 signal_df를 전달해야 함

## 8) 메모(Notes)

### 핵심 결정 사항

- **별도 앱 생성**: `app_single_backtest.py`와 분리 — 데이터 구조(summary.json)와 시각화 요구사항이 본질적으로 다름
- **차트 라이브러리**: 기존 스택 유지 (lightweight-charts + Plotly) — vendor fork에 tooltip 지원 이미 완비
- **signal.csv 추가**: 매매 근거 시각 확인을 위해 OHLC + MA + 밴드 데이터를 CSV로 저장
- **SplitStrategyResult에 signal_df 추가**: 방안 B 선택 — 중복 로딩 방지, MA 사전 계산 재활용

### 참고 문서

- 선행 계획서: `docs/plans/PLAN_split_strategy.md` (분할 매수매도 오케스트레이터)
- 설계 문서: `docs/tranche_architecture.md` (§4 시각화 데이터 상세)
- 기존 대시보드: `scripts/backtest/app_single_backtest.py` (패턴 참고)

### 진행 로그 (KST)

- 2026-03-15: 계획서 작성

---
