# Implementation Plan: 포트폴리오 D 시리즈 추가 (QQQ 100% / TQQQ 100% 비교군)

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

**작성일**: 2026-03-19 00:00
**마지막 업데이트**: 2026-03-19 00:00
**관련 범위**: backtest, scripts/backtest
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [ ] `portfolio_configs.py`에 D-1 (QQQ 버퍼존 100%), D-2 (TQQQ 버퍼존 100%) 실험 추가
- [ ] `app_portfolio_backtest.py`의 실험 색상 사전에 D-1, D-2 항목 추가
- [ ] `test_portfolio_configs.py` 수정 (개수 9개, D-2 TQQQ 시그널 계약 추가)

## 2) 비목표(Non-Goals)

- 기존 A/B/C 시리즈 설정 변경
- 글로벌 시작일 계산 로직 변경 (D-1/D-2 추가 후에도 동일 기간 유지됨)
- `run_portfolio_backtest.py` 수정 (`PORTFOLIO_CONFIGS` 기반 자동 동작)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

기존 포트폴리오 실험(A/B/C 7가지)에서 비교군이 부족하다.
단일 자산 100% 전략(QQQ 버퍼존 100%, TQQQ 버퍼존 100%)을 포트폴리오 대시보드에서
직접 비교할 수 없어 분산의 효과를 판단하기 어렵다.

D 시리즈 설계:
- D-1: QQQ 버퍼존 100% (단일 자산, 분산 없음, TQQQ 없음)
- D-2: TQQQ 버퍼존 100% (단일 자산, 분산 없음, QQQ 시그널 사용)

글로벌 시작일 영향 분석:
- D-1 (QQQ만): A/B 시리즈에서 이미 QQQ 사용 중 → 글로벌 시작일 변화 없음
- D-2 (TQQQ): C-1에서 이미 TQQQ 사용 중 → 글로벌 시작일 변화 없음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 기능 요구사항 충족 (D-1, D-2 설정 추가 + 색상 추가)
- [ ] 테스트 수정 (개수 7 → 9, D-2 TQQQ 시그널 계약, D 시리즈 신규 테스트)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (backtest/CLAUDE.md의 portfolio_configs 목록)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_configs.py` — D-1, D-2 설정 추가, PORTFOLIO_CONFIGS 확장
- `scripts/backtest/app_portfolio_backtest.py` — `_EXPERIMENT_COLORS` 사전에 D-1, D-2 색상 추가
- `tests/test_portfolio_configs.py` — 개수 7 → 9, D-2 시그널 계약, D 시리즈 테스트 추가
- `src/qbt/backtest/CLAUDE.md` — portfolio_configs 설정 목록 업데이트

### 데이터/결과 영향

- 기존 실험 결과(A/B/C) 재실행 불필요
- D-1, D-2는 `run_portfolio_backtest.py --experiment all` 실행 시 자동 포함됨
- 사용자가 `run_portfolio_backtest.py`를 다시 실행해야 D-1, D-2 결과 생성됨

## 6) 단계별 계획(Phases)

### Phase 1 — portfolio_configs.py D 시리즈 추가

**작업 내용**:

- [ ] `portfolio_configs.py`에 `_CONFIG_D1` (QQQ 100%) 추가
- [ ] `portfolio_configs.py`에 `_CONFIG_D2` (TQQQ 100%, QQQ 시그널) 추가
- [ ] `PORTFOLIO_CONFIGS` 리스트에 `_CONFIG_D1`, `_CONFIG_D2` 추가

---

### Phase 2 — 테스트 수정

**작업 내용**:

- [ ] `test_portfolio_configs_count` 테스트: 7 → 9로 수정
- [ ] `test_b_c_series_tqqq_signal_is_qqq`: `portfolio_d2` 추가
- [ ] D 시리즈 전용 테스트 클래스 추가 (`TestDSeriesConfigs`)
  - D-1: QQQ 100% 전액 투자 검증 (target_weight 합 == 1.0, TQQQ 없음)
  - D-2: TQQQ 100% 전액 투자 검증 (target_weight 합 == 1.0, signal == QQQ)

---

### Phase 3 — app_portfolio_backtest.py 색상 추가

**작업 내용**:

- [ ] `_EXPERIMENT_COLORS`에 `"portfolio_d1"`, `"portfolio_d2"` 색상 추가
  - portfolio_d1: 진한 파란색 계열 (QQQ 단독)
  - portfolio_d2: 진한 주황색 계열 (TQQQ 단독)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md`의 portfolio_configs 설정 목록에 D-1, D-2 추가
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=**)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 / D 시리즈 추가 (QQQ 100%, TQQQ 100% 단일 비교군)
2. 포트폴리오 / 단일 자산 비교군(D-1/D-2) 추가 + 테스트 보강
3. 포트폴리오 / QQQ 버퍼존 100%, TQQQ 버퍼존 100% 실험 추가
4. 포트폴리오 / D 시리즈 실험 추가 + 색상/테스트 반영
5. 포트폴리오 / 비교군(D-1/D-2) 신설 + 대시보드 색상 + 테스트 9개 기준 수정

## 7) 리스크(Risks)

- `test_portfolio_configs_count`가 7로 하드코딩되어 있어 수정 필수 (미수정 시 테스트 실패)
- D-2의 `test_b_c_series_tqqq_signal_is_qqq` 미추가 시 D-2의 TQQQ 시그널 계약 미검증

## 8) 메모(Notes)

- D-1: `experiment_name="portfolio_d1"`, `display_name="D-1 (QQQ 100%)"`
- D-2: `experiment_name="portfolio_d2"`, `display_name="D-2 (TQQQ 100%)"`
- TQQQ는 항상 QQQ 시그널 사용 (B/C 시리즈와 동일 원칙)
- `run_portfolio_backtest.py`는 `PORTFOLIO_CONFIGS` 기반으로 동작하므로 별도 수정 불필요

### 진행 로그 (KST)

- 2026-03-19 00:00: 계획서 작성
