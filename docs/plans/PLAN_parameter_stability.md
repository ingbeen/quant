# Implementation Plan: 백테스트 파라미터 안정성 분석 대시보드

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

**작성일**: 2026-03-05 21:00
**마지막 업데이트**: 2026-03-05 22:00
**관련 범위**: backtest, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `overfitting_analysis_report.md` 11.2절

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

- [x] 버퍼존 QQQ 그리드 서치 결과(432개)의 파라미터 안정성을 시각화하는 Streamlit 대시보드 구축
- [x] overfitting_analysis_report.md 11.2절 "1단계: 파라미터 안정성 확인"의 3가지 분석 항목 구현
- [x] 분석 로직을 비즈니스 계층(`src/qbt/backtest/`)에, UI를 CLI 계층(`scripts/backtest/`)에 분리

## 2) 비목표(Non-Goals)

- 3파라미터 단순화 실험 (hold_days=0, recent_months=0 고정 후 27개 조합 재실행) — 별도 작업으로 분리
- 2단계(WFO 윈도우 분포 분석), 3단계(교차 자산 검증) 구현
- 기존 그리드 서치 로직 변경
- 새로운 백테스트 실행 (기존 grid_results.csv만 사용)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

overfitting_analysis_report.md에서 버퍼존 전략의 과최적화 여부를 3단계로 검증하는 계획을 수립하였다. 1단계는 "파라미터 안정성 확인"으로, 이미 보유한 grid_results.csv 데이터만으로 수행 가능하다.

핵심 질문: "버퍼존 QQQ 전략이 특정 파라미터 조합에 의존하는가, 아니면 넓은 파라미터 영역에서 작동하는가?"

사전 확인된 데이터 특성:
- 432개 전체 조합의 Calmar가 **모두 양수** (최소 0.0531, 최대 0.301)
- 보고서 1단계 통과 기준 첫 번째 항목("Calmar > 0이 과반수") 이미 충족

### 데이터 구조

grid_results.csv (432행):
```
이평기간,매수버퍼존,매도버퍼존,유지일,조정기간(월),수익률,CAGR,MDD,Calmar,거래수,승률,최종자본
```

파라미터 그리드:
- MA: [100, 150, 200] (3개)
- buy_buffer: [0.01, 0.03, 0.05] (3개)
- sell_buffer: [0.01, 0.03, 0.05] (3개)
- hold_days: [0, 2, 3, 5] (4개)
- recent_months: [0, 4, 8, 12] (4개)
- 합계: 3 x 3 x 3 x 4 x 4 = 432개

### 설계 결정 사항

**1. hold_days/recent_months 처리: 평균 집계**

히트맵에서 hold_days/recent_months를 **특정 값으로 고정하지 않고 평균 집계**한다.
- 근거: 특정 값(hold=3, recent=0) 고정은 "이미 최적인 값"을 선택하는 것이므로 결과가 편향된다
- 평균 집계는 "핵심 파라미터(buy/sell buffer)가 부차 파라미터에 관계없이 견고한가"를 측정하므로 과최적화 진단에 적합
- 평균과 함께 **최소값(min)도 표시**하여 최악의 경우 확인

**2. 시각화 도구: Streamlit + Plotly (별도 앱)**

- 프로젝트 기존 패턴과 일관성 유지 (app_single_backtest.py, app_daily_comparison.py 모두 Streamlit + Plotly)
- "백테스트 결과 시각화"와 "그리드 서치 메타 분석"은 성격이 다르므로 별도 앱으로 분리

**3. MA별 히트맵 3개 제공**

MA=200뿐 아니라 MA=100, MA=150도 히트맵을 제공한다.
- "MA 값에 관계없이 buy/sell buffer의 고원이 유지되는가" 확인
- MA=200에서만 고원이면 "전략이 MA=200에 의존한다"는 중요 정보

**4. 인접 파라미터 비교에 hold_days 축 포함**

buy/sell buffer 인접뿐 아니라 hold_days 변화에 따른 Calmar도 시각화한다.
- "hold_days를 제거해도 되는가(= hold_days=0으로 해도 괜찮은가)"의 근거 자료

**5. 히트맵 hover에 CAGR/MDD 보조 지표 표시**

같은 Calmar라도 "CAGR 높고 MDD 높은" 조합과 "CAGR 낮고 MDD 낮은" 조합은 성격이 다르므로, Plotly heatmap의 customdata + hovertemplate로 보조 지표를 함께 표시한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 계층 분리, 상수 관리, 코딩 표준, 스크립트 실행 규칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙, grid_results.csv 형식
- `scripts/CLAUDE.md`: CLI 계층 규칙, Streamlit 앱 규칙 (width 파라미터 등)
- `tests/CLAUDE.md`: Given-When-Then 패턴, 파일 격리, 부동소수점 비교
- `src/qbt/utils/CLAUDE.md`: 유틸리티 패키지 설계 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `src/qbt/backtest/parameter_stability.py` 구현 완료 (비즈니스 로직)
- [x] `scripts/backtest/app_parameter_stability.py` 구현 완료 (Streamlit 대시보드)
- [x] `tests/test_parameter_stability.py` 테스트 추가 (데이터 가공 로직 단위 테스트)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (새 모듈 설명, 보고서 11.2절 대응 관계 명시)
- [x] `README.md` 업데이트 (파라미터 안정성 대시보드 워크플로우 추가)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

신규 생성:
- `src/qbt/backtest/parameter_stability.py` — 분석 로직 (비즈니스 계층)
- `scripts/backtest/app_parameter_stability.py` — Streamlit 대시보드 (CLI 계층)
- `tests/test_parameter_stability.py` — 단위 테스트

수정:
- `src/qbt/backtest/CLAUDE.md` — 새 모듈 설명 추가
- `README.md` — 워크플로우에 파라미터 안정성 대시보드 추가

### 데이터/결과 영향

- 기존 데이터/결과 변경 없음
- 입력: `storage/results/backtest/buffer_zone_qqq/grid_results.csv` (읽기 전용)
- 출력: 없음 (대시보드에서 실시간 시각화만 수행)

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트로 인터페이스/정책 고정 (레드)

`parameter_stability.py`의 공개 함수 인터페이스와 데이터 가공 정책을 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `tests/test_parameter_stability.py` 작성
  - [x] `test_load_grid_results_returns_dataframe`: grid_results.csv 로드 → 내부 컬럼명 변환 검증 (DISPLAY → COL)
  - [x] `test_load_grid_results_validates_required_columns`: 필수 컬럼 미존재 시 ValueError
  - [x] `test_build_calmar_histogram_data_returns_all_432`: 히스토그램 데이터가 전체 행 수와 동일한지 검증
  - [x] `test_build_heatmap_data_filters_by_ma`: MA=200 필터링 시 정확히 144개 행 반환
  - [x] `test_build_heatmap_data_aggregates_mean_and_min`: buy_buffer x sell_buffer별 평균/최소 집계 → 9셀 피벗
  - [x] `test_build_heatmap_data_includes_cagr_mdd`: 집계 결과에 CAGR 평균, MDD 평균 포함
  - [x] `test_build_adjacent_comparison_returns_optimal_and_neighbors`: 최적 파라미터 기준 인접 조합 비교 데이터 반환
  - [x] `test_build_adjacent_comparison_includes_hold_days_axis`: hold_days 축 변화에 따른 Calmar 포함
  - [x] `test_evaluate_stability_criteria`: 보고서 11.2절 통과 기준 평가 함수 (Calmar>0 비율, 인접 30% 이내, 고원 여부)

---

### Phase 1 — 비즈니스 로직 구현 (그린 유지)

`src/qbt/backtest/parameter_stability.py` 모듈을 구현하여 Phase 0 테스트를 통과시킨다.

**작업 내용**:

- [x] `parameter_stability.py` 신규 생성
  - [x] 모듈 docstring (보고서 11.2절 대응 관계 명시)
  - [x] `load_grid_results(grid_results_path: Path) -> pd.DataFrame`
    - CSV 로드 + DISPLAY 컬럼명 → COL 컬럼명 변환 (rename 매핑)
    - 필수 컬럼 검증 (COL_MA_WINDOW, COL_BUY_BUFFER_ZONE_PCT, COL_SELL_BUFFER_ZONE_PCT, COL_CALMAR 등)
    - 파일 미존재/컬럼 부족 시 ValueError
  - [x] `build_calmar_histogram_data(df: pd.DataFrame) -> pd.Series`
    - 전체 Calmar 값 시리즈 반환
  - [x] `build_heatmap_data(df: pd.DataFrame, ma_window: int) -> pd.DataFrame`
    - MA 필터링 → buy_buffer x sell_buffer별 groupby
    - 집계: Calmar mean/min, CAGR mean, MDD mean
    - 반환: 피벗 가능한 DataFrame
  - [x] `build_adjacent_comparison(df: pd.DataFrame, optimal_ma: int, optimal_buy: float, optimal_sell: float) -> pd.DataFrame`
    - 최적 파라미터 기준 인접 조합 추출 (buy/sell 각각 한 단계 변경)
    - hold_days/recent_months는 평균 집계
    - hold_days 축: MA/buy/sell 고정 상태에서 hold_days별 평균 Calmar
    - 반환: 비교 테이블 DataFrame
  - [x] `evaluate_stability_criteria(df: pd.DataFrame, optimal_calmar: float) -> dict[str, Any]`
    - Calmar > 0 비율 (통과 기준: 과반수 216+)
    - 인접 파라미터 Calmar이 최적 대비 30% 이내인지 (통과 기준: >= 0.21)
    - 결과를 dict로 반환 (pass/fail 판정 포함)

---

### Phase 2 — Streamlit 대시보드 구현 (그린 유지)

`scripts/backtest/app_parameter_stability.py`를 구현한다.

**작업 내용**:

- [x] `app_parameter_stability.py` 신규 생성
  - [x] 모듈 docstring (선행 스크립트, 실행 명령어 명시)
  - [x] 페이지 설정 (`st.set_page_config`, wide layout)
  - [x] 전략 선택 (현재는 buffer_zone_qqq만, 추후 확장 가능하도록 selectbox)
  - [x] 섹션 A: Calmar 분포 히스토그램
    - Plotly histogram (432개 전체 Calmar)
    - Calmar > 0 비율, 평균, 중앙값, 표준편차 표시
    - 최적값 위치를 수직선으로 표시
  - [x] 섹션 B: MA별 buy_buffer x sell_buffer 히트맵
    - MA=100, MA=150, MA=200 세 개를 `st.columns(3)`으로 나란히 배치
    - Plotly heatmap (평균 Calmar 기준)
    - customdata + hovertemplate로 CAGR 평균, MDD 평균, Calmar 최소 표시
    - 색상 스케일 통일 (세 히트맵 간 zmin/zmax 동일)
  - [x] 섹션 C: 인접 파라미터 비교
    - 최적 파라미터 기준 인접 조합과의 Calmar 비교 바 차트
    - hold_days 축: MA=200, buy=0.03, sell=0.05 고정 상태에서 hold_days별 평균 Calmar 바 차트
    - 30% 임계선 표시 (최적 Calmar x 0.7)
  - [x] 섹션 D: 통과 기준 판정 요약
    - evaluate_stability_criteria 결과를 테이블로 표시
    - 통과/미달 시각적 표시

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - parameter_stability.py 모듈 설명 추가
  - 보고서 11.2절 대응 관계 명시
- [x] `README.md` 업데이트
  - 워크플로우 1에 "8. 파라미터 안정성 대시보드" 추가
  - 프로젝트 구조에 새 파일 반영
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=458, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 파라미터 안정성 분석 대시보드 추가 (과최적화 검증 1단계)
2. 백테스트 / 그리드 서치 결과 시각화 모듈 + Streamlit 앱 신규 구현
3. 백테스트 / 432개 파라미터 조합 안정성 분석 도구 구현
4. 백테스트 / 파라미터 히트맵 + 인접 비교 + 통과 기준 판정 대시보드 추가
5. 백테스트 / overfitting 검증 1단계 파라미터 안정성 시각화 구현

## 7) 리스크(Risks)

- **grid_results.csv 형식 변경 위험**: 기존 CSV의 컬럼명이 한글(DISPLAY_*)이므로, 로드 시 COL_* 내부 컬럼명으로 변환이 필요. 매핑이 틀리면 데이터 불일치 발생 → rename 매핑을 상수로 정의하고 테스트로 검증
- **Plotly heatmap 색상 스케일 불일치**: MA=100/150/200 세 히트맵의 Calmar 범위가 다를 경우 시각적 비교 어려움 → zmin/zmax를 전체 데이터 기준으로 통일

## 8) 메모(Notes)

### 사전 확인된 데이터 특성

- 432개 전체 Calmar > 0 (100% 양수, 최소 0.0531, 최대 0.301)
- 보고서 1단계 통과 기준 첫 번째 항목 이미 충족
- 최적: MA=200, buy=0.03, sell=0.05, hold=3, recent=0 → Calmar 0.301

### 보고서 11.2절 통과 기준 (대시보드에서 검증)

| 기준 | 통과 조건 |
|------|----------|
| Calmar > 0 비율 | 432개 중 과반수(216+) 이상 |
| 인접 파라미터 Calmar | 최적 대비 30% 이내 (>= 0.21) |
| 히트맵 형태 | 고원(넓고 완만) 관찰 |

### 진행 로그 (KST)

- 2026-03-05 21:00: 계획서 초안 작성
- 2026-03-05 22:00: 전체 Phase 완료, validate_project.py 통과 (458 passed, 0 failed, 0 skipped)

---
