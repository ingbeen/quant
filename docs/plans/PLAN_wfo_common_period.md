# Implementation Plan: 워크포워드 · 고원 그리드의 평가 기간 통일 — 재실행과 비율 지표 자릿수, 연구 보고서 반영

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-10 09:04
**마지막 업데이트**: 2026-10-10 09:04
**관련 범위**: backtest(`engines/backtest_engine`), scripts(러너 4 · 고원 대시보드), tests, storage/results(워크포워드 · 고원 · 단일 · 포트폴리오), docs/research
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/research/전략_검증_보고서.md`, `docs/AUDIT_REPORT.md`

---

## 1) 목표(Goal)

- [ ] 목표 1: **그리드의 평가 기간 통일** — 그리드 탐색이 모든 조합을 같은 기간(가장 긴 이동평균이 계산되는 첫날부터)으로 평가한다. 고원 러너의 이동평균 실험도 같다(감사 보고서 1-11, 결정 1 (가))
- [ ] 목표 2: **비율 지표 자릿수** — Calmar · Sharpe · Sortino 를 모든 저장물에서 `ROUND_RATIO`(4자리)로 저장하고, 러너에 숫자로 적힌 자릿수를 `ROUND_*` 상수로 바꾼다. 워크포워드 러너의 반올림 분기 오류와 이어 붙인 자본곡선 저장을 바로잡는다(3-17 · 3-7 · 2-7 · 2-10)
- [ ] 목표 3: **재실행** — 워크포워드(QQQ · TQQQ) · 고원 · 단일 · 포트폴리오 러너를 지금 데이터로 다시 돌린다(2-19, 2-1 의 남은 TQQQ 워크포워드). 단일 · 포트폴리오는 비율 지표 자릿수 밖의 값이 그대로임을 대조한다
- [ ] 목표 4: **연구 보고서 반영** — 재실행 결과로 `전략_검증_보고서.md` 의 워크포워드 결론(R1 · G.7.3 · G.8.1), 운영 점검표의 「현재 상태」(R6), 고원 표(R8)를 고친다. 「워크포워드가 4P 를 다시 찾는다 → 동결 원칙을 직접 지지한다」는 결론은 철회한다(결정 1)

## 2) 비목표(Non-Goals)

- **운영 점검표(§22.3)의 비교 대상을 새로 정하는 것** — 결정 1 대로 재실행 결과를 본 뒤 사용자가 정한다. 이 계획서는 「현재 상태: 정상」 문구만 지우고, 완료 보고에 결과와 선택지를 낸다
- **워크포워드의 다른 정리** — 최적 선택의 정렬(1-8) · 유지일 대기 상태(1-9) · 짧은 마지막 OOS(2-20) · `rolling_is_months`(6-1) · 결과 필드 정리(6-11 · 6-12)는 지금 결과를 바꾸지 않거나 다른 단계(감사 보고서 19절 10 · 11)다
- **동적 import 테스트 정리**(10절 3) — 5단계(기계적 정리)
- **연구 문서 경량화**(18-D-R) — 12단계. 이 계획서는 결론 · 수치만 고친다
- **대체 판 시계열 재생성**(결정 20) — 다음 시세 갱신 때

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`docs/AUDIT_REPORT.md`(2026-10-09 재검증판) 「A. 먼저 볼 것」 4 · 5 · 7 번과 관련 항목이다.

- **1-11 그리드가 조합마다 다른 기간을 평가한다** — `engines/backtest_engine.py` `_run_backtest_for_grid` 가 조합마다 자기 이동평균으로 `filter_valid_rows` 를 해, 이동평균 기간이 짧은 조합일수록 일찍 시작한다. QQQ 시세(QQQ · TQQQ 워크포워드 공통 신호) 기준 첫 유효일: 100일선 1999-07-30 · 150일선 1999-10-11 · 200일선 1999-12-21(2026-10-10 실측). 워크포워드 IS 는 늘 데이터 첫날부터라 모든 윈도우가 이 차이를 안고 고른다
  - 감사 재현: 평가 시작일을 맞추면 QQQ 11개 윈도우 중 9개의 선택이 (150, 0.05, 0.03, 3)으로 바뀌고 4P (200, 0.03, 0.05, 3)은 한 번도 안 뽑힌다. TQQQ 는 11개 중 5개가 바뀐다
  - 연구 보고서 G.7.3 「IS 가 14년을 넘어서면 독립적인 최적화 절차가 4P 를 재발견한다」는 이 차이 위에서 나왔다(같은 절이 초기 윈도우의 `ma=100` 선택을 「SMA200 의 워밍업 손실」로 설명한다 — 그 손실이 곧 기간 차이다)
- **고원 러너의 이동평균 실험도 같다** — `scripts/backtest/run_param_plateau_all.py` 실험 4 가 이동평균 값마다 따로 계산 · 필터해, QQQ 는 50일선 1999-05-19 부터 300일선 2000-05-15 부터다. 감사 재현: 공통 시작일이면 QQQ 정점이 250 → 200(고원 (200, 250) 은 그대로). 나머지 세 실험은 모두 200일선이라 이미 같은 기간이다
- **3-17 비율 지표 자릿수가 저장물마다 다르다** — Calmar 는 단일 `summary.json` · 고원 CSV · 포트폴리오 `summary.json` 이 2자리, 워크포워드 · 그리드 CSV 가 4자리다(채택 조합 `summary.json` 0.62 ↔ `combo_runs.csv` 0.6165). 고원 판정도 2자리로 깎인 값에서 한다(SPY 매수 버퍼 고원: 2자리 (0.02, 0.05) / 원값 (0.01, 0.05)). 포트폴리오는 Sharpe · Sortino 도 `ROUND_PERCENT` 다
- **3-7** — `run_walkforward.py` · `run_single_backtest.py` · `run_param_plateau_all.py` · `runners.py` 가 자릿수 2 · 4 를 숫자로 적는다(자릿수 SoT 는 `constants.py` `ROUND_*`)
- **2-7** — `run_walkforward.py` `_save_results` 의 `endswith("_pct")` 2자리 분기가 먼저 걸려 `*_buffer_zone_pct` 4자리 분기에 닿지 않는다(0.025 → 0.02, 지금 그리드 0건)
- **2-10** — 이어 붙인 자본곡선(`walkforward_equity_*.csv`, 열 Date · equity · position)의 equity 가 실수로 저장되고(`10000000.0`), 없는 열의 반올림 키 4개(`buy/sell_buffer_pct` · `upper/lower_band`)가 있다
- **2-19** — 워크포워드 · 고원 결과는 2026-08-21 데이터 기준이고 단일 결과 · 시세는 2026-09-24 다. TQQQ 합성을 다시 만든 뒤(2-1, 2026-10-09) TQQQ 워크포워드는 아직 다시 돌리지 않았다
- **R1 · R6 · R8** — 연구 보고서의 워크포워드 결론이 지금 결과와 반대인 채로 12곳에 현재형으로 있고(R1), 운영 점검표 두 곳이 「현재 상태: 정상」이다(R6). 고원 표 G.7.2 의 이동평균 행이 기간 차이 위에서 나왔다(R8). 위치는 감사 보고서 13-A 표

### 설계 결정

- **그리드의 평가 기간**: `run_grid_search` 가 이동평균을 모두 계산한 뒤 **가장 긴 이동평균 열로 한 번** `filter_valid_rows` 한다(단순이동평균은 한 번 유효해지면 그 뒤로 유효하므로 가장 긴 열 하나면 된다). `_run_backtest_for_grid` 의 조합별 필터는 지운다. 워크포워드는 IS 를 `run_grid_search` 에 넘기므로 따로 고치지 않는다. 워크포워드 그리드의 가장 긴 이동평균은 200일이라 평가 시작은 4P 단일 백테스트와 같은 날이다
- **고원 러너**: 이동평균 실험만 고친다 — 값 전부의 이동평균을 계산한 뒤 가장 긴 열로 한 번 자르고 모든 값을 그 구간으로 돈다. 유지일 · 매도 버퍼 · 매수 버퍼 실험은 지금처럼 200일선 구간이다(이미 같은 기간이고, 4P 단일 백테스트와 시작일이 같다). 그래서 이동평균 탭의 4P 점은 다른 탭보다 늦게 시작해 Calmar 가 다르다 — 고원 대시보드 이동평균 탭에 그 사실을 캡션 한 줄로 적는다
- **비율 지표**: Calmar · Sharpe · Sortino 를 `ROUND_RATIO` 로. 단일 대시보드는 Calmar 를 `:.2f` 로 표시하고, 포트폴리오 대시보드는 저장값을 그대로 표시하므로 4자리가 보인다(그리드 CSV 와 같은 값)
- **워크포워드 러너 반올림**: 윈도우 CSV 는 「열 이름 → 자릿수」 사전 하나로(분기 순서에 기대지 않는다), 이어 붙인 자본곡선은 equity 정수 변환 + 없는 열 키 삭제

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」(결과 파일 덮어쓰기 · 소요 시간 · 대시보드는 사용자가 실행 · `download_data.py` 금지) · 「가격 반올림 자릿수」
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [ ] 그리드 탐색의 모든 조합이 같은 기간을 평가한다 — 짧은 이동평균 조합의 결과가 긴 이동평균 유효 구간으로 자른 단독 실행과 같다(재현 테스트가 수정 전 실패 · 수정 후 통과)
- [ ] 고원 이동평균 실험의 모든 값이 같은 시작일이다(스크래치에서 러너 함수의 `period_start` 를 세어 확인)
- [ ] Calmar · Sharpe · Sortino 가 모든 저장물에서 4자리이고, 러너 4곳 · `runners.py` 에 반올림 자릿수 숫자가 남지 않는다(`grep`)
- [ ] 재실행 대조: 단일 14 · 포트폴리오 5 의 `summary.json` 에서 비율 지표 밖의 값이 그대로이고 결과 CSV 는 git diff 0. 워크포워드 · 고원 결과는 새 값(수치는 진행 로그)
- [ ] 연구 보고서 반영 — R1 위치 전부(감사 보고서 13-A R1 의 목록) · G.7.3 · G.8.1 · R6 두 곳 · G.7.2 의 바뀐 칸을 재실행 결과로 고쳤다
- [ ] 회귀/신규 테스트 추가
- [ ] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [ ] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [ ] 자동 포맷 적용 완료
- [ ] 필요한 문서 업데이트 — `src/qbt/backtest/CLAUDE.md`(`run_grid_search` 설명) · `docs/AUDIT_REPORT.md`(처리 표시) · `docs/COMMANDS.md`(변경 없음 — 실행 명령 · 옵션 그대로) · `README.md`(변경 없음) · `scripts/CLAUDE.md`(변경 여부 확인) · `tests/CLAUDE.md`(변경 없음)
- [ ] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [ ] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/engines/backtest_engine.py` — `run_grid_search` 의 한 번 자르기, `_run_backtest_for_grid` 의 조합별 필터 삭제
- `src/qbt/backtest/walkforward.py` — 그리드의 MA 처리를 설명하는 docstring 이 바뀐 동작과 어긋나면 그 문장만
- `src/qbt/backtest/runners.py` — 반올림 자릿수 상수
- `scripts/backtest/run_param_plateau_all.py` — 이동평균 실험의 한 번 자르기, 반올림 상수(Calmar 4자리)
- `scripts/backtest/run_walkforward.py` — 반올림 사전 · 상수, 이어 붙인 자본곡선 저장
- `scripts/backtest/run_single_backtest.py` · `scripts/backtest/run_portfolio_backtest.py` — 비율 지표 `ROUND_RATIO` · 숫자 자릿수를 상수로
- `scripts/backtest/app_parameter_stability.py` — 이동평균 탭 캡션 한 줄
- `tests/qbt/test_buffer_zone_run.py` — 평가 기간 재현 테스트
- `storage/results/backtest/**`(워크포워드 · 고원 · 단일) · `storage/results/portfolio/**/summary.json` · `storage/results/meta.json` — 재실행
- `docs/research/전략_검증_보고서.md` — R1 · R6 · R8 · G.7.3 · G.8.1
- `src/qbt/backtest/CLAUDE.md` · `docs/AUDIT_REPORT.md`
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · CLI 옵션 그대로)
- `README.md`: 변경 없음 (그리드 평가 기간 · 자릿수를 적은 곳이 없다)

### 데이터/결과 영향

- 워크포워드(`buffer_zone_qqq` · `buffer_zone_tqqq` 의 `walkforward_*` · `wfo_windows_*`): IS 선택 · OOS 성과 · 이어 붙인 자본곡선이 바뀐다 — 평가 기간 통일과 지금 데이터(2026-09-24) 두 원인이 겹친다. 원인을 가르려고 Phase 0 에서 지금 코드로 먼저 한 번 돌려 둔다
- 고원(`param_plateau/*.csv`): 이동평균 실험은 기간 통일, 전 실험은 지금 데이터 · Calmar 4자리로 바뀐다
- 단일 · 포트폴리오 `summary.json`: Calmar(포트폴리오는 Sharpe · Sortino 도) 자릿수만 바뀐다
- 대시보드: 워크포워드 판단 문구는 결과에서 다시 만들어지고(`walkforward_verdict.py`), 포트폴리오 표 · 지표의 Calmar · Sharpe · Sortino 가 4자리로 보인다

## 6) 단계별 계획(Phases)

### Phase 0 — 평가 기간 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [ ] **코드를 고치기 전에** 지금 결과 파일을 스크래치에 복사하고, 지금 코드로 `run_walkforward.py` · `run_param_plateau_all.py` 를 돌려 그 결과도 스크래치에 복사한다(데이터 갱신 효과만 반영된 값 — Phase 3 의 원인 분리에 쓴다)
- [ ] `tests/qbt/test_buffer_zone_run.py` — 이동평균 기간이 다른 두 조합의 그리드 결과에서, 짧은 쪽 조합의 CAGR · MDD · 거래 수가 「긴 이동평균의 첫 유효일부터 자른 데이터로 돌린 단독 실행」과 같다(지금은 짧은 쪽이 일찍 시작해 다르다)

**Validation**:

- [ ] `poetry run pytest tests/qbt/test_buffer_zone_run.py` — 실패가 새 재현 테스트뿐이다(레드)

---

### Phase 1 — 그리드 평가 기간 통일(그린 유지)

**작업 내용**:

- [ ] `backtest_engine.py` — `run_grid_search` 한 번 자르기, `_run_backtest_for_grid` 필터 삭제
- [ ] `run_param_plateau_all.py` — 이동평균 실험의 한 번 자르기
- [ ] `app_parameter_stability.py` — 이동평균 탭 캡션

**Validation**:

- [ ] `poetry run pytest tests/qbt/test_buffer_zone_run.py tests/qbt/test_walkforward_selection.py tests/qbt/test_walkforward_schedule.py` — 전부 통과
- [ ] 스크래치에서 고원 러너의 실험 함수를 불러 이동평균 실험 행의 `period_start` 가 자산마다 하나인지 확인

---

### Phase 2 — 비율 지표 자릿수와 반올림 상수(그린 유지)

**작업 내용**:

- [ ] 단일 · 포트폴리오 · 고원 러너의 Calmar(포트폴리오는 Sharpe · Sortino 도) → `ROUND_RATIO`, 숫자 자릿수 → `ROUND_PERCENT` · `ROUND_RATIO`(3-7 의 위치 전부, `runners.py` 포함)
- [ ] `run_walkforward.py` — 윈도우 CSV 반올림 사전, 요약 JSON 반올림의 숫자 → 상수, 이어 붙인 자본곡선 equity 정수 · 없는 열 키 삭제

**Validation**:

- [ ] `grep` — 다섯 파일에 `round(…, 2)` · `round(…, 4)` · 자릿수 숫자 사전 값이 남지 않는다(메타데이터의 파라미터 기록용 `round(x, 4)` 처럼 저장 자릿수가 아닌 것은 진행 로그에 이유와 함께 남긴다)

---

### Phase 3 — 재실행과 대조

**작업 내용**:

- [ ] 수정 코드로 `run_walkforward.py`(약 6분) · `run_param_plateau_all.py` · `run_single_backtest.py` · `run_portfolio_backtest.py` 실행
- [ ] 대조 스크립트(스크래치) — 단일 · 포트폴리오 `summary.json` 의 비율 지표 밖 값 동일 · 결과 CSV git diff 0. 워크포워드 윈도우별 선택(전 · 데이터만 · 수정 후 세 벌), Dynamic · Fixed 이어 붙인 CAGR · MDD · Calmar, 고원 범위 24칸(전 · 후)

**Validation**:

- [ ] 대조 결과 — 바뀐 키는 비율 지표뿐 · CSV 차이 0. 워크포워드 · 고원 수치와 원인 분리 결과는 진행 로그

---

### Phase 4 — 연구 보고서 반영

**작업 내용**:

- [ ] §2.5 를 날짜 붙은 「워크포워드 현황」 단락으로 — 지금 결과 · 평가 기간을 맞춘 이유 · Fixed 는 첫 윈도우 값이지 4P 가 아니라는 점
- [ ] R1 의 나머지 자리(감사 보고서 13-A R1 의 위치 목록)에 「[이전 결과 — 지금은 성립하지 않는다 → §2.5]」 한 줄씩(그 시점 결정의 근거라 본문은 이력으로 남긴다)
- [ ] G.7.3 — 「4P 재발견」 결론 철회와 이유(평가 기간 차이), 새 선택 표. G.8.1 표의 수치 갱신
- [ ] §22.3 · §23.2 의 「현재 상태: 정상」 삭제(R6)
- [ ] G.7.2 — 재실행 고원 값으로 바뀐 칸 갱신(이동평균 행 · 3-17 로 바뀌는 칸)

**Validation**:

- [ ] 보고서의 워크포워드 · 고원 수치를 결과 파일에서 다시 읽어 대조(스크래치 스크립트) — 불일치 0

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [ ] 문서 — `src/qbt/backtest/CLAUDE.md`(`run_grid_search` · `filter_valid_rows` 설명) · `docs/AUDIT_REPORT.md`(처리 표시). `docs/COMMANDS.md` 변경 없음
- [ ] 자동 포맷 적용 (`poetry run black .`)
- [ ] 변경 기능 및 전체 플로우 최종 검증
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

- **연구 결론이 바뀐다** — 「워크포워드가 4P 를 다시 찾는다」가 철회되고, 운영 점검표의 비교 대상이 비게 된다. 결정 1 이 받아들인 결과다. 완화: 점검표 비교 대상은 이 계획서에서 정하지 않고 결과와 선택지를 완료 보고에 낸다
- **원인이 둘 겹친다** — 평가 기간 통일과 데이터 갱신(08-21 → 09-24, TQQQ 합성 재생성)이 같은 재실행에 들어간다. 완화: Phase 0 에서 코드를 고치기 전에 지금 데이터로 먼저 돌려 두 효과를 따로 적는다(워크포워드가 두 번 돌아 약 6분이 더 든다)
- **실행 시간** — 워크포워드 약 6분은 Bash 기본 제한(2분)을 넘는다. 완화: 제한 시간을 늘리거나 백그라운드로 돌린다
- **결과 파일 덮어쓰기** — git 추적이라 되돌릴 수 있다. 착수 전에 작업 트리가 깨끗해야 대조가 쉽다(직전 계획서 변경을 사용자가 먼저 커밋한다). `download_data.py` 는 돌리지 않는다
- **이동평균 탭의 4P 점이 다른 탭과 다르다** — 설계상 그렇다(시작일이 늦다). 완화: 캡션 한 줄

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 1-11 · 2-7 · 2-10 · 2-19 · 3-7 · 3-17 · 13-A R1 · R6 · R8, 결정 1 (가)(2026-10-09 사용자 「진행」으로 추천안 확정)

### 진행 로그 (KST)

- 2026-10-10 09:04: 계획서 작성(Draft)
