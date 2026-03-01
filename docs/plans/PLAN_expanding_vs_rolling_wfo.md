# Implementation Plan: Expanding vs Rolling Window WFO 비교 실험

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

**작성일**: 2026-02-28 21:00
**마지막 업데이트**: 2026-03-01
**관련 범위**: backtest, scripts, tests
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

- [x] Expanding Anchored WFO와 Rolling Window WFO를 **동일 OOS 기간**에 대해 비교
- [x] Rolling Window의 "위기 데이터 망각" 위험을 **정량적으로 검증**
- [x] Stitched MDD / CAGR / Calmar 지표로 두 모드의 성과 차이를 측정

## 2) 비목표(Non-Goals)

- Rolling Window를 프로덕션 모드로 채택하는 것 (비교 실험만 수행)
- Sell Fixed / Fully Fixed 모드 비교 (Dynamic 모드만 비교)
- buffer_zone_tqqq 및 buffer_zone_qqq 전략 비교 (buffer_zone_atr_tqqq만 대상)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

§3.6에서 Expanding Anchored WFO의 "지연된 전환" 현상이 발견됨. IS가 항상 1999년부터 시작하므로 초기 위기 데이터의 비중이 점차 줄어들다 임계점에서 파라미터가 전환되는 효과.

§3.7에서 이론적으로 Rolling Window가 더 빠른 레짐 전환을 제공할 수 있으나 "위기 데이터 망각"이라는 핵심 위험이 있다고 분석. 이를 정량적으로 검증하는 것이 이 실험의 목적.

### Rolling Window 동작 원리

Expanding (현재):

- 모든 윈도우에서 IS가 data_start(1999)에서 시작, OOS 전까지 확장
- W1: IS=72개월, W3: IS=120개월, W5: IS=168개월, ...

Rolling (IS=120개월):

- IS가 최대 120개월(10년) 고정 길이, 초과 시 시작점이 전진
- W1~W3: IS < 120개월이므로 Expanding과 **동일** (data_start로 클램핑)
- W4+: IS=120개월 고정, 1999~2001년 데이터부터 순차적으로 탈락
- 후반 윈도우: 2000 닷컴버블, 2008 금융위기 경험 완전 소멸

**핵심 비교 포인트**: 동일 OOS 기간에서 IS 구성만 다르므로, 성과 차이 = IS 데이터 구성의 영향

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `generate_wfo_windows()`에 Rolling 모드 지원 추가
- [x] `run_walkforward()`에 `rolling_is_months` 파라미터 전달
- [x] 비교 모듈(`wfo_comparison.py`) 구현 완료
- [x] CLI 스크립트(`run_wfo_comparison.py`) 구현 완료
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=419, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (CLAUDE.md, improvement_log)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직 (src/qbt/backtest/):**

- `walkforward.py` — `generate_wfo_windows()` Rolling 모드 추가, `run_walkforward()` 파라미터 전달
- `wfo_comparison.py` — 신규 모듈, Expanding vs Rolling 비교 로직
- `constants.py` — Rolling IS 기본값, 비교 결과 파일명 상수 추가

**CLI 스크립트 (scripts/backtest/):**

- `run_wfo_comparison.py` — 신규, 비교 실험 실행 스크립트

**테스트 (tests/):**

- `test_backtest_walkforward.py` — Rolling 윈도우 생성 테스트 추가
- `test_wfo_comparison.py` — 신규, 비교 모듈 테스트

**문서:**

- `src/qbt/backtest/CLAUDE.md` — wfo_comparison 모듈 설명 추가
- `scripts/CLAUDE.md` — 스크립트 설명 추가
- `tests/CLAUDE.md` — 테스트 파일 목록 추가
- `buffer_zone_tqqq_improvement_log.md` — 실험 결과 반영

### 데이터/결과 영향

신규 결과 파일 (storage/results/backtest/buffer_zone_atr_tqqq/):

- `wfo_comparison_windows.csv` — 윈도우별 Expanding vs Rolling 비교
- `wfo_comparison_summary.json` — 요약 통계

기존 결과 파일: **변경 없음** (기존 WFO 결과 유지)

## 6) 단계별 계획(Phases)

### Phase 0 — Rolling 윈도우 생성 테스트 작성 (레드)

**작업 내용**:

- [x] `tests/test_backtest_walkforward.py`에 Rolling 윈도우 테스트 클래스 추가:
  - `test_rolling_same_oos_timing`: Rolling과 Expanding의 OOS 기간이 동일한지 검증
  - `test_rolling_is_start_diverges`: 특정 윈도우부터 IS 시작점이 다른지 검증
  - `test_rolling_is_length_capped`: Rolling IS 길이가 `rolling_is_months`를 초과하지 않는지 검증
  - `test_rolling_none_preserves_expanding`: `rolling_is_months=None`이면 기존 동작과 동일
  - `test_rolling_early_windows_identical`: 초기 윈도우에서 Expanding과 Rolling이 동일한지 검증

---

### Phase 1 — walkforward.py Rolling 모드 구현 (그린)

**작업 내용**:

- [x] `walkforward.py`에 `_first_day_months_before()` 헬퍼 함수 추가
  ```python
  def _first_day_months_before(ref_end: date, months: int) -> date:
      """ref_end의 월에서 months-1개월 전의 첫째 날을 반환한다."""
  ```
- [x] `generate_wfo_windows()`에 `rolling_is_months: int | None = None` 파라미터 추가
  - `None` (기본값): 기존 Expanding 동작 유지
  - `int`: Rolling 모드 — `is_start = max(data_start, _first_day_months_before(is_end, rolling_is_months))`
- [x] `run_walkforward()`에 `rolling_is_months: int | None = None` 파라미터 추가, `generate_wfo_windows()`로 전달
- [x] Phase 0 테스트 전부 통과 확인

---

### Phase 2 — wfo_comparison.py 비교 모듈 구현 + 테스트 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/constants.py`에 상수 추가:
  - `DEFAULT_WFO_ROLLING_IS_MONTHS: Final = 120`
  - `WFO_COMPARISON_WINDOWS_FILENAME: Final = "wfo_comparison_windows.csv"`
  - `WFO_COMPARISON_SUMMARY_FILENAME: Final = "wfo_comparison_summary.json"`
- [x] `src/qbt/backtest/wfo_comparison.py` 신규 모듈 구현 (atr_comparison.py 패턴 참조):

  **TypedDicts**:

  ```python
  class WfoComparisonResultDict(TypedDict):
      window_type: str  # "expanding" or "rolling"
      rolling_is_months: int | None
      window_results: list[WfoWindowResultDict]
      mode_summary: WfoModeSummaryDict

  class WfoComparisonWindowRow(TypedDict):
      window_idx: int
      oos_start: str
      oos_end: str
      expanding_is_start: str
      rolling_is_start: str
      is_identical: bool  # 두 모드의 IS가 동일한지
      exp_oos_cagr: float
      exp_oos_mdd: float
      exp_oos_calmar: float
      exp_oos_trades: int
      roll_oos_cagr: float
      roll_oos_mdd: float
      roll_oos_calmar: float
      roll_oos_trades: int
      diff_oos_cagr: float
      diff_oos_mdd: float
      diff_oos_calmar: float
  ```

  **함수 3개** (atr_comparison.py의 3-함수 패턴 준수):

  ```python
  def run_single_wfo_mode(
      signal_df, trade_df,
      rolling_is_months: int | None = None,
      ...WFO params...,
  ) -> WfoComparisonResultDict:
      """단일 WFO 모드(Expanding 또는 Rolling)를 실행한다."""

  def build_window_comparison(
      expanding: WfoComparisonResultDict,
      rolling: WfoComparisonResultDict,
  ) -> pd.DataFrame:
      """윈도우별 비교 DataFrame을 생성한다."""

  def build_comparison_summary(
      expanding: WfoComparisonResultDict,
      rolling: WfoComparisonResultDict,
      comparison_df: pd.DataFrame,
  ) -> dict[str, object]:
      """비교 요약 통계를 생성한다."""
  ```

- [x] `tests/test_wfo_comparison.py` 신규 테스트 추가:
  - `TestBuildWindowComparison`: 윈도우 수 불일치 검증, 차이 계산, is_identical 플래그
  - `TestBuildComparisonSummary`: 승수 카운트, 필수 필드 존재, diff 통계
  - `TestRunSingleWfoMode`: 구조 검증 (소규모 데이터 통합 테스트)

---

### Phase 3 — CLI 스크립트 구현 (그린)

**작업 내용**:

- [x] `scripts/backtest/run_wfo_comparison.py` 신규 CLI 스크립트:
  1. 데이터 로딩 (QQQ + TQQQ synthetic, overlap 추출)
  2. Expanding WFO Dynamic 실행 (`rolling_is_months=None`)
  3. Rolling WFO Dynamic 실행 (`rolling_is_months=120`)
  4. 비교 DataFrame + 요약 통계 생성
  5. 결과 테이블 출력
  6. CSV/JSON 저장 (반올림 규칙 적용)
  7. 메타데이터 저장

- [x] `src/qbt/utils/meta_manager.py`: `"wfo_comparison"` 타입 추가

---

### Phase 4 — 실험 실행 + 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run python scripts/backtest/run_wfo_comparison.py` 실행 (사용자 직접 실행)
- [x] 결과 분석 및 해석 (사용자 직접 수행)
- [x] `buffer_zone_tqqq_improvement_log.md` 업데이트 (실행 결과 반영 후):
  - §1 TL;DR에 결과 요약 추가
  - §3.7에 정량적 결과 추가
  - §6 실험 계획에서 4순위 완료 처리
  - §8 변경 로그에 항목 추가
- [x] `src/qbt/backtest/CLAUDE.md` — wfo_comparison 모듈 설명 추가
- [x] `scripts/CLAUDE.md` — run_wfo_comparison.py 설명 추가
- [x] `tests/CLAUDE.md` — test_wfo_comparison.py 목록 추가
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=419, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Expanding vs Rolling WFO 비교 실험 모듈 신규 추가
2. 백테스트 / Rolling Window WFO 지원 및 비교 실험 구현
3. 백테스트 / WFO 윈도우 방식 비교 실험 (Expanding vs Rolling) 추가
4. 백테스트 / Rolling WFO 위기 데이터 망각 위험 정량 검증 구현
5. 백테스트 / Expanding·Rolling WFO 비교 모듈 + CLI + 테스트 추가

## 7) 리스크(Risks)

| 리스크                                                    | 완화책                                                                         |
| --------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Rolling WFO 실행 시간 (기존 WFO와 동일한 그리드 서치 2회) | buffer_zone_atr_tqqq 단일 전략만 대상. 순차 실행으로 약 20~30분 예상           |
| Rolling IS에서 데이터 부족으로 그리드 서치 실패           | `min_trades` 필터로 거래수 부족 조합 제거 (기존 로직 재사용)                   |
| OOS 기간 정렬 불일치                                      | `generate_wfo_windows()`가 동일 OOS 생성, `build_window_comparison()`에서 검증 |

## 8) 메모(Notes)

### 핵심 설계 결정

- **Rolling IS 길이**: 120개월 (10년). §3.7 예시 및 위기 데이터(2000 닷컴, 2008 금융위기) 포함 여부 검증에 적합
- **비교 대상**: buffer_zone_atr_tqqq Dynamic 모드만. 이유: 현재 프로덕션 전략이며, ATR 스탑의 위기 대응 효과와 Rolling의 위기 데이터 손실 효과를 동시에 관찰 가능
- **OOS 정렬**: Expanding과 Rolling이 동일 OOS 기간을 사용하여 IS 구성의 영향만 분리 측정
- **기존 코드 재사용**: `run_walkforward()`, `build_params_schedule()`, stitched equity 생성 로직 전부 재사용. `generate_wfo_windows()`에 파라미터 1개 추가만으로 Rolling 지원

### 참고 패턴

- `atr_comparison.py`의 3-함수 패턴 (run_single → build_window_comparison → build_summary)
- `run_atr_comparison.py`의 CLI 오케스트레이션 패턴

### 진행 로그 (KST)

- 2026-02-28 21:00: 계획서 초안 작성
- 2026-03-01: Phase 0~3 코드 구현 + Phase 4 문서/검증 완료 (passed=419, failed=0, skipped=0)
- 2026-03-02: 스크립트 실행 + 결과 분석 + improvement_log 반영 → Done

---
