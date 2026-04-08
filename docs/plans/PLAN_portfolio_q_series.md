# Implementation Plan: Q 시리즈 포트폴리오 실험 추가

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

**작성일**: 2026-04-08 19:30
**마지막 업데이트**: 2026-04-08 19:30
**관련 범위**: backtest (portfolio_configs)
**관련 문서**: src/qbt/backtest/CLAUDE.md, tests/CLAUDE.md

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

- [x] Q 시리즈 3개 실험(Q-1, Q-2, Q-3)을 `portfolio_configs.py`에 추가한다
- [x] 기존 테스트(`test_portfolio_configs.py`)가 Q 시리즈를 포함하여 통과한다
- [x] `validate_project.py` 전체 통과 (failed=0, skipped=0)

## 2) 비목표(Non-Goals)

- 실험 실행 (`run_portfolio_backtest.py`)은 사용자가 직접 수행한다
- 결과 분석 및 보고서 업데이트는 실험 실행 후 별도 진행
- Q 시리즈 이외의 기존 실험 변경 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

F-6H(SPY30/TQQQ30/GLD20-BH/TLT20-BH)가 최종 선정되었으나, TQQQ 30% 비중이 합성 데이터(QQQ x 3)에 기반한다는 근본적 약점이 존재한다(v2 보고서 Section 41.1). TQQQ를 QQQ로 교체하면 합성 데이터 리스크가 완전 제거되며, 모든 수치를 실데이터 기반으로 신뢰할 수 있게 된다.

추가로 QQQ는 TQQQ 대비 변동성이 낮아, 방어 자산(GLD/TLT) 40%가 과도할 수 있다. 방어 자산 비중을 30%/35%로 줄이는 민감도 실험도 함께 수행한다.

### Q 시리즈 설계

| 실험 | SPY | QQQ | GLD(B&H) | TLT(B&H) | 방어자산 | 목적 |
|------|-----|-----|----------|----------|----------|------|
| Q-1 | 30% | 30% | 20% | 20% | 40% | F-6H 직접 대체 (TQQQ→QQQ 순수 비교) |
| Q-2 | 35% | 35% | 15% | 15% | 30% | 방어자산 축소, 수익 비중 확대 |
| Q-3 | 30% | 35% | 20% | 15% | 35% | QQQ 약간 비중 확대, GLD:TLT 유지 안 함 |

공통 원칙:
- GLD/TLT는 B&H (`strategy_id="buy_and_hold"`) — F-6H 결론(Section 38) 유지
- 5% 단위 라운드 넘버 — 과최적화 방지 원칙(Section 43) 준수
- SPY/QQQ는 각각 자체 시그널+자체 거래 데이터 사용 (합성 데이터 없음)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] Q-1, Q-2, Q-3 PortfolioConfig가 PORTFOLIO_CONFIGS에 추가됨
- [x] 기존 테스트(test_portfolio_configs.py) 통과 (target_weight 합, asset_id 중복 등 불변조건)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=499, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_configs.py`: Q-1/Q-2/Q-3 config 추가, 모듈 docstring 업데이트
- `README.md`: 변경 없음

### 데이터/결과 영향

- 기존 실험 결과에 영향 없음 (추가만 수행)
- `storage/results/portfolio/portfolio_q1/`, `portfolio_q2/`, `portfolio_q3/` 디렉토리는 실험 실행 시 자동 생성됨

## 6) 단계별 계획(Phases)

### Phase 1 — Q 시리즈 config 추가 (그린 유지)

**작업 내용**:

- [x] `portfolio_configs.py` 모듈 docstring에 Q 시리즈 설명 추가
- [x] `_CONFIG_Q1` 정의: SPY 30% / QQQ 30% / GLD 20%(B&H) / TLT 20%(B&H)
- [x] `_CONFIG_Q2` 정의: SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H)
- [x] `_CONFIG_Q3` 정의: SPY 30% / QQQ 35% / GLD 20%(B&H) / TLT 15%(B&H)
- [x] `PORTFOLIO_CONFIGS` 리스트에 Q 시리즈 추가 (H 시리즈 뒤)

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=499, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 / Q 시리즈 실험 3개 추가 (TQQQ→QQQ 대체 + 방어 비중 민감도)
2. 포트폴리오 / TQQQ 합성 데이터 리스크 제거를 위한 QQQ 기반 실험 추가
3. 포트폴리오 / Q-1~Q-3 실험 config 추가 (실데이터 기반 포트폴리오 대안 탐색)
4. 포트폴리오 / F-6H 대안 실험 추가: QQQ 교체 + GLD/TLT 비중 민감도
5. 포트폴리오 / Q 시리즈 추가 — 합성 데이터 없는 실전 포트폴리오 후보

## 7) 리스크(Risks)

- 리스크 낮음: 기존 코드/실험에 영향 없는 순수 추가 작업
- test_portfolio_configs.py의 불변조건 테스트가 Q 시리즈에 자동 적용됨 (target_weight 합 = 1.0 등)

## 8) 메모(Notes)

- Q-3의 GLD:TLT 비중(20:15)은 F-6H의 1:1 균등 원칙에서 벗어남. 이는 의도적인 민감도 테스트이며, 최종 선정 시 재논의 필요.
- Q 시리즈는 모두 실데이터만 사용하므로, 종료일이 2026-03-31로 통일될 예정 (TQQQ 미포함)

### 진행 로그 (KST)

- 2026-04-08 19:30: 계획서 작성
- 2026-04-08 19:45: Phase 1 완료 — Q-1/Q-2/Q-3 config 추가, test count 34로 업데이트
- 2026-04-08 19:50: Phase 2 완료 — black 포맷 + validate_project.py 통과 (499 passed, 0 failed, 0 skipped)
