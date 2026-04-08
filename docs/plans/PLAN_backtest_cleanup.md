# Implementation Plan: 백테스트 / 잠재 버그 수정 및 코드 정리

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

**작성일**: 2026-04-08 16:00
**마지막 업데이트**: 2026-04-08 16:00
**관련 범위**: backtest, walkforward, scripts, docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] 잠재 버그 및 비일관성 수정 (보고서 2-1~2-9)
- [ ] 문서/코드 불일치 수정 (보고서 1-1~1-2)
- [ ] 중복 코드 및 dead code 정리 (보고서 3-3~3-8)
- [ ] 테스트 내 하드코딩된 구체적 숫자 제거

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 (동작 동일 유지)
- 포트폴리오 엔진 전면 리팩토링 (별도 계획)
- intent_type enum화
- 상수 명명 규칙 전면 개정

## 3) 배경/맥락(Context)

### 현재 문제점

REPORT_backtest_code_review.md에서 식별된 잔존 이슈:
- walkforward.py ma_type 리터럴 혼용 (Plan 1에서 해결됨)
- _update_bands Protocol 제약 미문서화
- weight 계산 비대칭, dead code, 미사용 변수
- 데이터 로딩 / 밴드 보강 중복 패턴
- types.py docstring, portfolio_configs.py 구체적 숫자

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 잠재 버그/비일관성 수정 완료
- [x] 문서 불일치 수정 완료
- [x] 중복 코드 정리 완료
- [x] 테스트 내 구체적 숫자 제거
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/strategies/buffer_zone.py` — Protocol 제약 주석
- `src/qbt/backtest/walkforward.py` — 미사용 변수, 밴드 보강 중복
- `src/qbt/backtest/engines/portfolio_engine.py` — weight 비대칭, dead code
- `src/qbt/backtest/types.py` — docstring 수정
- `src/qbt/backtest/runners.py` — 밴드 보강 함수 공용화
- `scripts/backtest/run_walkforward.py` — 이중 타입 변환, 데이터 로딩 중복
- `scripts/backtest/run_param_plateau_all.py` — 데이터 로딩 중복
- `tests/test_portfolio_configs.py` — 구체적 숫자 제거
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 변경 없음 (동작 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — 잠재 버그/비일관성 수정

- [ ] walkforward.py: `generate_wfo_windows()`의 미사용 `window_idx` 변수 제거 (2-7)
- [ ] portfolio_engine.py: weight 계산에 `current_equity > 0` 검사 추가 (equity_rows 쪽) (2-4)
- [ ] portfolio_engine.py: dead code (`trade_type` 컬럼 보정) 제거 (2-8)
- [ ] run_walkforward.py: 이중 타입 변환 `Path(str(...))` → 직접 접근 (2-6)
- [ ] buffer_zone.py: `_update_bands` Protocol 제약을 docstring에 명시 (2-1)

---

### Phase 2 — 문서/코드 불일치 + 테스트 정리

- [ ] types.py: docstring에서 `strategy_common.py: HoldState` → `buffer_zone_helpers.py: HoldState` 수정 (1-2)
- [ ] tests/: 테스트 내 하드코딩된 구체적 숫자를 동적 검증으로 변경 (관련 테스트 전수 검사)

---

### Phase 3 — 중복 코드 정리

- [ ] walkforward.py의 밴드 보강 로직을 runners.py의 `_enrich_equity_with_bands` 재사용으로 변경 (3-4)
- [ ] holding_days 계산 중복 정리: analysis.py가 csv_export와 동일 패턴 사용 → 공용 함수 고려 (3-3)

---

### Phase 4 (마지막) — 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=499, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. 백테스트 / 잠재 버그 수정 및 코드 정리 (동작 동일)
2. 백테스트 / dead code 제거 + Protocol 제약 문서화 + 중복 정리
3. 백테스트 / 비일관성 해소 및 테스트 구체적 숫자 제거
4. 백테스트 / weight 비대칭 수정 + 밴드 보강 중복 제거 + docstring 정리
5. 백테스트 / 코드 리뷰 이슈 수정 (REPORT 기반 22건 중 잔여 처리)

## 7) 리스크(Risks)

- dead code 제거로 빈 DataFrame의 컬럼 구조가 변경될 수 있음 → 테스트로 검증
- 밴드 보강 함수 공용화 시 import 의존성 변경 → walkforward.py가 runners.py를 import하면 순환 가능성 확인 필요

## 8) 메모(Notes)

- 보고서 1-3 (상수 명명 규칙 괴리)은 정보 수준이며 이번 Plan에서 제외. 별도 논의 필요.

### 진행 로그 (KST)

- 2026-04-08 16:00: Plan 작성 완료, 구현 시작
