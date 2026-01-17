# quant 프로젝트 작업 프롬프트 (2단계 분리본)

> 이 파일에는 **프롬프트 1**과 **프롬프트 2**가 함께 들어있다.  
> 코딩 AI는 이 파일을 전체로 읽은 뒤, 사용자의 지시에 따라 **1번 작업만 수행**하거나 **2번 작업만 수행**한다.  
> 2번 진행 시 1번 프롬프트를 읽어 “의도/변경점”은 파악할 수 있으나, 실제 코드 상태는 반드시 repo에서 확인하고 진행한다(추측 금지, Fail-fast).

---

## 공통 컨텍스트(두 프롬프트 공통)

- 프로젝트 경로: `/home/yblee/workspace/quant`
- 문제 원인(핵심): Streamlit 분석(`streamlit_rate_spread_lab.py`)에서 **FFR(금리 수준)** 과 **월말 누적오차(e_m)** 사이에 **강한 양(+) 관계** 관측  
  → 고금리 구간에서 시뮬레이션 TQQQ가 실제보다 높게(= 비용 과소 반영) 나오는 경향  
  → `funding_spread`를 **FFR 수준에 따라 동적으로 증가**시키는 로직이 필요
- ΔFFR 기반 반응은 약하므로 우선순위 낮음
- 1차 목표: **TQQQ 실존 기간** 동안 실제 TQQQ와 시뮬레이션 TQQQ를 **최대한 일치(RMSE 기준)**

### 공통 필수 규칙 / 전제

- **루트 및 폴더별 `CLAUDE.md`를 반드시 먼저 읽고 준수**
- **Fail-fast**: 결측/키 누락/NaN/inf/타입 불일치 등은 즉시 예외
- **베이스라인 동작 불변(절대 중요)**: `funding_spread`를 단일 float로 넣어 실행할 때 결과(산출 CSV, 핵심 수치)가 수정 전과 동일해야 함
- 단위/제약(확정):
  - `funding_spread`는 **ratio 단위** (예: `0.0034 = 0.34%`)
  - **min/max 클리핑(출력 clamp) 금지**
  - **음수 불허**, 그리고 **0도 불허**(반환 spread는 항상 `> 0`)
- 목적함수(확정): 프로젝트 기존 지표 `cumul_multiple_log_diff_rmse_pct` 를 RMSE로 사용하여 최소화
- 메타 기록(확정):
  - 참고 파일: `/home/yblee/workspace/quant/src/qbt/utils/meta_manager.py`
  - 기록 위치: `/home/yblee/workspace/quant/storage/results/meta.json`
  - 기록 방식: `save_metadata("tqqq_rate_spread_lab", meta_dict)` 형태로 append

### 기준 실행/산출물(공통)

- 실행 스크립트(베이스라인/기능 확인용):  
  `/home/yblee/workspace/quant/scripts/tqqq/streamlit_rate_spread_lab.py`
- 기존 산출물(항상 유지/생성):
  - `/home/yblee/workspace/quant/storage/results/tqqq_rate_spread_lab_model.csv`
  - `/home/yblee/workspace/quant/storage/results/tqqq_rate_spread_lab_monthly.csv`
  - `/home/yblee/workspace/quant/storage/results/tqqq_rate_spread_lab_summary.csv`

---

# 프롬프트 1: 핵심 기능 구현(동적 spread + softplus + inf 가드 + 메타) + 베이스라인 동일성 검증

> 목표: **동적 funding_spread 지원 + softplus 기반 f(FFR) 동적 스프레드 적용 + rolling corr inf/NaN 가드 + 메타 기록**을 구현한다.  
> 워크포워드는 **프롬프트 2에서** 다룬다.

## 1) 개발 시작 전(필수): 규칙 숙지 + 베이스라인 재현

1. 루트 및 관련 폴더의 `CLAUDE.md`를 먼저 읽고, 작업에 영향을 주는 규칙(파일 저장 규칙/Fail-fast/스키마/구조)을 간단히 메모하라.
2. 아래 스크립트를 “변경 전” 상태로 1회 실행하여 베이스라인 산출물을 확인한다:
   - 실행: `/home/yblee/workspace/quant/scripts/tqqq/streamlit_rate_spread_lab.py`
   - 결과(3개) 생성 확인:
     - `.../tqqq_rate_spread_lab_model.csv`
     - `.../tqqq_rate_spread_lab_monthly.csv`
     - `.../tqqq_rate_spread_lab_summary.csv`
3. 이후 코드 변경 후 동일 조건(고정 float spread)으로 다시 실행했을 때 **핵심 수치가 동일**해야 한다(가능한 방식으로 비교 근거를 남길 것).

## 2) 구현 요구사항 A: funding_spread “동적 입력” 지원(필수)

현재 시뮬레이터/비용 계산이 `funding_spread: float`만 받는 구조라면, 아래 타입을 모두 지원하도록 확장하되 **기존 float 동작은 100% 유지**하라.

### 2.1 지원 타입

- `float` (기존과 동일)
- `dict[str, float]` : 키 `"YYYY-MM"` → 해당 월 spread
- `Callable[[date], float]` 또는 `Callable[[datetime], float]` : 날짜를 넣으면 spread 반환

### 2.2 Fail-fast 규칙(강제)

- dict 모드에서 월 키 누락 시 즉시 `ValueError`
- callable 반환값이 숫자가 아니거나 NaN/inf면 즉시 `ValueError`
- 최종 spread가 `<= 0`이면 즉시 `ValueError`

### 2.3 구현 가이드(권장)

- 로직 중앙화: `_resolve_spread(d, spread_spec) -> float` 같은 유틸로 통일
- `month_key = f"{d.year:04d}-{d.month:02d}"`로 조회

## 3) 구현 요구사항 B: 동적 spread = f(FFR) softplus (필수)

### 3.1 FFR 데이터

- 파일: `/home/yblee/workspace/quant/storage/etc/federal_funds_rate_monthly.csv`
- 단위: ratio (예: `0.0525`)

### 3.2 softplus(수치 안정)

- `softplus(x) = log1p(exp(-abs(x))) + max(x, 0)`

### 3.3 함수 스펙(확정)

- `ffr_pct = 100.0 * ffr_ratio`
- `spread = softplus(a + b * ffr_pct)`
- 제약: spread는 항상 `> 0` (아니면 에러), 출력 clamp(min/max) 금지
- 적용 해상도: **월별 spread 맵(YYYY-MM → spread)** 생성 후 dict 모드로 시뮬레이터에 주입  
  (비용은 거래일(일별)마다 적용하되, 그 날짜가 속한 월의 spread를 참조)

## 4) 구현 요구사항 C: (a,b) 글로벌 튜닝(RMSE 최소화) “기능” 구현(필수)

> 프롬프트 1에서는 “워크포워드”는 제외하지만,  
> **글로벌 최적 (a,b)를 찾는 튜닝 경로**는 구현해 둔다(스트림릿에서 실행 가능해야 함).

- 목적함수: `cumul_multiple_log_diff_rmse_pct` 최소화
- 권장: 2-stage grid search
  - Stage1:
    - `a ∈ [-10.0, -3.0] step 0.25`
    - `b ∈ [0.00, 1.50] step 0.05`
  - Stage2:
    - `a ∈ [a* - 0.75, a* + 0.75] step 0.05`
    - `b ∈ [b* - 0.30, b* + 0.30] step 0.02`
- 평가 함수는 프로젝트 기존 “시뮬→비교→지표산출” 경로를 가능한 재사용
- 성능/시간이 과도하면:
  - 캐싱/재사용(데이터 로딩/정렬) 등으로 최적화하되, 규칙 충돌 시 사용자에게 질문

## 5) 구현 요구사항 D: rolling corr inf/NaN 가드(필수)

- corr 계산 전: 표준편차가 0 또는 매우 작으면 corr = NaN
- corr 계산 후: ±inf를 NaN으로 치환
- 변경 후 summary/시각화가 깨지지 않아야 함

## 6) 메타 기록(필수)

- `meta_manager.py`를 사용해 `/storage/results/meta.json`에 append 기록
- 최소 포함 키:
  - `funding_spread_mode`: `"fixed_float"` / `"softplus_ffr_monthly"`
  - `softplus_a`, `softplus_b`
  - `ffr_scale`: `"pct"`
  - `objective`: `"cumul_multiple_log_diff_rmse_pct"`
  - grid 설정(stage1/stage2 범위/스텝)
  - 산출 파일 경로 목록(기존 3개)

## 7) Streamlit 반영(필수)

- `/scripts/tqqq/streamlit_rate_spread_lab.py`가 아래를 지원해야 한다:
  - 기존 고정 spread(float) 실행 경로 유지(베이스라인 검증용)
  - softplus 동적 spread 모드 실행 경로 추가(글로벌 (a,b) 튜닝 실행 가능)

## 8) 완료 기준(프롬프트 1)

1. **고정 spread(float) 모드**로 실행 시 수정 전과 동일한 결과(핵심 지표 포함)
2. softplus 동적 모드가 실행 가능(글로벌 (a,b) 탐색/선정)
3. rolling corr inf 제거 확인
4. meta.json에 append 기록 확인

## 9) 불명확/충돌 시 질문(필수)

- CLAUDE.md 규칙과 요구사항 충돌
- 기존 3개 CSV 스키마 변경 필요
- 지표 계산 경로 재사용 불가/애매
  → 위 상황에서는 추측하지 말고 사용자에게 질문하고 답을 받은 뒤 진행

---

# 프롬프트 2: 워크포워드(60m train / 1m test) 구현 + 산출물/리포트 + 성능/시간 최적화

> 목표: 프롬프트 1에서 구현된 동적 spread/softplus/글로벌 튜닝 기반 위에  
> **워크포워드 검증(60개월 학습, 1개월 테스트)**을 구현하고 CSV 산출물을 생성한다.  
> **중요:** 사용자 요구로 인해, Streamlit에서 “토글/버튼” 없이 **기본 실행 시 워크포워드를 무조건 실행**하도록 반영한다.

## 0) 시작 단계(필수): 현재 repo 상태 점검(추측 금지)

- 이 프롬프트는 프롬프트 1이 “이미 적용된 상태”일 수 있지만 세션 분리로 보장되지 않는다.
- 따라서 다음을 repo에서 직접 확인하라:
  1. `funding_spread`가 float + dict + callable을 지원하는지
  2. softplus 기반 월별 spread 생성 및 적용이 가능한지
  3. rolling corr inf/NaN 가드가 적용되어 있는지
  4. `meta_manager.py`를 통한 meta.json append 기록이 가능한지
- 만약 (1)~(4)가 구현되어 있지 않다면, **프롬프트 1 요구사항을 먼저 최소 범위로 재구현**한 후 진행하라.  
  (단, 중복 구현/불필요 변경을 피하고, 기존 코드와 충돌 시 사용자에게 질문)

## 1) 워크포워드 설정(확정)

- Train window: 60개월(5년)
- Test step: 1개월
- 매 테스트 월마다:
  - 직전 60개월로 (a,b) 튜닝
  - 다음 1개월(테스트 월) 적용
  - 테스트 RMSE 산출(`cumul_multiple_log_diff_rmse_pct`)
- 전제(A안 확정): 워크포워드에서도 **테스트 월 spread 계산에 해당월 FFR(월값)**을 사용  
  (미래예측 OOS가 아니라 파라미터 안정성/일반화 체크 목적)

## 2) 워크포워드 튜닝 방식(실행시간 고려, 필수)

워크포워드에서 매월 “2-stage 전체 그리드”는 매우 비쌀 수 있다.  
아래 정책을 기본으로 구현하라(규칙 충돌 시 사용자에게 질문):

- 첫 워크포워드 구간:
  - 프롬프트 1의 2-stage grid search로 (a,b) 탐색
- 이후 구간(월별 반복):
  - 직전 월 최적 (a_prev, b_prev) 주변에서 **국소 탐색(local refine grid)**을 수행
  - 권장 범위:
    - `a ∈ [a_prev-0.50, a_prev+0.50] step 0.05`
    - `b ∈ [b_prev-0.15, b_prev+0.15] step 0.02`
- 단, 국소 탐색 정책/범위를 메타에 기록할 것

## 3) 워크포워드 시작/정책(Fail-fast 포함)

- 워크포워드 시작점은 “60개월 학습이 가능한 첫 달”부터 자동 시작
- 그 외 결측/누락/NaN/inf는 즉시 예외(Fail-fast)
- 정상적으로 시작/종료 가능한 기간 및 테스트 월 리스트를 명확히 산출물에 남길 것

## 4) 산출물(필수)

기존 3개 CSV는 유지하며, 워크포워드 결과를 추가 파일로 저장한다.

- `/home/yblee/workspace/quant/storage/results/tqqq_rate_spread_lab_walkforward.csv`
- `/home/yblee/workspace/quant/storage/results/tqqq_rate_spread_lab_walkforward_summary.csv`

### 4.1 walkforward.csv 권장 컬럼(가능하면 고정)

- `train_start`, `train_end`
- `test_month` (YYYY-MM)
- `a_best`, `b_best`
- `train_rmse_pct`, `test_rmse_pct`
- (권장) `n_train_days`, `n_test_days`
- (선택) `search_mode` (예: "full_grid_2stage" / "local_refine")

### 4.2 walkforward_summary.csv 권장

- 테스트 RMSE 요약: 평균/중앙값/표준편차/최댓값/최솟값
- 글로벌 최적 (a,b) (가능하면 함께 계산/기록) 대비 워크포워드 요약 비교

## 5) 메타 기록(필수)

- `/storage/results/meta.json`에 append 기록
- 최소 포함 키:
  - `funding_spread_mode`: `"softplus_ffr_monthly"`
  - 워크포워드 설정: `train_window_months=60`, `test_step_months=1`
  - “테스트 월에도 해당월 FFR 사용” 명시
  - 튜닝 정책(첫 구간 2-stage, 이후 local refine 범위/step)
  - 워크포워드 산출물 경로 2개

## 6) Streamlit 반영(필수, 사용자 요구로 변경됨)

- `/scripts/tqqq/streamlit_rate_spread_lab.py` 실행 시, **워크포워드를 기본적으로(항상) 실행**하도록 반영하라.
- 토글/버튼/체크박스 등 “워크포워드 실행 여부 선택 UI”는 구현하지 말 것.
- 단, 실행시간이 매우 길어 UX/개발이 현실적으로 곤란해지고, `CLAUDE.md` 규칙 또는 기존 사용 패턴과 충돌이 발생한다면:
  - 반드시 사용자에게 질문하고 정책을 합의한 뒤 진행(추측 금지).

## 7) 완료 보고(필수)

아래를 텍스트로 요약해 보고하라:

1. 워크포워드 테스트 RMSE 요약(평균/중앙값/표준편차/최댓값/최솟값)
2. 월별 (a,b) 값이 얼마나 변하는지(안정성 코멘트)
3. 실행시간(대략) 및 local refine 정책 효과
4. 산출물 생성/경로 확인
5. meta.json 기록 항목 요약

## 8) 불명확/충돌 시 질문(필수)

- CLAUDE.md 규칙과 요구사항 충돌
- 워크포워드 산출물 스키마/경로 변경 필요
- 실행시간이 과도하여 정책 변경이 필요
  → 위 상황에서는 추측하지 말고 사용자에게 질문하고 답을 받은 뒤 진행
