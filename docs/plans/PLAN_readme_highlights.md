# Implementation Plan: README 엔지니어링 하이라이트 섹션 추가

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

**작성일**: 2026-04-19 00:45
**마지막 업데이트**: 2026-04-19 00:52
**관련 범위**: 루트 문서 (README.md)
**관련 문서**: [CLAUDE.md](../../CLAUDE.md), [docs/plans/PLAN_readme_refactor.md](PLAN_readme_refactor.md)

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

- [x] 포트폴리오 독자가 README 만 읽고도 "이 프로젝트가 단순 백테스터가 아니라는 점" 을 파악할 수 있도록 **엔지니어링 하이라이트 섹션** 추가
- [x] 프로젝트 소개 첫 문장에 "매일 실제로 돌아가는" 포인트 1회 자연스럽게 삽입
- [x] [CLAUDE.md](../../CLAUDE.md) "문서 내구성 원칙" 준수 — 구체 수치(테스트 개수 등) 대신 정성적 역할 중심 표현 사용

## 2) 비목표(Non-Goals)

- 실행 명령어 / 코드 변경 없음
- README 구조 재편 없음 (기존 섹션 유지, 새 섹션만 삽입)
- 구체 수치(테스트 개수, 자산 개수 등) 기재 금지 — 내구성 원칙

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 이전 plan([PLAN_readme_refactor](PLAN_readme_refactor.md))으로 README 는 가벼워졌지만, "이 사람 깊이 있게 만들었구나" 가 첫눈에 드러나지 않음.
- 실제 운영 중(GitHub Actions) · 과최적화 방어 장치(WFO/고원) · 정합성 자동 검증(5개 불변조건) · PyRight strict / `validate_project.py` 통합 검증 등은 모두 실코드 기반 포인트라 어필 근거가 확실함.
- 사용자와 대화로 강조 조합 🅐(실운영) + 🅑(과최적화 방어 + 정합성 검증) + 🅓(엔지니어링 품질) 확정.

### 영향받는 규칙(반드시 읽고 전체 숙지)

- [루트 CLAUDE.md](../../CLAUDE.md): "문서 내구성 원칙", "실행 명령어 관리 원칙" (추가 명령어 기재 금지)
- [docs/CLAUDE.md](../CLAUDE.md): plans 운영 규칙

## 4) 완료 조건(Definition of Done)

- [x] README.md 에 "엔지니어링 하이라이트" 섹션 추가 ("주요 기능" 섹션 바로 앞에 배치)
- [x] 프로젝트 소개 문장에 "매일 실제로 돌아가는" 뉘앙스 1회 삽입
- [x] 구체 수치 / 가변 목록 미사용 (문서 내구성 원칙)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `README.md` — "엔지니어링 하이라이트" 섹션 추가 + 소개 문장 보강 (변경 있음)
- `docs/COMMANDS.md`: 변경 없음

### 데이터/결과 영향

- 소스 / 테스트 / 데이터 영향 없음
- 문서 전용 변경

## 6) 단계별 계획(Phases)

### Phase 1 — README 소개 문장 보강 + 엔지니어링 하이라이트 섹션 추가

**작업 내용**:

- [x] 프로젝트 소개 첫 문장에 "매일 실제로 돌아가는" 표현 삽입
- [x] "주요 기능" 섹션 바로 앞에 `## 엔지니어링 하이라이트` 섹션 추가 — 4개 항목 (라이브 시스템 / 과최적화 방어 / 정합성 자동 검증 / 엔지니어링 품질)
- [x] 각 항목은 역할 중심 정성적 표현, 구체 수치 미사용

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .`
- [x] DoD / Phase 체크박스 최신화

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1019, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서 / README 엔지니어링 하이라이트 섹션 추가 (포트폴리오 공개 대비)
2. 문서 / README 에 라이브 시스템 · 과최적화 방어 · 정합성 검증 강조 블록 추가
3. 문서 / README 프로젝트 강조점 섹션 신설 (실운영 / 정합성 / 엔지니어링 품질)
4. 문서 / README 소개 문장 보강 + 하이라이트 섹션 추가
5. 문서 / 포트폴리오 어필 포인트 README 반영

## 7) 리스크(Risks)

- 문구에 구체 수치가 섞여 들어가 내구성 원칙 위반 → 작성 중 체크, 정성적 표현만 사용
- 하이라이트 과장 → 실코드로 검증 가능한 포인트만 기재

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-19 00:45: plan 작성
- 2026-04-19 00:50: Phase 1 구현 완료 (README 소개 문장 보강 + 엔지니어링 하이라이트 4개 항목 추가)
- 2026-04-19 00:52: `poetry run black .` (146 files unchanged) + `validate_project.py` 통과 (passed=1019, failed=0, skipped=0) → 상태 ✅ Done

---
