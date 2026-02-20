# Implementation Plan: 상수 통합 및 코드 일관성

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-20 20:00
**마지막 업데이트**: 2026-02-20 20:00
**관련 범위**: src/qbt/tqqq, src/qbt/common_constants, scripts/tqqq
**관련 문서**: `CLAUDE.md`(루트), `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [ ] 목표 1: 중복 정의된 상수 통합 (보고서 D-2, D-8)
- [ ] 목표 2: 코드 일관성 확보 — 로거, CSV 인코딩, Path 사용, 컬럼 검증 패턴 (보고서 F-2, F-3, F-5, F-6)

## 2) 비목표(Non-Goals)

- `COL_` 접두사 한글/영문 혼재(F-1) 수정: tqqq_daily_comparison.csv의 한글 컬럼명은 이미 외부 소비자(대시보드 앱)가 사용하므로 이번 범위 외. 변경 시 하위 호환성 검토 필요
- `__all__` 전면 통일(F-4): 선택적 사용은 프로젝트 전반에 영향이 크므로 이번 범위 외
- 비즈니스 로직 변경: 상수 참조 경로만 변경하며 계산 로직은 불변

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- D-2: `COL_A = "a"`, `COL_B = "b"`, `COL_RMSE_PCT = "rmse_pct"` 상수가 4개 스크립트에서 각각 독립 정의. 값 불일치 시 조용한 실패 위험
- D-8: `TQQQ_SYNTHETIC_DATA_PATH`(common_constants)와 `TQQQ_SYNTHETIC_PATH`(tqqq/constants)가 동일 경로를 가리킴. 상수 중복 금지 원칙 위반
- F-2: `simulation.py`만 `utf-8-sig`, 나머지는 `utf-8` — 동일 도메인 내 인코딩 불일치
- F-3: `app_rate_spread_lab.py`만 `setup_logger()`, 나머지 12개 스크립트는 `get_logger()` 사용
- F-5: 누락 컬럼 검증에 `set` 차집합과 리스트 컴프리헨션이 혼재
- F-6: `os.path.getmtime` 사용 — Path 객체 규칙 위반

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md`(루트): 상수 관리 3계층, 상수 명명 규칙, Path 객체 사용 규칙
- `src/qbt/tqqq/CLAUDE.md`: TQQQ 도메인 상수 목록
- `scripts/CLAUDE.md`: CLI 스크립트 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] D-2: `COL_A`, `COL_B`, `COL_RMSE_PCT`가 `tqqq/constants.py`에 1곳만 정의
- [ ] D-8: `TQQQ_SYNTHETIC_PATH` 중복 제거, 1곳만 유지
- [ ] F-2: 동일 도메인 내 CSV 인코딩 통일
- [ ] F-3: 로거 초기화 `get_logger()`로 통일
- [ ] F-5: 누락 컬럼 검증 패턴 통일
- [ ] F-6: `os.path.getmtime` → `Path.stat().st_mtime` 대체
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**상수 통합 (D-2)**:
- `src/qbt/tqqq/constants.py` — `COL_A`, `COL_B`, `COL_RMSE_PCT` 상수 추가
- `scripts/tqqq/spread_lab/tune_softplus_params.py` — 로컬 상수 → import로 변경
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py` — 동일
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` — 동일
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — 동일

**경로 상수 통합 (D-8)**:
- `src/qbt/tqqq/constants.py` — `TQQQ_SYNTHETIC_PATH` 제거, `common_constants.TQQQ_SYNTHETIC_DATA_PATH` 사용으로 통일
- `TQQQ_SYNTHETIC_PATH` 사용처 모두 `TQQQ_SYNTHETIC_DATA_PATH`로 변경

**일관성 수정**:
- `src/qbt/tqqq/simulation.py` — CSV 인코딩 `utf-8-sig` → `utf-8` (F-2)
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — `setup_logger` → `get_logger` (F-3)
- `scripts/tqqq/app_daily_comparison.py` — `os.path.getmtime` → `path.stat().st_mtime` (F-6)
- 누락 컬럼 검증 패턴 통일 대상 파일 (F-5):
  - `src/qbt/tqqq/data_loader.py`
  - `src/qbt/tqqq/analysis_helpers.py`

### 데이터/결과 영향

- D-2, D-8: import 경로만 변경, 상수 값은 동일하므로 출력 변경 없음
- F-2: `utf-8-sig` → `utf-8` 변경으로 BOM 문자가 CSV에서 제거됨. 기존 CSV를 재생성해야 동일해지지만, 데이터 내용 자체는 동일
- F-3, F-5, F-6: 동작 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 통합 (그린 유지)

**작업 내용**:

- [ ] D-2: `src/qbt/tqqq/constants.py`에 `COL_A`, `COL_B`, `COL_RMSE_PCT` 상수 추가
- [ ] D-2: 4개 스크립트에서 로컬 정의 제거, `from qbt.tqqq.constants import COL_A, COL_B, COL_RMSE_PCT`로 변경
- [ ] D-8: `TQQQ_SYNTHETIC_PATH` 사용처를 `TQQQ_SYNTHETIC_DATA_PATH`로 통일
  - `tqqq/constants.py`에서 `TQQQ_SYNTHETIC_PATH` 제거
  - 기존 import 경로 업데이트

---

### Phase 2 — 코드 일관성 수정 (그린 유지)

**작업 내용**:

- [ ] F-2: `simulation.py`의 `_save_daily_comparison_csv` 인코딩을 `utf-8`로 변경
- [ ] F-3: `app_rate_spread_lab.py`의 `from qbt.utils.logger import setup_logger` → `from qbt.utils import get_logger`
- [ ] F-5: 누락 컬럼 검증 패턴을 `set` 차집합 방식(`sorted(set(required) - set(df.columns))`)으로 통일
- [ ] F-6: `app_daily_comparison.py`에서 `import os` 제거, `os.path.getmtime(path)` → `path.stat().st_mtime`

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `tqqq/CLAUDE.md`에 새로 추가된 상수(`COL_A`, `COL_B`, `COL_RMSE_PCT`) 반영
- [ ] `poetry run black .` 실행
- [ ] DoD 체크리스트 최종 업데이트

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트 / 상수 중복 제거 + CSV 인코딩/로거/Path 일관성 통일
2. TQQQ시뮬레이션 / 상수 통합 및 코드 일관성 개선 (동작 동일)
3. 프로젝트 / D-2, D-8, F-2~F-6 상수/일관성 정비
4. 프로젝트 / COL_A/B 상수 통합 + TQQQ_SYNTHETIC 경로 중복 제거
5. 프로젝트 / 상수 관리 원칙 준수를 위한 통합 및 일관성 보정

## 7) 리스크(Risks)

- D-8: `TQQQ_SYNTHETIC_PATH` 참조 누락 시 ImportError 발생 — Grep으로 전수 검색하여 방지
- F-2: BOM 제거로 인해 Excel에서 한글이 깨질 수 있으나, 분석 도구(pandas, Python)에서는 무관. 다른 CSV도 `utf-8`이므로 통일이 합리적
- F-5: 검증 패턴 변경은 에러 메시지의 컬럼 순서가 달라질 수 있음 (sorted로 통일)

## 8) 메모(Notes)

- 이 계획서는 `PROJECT_ANALYSIS_REPORT.md`의 D-2, D-8, F-2, F-3, F-5, F-6 항목을 대상으로 함
- F-1(COL_ 한글 혼재)과 F-4(__all__ 통일)은 영향 범위가 넓어 별도 검토 필요

### 진행 로그 (KST)

- 2026-02-20 20:00: 계획서 초안 작성

---
