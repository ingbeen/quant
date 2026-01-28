# Implementation Plan: Streamlit 튜닝 연산 분리 및 테스트 재구현

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

**작성일**: 2026-01-27 20:30
**마지막 업데이트**: 2026-01-28
**관련 범위**: tqqq, scripts, tests
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: Streamlit 앱에서 연산 로직(softplus 튜닝, 워크포워드 검증)을 CLI 스크립트로 분리
- [x] 목표 2: spawn 방식 병렬처리 시 Streamlit 경고 문구 제거
- [x] 목표 3: 주석 처리된 7개 테스트를 삭제하고 새 구조에 맞게 재구현 (병렬 전체 실행 제외)

## 2) 비목표(Non-Goals)

- parallel_executor.py의 spawn 방식 변경 (fork로 전환하지 않음)
- 병렬처리 전체를 실행하는 테스트 코드 구현 (너무 오래 걸림)
- Streamlit 앱 UI/UX 변경 (기존 시각화 기능 유지)
- 성능 추가 최적화 (이전 계획서에서 완료)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**1. Streamlit 경고 문구 발생**

```
WARNING streamlit.runtime.caching.cache_data_api: No runtime found, using MemoryCacheStorageManager
```

- 원인: spawn 방식 병렬처리 시 워커가 모듈을 재임포트하면서 `@st.cache_data` 데코레이터 실행
- 워커 프로세스에는 Streamlit 런타임이 없어 경고 발생 (14회 반복)

**2. 아키텍처 불일치**

- 현재: Streamlit 앱 내에서 연산 로직 직접 호출
- 권장: CLI 계층(scripts/)에서 연산, Streamlit은 시각화 전용

**3. 주석 처리된 테스트 코드**

- `test_tqqq_simulation.py` 하단 7개 테스트가 주석 처리됨
- 워크포워드 검증 테스트는 실행 시간이 오래 걸려 임시 비활성화

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- 작업 도메인 `CLAUDE.md`: `src/qbt/tqqq/CLAUDE.md`
- 스크립트 `CLAUDE.md`: `scripts/CLAUDE.md`
- 테스트 `CLAUDE.md`: `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] CLI 스크립트 생성: `scripts/tqqq/run_softplus_tuning.py`
- [x] CLI 스크립트 생성: `scripts/tqqq/run_walkforward_validation.py`
- [x] Streamlit 앱에서 튜닝 버튼 제거 및 CSV 로드 방식으로 변경
- [x] 주석 처리된 7개 테스트 삭제
- [x] 새 구조에 맞는 테스트 코드 추가 (병렬 전체 실행 제외)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**신규 생성:**
- `scripts/tqqq/run_softplus_tuning.py` - softplus 튜닝 CLI
- `scripts/tqqq/run_walkforward_validation.py` - 워크포워드 검증 CLI

**수정:**
- `scripts/tqqq/streamlit_rate_spread_lab.py` - 튜닝 버튼 제거, CSV 로드 방식으로 변경
- `tests/test_tqqq_simulation.py` - 주석 테스트 삭제, 새 테스트 추가
- `src/qbt/tqqq/constants.py` - 튜닝 결과 CSV 경로 상수 추가

### 데이터/결과 영향

- 신규 CSV 파일: `storage/results/tqqq_softplus_tuning.csv`
- 신규 CSV 파일: `storage/results/tqqq_walkforward_validation.csv`
- 기존 결과 비교: 해당 없음 (새 파일 생성)

## 6) 단계별 계획(Phases)

### Phase 1 — CLI 스크립트 생성 및 상수 추가

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 튜닝 결과 CSV 경로 상수 추가
  - `SOFTPLUS_TUNING_CSV_PATH`
  - `WALKFORWARD_VALIDATION_CSV_PATH`
- [x] `scripts/tqqq/run_softplus_tuning.py` 생성
  - 데이터 로딩 (QQQ, TQQQ, FFR, Expense)
  - `find_optimal_softplus_params()` 호출
  - 결과 CSV 저장 + 메타데이터 저장
  - `@cli_exception_handler` 데코레이터 적용
- [x] `scripts/tqqq/run_walkforward_validation.py` 생성
  - 데이터 로딩
  - `run_walkforward_validation()` 호출
  - 결과 CSV 저장 + 메타데이터 저장
  - `@cli_exception_handler` 데코레이터 적용

**Validation**:

- [x] `poetry run python validate_project.py` (passed=241, failed=0, skipped=0)

---

### Phase 2 — Streamlit 앱 수정

**작업 내용**:

- [x] `streamlit_rate_spread_lab.py`에서 튜닝 버튼 및 관련 코드 제거
  - `_run_softplus_tuning()` 함수 제거
  - 튜닝 실행 UI 섹션 제거
- [x] CSV 로드 방식으로 변경
  - 튜닝 결과 CSV 로드 함수 추가
  - CSV 존재 여부 체크 및 안내 메시지
- [x] 워크포워드 검증 결과 표시 섹션 추가 (선택적)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=241, failed=0, skipped=0)

---

### Phase 3 — 테스트 코드 재구현

**작업 내용**:

- [x] 주석 처리된 7개 테스트 삭제 (line 1998~2377)
  - `TestLocalRefineSearch` 클래스 (2개)
  - `TestRunWalkforwardValidation` 클래스 (5개)
- [x] 새 구조에 맞는 테스트 추가 (병렬 전체 실행 제외)
  - `_local_refine_search` 단위 테스트: 작은 그리드로 기본 동작 검증
  - `run_walkforward_validation` 인터페이스 테스트: 예외 케이스만 검증
  - CLI 스크립트 존재 및 임포트 테스트

**테스트 설계 원칙**:
- 병렬처리 전체 실행 제외 (max_workers=1 또는 monkeypatch로 그리드 축소)
- 예외 케이스 검증 (데이터 부족, FFR 갭 등)
- 인터페이스/계약 검증 (반환 타입, 필수 키)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=244, failed=0, skipped=0)

---

### Phase 4 — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트 (CLI 스크립트 설명 추가)
- [x] `scripts/CLAUDE.md` 업데이트 (새 스크립트 설명 추가)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] CLI 스크립트 실행 테스트 (수동)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=244, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Streamlit 연산 분리 (softplus 튜닝, 워크포워드 CLI화)
2. TQQQ시뮬레이션 / 튜닝 CLI 분리로 spawn 경고 해결 + 테스트 재구현
3. TQQQ시뮬레이션 / 연산-시각화 계층 분리 (CLI + Streamlit)
4. TQQQ시뮬레이션 / CLI 스크립트 추가 및 테스트 정리
5. TQQQ시뮬레이션 / 아키텍처 개선 (연산 CLI 분리, 테스트 재작성)

## 7) 리스크(Risks)

- CLI 스크립트 실행 후 Streamlit 앱에서 결과를 못 찾을 수 있음
  - 완화책: CSV 미존재 시 명확한 안내 메시지 표시
- 테스트 재구현 시 커버리지 감소 가능
  - 완화책: 핵심 계약/예외 케이스 위주로 검증

## 8) 메모(Notes)

### 분리 후 사용 흐름

```bash
# 1. softplus 튜닝 실행 (CLI)
poetry run python scripts/tqqq/run_softplus_tuning.py

# 2. 워크포워드 검증 실행 (CLI)
poetry run python scripts/tqqq/run_walkforward_validation.py

# 3. 결과 시각화 (Streamlit)
poetry run streamlit run scripts/tqqq/streamlit_rate_spread_lab.py
```

### 삭제 대상 테스트 목록 (7개)

| 클래스 | 함수 | 라인 |
|--------|------|------|
| `TestLocalRefineSearch` | `test_local_refine_search_basic` | 2008-2060 |
| `TestLocalRefineSearch` | `test_local_refine_search_b_non_negative` | 2062-2106 |
| `TestRunWalkforwardValidation` | `test_walkforward_start_point_calculation` | 2116-2172 |
| `TestRunWalkforwardValidation` | `test_walkforward_result_schema` | 2174-2234 |
| `TestRunWalkforwardValidation` | `test_walkforward_first_window_full_grid` | 2236-2282 |
| `TestRunWalkforwardValidation` | `test_walkforward_subsequent_windows_local_refine` | 2284-2331 |
| `TestRunWalkforwardValidation` | `test_walkforward_insufficient_data_raises` | 2333-2376 |

### 진행 로그 (KST)

- 2026-01-27 20:30: 계획서 초안 작성
- 2026-01-28: Phase 1-4 완료, 상태 Done

---
