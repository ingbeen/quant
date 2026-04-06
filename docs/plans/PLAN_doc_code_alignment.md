# Implementation Plan: 문서/주석/소스코드 불일치 수정

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

**작성일**: 2026-04-07 00:30
**마지막 업데이트**: 2026-04-07 01:00
**관련 범위**: docs, CLAUDE.md (root/backtest/scripts/tests), README.md
**관련 문서**: `CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `README.md`

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

- [ ] 루트 CLAUDE.md의 디렉토리 구조를 실제 파일 시스템과 일치시킨다
- [ ] src/qbt/backtest/CLAUDE.md의 함수명/클래스명/섹션 번호 오류를 수정한다
- [ ] README.md의 디렉토리 구조 및 예시를 실제 코드와 일치시킨다
- [ ] scripts/CLAUDE.md의 메타데이터 타입 목록을 실제 코드와 일치시킨다
- [ ] tests/CLAUDE.md의 테스트 파일 목록을 실제 파일과 일치시킨다

## 2) 비목표(Non-Goals)

- 소스코드(.py) 변경: 문서/주석만 수정하며 비즈니스 로직은 변경하지 않는다
- 새로운 테스트 추가 또는 기존 테스트 수정
- 결과 데이터(CSV/JSON) 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

포트폴리오 엔진이 4개 하위 모듈로 분리되고, F 시리즈가 확장(F5~F7h 추가)되는 등 코드가 진화했으나 문서가 업데이트되지 않아 불일치 발생.

### 발견된 불일치 목록

#### A. 루트 CLAUDE.md — 디렉토리 구조 누락

| 누락된 파일/폴더 | 실제 위치 |
|---|---|
| `csv_export.py` | `src/qbt/backtest/csv_export.py` |
| `strategy_registry.py` | `src/qbt/backtest/strategy_registry.py` |
| `buffer_zone_helpers.py` | `src/qbt/backtest/strategies/buffer_zone_helpers.py` |
| `portfolio_data.py` | `src/qbt/backtest/engines/portfolio_data.py` |
| `portfolio_execution.py` | `src/qbt/backtest/engines/portfolio_execution.py` |
| `portfolio_planning.py` | `src/qbt/backtest/engines/portfolio_planning.py` |
| `portfolio_rebalance.py` | `src/qbt/backtest/engines/portfolio_rebalance.py` |
| `split_buffer_zone_qqq/` | `storage/results/backtest/split_buffer_zone_qqq/` |
| `split_buffer_zone_tqqq/` | `storage/results/backtest/split_buffer_zone_tqqq/` |
| `portfolio/` 하위 폴더 | `storage/results/portfolio/` (F시리즈 확장: f5~f7h) |

#### B. src/qbt/backtest/CLAUDE.md — 잘못된 이름/번호

| 문서 표기 | 실제 코드 | 파일 |
|---|---|---|
| `_generate_signal_intents` | `generate_signal_intents` | portfolio_planning.py |
| `_compute_projected_portfolio` | `compute_projected_portfolio` | portfolio_planning.py |
| `_merge_intents` | `merge_intents` | portfolio_planning.py |
| `_execute_orders` | `execute_orders` | portfolio_execution.py |
| `_is_first_trading_day_of_month` | `is_first_trading_day_of_month` | portfolio_rebalance.py |
| `_compute_portfolio_equity` | `compute_portfolio_equity` | portfolio_planning.py |
| `_create_strategy_for_slot` | `create_strategy_for_slot` | portfolio_planning.py |
| `_ProjectedPortfolio` | `ProjectedPortfolio` | portfolio_planning.py |
| `_AssetState` | `AssetState` | portfolio_types.py |
| `_ExecutionResult` | `ExecutionResult` | portfolio_execution.py |
| `_DEFAULT_REBALANCE_POLICY` | `DEFAULT_REBALANCE_POLICY` | portfolio_rebalance.py |
| 섹션 10 중복 (strategies, runners) | 10→10, 11→runners, 12→csv | 섹션 번호 오류 |
| `_AssetState`를 portfolio_execution.py 소속으로 설명 | `AssetState`는 portfolio_types.py에 정의 | 모듈 위치 오류 |

#### C. README.md

| 위치 | 문제 | 수정 방향 |
|---|---|---|
| Line 47 | `buffer_zone_spy` 예시가 DEFAULT_SINGLE_BACKTEST_STRATEGIES에 없음 | `buffer_zone_tlt`로 변경 |
| Line 165-168 | `test_buffer_zone_helpers.py` 파일이 존재하지 않음 | `test_buffer_zone_run.py`로 변경 |
| Lines 235-238 | engines/ 하위 4개 모듈 누락 | 추가 |

#### D. scripts/CLAUDE.md

| 위치 | 문제 |
|---|---|
| Line 53-58 | `"portfolio_backtest"` 메타데이터 타입 누락 |

#### E. tests/CLAUDE.md

| 문제 | 상세 |
|---|---|
| 누락된 테스트 파일 | `test_strategy_interface.py`, `test_strategy_registry.py` 가 폴더구조 목록에 없음 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 문서 내구성 원칙
- `docs/CLAUDE.md`: 계획서 운영 규칙

## 4) 완료 조건(Definition of Done)

- [x] 루트 CLAUDE.md 디렉토리 구조가 실제 파일과 일치
- [x] backtest CLAUDE.md의 함수명/클래스명이 실제 코드와 일치
- [x] backtest CLAUDE.md의 섹션 번호가 올바르게 연속
- [x] README.md의 예시/디렉토리 구조가 실제와 일치
- [x] scripts/CLAUDE.md의 메타데이터 타입 목록이 완전
- [x] tests/CLAUDE.md의 테스트 파일 목록이 실제와 일치
- [x] `poetry run python validate_project.py` 통과 (passed=483, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `README.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

### 데이터/결과 영향

- 없음 (문서만 변경)

## 6) 단계별 계획(Phases)

### Phase 1 — 문서 불일치 수정

**작업 내용**:

- [x] 루트 CLAUDE.md: 디렉토리 구조에 누락 파일 추가 (csv_export.py, strategy_registry.py, buffer_zone_helpers.py, portfolio_* 엔진 4개, split_buffer_zone 결과 폴더, portfolio/ 결과 폴더)
- [x] backtest CLAUDE.md: 함수명/클래스명에서 잘못된 언더스코어 접두사 제거 (11개 항목) + 모듈 소속 표기 추가
- [x] backtest CLAUDE.md: 섹션 번호 수정 (10→10 strategies, 10→11 runners, 12→12 csv_export)
- [x] backtest CLAUDE.md: AssetState 모듈 위치를 portfolio_types.py로 수정, portfolio_execution.py 설명 수정
- [x] README.md: Line 47 buffer_zone_spy → buffer_zone_tlt
- [x] README.md: Line 165-168 test_buffer_zone_helpers.py → test_buffer_zone_run.py
- [x] README.md: Lines 235-238 engines/ 하위 모듈 추가
- [x] scripts/CLAUDE.md: "portfolio_backtest" 메타데이터 타입 추가
- [x] tests/CLAUDE.md: test_strategy_interface.py, test_strategy_registry.py 추가 + test_buffer_zone_helpers.py 참조를 test_buffer_zone_run.py로 수정

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] 변경 문서 전체 교차 검증
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=483, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서 / 문서-소스코드 불일치 일괄 수정 (디렉토리 구조, 함수명, 섹션 번호)
2. 문서 / CLAUDE.md 5개 파일 + README.md 동기화
3. 문서 / 포트폴리오 엔진 분리 후 누락된 문서 업데이트
4. 문서 / 디렉토리 트리, API명, 메타타입 불일치 수정
5. 문서 / 전체 CLAUDE.md + README 실제 코드 기준 정렬

## 7) 리스크(Risks)

- 문서만 변경하므로 회귀 위험 없음
- validate_project.py는 .md 파일을 검사하지 않으므로 수동 교차 검증 필요

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-07 00:30: 계획서 작성 완료, Phase 1 착수
- 2026-04-07 01:00: Phase 1 + 마지막 Phase 완료. validate_project.py 통과 (passed=483, failed=0, skipped=0)

---
