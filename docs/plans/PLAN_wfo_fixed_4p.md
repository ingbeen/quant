# Implementation Plan: 워크포워드 Fully Fixed 모드를 4P 고정으로 — 운영 점검표 체크 1 이 4P 를 재게 한다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-10 11:05
**마지막 업데이트**: 2026-10-10 11:43
**관련 범위**: backtest(`walkforward_verdict`), scripts(`run_walkforward.py` · `app_walkforward.py`), storage/results(워크포워드), docs/research
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `docs/research/전략_검증_보고서.md`, `docs/AUDIT_REPORT.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 워크포워드의 Fully Fixed 모드가 **확정 파라미터 4P 를 모든 윈도우에 고정**한다(지금은 첫 윈도우의 IS 최적값을 고정)
- [x] 목표 2: 대시보드 판단 문구 · 설명이 바뀐 정의를 말한다
- [x] 목표 3: 워크포워드를 다시 돌리고, 연구 보고서 §2.5 와 운영 점검표(§22.3)를 새 결과로 고친다

## 2) 비목표(Non-Goals)

- **모드 키 · 파일 이름 변경** — `fully_fixed` · `walkforward_fully_fixed.csv` · `wfo_windows_fully_fixed/` 는 그대로 둔다(「파라미터를 끝까지 고정한다」는 뜻이 그대로 맞고, 바꾸면 상수 · 러너 · 대시보드 · 판단 모듈 · 테스트가 함께 바뀐다)
- **판단 문구 테스트 보강**(감사 보고서 2-26) — 6단계(검사 보강)
- **워크포워드의 다른 정리**(1-8 · 1-9 · 2-20 · 6-1 등) — 감사 보고서 19절의 해당 단계

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 운영 점검표(`전략_검증_보고서.md` §22.3) 체크 1 과 폐기 기준 3(§23.2)은 「Dynamic 대 Fixed」를 비교하는데, Fixed 는 첫 윈도우의 IS 최적값(QQQ (100, 0.03, 0.01, 5) · TQQQ (200, 0.05, 0.01, 3))이라 운영 중인 4P (200, 0.03, 0.05, 3)를 재지 않는다
- 2026-10-10 사용자 결정(감사 보고서 19절 4-1): 체크 1 의 비교 대상을 「4P 를 첫 OOS 시작일부터 끝까지 쓴 성과」로 바꾼다
- 지금 Fixed 를 정하는 곳은 러너 한 곳이다 — `scripts/backtest/run_walkforward.py` 의 「Mode 2」가 `dynamic_results[0]` 의 선택을 단일 값 목록으로 넘긴다. 정의를 말하는 곳은 대시보드 설명 3곳(`app_walkforward.py` 의 모드 설명 · 이어 붙인 자본곡선 설명 · 화면 머리 설명)과 판단 문구 1곳(`walkforward_verdict._describe_cagr_gap` 의 「처음 것을 고정하든」)이다. 판단 문구를 단언하는 테스트는 없다

### 설계 결정

- **Fully Fixed = 4P 고정**: 러너가 Mode 2 에 `FIXED_4P_*` 상수를 단일 값 목록으로 넘긴다. IS 평가 시작일은 지금처럼 Dynamic 그리드의 가장 긴 이동평균(`eval_ma_window`) — 4P 의 200일선과 같다
- **첫 윈도우 선택 고정 모드는 없앤다** — 두 모드 구조를 유지하고 판단 모듈 · 대시보드 표(4열)를 그대로 쓴다. 그 모드의 마지막 결과(2026-10-10: QQQ CAGR 5.33 · Calmar 0.2299, TQQQ 24.05 · 0.4421)는 연구 보고서 §2.5 에 한 줄로 남긴다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 재실행한 `walkforward_fully_fixed.csv` 의 선택이 QQQ · TQQQ 22개 윈도우 모두 4P 이고, Dynamic 결과 파일은 바이트 단위로 그대로다
- [x] 판단 문구 · 대시보드 설명에 「첫 윈도우 … 고정」 · 「처음 것을 고정」이 남지 않는다(`grep`)
- [x] 연구 보고서 §2.5 · §22.3 을 새 결과로 고쳤다
- [x] 회귀/신규 테스트 — 일정 규칙 테스트 2개(리뷰 1회차 ⑧ 수정과 2회차 보강으로 생겼다). 모드 구성 값은 결과 파일 대조로 확인
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`(처리 표시) · `scripts/CLAUDE.md` · `README.md` · `docs/COMMANDS.md`(「Dynamic / Fully Fixed」 표기만 있어 변경 없음 — 확인) · `src/qbt/backtest/CLAUDE.md`(변경 여부 확인)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/run_walkforward.py` — Mode 2 를 4P 로, 관련 주석 · 로그
- `src/qbt/backtest/walkforward_verdict.py` — 「처음 것을 고정하든」 문구
- `scripts/backtest/app_walkforward.py` — 모드 정의 설명 3곳
- `storage/results/backtest/buffer_zone_{qqq,tqqq}/` 의 `walkforward_fully_fixed.csv` · `walkforward_equity_fully_fixed.csv` · `walkforward_summary.json` · `wfo_windows_fully_fixed/` · `storage/results/meta.json` — 재실행
- `docs/research/전략_검증_보고서.md` — §2.5 · §22.3
- `docs/AUDIT_REPORT.md` — 처리 표시
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · 옵션 그대로)
- `README.md`: 변경 없음 (「Dynamic / Fully Fixed 2-Mode」 표기는 그대로 맞다)

### 데이터/결과 영향

- Fully Fixed 결과(선택 · IS/OOS 지표 · 이어 붙인 자본곡선 · 요약)가 4P 기준으로 바뀐다. Dynamic 은 그대로다
- 대시보드 워크포워드 화면의 판단 문구가 새 결과로 다시 만들어진다

## 6) 단계별 계획(Phases)

### Phase 1 — Fully Fixed 를 4P 로(그린 유지)

**작업 내용**:

- [x] `run_walkforward.py` — Mode 2 에 `FIXED_4P_*` 를 단일 값 목록으로
- [x] `walkforward_verdict.py` · `app_walkforward.py` — 정의를 말하는 문구

**Validation**:

- [x] `poetry run pytest tests/qbt/test_walkforward_verdict.py tests/qbt/test_walkforward_summary.py` — 전부 통과
- [x] `grep` — 「첫 윈도우 … 고정」 · 「처음 것을 고정」 0건(판단 모듈 · 대시보드 · 러너)

---

### Phase 2 — 재실행과 대조

**작업 내용**:

- [x] `run_walkforward.py` 실행(약 3분)
- [x] 대조(스크래치) — Fully Fixed 선택 22 / 22 가 4P, Dynamic 파일 해시 동일, Fixed 지표 전 · 후

**Validation**:

- [x] 대조 결과(수치는 진행 로그)

---

### Phase 3 — 연구 보고서

**작업 내용**:

- [x] §2.5 — 표의 Fixed 열을 4P 고정 값으로, 「읽는 법」을 새 정의로, 첫 윈도우 선택 고정의 마지막 결과 한 줄
- [x] §22.3 — 체크 1 의 「비교 대상 재검토」 표시를 지우고 비교 대상이 4P 고정임을 적는다
- [x] 지난 계획서가 붙인 표시 중 「Fixed 는 4P 가 아니다」를 현재형으로 말하는 자리(`grep`)를 「그때의 Fixed 는 첫 윈도우의 선택」으로 — 정의가 바뀌면 현재형이 거짓이 된다
- [x] §2.5 「읽는 법」에 파라미터 추이 사실 한 줄 — QQQ w2 ~ w10 의 150일선 · 매도 3% 가 QQQ 고원(G.7.2) 밖이라 폐기 기준 4(§23.2)에 해당하고, 폐기 검토 조건(기준 2개 이상)에는 못 미친다

**Validation**:

- [x] §2.5 표를 결과 파일과 대조(스크래치) — 불일치 0

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 — `docs/AUDIT_REPORT.md`(처리 표시) · `scripts/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`(변경 여부 확인). `docs/COMMANDS.md` · `README.md` 변경 없음
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 12건 — 버그 3 [무거움 3 · 가벼움 0] · 그 외 9 · 조치: 버그 3 수정 · 그 외 7 반영 · 미조치 2)
- [x] `/code-review xhigh` **2회차** (발견 13건 — 버그 2 [무거움 2 · 가벼움 0] · 그 외 11 · 조치: 버그 1 수정 · 버그 1 사용자에게 올림 · 그 외 8 반영 · 미조치 3)
- [x] 수정분 검증 (수정 7건 · 발견 5건 — 무거움 0 · 조치: 고치지 않고 기록 · 문구 3곳은 사용자에게 올림)
- [x] `poetry run python validate_project.py` (passed=868, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 워크포워드 Fully Fixed 모드를 4P 고정으로 변경
2. 백테스트 / 운영 점검표 체크 1 의 비교 대상을 4P 고정으로 변경과 사후 확정 편향 단서 추가
3. 백테스트 / Fully Fixed 4P 고정 · 단일 조합의 거래 수 하한 해제 · 같은 파라미터 구간의 전략 교체 생략, 판단 문구 · 연구 보고서 갱신과 워크포워드 재실행
4. 백테스트 / 첫 구간 선택을 고정해 4P 를 재지 못하던 워크포워드 비교 정정
5. 백테스트 / 점검 보고서 4-1 · 1-9 처리 — 4P 고정 비교와 일정 규칙 테스트 보강

## 7) 리스크(Risks)

- **첫 윈도우 선택 고정 비교가 사라진다** — 「가장 짧은 IS 의 최적값에 장기를 묶는 위험」(G.7.3-(2))을 다시 볼 수 없다. 완화: 마지막 결과를 §2.5 에 남긴다. 다시 필요하면 러너 한 줄로 되돌릴 수 있다
- **이름과 뜻** — `fully_fixed` 키 · 파일 이름은 그대로라 옛 결과(커밋 이력)와 새 결과의 뜻이 다르다. 완화: §2.5 에 바뀐 날짜를 적는다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 19절 4-1 · 13-A R6, 2026-10-10 사용자 결정(체크 1 비교 대상 = 4P 고정)

### 진행 로그 (KST)

- 2026-10-10 11:05: 계획서 작성(Draft). 자체 검증 — 지난 계획서의 표시 중 「Fixed 는 4P 가 아니다」 현재형이 정의 변경 뒤 거짓이 되므로 시제 정리를 Phase 3 에 더했다. 폐기 기준 4 해당 사실(사용자에게 보고한 것)을 §2.5 에 적는 일도 더했다
- 2026-10-10 11:06 이전(시각 미측정 — 처음에 11:08 로 잘못 적었다): 승인 — 사용자 「승인 — Fully Fixed 를 4P 로 바꿈」. 직전 계획서는 사용자가 커밋함(`96c935f`, 작업 트리에는 이 계획서뿐). Phase 1 착수
- 2026-10-10 11:06: Phase 1 — 러너 Mode 2 를 `FIXED_4P_*` 단일 값 목록으로(`first_best` 삭제), 판단 문구 「처음 것을 고정하든」 → 「확정값(4P)으로 고정하든」, 대시보드 정의 설명 3곳. `grep` 0건, 테스트 2파일 23 passed
- 2026-10-10 11:06: Phase 2 — `run_walkforward.py` 재실행. Dynamic 결과 파일 70개(요약 CSV · 자본곡선 · 윈도우 상세) 해시 동일. Fixed 선택 22 / 22 가 4P. Fixed 전(첫 윈도우 선택) → 후(4P): QQQ CAGR / MDD / Calmar 5.33 / −23.18 / 0.2299 → 11.65 / −26.43 / 0.4409, TQQQ 24.05 / −54.39 / 0.4421 → 24.13 / −62.09 / 0.3886. Dynamic Calmar QQQ 0.4465 · TQQQ 0.3251 — 4P 고정이 QQQ 와 비슷하고 TQQQ 에서 앞선다
- 2026-10-10 11:06: Phase 3 — §2.5 표 · 선택 파라미터 · 읽는 법을 다시 씀(Fixed = 4P, 첫 윈도우 선택 모드의 마지막 결과 한 줄, 4P 고정 ≥ Dynamic, 폐기 기준 4 해당 사실). WFE 문장은 4P 고정에서 QQQ 극단값이 w8(IS Calmar 0.283)에서 나와 「극단 구간 IS Calmar −0.04 ~ 0.12」가 다시 틀려지므로, 네 결과 전체에 맞는 「모든 윈도우의 IS Calmar −0.09 ~ 0.38」 · WFE −40.79 ~ 80.12 로 고쳤다. §22.3 표시를 「체크 1 의 Fixed 는 4P 고정」으로, §20.3 · §20.5.4 표시의 현재형 「Fixed 는 4P 가 아니다」를 과거형으로. 표 24칸 불일치 0
- 2026-10-10 11:25: `/code-review xhigh` 1회차 — 발견 12건
  - 고친 버그 3: ① Fully Fixed(4P)에도 「IS 거래 3회 이상」 필터(`min_trades`)가 걸려, 4P 의 w0 IS 거래가 정확히 3회라 데이터가 조금만 바뀌거나 `initial_is_months` 를 60 으로 줄이면 실행 전체가 ValueError 로 멈춤 — 무거움(죽는다) · 닿는다(재수집 · 상수) → `_run_single_mode` 에 `min_trades` 를 받아 Fixed 는 0 ⑨ 4P 의 이동평균이 그리드 최댓값보다 길어지면 Fixed 의 IS 가 조용히 늦게 시작하고 `is_start` 는 그대로 — 무거움(위험한 쪽) · 닿는다(상수) → `eval_ma_window=max(*그리드, FIXED_4P_MA_WINDOW)` ⑧ 이어 붙인 자본곡선이 OOS 경계마다 새 전략 객체를 넣어 유지일 대기 상태를 버림 — 경계 직전 돌파의 확정이 경계 뒤로 넘어가면 진입이 에러 없이 사라져 「4P 를 끝까지 쓴 성과」와 달라질 수 있다(지금 데이터 0행 차이) — 무거움 · 닿는다(데이터). 점검 보고서 1-9 와 같은 결함 → `build_params_schedule` 이 파라미터가 직전 윈도우와 같으면 일정에 넣지 않는다(Fixed 는 일정이 비어 한 번의 연속 실행이 된다)
    - 같은 모양 찾기: 「고를 조합이 하나인데 고르는 단계의 장치가 걸린다」는 `min_trades` 한 곳, 「정의가 바뀐 상수와 다른 상수가 어긋날 수 있다」는 `eval_ma_window` 한 곳
    - 변형 확인(`PYTHONDONTWRITEBYTECODE=1`, 사본과 `diff -q` 동일 복원): M5 일정 거름 줄 삭제 → `test_same_params_as_previous_window_do_not_switch_strategy` 1 failed, 복원 뒤 통과. ① · ⑨ 는 스크립트 `main` 의 인자라 단위 테스트가 없고(미조치 ⑪ 참고) 재실행으로 확인
    - 수정 뒤 재실행: 워크포워드 결과 142개 파일 해시 모두 그대로(지금 결과를 바꾸지 않는다)
  - 반영한 그 외 7: ② 사후 확정 편향 — 4P 는 전 기간을 보고 정했으므로 OOS 도 4P 에게는 본 구간이라 「4P 고정 ≥ Dynamic」은 예상되는 결과이고 독립 근거가 아니다 → §2.5 · §22.3 에 단서, §2.5 의 「보조 확인」 문장 삭제 ③ 판단 문구 세 갈래와 대시보드 설명 2곳에 같은 단서(문구 상수 `_HINDSIGHT_NOTE` 하나) ④ 폐기 기준 4 사실 정정 — QQQ 는 w0 · w1(100일선 · 매도 1%)도 2개가 고원 밖이라 11개 윈도우 모두, TQQQ 도 w3 ~ w10, 점검표 §22.4 의 「고원 이탈 → §23.3 검토」, 「3회 연속」 해석이 정해지지 않았음 ⑤ §23.2 기준 3 에 「2026-10-10 부터 4P 고정 — 그 전 점검과 이어서 세지 않는다」 ⑥ 점검 보고서 4-1 문단을 지금 상태로 ⑦ G.7.3-(2) 의 현재형 정의를 과거형으로 ⑫ 판단 모듈 테스트 독스트링의 「실제 SMA 기준 … 값」 표기 삭제(옛 정의의 값)
  - 미조치 2: ⑩ 메타 · 요약에 Fixed 파라미터가 기록되지 않아 실행 이력의 두 정의를 가를 수 없다 — 기록(기준 3). 메타 기능은 결정 6 으로 지울 예정 ⑪ Mode 2 가 `FIXED_4P_*` 를 쓴다는 것을 고정하는 테스트가 없다 — 스크립트 `main` 의 구성값이라 테스트하려면 스크립트를 동적 import 해야 하고(점검 보고서 10절이 없애려는 방식), 고정하는 것이 상수 참조 한 줄이다 — 그 외(기준 3). 사용자가 원하면 넣는다
- 2026-10-10 11:34: `/code-review xhigh` 2회차(상한) — 발견 13건. 수정 전 사본을 스크래치 `step41/r2_before/` 에 떴다
  - 고친 버그 1: ① 일정 테스트가 「직전 윈도우와 비교」(`prev_params = params`)를 고정하지 못함 — 그 줄을 지우거나 첫 윈도우와만 비교해도 47개가 통과하고, 그때 Dynamic 이 A → B → A 를 고르면 셋째 구간이 B 로 돌아 에러 없이 틀린다(무거움 — 검사 보강 규칙) → 테스트를 A · A · B · B · A 로(키 = 셋째 · 다섯째) + 「모두 같으면 빈 일정」 테스트. 변형 M6(그 줄 삭제) → 1 failed, 복원 뒤 통과(사본과 `diff -q` 동일)
  - 사용자에게 올린 버그 1: ② 파라미터가 **바뀌는** 경계에서도 새 전략 객체가 유지일 대기 상태를 버린다(Dynamic QQQ w1 → w2 · TQQQ w0 → w3 경계) — 1회차에 고친 같은 자리라 규칙대로 고치지 않고 다시 설계할지 사용자에게 묻는다. 깊은 수정은 엔진의 전략 교체 지점에서 새 전략을 앞쪽 행으로 데우는 것(리뷰 제안)
  - 반영한 그 외 8: ④ 판단 문구 WFE 서술과 대시보드 WFE 설명에 「Fixed(4P)의 값은 과최적화를 재지 않는다」 ⑥ `build_params_schedule` 반환 설명 ⑦ 대시보드 IS 시작 설명 · `eval_ma_window` 설명을 「모든 모드의 이동평균 중 최댓값」으로 ⑧ `min_trades` 를 키워드로 ⑨ 보고서 §2.5 의 TQQQ 고원 밖 윈도우에 w1 추가(w1 · w3 ~ w10) ⑩ 점검 보고서 1-9 를 처리함으로, 19절 목록에서 삭제 ⑪ 「모두 같으면 빈 일정」 경계 테스트 ⑫ 이 계획서의 범위 — 바뀐 파일에 `src/qbt/backtest/walkforward.py` · `tests/qbt/test_walkforward_schedule.py` 가 더해졌고(1회차 ⑧ 수정), DoD 의 테스트 줄을 「해당 없음」에서 실제로 고쳤다
  - 미조치 3: ③ 판단 문구의 수익 집중도가 Dynamic 값만 서술(4P 의 PC 0.7702 는 표에만 있다) — 표시 개선(기준 3) ⑤ 메타에 Fixed 파라미터 미기록 — 1회차 ⑩ 과 같다(기준 3) ⑬ `_window_params` 와 전략 생성이 같은 네 필드를 따로 읽는다 — 정리(기준 3)
  - 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=868, failed=0, skipped=0
- 2026-10-10 11:39: 수정분 검증(`general-purpose` 서브에이전트, 2회차 수정분 diff 7 hunk 와 각 hunk 가 겨냥한 지적만 전달) — hunk 7개 모두 ① ② ③ 에 답. 바뀐 결과는 (a) 의 의도한 문장 추가뿐(옛 / 새 `_describe_wfe` 를 9개 입력으로 비교, 현재 결과로 판단 문구 렌더), 키워드화한 호출의 인자 묶임 동일(AST 비교), 테스트 38 passed, 위험한 쪽으로 바뀐 것 0. 발견 5건(무거움 0)
  - L1 `_describe_wfe` 의 꼬리 문장이 두 모드 중 큰 · 작은 값으로 골라 4P 값 하나로 판정이 나올 수 있다 — 지금 결과는 Dynamic 만으로도 같은 분기라 영향 없음. 원래 있던 결함이고 점검 보고서 1-10 이 다룬다 → 1-10 행에 「꼬리 문장에서 Fixed 값을 뺀다」를 덧붙인다(미룬 지적 파일과 두 벌을 만들지 않는다)
  - L2 사후 확정 단서가 빠진 해석이 더 있다 — 대시보드 이어 붙인 자본곡선 설명의 「두 곡선이 비슷하면 고정 파라미터로도 충분」, 이어 붙인 자본곡선 판단이 두 모드 중 큰 Calmar 로 「양호」를 판정, README 「과최적화 방어 장치」 소개 / L3 연구 보고서 §2.5 첫 문단의 IS 시작 설명에 4P 가 빠짐(값은 같다) — 문구라 사용자에게 지금 고칠지 묻는다(Calmar 판정은 코드라 1-10 과 함께)
  - L4 새 WFE 경고 문장을 고정하는 테스트 없음 — 그 외(기준 3), 판단 모듈 테스트 보강은 6단계(2-26)
  - L5 점검 보고서에서 1-9 를 처리함으로 바꾸며 「파라미터가 바뀌는 경계의 대기 상태」 결정이 할 일 목록에서 빠졌다 — 2회차 ② 와 함께 사용자에게 묻고 답에 따라 점검 보고서에 적는다
- 2026-10-10 11:42: 사용자 결정 — ① 리뷰 3회차 없이 마무리 ② 파라미터가 바뀌는 경계의 대기 상태 유실은 받아들인다(파라미터가 바뀌면 밴드가 달라져 새 전략이 처음부터 세는 것이 Dynamic 의 뜻) — 이유를 `build_params_schedule` 주석과 점검 보고서 1-9 행에 적었다 ③ 문구 3곳을 지금 고친다 → 대시보드 이어 붙인 자본곡선 설명의 「비슷하면 4P 로도 충분 — 이 비교는 4P 에 유리」, README 「과최적화 방어 장치」 줄에 「Fully Fixed 는 4P 고정, 그 비교는 4P 에 유리」(Scope 의 「README 변경 없음」과 달라졌다), 보고서 §2.5 첫 문단 「Dynamic 그리드와 4P 중 가장 긴 이동평균(지금 둘 다 200일)」. 문구 · 주석만이라 수치 · 결과 파일 변화 없음
- 2026-10-10 11:42: 미룬 지적 — 옮길 것 없음. 1회차 미조치 ⑩ ⑪ · 2회차 미조치 ③ ⑤ ⑬ · 수정분 검증 L4 는 거르는 기준 3, 수정분 검증 L1(판단 문구가 두 모드 중 큰 값으로 판정)은 원래 있던 결함으로 점검 보고서 1-10 이 다루므로 그 행에 덧붙였다(두 벌을 만들지 않는다), L2 · L3 은 사용자 결정으로 고쳤고 L5 는 1-9 행에 결정을 적었다. 이 계획서가 고친 `DEFERRED_FINDINGS.md` 항목 없음
- 2026-10-10 11:42: 근거 승격 — 4P 고정으로 바꾼 이유는 러너 Mode 2 주석, 사후 확정 편향은 판단 모듈 `_HINDSIGHT_NOTE` 주석 · 보고서 §2.5 · §22.3, 정의가 바뀐 날짜와 그 전 정의 · 마지막 결과는 §2.5 · §23.2 기준 3, 같은 파라미터 경계 규칙과 바뀌는 경계를 받아들인 이유는 `build_params_schedule` 주석, 거래 수 하한을 빼는 이유는 러너 주석에 있다
- 2026-10-10 11:43: 문구 수정 뒤 품질 검증 재실행 — Ruff · PyRight 통과, passed=868, failed=0, skipped=0(Validation 줄과 같다). `/commit` — 대상은 unstaged + untracked(이 계획서) 전체, 모두 이 계획서 한 묶음이라 분리 제안 없음. 후보 5개를 옮기고 Done
