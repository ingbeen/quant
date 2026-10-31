# Implementation Plan: QLD 일별 비교를 기존 검증 · 대시보드에 연결

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-31 23:04
**마지막 업데이트**: 2026-10-31 23:04
**관련 범위**: tqqq(상수 · 차트), scripts/tqqq, scripts/data, tests, docs
**관련 문서**: src/qbt/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md, docs/CLAUDE.md, docs/COMMANDS.md

---

## 1) 목표(Goal)

- [ ] 목표 1: `generate_daily_comparison.py` 가 TQQQ · QLD 일별 비교 CSV 를 함께 만든다 (새 스크립트 없음)
- [ ] 목표 2: `app_daily_comparison.py` 에서 상품을 골라 QLD 검증 결과를 본다
- [ ] 목표 3: TQQQ 결과는 코드 변경으로 한 글자도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- `QLD_synthetic_max.csv`(상장 전 시뮬레이션 + 상장 후 실물) 생성 — 읽을 코드가 없다 (사용자 결정 2026-10-31)
- QLD 전용 운용보수 파일 도입 — TQQQ 보수 유지 (사용자 결정 2026-10-31)
- 스프레드 a · b 재튜닝, 튜닝 스크립트 복원
- 스프레드 랩 앱 변경, `qbt/tqqq` 패키지 · 결과 폴더 이름 변경
- `QLD_proxy_max.csv` 등 대용 · 합성 시세 재생성과 `run_*` 러너 재실행 — 이 작업이 만드는 결과는 일별 비교 CSV 2개뿐이다
- TQQQ 와 QLD 를 나란히 놓는 화면 — 「비교」는 실제 대 시뮬 비교로 해석했다
- SSO 등 다른 레버리지 ETF 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 일별 비교 스크립트와 대시보드가 TQQQ 로 고정돼 있어 QLD 의 추적 오차(RMSE · 누적배수 로그차이 추이 · 일일 오차 분포)를 볼 수 없다.
- QLD 2배 합성 자체는 이미 있다: `generate_long_proxy_series.py` 의 `QLD_proxy_max.csv`. `app_proxy_comparison.py` 는 상관 · CAGR · MDD 만 보여 준다.
- 스크립트 경로만 QLD 로 바꾸면 실패한다: `create_expense_dict` 는 2010-02 부터라 `Expense 데이터 부족: 2006-06 이전의 Expense 데이터가 존재하지 않습니다.` 로 멈춘다. `build_extended_expense_dict` 가 필요하다.

### 실측 근거 (2026-10-31 23:04, 커밋 `c8d7007` 의 시세 — QLD · QQQ · TQQQ 끝 2026-10-29, 저장소 파일 변경 없이 측정)

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

### 재사용 함수 호출처 (정의 · 주석 · 테스트 제외, `src` · `scripts` grep)

| 함수 | 실제 호출 |
|---|---|
| `simulate` | 3곳 (`generate_daily_comparison` · `generate_synthetic` · `generate_long_proxy_series` — 마지막은 이미 배율 2) |
| `calculate_validation_metrics` | 1곳 (`generate_daily_comparison`) |
| `build_extended_expense_dict` | 2곳 (`generate_synthetic` · `generate_long_proxy_series`) |
| `load_comparison_data` | 2곳 (`app_daily_comparison` · `app_rate_spread_lab`) |
| `create_price_comparison_chart` | 1곳 (`app_daily_comparison`), 테스트 2곳 |
| 히스토그램 · 로그차이 차트 | 각 1곳 (`app_daily_comparison`) |

`scripts/` 를 import 하는 테스트는 0건이다 — 스크립트 변경은 pytest 로 잡히지 않으므로 Phase 2 의 실행 대조로 검증한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」, `docs/MEMORY.md`
- `src/qbt/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`
- `tests/CLAUDE.md`, 전역 `~/.claude/rules/python.md`, `~/.claude/rules/python-tests.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [ ] `tqqq_daily_comparison.csv` 가 변경 전 코드의 기준값과 바이트 단위로 같다
- [ ] `qld_daily_comparison.csv` 행 수가 `QLD_max.csv` 행 수와 같고, 지표가 Context 의 실측과 일치한다 (시세가 그대로일 때)
- [ ] 대시보드에서 두 상품을 고를 수 있고 제목 · 범례 · 문구가 고른 상품을 따른다
- [ ] 회귀/신규 테스트 추가 (차트 라벨, 상품 표 계약, 보수 파일보다 먼저 상장한 상품)
- [ ] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [ ] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [ ] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [ ] 필요한 문서 업데이트 (`docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md`)
- [ ] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (`docs/research/전략_검증_보고서.md` §49 에 실측과 탈락안)
- [ ] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/constants.py` — `QLD_DAILY_COMPARISON_PATH`, `LEVERAGE_2X`, 상품 표 `DAILY_COMPARISON_TARGETS` (이름 · 실물 시세 · 배율 · CSV). 두 파일이 쓰므로 도메인 상수에 둔다
- `src/qbt/tqqq/visualization.py` — `create_price_comparison_chart(df, product_name)`: 하드코딩된 TQQQ 3곳을 인자로. 기본값을 두지 않는다 — 빠뜨린 호출이 조용히 TQQQ 로 표시되지 않게
- `scripts/tqqq/generate_daily_comparison.py` — 상품 표를 도는 반복문, `build_extended_expense_dict` 로 교체, 로그 · docstring
- `scripts/tqqq/app_daily_comparison.py` — 상품 선택 `st.radio`(`app_proxy_comparison.py` 의 2지선다 관용), 제목 · 문구 · 데이터 소스를 고른 상품으로. 「운용보수와 스프레드는 두 상품 모두 TQQQ 기준」 안내 — 숫자를 적지 않고 상수의 파일 이름을 참조
- `scripts/data/generate_long_proxy_series.py` — 자체 `LEVERAGE_2X` 를 constants 에서 가져온다 (상수 중복 금지, 값 동일)
- `tests/qbt/test_tqqq_visualization.py`, `tests/qbt/test_tqqq_simulation_outputs.py`, `tests/qbt/test_tqqq_simulation_cost_model.py`
- `README.md` — 기능 소개 줄을 TQQQ · QLD 로
- `scripts/CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`
- `docs/research/전략_검증_보고서.md` — §49 하위에 QLD 추적 검증 절 추가 (계획서 규약: 설계 결정 · 탈락안의 자리)
- `docs/COMMANDS.md`: **변경 있음** — 워크플로우 2 의 제목 · 선행 시세(QLD) · 출력 · 대시보드 필요 파일, 「다시 돌리는 순서」 ⑤ 설명. 실행 명령과 CLI 옵션은 그대로

**바꾸지 않는 것**: `simulate`, `calculate_validation_metrics`, `load_comparison_data`, `generate_synthetic.py`, `app_rate_spread_lab.py`

### 데이터/결과 영향

- 신규: `storage/results/tqqq/qld_daily_comparison.csv` — 열 · 인코딩은 TQQQ CSV 와 같다(같은 저장 함수)
- 갱신: `storage/results/tqqq/tqqq_daily_comparison.csv` 끝이 2026-09-24 → 2026-10-29. **원인은 코드가 아니라 커밋 `c8d7007` 의 시세다** — 조정 종가가 함께 바뀌어 과거 행도 달라진다. Phase 0 기준값으로 코드 영향이 0 임을 분리한다
- 스프레드 랩 앱은 같은 경로 · 같은 열의 TQQQ CSV 를 그대로 읽는다
- 작업 트리는 `c8d7007` 기준 깨끗하다 — 이 작업의 diff 에는 이 계획이 만든 변경만 남는다
- `TQQQ_synthetic_max.csv` · `QLD_proxy_max.csv` · 대체-실물 요약은 2026-09-24 끝으로 남는다 — 지금 상태 그대로이고 이 작업이 건드리지 않는다

## 6) 단계별 계획(Phases)

### Phase 0 — 기준값 확보와 계약 테스트(레드)

**작업 내용**:

- [ ] 변경 전 코드로 `generate_daily_comparison.py` 를 실행하고 `tqqq_daily_comparison.csv` 사본을 scratchpad 에 기준값으로 둔다
- [ ] `test_tqqq_visualization.py` — 인자로 준 상품 이름이 범례 2개와 제목에 들어간다(QLD), 기존 호출 2곳 갱신
- [ ] `test_tqqq_simulation_outputs.py` — `DAILY_COMPARISON_TARGETS` 계약: 배율 `{"TQQQ": 3.0, "QLD": 2.0}` 숫자 고정, CSV 경로가 서로 달라 한 상품이 다른 상품을 덮어쓰지 않는다
- [ ] `test_tqqq_simulation_cost_model.py` — 보수 파일보다 먼저 상장한 상품: `create_expense_dict` 는 `ValueError`, `build_extended_expense_dict` + 배율 2 는 손계산 종가와 일치

**Validation**:

- [ ] 앞의 두 테스트가 구현 전이라 실패하는 것을 확인한다 (특정 파일 `pytest`)
- [ ] 셋째 테스트는 기존 함수 조합을 고정하므로 바로 통과한다 — 확장값을 일부러 바꿔 실패를 본 뒤 되돌린다 (`PYTHONDONTWRITEBYTECODE=1`)

---

### Phase 1 — 구현(그린 유지)

**작업 내용**:

- [ ] `constants.py` 추가, `generate_long_proxy_series.py` 의 상수 이전
- [ ] `visualization.py` 라벨 인자
- [ ] `generate_daily_comparison.py` 반복문과 보수 함수 교체
- [ ] `app_daily_comparison.py` 상품 선택과 문구

**Validation**:

- [ ] Phase 0 테스트 3개 파일 통과 (특정 파일 `pytest`)

---

### Phase 2 — 실행 대조

**작업 내용**:

- [ ] 변경 후 `generate_daily_comparison.py` 실행 — 대체 시세 · 러너는 돌리지 않는다
- [ ] 일회성 화면 코드 확인: `streamlit.testing.v1.AppTest` 로 scratchpad 에서 두 상품을 돌려 예외 0건과 제목 · 최종 종가를 확인한다. 서버 · 포트를 쓰지 않고 저장소 테스트로 넣지 않는다 (저장소의 AppTest 사용 0건). **사용자 승인 대기 — 거절되면 이 줄을 빼고 사용자 화면 확인만 둔다**

**Validation**:

- [ ] `cmp` 로 TQQQ CSV 가 Phase 0 기준값과 같다
- [ ] QLD CSV 행 수와 `QLD_max.csv` 행 수를 따로 세어 맞춘다
- [ ] QLD CSV 를 다시 읽어 RMSE · 평균 · 최대 · 마지막 날 값을 Context 실측과 대조한다
- [ ] `git status` — Scope 밖 변경 0건

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [ ] 문서 업데이트: `docs/COMMANDS.md`(변경 있음) · `README.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md`
- [ ] 근거 승격: `docs/research/전략_검증_보고서.md` §49 에 실측 표, 재튜닝 · 보수 탈락안과 근거, 상장 전 구간은 대조 불가라는 한계
- [ ] 자동 포맷 적용 (`poetry run black .`)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] 사용자용 대시보드 확인 안내: 실행 명령과 볼 지점 (AI 는 띄우지 않는다)
- [ ] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [ ] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [ ] `/code-review xhigh` **1회차** (발견 \_\_건 — 버그 \_\_ [무거움 \_\_ · 가벼움 \_\_] · 그 외 \_\_ · 조치: \_\_)
- [ ] 수정분 검증 (수정 \_\_건 · 발견 \_\_건 — 무거움 \_\_ · 조치: \_\_ — 마지막 회차에 고친 것이 없으면 「해당 없음」)
- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

- [ ] (미작성 — `/commit` 을 실행하고 후보 5개를 **이 자리에** 번호 붙은 줄로 옮긴 뒤 이 줄을 지운다)

## 7) 리스크(Risks)

- **TQQQ 결과 회귀** — 보수 함수 교체와 반복문 때문. 완화: Phase 0 기준값과 바이트 대조
- **부분 저장** — QLD 계산이 실패하면 TQQQ CSV 만 새로 저장된 채 종료 코드 1 로 끝난다. 실패가 드러나고 재실행으로 복구되므로 원자적 저장을 만들지 않는다
- **QLD CSV 가 없을 때** — 앱은 TQQQ 와 같이 `FileNotFoundError` 를 낸다. 경로가 메시지에 나오고 결과 CSV 는 git 이 추적하므로 별도 안내를 두지 않는다
- **QLD 입력이 사실과 다름** — 최근 운용보수가 공시(`Net Expense Ratio* 0.95%`, ProShares 팩트시트 2026-09-30 기준)보다 0.13%p 낮다. 사용자가 합성 시세와 같은 입력을 택했다. 완화: 화면 안내와 보고서 기록
- **상장 전 구간은 이 검증으로 보장되지 않는다** — 대조 실물이 없다(1999-03-10 ~ 2006-06-20). 완화: 보고서 기록
- **검증 중 시세 재다운로드** — 실측 대조가 깨진다. 완화: 작업 중 `download_data.py` 를 돌리지 않는다. 시세가 바뀌면 대조 기준을 다시 잰다
- **격자 최저값은 전 기간에 맞춘 값** — 재튜닝 탈락의 근거로만 쓰고 모델 성능으로 인용하지 않는다

## 8) 메모(Notes)

### 결정

- 2026-10-31 사용자 결정: 이어 붙인 QLD 시세를 만들지 않는다, TQQQ 운용보수를 유지한다 (보고한 추천안 채택)
- 재튜닝 안 함: 개선 0.0466%p, 튜닝 스크립트는 저장소에 없다(복원 지점 `c81690b^`) — 「기존 스크립트 활용」 조건과 충돌
- 인자 없이 두 상품을 항상 함께 생성 — 두 CSV 의 시세 기준일이 어긋나지 않는다
- 상품 선택은 보고 때의 선택 상자 대신 `st.radio` — 2지선다라 두 항목이 항상 보이고, `app_proxy_comparison.py` 관용과 같다

### 계획서 자체 검증 (2026-10-31)

| 회차 | 각도 | 결과 |
|---|---|---|
| 1 | 논리 · 누락 | 스크립트를 import 하는 테스트 0건 → 실행 대조와 기준값을 넣음. 두 상품이 같은 경로를 쓰면 조용히 덮어쓰므로 표 계약 테스트 추가 |
| 2 | 다른 로직 영향 | `src/qbt/CLAUDE.md:47`, `docs/COMMANDS.md:200` 언급을 문서 범위에 추가. 대체 시세를 다시 만들지 않음을 비목표로 명시 |
| 3 | 오류 · 동시성 | 부분 저장과 CSV 부재를 위험으로 기록 — 드러나는 실패라 코드를 늘리지 않음 |
| 4 | 단순화 | 개선 없음 |
| 5 | 사용자 조건(새 스크립트 없음, 대시보드는 사용자 실행) | 개선 없음 |
| 6 | 문서 · 근거 승격 | 개선 없음 — 연속 3회 개선 없어 종료 |

### 진행 로그 (KST)

- 2026-10-31 23:04: 앞서 쓴 계획서가 폴더에서 사라져 사용자 요청으로 다시 작성. 커밋 `c8d7007` 시세로 실측을 다시 재어 모든 값이 같음을 확인, 작업 트리 상태 서술만 갱신. 승인 대기

---
