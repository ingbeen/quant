# Implementation Plan: scripts/tqqq 스크립트 네이밍 통일

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-10 21:00
**마지막 업데이트**: 2026-02-10 21:00
**관련 범위**: scripts/tqqq, docs, tests
**관련 문서**: `CLAUDE.md`(루트), `scripts/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] `scripts/tqqq` 내 스크립트 파일명을 일관된 네이밍 규칙으로 리네임
- [ ] 저장소 전체에서 구 파일명 참조를 신 파일명으로 업데이트 (0건 달성)
- [ ] 새 파일명 기준으로 실행/도움말 출력이 정상 동작하는지 검증

## 2) 비목표(Non-Goals)

- 스크립트의 기능 변경, 알고리즘 변경, 로직 리팩터링은 하지 않는다
- `scripts/tqqq` 밖의 파일명 규칙을 새로 강제하지 않는다
- Python 함수명 `run_walkforward_validation()` 등은 변경하지 않는다 (파일명만 변경)
- 폴더 구조 변경 없음 (리네임만 수행)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `scripts/tqqq` 폴더 내 파일명에 도메인 접두사(`tqqq_`)가 혼용되어 규칙이 불명확
- 동사 접두사(`run_`, `validate_`, `generate_`)가 실제 목적과 불일치하는 경우 존재
- Streamlit 앱의 기술명(`streamlit_`) 접두사가 향후 기술 변경 시 혼동 유발

### 파일명 매핑표

| 현재 파일명 | 새 파일명 | 변경 이유 |
|---|---|---|
| `generate_synthetic_tqqq.py` | `generate_synthetic.py` | 도메인 접두사 제거 |
| `generate_tqqq_daily_comparison.py` | `generate_daily_comparison.py` | 도메인 접두사 제거 |
| `generate_rate_spread_lab.py` | (유지) | 이미 규칙 부합 |
| `run_softplus_tuning.py` | `tune_softplus_params.py` | `tune_` 접두사로 표준화 |
| `run_walkforward_validation.py` | `validate_walkforward.py` | `validate_` 접두사로 표준화 |
| `validate_tqqq_simulation.py` | `tune_cost_model.py` | 실제 목적(비용모델 탐색)에 맞게 `tune_` 반영 |
| `streamlit_daily_comparison.py` | `app_daily_comparison.py` | UI 엔트리포인트 `app_` 표준화 |
| `streamlit_rate_spread_lab.py` | `app_rate_spread_lab.py` | 동일 규칙 적용 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 프로젝트 전반 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 계층 규칙
- `src/qbt/tqqq/CLAUDE.md`: TQQQ 도메인 규칙
- `tests/CLAUDE.md`: 테스트 규칙

### 중요: 함수명과 파일명 구분

`run_walkforward_validation`은 `src/qbt/tqqq/simulation.py`의 **함수명**이자 스크립트 **파일명**이다.
이 작업에서는 **파일명 참조만 변경**하며, 함수명은 변경하지 않는다.

영향 없는 참조 (변경 금지):
- `src/qbt/tqqq/simulation.py:1798` -- `def run_walkforward_validation(` (함수 정의)
- `src/qbt/tqqq/types.py:76` -- 함수 docstring 참조
- `scripts/tqqq/validate_walkforward.py` 내 `from qbt.tqqq.simulation import run_walkforward_validation` (함수 import)
- `tests/test_tqqq_simulation.py:2108-2159` -- 함수 테스트 (클래스/docstring/import/호출 모두 함수 참조)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] 파일 리네임 완료 (7개 파일 `git mv`)
- [ ] 저장소 전체에서 구 파일명 검색 결과 0건
- [ ] 새 파일명 기준 스모크 체크 통과 (`--help` 또는 import 확인)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트 (README, CLAUDE.md 등)
- [ ] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

**리네임 대상 (git mv)**:
- `scripts/tqqq/generate_synthetic_tqqq.py` -> `generate_synthetic.py`
- `scripts/tqqq/generate_tqqq_daily_comparison.py` -> `generate_daily_comparison.py`
- `scripts/tqqq/run_softplus_tuning.py` -> `tune_softplus_params.py`
- `scripts/tqqq/run_walkforward_validation.py` -> `validate_walkforward.py`
- `scripts/tqqq/validate_tqqq_simulation.py` -> `tune_cost_model.py`
- `scripts/tqqq/streamlit_daily_comparison.py` -> `app_daily_comparison.py`
- `scripts/tqqq/streamlit_rate_spread_lab.py` -> `app_rate_spread_lab.py`

**참조 업데이트 대상**:
- `README.md` -- 실행 예시 명령어 + 디렉토리 트리 (약 15개 참조)
- `CLAUDE.md` (루트) -- 디렉토리 구조 (2개 참조)
- `scripts/CLAUDE.md` -- 파일 목록 (6개 참조)
- `src/qbt/tqqq/CLAUDE.md` -- 섹션 제목 + 파일 목록 (4개 참조)
- `scripts/tqqq/app_rate_spread_lab.py` (리네임 후) -- 다른 스크립트 경로 참조 f-string (6개 참조)
- 각 스크립트 파일 docstring -- 자기 자신의 실행 명령어 (7개 파일)
- `tests/test_tqqq_simulation.py` -- 스크립트 존재 테스트 + 주석 (약 8개 참조)

### 데이터/결과 영향

- 없음. 파일명 변경만 수행하며 출력 스키마/데이터에 영향 없음.

## 6) 단계별 계획(Phases)

Phase 0은 불필요 (핵심 인바리언트/정책 변경 없음, 테스트 로직 변경 없음)

---

### Phase 1 -- 파일 리네임 + 전체 참조 업데이트 (그린 유지)

**작업 내용**:

**A. git mv 수행 (7개 파일)**:
- [ ] `git mv scripts/tqqq/generate_synthetic_tqqq.py scripts/tqqq/generate_synthetic.py`
- [ ] `git mv scripts/tqqq/generate_tqqq_daily_comparison.py scripts/tqqq/generate_daily_comparison.py`
- [ ] `git mv scripts/tqqq/run_softplus_tuning.py scripts/tqqq/tune_softplus_params.py`
- [ ] `git mv scripts/tqqq/run_walkforward_validation.py scripts/tqqq/validate_walkforward.py`
- [ ] `git mv scripts/tqqq/validate_tqqq_simulation.py scripts/tqqq/tune_cost_model.py`
- [ ] `git mv scripts/tqqq/streamlit_daily_comparison.py scripts/tqqq/app_daily_comparison.py`
- [ ] `git mv scripts/tqqq/streamlit_rate_spread_lab.py scripts/tqqq/app_rate_spread_lab.py`

**B. 스크립트 내부 docstring 자기 참조 업데이트 (7개 파일)**:
- [ ] `generate_synthetic.py` -- docstring 실행 명령어
- [ ] `generate_daily_comparison.py` -- docstring 실행 명령어
- [ ] `tune_softplus_params.py` -- docstring 실행 명령어
- [ ] `validate_walkforward.py` -- docstring 실행 명령어
- [ ] `tune_cost_model.py` -- docstring 실행 명령어
- [ ] `app_daily_comparison.py` -- docstring 실행 명령어
- [ ] `app_rate_spread_lab.py` -- docstring 실행 명령어 + 타 스크립트 참조

**C. app_rate_spread_lab.py 내부 타 스크립트 경로 참조 업데이트**:
- [ ] docstring 내 `run_softplus_tuning.py` -> `tune_softplus_params.py`
- [ ] docstring 내 `run_walkforward_validation.py` -> `validate_walkforward.py`
- [ ] f-string 내 `run_softplus_tuning.py` -> `tune_softplus_params.py` (약 2곳)
- [ ] f-string 내 `run_walkforward_validation.py` -> `validate_walkforward.py` (약 2곳)

**D. 문서 참조 업데이트**:
- [ ] `README.md` -- 실행 예시 명령어 + 디렉토리 트리
- [ ] `CLAUDE.md` (루트) -- 디렉토리 구조
- [ ] `scripts/CLAUDE.md` -- 파일 목록
- [ ] `src/qbt/tqqq/CLAUDE.md` -- 섹션 제목 + 파일 목록

**E. 테스트 파일 참조 업데이트**:
- [ ] `tests/test_tqqq_simulation.py` -- `test_softplus_tuning_script_exists`: 파일 경로 + docstring
- [ ] `tests/test_tqqq_simulation.py` -- `test_walkforward_validation_script_exists`: 파일 경로 + docstring
- [ ] `tests/test_tqqq_simulation.py` -- 주석 내 `scripts/tqqq/run_walkforward_validation.py` 참조

**F. 구 파일명 0건 검증**:
- [ ] `rg` 검색으로 구 파일명 문자열 0건 확인

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 2 (Final) -- 포맷팅, 스모크 체크, 최종 검증

**작업 내용**:

- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 스모크 체크: 각 스크립트 `--help` 또는 인자 없이 실행하여 즉시 크래시 없는지 확인
  - `generate_synthetic.py`
  - `generate_daily_comparison.py`
  - `tune_softplus_params.py`
  - `validate_walkforward.py`
  - `tune_cost_model.py`
  - `generate_rate_spread_lab.py` (유지된 파일도 확인)
  - `app_daily_comparison.py` -- import 확인 (Streamlit 앱은 --help 불가)
  - `app_rate_spread_lab.py` -- import 확인 (Streamlit 앱은 --help 불가)
- [ ] 구 파일명 최종 0건 검증 (rg 결과 기록)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. TQQQ시뮬레이션 / scripts/tqqq 스크립트 파일명 네이밍 통일 (도메인 접두사 제거, 동사 표준화)
2. TQQQ시뮬레이션 / scripts/tqqq 파일 리네임 + 전체 참조 업데이트 (네이밍 규칙 적용)
3. TQQQ시뮬레이션 / scripts/tqqq 네이밍 통일 (tqqq_ 제거, tune_/validate_/app_ 표준화)
4. TQQQ시뮬레이션 / scripts/tqqq 스크립트명 일관성 리팩터링 및 문서 업데이트
5. TQQQ시뮬레이션 / scripts/tqqq 파일명 표준화 (7개 리네임 + 참조 0건 달성)

## 7) 리스크(Risks)

- **함수명/파일명 혼동**: `run_walkforward_validation`이 함수명과 파일명에 모두 사용됨
  - 완화: 파일 경로 참조만 변경, 함수명 참조는 변경하지 않음
  - 검증: validate_project.py로 import/타입 오류 확인
- **Streamlit 앱 import 오류**: 리네임 후 streamlit run 명령어가 실패할 수 있음
  - 완화: import 수준 스모크 체크로 사전 확인

## 8) 메모(Notes)

- `generate_rate_spread_lab.py`는 이미 규칙에 부합하여 리네임 대상에서 제외
- 추가 파일 존재 여부: `scripts/tqqq/` 내 8개 `.py` 파일이 정확히 테이블과 일치 (추가 파일 없음)
- `src/qbt/tqqq/simulation.py`의 `run_walkforward_validation()` 함수, `src/qbt/tqqq/types.py`의 docstring은 함수 참조이므로 변경 불가

### 진행 로그 (KST)

- 2026-02-10 21:00: 계획서 작성
