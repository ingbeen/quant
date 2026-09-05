# Implementation Plan: 문서·주석·코드 3자 동기화 — WFO 판단 문구 동적화 + 재점검 지적사항 정리

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

**작성일**: 2026-09-05 19:19
**마지막 업데이트**: 2026-09-05 19:46
**관련 범위**: `scripts/backtest/`, `src/qbt/backtest/`, `tests/qbt/`, 문서 전반(루트·docs·각 CLAUDE.md)
**관련 문서**: 루트 `CLAUDE.md`, `docs/CLAUDE.md`, `docs/COMMANDS.md`, `README.md`, `scripts/CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `tests/CLAUDE.md`, `.claude/rules/python.md`

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

- [x] 목표 1: **WFO 대시보드의 판단 문구를 `walkforward_summary.json` 기반으로 동적 생성**하여, 워크포워드를 재실행해도 문구가 스스로 따라오게 만든다 (같은 사고의 재발 차단)
- [x] 목표 2: 문서가 서술하는 동작과 실제 코드 동작이 어긋난 곳을 전량 일치시킨다
- [x] 목표 3: 이미 끝난 작업의 진행 단계(Phase/RED/GREEN)와 리팩토링 이력을 영구 코드·문서에서 제거한다
- [x] 목표 4: 여러 문서에 복제된 상수값과 자주 바뀌는 목록을 선별 정리한다
- [x] 목표 5: live 제거가 남긴 끊어진 링크와 「근거 승격 목적지」 규약을 복구한다

## 2) 비목표(Non-Goals)

- **포트폴리오 대시보드에 없는 섹션의 신규 구현** — "실험 해설·거래 현황 바차트·거래 내역 테이블"은 문서에만 있고 구현이 없다. 사용자 결정에 따라 **문서를 코드에 맞춘다.** 기능 추가는 이번 범위 밖이다
- **워크포워드·백테스트 재실행 및 데이터 갱신** — `storage/results/`는 건드리지 않는다. 현재 결과 파일이 검증 기준이다
- **`docs/research/` 본문의 과거 기록 수정** — research는 「과거 이력의 기록 위치」로 규정된 폴더다(`docs/CLAUDE.md`). 기준일이 명시된 연구 수치는 그대로 둔다. 단 임시 문서(`docs/plans/`)를 참조하는 2곳은 참조 방향 위반이므로 예외로 정리한다
- **새 설계 문서 신설** — 「설계 결정과 탈락안」의 승격 목적지는 `docs/research/`로 통합한다(사용자 결정). 빈 `docs/DESIGN.md`를 만들지 않는다
- **`app_rate_spread_lab.py`의 "스프레드 모델 변천" 서술과 "복원 방법" 안내 유지** — 아래 근거로 존치한다
  - 루트 `CLAUDE.md`가 금지한 것은 *삭제된 코드의 **스냅샷**(함수 목록·파일 구조)을 문서로 복제*하는 것이며, git 조회 방법 안내는 이에 해당하지 않는다
  - 이 앱은 연구 결과 **열람 전용**이고, 해당 안내는 CSV가 없을 때만 노출되는 경고다. "왜 비었는지"를 알려주는 실질 정보다
  - 다만 **"삭제됨"이라는 과거형 표현**은 현재 상태 서술로 바꾼다 (Phase 3)
- **`pytest.ini` 미사용 마커(slow/integration/unit) 제거** — `tests/CLAUDE.md`가 이미 "참고용"으로 명시하고 있고, `--strict-markers` 하에서 정의를 남기는 편이 안전하다. Notes에 기록만 한다
- **`storage/` 결과 파일·CSV 수정**

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

live 패키지 제거(`fb881ba`) 직후 저장소 전체를 재점검한 결과, 세 종류의 문제가 확인되었다.

**(1) WFO 대시보드가 현재 데이터와 반대되는 판단을 표시한다 — 가장 심각**

`scripts/backtest/app_walkforward.py`의 판단 문구가 하드코딩되어 있고, EMA→SMA 전환(`f836ab5` → `9e22b10`)으로 결과가 재생성되면서 전면 무효화됐다. git 이력으로 원인을 확정했다.

| 문구의 값 | `2318307`(2026-04-01) 당시 실제값 | 현재(SMA) |
| --- | --- | --- |
| QQQ Dynamic / Fixed CAGR | 11.33 / 11.97 | 9.46 / 5.16 |
| QQQ WFE Calmar Robust | 0.9326 | 1.15 / 1.1767 |
| QQQ PC 최대 | 0.4459 | 0.4855 |
| TQQQ Dynamic / Fixed CAGR | 24.84 / 26.27 | 19.38 / 9.25 |
| TQQQ WFE Calmar Robust | 0.19 / 0.04 | 4.5337 / -0.0436 |
| TQQQ PC 최대 | 0.6903 | 0.9024 |

문구는 **작성 당시 전부 정확했다.** 파라미터 추이 서술도 EMA 시절 CSV와 완전히 일치한다. 문제는 수치가 아니라 **해석의 방향**이다. 현재 문구는 "Fixed가 Dynamic보다 유리하다 → 재최적화는 가치가 없다"고 단언하지만, SMA 기준으로는 두 자산 모두 Dynamic이 Fixed를 크게 앞선다(QQQ 9.46 vs 5.16, TQQQ 19.38 vs 9.25). **결론이 뒤집혔다.**

QQQ CAGR은 SMA 전환 이전에도 데이터 누적만으로 11.33 → 11.84까지 이미 움직였다. 즉 이 문구는 **재실행할 때마다 낡는 구조**이며, 값만 고쳐 넣으면 다음 실행에서 같은 일이 반복된다. 그래서 동적 생성으로 전환한다.

**(2) 문서가 서술하는 동작이 코드와 다르다**

- `app_portfolio_backtest.py`에 "실험 해설·거래 현황 바차트·거래 내역 테이블" 구현이 없는데 문서 4곳(모듈 docstring 포함)이 이를 설명한다
- 정합성 검증 실패 시 코드는 `ValueError`로 **중단**하는데 `src/qbt/backtest/CLAUDE.md`만 "WARNING 로그를 남긴다"로 적혀 있다
- `README.md`가 시각화 스택에 **matplotlib**을 넣었으나 의존성·코드 어디에도 없다
- 루트 `CLAUDE.md`의 「근거 승격 목적지」가 삭제된 `docs/DESIGN_QBT_LIVE_FINAL.md`를 가리켜, **계획서 규약 자체가 동작하지 않는다**

**(3) 이미 끝난 작업의 진행 상태가 영구 코드에 남아 있다**

`.claude/rules/python.md`가 `"Phase 0"`·`"레드"`·`"그린"`을 **금지 패턴으로 명시**하는데 테스트 4개 파일에 17건이 남아 있다(오탐 3건 제외 후 확정). 단순 용어 문제가 아니다 — `test_portfolio_execution.py:370`의 "**RED 사유: 현재 버그로 GLD 추가매수가 체결되지 않아** weight가 회복되지 않음"은 **지금 거짓**이다. 해당 4개 파일 57건이 전부 통과하므로 버그는 이미 고쳐졌고 주석만 남았다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」, 「문서 보관 원칙」, 「실행 명령어 관리 원칙」
- `.claude/rules/python.md` — 특히 「문서화」의 주석 작성 원칙과 문서 내구성 원칙
- `docs/CLAUDE.md` — 문서 보관 정책, research 폴더 사용 규칙
- `scripts/CLAUDE.md` — CLI 계층 원칙(도메인 로직 구현 금지)
- `src/qbt/CLAUDE.md` — 계층 분리, 상수 관리 3계층
- `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md` — Given-When-Then, 결정적 테스트, 부동소수점 비교 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] WFO 대시보드 4개 판단 섹션이 `walkforward_summary.json`에서 생성되며, 하드코딩된 성과 수치가 0건
- [x] 신규 판단 문구 생성 모듈에 대한 테스트 추가 (대소관계 역전·임계값 경계 포함)
- [x] 재점검에서 확인된 3자 불일치 항목 전량 해소
- [x] 테스트 4개 파일의 Phase/RED/GREEN 표현 17건 제거 (오탐 3건은 대상 아님)
- [x] 복제 수치·가변 목록 선별 정리 완료 (제거/참조/유지 3분류 적용)
- [x] 깨진 링크 0건 — `docs/plans/` 를 제외한 모든 `.md` 대상 (계획서끼리의 참조는 임시 문서 간 링크이며 정리 시점을 사용자가 판단하므로 범위 밖. 현재 `PLAN_doc_history_cleanup.md` 2건이 이에 해당)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `README.md` **변경 있음** / `docs/COMMANDS.md` **변경 있음**
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (SMA 전환이 대시보드 문구를 무효화한 경위와 동적화 판단 기준을 `docs/research/전략_검증_보고서.md` 에 부록으로 이관.
      WFO 해석 기준을 이미 다루는 문서이므로 새 파일을 만들지 않는다)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규**

- `src/qbt/backtest/walkforward_verdict.py` — WFO 판단 문구 생성 (기존 관용 준수: `parameter_stability.py`·`tqqq/spread_lab_helpers.py`가 이미 "앱 전용 헬퍼를 src에 두고 테스트를 붙이는" 선례)
- `tests/qbt/test_walkforward_verdict.py`

**수정 — 코드**

- `scripts/backtest/app_walkforward.py` — 4개 판단 섹션 동적화. `_render_stitched_equity`·`_render_is_vs_oos`는 현재 `summaries`를 받지 않으므로 시그니처 변경 필요
- `scripts/backtest/app_portfolio_backtest.py` — 모듈 docstring에서 미구현 섹션 언급 제거
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — "삭제됨" 과거형 표현만 현재 상태 서술로 교체
- `tests/qbt/test_portfolio_execution.py`(9건), `test_portfolio_backtest_scenarios.py`(4건), `test_portfolio_state_log.py`(2건), `test_engine_common.py`(2건) — docstring·주석만, 단언·로직 불변
- `pytest.ini` — `minversion` 주석 오류 수정

**수정 — 문서**

- 루트 `CLAUDE.md` — 근거 승격 목적지 복구, 소요 시간 서술
- `README.md`: **변경 있음** — matplotlib 제거
- `docs/COMMANDS.md`: **변경 있음** — 미구현 대시보드 섹션 서술 제거, 리밸런싱 수치 중복 정리
- `.claude/rules/python.md` — 상대경로 오류, pyright 적용 범위 서술
- `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `tests/CLAUDE.md`
- `docs/research/QQQ_지연진입_연구.md` — `docs/plans/` 참조 2곳만 자립화 (본문 수치는 불변)

### 데이터/결과 영향

- **없음.** `storage/` 하위 파일을 읽기만 하고 쓰지 않는다
- 출력 스키마 변경 없음. 백테스트·WFO 산식과 지표 정의를 건드리지 않는다
- 대시보드 화면의 **표시 문구만** 달라진다 (표·차트 수치는 원래부터 JSON/CSV에서 읽고 있었다)

## 6) 단계별 계획(Phases)

### Phase 0 — 판단 문구 생성 계약을 테스트로 먼저 고정(레드)

> 해당 사유: **판단 기준(임계값)이 코드로 들어온다.** PC·WFE·Dynamic vs Fixed 대소관계에 따라 문장이 갈리므로,
> 기준과 분기를 테스트로 먼저 고정하지 않으면 "또 낡는 것을 막는다"는 이번 작업의 목적 자체가 검증되지 않는다.

**작업 내용**:

- [x] `walkforward_verdict.py`의 공개 인터페이스 확정 (입력: `summary` dict → 출력: 문장 리스트)
- [x] 판단 임계값을 상수로 고정하고 배치 위치를 결정 (`src/qbt/CLAUDE.md` 상수 3계층 규칙 적용 — 단일 파일 사용이면 파일 상단)
- [x] 기존 문서에 흩어진 해석 기준을 상수의 근거로 명시 — PC 0.5 초과 시 집중 경고, WFE Calmar Robust 1 기준 재현성 판정
- [x] 테스트 작성(레드 허용):
  - [x] Dynamic > Fixed일 때와 Fixed > Dynamic일 때 **서술 방향이 뒤집히는지** (이번 사고의 핵심 계약)
  - [x] PC 임계값 경계(0.5 미만/이상)에서 문장이 갈리는지
  - [x] WFE Calmar Robust가 음수일 때 재현성 실패로 서술되는지
  - [x] 파라미터 리스트(`param_ma_windows` 등)로부터 "전 윈도우 동일 / 변동" 판정이 정확한지
  - [x] 키 누락·`None` 등 결측 입력에서 예외 없이 안전하게 처리되는지

---

### Phase 1 — WFO 판단 문구 동적 생성 구현(그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/walkforward_verdict.py` 구현으로 Phase 0 테스트 통과
- [x] `app_walkforward.py` L249 섹션(`_render_mode_summary`) 연결 — 이 함수는 이미 `summaries`를 보유
- [x] `app_walkforward.py` L632 섹션(`_render_param_drift`) 연결 — `summary.json`의 `param_*` 리스트 사용 (추가 CSV 로딩 불필요)
- [x] `app_walkforward.py` L362 섹션(`_render_stitched_equity`) — `summaries` 인자 추가 후 연결
- [x] `app_walkforward.py` L522 섹션(`_render_is_vs_oos`) — 수치를 단정하는 문장만 동적화하고, 정성 서술(그래프 읽는 법 등)은 유지
- [x] L1156~1166 윈도우 기간 표를 WFO 결과에서 생성 (현재 W10 OOS 종료일이 실제 `2026-08-21`인데 `2026-03`으로 표기됨)
- [x] 「용어 설명」·「해석 방법」 두 블록은 **정적 유지** — 데이터와 무관한 설명이다

---

### Phase 2 — 문서·주석·코드 3자 불일치 해소(그린 유지)

**작업 내용**:

- [x] 미구현 대시보드 섹션 서술 제거 4곳 — `scripts/CLAUDE.md` L174-175, `src/qbt/backtest/CLAUDE.md` L553-554, `docs/COMMANDS.md` L71, `app_portfolio_backtest.py` L5 docstring
- [x] `src/qbt/backtest/CLAUDE.md` L126 — "WARNING 로그를 남긴다" → 실제 동작(ERROR 로그 후 `ValueError` 중단)으로 수정
- [x] `README.md` L27 — matplotlib 제거
- [x] `tests/CLAUDE.md` L66 — `calculate_daily_cost` → `_calculate_daily_cost`
- [x] `src/qbt/tqqq/CLAUDE.md` 주요 함수 목록에 `_calculate_daily_cost` 추가 (비용 모델의 핵심인데 누락)
- [x] `src/qbt/backtest/CLAUDE.md` L139 — "4개 모듈" vs 5개 나열 모순 해소
- [x] `src/qbt/backtest/CLAUDE.md` L145 — facade 서술 수정 (공개 API 2개가 내부 헬퍼로 읽히는 문장 구조)
- [x] `src/qbt/backtest/CLAUDE.md` L516 — 내용 없는 「CSV 파일 형식」 섹션을 **삭제**한다. 같은 내용이 `src/qbt/CLAUDE.md` L224-233(「분석 결과 - 백테스트」)에 이미 있으므로 채우면 중복이 된다
- [x] `pytest.ini` L17-18 — `minversion`은 pytest 버전이므로 "최소 Python 버전" 주석 수정
- [x] `.claude/rules/python.md` L108 — `docs/COMMANDS.md` 상대경로 수정(`.claude/rules/` 기준이라 열리지 않음)
- [x] `.claude/rules/python.md` L112 — pyright 적용 범위 "tests" → 실제 `tests/qbt`
- [x] 루트 `CLAUDE.md` L84 — 「근거 승격 목적지」의 "설계 결정과 탈락안" 행을 `docs/research/`로 통합 (사용자 결정)
- [x] 루트 `CLAUDE.md` L87 — 없어진 설계 문서를 전제한 서술 정리
- [x] `.md` 전량 링크 기계 검증으로 깨진 링크 0건 확인 (검증 명령은 Notes 「링크 검증 방법」 참고)

---

### Phase 3 — 과거 상태·변경 이력·계획 단계 표현 제거(그린 유지)

**작업 내용**:

- [x] 테스트 Phase/RED/GREEN 17건 제거 — 계약 서술로 대체하되 **단언과 로직은 손대지 않는다**
  - [x] `test_portfolio_execution.py` 9건 (L162·292·312·352·370·410·429·515·520)
  - [x] `test_portfolio_backtest_scenarios.py` 4건 (L319·523·682·701)
  - [x] `test_portfolio_state_log.py` 2건 (L143·200)
  - [x] `test_engine_common.py` 2건 (L81·128)
  - [x] "RED 사유: 현재 버그로 …" 4곳은 **이미 거짓**이므로 현재 계약 서술로 교체
  - [x] 오탐 3건(`test_tqqq_simulation_cost_model.py` L3·351, `test_integration.py` L211 — 「스프레드」의 "레드")은 **건드리지 않는다**
- [x] `src/qbt/backtest/CLAUDE.md` 리팩토링 이력 5곳 정리 (L25·102·103·287·292 — "이동하여"·"제거됨"·"이동됨")
- [x] `src/qbt/backtest/CLAUDE.md` L441-443 — EMA 시절 마이그레이션 노트 제거. **단 SMA 채택 근거(L429-439)는 존치** (판단의 근거이며 재도입 방지 목적)
- [x] `src/qbt/tqqq/CLAUDE.md` L238 — "CSV 생성 스크립트는 삭제됨" → 현재 상태 서술
- [x] `app_rate_spread_lab.py` "삭제됨" 과거형 6곳 → 현재 상태 서술 (안내 자체는 존치, Non-Goals 참고)
- [x] `docs/research/QQQ_지연진입_연구.md` L394·L429 — `docs/plans/` 참조를 자립 서술로 교체 (영구 문서가 임시 문서를 참조하지 않는다)

---

### Phase 4 — 수치 하드코딩 선별 정리(그린 유지)

> 원칙: 전부 걷어내지 않는다. 문제를 낸 것은 **복제된 값**과 **자주 바뀌는 목록**이다.
> 안정적인 단일 기재는 문서의 가독성에 기여하므로 남긴다.

**작업 내용**:

- [x] **제거**(자주 바뀜):
  - [x] `scripts/CLAUDE.md` L136 — WFO 전략 목록 직접 나열 (같은 문서 L141·L242의 "코드를 직접 확인하라" 방침과 불일치)
  - [x] `scripts/CLAUDE.md` L168 — "11 윈도우" (데이터 길이에 따라 변함)
  - [x] 대시보드 섹션 3중 나열 (Phase 2에서 일부 처리되고 남은 부분)
- [x] **한 곳만 남기고 참조**(복제):
  - [x] 리밸런싱 10%/20% — 4곳(`backtest/CLAUDE.md` L197-198·L202·L225, `COMMANDS.md` L42)
  - [x] `MAX_HISTORY_COUNT = 5` — 2곳(`scripts/CLAUDE.md` L50, `utils/CLAUDE.md` L67)
  - [x] softplus a·b — 2곳(`tqqq/CLAUDE.md` L131·L136)
  - [x] 슬리피지 0.3%/0.6% — 2곳(`backtest/CLAUDE.md` L36·L449)
  - [x] "5개 정합성 규칙" 개수 — 문서 3곳에 분산
- [x] **유지**(안정적 단일 기재): `1e10`, 레버리지 3.0, FFR 2개월/12개월, `2005-01-01`, 4P 확정값
- [x] 루트 `CLAUDE.md` L173 — `run_walkforward.py` "약 6분"에 실측 시점 명시 또는 범위 표현으로 완화

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 — `README.md` **변경 있음**(matplotlib) / `docs/COMMANDS.md` **변경 있음**(미구현 섹션·중복 수치)
- [x] 근거 승격 — SMA 전환이 대시보드 문구를 무효화한 경위와 동적화 판단 기준을 `docs/research/전략_검증_보고서.md` 부록으로 이관
- [x] 자동 포맷 적용: `poetry run black .`
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] `.md` 링크 전량 재검증 (깨진 링크 0건)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=543, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / WFO 대시보드 판단 문구 동적화 + 문서·주석 3자 동기화
2. 백테스트 / SMA 전환으로 무효화된 WFO 해석 문구를 summary.json 기반으로 전환
3. 문서 / 재점검 지적사항 정리 — 3자 불일치·이력 표현·복제 수치 해소
4. 백테스트 / 재실행에도 낡지 않는 WFO 판단 문구 + 재점검 정리
5. 문서 / live 제거 후 재점검 반영 — 대시보드 문구 동적화 및 규약 복구

## 7) 리스크(Risks)

| 리스크 | 완화책 |
| --- | --- |
| **동적 생성 문구가 어색하거나 정보량이 줄어든다** | Phase 0에서 문장 템플릿을 먼저 고정하고 테스트로 출력 형태를 검증한다. 기존 문구의 정보 구조(한 줄 요약 → 근거 3~4줄)를 유지한다 |
| **대시보드는 AI가 실행할 수 없어 화면 확인이 불가** | 루트 `CLAUDE.md` 규칙대로 사용자가 실행한다. AI는 `summary.json`을 직접 읽어 생성 함수의 출력을 테스트로 검증하고, 사용자에게 볼 지점을 안내한다 |
| **`_render_stitched_equity`·`_render_is_vs_oos` 시그니처 변경이 호출부를 깨뜨림** | 호출부는 `main()` 한 곳뿐임을 확인했다. PyRight strict가 인자 불일치를 잡는다 |
| **테스트 docstring 정리 중 실수로 단언을 건드림** | Phase 3은 docstring·주석만 대상으로 한다. 착수 전 해당 4개 파일 57건 통과를 확인했고, Phase 3 종료 시 같은 명령으로 재확인한다 |
| **문서에서 수치를 걷어내 오히려 가독성이 떨어진다** | 전부 제거하지 않는다. Phase 4의 제거/참조/유지 3분류를 적용하고, 복제와 가변 목록만 손댄다 |
| **판단 임계값(PC 0.5, WFE 1.0)이 근거 없이 코드로 굳는다** | 기존 문서의 「지표를 해석하는 방법」 블록이 이미 이 기준을 명시하고 있다. 상수 주석에 그 출처를 남긴다 |

## 8) 메모(Notes)

### 원인 규명 기록 (근거 승격 대상)

- WFO 문구 노후화의 결정타는 `9e22b10`(EMA 계산 경로 완전 제거)이다. 이 커밋이 `walkforward_summary.json`·`walkforward_dynamic.csv` 등 결과 파일을 전량 재생성했으나 `app_walkforward.py`는 포함하지 않았다
- 후속 `18b75fb`("SMA 전환 후 연구 수치 재산출")는 대상이 `docs/research/`와 폐기 실험 정리였고, **대시보드 해설은 재산출 범위에 없었다**
- 문구가 마지막으로 정확했던 시점은 `2318307`(2026-04-01)이며, 그 시점 JSON 값과 문구가 완전히 일치함을 확인했다
- QQQ CAGR은 SMA 전환 이전에도 데이터 누적만으로 11.33 → 11.84로 이동했다. **하드코딩인 한 재실행마다 낡는다**는 것이 동적화의 근거다

### 조사에서 확인한 사실

- 테스트가 `scripts/`를 import하는 사례 0건. 반면 앱 전용 헬퍼를 `src/qbt/`에 두고 테스트를 붙이는 선례는 `parameter_stability.py`·`tqqq/spread_lab_helpers.py` 2건 → 신규 모듈은 `src/qbt/backtest/`에 둔다
- `summary.json`에 `param_ma_windows`·`param_buy_buffers`·`param_sell_buffers`·`param_hold_days` 리스트가 이미 존재 → 파라미터 추이 문구에 추가 CSV 로딩 불필요
- Phase/RED/GREEN grep 결과 20건 중 3건은 「스프레드」의 "레드" 오탐 → 실제 대상 17건

### 링크 검증 방법

`docs/plans/` 를 제외한 모든 `.md` 의 상대 링크가 실제 파일을 가리키는지 확인한다.

```bash
for f in $(git ls-files | grep -v '^vendor/' | grep '\.md$' | grep -v '^docs/plans/'); do
  d=$(dirname "$f")
  grep -oE '\]\([^)#][^)]*\)' "$f" | sed 's/^](//; s/)$//; s/#.*//' | while read -r link; do
    case "$link" in http*|mailto*|"") continue;; esac
    [ -e "$d/$link" ] || echo "[BROKEN] $f -> $link"
  done
done
```

착수 시점 기준 이 명령의 출력은 2건이다 — 루트 `CLAUDE.md` → `docs/DESIGN_QBT_LIVE_FINAL.md`, `.claude/rules/python.md` → `docs/COMMANDS.md`. 둘 다 Phase 2에서 해소한다.

### 보류 항목

- `pytest.ini`의 미사용 마커 3종(slow/integration/unit): 사용처 0건이나 `tests/CLAUDE.md`가 "참고용"으로 이미 명시. `--strict-markers` 하에서 정의를 남기는 편이 안전하므로 이번 범위에서 제외

### 진행 로그 (KST)

- 2026-09-05 19:19: 계획서 작성. live 제거 후 재점검 결과와 SMA 전환 원인 규명을 반영. 사용자 결정 3건 확정 — ① 판단 문구는 summary.json 기반 동적 생성 ② 미구현 대시보드 섹션은 문서를 코드에 맞춤 ③ 「설계 결정과 탈락안」 승격 목적지는 `docs/research/`로 통합
- 2026-09-05 19:30: Phase 0~1 완료. `walkforward_verdict.py` 신설(공개 함수 5개), 테스트 19건 그린. 대시보드 판단 4개 섹션 + 윈도우 기간 표를 결과 파일 기반으로 전환. 실측 대조 결과 생성 문구가 JSON·CSV 값과 일치함을 확인
- 2026-09-05 19:36: Phase 2~4 완료. 3자 불일치 해소(미구현 섹션 4곳·WARNING 오기·matplotlib·함수명·모듈 개수 모순·facade 서술·빈 섹션·pytest.ini 주석·python.md 경로 2건·근거 승격 목적지), 이력 표현 제거(테스트 4개 파일 18건·CLAUDE.md 이력 5곳·EMA 마이그레이션 노트·"삭제됨" 7곳·research→plans 참조 2곳), 수치 하드코딩 선별 정리
- 2026-09-05 19:46: 근거를 `docs/research/전략_검증_보고서.md` 부록 G.8로 승격. `black` 적용 후 품질 검증 통과(passed=543, failed=0, skipped=0). Ruff UP038 3건은 `isinstance` 를 `|` 문법으로 고쳐 해소 → **Done**

### 계획 대비 실제 차이

- **테스트 이력 표현이 17건이 아니라 18건이었다.** 착수 시 grep 패턴(`phase|RED|GREEN|레드|그린`)에 `현재 버그` 가 없어
  `test_portfolio_backtest_scenarios.py:730` 을 놓쳤다. 같은 성격이므로 함께 정리했다.
- **윈도우 기간 표는 전략별로 나누어 생성했다.** 계획서는 단일 표를 상정했으나, QQQ 와 TQQQ 의
  마지막 OOS 종료일이 다르다(2026-08-21 vs 2026-03-12). 하나로 합치면 어느 한쪽이 부정확해진다.
- **`_render_stitched_equity` 외에 `main()` 의 실행 순서도 바꿨다.** 윈도우 기간 표가 개념 설명 expander 안에 있어
  결과 로드보다 먼저 렌더링됐기 때문이다. 전략 탐색을 expander 앞으로 옮겼고, 화면에 보이는 순서는 그대로다.

---
