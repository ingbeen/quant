# Implementation Plan: 문서 정리 (포트폴리오 명시 제거 / 로그차이 정의 통일 / 기타)

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

**작성일**: 2026-04-10 10:19
**마지막 업데이트**: 2026-04-10 10:30
**관련 범위**: docs, scripts, src/qbt/backtest, src/qbt/tqqq, tests, validate_project
**관련 문서**: 루트 CLAUDE.md, scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, tests/CLAUDE.md

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

- [x] 변경 가능성이 큰 포트폴리오 실험 목록/시리즈 명시를 문서에서 제거하고, 코드 참조 안내와 "직접 명시 금지" 주의문을 추가한다.
- [x] 누적배수 로그차이 지표 2종(abs / signed)을 문서·docstring에서 일관된 정의로 통일한다.
- [x] 비용 모델의 왕복 비용(= 2 × SLIPPAGE_RATE) 의미를 주석/문서에 명시한다.
- [x] 루트 CLAUDE.md 디렉토리 트리의 변경 가능성 높은 나열(포트폴리오 A~H) 및 tests/CLAUDE.md 누락 파일을 정리한다.
- [x] validate_project.py의 이모지 사용을 텍스트 라벨로 치환한다.

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 금지 (수식/분기/상수값 불변).
- csv_export ↔ analysis 의존 방향 리팩토링은 Plan 3에서 처리한다.
- 불변조건 위반 중단 포인트 추가는 Plan 2에서 처리한다.
- app_portfolio_backtest 도메인 로직 이동은 Plan 4에서 처리한다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `PORTFOLIO_CONFIGS`가 실험 추가/삭제로 자주 변경되는데, 루트 CLAUDE.md·scripts/CLAUDE.md·src/qbt/backtest/CLAUDE.md·README.md가 A~H 시리즈 / portfolio_a2 등 구체 실험명을 명시하고 있어 문서가 쉽게 stale 된다. 이미 실제 코드에는 D·F·Q 시리즈만 존재하여 불일치가 관측된다.
- TQQQ 누적배수 로그차이는 abs(`simulation._calculate_cumul_multiple_log_diff`)와 signed(`analysis_helpers.calculate_signed_log_diff_from_cumulative_returns`) 2종인데, CLAUDE.md·두 함수의 docstring이 각각 다른 분자/분모 순서로 기술되어 독자 혼동을 유발한다. 수학적으로는 abs 버전은 방향 무관이므로 문제 없으나, 정의 모양이 달라 "버그로 오인"될 위험.
- `SLIPPAGE_RATE`는 매수/매도 각각 1회 적용(왕복 0.6%)이 의도된 설계이나, 주석/도메인 문서에 "왕복 비용" 관점 설명이 없어 감사/디버깅 시 슬리피지 이중 적용 오해를 유발.
- `tests/CLAUDE.md`에 `test_portfolio_state_log.py`, `test_portfolio_validation.py`가 누락되어 있다.
- `validate_project.py`가 `✓`, `✗`, `🎉`, `❌` 이모지를 사용해 루트 CLAUDE.md "이모지 사용 금지" 정책을 직접 위반.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`
- `docs/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 루트 CLAUDE.md / scripts/CLAUDE.md / src/qbt/backtest/CLAUDE.md / README.md에서 구체 포트폴리오 실험명·시리즈(A~H) 나열이 제거되었고, "직접 명시 금지" 주의문이 도메인 문서에 추가됨
- [x] src/qbt/tqqq/CLAUDE.md의 "누적배수 로그차이" 섹션이 abs/signed 2종 지표를 명확히 구분 기술하고, src/qbt/tqqq/simulation.py의 `_calculate_cumul_multiple_log_diff` docstring이 절댓값 표기(`| |`)로 정정됨
- [x] src/qbt/backtest/CLAUDE.md "비용 모델" 섹션 또는 src/qbt/backtest/constants.py `SLIPPAGE_RATE` 주석에 왕복 비용 의미가 명시됨
- [x] tests/CLAUDE.md의 테스트 파일 목록이 실제 `tests/` 내용과 일치함
- [x] validate_project.py에서 이모지가 제거되고 텍스트 라벨로 대체됨
- [x] `poetry run python validate_project.py` 통과 (passed=495, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] README.md 업데이트 완료 (A~H 시리즈 문구 정리)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `CLAUDE.md` (루트): 디렉토리 트리의 `portfolio_configs.py` 주석에서 "A~H 시리즈" 제거
- `README.md`: A~H 시리즈/portfolio_a2 예시 → "실험 구성은 `PORTFOLIO_CONFIGS` 참고"
- `scripts/CLAUDE.md`: 포트폴리오 섹션 주의문 추가 (변경 빈번, 코드 참조)
- `src/qbt/backtest/CLAUDE.md`: `portfolio_configs.py` 섹션에서 A~H 시리즈 나열 삭제 + 주의문, `비용 모델` 섹션에 왕복 비용 명시
- `src/qbt/backtest/constants.py`: `SLIPPAGE_RATE` 주석 보강(왕복 비용 = 0.006)
- `src/qbt/tqqq/CLAUDE.md`: "누적배수 로그차이" 섹션을 abs/signed 2종 설명으로 재작성
- `src/qbt/tqqq/simulation.py`: `_calculate_cumul_multiple_log_diff` docstring 정정 (절댓값 표기 복원)
- `tests/CLAUDE.md`: `test_portfolio_state_log.py`, `test_portfolio_validation.py` 추가
- `validate_project.py`: 이모지(`✓ ✗ 🎉 ❌`) → 텍스트 라벨(`[OK] [FAIL] [SUCCESS] [FAILED]`)
- `README.md`: (변경 있음)

### 데이터/결과 영향

- 출력 스키마 변경 없음.
- 기존 결과 CSV/JSON 비교 불필요.
- validate_project.py 콘솔 출력 문구가 이모지 → 텍스트로 바뀌지만 종료 코드/동작 동일.

## 6) 단계별 계획(Phases)

### Phase 1 — 포트폴리오 실험 명시 제거

**작업 내용**:

- [x] 루트 `CLAUDE.md` 디렉토리 트리에서 `portfolio_configs.py  # 포트폴리오 실험 설정 (A~H 시리즈)` → `portfolio_configs.py  # 포트폴리오 실험 설정 (목록은 PORTFOLIO_CONFIGS 참고)` 로 수정
- [x] `README.md`에서 A~H 시리즈 나열 및 `portfolio_a2` 예시를 제거하고 코드 참조 안내로 교체
- [x] `scripts/CLAUDE.md`의 포트폴리오 섹션에 "실험 목록은 자주 변경되므로 문서에 직접 명시하지 않는다. 최신 값은 `src/qbt/backtest/portfolio_configs.py`의 `PORTFOLIO_CONFIGS`를 직접 확인할 것." 주의문 추가
- [x] `src/qbt/backtest/CLAUDE.md`의 `portfolio_configs.py` 섹션에서 A~H 시리즈 불릿 나열 제거, "실험 구성은 `PORTFOLIO_CONFIGS` 참고" + 동일 주의문 추가

---

### Phase 2 — 누적배수 로그차이 문서 통일

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md`의 "누적배수 로그차이 계산" 섹션을 abs/signed 2종 지표로 재작성 (공통 M 정의 + 각 지표의 용도·수식·부호 해석)
- [x] `src/qbt/tqqq/simulation.py`의 `_calculate_cumul_multiple_log_diff` docstring에서 수식 표기를 `로그차이(%) = |ln(M_actual(t) / M_sim(t))| × 100` 형태로 유지 + "절댓값이므로 분자/분모 순서 무관" 한 줄 추가
- [x] 문서·docstring 간 기술이 모순되지 않는지 재확인

---

### Phase 3 — 기타 문서/주석/라벨 정리

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`의 "비용 모델" 섹션에 "왕복(매수+매도) 비용 = 2 × SLIPPAGE_RATE" 설명 추가
- [x] `src/qbt/backtest/constants.py`의 `SLIPPAGE_RATE` 주석을 `# 0.3% / 매수 or 매도 1회 (왕복 0.6%)`로 보강
- [x] `tests/CLAUDE.md`의 테스트 파일 목록에 `test_portfolio_state_log.py`, `test_portfolio_validation.py` 추가 (포트폴리오 관련 항목 근처)
- [x] `validate_project.py`의 `✓`, `✗`, `🎉`, `❌` 문자를 각각 `[OK]`, `[FAIL]`, `[SUCCESS]`, `[FAILED]`로 치환

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 확인 (README.md 포함 — 변경 있음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=495, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서 / 포트폴리오 실험 명시 제거 + 누적배수 로그차이 정의 통일 + 비용 주석 보강
2. 문서 / 변경 가능성 높은 실험 목록 문서화 제거 및 지표 정의 정리
3. 문서 / CLAUDE.md 정리 (포트폴리오·로그차이·슬리피지) + validate_project 이모지 제거
4. 문서 / 도메인 가이드 일관성 정리 + tests 목록 보정
5. 문서 / 정합성 정리 (포트폴리오·로그차이·왕복비용·이모지·tests 목록)

## 7) 리스크(Risks)

- README.md 예시 변경 시 README 외부 문서에서 끊긴 링크 없음 확인 필요 (내부 docs/archive는 무시)
- validate_project.py 콘솔 출력 변경이 기존 스크린샷/문서 참조와 차이를 만들 수 있음 — 사용자에게 표기 변경 고지 정도로 충분
- Phase 간 의존성은 독립적이므로 하나의 Phase 실패가 다른 Phase를 막지 않음

## 8) 메모(Notes)

- 본 plan은 문서·주석·console 라벨만 변경하며 비즈니스 로직·산식·분기·상수값을 변경하지 않음.
- Plan 2~4와 파일 겹침이 최소화되도록 도메인별 독립 파일에 집중. Phase 3의 `src/qbt/backtest/constants.py` 수정은 주석만이며 Plan 2의 불변조건 강화와 충돌하지 않음.

### 진행 로그 (KST)

- 2026-04-10 10:19: Plan 작성
- 2026-04-10 10:25: Phase 1 (포트폴리오 명시 제거) 완료
- 2026-04-10 10:27: Phase 2 (로그차이 정의 통일) 완료
- 2026-04-10 10:29: Phase 3 (SLIPPAGE 주석/tests 목록/이모지 제거) 완료
- 2026-04-10 10:30: 마지막 Phase 완료 — black + validate_project 통과 (passed=495, failed=0, skipped=0)

---
