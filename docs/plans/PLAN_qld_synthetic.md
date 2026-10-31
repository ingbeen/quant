# Implementation Plan: 합성 QLD 시세 파일 생성

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-01 00:18
**마지막 업데이트**: 2026-11-01 00:47
**관련 범위**: scripts/tqqq, common_constants, docs
**관련 문서**: src/qbt/CLAUDE.md, scripts/CLAUDE.md, docs/CLAUDE.md, docs/COMMANDS.md

---

## 1) 목표(Goal)

- [x] 목표 1: `generate_synthetic.py` 가 `QLD_synthetic_max.csv` 를 함께 만든다 (새 스크립트 없음)
- [x] 목표 2: 같은 시세에서 `TQQQ_synthetic_max.csv` 는 코드 변경으로 한 글자도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- QLD 를 읽는 단일 백테스트 전략 추가 — 사용자가 A(파일만)를 골랐다 (2026-11-01)
- `run_single_backtest.py` · `run_walkforward.py` 등 러너 재실행, 대체 시세 재생성
- `simulate` · `splice_proxy` · 비용 모델 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `generate_synthetic.py` 는 TQQQ 만 만든다. QLD 는 상장 전 구간을 합성으로 이은 파일이 없고, 전 구간 합성인 `QLD_proxy_max.csv` 만 있다.
- 2026-10-31 결정 「읽을 코드가 없으니 만들지 않는다」를 사용자가 2026-11-01 에 뒤집었다.

### 실측 근거 (2026-11-01, 커밋 `b288321` 의 시세, 저장소 파일을 쓰지 않은 시험 생성)

- 6,954행 = 합성 1,832 + 실물 5,122, 1999-03-10 ~ 2026-10-29, 이음매 2006-06-21
- 실물 구간 종가가 `QLD_max.csv` 와 같음, 0 이하 가격 0행, 고가 · 저가 불변식 위반 0행, 합성 구간 꼬리 있는 행 0.9989
- 전 구간 MDD -98.92%, 닷컴 2000-03 ~ 2002-12 MDD -98.76% (QQQ -82.96%)
- 최대 일간 등락 33.65%, 최저가 0.297025

### 재사용 함수 호출처 (정의 · 주석 · 테스트 제외)

| 함수 | 실제 호출 |
|---|---|
| `simulate` | 3곳 — `generate_long_proxy_series` 가 이미 같은 QQQ 2배 호출 |
| `build_extended_expense_dict` | 2곳 (`generate_synthetic` · `generate_long_proxy_series`), 일별 비교까지 3곳 |
| `splice_proxy` | 3개 스크립트 (`generate_synthetic` · `generate_long_proxy_series` · `generate_proxy_series`) |

`scripts/` 를 import 하는 테스트는 0건이다 — 실행 대조로 검증한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」, 「가격 반올림 자릿수」, `docs/MEMORY.md`
- `src/qbt/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/CLAUDE.md`
- 전역 `~/.claude/rules/python.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `TQQQ_synthetic_max.csv` 가 변경 전 코드로 만든 기준값과 바이트 단위로 같다
- [x] `QLD_synthetic_max.csv` 가 Context 의 시험 생성과 행 수 · 기간 · 불변식 · MDD 가 일치한다
- [x] 이음매 뒤 행이 `QLD_max.csv` 의 실물 행과 전 열 같다
- [x] 이음매 앞 종가 수익률이 배율 2 합성과 일치한다 (배율 · 실물 표 칸의 오입력을 잡는다)
- [x] `load_stock_data` 로 새 파일을 읽는다
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 (`docs/COMMANDS.md` · `scripts/CLAUDE.md`, `README.md` 는 변경 없음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (`docs/research/전략_검증_보고서.md` §49.4)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」) → 1건 옮김 — 합성 스크립트의 저장 연결 테스트 공백
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py` — `QLD_SYNTHETIC_DATA_PATH` (이웃 `TQQQ_SYNTHETIC_DATA_PATH` 와 같은 자리)
- `scripts/tqqq/generate_synthetic.py` — 상품 표 `SYNTHETIC_TARGETS` (스크립트 상단, `generate_long_proxy_series.py` 의 `LEVERAGED_PROXIES` 관용)를 도는 반복문, 로그 · docstring
- `scripts/CLAUDE.md` — 스크립트 지도 한 줄
- `docs/research/전략_검증_보고서.md` — §49.4 에 합성 파일 실측 한 단락
- `docs/COMMANDS.md`: **변경 있음** — 워크플로우 2 의 3 번 설명 · 출력, 「다시 돌리는 순서」 ③ 설명. 실행 명령과 CLI 옵션은 그대로
- `README.md`: 변경 없음 — 이미 TQQQ · QLD 시뮬레이션으로 적혀 있고 파일 단위를 다루지 않는다
- 테스트: 추가 없음 — 스크립트 표 변경이고 저장소 관용상 scripts 를 import 하지 않는다. 호출하는 함수의 계약은 이미 테스트가 있다
- **리뷰 1회차로 바뀐 범위** (Notes 「결정 변경」): `SYNTHETIC_TARGETS` 대신 `src/qbt/tqqq/constants.py` 의 `SYNTHETIC_DATA_PATHS` 를 두고, `tests/qbt/test_tqqq_simulation_outputs.py` 에 테스트 1개를 더한다. `docs/DEFERRED_FINDINGS.md` 에 항목 1개를 옮긴다

### 데이터/결과 영향

- 신규: `storage/stock/QLD_synthetic_max.csv` — 지금 이 파일을 읽는 코드는 없다
- 갱신: `storage/stock/TQQQ_synthetic_max.csv` — 끝이 2026-09-24 → 2026-10-29, 상장 전 고가 · 저가가 새 식으로 바뀐다. **원인은 이미 받은 시세와 커밋 `b288321` 이고 이번 코드가 아니다** — Phase 0 기준값으로 분리한다
- `buffer_zone_tqqq` · `buy_and_hold_tqqq` 의 결과 폴더와 워크포워드 결과는 옛 파일 기준으로 남는다. 사용자가 러너 재실행을 범위에서 뺐다
- `docs/COMMANDS.md` 의 시세 다운로드 순환은 `*_synthetic_max.csv` 를 건너뛰므로 새 파일을 내려받으려 하지 않는다

## 6) 단계별 계획(Phases)

### Phase 0 — 기준값 확보

**작업 내용**:

- [x] 변경 전 코드로 `generate_synthetic.py` 를 실행하고 `TQQQ_synthetic_max.csv` 사본을 scratchpad 에 기준값으로 둔다

**Validation**:

- [x] 기준값 행 수와 끝 날짜를 확인한다

---

### Phase 1 — 구현과 실행 대조

**작업 내용**:

- [x] `common_constants.py` 상수 추가
- [x] `generate_synthetic.py` 표와 반복문
- [x] 변경 후 `generate_synthetic.py` 실행

**Validation**:

- [x] `cmp` 로 `TQQQ_synthetic_max.csv` 가 기준값과 같다
- [x] 새 파일을 `load_stock_data` 로 읽어 행 수 · 기간 · 불변식 · MDD 를 시험 생성과 대조한다
- [x] 이음매 뒤 행을 `QLD_max.csv` 와 전 열 대조한다
- [x] 이음매 앞 종가 수익률을 `simulate` 배율 2 와 대조한다
- [x] `git status` — Scope 밖 변경 0건

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 업데이트: `docs/COMMANDS.md`(변경 있음) · `scripts/CLAUDE.md`
- [x] 근거 승격: `docs/research/전략_검증_보고서.md` §49.4
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 13건 — 버그 5 [무거움 2 · 가벼움 3] · 그 외 8 · 조치: 무거움 1 수정 — 표 칸 테스트 공백. 그 외 중 §49.4 사실 오류는 진행 로그의 이유로 함께 수정)
- [x] `/code-review xhigh` **2회차** (발견 15건 — 버그 6 [무거움 2 · 가벼움 4] · 그 외 9 · 조치: 코드 수정 없음, 고칠 것 0. 무거움 1 은 미룬 지적으로 옮김, 무거움 1 은 닿지 않음)
- [x] 수정분 검증 — 해당 없음 (마지막 회차에 고친 것 없음)
- [x] `poetry run python validate_project.py` (passed=926, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. TQQQ시뮬레이션 / 합성 QLD 시세 파일 생성 추가
2. TQQQ시뮬레이션 / generate_synthetic 의 TQQQ · QLD 확장과 QLD_synthetic_max.csv 생성
3. TQQQ시뮬레이션 / 상장 전 합성과 실물을 이은 QLD 시세 추가와 일별 비교 상품 표 재사용
4. TQQQ시뮬레이션 / 합성 QLD 시세 생성과 합성 파일 표 테스트 추가, TQQQ 합성 시세 갱신
5. TQQQ시뮬레이션 / 닷컴 구간 참고용 QLD 합성 시세 추가 — §49.4 신뢰 범위 실측과 미룬 지적 기록

## 7) 리스크(Risks)

- **TQQQ 합성 회귀** — 반복문으로 옮기면서 입력이 바뀔 수 있다. 완화: Phase 0 기준값과 바이트 대조
- **표 칸 오입력** — 스크립트는 테스트가 닿지 않는다. 완화: 이번에는 이음매 뒤 실물 행 · 이음매 앞 배율을 실행으로 대조한다. 표는 이웃 `LEVERAGED_PROXIES` 와 같이 스크립트에 두고 테스트를 늘리지 않는다
- **결과와 입력의 기준일 불일치** — TQQQ 전략 결과는 옛 파일 기준으로 남는다. 러너를 돌리면 해소된다. 고가 · 저가는 매매 계산이 읽지 않지만 기간이 늘어 성과 수치는 바뀔 수 있다
- **부분 저장** — QLD 시세가 깨져 있으면 TQQQ 파일만 새로 저장되고 종료 코드 1 로 끝난다. 드러나는 실패이고 재실행으로 복구되어 원자적 저장을 만들지 않는다
- **상장 전 구간은 대조할 실물이 없다** — 1999-03-10 ~ 2006-06-20. 판정이 아니라 참고용이다. 완화: 보고서 기록
- **검증 중 시세 재다운로드** — 대조가 깨진다. 완화: 작업 중 `download_data.py` 를 돌리지 않는다

## 8) 메모(Notes)

### 결정

- 2026-11-01 사용자 결정: A — 합성 QLD 파일만 만들고 전략은 추가하지 않는다. 진행 후 커밋명을 받는다
- 표는 `SYNTHETIC_TARGETS` 로 스크립트 상단에 둔다 — 한 파일만 쓰는 상수의 자리(`src/qbt/CLAUDE.md` 「상수 관리」). `DAILY_COMPARISON_TARGETS` 를 재사용하지 않는다 — 일별 비교 대상과 합성 대상은 다른 결정이고, 합성 경로 칸을 넣으면 그 표가 두 책임을 진다
- 저장 검사는 두 상품 모두 `check_price_spikes=False` — 3배가 50% 를 넘는 날이 있어 꺼 둔 기존 호출을 그대로 쓴다. QLD 최대 등락은 33.65% 라 켜도 통과하지만 상품별 분기를 만들 이유가 없다

### 결정 변경 (2026-11-01, 코드 리뷰 1회차)

- 위 「표는 스크립트 상단」 · 「`DAILY_COMPARISON_TARGETS` 를 재사용하지 않는다」 · 리스크의 「테스트를 늘리지 않는다」를 뒤집었다. 표 칸을 잘못 적으면 틀린 시세 파일이 에러 없이 저장되는데 지키는 테스트가 없었다 — 검사 공백이 막는 결함이 무거워 `review.md` 기준으로 고칠 지적이다
- 지금 구조: `generate_synthetic.py` 가 `DAILY_COMPARISON_TARGETS` 를 돌고 저장 경로만 `SYNTHETIC_DATA_PATHS[상품 이름]` 으로 찾는다 — 일별 비교로 검증한 상품만 합성한다
- 대가 둘: `SYNTHETIC_DATA_PATHS` 는 스크립트 한 파일만 쓰는데 테스트가 scripts 를 불러오지 않아 도메인 상수에 두었다(`src/qbt/CLAUDE.md` 상수 배치 규칙과 다름). 일별 비교에 상품을 더하면 합성 파일 항목도 더해야 한다 — 빠지면 표 테스트가 잡는다

### 계획서 자체 검증 (2026-11-01)

| 회차 | 각도 | 결과 |
|---|---|---|
| 1 | 논리 · 누락 | 스크립트에 테스트가 닿지 않음 → 표 칸 오입력을 잡는 실행 대조 2개(이음매 뒤 실물 · 이음매 앞 배율) 추가 |
| 2 | 다른 로직 영향 | 같은 스크립트가 TQQQ 파일을 다시 씀 → 기준값 대조와 결과 기준일 불일치를 위험에 기록. 다운로드 순환이 새 파일을 건너뜀을 확인 |
| 3 | 오류 · 동시성 | 부분 저장을 위험으로 기록 — 드러나는 실패라 코드를 늘리지 않음 |
| 4 | 단순화 | 개선 없음 |
| 5 | 사용자 조건(A 만, 새 스크립트 없음) | 개선 없음 |
| 6 | 문서 · 근거 승격 | 개선 없음 — 연속 3회 개선 없어 종료 |

### 진행 로그 (KST)

- 2026-11-01 00:18: 계획서 작성. 사용자가 「A만 진행 후 커밋명 알려줘」로 착수를 지시해 바로 진행
- 2026-11-01 00:20: Phase 0 기준값 — TQQQ 합성 6,954행, 끝 2026-10-29. 변경 후 실행 대조: TQQQ 기준값과 바이트 동일, QLD 6,954행 = 합성 1,832 + 실물 5,122, 이음매 뒤 실물과 네 가격 최대 차 0.0 · 거래량 · 날짜 같음, 이음매 앞 일별 수익률 최대 차 2.08e-06, QQQ 대비 기울기 2.0001, 불변식 위반 0행, 전 구간 MDD -98.92 · 닷컴 MDD -98.76
- 2026-11-01 00:21 ~ 00:34: 리뷰 1회차 수정. 표 칸 테스트 공백 1곳 → 상품 표 재사용 + `SYNTHETIC_DATA_PATHS` + 테스트 1개. 변형 3가지 모두 실패를 보고 되돌림(QLD 가 TQQQ 합성을 덮어씀 1건 · TQQQ 가 QLD 합성을 덮어씀 1건 · QLD 항목 누락 1건). 수정 후 두 합성 파일 바이트 동일
- 2026-11-01 00:34: 리뷰 1회차의 「그 외」 중 §49.4 근거 기록의 사실 오류는 규칙과 달리 고쳤다 — 고치지 않으면 틀린 수치가 살아있는 문서에 남고 계획서의 근거 승격이 거짓이 된다. 87개월 → 88개월(다시 재서 88 · 초과 15 확인), 금융위기 행에 구간 첫날 기준을 적고 상장일 기준 RMSE 1.677 · 마지막 +1.0793 병기, 성과 지표 문구를 식 변경과 재생성으로 가름, 이음매 날 시가 틈(+4.15% · QQQ 2배 +0.32%) 추가, 재측정 범위 문구 수정. 같은 이유로 부록 I 에 합성 시세 참조 한 문장을 더했다
- 2026-11-01 00:46: 품질 검증 passed=926, failed=0, skipped=0. 리뷰 2회차 고칠 것 0 — 무거움 1건(스크립트 저장 연결 테스트 공백)은 파일 생성 범위를 넘어 `docs/DEFERRED_FINDINGS.md` 로 옮김. 같은 모양 항목의 이전 사용자 결정(2026-10-19 「미룬 지적으로 옮긴다」)을 따랐다
- 2026-11-01 00:46: 거른 지적(기준 번호): 운용보수 파일 앞 행이 지워지면 TQQQ 도 멈추지 않음(1, 근거: 파일 이력 6개 커밋 모두 첫 달 2010-02, 갱신은 끝에 붙이기뿐) · QLD 입력 실패 시 부분 저장(2, 계획서가 받아들임) · QLD 급등락 검사 꺼짐(1, 근거: 지금 최대 33.65% 로 0행, 같은 오입력은 대체 시세 단계가 멈춤) · 저장 때 열 없으면 KeyError(2) · QLD CSV 부재 시 날것의 예외(2) · 입력과 결과의 기준일 불일치(3, 사용자가 러너 재실행을 범위에서 뺌) · 툴팁 소수 2자리(3) · 테스트 docstring 범위(3) · 낡은 주석 · docstring · CLAUDE.md 배율 문구(3) · 두 표 결합(3) · 상수 배치 2건(3) · 전 기간 시뮬레이션(3) · 입력 준비 반복(3) · 로그의 상품 이름(3)

---
