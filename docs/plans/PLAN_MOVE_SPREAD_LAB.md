# Implementation Plan: 스프레드 검증 파일 하위폴더 분리

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-15 22:30
**마지막 업데이트**: 2026-02-15 23:00
**관련 범위**: tqqq, scripts, docs
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] SoftPlus 스프레드 검증용 스크립트를 `scripts/tqqq/spread_lab/`으로 이동
- [x] SoftPlus 스프레드 검증용 결과 CSV를 `storage/results/spread_lab/`으로 이동
- [x] 모든 경로 참조(상수, docstring, 에러 메시지, 문서) 업데이트

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 (함수 시그니처, 계산 로직 등)
- 테스트 코드 변경 (기존 테스트는 `RESULTS_DIR` 기반 상수를 사용하므로 상수만 바뀌면 됨)
- 기존 결과 CSV 파일 내용 변경 (경로만 이동)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- SoftPlus 스프레드 모델이 확정되어 검증용 스크립트/결과의 사용 빈도가 크게 감소
- `scripts/tqqq/`에 핵심 스크립트(3개)와 검증용 스크립트(6개)가 혼재
- `storage/results/`에 핵심 결과(3개)와 검증용 결과(12개)가 혼재
- 하위폴더 분리로 핵심 파일과 검증용 파일을 명확히 구분

### 파일 분류

**메인에 남길 파일 (scripts/tqqq/):**
- `generate_daily_comparison.py` — 일별 비교 데이터 생성
- `generate_synthetic.py` — 합성 데이터 생성
- `app_daily_comparison.py` — 일별 비교 대시보드

**spread_lab/으로 이동할 스크립트 (6개):**
- `app_rate_spread_lab.py`
- `generate_rate_spread_lab.py`
- `tune_softplus_params.py`
- `validate_walkforward.py`
- `validate_walkforward_fixed_b.py`
- `validate_walkforward_fixed_ab.py`

**메인에 남길 결과 파일 (storage/results/):**
- `grid_results.csv` — 백테스트 그리드 서치
- `meta.json` — 메타데이터
- `tqqq_daily_comparison.csv` — 일별 비교

**spread_lab/으로 이동할 결과 CSV (12개):**
- `tqqq_rate_spread_lab_monthly.csv`
- `tqqq_rate_spread_lab_summary.csv`
- `tqqq_rate_spread_lab_model.csv`
- `tqqq_rate_spread_lab_walkforward.csv`
- `tqqq_rate_spread_lab_walkforward_summary.csv`
- `tqqq_rate_spread_lab_walkforward_fixed_b.csv`
- `tqqq_rate_spread_lab_walkforward_fixed_b_summary.csv`
- `tqqq_rate_spread_lab_walkforward_fixed_ab.csv`
- `tqqq_rate_spread_lab_walkforward_fixed_ab_summary.csv`
- `tqqq_softplus_tuning.csv`
- `tqqq_softplus_spread_series_static.csv`

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 스크립트 6개가 `scripts/tqqq/spread_lab/`으로 이동
- [x] 결과 CSV 12개가 `storage/results/spread_lab/`으로 이동 (기존 파일 삭제)
- [x] 경로 상수 업데이트 (`src/qbt/tqqq/constants.py`)
- [x] 스크립트 내 docstring/에러메시지의 경로 참조 업데이트
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 문서 업데이트 (README.md, CLAUDE.md(루트), scripts/CLAUDE.md, src/qbt/tqqq/CLAUDE.md)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**경로 상수 변경:**
- `src/qbt/tqqq/constants.py`: `SPREAD_LAB_DIR` 추가, 11개 경로 상수 업데이트

**스크립트 이동 + 내부 경로 수정:**
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py`: 이동 + docstring/에러메시지 내 경로 업데이트 (약 10곳)
- `scripts/tqqq/spread_lab/generate_rate_spread_lab.py`: 이동 + docstring 내 경로 업데이트
- `scripts/tqqq/spread_lab/tune_softplus_params.py`: 이동 + docstring 업데이트
- `scripts/tqqq/spread_lab/validate_walkforward.py`: 이동 + docstring 업데이트
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py`: 이동 + docstring/에러메시지 업데이트
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py`: 이동 + docstring/에러메시지 업데이트

**문서 업데이트:**
- `README.md`: 디렉토리 구조, 실행 명령어, 파일 경로 업데이트
- `CLAUDE.md` (루트): 디렉토리 구조, 결과 파일 경로 업데이트
- `scripts/CLAUDE.md`: 스크립트 목록/경로 업데이트
- `src/qbt/tqqq/CLAUDE.md`: CLI 스크립트 섹션, 경로 업데이트

### 데이터/결과 영향

- 결과 CSV 파일 위치만 변경, 내용은 동일
- `meta.json`은 이동하지 않음 (메인에 유지)
- `meta_manager.py`의 `VALID_CSV_TYPES`는 변경 불필요 (타입 이름은 경로와 무관)

## 6) 단계별 계획(Phases)

### Phase 1 — 경로 상수 변경 + 파일 이동

**작업 내용**:

- [x] `src/qbt/tqqq/constants.py`에 `SPREAD_LAB_DIR` 상수 추가
  ```python
  SPREAD_LAB_DIR: Final = RESULTS_DIR / "spread_lab"
  ```
- [x] 11개 검증용 경로 상수를 `RESULTS_DIR` → `SPREAD_LAB_DIR` 기반으로 변경
- [x] `scripts/tqqq/spread_lab/` 디렉토리 생성 + 스크립트 6개 이동 (`git mv`)
- [x] `storage/results/spread_lab/` 디렉토리 생성 + 결과 CSV 12개 이동 (`mv`)

---

### Phase 2 — 스크립트 내부 경로 참조 업데이트

**작업 내용**:

- [x] `app_rate_spread_lab.py`: docstring 실행 명령어 + 본문 내 `scripts/tqqq/` → `scripts/tqqq/spread_lab/` (약 10곳)
- [x] `generate_rate_spread_lab.py`: docstring 경로 업데이트
- [x] `tune_softplus_params.py`: docstring 경로 업데이트
- [x] `validate_walkforward.py`: docstring 경로 업데이트
- [x] `validate_walkforward_fixed_b.py`: docstring + 에러메시지 경로 업데이트
- [x] `validate_walkforward_fixed_ab.py`: docstring + 에러메시지 경로 업데이트

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` 업데이트 (디렉토리 구조, 실행 명령어, 결과 파일 경로)
- [x] `CLAUDE.md` (루트) 업데이트 (디렉토리 구조, 결과 파일 경로)
- [x] `scripts/CLAUDE.md` 업데이트 (스크립트 목록/경로)
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트 (CLI 스크립트 섹션)
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=267, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트정리 / SoftPlus 스프레드 검증용 스크립트와 결과를 spread_lab 하위폴더로 분리
2. 프로젝트정리 / 검증 완료된 스프레드 모델 관련 파일을 하위폴더로 이동하여 핵심 파일 가시성 개선
3. TQQQ시뮬레이션 / 스프레드 검증 스크립트·결과 CSV를 spread_lab 폴더로 재배치
4. 프로젝트정리 / scripts/tqqq 및 storage/results에서 스프레드 검증 파일 하위폴더 분리
5. 프로젝트정리 / 확정된 SoftPlus 모델 검증 산출물을 spread_lab으로 아카이빙

## 7) 리스크(Risks)

- **낮음**: `git mv`로 스크립트 이동하므로 git 이력 보존
- **낮음**: 결과 CSV는 git 추적 대상이 아닐 수 있음 → `.gitignore` 확인 필요
- **낮음**: `storage/results/spread_lab/` 디렉토리가 없으면 스크립트 실행 시 에러 → `constants.py`에서 디렉토리 자동 생성하거나, 스크립트에서 `mkdir -p` 처리

## 8) 메모(Notes)

- `meta_manager.py`의 `VALID_CSV_TYPES` 목록은 경로가 아닌 논리적 타입명이므로 변경 불필요
- `__pycache__` 폴더는 이동하지 않음 (자동 재생성)

### 진행 로그 (KST)

- 2026-02-15 22:30: 계획서 초안 작성
- 2026-02-15 23:00: 모든 Phase 완료, 검증 통과 (passed=267, failed=0, skipped=0)
