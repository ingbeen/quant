# Implementation Plan: QLD 일별 비교 연결과 TQQQ · QLD 시가 · 고가 · 저가 · 종가

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-31 23:04
**마지막 업데이트**: 2026-11-01 00:09
**관련 범위**: tqqq(시뮬레이션 · 상수 · 로더 · 차트), scripts/tqqq, scripts/data, tests, docs
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md, docs/CLAUDE.md, docs/COMMANDS.md

---

## 1) 목표(Goal)

- [x] 목표 1: `generate_daily_comparison.py` 가 TQQQ · QLD 일별 비교 CSV 를 함께 만든다 (새 스크립트 없음)
- [x] 목표 2: `app_daily_comparison.py` 에서 상품과 가격 종류(시가 · 고가 · 저가 · 종가)를 골라 실제 대 시뮬을 본다
- [x] 목표 3: `simulate` 의 고가 · 저가를 기초 자산의 장중 고가 · 저가로 계산한다
- [x] 목표 4: TQQQ CSV 의 기존 10개 열과 `simulate` 의 시가 · 종가는 코드 변경으로 한 값도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- `QLD_synthetic_max.csv`(상장 전 시뮬레이션 + 상장 후 실물) 생성 — 읽을 코드가 없다 (사용자 결정 2026-10-31)
- QLD 전용 운용보수 파일 도입 — TQQQ 보수 유지 (사용자 결정 2026-10-31)
- 스프레드 a · b 재튜닝, 튜닝 스크립트 복원
- 스프레드 랩 앱 화면 변경, `qbt/tqqq` 패키지 · 결과 폴더 이름 변경
- `TQQQ_synthetic_max.csv` · `QLD_proxy_max.csv` 등 대용 · 합성 시세 재생성과 `run_*` 러너 재실행 — **결정 대기, 추천안 기준으로 적었다** (Notes 「결정 대기」)
- 시가 · 고가 · 저가의 정확도 지표를 화면 · CSV 에 추가 — 실측은 보고서에 남긴다
- TQQQ 와 QLD 를 나란히 놓는 화면 — 「비교」는 실제 대 시뮬 비교로 해석했다
- SSO 등 다른 레버리지 ETF 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 일별 비교 스크립트와 대시보드가 TQQQ 로 고정돼 있어 QLD 의 추적 오차(RMSE · 누적배수 로그차이 추이 · 일일 오차 분포)를 볼 수 없다.
- 일별 비교 CSV 와 화면에 종가만 있다. 사용자가 두 상품 모두 시가 · 고가 · 저가 · 종가를 요청했다.
- **시뮬레이션의 고가 · 저가는 지금 실제 장중 값이 아니다.** `simulation.py:393-394` 가 `max(시가, 종가)` · `min(시가, 종가)` 로 채워, 장중 고가 · 저가가 시가 · 종가 밖으로 나간 부분(꼬리)이 전 행에 없다. 실물은 TQQQ 100%, QLD 99.88% 의 날에 있다. 그대로 비교하면 고가 · 저가 열은 검증 의미가 없다.
- QLD 2배 합성 자체는 이미 있다: `generate_long_proxy_series.py` 의 `QLD_proxy_max.csv`. `app_proxy_comparison.py` 는 상관 · CAGR · MDD 만 보여 준다.
- 스크립트 경로만 QLD 로 바꾸면 실패한다: `create_expense_dict` 는 2010-02 부터라 `Expense 데이터 부족: 2006-06 이전의 Expense 데이터가 존재하지 않습니다.` 로 멈춘다. `build_extended_expense_dict` 가 필요하다.

### 실측 근거 — 종가 추적 (2026-10-31 23:04, 커밋 `c8d7007` 의 시세 — QLD · QQQ · TQQQ 끝 2026-10-29, 저장소 파일 변경 없이 측정)

| | TQQQ (3배) | QLD (2배, 기존 모델 그대로) |
|---|---|---|
| 기간 | 2010-02-11 ~ 2026-10-29 | 2006-06-21 ~ 2026-10-29 |
| 거래일 | 4,205 | 5,122 |
| 누적배수 로그차이 RMSE | 1.0243% | 0.8083% |
| 평균 | 0.8416% | 0.6398% |
| 최대 (날짜) | 5.4299% (2020-03-16) | 3.9293% (2008-04-17) |
| 마지막 날 signed | -0.3089% | -0.5611% |
| 일일수익률 절대차이 평균 | 0.094 | 0.1067 |
| 마지막 날 종가 실제 / 시뮬 | 69.26 / 69.0464 | 88.74 / 88.2435 |

- QLD, TQQQ 와 같은 기간(2010-02-11 ~): RMSE 0.8991%
- QLD 보수 0.95% 고정: RMSE 0.8274%, 마지막 날 signed -0.9691%
- a · b 격자 9,211칸(a -9.0 ~ -3.0, b 0 ~ 1.5) 최저: RMSE 0.7617% (a -5.9, b 0.31, 전 기간에 맞춘 값) — 현행보다 0.0466%p
- TQQQ 를 `create_expense_dict` · `build_extended_expense_dict` 로 각각 돌린 결과: 4,205행 중 다른 종가 0행

### 실측 근거 — 시가 · 고가 · 저가 (2026-10-31 23:27, 같은 시세)

**고가 · 저가 후보식**: `전날 시뮬 종가 × (1 + (기초 고가 또는 저가 ÷ 기초 전날 종가 − 1) × 배율)`. 시가에 이미 쓰는 식과 같다. 펀드의 장중 노출은 전날 종가에 고정되므로 장중 가치는 기초 자산에 선형이고, 기초의 고가 · 저가 시점이 곧 펀드의 고가 · 저가다.

전날 실제 종가에서 출발한 한 날치 예측과 실제의 차이다 (전날 실제 종가 대비 %p, RMSE):

| | TQQQ | QLD |
|---|---|---|
| 시가 (기존 식) | 0.1818 | 0.2415 |
| 종가 (비용 제외) | 0.1862 | 0.2484 |
| 고가 현행 → 후보 | 1.3115 → 0.2761 | 1.0067 → 0.2561 |
| 저가 현행 → 후보 | 1.6753 → 0.4209 | 1.2183 → 0.3356 |
| 후보, 괴리 상위 3일 뺀 고가 / 저가 | 0.2302 / 0.2116 | 0.23 / 0.2193 |

- 저가의 큰 괴리는 2015-08-24 다: 기초 QQQ -17.25%, 실물 TQQQ -28.96%, 실물 QLD -17.32% — ETF 시세가 장중에 왜곡된 날이라 고치지 않고 기록한다.
- **후보식 그대로면 저가가 시가 · 종가보다 높은 날이 있다**: TQQQ 16행, QLD 30행, 초과는 최대 0.04648%, 0.03083%. 일일 비용을 종가에서만 빼기 때문이다 (고가 쪽은 0행). → `고가 = max(후보, 시가, 종가)`, `저가 = min(후보, 시가, 종가)` 로 맞춘다.
- **0 이하 위험 없음**: 전 구간 최저 비율 QQQ 3배 0.4826, QQQ 2배 0.6551 (둘 다 2015-08-24), SPY 2배 0.7627 (2020-03-16), 0 이하 0행.

### 재사용 함수 호출처 (정의 · 주석 · 테스트 제외, `src` · `scripts` grep)

| 함수 | 실제 호출 |
|---|---|
| `simulate` | 3곳 (`generate_daily_comparison` · `generate_synthetic` · `generate_long_proxy_series` — 마지막은 이미 배율 2), 테스트 21곳 |
| `calculate_validation_metrics` | 1곳 (`generate_daily_comparison`) |
| `build_extended_expense_dict` | 2곳 (`generate_synthetic` · `generate_long_proxy_series`) |
| `load_comparison_data` | 2곳 (`app_daily_comparison` · `app_rate_spread_lab`) |
| `create_price_comparison_chart` | 1곳 (`app_daily_comparison`), 테스트 2곳 |
| 히스토그램 · 로그차이 차트 | 각 1곳 (`app_daily_comparison`) |

**고가 · 저가를 읽는 곳**: `csv_export.py`(signal CSV 의 `high_pct` · `low_pct`) · `runners.py:168`(보유 전략 signal 표) · `dashboard_charts.py`(캔들) · `run_walkforward.py:237`(내보내기) · `proxy_series.py`(스케일 · 바스켓). 엔진 · 전략의 매매 계산은 쓰지 않는다 — CAGR · MDD 는 이 변경으로 바뀌지 않는다.

`scripts/` 를 import 하는 테스트는 0건이다 — 스크립트 변경은 pytest 로 잡히지 않으므로 Phase 2 의 실행 대조로 검증한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」, 「가격 반올림 자릿수」, `docs/MEMORY.md`
- `src/qbt/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`
- `tests/CLAUDE.md`, 전역 `~/.claude/rules/python.md`, `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `tqqq_daily_comparison.csv` 의 기존 10개 열이 변경 전 코드의 기준값과 전 행 같다
- [x] 두 CSV 에 시가 · 고가 · 저가의 실제 · 시뮬 열이 있고, 실제 열은 `TQQQ_max.csv` · `QLD_max.csv` 를 반올림한 값과 같다
- [x] 시뮬 고가 ≥ max(시가, 종가), 시뮬 저가 ≤ min(시가, 종가) 가 두 CSV 전 행에서 성립한다
- [x] `qld_daily_comparison.csv` 행 수가 `QLD_max.csv` 행 수와 같고, 종가 지표가 Context 의 실측과 일치한다 (시세가 그대로일 때)
- [x] 시뮬 시가 · 고가 · 저가의 한 날치 RMSE 가 Context 실측의 후보값과 일치한다 (맞춘 저가 · 고가 기준으로 다시 잰다)
- [x] 대시보드에서 상품과 가격 종류를 고를 수 있고 제목 · 범례 · 문구가 선택을 따른다
- [x] 회귀/신규 테스트 추가 (고가 · 저가 계산과 불변식, 차트 라벨 · 가격 종류, 상품 표 계약, 보수 파일보다 먼저 상장한 상품, CSV 새 열)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 (`docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md`)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (`docs/research/전략_검증_보고서.md` §49 에 실측과 탈락안)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」) → **해당 없음** — 고치지 않은 지적은 전부 거르는 기준에 들었다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/simulation.py` — `simulate`: 필수 열에 고가 · 저가 추가, 고가 · 저가를 후보식으로 계산하고 시가 · 종가로 맞춤. `_save_daily_comparison_csv`: 시가 · 고가 · 저가의 실제 · 시뮬 6개 열 추가 (`ROUND_PRICE`)
- `src/qbt/tqqq/constants.py` — 새 열 `COL_*`, 가격 종류 표(이름 → 실제 · 시뮬 열), `QLD_DAILY_COMPARISON_PATH`, `LEVERAGE_2X`, 상품 표 `DAILY_COMPARISON_TARGETS` (이름 · 실물 시세 · 배율 · CSV)
- `src/qbt/tqqq/data_loader.py` — `COMPARISON_COLUMNS` 에 6개 열 추가
- `src/qbt/tqqq/visualization.py` — `create_price_comparison_chart(df, product_name, price_kind)`: 하드코딩된 TQQQ · 종가를 인자로. 기본값을 두지 않는다 — 빠뜨린 호출이 조용히 TQQQ 종가로 표시되지 않게
- `scripts/tqqq/generate_daily_comparison.py` — 상품 표를 도는 반복문, `build_extended_expense_dict` 로 교체, 로그 · docstring
- `scripts/tqqq/app_daily_comparison.py` — 상품 선택과 가격 종류 선택 `st.radio`(`app_proxy_comparison.py` 의 관용, 가격 기본값은 종가), 제목 · 문구 · 데이터 소스를 선택에 맞춤. 「운용보수와 스프레드는 두 상품 모두 TQQQ 기준」 안내 — 숫자를 적지 않고 상수의 파일 이름을 참조
- `scripts/data/generate_long_proxy_series.py` — 자체 `LEVERAGE_2X` 를 constants 에서 가져온다 (상수 중복 금지, 값 동일)
- `tests/qbt/test_tqqq_simulation_core.py` — 근사값을 고정하던 `test_high_low_approximation_for_synthetic_data` 를 새 계약으로 교체, 픽스처에 고가 · 저가 추가
- `tests/qbt/test_integration.py`, `tests/qbt/test_tqqq_simulation_outputs.py`, `tests/qbt/test_tqqq_data_loader.py`, `tests/qbt/test_tqqq_visualization.py`, `tests/qbt/test_tqqq_simulation_cost_model.py`
- `README.md` — 기능 소개 줄을 TQQQ · QLD 로
- `scripts/CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md` (시뮬레이션 규칙에 고가 · 저가 식과 맞춤의 이유)
- `docs/research/전략_검증_보고서.md` — §49 하위에 QLD 추적 · 시고저 검증 절 추가 (계획서 규약: 설계 결정 · 탈락안의 자리)
- `docs/COMMANDS.md`: **변경 있음** — 워크플로우 2 의 제목 · 선행 시세(QLD) · 출력 · 대시보드 필요 파일, 「다시 돌리는 순서」 ⑤ 설명. 실행 명령과 CLI 옵션은 그대로

**바꾸지 않는 것**: `simulate` 의 시가 · 종가 계산, `calculate_validation_metrics` 의 지표, `generate_synthetic.py`, `app_rate_spread_lab.py`

### 데이터/결과 영향

- 신규: `storage/results/tqqq/qld_daily_comparison.csv` — 16개 열, 인코딩은 TQQQ CSV 와 같다(같은 저장 함수)
- 갱신: `storage/results/tqqq/tqqq_daily_comparison.csv` — 6개 열 추가. 끝이 2026-09-24 → 2026-10-29 로 늘고 과거 행도 달라지는 것은 **코드가 아니라 커밋 `c8d7007` 의 시세 때문이다.** Phase 0 기준값으로 코드 영향이 0 임을 분리한다
- 스프레드 랩 앱은 같은 경로의 TQQQ CSV 를 읽고 쓰는 열이 그대로다. 로더의 필수 열이 늘어 **새 CSV 가 필요하다** — 같은 커밋에 재생성본이 들어간다
- 다음 재생성 때 `TQQQ_synthetic_max.csv` · `SSO_proxy_max.csv` · `QLD_proxy_max.csv` 의 고가 · 저가만 바뀐다(실물 구간 제외, 시가 · 종가 불변). TQQQ 보유 전략 대시보드의 상장 전 캔들에 꼬리가 생기고 signal CSV 의 `high_pct` · `low_pct` 가 바뀐다. 성과 지표는 그대로다
- 작업 트리는 `c8d7007` 기준 깨끗하다 — 이 작업의 diff 에는 이 계획이 만든 변경만 남는다

## 6) 단계별 계획(Phases)

### Phase 0 — 기준값 확보와 계약 테스트(레드)

**작업 내용**:

- [x] 변경 전 코드로 `generate_daily_comparison.py` 를 실행하고 `tqqq_daily_comparison.csv` 사본을 scratchpad 에 기준값으로 둔다
- [x] 변경 전 `simulate` 의 시가 · 종가를 TQQQ · QLD 전 구간으로 뽑아 scratchpad 에 기준값으로 둔다
- [x] `test_tqqq_simulation_core.py` — 고가 · 저가 손계산 값, 장중 꼬리가 시뮬에 반영됨, 저가가 종가 위로 나가는 날은 몸통으로 맞춤, 첫날은 시작 가격, 고가 · 저가 열이 없으면 `ValueError`, 결측은 메우지 않음
- [x] `test_tqqq_visualization.py` — 인자로 준 상품 이름 · 가격 종류가 범례 2개와 제목에 들어가고 해당 열을 그린다
- [x] `test_tqqq_simulation_outputs.py` — `DAILY_COMPARISON_TARGETS` 계약(배율 `{"TQQQ": 3.0, "QLD": 2.0}` 숫자 고정, CSV 경로가 서로 다름), CSV 새 6개 열과 자릿수
- [x] `test_tqqq_simulation_cost_model.py` — 보수 파일보다 먼저 상장한 상품: `create_expense_dict` 는 `ValueError`, `build_extended_expense_dict` + 배율 2 는 손계산 종가와 일치
- [x] 기존 픽스처(`test_tqqq_simulation_core.py`, `test_integration.py`, `test_tqqq_simulation_outputs.py`, `test_tqqq_data_loader.py`)에 필요한 열 추가

**Validation**:

- [x] 새 계약 테스트가 구현 전이라 실패하는 것을 확인한다 (특정 파일 `pytest`)
- [x] 보수 테스트는 기존 함수 조합을 고정하므로 바로 통과한다 — 확장값을 일부러 바꿔 실패를 본 뒤 되돌린다 (`PYTHONDONTWRITEBYTECODE=1`)

---

### Phase 1 — 구현(그린 유지)

**작업 내용**:

- [x] `simulation.py` 고가 · 저가 계산과 CSV 열
- [x] `constants.py` · `data_loader.py` 추가, `generate_long_proxy_series.py` 의 상수 이전
- [x] `visualization.py` 인자
- [x] `generate_daily_comparison.py` 반복문과 보수 함수 교체
- [x] `app_daily_comparison.py` 상품 · 가격 종류 선택과 문구

**Validation**:

- [x] Phase 0 테스트 파일 전부 통과 (특정 파일 `pytest`)

---

### Phase 2 — 실행 대조

**작업 내용**:

- [x] 변경 후 `generate_daily_comparison.py` 실행 — 대체 시세 · 러너는 돌리지 않는다
- [x] 일회성 화면 코드 확인: `streamlit.testing.v1.AppTest` 로 scratchpad 에서 두 상품 × 가격 종류 4개를 돌려 예외 0건과 제목 · 최종 종가를 확인한다. 서버 · 포트를 쓰지 않고 저장소 테스트로 넣지 않는다 (저장소의 AppTest 사용 0건, 사용자 승인 2026-10-31)

**Validation**:

- [x] TQQQ CSV 의 기존 10개 열이 Phase 0 기준값과 전 행 같다 (열 이름으로 대조)
- [x] `simulate` 의 시가 · 종가가 Phase 0 기준값과 전 행 같다 (TQQQ · QLD)
- [x] 두 CSV 의 실제 시가 · 고가 · 저가를 원본 시세의 반올림 값과 대조한다
- [x] 두 CSV 의 전 행에서 시뮬 고가 · 저가 불변식을 확인한다
- [x] QLD CSV 행 수와 `QLD_max.csv` 행 수를 따로 세어 맞춘다
- [x] QLD CSV 를 다시 읽어 RMSE · 평균 · 최대 · 마지막 날 값을 Context 실측과 대조한다
- [x] 시뮬 시가 · 고가 · 저가의 한 날치 RMSE 를 다시 재어 Context 표와 대조한다
- [x] `git status` — Scope 밖 변경 0건

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 업데이트: `docs/COMMANDS.md`(변경 있음) · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md`
- [x] 근거 승격: `docs/research/전략_검증_보고서.md` §49 에 종가 · 시고저 실측 표, 재튜닝 · 보수 · 근사 유지의 탈락 근거, 2015-08-24 왜곡, 상장 전 구간은 대조 불가라는 한계
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] 사용자용 대시보드 확인 안내: 실행 명령과 볼 지점 (AI 는 띄우지 않는다)
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 14건 — 버그 7 [무거움 5 · 가벼움 2] · 그 외 7 · 조치: 5건 수정 — 음수 저가 멈춤 · 표 계약 파일 고정 · 맞춤 분기 테스트 · 시가 · 종가 불변 정확 대조 · 테스트 타입 오류)
- [x] `/code-review xhigh` **2회차** (발견 12건 — 버그 7 [무거움 2 · 가벼움 5] · 그 외 5 · 조치: 없음, 고칠 것 0. 무거움 2 는 닿지 않음)
- [x] 수정분 검증 — 해당 없음 (마지막 회차에 고친 것 없음)
- [x] `poetry run python validate_project.py` (passed=925, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. TQQQ시뮬레이션 / QLD 일별 비교 연결과 시가 · 고가 · 저가 · 종가 비교 추가
2. TQQQ시뮬레이션 / 일별 비교 CSV · 대시보드의 TQQQ · QLD 확장과 시뮬 고가 · 저가의 기초 자산 장중 값 기반 계산
3. TQQQ시뮬레이션 / 시뮬 고가 · 저가를 시가 · 종가 복사본에서 기초 자산 장중 값 기반으로 변경, QLD 일별 비교 추가
4. TQQQ시뮬레이션 / 새 스크립트 없이 generate_daily_comparison · app_daily_comparison 에 QLD 와 가격 종류 선택 추가, §49.4 실측 기록
5. TQQQ시뮬레이션 / QLD 추적 검증 — 기존 비용 모델 유지(RMSE 0.8083%)와 시가 · 고가 · 저가 일별 비교 · 0 이하 가격 멈춤 추가

## 7) 리스크(Risks)

- **공유 함수 `simulate` 변경** — 호출 스크립트 3곳과 테스트 21곳에 닿는다. 완화: 시가 · 종가를 기준값과 전 행 대조, 고가 · 저가는 매매 계산이 읽지 않음을 grep 으로 확인했다
- **합성 · 대체 파일과 코드의 일시적 불일치** — 재생성 전까지 저장된 파일의 고가 · 저가는 근사값으로 남는다. 완화: `docs/COMMANDS.md` 의 재실행 순서를 돌릴 때 함께 반영되고, 그전에도 성과 지표에는 영향이 없다
- **다른 PC 의 옛 일별 비교 CSV** — 필수 열이 늘어 옛 CSV 는 로더가 `ValueError` 로 멈춘다. 메시지에 빠진 열이 나오고, 재생성본이 같은 커밋에 들어간다
- **TQQQ 결과 회귀** — 보수 함수 교체와 반복문 때문. 완화: Phase 0 기준값과 열별 대조
- **장중 왜곡일의 큰 괴리** — 2015-08-24 시뮬 저가가 실물보다 크게 낮다(후보식이 기초 QQQ 의 저가를 그대로 배율로 키운다). 고치지 않고 기록한다
- **거래 마감 시각 차이와 호가 왜곡** — 실물 ETF 는 장중 값이 순자산가치와 벌어질 수 있어 고가 · 저가 오차는 시가 · 종가보다 크다. 완화: 표로 기록하고 판단은 사용자가 화면에서 한다
- **부분 저장** — QLD 계산이 실패하면 TQQQ CSV 만 새로 저장된 채 종료 코드 1 로 끝난다. 실패가 드러나고 재실행으로 복구되므로 원자적 저장을 만들지 않는다
- **QLD CSV 가 없을 때** — 앱은 TQQQ 와 같이 `FileNotFoundError` 를 낸다. 경로가 메시지에 나오고 결과 CSV 는 git 이 추적하므로 별도 안내를 두지 않는다
- **QLD 입력이 사실과 다름** — 최근 운용보수가 공시(`Net Expense Ratio* 0.95%`, ProShares 팩트시트 2026-09-30 기준)보다 0.13%p 낮다. 사용자가 합성 시세와 같은 입력을 택했다. 완화: 화면 안내와 보고서 기록
- **상장 전 구간은 이 검증으로 보장되지 않는다** — 대조 실물이 없다(1999-03-10 ~ 2006-06-20). 완화: 보고서 기록
- **검증 중 시세 재다운로드** — 실측 대조가 깨진다. 완화: 작업 중 `download_data.py` 를 돌리지 않는다. 시세가 바뀌면 대조 기준을 다시 잰다
- **격자 최저값은 전 기간에 맞춘 값** — 재튜닝 탈락의 근거로만 쓰고 모델 성능으로 인용하지 않는다

## 8) 메모(Notes)

### 결정

- 2026-10-31 사용자 결정: 이어 붙인 QLD 시세를 만들지 않는다, TQQQ 운용보수를 유지한다, `AppTest` 일회성 확인을 넣는다 (보고한 추천안 채택)
- 2026-10-31 사용자 요청: TQQQ · QLD 모두 시가 · 고가 · 저가 · 종가를 갖춘다 — 이 요청으로 범위를 넓혔다
- **`simulate` 를 바꾼다** — 앞선 판의 「바꾸지 않는 것」을 뒤집었다. 시뮬 고가 · 저가가 시가 · 종가의 복사본이라 그대로 내면 비교가 무의미하다. 탈락안: ① 근사값 유지(고가 RMSE 1.3115, 꼬리 0) ② 일별 비교에서만 따로 계산(시뮬 고가 · 저가의 정의가 둘이 된다)
- 재튜닝 안 함: 개선 0.0466%p, 튜닝 스크립트는 저장소에 없다(복원 지점 `c81690b^`) — 「기존 스크립트 활용」 조건과 충돌
- 인자 없이 두 상품을 항상 함께 생성 — 두 CSV 의 시세 기준일이 어긋나지 않는다
- 상품 · 가격 선택은 보고 때의 선택 상자 대신 `st.radio` — 항목이 적어 항상 보이고, `app_proxy_comparison.py` 관용과 같다
- 화면은 캔들이 아니라 선택한 가격의 실제 대 시뮬 선 차트 — 두 시리즈를 겹쳐 대조하는 기존 차트의 목적을 유지한다

- 2026-10-31 사용자 결정: `simulate` 의 고가 · 저가를 바꾼다, 합성 · 대체 파일은 이번에 다시 만들지 않는다 (Non-Goals 의 「결정 대기」 항목도 이 결정으로 닫혔다)

### 계획서 자체 검증 (2026-10-31)

| 회차 | 각도 | 결과 |
|---|---|---|
| 1 | 논리 · 누락 | 스크립트를 import 하는 테스트 0건 → 실행 대조와 기준값을 넣음. 두 상품이 같은 경로를 쓰면 조용히 덮어쓰므로 표 계약 테스트 추가 |
| 2 | 다른 로직 영향 | `src/qbt/CLAUDE.md:47`, `docs/COMMANDS.md:200` 언급을 문서 범위에 추가. 대체 시세를 다시 만들지 않음을 비목표로 명시 |
| 3 | 오류 · 동시성 | 부분 저장과 CSV 부재를 위험으로 기록 — 드러나는 실패라 코드를 늘리지 않음 |
| 4 | 단순화 | 개선 없음 |
| 5 | 사용자 조건(새 스크립트 없음, 대시보드는 사용자 실행) | 개선 없음 |
| 6 | 문서 · 근거 승격 | 개선 없음 — 연속 3회 개선 없어 종료 |
| 7 | 범위 확대 — 식의 불변식 | 후보식 그대로면 저가가 몸통 위로 나가는 날이 있음(16 · 30행) → 맞춤을 계획에 넣음. 0 이하 위험은 전 구간에서 0행 |
| 8 | 범위 확대 — 결측 정책 | `max(axis=1)` 기본값은 결측을 건너뛰어 시세를 메우는 꼴이 된다 → 첫날만 시작 가격으로 두고 나머지 결측은 그대로 남기는 테스트를 넣음 (시가의 기존 정책과 같음) |
| 9 | 범위 확대 — 로더 · 다른 앱 | 필수 열이 늘어 옛 CSV 가 멈춤 → 위험 기록, 스프레드 랩 앱이 같은 CSV 를 읽는 점 확인 |
| 10 | 범위 확대 — 단순화 | 개선 없음 |
| 11 | 범위 확대 — 사용자 조건 | 개선 없음 |
| 12 | 범위 확대 — 근거 승격 | 개선 없음 — 연속 3회 개선 없어 종료 |

### 진행 로그 (KST)

- 2026-10-31 23:04: 앞서 쓴 계획서가 폴더에서 사라져 사용자 요청으로 다시 작성. 커밋 `c8d7007` 시세로 실측을 다시 재어 모든 값이 같음을 확인, 작업 트리 상태 서술만 갱신. 승인 대기
- 2026-10-31 23:27: 사용자 요청으로 시가 · 고가 · 저가 · 종가 범위 추가. 시뮬 고가 · 저가가 근사값임을 실측으로 확인하고 `simulate` 변경을 계획에 넣음. 승인 대기
- 2026-10-31 23:33: 사용자 승인 — 「추천대로」. Phase 0 착수
- 2026-10-31 23:33: Phase 0 기준값 확보 — TQQQ CSV 4,205행, `simulate` 전 열 TQQQ 4,205 · QLD 5,122 · QQQ 3배 전 구간 6,954행 (scratchpad)
- 2026-10-31 23:33 ~ 23:39: 레드 확인 — 상수 없는 3개 파일 수집 실패, 나머지에서 새 계약 5건 실패 · 46건 통과. 보수 테스트는 확장값을 0.0195 로 바꿔 1건 실패를 본 뒤 되돌림 (사본과 같은 값 확인)
- 2026-10-31 23:33 ~ 23:39: 그린 — 영향받는 테스트 파일 6개 104건 통과. `test_integration.py` 는 픽스처가 이미 고가 · 저가를 가져 고칠 것이 없었다 (Scope 예상과 다름)
- 2026-10-31 23:39: 실행 대조 — TQQQ 기존 10개 열 글자까지 일치(4,205행). 시가 · 종가 전 행 동일(TQQQ · QLD · QQQ 3배 전 구간), 고가 · 저가는 각 4,164 · 4,148 / 5,068 · 5,040 / 6,870 · 6,819 행 변경. 실제 시가 · 고가 · 저가 · 종가와 원본 반올림 최대 차 0.0. 시뮬 고가 · 저가 불변식 위반 0행, 꼬리 있는 행 0.9998. QLD 5,122행 = `QLD_max.csv` 5,122행, RMSE 0.8083 · 평균 0.6398 · 최대 3.9293 · 마지막 -0.5611. 한 날치 RMSE 시가 · 고가 · 저가 TQQQ 0.1818 · 0.2761 · 0.4209, QLD 0.2415 · 0.2561 · 0.3356
- 2026-10-31 23:40: AppTest — 두 상품 × 가격 4종 예외 0건, 최종 종가 TQQQ $69.26 / $69.05, QLD $88.74 / $88.24, 차트 3개. 첫 시도는 확인 스크립트의 상대 경로 때문에 앱이 실행되기 전에 실패해 절대 경로로 고쳐 다시 돌렸다. streamlit 상주 프로세스 0개
- 2026-10-31 23:40 ~ 23:56: 리뷰 1회차 수정. 모양과 찾은 자리 수 — 입력이 가격을 0 이하로 만듦 1곳(저가가 시가 · 종가 이하라 검사 하나로 덮음), 표 계약이 칸 일부만 고정 1곳, 픽스처가 맞춤 분기에 못 닿음 1곳, 허용오차로 「값까지 같다」를 대조 1곳, 테스트 타입 미좁힘 1곳(5줄)
- 2026-10-31 23:56: 보강 검사 변형 확인 — 9가지 모두 실패를 보고 되돌림(저가 검사 제거 2건 실패 · 고가 맞춤 제거 1 · 고가 맞춤에서 시가 제거 1 · 저가 맞춤에서 시가 제거 1 · 저가 맞춤에서 종가 제거 3 · 고가의 시가 유입 5 · QLD 시세 TQQQ 로 1 · QLD CSV 겹침 1 · QLD 배율 3 1). 되돌린 뒤 사본과 일치, 수정 전후 `simulate` 출력 바이트 동일, 재실행 대조 통과
- 2026-11-01 00:07: 품질 검증 passed=925, failed=0, skipped=0
- 2026-11-01 00:09: `/commit` 후보를 옮기고 Done 처리
- 2026-11-01 00:09: 고치지 않은 지적 처리 — 옮긴 항목 없음. 거른 지적(기준 번호): 저장 때 시가 · 고가 · 저가 열이 없으면 KeyError(2) · 운용보수 파일 앞 행이 지워지면 TQQQ 도 멈추지 않음(1, 근거: 파일 이력 6개 커밋 모두 첫 달 2010-02, 갱신은 끝에 붙이기뿐) · 고가 · 저가 결측이 저장까지 감(1, 근거: 호출처 3곳 모두 `load_stock_data` 를 거쳐 결측이 들어오지 않음) · QLD CSV 부재 시 날것의 예외(2) · QLD 시세 실패 시 부분 저장(2, 계획서가 받아들임) · 옛 CSV 메시지에 재생성 안내 없음(2) · 0 이하 오류 문구가 저가만 지목(2) · 툴팁 소수 2자리(3) · 화면 안내에 고정값 구간 미표기(3) · 낡은 주석 · docstring(3) · 부동소수점 `==`(3) · 주석 문체(3) · §49.4 재현 문구의 범위(3) · 계획서 자기 서술(3)

---
