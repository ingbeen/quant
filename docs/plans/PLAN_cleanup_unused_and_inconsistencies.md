# Implementation Plan: 미사용 코드 제거 및 문서/주석 불일치 수정

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

**작성일**: 2026-03-14 15:00
**마지막 업데이트**: 2026-03-14 15:30
**관련 범위**: backtest, scripts, tests, docs
**관련 문서**: CLAUDE.md(루트), src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md, docs/CLAUDE.md

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

- [x] 프로젝트 내 미사용 코드(상수, 함수, export) 제거
- [x] 문서(CLAUDE.md)와 실제 코드/파일 구조 간 불일치 수정
- [x] 코드 주석과 실제 동작 간 불일치 수정

## 2) 비목표(Non-Goals)

- 기능 변경 또는 리팩토링
- 새로운 테스트 추가
- 문서/주석에 구체적 수치 기재 (변경 가능성이 있으므로 패턴/설명만 기술)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 4P 확정 이후 대체된 `DEFAULT_*` 상수가 잔존
- 그리드 서치 CSV용 `DISPLAY_*` 상수가 정의만 되고 미사용
- `load_plateau_detail()` 함수가 존재하나 대응하는 CSV를 생성하는 코드가 없음
- `__init__.py` export 중 외부에서 사용하지 않는 항목 존재
- 코드 변경(recent_months 제거, WFO 추가 등) 후 문서가 미갱신

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 미사용 상수/함수/export 제거 완료
- [x] 문서/주석 불일치 수정 완료
- [x] 테스트 추가 불필요 (동작 변경 없음, 제거만)
- [x] `poetry run python validate_project.py` 통과 (passed=325, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/constants.py` — 미사용 상수 제거
- `src/qbt/backtest/__init__.py` — 미사용 export 정리
- `src/qbt/backtest/strategies/__init__.py` — 미사용 export 정리
- `src/qbt/backtest/parameter_stability.py` — 미사용 함수 제거, docstring 수정
- `src/qbt/backtest/types.py` — 주석 예시 수정
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — 주석 수정
- `CLAUDE.md` (루트) — 디렉토리 구조, 파일 목록 갱신
- `src/qbt/backtest/CLAUDE.md` — 함수/타입 설명 갱신
- `scripts/CLAUDE.md` — app_walkforward.py 설명 수정
- `tests/CLAUDE.md` — 제거된 기능 참조 정리
- `tests/test_parameter_stability.py` — 제거된 함수의 테스트 정리
- `docs/plans/PLAN_remove_recent_months.md` — 상태 갱신

### 데이터/결과 영향

- 없음 (코드 동작 변경 없음)

## 6) 단계별 계획(Phases)

### Phase 1 — 미사용 코드 제거

**작업 내용**:

- [x] `constants.py`: `DEFAULT_MA_WINDOW`, `DEFAULT_BUY_BUFFER_ZONE_PCT`, `DEFAULT_SELL_BUFFER_ZONE_PCT`, `DEFAULT_HOLD_DAYS` 제거
- [x] `constants.py`: `DISPLAY_*` 상수 11개 제거 (DISPLAY_MA_WINDOW ~ DISPLAY_FINAL_CAPITAL)
- [x] `backtest/__init__.py`: `BestGridParams` import/export 제거
- [x] `strategies/__init__.py`: `create_buffer_zone_runner`, `get_buffer_zone_config`, `resolve_buffer_params` import/export 제거
- [x] `parameter_stability.py`: `load_plateau_detail()` 함수 제거
- [x] `test_parameter_stability.py`: `TestLoadPlateauDetail` 클래스 제거

---

### Phase 2 — 문서/주석 불일치 수정

**작업 내용**:

- [x] `types.py`: `strategy_name`, `display_name` 주석 예시를 패턴 설명으로 변경
- [x] `buffer_zone_helpers.py`: `hold_days` 주석을 실제 의미("신호 확정 대기 기간")로 수정
- [x] `buffer_zone_helpers.py`: "sell buffer (고정)" → "초기 sell buffer"로 수정
- [x] `parameter_stability.py`: `load_plateau_pivot` docstring에서 하드코딩된 지표 목록 제거
- [x] 루트 `CLAUDE.md`: grid_results.csv 참조 제거, WFO 결과 파일 추가
- [x] `backtest/CLAUDE.md`: WfoWindowResultDict/WfoModeSummaryDict 설명 수정, constants.py/parameter_stability 섹션 갱신
- [x] `scripts/CLAUDE.md`: app_walkforward.py "탭 자동 생성" → 통합 뷰 설명으로 수정
- [x] `tests/CLAUDE.md`: "동적 파라미터 조정 (최근 매수 기반)" 항목 제거
- [x] `docs/plans/PLAN_remove_recent_months.md`: 상태를 Done으로 변경

---

### Phase 3 — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] `poetry run python validate_project.py` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=325, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 정리 / 미사용 코드 제거 및 문서-코드 불일치 수정
2. 정리 / dead code 제거 + CLAUDE.md 문서 현행화
3. 정리 / 미사용 상수·함수·export 제거, 문서·주석 동기화
4. 정리 / 코드베이스 위생 정비 (미사용 코드, 문서 불일치)
5. 정리 / 프로젝트 전반 미사용 코드 정리 및 문서 갱신

## 7) 리스크(Risks)

- 제거 대상이 실제로 어딘가에서 사용 중일 가능성 → Ruff + PyRight + 테스트로 검증
- CLAUDE.md 수정 시 다른 규칙과 충돌 → 수치 대신 패턴/설명으로 기술하여 완화

## 8) 메모(Notes)

- 문서/주석에 정확한 수치를 기재하지 않음 (변경 가능성이 크므로)
- `docs/CLAUDE.md`의 "Phase 0(레드)", "그린" 표현은 plan 운영 규칙 맥락이므로 유지 (코드 주석 금지 규칙과는 별개)

### 진행 로그 (KST)

- 2026-03-14 15:00: 계획서 작성 완료
- 2026-03-14 15:30: 전체 작업 완료, 검증 통과 (passed=325, failed=0, skipped=0)
