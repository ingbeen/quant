# Implementation Plan: 판단일에 들어오는 자산을 리밸런싱 편차 판정에서 제외

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-10-03 23:50
**마지막 업데이트**: 2026-10-03 23:50
**관련 범위**: backtest(포트폴리오 리밸런싱 정책 · 판단일 함수), storage/results/portfolio, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `docs/research/전략_검증_보고서.md`, `docs/research/Q2_2XS_보완_전략_설계.md`, `docs/DEFERRED_FINDINGS.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 `/impl-plan` 스킬을 따릅니다.

- 품질 검증 명령은 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: 월말 판단일에 보유 0 에서 새로 들어오는 자산(같은 날 진입 신호가 난 자산)을 리밸런싱 편차 판정에서 뺀다 — 설계서 결정 D30. 남은 자산의 편차가 10% 를 넘을 때만 리밸런싱이 일어나고, 일어나면 지금처럼 진입 자산을 포함한 보유 자산 전부를 맞춘다
- [x] 목표 2: 리밸런싱 판단일 함수가 (연, 월)로 비교하고, 범위 밖 인덱스에는 `ValueError` 를 던진다 — 미룬 지적(`docs/DEFERRED_FINDINGS.md`) 「판단일 함수가 연도를 비교하지 않고 …」, 결정 D32
- [x] 목표 3: 기존 포트폴리오 실험 4개를 다시 산출하고, 결과가 착수 전 임시 측정값과 최종 자본까지 같음을 확인한다
- [x] 목표 4: 규칙 변경과 수치를 `docs/research/전략_검증_보고서.md` 부록 L 에 남긴다

## 2) 비목표(Non-Goals)

- **엔진 확장(매매법별 장부 · 종목 단위 상계 · 비중이 바뀌는 매매법)** — 후속 계획서 ②-2 가 맡는다. 이 계획서는 결과 수치가 바뀌는 변경만 따로 담아, 수치 변화의 원인을 「D30 규칙」과 「엔진 확장」으로 가른다(D30 · D27)
- **「1주 미만 리밸런싱 주문 → 검사기 중단」 수정** — 계획서 ②-2 에서 검사 규칙을 다시 쓰며 함께 고친다(D32). 결과 수치와 무관하다
- **「체결 전후 비교 표의 매수일 누락」 수정** — 미룸 유지(D32)
- **임계값(10%) · 판단 시점 변경** — 판정에서 뺄 자산만 바뀐다
- **월중 재진입 동작 변경** — 월중에는 리밸런싱 판정이 없으므로 이 변경과 무관하다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 지금 엔진은 판단일에 진입 신호가 난 자산을 `ProjectedPortfolio.active_assets` 에 넣고, 보유가 0 이라 편차를 `|0 ÷ 목표 − 1| = 100%` 로 계산한다([portfolio_rebalance.py:47-55](../../src/qbt/backtest/engines/portfolio_rebalance.py#L47-L55)). 그래서 진입 신호 하나가 그날 보유 자산 전부의 리밸런싱을 일으킨다. 계획서 ① 에서는 20년에 한 번(2009-05-29)이라 받아들였다(부록 L.5)
- 보완 전략의 HAA 는 월말에 종목을 바꾸고(예비 연 약 7회), D19 는 「종목이 바뀔 때만 사고팔고, 남은 종목은 편차 10% 를 넘을 때만 맞춘다」로 정했다. 지금 동작을 그대로 쓰면 종목이 바뀔 때마다 남은 종목도 다시 맞춘다. 규칙 하나로 D19 를 지키기 위해 사용자가 D30 을 정했다(2026-10-03, S3)
- 판단일 함수 `is_last_trading_day_of_month` 는 다음 거래일과 「월」만 비교해, 이웃한 두 거래일이 정확히 12개월 배수만큼 떨어지면 판단일을 놓친다. 범위 밖 인덱스(음수 포함)에도 조용히 False 를 돌려준다. 공식 데이터에는 이런 공백이 0건이라 결과는 바뀌지 않는다

### 착수 전 임시 측정 (세션 스크래치, 저장소 무변경)

엔진은 그대로 두고 `portfolio_engine.DEFAULT_REBALANCE_POLICY` 만 측정 동안 「보유 0 인 active 자산을 편차 판정에서 빼는」 정책으로 바꿔 끼워 4개 실험을 돌렸다. `current` 는 저장소의 공식 결과를 최종 자본까지 그대로 재현했다. 도구 출력 그대로:

```
label,experiment,final_capital,cagr,mdd,calmar,sell_trades,rebalanced_days,violations,signal_buy+rebalance_rows,dates
current,portfolio_d1,106497267,11.505067,-26.428056,0.435335,11,0,0,1,2009-05-29
current,portfolio_d1_2x,359932361,20.217474,-46.369999,0.436003,10,0,0,1,2009-05-29
current,portfolio_q2,79587110,10.019898,-15.718483,0.637460,127,59,0,1,2009-05-29
current,portfolio_q2_2xs,163221216,15.430201,-27.931119,0.552438,148,74,0,1,2009-05-29
d30,portfolio_d1,106497267,11.505067,-26.428056,0.435335,11,0,0,0,
d30,portfolio_d1_2x,359932361,20.217474,-46.369999,0.436003,10,0,0,0,
d30,portfolio_q2,79638899,10.023193,-15.718572,0.637666,126,59,0,0,
d30,portfolio_q2_2xs,163205615,15.429634,-27.931110,0.552417,147,73,0,0,
```

- Q-2 · Q-2-2XS 의 `d30` 최종 자본은 S2 가 잰 값(부록 L.5 의 163,205,615, 계획서 ① 진행 로그의 79,638,899)과 같다
- 4개 실험 모두 판단일 진입은 2009-05-29 하루뿐이다. D-1 · D-1-2X 는 자산이 하나라 매매량이 같고, 상태 로그의 그날 `{자산}_pending_reason` 표기만 `signal_buy+rebalance` → `signal buy` 로 바뀔 것으로 본다
- 측정 정책은 「보유 0 인 active 자산」을 뺐고, 구현은 「그날 진입 신호가 난 자산」을 뺀다. 두 집합은 진입 체결이 0주로 끝나 신호 상태만 매수인 자산이 있을 때만 갈리며, 공식 결과에는 그런 자산이 없다(4개 실험 모두 정합성 위반 0건 — 0주 진입이면 검사기 규칙 1 이 잡는다). 그래서 기대값으로 쓸 수 있다

**완료 조건으로 고정하는 기대값** (`summary.json` 기준, 반올림은 결과 파일 그대로):

| 실험 | 최종 자본 | CAGR | MDD | Calmar | 매도 체결 |
| --- | --- | --- | --- | --- | --- |
| portfolio_d1 | 106497267 (불변) | 11.51 | -26.43 | 0.44 | 11 |
| portfolio_d1_2x | 359932361 (불변) | 20.22 | -46.37 | 0.44 | 10 |
| portfolio_q2 | 79587110 → **79638899** | 10.02 | -15.72 | 0.64 | 127 → **126** |
| portfolio_q2_2xs | 163221216 → **163205615** | 15.43 | -27.93 | 0.55 | 148 → **147** |

리밸런싱한 날: Q-2 59 (불변), Q-2-2XS 74 → **73**.

### 구현 방식

- `ProjectedPortfolio` 에 그날 진입 신호 자산 집합(`entering_assets`, 기본값 빈 집합)을 둔다. `compute_projected_portfolio` 가 `ENTER_TO_TARGET` 자산을 이 집합에 넣는다
- `RebalancePolicy.should_rebalance` 가 이 집합의 자산을 판정에서 건너뛴다. `build_rebalance_intents` 는 바꾸지 않는다 — 판정이 걸리면 진입 자산도 목표 금액으로 맞추고, `merge_intents` 의 「ENTER + INCREASE → ENTER(리밸런싱 목표)」 규칙이 지금처럼 적용된다
- 기본값이 있는 필드라 `ProjectedPortfolio(...)` 를 직접 만드는 기존 테스트는 그대로 동작한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)
- `docs/MEMORY.md`
- `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `docs/CLAUDE.md`
- `.claude/rules/python.md` (전역 `~/.claude/rules/python.md`)
- `docs/research/Q2_2XS_보완_전략_설계.md` 0장 「세션 인계 규칙」

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 판단일 진입 자산이 편차 판정에서 빠진다 — 남은 자산이 10% 이하면 진입 자산만 사고, 남은 자산이 10% 를 넘으면 진입 자산까지 전부 맞춘다 (Phase 0 테스트 통과)
- [x] 판단일 함수가 (연, 월)로 비교하고 범위 밖 인덱스에 `ValueError` 를 던진다 (Phase 0 테스트 통과)
- [x] 재산출한 4개 실험의 `summary.json` 이 Context 기대값과 같다 (최종 자본 · CAGR · MDD · Calmar · 매도 체결 · 기간), 리밸런싱한 날 수가 같다, 정합성 위반 0건
- [x] portfolio_d1 · portfolio_d1_2x 는 `state_log.csv` 의 2009-05-29 `pending_reason` 표기 외 결과 파일 git diff 0
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/research/전략_검증_보고서.md`(부록 L) · `src/qbt/backtest/CLAUDE.md`(판단일 진입 서술) · `docs/research/Q2_2XS_보완_전략_설계.md`(진행 상태) · `README.md`(변경 없음 — 리밸런싱 서술이 「월말 판단」 수준이라 해당 없음) · `docs/COMMANDS.md`(변경 없음 — 실행 명령 · CLI 옵션 변경 없음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관.
      `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 스킬 "미룬 지적 옮기기" 참고) — 옮긴 것 0건(전부 거름), 판단일 함수 항목 삭제
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/engines/portfolio_planning.py` — `ProjectedPortfolio.entering_assets` 필드, `compute_projected_portfolio` 가 채움
- `src/qbt/backtest/engines/portfolio_rebalance.py` — `should_rebalance` 가 `entering_assets` 를 건너뜀, `is_last_trading_day_of_month` 의 (연, 월) 비교 · 범위 검증
- `tests/qbt/test_portfolio_planning.py` — 진입 자산 제외 판정 테스트, `compute_projected_portfolio` 의 `entering_assets` 테스트
- `tests/qbt/test_portfolio_backtest_scenarios.py` — 엔진 수준 시나리오(판단일 재진입 + 남은 자산 편차 이하 / 초과), 판단일 함수 경계 테스트
- `storage/results/portfolio/*` · `storage/results/meta.json` — 재산출
- `docs/research/전략_검증_보고서.md` — 부록 L.5 마지막 두 항목 갱신, L.6 표에 D30 반영 값 추가
- `src/qbt/backtest/CLAUDE.md` — 「재진입 신호가 판단일에 겹치면 …」 서술 갱신
- `docs/research/Q2_2XS_보완_전략_설계.md` — 0.2 진행 상태
- `docs/DEFERRED_FINDINGS.md` — 판단일 함수 항목에 「고치는 중」 표시(착수 시) → Done 때 항목 삭제
- `docs/COMMANDS.md`: **변경 없음** — 실행 명령 · CLI 옵션 변경 없음

### 데이터/결과 영향

- 공식 결과가 바뀐다: Q-2 · Q-2-2XS (기대값은 Context 표, 2009-05-29 이후 경로). D-1 · D-1-2X 는 성과 불변, 상태 로그 표기 1행씩
- 결과 파일 스키마 변경 없음
- `storage/stock/` 데이터는 건드리지 않는다(재다운로드 없음)

## 6) 단계별 계획(Phases)

### Phase 0 — 새 판정 규칙과 판단일 함수 계약을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `docs/DEFERRED_FINDINGS.md` 의 판단일 함수 항목 출처에 「고치는 중: PLAN_rebalance_entering_exclusion」 덧붙임
- [x] 정책 테스트: active 자산 a(편차 5%) · 진입 자산 b(보유 0) → `should_rebalance` False / a 편차 15% · 진입 b → True
- [x] `compute_projected_portfolio` 테스트: `ENTER_TO_TARGET` 자산이 `entering_assets` 에 들어가고, `EXIT_ALL` · 무신호 자산은 들어가지 않는다
- [x] 엔진 시나리오(합성 CSV, 버퍼존 자산 1개 + 보유 자산 1개): 버퍼존 자산의 진입 신호가 월 마지막 거래일에 나고 보유 자산 편차가 **0 보다 크고 10% 이하**(예: 월중 +5%, 상대 편차 약 2.4%) → 다음 거래일 체결이 진입 자산 매수뿐(보유 자산 REDUCE/INCREASE 없음, `rebalanced` False) / 보유 자산 편차가 10% 초과 → 보유 자산도 맞춤(`rebalanced` True). 편차가 정확히 0 이면 지금 코드도 보유 자산에 주문을 만들지 않아 레드가 되지 않으므로 0 을 피한다
- [x] 판단일 함수: 2008-03-31 다음 행이 2009-03-02 → True, 인덱스 −1 · 길이 이상 → `ValueError`, 마지막 행 → False(기존 테스트 유지)

**Validation**:

- [x] 새 테스트가 현행 코드에서 실패함을 확인 (특정 파일 pytest 직접 실행 — `docs/COMMANDS.md` 「테스트 (특정 모듈/파일)」). 실패 메시지를 진행 로그에 남긴다

---

### Phase 1 — 구현 · 재산출 · 기대값 대조(그린 유지)

**작업 내용**:

- [x] `portfolio_planning.py` · `portfolio_rebalance.py` 구현 (Scope 참고)
- [x] 포트폴리오 테스트 파일만 pytest 직접 실행해 통과
- [x] 변형 확인: `should_rebalance` 의 진입 자산 건너뛰기를 지우면 Phase 0 정책 · 시나리오 테스트가 실패하는지, 판단일 함수를 월만 비교로 되돌리면 경계 테스트가 실패하는지 확인하고 사본과 diff 로 복원 확인
- [x] 결과 재산출 전 작업 트리 확인(`storage/` 변경 없음) 후 `run_portfolio_backtest.py` 전체 실행 (명령은 `docs/COMMANDS.md`)
- [x] 4개 실험 `summary.json` 을 Context 기대값과 대조 — 표의 모든 칸, 행 수 4 를 따로 센다. 리밸런싱한 날 수 대조
- [x] portfolio_d1 · portfolio_d1_2x 결과 파일 git diff 확인 (DoD 조건)

**Validation**:

- [x] 기대값 대조 결과를 진행 로그에 도구 출력 그대로 붙인다
- [x] 정합성 위반 0건 (러너가 멈추지 않음)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **`/commit` 이 «맨 마지막»인 것은 의도다.** 그 스킬은 「후보 뒤에는 아무것도 덧붙이지 말 것」으로
> 끝나므로 **호출하는 순간 그 턴이 거기서 닫힌다.** 중간에 두면 뒤에 적힌 항목이 그 벽 너머에 남는다 —
> 실제로 두 번 그렇게 샜다(`[실측] 2026-09-14` 후보를 계획서에 안 옮김 · `2026-09-16` 옮기고 체크박스를 안 닫음).
> **체크박스와 상태를 먼저 확정하고, 커밋 후보를 마지막에 만든다.**

- [x] `docs/research/전략_검증_보고서.md` — 부록 L.5 의 「판단일 재진입 → 전체 리밸런싱(받아들임)」 서술을 바뀐 규칙으로 갱신(근거: D19 · HAA, 측정값), L.6 표에 D30 반영 값(최종 자본 · 매도 체결 · 리밸런싱한 날)을 추가하고 L.1 표가 그대로인 이유(표시 자릿수에서 같음)를 한 줄
- [x] `src/qbt/backtest/CLAUDE.md` 의 판단일 재진입 서술 갱신
- [x] `docs/research/Q2_2XS_보완_전략_설계.md` 0.2 진행 상태 갱신 (계획서 ②-1 완료)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      `/commit` 은 계획서를 모르고 「후보 뒤에 아무것도 덧붙이지 말 것」으로 끝나므로,
      **대화에만 내면 그 절이 빈 채로 남는다.** 체크박스 갱신이 diff 에 더 들어가지만
      커밋 메시지의 내용을 바꾸지 않는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.
> **고칠 것이 0 인 회차에서 끝낸다** — 고칠 것은 무거운 버그 전부와, 실제 산출물에 나오는 가벼운 버그다.
> 2회차에도 무거운 버그가 나오면 사용자에게 보고하고 3회차 여부를 묻는다 — 나머지 가벼운 버그와
> 「그 외」는 목록만 남기고 고치지 않는다. 무게의 정의는 `/impl-plan` 의 「코드 리뷰」 절이 SoT 다.
> **뒤에 리뷰 회차가 오지 않는 수정은 고치기 «전»에 바꿀 파일을 스크래치에 복사해 두고, 고친 뒤 수정분 검증을
> 거친다** — 절차는 `/impl-plan` 의 「지적을 고칠 때」다.

- [x] `/code-review xhigh` **1회차** (발견 8건 — 버그 0 [무거움 0 · 가벼움 0] · 그 외 8 · 조치: 그 외 3 수정(코드 주석 · 테스트 docstring 이 임시 문서를 가리킴 — 전역 「문서 참조 방향」 위반 · 새 필드로 낡은 docstring · 할 일을 말하지 않는 오류 메시지 — 전역 「사용자 중심」 위반), 그 외 5 목록)
- [x] 수정분 검증 (수정 3건 · 발견 4건 — 무거움 0 · 조치: 고치지 않고 사용자 보고 — 회귀 0 · 위험 방향 전환 0)
- [x] `poetry run python validate_project.py` (passed=559, failed=0, skipped=0)
- [x] 리뷰 · 포맷 이후 결과가 바뀌지 않았음 — 재산출 뒤 엔진 코드가 바뀌었다면 엔진을 메모리에서 다시 돌려 4개 최종 자본이 기대값과 같은지 재대조

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

1. 백테스트 / 판단일 진입 자산의 리밸런싱 편차 판정 제외
2. 백테스트 / 판단일 진입 자산 편차 판정 제외와 판단일 함수 연도 비교·범위 검증, 기존 실험 4개 결과 재산출
3. 백테스트 / 종목 교체형 보완 전략(HAA)에 맞춘 판단일 진입 자산의 리밸런싱 판정 제외
4. 백테스트 / 재진입 신호 하나가 전체 리밸런싱을 일으키던 경계 동작 제거와 전략 검증 보고서 부록 L 갱신
5. 백테스트 / 판단일 진입 자산 판정 제외 반영과 보완 전략 설계서 결정 D29 – D34 기록

## 7) 리스크(Risks)

- **기대값 불일치** — 구현이 「그날 진입 신호 자산」을 빼고 측정은 「보유 0 인 active 자산」을 뺐다. 공식 결과에서는 두 집합이 같다고 보지만(Context), 다르면 원인을 찾기 전에는 진행하지 않는다(기대값을 결과에 맞춰 고치지 않는다)
- **판단일 함수의 예외화가 호출부를 멈춤** — 엔진은 0 이상 길이 미만만 넘긴다(`range(0, n)`). 완화: 범위 검증 테스트 + 4개 실험 재산출이 끝까지 돈다
- **0주 진입 자산의 판정 누락** — 진입 체결이 0주로 끝나면(현금 부족) 다음 판단일에는 진입 신호가 없으므로 그 자산이 다시 판정에 들어와 편차 100% 로 리밸런싱을 일으킨다. 매수를 다시 시도하는 쪽이라 받아들인다
- **대시보드 표시** — 성과 대시보드의 「월초 정기」 표기 등 기존 표시는 바뀌지 않는다. 결과 스키마 변경이 없어 대시보드 확인 단계는 두지 않는다

## 8) 메모(Notes)

- 결정 근거: `docs/research/Q2_2XS_보완_전략_설계.md` 6장 D30 · D32 (2026-10-03, S3)
- 후속: 계획서 ②-2 엔진 확장(매매법별 장부 · 종목 단위 상계 · 비중이 바뀌는 매매법)은 이 계획서가 커밋된 결과와 기존 결과 diff 0 을 완료 조건으로 한다
- 임시 측정 스크립트는 세션 스크래치에만 있다(저장소 밖). 수치는 위 Context 출력이 전부다

### 진행 로그 (KST)

- 2026-10-03 23:50: 계획서 작성. 기대값은 착수 전 임시 측정(`current` 가 공식 결과를 최종 자본까지 재현함을 확인)
- 2026-10-03 23:58: 사용자 승인(「진행해줘」), 착수. 같은 답으로 계획서 ②-2 의 결과 키 K안과 기본값 6개도 확정 — 설계서 D33 · D34
- 2026-10-04 00:01: Phase 0 — 새 테스트 8건이 현행 코드에서 실패: `TypeError: ProjectedPortfolio.__init__() got an unexpected keyword argument 'entering_assets'` 2 · `AttributeError: ... no attribute 'entering_assets'` 2 · 판단일 연도 `assert False is True` 1 · 범위 밖 인덱스 `DID NOT RAISE ValueError` 2 · 시나리오 `assert [datetime.date(2024, 2, 1)] == []` 1. 실패 로그에 현행 동작이 찍힘 — 2024-02-01 에 편차 약 2.3% 인 b 까지 1,118주 매도. 「남은 자산 10% 초과」 시나리오는 현행에서도 통과(회귀 방지용, 의도대로)
- 2026-10-04 00:01: Phase 1 — 구현 후 포트폴리오 테스트 7개 파일 `110 passed`. 변형 확인 ① `should_rebalance` 의 진입 자산 건너뛰기 삭제 → `test_entering_asset_alone_does_not_trigger` · `test_only_entering_asset_trades_when_others_within_threshold` 실패 ② 판단일 함수를 월만 비교로 → `test_true_when_next_row_is_same_month_of_later_year` 실패. 둘 다 사본과 `diff` 로 복원 확인
- 2026-10-04 00:01: 재산출 전 `git status --short storage/` 출력 없음 확인 후 `run_portfolio_backtest.py` 전체 실행, 4개 모두 「정합성 검증 통과」. 기대값 대조(summary.json · equity.csv 직접 읽기, 4행):
  `portfolio_d1 106497267 11.51 -26.43 0.44 11 2005-01-03 2026-09-24 rebalanced_days 0` ·
  `portfolio_d1_2x 359932361 20.22 -46.37 0.44 10 2007-04-09 2026-09-24 rebalanced_days 0` ·
  `portfolio_q2 79638899 10.02 -15.72 0.64 126 2005-01-03 2026-09-24 rebalanced_days 59` ·
  `portfolio_q2_2xs 163205615 15.43 -27.93 0.55 147 2007-04-09 2026-09-24 rebalanced_days 73` → Context 표와 전부 일치
- 2026-10-04 00:01: D-1 · D-1-2X 는 `state_log.csv` 만 바뀜 — 각 1행 1칸: `2009-05-29 qqq_pending_reason signal_buy+rebalance → signal buy`, `2009-05-29 qld_pending_reason signal_buy+rebalance → signal buy`
- 2026-10-04 00:15: 문서 — 보고서 부록 L.2 표에 「판단일 진입 자산」 행, L.5 의 「받아들임」 서술을 바뀐 규칙과 근거로, L.6 끝에 반영 뒤 표(최종 자본 · 매도 체결 · 리밸런싱한 날). 보고서에 적은 「2009-06-01 GLD · TLT 리밸런싱이 없어짐」은 결과 파일로 확인 — HEAD `trades.csv` 의 `2009-06-01 gld rebalance 881주` 가 새 결과에 없고, 새 state_log 의 그날 체결은 `qld ENTER_TO_TARGET` 뿐. `src/qbt/backtest/CLAUDE.md`(ProjectedPortfolio 필드 · should_rebalance · 판단일 함수 · 재진입 서술), 설계서 0.2 · 0.3 갱신. `black .` 115 files unchanged
- 2026-10-04 00:15: 리뷰 1회차 8건 — 버그 0. ① 「10% 초과면 진입 자산까지 맞춘다」 엔진 테스트가 진입 자산의 리밸런싱 포함 여부를 가려내지 못함(매도 선체결로 신호 단독 진입이어도 통과) — 그 외 목록. 같은 계약은 `TestBuildRebalanceIntents`(active 전체 대상) · `TestMergeIntents`(ENTER+INCREASE → 리밸런싱 목표)가 단위로 고정 ② `DEFAULT_REBALANCE_POLICY` 주석 · 엔진 모듈 docstring · 부록 L.1 서술에 진입 자산 제외가 없음 — 그 외 목록 ③ 코드 주석 · 테스트 docstring 이 임시 문서(설계서 D30)를 가리킴 — **수정**(부록 L.5 로) ④ `entering_assets` 기본값 때문에 직접 생성하는 곳이 필드를 빠뜨려도 조용히 옛 판정 — 그 외 목록, 계획서 ②-2 Risks 로 넘김 ⑤ `ProjectedPortfolio` · `compute_projected_portfolio` docstring 에 새 필드 없음 — **수정** ⑥ params_json 이 판정 규칙 변경을 기록하지 않음 — 그 외 목록 ⑦ DEFERRED_FINDINGS 항목의 줄 번호가 낡음 — 항목 삭제로 사라짐 ⑧ 오류 메시지가 할 일을 말하지 않음 — **수정**
- 2026-10-04 00:15: 수정 전 사본(`scratchpad/fix1/`) → 수정 → `black`(오류 메시지 두 줄이 한 줄 암묵 연결로 합쳐짐 — 저장소에 같은 모양 있음, 둠) → 54 passed. 수정분 검증(general-purpose, 수정분 diff 와 지적만 전달): 7 hunk 모두 회귀 0 · 위험 방향 전환 0, `pytest.raises(match="인덱스")` 계속 일치, 새 출처 부록 L.5 가 실재함 확인. 발견 4건(가벼움, 고치지 않음 · 사용자 보고): 보고서 L.5 새 항목이 임시 문서(설계서 D19 · D30)를 가리킴 · 오류 메시지 f-string 암묵 연결 · 빈 목록이면 「0 이상 0 미만」 안내(운영 경로에서 도달 불가) · 테스트의 출처 표기가 전체 경로가 아님
- 2026-10-04 00:15: `validate_project.py` passed=559 failed=0 skipped=0. 엔진을 메모리에서 다시 돌려 4개 최종 자본(106497267 · 359932361 · 79638899 · 163205615)과 매도 체결(11 · 10 · 126 · 147), 위반 0건 재확인 — 재산출 뒤 바뀐 코드는 주석 · docstring · 오류 메시지뿐
- 2026-10-04 00:15: 미룬 지적 — 판단일 함수 항목은 고쳐서 `docs/DEFERRED_FINDINGS.md` 에서 삭제. 옮긴 것 0건, 거른 것: 1회차 ① [기준 3] · ② [기준 3] · ④ [기준 3] · ⑥ [기준 3] · 수정분 검증 (가) L.5 임시 문서 참조 [기준 3 — 문서. 보고서 L.3 · L.8 에도 기존부터 같은 참조가 있어 설계서를 부록으로 통합할 때 함께 정리] · (나) f-string 암묵 연결 [기준 3] · (다) 빈 목록 안내 [기준 2 — 막는 쪽으로만 틀리고 운영 경로에서 도달 불가] · (라) 출처 표기 형식 [기준 3]
