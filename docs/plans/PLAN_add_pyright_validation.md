# Implementation Plan: PyRight 타입 체커 통합 검증 추가

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

**작성일**: 2026-01-02 16:25
**마지막 업데이트**: 2026-01-02 19:21
**관련 범위**: 개발도구 (validate_project.py), 테스트
**관련 문서**: tests/CLAUDE.md

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

- [x] PyRight 타입 체커를 validate_project.py에 통합하여 명령어로 실행 가능하게 함
- [x] Mypy와 PyRight를 병행 사용하여 더 엄격한 타입 검증 수행
- [x] 전체 검증 시 Ruff + Mypy + PyRight + Pytest를 모두 실행
- [x] 기존 PyRight 타입 오류(test_tqqq_visualization.py:111)를 수정하여 검증 통과

## 2) 비목표(Non-Goals)

- Mypy 제거 또는 대체 (병행 사용)
- PyRight 설정 조정으로 오류 우회 (코드 수정으로 해결)
- 다른 타입 체커(Pyre, Pytype 등) 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- IDE(VSCode)의 Pylance는 PyRight 기반으로 동작하여 타입 오류를 표시하지만, validate_project.py는 Mypy만 실행하므로 오류를 감지하지 못함
- Mypy와 PyRight는 서로 다른 타입 체커이므로 검증 결과가 다를 수 있음
- 현재 test_tqqq_visualization.py:111에서 PyRight 오류 발생:
  - `Cannot access attribute "name" for class "BaseTraceType"`
  - `isinstance` 타입 좁히기 후에도 PyRight가 `.name` 속성을 인식하지 못함
- 개발자는 IDE에서 오류를 보지만, CI/CD 파이프라인에서는 통과할 수 있어 혼란 발생

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `tests/CLAUDE.md` (테스트)
- `docs/CLAUDE.md` (계획서 운영)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] validate_project.py에 `run_pyright()` 함수 추가
- [x] `--only-pyright` 명령행 옵션 추가
- [x] 전체 검증 시 Ruff + Mypy + PyRight + Pytest 실행
- [x] test_tqqq_visualization.py의 PyRight 타입 오류 수정
- [x] `poetry run python validate_project.py` 통과 (passed=182, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 루트 CLAUDE.md의 품질 검증 섹션 업데이트 (PyRight 추가)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `validate_project.py`: PyRight 실행 함수 추가, 명령행 옵션 추가, 통합 실행
- `tests/test_tqqq_visualization.py`: PyRight 타입 오류 수정
- `CLAUDE.md` (루트): 품질 검증 섹션에 PyRight 추가

### 데이터/결과 영향

- 없음 (개발 도구 개선)

## 6) 단계별 계획(Phases)

### Phase 1 — PyRight 실행 함수 구현 및 통합

**작업 내용**:

- [x] `run_pyright()` 함수 구현 (run_ruff, run_mypy와 유사한 구조)
  - `poetry run pyright` 실행
  - stdout/stderr 출력 표시
  - 오류 개수 파싱 (exit code 기반)
  - 성공/실패 메시지 출력
- [x] `parse_args()` 함수에 `--only-pyright` 옵션 추가
- [x] `main()` 함수에 PyRight 실행 로직 통합
  - 전체 실행 시 Ruff → Mypy → PyRight → Pytest 순서로 실행
  - `--only-pyright` 옵션 처리
- [x] 최종 결과 요약에 PyRight 결과 포함

**Validation**:

- [x] `poetry run python validate_project.py --only-pyright` (passed=0, failed=1, skipped=0)
- [x] `poetry run python validate_project.py` (전체 실행, passed=182, failed=0, skipped=0 - PyRight 오류 1개 발견)

---

### Phase 2 — 테스트 코드 수정하여 PyRight 오류 해결

**작업 내용**:

- [x] test_tqqq_visualization.py:111 오류 분석
  - `isinstance(fig.data[1], go.Scatter)` 후에도 `.name` 접근이 안전하지 않다고 판단되는 이유 파악
  - PyRight는 타입 좁히기를 인식하지 못하지만 Mypy는 인식함 (타입 체커 차이)
- [x] 타입 안전한 방식으로 코드 수정
  - `from typing import cast` 추가
  - `isinstance` 체크 후 `cast()` 사용하여 명시적 타입 캐스팅
  - Mypy의 redundant-cast 경고 억제를 위해 `# type: ignore` 주석 추가
- [x] 동일한 패턴이 사용된 다른 테스트 케이스도 수정 (60-63, 114-115, 168-169번째 줄)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

---

### Phase 3 — 문서 업데이트 및 최종 검증

**작업 내용**

- [x] 루트 CLAUDE.md의 "품질 검증" 섹션 업데이트
  - PyRight 옵션 추가: `poetry run python validate_project.py --only-pyright`
  - 전체 검증에 PyRight 포함됨을 명시 (Ruff + Mypy + PyRight + Pytest)
  - 금지 명령어에 `poetry run pyright` 추가
- [x] `poetry run black .` 실행(자동 포맷 적용) - 모든 파일 이미 포맷됨
- [x] 변경 기능 및 전체 플로우 최종 검증
  - 각 옵션별 실행 테스트 (--only-lint, --only-mypy, --only-pyright, --only-tests, 전체)
  - 모든 검증 도구 통과 확인
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=182, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 개발도구 / PyRight 타입 체커 통합 검증 추가 및 기존 타입 오류 수정
2. 개발도구 / Mypy+PyRight 병행 검증으로 타입 안정성 강화
3. 개발도구 / IDE(Pylance) 일치성 확보 - PyRight 통합 및 타입 오류 해결
4. 개발도구 / 통합 검증 도구 확장 - PyRight 추가 및 테스트 타입 안전성 개선
5. 개발도구 / validate_project.py에 PyRight 체크 추가 및 관련 타입 이슈 수정

## 7) 리스크(Risks)

- **Mypy와 PyRight의 결과 차이로 인한 혼란**: 완화책 - 두 도구 모두 통과하도록 코드 작성
- **기존 코드에서 PyRight 오류 추가 발견 가능성**: 완화책 - Phase 2에서 전체 스캔 후 오류 수정
- **타입 캐스팅 남용으로 타입 안전성 저하**: 완화책 - 가능한 한 타입 좁히기로 해결, 불가피한 경우에만 캐스팅 사용
- **CI/CD 파이프라인 실행 시간 증가**: 완화책 - PyRight는 빠르게 실행되므로 영향 최소

## 8) 메모(Notes)

### 관련 정보

- PyRight는 VSCode의 Pylance 타입 체커의 기반 엔진
- Mypy와 PyRight는 서로 다른 타입 추론 알고리즘을 사용하므로 결과가 다를 수 있음
- pyproject.toml에 이미 PyRight 설치됨 (poetry add --group dev pyright)

### 진행 로그 (KST)

- 2026-01-02 16:25: 계획서 작성 시작
- 2026-01-02 16:25: 사용자 확인 완료 (Mypy+PyRight 병행, 테스트 코드 수정)
- 2026-01-02 16:30~18:00: Phase 1 완료 - PyRight 통합 및 초기 검증 (1개 타입 오류 발견)
- 2026-01-02 18:00~19:00: Phase 2 완료 - 테스트 코드 타입 오류 수정 (typing.cast 사용)
- 2026-01-02 19:00~19:21: Phase 3 완료 - 문서 업데이트 및 최종 검증 통과
- 2026-01-02 19:21: 모든 작업 완료 - 전체 품질 검증 통과 (Ruff + Mypy + PyRight + Pytest)

---
