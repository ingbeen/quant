# Implementation Plan: 검사 공백 보강 — 무거운 결함을 막아야 할 테스트 · 가드가 실제로 잡게 한다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-10 12:48
**마지막 업데이트**: 2026-10-10 22:00
**관련 범위**: tests(`tests/qbt/`), backtest(`allocators/haa.py`), utils(`proxy_comparison.py` · `proxy_series.py`), scripts(`data/generate_proxy_comparison.py`)
**관련 문서**: `tests/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 6단계), `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 결함을 넣어도 통과하던 테스트 넷(신호 · 매매 시세 분리, 워크포워드 판단 문구, Sharpe · Sortino 값, 반올림 · 나눗셈의 허용오차)이 그 결함에서 실패한다
- [x] 목표 2: 미룬 지적 셋(매매법 장부 비용 · HAA 시세 정렬 · 대체-실물 교차 확인 범위)을 막는 검사를 넣는다
- [x] 목표 3: 지금 결과 파일은 하나도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- **판단 문구의 로직 변경**(점검 보고서 1-10 — 꼬리 문장 · 「양호」 판정을 Dynamic 값만으로) — 11단계. 이 계획서의 판단 문구 테스트는 두 모드가 같은 쪽을 가리키는 입력만 써서 1-10 이 바꿀 동작을 고정하지 않는다
- **HAA 카나리아 점수가 NaN 일 때의 처리**(미룬 지적 본문의 작은 빈틈) — 뿌리가 시세의 NaN 이고 10단계(9-12, 시세 로더의 NaN 검사)가 막는다
- **대체 비교 스크립트 ↔ 대시보드의 두 벌**(5-6 중 반올림 · 파일 이름 · 국면 변환) — 반올림 상수의 자리(결정 10, 3-6)가 먼저 정해져야 해 11단계로 옮긴다. 여기서는 src 안의 두 벌(`_require_strictly_increasing_dates`)만 합친다
- **배분 규칙 공용 모듈 신설** — HAA 의 거래일 대조는 HAA 안에 둔다(아래 설계 결정 2)
- **무위험 수익률이 0 이 아닌 Sharpe · Sortino 테스트** — 프로덕션 호출이 그 인자를 넘기지 않는다(`grep` 0건)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 6단계다. 대상은 「테스트가 막지 못하는 결함」 표(2-25 · 2-26 · 2-27 · 2-29)와 고치기로 한 미룬 지적 2 · 8 · 13 이고, 같은 파일의 작은 정리(3-11 · 3-19 · 6-14 · 5-6 일부)를 함께 한다
- 대상마다 지금 무엇이 비어 있는가(2026-10-10 지금 코드에서 다시 확인)

| 항목 | 지금 | 근거 |
|---|---|---|
| 2-25 단일 엔진 | `test_buffer_zone_dual_ticker.py` 의 체결가 단언이 `if not trades_df.empty:` 안에 있는데 픽스처에 매도가 없어 0행이다(건너뜀). 에쿼티 단언 `equity < 주수 × 112` 는 신호 종가로 계산해도 참이다 | 스크래치 실행: 거래 0행, 체결일 주수 153(신호 시가였다면 94), 에쿼티 12265.165(신호 종가였다면 16855.165 — 둘 다 17136 미만) |
| 2-25 포트폴리오 | 신호 시세와 매매 시세가 다른 슬롯을 검사하는 테스트가 없다 — 「공유 시그널」 테스트도 두 CSV 에 같은 표를 쓴다 | `test_portfolio_backtest_scenarios.py` `TestQQQTQQQSharedSignal` |
| 2-26 | `test_walkforward_verdict.py` 의 결론 단언이 `!=`(두 문구가 다르다) · 숫자 포함뿐이라, 결론이 한쪽으로 고정돼도 통과한다 | 문구에 수치가 들어가 두 입력의 문자열은 늘 다르다 |
| 2-27 | Sharpe · Sortino 정상 계산 테스트가 `!= 0.0` 만 본다 | `test_analysis.py` `TestCalculateSharpeRatio` · `TestCalculateSortinoRatio` |
| 2-29 | 허용오차가 검사하려는 것보다 크다 — 다운로더 6자리(±1e-6), 일별 비교 4자리(±0.0001), 손익률 분모(±1e-12) | 반올림 · EPSILON 유무의 차이가 허용오차 안이다. 넷째 자리(워크포워드 요약)는 5단계에서 테스트째 지웠다 |
| 미룬 지적 2 | 매매법 장부의 `cost` 를 대조하는 테스트 · 검사기 규칙이 없다(cash · target_share 결함은 기존 테스트가 잡는다) | 점검 보고서 17절 재현 |
| 미룬 지적 8 | HAA 는 월말 행을 TIP 날짜로 정하고 나머지 9개 시세를 같은 행 번호로 읽는데, 거래일이 같은지 확인하지 않는다. 로테이션 규칙은 확인한다 | `haa.py` `_past_month_ends` ↔ `us_weakness_rotation.py` `_ratio_with_average` |
| 미룬 지적 13 | 교차 확인 쌍의 넷째 칸(자를 실물)이 `None` 이거나 `before` 가 아무 날도 자르지 않아도 전 구간으로 잰다 | `generate_proxy_comparison.py` `main` · `proxy_comparison.align_closes` |

### 설계 결정

1. **테스트 보강은 「조건부 단언 → 무조건 단언」 · 「다르다 → 이 결론이다」 · 「0 이 아니다 → 이 값이다」로 바꾼다.** 기대값은 테스트 안에서 입력으로부터 산식으로 낸다(출력에서 베낀 숫자를 박지 않는다)
   - 단일 엔진: 체결일 주수 = `int(자본 ÷ (매매 시가 × (1 + SLIPPAGE_RATE)))`, 미청산 진입가 = 매매 시가 × (1 + SLIPPAGE_RATE), 에쿼티 = 남은 현금 + 주수 × 매매 종가
   - 포트폴리오: 신호 시세(100 대)와 매매 시세(50 대)가 다른 버퍼존 슬롯 하나 — 첫 보유일 주수와 평가액이 매매 시세 기준
   - 판단 문구: 결론을 가르는 구절(「Dynamic이 Fully Fixed(4P)를 앞섭니다」 등)이 맞는 입력의 문구에 있고 반대 입력의 문구에는 없다
   - Sharpe · Sortino: 에쿼티 100 → 110 → 99 → 108.9(수익률 +10% · −10% · +10%)면 Sharpe = √21, Sortino = √84
   - 허용오차: 반올림 결과와 나눗셈은 `==` 로 정확 비교
2. **HAA 의 거래일 대조는 HAA 안에 둔다** — 첫 호출에서 자산 9개의 날짜가 TIP 과 같은지 보고 다르면 ValueError(로테이션과 같은 문구 모양). 로테이션의 대조와 합친 공용 함수를 두려면 배분 규칙 패키지에 새 모듈이 필요한데(레지스트리는 규칙 모듈을 import 해 반대 방향이 막힌다), 두 대조는 보는 시세 묶음이 달라 합쳐도 4줄씩이다
3. **교차 확인 범위는 표의 모양으로 막는다** (리뷰 1 · 2회차와 수정분 검증 뒤 사용자 결정으로 조정 — 진행 로그) — 등록 쌍 표를 묶음마다 따로 둔다: `LONG_PAIRS` · `SPLICED_PAIRS`(대체 · 기준)와 `CROSS_PAIRS`(대체 · 기준 · 자를 실물). 묶음 이름은 표가 정하므로 「상장 전 교차 확인」으로 나가는 행은 반드시 자를 실물을 가진다. `align_closes` 에는 가드를 넣지 않는다 — `before` 가 자르는 날이 0 이면 겹치는 날이 전부 상장 전이라 그 결과는 맞다
   - 처음 안(조정 전): `align_closes` 가 잘린 날 0 이면 ValueError, 스크립트 `main` 이 교차 확인 묶음의 넷째 칸 `None` 이면 ValueError. 앞의 것은 맞는 입력을 멈추고 막으려던 실수는 통과시켜 뺐고, 뒤의 것은 지켜 주는 테스트를 둘 수 없어 표를 나누는 쪽으로 바꿨다
   - 둘째 안(2회차 뒤): 일반 쌍 `PAIRS`(묶음 · 대체 · 기준)와 `CROSS_PAIRS` 둘로 나눔. 묶음 칸이 자유 문자열이라 교차 확인 쌍을 `PAIRS` 에 적으면 전 구간 수치가 「상장 전 교차 확인」으로 에러 없이 나갔다(수정분 검증의 무거운 발견) → 묶음별 표로
4. **`align_closes` 의 시작 · 끝 필터 삭제(6-14)** — inner join 결과의 날짜는 두 시세 모두에 있으므로 「기준 첫날 이상 · 두 끝 중 이른 날 이하」가 늘 참이다
5. **HAA 상수(3-11 · 3-19)** — `HAA_ASSET_IDS` 는 공격 · 방어 목록에서 만들고(값 · 순서 그대로), `HAA_WARMUP_ROWS` 는 주석의 산식대로 `HAA_LOOKBACK_MONTHS` 에서 낸다(값 253 그대로)
6. **새 검사는 전부 변형으로 확인한다** — 그 검사가 잡아야 할 결함을 일부러 넣어 실패를 보고 되돌린다(`PYTHONDONTWRITEBYTECODE=1`, 사본과 대조). 변형 목록은 Phase 2 Validation

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md`
- `scripts/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 보강 · 추가한 검사마다 변형 확인 기록이 있다(변형 → 실패한 테스트 → 되돌린 뒤 통과)
- [x] HAA 거래일 대조가 들어갔고 재현 테스트가 수정 전 실패 → 수정 후 통과. 「상장 전 교차 확인」으로 나가는 쌍은 반드시 자를 실물을 가진다(조정 — 설계 결정 3. 그 칸이 없거나 `None` 이면 타입 검사와 실행이 모두 멈추는 것을 사본에서 확인)
- [x] 결과 파일 변화 0 — 사본에서 포트폴리오 러너와 대체-실물 비교 스크립트를 다시 돌린 결과가 저장된 결과와 같다
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절) · `src/qbt/backtest/CLAUDE.md`(HAA 설명에 거래일 대조) · `tests/CLAUDE.md`(허용오차 표) · `scripts/CLAUDE.md` 와 `docs/COMMANDS.md`(쌍 목록 상수 이름 — 조정으로 생김, 실행 명령은 그대로). `README.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] 미룬 지적 옮김 — 새로 옮긴 것 0(미조치 지적은 거르는 기준에 걸리거나 점검 보고서의 기존 행에 덧붙였다), 이 계획서가 고친 항목 셋(장부 비용 · HAA 거래일 · 교차 확인 범위)은 파일에서 지웠다. 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/allocators/haa.py` — 거래일 대조, 상수 둘
- `src/qbt/utils/proxy_comparison.py` — `before` 가 자르는 날 0 이면 ValueError, 시작 · 끝 필터 삭제, 날짜 순서 검사를 `proxy_series` 의 것으로
- `src/qbt/utils/proxy_series.py` — 날짜 순서 검사 함수를 공개 이름으로
- `scripts/data/generate_proxy_comparison.py` — 교차 확인 쌍의 넷째 칸 확인
- `tests/qbt/test_buffer_zone_dual_ticker.py` · `test_portfolio_backtest_scenarios.py` · `test_walkforward_verdict.py` · `test_analysis.py` · `test_stock_downloader.py` · `test_tqqq_simulation_outputs.py` · `test_engine_common.py` · `test_portfolio_methods.py` · `test_allocators.py` · `test_proxy_comparison.py`
- `docs/AUDIT_REPORT.md` · `docs/DEFERRED_FINDINGS.md`(항목 2 · 8 · 13 — 착수 때 「고치는 중」, Done 때 삭제) · `src/qbt/utils/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · 옵션 그대로)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 없음. 새 가드는 지금 데이터에서 걸리지 않는다(HAA 판단 시세는 엔진이 공통 거래일로 맞춰 넘기고, 교차 확인 3쌍은 모두 실제로 잘린다). 확인용 재실행은 사본에서 한다

## 6) 단계별 계획(Phases)

### Phase 0 — 새 가드의 재현 테스트(레드)

**작업 내용**:

- [x] `test_allocators.py` — HAA 시세 하나의 거래일이 하루 어긋나면 ValueError
- [x] `test_proxy_comparison.py` — `before` 가 겹치는 날을 하나도 자르지 않으면 ValueError (리뷰 1회차 뒤 반대 계약 「자르지 않아도 정상」 테스트로 바꿈 — 설계 결정 3)

**Validation**:

- [x] 두 테스트가 지금 코드에서 실패한다(`DID NOT RAISE`)

---

### Phase 1 — 가드와 같은 파일의 정리(그린)

**작업 내용**:

- [x] `haa.py` — 첫 호출의 거래일 대조, `HAA_ASSET_IDS` · `HAA_WARMUP_ROWS` 를 다른 상수에서 낸다
- [x] `proxy_comparison.py` — `before` 가드(리뷰 1회차 뒤 뺌), 시작 · 끝 필터 삭제, 날짜 순서 검사 한 벌로(`proxy_series.py` 의 함수를 공개 이름으로 바꿔 쓴다)
- [x] `generate_proxy_comparison.py` — 교차 확인 묶음인데 넷째 칸이 `None` 이면 ValueError (리뷰 2회차 뒤 표를 둘로 나눠 대체)

**Validation**:

- [x] `poetry run pytest tests/qbt/test_allocators.py tests/qbt/test_proxy_comparison.py tests/qbt/test_proxy_series.py` — 전부 통과(Phase 0 의 둘 포함)
- [x] 상수 값이 그대로다 — `HAA_ASSET_IDS` 순서 · `HAA_WARMUP_ROWS == 253`(스크래치)

---

### Phase 2 — 검사 보강(테스트만)

**작업 내용**:

- [x] 2-25 단일 엔진 — `test_buffer_zone_dual_ticker.py` 두 테스트를 무조건 단언으로(체결일 주수 · 미청산 진입가 · 에쿼티)
- [x] 2-25 포트폴리오 — `test_portfolio_backtest_scenarios.py` 에 신호 시세와 매매 시세가 다른 슬롯 테스트 1개
- [x] 2-26 — `test_walkforward_verdict.py` 의 `!=` 단언에 결론 구절 단언을 더한다(모드 요약 · 수익 집중도 · WFE · 이어 붙인 자본곡선 · IS 대 OOS)
- [x] 2-27 — `test_analysis.py` Sharpe · Sortino 값 테스트
- [x] 2-29 — `test_stock_downloader.py` · `test_tqqq_simulation_outputs.py` · `test_engine_common.py` 의 해당 단언을 `==` 로
- [x] 미룬 지적 2 — `test_portfolio_methods.py` 에 장부 비용 테스트 1개(매매법마다 Σ |주수 변화| × 시가 × SLIPPAGE_RATE 를 상태 로그와 시세로 다시 계산해 장부 `cost` 와 대조)

**Validation**:

- [x] 바뀐 테스트 파일 `poetry run pytest <파일들>` — 전부 통과
- [x] 변형 확인(스크래치 사본에서, 변형마다 실패한 테스트 이름을 진행 로그에)
  - 단일 엔진: 체결가를 신호 시가로 / 평가를 신호 종가로
  - 포트폴리오 엔진: 체결가를 신호 시가로 / 평가를 신호 종가로
  - 판단 문구: CAGR 비교 분기 고정 / 수익 집중도 부등호 반대 / WFE 꼬리 고정 / IS 대 OOS 분기 고정
  - Sharpe 연율화를 √365 로 / Sortino 하방 편차를 전체 표준편차로
  - 다운로더 반올림 삭제 / 일별 비교 반올림 삭제 / 손익률 분모에 EPSILON
  - 장부 비용 두 배
  - HAA 거래일 대조 삭제 / `before` 가드 삭제
  - 스크립트 `main` 가드: 교차 확인 쌍 하나의 넷째 칸을 `None` 으로 바꿔 실행 → ValueError

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 결과 파일 변화 0 확인(스크래치 사본) — 포트폴리오 러너와 `generate_proxy_comparison.py` 를 돌려 `storage/results/portfolio/` · `storage/results/proxy_comparison/` 가 저장소와 같은지
- [x] 문서 — `docs/AUDIT_REPORT.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `docs/DEFERRED_FINDINGS.md`(고친 항목 삭제). `docs/COMMANDS.md` · `README.md` 변경 없음 (조정: `src/qbt/utils/CLAUDE.md` 는 가드를 빼며 원래대로, `tests/CLAUDE.md` · `scripts/CLAUDE.md` · `docs/COMMANDS.md` 가 더해짐 — DoD 줄 참고)
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 11건 — 버그 6 [무거움 5 · 가벼움 1] · 그 외 3 · 앞선 커밋에서 이미 판정한 것 2 · 조치: 무거움 5 수정 · 가벼움 1 미조치 · 그 외 2 반영 · 1 미조치)
- [x] `/code-review xhigh` **2회차** (발견 10건 — 버그 6 [무거움 4 · 가벼움 2] · 그 외 4 · 조치: 무거움 4 수정(셋은 1회차와 같은 자리라 사용자 결정으로) · 가벼움 1 수정 · 가벼움 1 미조치 · 그 외 4 반영)
- [x] 수정분 검증 (2회차 수정 19 hunk · 발견 7건 — 무거움 2 · 조치: 이 수정이 만든 무거움 1은 사용자 결정으로 다시 고침 · 원래 있던 무거움 1은 점검 보고서 2-11 행에 덧붙임 · 가벼움 5는 기록)
- [x] 수정분 재검증 (발견 1 을 고친 3 hunk · 발견 2건 — 무거움 0 · 조치: 둘 다 주석 · 독스트링 문구라 사실에 맞게 고치고 코드 동일을 AST 로 확인)
- [x] `poetry run python validate_project.py` (passed=885, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 테스트 / 결함을 넣어도 통과하던 검사 보강과 미룬 지적 3건 처리
2. 테스트 / 신호 · 매매 시세 분리 · 워크포워드 판단 문구 · Sharpe · Sortino · 장부 비용 테스트 보강, HAA 거래일 대조 추가, 대체-실물 비교 쌍 표를 묶음별로 분리
3. 테스트 / 변형 32종을 잡도록 검사 공백 보강 — 보강 전 테스트는 처음 22종 중 21종 통과
4. 테스트 / 점검 보고서 6단계 처리 — 테스트 보강 · HAA 입력 시세 정렬 가드 · 교차 확인 쌍의 자를 실물 필수화
5. 테스트 / 틀린 체결가 · 판단 문구 · 장부 비용이 에러 없이 나가도 못 잡던 테스트 공백 해소

## 7) 리스크(Risks)

- **새 가드가 정상 실행을 멈출 수 있다** — HAA 거래일 대조나 `before` 가드가 지금 데이터에서 걸리면 포트폴리오 러너 · 그리드 · 대체 비교가 멈춘다. 완화: 마지막 Phase 에서 사본으로 두 러너를 돌려 확인한다. 그리드 두 개(각 1 ~ 3분)는 같은 구성 함수 · 같은 시세를 쓰므로 포트폴리오 러너와 테스트(`TestEngineIntegration`)로 갈음한다
- **구절 단언은 문구를 바꿀 때 함께 고쳐야 한다** — 결론 구절을 테스트가 붙잡으므로 표현만 바꿔도 테스트가 실패한다. 의도한 비용이다(결론이 바뀌었는지 사람이 한 번 보게 된다). 구절은 결론을 가르는 최소 길이만 쓴다
- **`==` 정확 비교** — 반올림 결과(`round` 의 출력)와 같은 식의 나눗셈이라 부동소수 오차가 끼지 않는다. 변형 전 통과로 확인한다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 「테스트가 막지 못하는 결함」 표(2-25 ~ 2-29) · 17절(미룬 지적 2 · 8 · 13) · 19절 6단계
- 19절 6단계에 적혀 있던 「5-6 의 대체 비교 두 벌」 중 스크립트 ↔ 대시보드 부분은 11단계(결정 10 과 함께)로 옮긴다 — 비목표 참고

### 진행 로그 (KST)

- 2026-10-10 12:48: 계획서 작성(Draft). 대상 코드를 읽고 스크래치에서 기대값을 확인했다 — 단일 엔진 체결일 주수 153 · 미청산 진입가 65.195 · 에쿼티 12265.165, 포트폴리오 첫 보유일 주수 182937(신호 시가였다면 91051), Sharpe √21 · Sortino √84(계산값과 1e-12 안에서 같다). 프로덕션이 무위험 수익률 인자를 넘기는 곳은 0건이라 그 테스트는 넣지 않는다
- 2026-10-10 12:52: 승인 — 사용자 「승인」. 5단계는 사용자가 커밋함(`a436a1c`). 미룬 지적 2 · 8 · 13 의 출처에 「고치는 중」을 달고, 점검 보고서 19절에 5-6 의 스크립트 ↔ 대시보드 두 벌을 11단계로 옮긴다고 적었다. Phase 0 착수
- 2026-10-10 12:54: Phase 0 — 재현 테스트 셋(HAA 거래일 어긋남 2 경우 · `before` 가 자르는 날 0)이 지금 코드에서 `DID NOT RAISE` 로 실패. 경계 테스트(`before` = 마지막 겹치는 날 → 그날 하나가 잘린다)는 통과
- 2026-10-10 12:56: Phase 1 — `haa.py` 첫 호출에서 자산 9개의 날짜를 TIP 과 대조(다르면 ValueError), `HAA_ASSET_IDS` 를 공격 · 방어 목록에서, `HAA_WARMUP_ROWS` 를 `max(HAA_LOOKBACK_MONTHS) × (TRADING_DAYS_PER_YEAR // 12) + 1` 로(값 253 · 순서 그대로 확인). `proxy_comparison.align_closes` — 마지막 겹치는 날이 `before` 보다 앞이면 ValueError, 시작 · 끝 필터 삭제, 날짜 순서 검사는 `proxy_series.require_strictly_increasing_dates`(공개 이름으로 바꿈, 호출처 src 두 파일 6곳)를 쓴다. 스크립트 `main` 에 교차 확인 쌍의 넷째 칸 확인. 테스트 3파일 118 passed
- 2026-10-10 12:59: Phase 2 — 테스트 보강. 단일 엔진 2개를 무조건 단언으로(주수 153 · 진입가 · 에쿼티, 손으로 박았던 0.003 을 `SLIPPAGE_RATE` 로), 포트폴리오에 신호 ≠ 매매 시세 테스트 1개, 판단 문구 테스트에 결론 구절 단언(구절 상수 10개)과 경계 · 반대 결론 테스트 3개(수익 집중도가 기준과 같을 때 · 파라미터 전부 고정 대 전부 변동 · Calmar 기준), Sharpe · Sortino 값 테스트 2개, 허용오차 3곳을 `==` 로, 장부 비용 테스트 1개. 바뀐 테스트 10파일 276 passed
- 2026-10-10 13:01: 변형 확인(스크래치 사본 `copy4`, `PYTHONDONTWRITEBYTECODE=1`, 변형마다 원본 문자열로 복원 확인) — **22종 모두 잡음**. 같은 22종을 보강 전 테스트(HEAD)로 돌리면 21종을 놓친다(잡는 것은 Sortino 하방 편차 하나)
  - 단일 엔진: 체결가를 신호 시가로 → `test_signal_from_signal_df_trade_from_trade_df` · `test_equity_uses_trade_df_close` / 평가를 신호 종가로 → `test_equity_uses_trade_df_close`
  - 포트폴리오 엔진: 체결가를 신호 시가로 / 평가를 신호 종가로 → `TestSignalAndTradeDataSeparation::test_fills_and_valuation_use_trade_data`
  - 판단 문구 10종: CAGR 우세 분기 고정 → `test_direction_flips_when_fixed_is_superior` · `test_verdict_flips_with_mode_superiority` / 비슷 분기 끔 → `test_small_gap_is_described_as_similar` / 수익 집중도 `>=` 를 `>` 로 → `test_pc_at_threshold_warns_concentration` / 부등호 반대 → 수익 집중도 테스트 3개 / WFE 음수 분기 끔 → `test_negative_wfe_is_described_as_not_reproduced` / 낙폭 비교 반대 → `test_verdict_flips_with_mode_superiority` / Calmar 기준 반대 → `test_calmar_verdict_follows_threshold` / IS 대 OOS 첫 분기 고정 → IS 대 OOS 테스트 2개 / 음수 분기 끔 → `test_negative_oos_windows_are_counted` / 파라미터 전부 고정 분기 끔 → `test_all_fixed_and_all_changing_reach_opposite_conclusions`
  - Sharpe 연율화를 365 로 → `TestCalculateSharpeRatio::test_value_matches_definition` / Sortino 하방 편차를 전체 편차로 → `TestCalculateSortinoRatio::test_value_matches_definition` 외 1
  - 다운로더 반올림을 9자리로 → `test_price_rounding` / 일별 비교 반올림을 8자리로 → `test_csv_numeric_precision` / 손익률 분모에 1e-12 → `test_pnl_pct_no_epsilon_in_denominator`
  - 장부 비용 두 배 → `test_ledger_cost_is_own_turnover_times_open_times_slippage`
  - HAA 거래일 대조 끔 → `test_misaligned_trading_days_raise` 2 경우 / `before` 가드 끔 → `test_before_cutting_nothing_raises`
  - 스크립트 `main` 가드(테스트 없음 — 스크립트라 실행으로 확인): 사본의 교차 확인 쌍 하나의 넷째 칸을 `None` 으로 바꿔 실행 → exit 1, `ValueError: 교차 확인 쌍 VTMGX ↔ EFA 에 비교를 자를 실물 파일이 없습니다`. 복원 뒤 저장소 파일과 `cmp` 동일
- 2026-10-10 13:02: 결과 파일 변화 0 확인(사본 `copy4` 에서 실행) — `generate_proxy_comparison.py` exit 0, `storage/results/proxy_comparison/` 가 저장소와 같다. `run_portfolio_backtest.py` exit 0(정합성 통과), `storage/results/portfolio/` 51개 파일이 저장소와 같다. 사본과 저장소의 `storage/` 차이는 `meta.json`(실행 시각)뿐이고 저장소의 `storage/` 변경은 0
- 2026-10-10 13:04: 문서 — `src/qbt/utils/CLAUDE.md`(`align_closes` 의 새 예외) · `src/qbt/backtest/CLAUDE.md`(HAA 거래일 대조) · `docs/AUDIT_REPORT.md`(2-25 · 2-26 · 2-27 · 2-29 · 3-11 · 3-19 · 6-14 · 5-6 일부 · 17절 2 · 8 · 13 · 19절 6단계 처리 표시). `black` 적용 — 합쳐진 줄에 남은 쪼개진 문자열 3곳을 한 문자열로 정리
- 2026-10-10 13:05: `/code-review xhigh` 1회차 — 사용 한도로 중단. 18:04 다시 실행
- 2026-10-10 18:04 이후(완료 시각 미측정): `/code-review xhigh` 1회차 — 발견 11건(이 계획서 9 · 앞선 커밋 `a436a1c` 2)
  - 고친 버그 5(무거움)
    - ① `align_closes` 의 새 가드(「`before` 가 자르는 날 0 이면 ValueError」)가 맞는 입력을 멈춘다 — 자르는 날이 0 이면 겹치는 날이 전부 실물 상장 전이라 그 비교는 이미 「상장 전 교차 확인」이고, 막으려던 실수(넷째 칸에 다른 실물 파일)는 그 파일의 첫 거래일이 겹치는 구간 안이면 통과한다. 계획서 설계 결정 3 의 전제(「자를 것이 없으면 전 구간으로 재어진다 = 틀림」)가 틀렸다 → **사용자 결정: 가드 삭제.** `align_closes` 에서 가드를 빼고(6-14 의 필터 삭제 · 날짜 순서 검사 한 벌은 그대로), 재현 테스트를 반대 계약(「겹치는 날이 모두 `before` 앞이면 하나도 자르지 않는다」)으로 바꿨다. `src/qbt/utils/CLAUDE.md` 의 추가 문장도 뺐다. 미룬 지적 13 은 「넷째 칸 `None`」 절반만 결함이었다
    - ② 장부 비용 테스트가 시가와 종가를 구분하지 못함(픽스처가 시가 = 종가) — 비용을 그날 종가로 계산해도 통과 → 시나리오 시세를 `_frames` 한 곳에서 만들고 이 테스트는 시가를 종가보다 1 낮춘 시세로 돈다
    - ③ 스크립트 `main` 의 확인이 한 방향만 봄 — 교차 확인이 아닌 묶음에 넷째 칸이 들어가면 그 묶음의 수치가 조용히 잘린다 → `(묶음 == 교차 확인) == (넷째 칸 있음)` 을 루프 앞에서 한 번 검사(앞선 쌍을 계산한 뒤에 실패하지 않는다)
    - ④ 판단 문구 테스트가 기준값 경계를 고정하지 않음(수익 집중도만 있었다) → `TestVerdictThresholdBoundaries` 6개(CAGR 차 = 기준 · WFE = 1 · WFE = 0 · Calmar = 기준 · 윈도우 절반이 웃돎 · 절반이 음수)
    - ⑦ HAA 재현 테스트가 길이가 다른 어긋남만 봄 — 대조를 길이 비교로 바꿔도 통과 → 행 수는 같고 첫 거래일만 다른 경우 테스트 추가
    - 같은 모양 찾기: 「픽스처가 구분해야 할 두 값을 같게 둔다」는 ② 한 곳(단일 · 포트폴리오 신호/매매 테스트는 시세가 서로 다르다), 「경계값 미고정」은 판단 문구 6곳
  - 반영한 그 외 2: ⑤ 문서의 「첫 호출에서 확인」이 사실과 다름(판단일이 아니면 대조 전에 None 을 돌려준다 — 틀린 비중은 나가지 않는다) → `src/qbt/backtest/CLAUDE.md` 를 「점수를 처음 낼 때(첫 판단일)」로. 계획서 설계 결정 2 의 「첫 호출」도 같은 뜻으로 읽는다 ⑨ 부동소수 `==` 는 전역 테스트 규칙(부동소수는 `pytest.approx`) 위반 → `approx` 로 되돌리고 허용오차를 반올림 단위보다 훨씬 작게(반올림 값 `abs=1e-9`, 손익률 `rel=1e-15`)
  - 미조치 버그 1(가벼움): ⑩ `before` 가 겹치는 날을 전부 잘라 2개 미만이 남을 때의 오류 문구가 `before` 를 언급하지 않는다 — 멈추는 쪽이고 문구 문제(거르는 기준 2), 바뀌지 않은 줄
  - 미조치 그 외 1: ⑪ 거래일 대조를 규칙마다 두지 말고 엔진이 배분 규칙 시세를 채우는 자리에서 한 번 — 설계 제안. 사용자가 계획 승인 때 「HAA 안에 둔다」를 골랐고, 엔진 쪽 검사는 엔진 밖 단독 호출을 덮지 못한다(기준 3)
  - 판단 문구에서 고정하지 않은 것(리뷰의 변형 9종 중 3): 두 모드 중 어느 값으로 판정하는가(`max` ↔ `min` 2종) — 점검 보고서 1-10 이 바꿀 동작이라 비목표, 낙폭이 같을 때의 문구 — 어느 쪽도 「더 얕다」가 아니라 고정할 정답이 없다
  - 앞선 커밋에 대한 2건은 그 계획서에서 이미 판정했다: 대시보드가 bool 이 아닌 `rebalanced` 열에서 멈춤(거르는 기준 2), 워크포워드 요약 반올림 함수를 실행하는 테스트 없음(사용자가 승인한 삭제, 점검 보고서 10절에 기록)
- 2026-10-10 18:28: 1회차 수정 뒤 — 바뀐 테스트 11파일 324 passed, ruff 통과. 변형 확인(사본을 새로 떠서) **30종 모두 잡음**: 기존 22종(가드를 뺀 자리는 「`before` 당일 포함」 변형으로 바꿈 → `before` 테스트 3개)과 리뷰가 통과시켰다고 짚은 8종 — 장부 비용을 종가로 → `test_ledger_cost_…`, HAA 대조를 길이만으로 → `test_same_length_but_different_days_raise`, 경계 6종 → `TestVerdictThresholdBoundaries` 의 6개. 스크립트 확인 양방향: 교차 확인 쌍의 넷째 칸을 `None` 으로 / 대체 판 쌍에 넷째 칸을 넣어 실행 → 둘 다 exit 1 과 ValueError, 복원 뒤 `cmp` 동일. 원래 코드로 `generate_proxy_comparison.py` · `run_portfolio_backtest.py` 를 사본에서 실행 → 두 결과 폴더가 저장소와 같다
- 2026-10-10 18:28 이후(완료 시각 미측정): `/code-review xhigh` 2회차(상한) — 발견 10건. 운영 코드에서 동작이 틀린 곳은 없고, 전부 검사 공백이 덜 닫힌 곳과 문서다. 수정 전 사본을 스크래치 `step6/r2_before/`(18파일)에 떴다
  - 고친 버그 — 새 자리 1(무거움): ① 포트폴리오의 신호 · 매매 분리 테스트가 「신호를 어느 시세에서 읽는가」를 고정하지 못함(두 시세의 모양이 같아 신호 경로를 매매 시세로 바꿔도 결과가 같다) → 매매 시세를 돌파 없이 평탄하게 바꾸고 첫 보유일이 신호 시세의 돌파 다음 거래일인지 단언
  - 1회차와 같은 자리에서 다시 나온 것 — 규칙대로 사용자에게 올렸고 **사용자 결정: 표를 둘로 나눔 · 셋 다 지금 고침**
    - ③(무거움) 스크립트의 넷째 칸 확인을 지키는 자동 검사가 0 이고, 확인 자체가 표가 같은 정보를 두 칸에 중복해 들어 생긴 것 → `PAIRS`(묶음 · 대체 · 기준)와 `CROSS_PAIRS`(대체 · 기준 · 자를 실물)로 나누고 실행 때 확인을 지웠다. 교차 확인 쌍의 비교 제한일은 일감을 만들 때 실물 파일에서 바로 읽는다(「`None` 이면 자르지 않는다」 분기를 없앴다)
    - ②(무거움) WFE 판단 문구의 세 결론 중 「0 초과 · 기준 미만 → 약 N% 재현」을 고정하는 테스트 없음 → 테스트 1개
    - ④(무거움) 장부 비용 테스트가 그 실행에서 상계가 일어났는지 단언하지 않음 → 단언 1줄
    - ⑤(가벼움) CAGR 차 경계 테스트의 입력이 기준값이 2진수로 딱 떨어질 때만 정확 → Dynamic = 기준값 · Fixed = 0.0
  - 미조치 버그 1(가벼움): ⑥ HAA 거래일 대조가 도는 목록이 점수가 읽는 목록 `(*HAA_ASSET_IDS, *HAA_SERIES_IDS)` 에서 파생되지 않음 — 지금은 신호용 시세가 TIP 하나라 두 집합이 같고, 어긋나려면 `HAA_SERIES_IDS` 에 시세를 더하는 새 코드가 있어야 한다(닿지 않음 — 거르는 기준 1)
  - 반영한 그 외 4: ⑦ `tests/CLAUDE.md` 허용오차 표에 「작은 차이 자체를 검증할 때」 행 — 2-29 의 뿌리가 이 표였고 근거가 임시 문서에만 있었다 ⑧ 가드를 빼면서 기존 테스트와 같은 계약이 된 `test_before_on_last_common_date_cuts_that_date` 삭제 ⑨ 결정 14(비용률 같은 정책 값은 테스트에 손으로 고정)와 어긋나게 `0.003` 을 `SLIPPAGE_RATE` 로 바꿨던 것을 되돌리고, Sharpe · Sortino 기대값도 `TRADING_DAYS_PER_YEAR` 대신 √21 · √84 로 고정 ⑩ 계획서 본문이 뺀 가드를 구현 대상으로 적고 있던 것 — 설계 결정 3 · DoD · Phase 줄에 조정을 적었다(사용자가 승인한 변경)
  - 확인 중 스스로 찾은 것: 표를 나눈 직후에는 교차 확인 쌍의 실물 칸을 `None` 으로 적으면 타입 검사만 잡고 **실행은 예외 없이 전 구간으로 쟀다**(「`None` 이면 자르지 않는다」 분기가 남아 있었다) → 일감을 만들 때 실물 파일을 바로 읽게 고쳐 실행도 멈춘다
- 2026-10-10 19:04: 2회차 수정 뒤 — 변형 확인 **32종 모두 잡음**(새로 더한 2종: 신호를 매매 시세에서 읽음 → `TestSignalAndTradeDataSeparation`, WFE 재현 분기 고정 → `test_wfe_between_zero_and_threshold_is_partial_reproduction`. CAGR 경계 · 장부 비용 · `before` 변형도 다시 잡음). 표의 틀린 모양 셋(교차 확인 쌍의 실물을 `None` 으로 · 실물 칸을 뺌 · 일반 쌍에 넷째 칸)은 사본에서 pyright 오류 1건씩 + 실행 exit 1(`AttributeError` · `ValueError` 2). 원래 코드로 사본에서 실행 → `storage/results/proxy_comparison/` 가 저장소와 같고 메타데이터의 쌍 목록 20개도 같다. 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=885, failed=0, skipped=0. `storage/` 변경 0. 수정분 검증(서브에이전트)을 띄웠다
- 2026-10-10 21:40: 수정분 검증이 사용 한도로 중단돼 이어서 돌림. 결과 — 2회차 수정 19 hunk 모두 ① ② ③ 에 답(수정 전 · 후 사본에서 프로덕션 변형 21종 + 스크립트 표 변형 9종을 양쪽 테스트 · 스크립트로 실행, 기준선 두 쪽 모두 885 passed). 출력 CSV · 메타데이터의 쌍 20개는 수정 전과 같다. 발견 7건(무거움 2 · 가벼움 5)
  - 무거움 1(이 수정이 만든 것): 표를 `PAIRS` · `CROSS_PAIRS` 로 나눈 뒤 `PAIRS` 의 묶음 칸이 자유 문자열이라, 교차 확인 쌍을 `PAIRS` 에 적으면 exit 0 · pyright 0 errors 로 「상장 전 교차 확인」 행이 전 구간 수치(거래일 6312 · 일간 상관 0.966, 정상 1484 · 0.8755)로 나간다. 나누기 전에는 같은 실수가 ValueError 로 멈췄다 → **사용자 결정: 묶음마다 표를 따로, 이 부분만 수정분 검증 한 번 더**
  - 무거움 2(원래 있던 것 · diff 밖): 신호 공유 테스트 `TestQQQTQQQSharedSignal` 이 두 CSV 에 같은 표를 써서, 신호 캐시에 적중한 슬롯이 신호를 매매 시세에서 읽어도 전체 테스트가 통과한다. 지금 신호 ≠ 매매인 캐시 적중 슬롯은 0건이고 그 캐시는 점검 보고서 2-11(7단계)에서 지운다 → 미룬 지적 파일과 두 벌을 만들지 않고 2-11 행에 덧붙였다
  - 가벼움 5: 지운 중복 테스트만 잡던 경계 변형 1종(「`before` = 마지막 겹치는 날이면 자르지 않는다」 — 지금 코드에 그런 분기 없음) · 비용률 상수를 참조하는 테스트가 다른 파일에 더 있음(점검 보고서 3-21 행에 덧붙임) · 지울 문서 2곳의 옛 표 이름 · 표 모양이 틀렸을 때의 오류 문구가 파이썬 원문 · 독스트링 수치가 근사 — 마지막 것은 문구만 고쳤고 나머지는 고치지 않았다
  - 사용자 결정: 리뷰 3회차 없이 마무리
- 2026-10-10 21:55: 발견 1 수정(수정 전 사본 `step6/r3_before/`) — 표를 `LONG_PAIRS` · `SPLICED_PAIRS` · `CROSS_PAIRS` 로, 묶음 이름은 일감을 만들 때 표에서 붙인다. 사본에서 틀린 모양 넷 확인: 교차 확인 쌍의 실물 `None` / 실물 칸 뺌 / 대체 판 쌍에 셋째 칸 → 각각 pyright 오류 1건 + 실행 exit 1. 교차 확인 쌍을 대체 판 표에 옮겨 적음(발견 1 의 실수) → 실행은 되지만 그 쌍은 「대체 판」 행으로 나가고, 「상장 전 교차 확인」 행 2개의 비교 제한일 결측은 0 — 교차 확인 표시가 붙은 전 구간 수치는 생기지 않는다. 원래 코드 실행 결과는 저장소와 같고 메타데이터 쌍 20개도 같다. ruff · pyright 통과. 문서의 쌍 목록 포인터는 「묶음별 `*_PAIRS` 표」로. 이 수정분의 재검증을 같은 서브에이전트에 맡겼다
- 2026-10-10 22:00: 수정분 재검증 결과 — 3 hunk 모두 ① ② ③ 에 답, **무거운 발견 0**. 표 변형 10종에서 「상장 전 교차 확인」 표시가 붙고 자르지 않은 행은 0건(모양이 틀린 7종은 exit 1, 교차 확인 쌍을 대체 판 표에 2칸으로 적으면 그 쌍이 「대체 판」 행으로 나간다). 출력 CSV · 메타데이터 쌍 20개 동일, 수정 후 사본 전체 885 passed. 발견 2건(가벼움): 스크립트 주석 「쌍을 잘못된 묶음 이름으로 적을 수 없다」가 보장보다 넓다 · 고친 독스트링이 「둘 다 신호 시세」로 읽으면 틀린다 → 둘 다 문구라 사실에 맞게 고쳤다(재검증 받은 상태와 주석 · 독스트링을 뺀 AST 동일 확인)
  - 재검증이 적어 둔 남는 범위(발견으로 세지 않음): 실물 칸에 «다른 실물 파일»을 적는 값 실수는 막지 못한다 — 표 모양이 아니라 값이 틀린 경우이고, 어디서 잘랐는지는 `summary.csv` 의 「비교 제한」 열과 메타데이터에 드러난다
- 2026-10-10 22:00: 품질 검증 `validate_project.py` 최종 — Ruff · PyRight 통과, Pytest passed=885, failed=0, skipped=0. `storage/` 변경 0
- 2026-10-10 22:00: 미룬 지적 — 새로 옮긴 것 없음. 1회차 ⑩(오류 문구 — 기준 2) · ⑪(엔진 쪽 대조 — 기준 3, 사용자가 HAA 안을 고름), 2회차 ⑥(HAA 대조 목록 — 기준 1), 수정분 검증의 가벼움 4(경계 변형 1종 · 문서 잔재 · 오류 문구 — 기준 2 · 3)는 거름. 수정분 검증의 무거움 2(신호 공유 테스트)는 점검 보고서 2-11 행, 비용률 상수 참조는 3-21 행에 덧붙였다(같은 일을 다룰 단계가 이미 있어 두 벌을 만들지 않는다). 이 계획서가 고친 `DEFERRED_FINDINGS.md` 항목 셋(장부 비용 · HAA 거래일 · 교차 확인 범위)을 지웠다 — 남은 항목 5
- 2026-10-10 22:00: 근거 승격 — HAA 대조의 이유는 `haa.py` 주석과 `src/qbt/backtest/CLAUDE.md`, 표를 묶음별로 둔 이유는 스크립트 주석, 「작은 차이 자체를 검증할 때의 허용오차」는 `tests/CLAUDE.md` 표, 정책 값을 테스트에 고정하는 이유는 해당 테스트의 주석 · 독스트링, `before` 가 자르는 날 0 을 정상으로 두는 이유는 `test_before_after_all_common_dates_keeps_all` 의 독스트링, 처리 사실과 남은 일(2-11 · 3-21 · 5-6)은 점검 보고서
- 2026-10-10 22:02: `/commit` — 대상은 unstaged + untracked(이 계획서) 전체(21파일, staged 없음). 모두 이 계획서 한 묶음이라 분리 제안 없음. 후보 5개를 옮기고 Done

---
