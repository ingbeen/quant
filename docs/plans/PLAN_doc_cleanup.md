# Implementation Plan: 문서/주석 내구성 개선 — 가변 정보 제거 및 역할 중심 설명으로 전환

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

**작성일**: 2026-03-26 00:00
**마지막 업데이트**: 2026-03-26 09:00
**관련 범위**: backtest, scripts, README
**관련 문서**: 루트 CLAUDE.md, scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md

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

- [x] 문서/주석에서 실험 개수(7가지, 25가지, 7개, 4개 등)를 제거한다.
- [x] 문서/주석에서 실험 ID 나열(portfolio_a1 ~ portfolio_c1 등)을 제거한다.
- [x] 구체적 스냅샷 정보 대신 역할/책임 중심 설명으로 교체한다.
- [x] 코드 로직은 일절 변경하지 않는다.

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경
- 테스트 추가/수정 (문서-only 변경이므로 테스트 불필요)
- `app_walkforward.py`의 VERBATIM "현재 판단" 섹션 (의도적으로 날짜 기준 스냅샷, 별도 정리 필요)
- `docs/strategy_validation_report.md` (분석 보고서 특성상 구체 수치가 의미 있음)
- `docs/archive/` 하위 문서 (과거 기록, 변경 불필요)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **개수 불일치**: `portfolio_configs.py` 주석, `scripts/CLAUDE.md`, `app_portfolio_backtest.py` 등 여러 곳에서 "7가지 포트폴리오 실험"으로 기술하고 있으나 실제 코드에는 A~H 시리즈 25개 실험이 정의되어 있다.
2. **특정 ID 나열**: `portfolio_a1 ~ portfolio_c1` 같은 나열이 문서에 박혀 있어 실험이 추가/변경되면 문서가 즉시 틀려진다.
3. **특정 시리즈명 고정**: `A/B/C 시리즈` 등 현재 일부 시리즈만 언급해 확장 시 오해 유발.
4. **파라미터 수치 하드코딩**: README에 `MA=200, buy=0.03, sell=0.05, hold=3` 등 구체 수치가 박혀 있어 파라미터 변경 시 문서가 stale해진다.
5. **존재하지 않는 파일 참조**: `PLAN_portfolio_experiment.md` 참조가 UI caption에 남아 있으나 해당 파일은 없다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족 (개수 표현 제거, 역할 중심 설명 적용)
- [x] 테스트 추가 없음 (문서-only 변경)
- [x] `poetry run python validate_project.py` 통과 (passed=394, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 위치 | 변경 유형 |
|------|-----------|-----------|
| `src/qbt/backtest/portfolio_configs.py` | 주석 L41 | 개수 표현 제거 |
| `src/qbt/backtest/CLAUDE.md` | L187, L190, L191-197, L437 | 개수/ID 나열 제거 |
| `scripts/CLAUDE.md` | L138-139, L143, L145, L147, L159, L165, L169 | 개수/ID/시리즈명 정리 |
| `scripts/backtest/app_portfolio_backtest.py` | L3, L310, L800 | 개수/시리즈명/plan 참조 제거 |
| `scripts/backtest/run_portfolio_backtest.py` | 주석 L281 | 개수 표현 제거 |
| `scripts/backtest/run_param_plateau_all.py` | docstring L3 | 개수 표현 제거 |
| `scripts/backtest/app_single_backtest.py` | caption L902 | 구간 개수 제거 |
| `README.md` | L8-9, L37, L63, L84, L295-324 | 개수/수치/실험 목록 제거 |

### 데이터/결과 영향

- 없음 (문서/주석만 변경, 비즈니스 로직 미변경)

## 6) 단계별 계획(Phases)

### Phase 1 — 문서/주석 수정 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/portfolio_configs.py` 주석 수정
- [x] `src/qbt/backtest/CLAUDE.md` 수정 (개수/ID/시리즈 나열 제거)
- [x] `scripts/CLAUDE.md` 수정
- [x] `scripts/backtest/app_portfolio_backtest.py` 수정
- [x] `scripts/backtest/run_portfolio_backtest.py` 주석 수정
- [x] `scripts/backtest/run_param_plateau_all.py` docstring 수정
- [x] `scripts/backtest/app_single_backtest.py` caption 수정
- [x] `README.md` 수정

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=394, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서/주석 / 가변 정보 제거 — 역할 중심 설명으로 전환
2. 문서/주석 / 실험 개수·ID 하드코딩 제거 및 내구성 개선
3. 문서/주석 / 리팩토링 내성 강화 — 구체 수치·시리즈 나열 정리
4. 백테스트 / 문서 cleanup — 7가지→역할 기술, 개수 표현 일괄 제거
5. 문서/주석 / stale 개수·실험ID 제거 + 역할 중심 설명 통일

## 7) 리스크(Risks)

- 없음 (문서-only, 비즈니스 로직 미변경)

## 8) 메모(Notes)

### 변경 제외 항목 (의도적 유지)

- `app_walkforward.py` VERBATIM "현재 판단" 섹션: 날짜 기준 스냅샷으로 의도적 구조, 별도 정리 필요
- `docs/strategy_validation_report.md`: 분석 보고서 특성상 구체 수치 유의미
- `scripts/backtest/run_param_plateau_all.py` `_ASSET_CONFIGS` 내 자산 목록: 비즈니스 로직(코드)이므로 변경 없음
- `scripts/backtest/app_parameter_stability.py`: 탭 구성 등 내부 로직, 범위 외

### 진행 로그 (KST)

- 2026-03-26 00:00: 계획서 작성 완료, Phase 1 시작
- 2026-03-26 09:00: 전체 수정 완료, validate_project.py passed=394, failed=0, skipped=0
