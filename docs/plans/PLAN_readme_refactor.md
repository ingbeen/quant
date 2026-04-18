# Implementation Plan: README 포트폴리오화 + 명령어 docs/COMMANDS.md 이전

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

**작성일**: 2026-04-19 00:15
**마지막 업데이트**: 2026-04-19 00:40
**관련 범위**: docs, 프로젝트 루트 문서
**관련 문서**: [CLAUDE.md](../../CLAUDE.md), [docs/CLAUDE.md](../CLAUDE.md), [docs/plans/_template.md](_template.md)

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

- [x] README.md 를 포트폴리오 관점의 프로젝트 소개 문서로 축소(소개 + 주요 기능 + 기술 스택 + 관련 문서 링크)
- [x] 현재 README.md 에 있는 모든 실행 명령어를 신규 `docs/COMMANDS.md` 로 이전 (SoT 단일화)
- [x] 루트 CLAUDE.md / docs/CLAUDE.md / docs/plans/\_template.md 를 새 SoT(`docs/COMMANDS.md`)에 맞춰 업데이트
- [x] README.md 의 "라이선스" 문구 제거 (포트폴리오용, 격식 최소화)

## 2) 비목표(Non-Goals)

- 실행 명령어 자체의 내용 변경 / 리팩토링 (이전만 수행, 문구는 가급적 보존)
- CLAUDE.md 체계(도메인별 CLAUDE.md) 자체의 변경
- 소스 코드 / 테스트 / 데이터 스키마 변경
- `README.md` 외 루트 다른 문서(예: `scripts/CLAUDE.md`, 도메인 CLAUDE.md)의 명령어/링크 변경 — 이번 변경과 직접 관련된 루트 문서 3종만 대상으로 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 [README.md](../../README.md) 는 약 399줄로, 사실상 개발자 매뉴얼에 가깝다.
- 사용자는 이 리포를 **포트폴리오로 외부에 노출**할 계획이며, 라이선스 명시/과도한 격식 없이 프로젝트가 "무엇을 하는지"만 보여주고 싶어한다.
- 동시에 AI(Claude Code) 와 사용자 본인에게는 명령어 레퍼런스가 계속 필요하다 → README 에서 빼되 잃어버려서는 안 된다.
- 루트 [CLAUDE.md](../../CLAUDE.md) 는 "모든 실행 명령어는 README.md 에서 단일 관리" 라고 명시 — 이전하려면 이 규칙도 함께 수정해야 한다.
- [docs/CLAUDE.md](../CLAUDE.md) 와 [docs/plans/\_template.md](_template.md) 에는 Scope/DoD 에서 "README.md 업데이트 필요 여부 명시" 규칙이 있음 → 새 SoT 파일도 같은 수준으로 명시 필요.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md): "실행 명령어 관리 원칙", "문서 내구성 원칙", "도메인별 CLAUDE.md 참고 규칙"
- [docs/CLAUDE.md](../CLAUDE.md): plans 운영 규칙 / Scope 기재 규칙 / Phase 구성 원칙
- [docs/plans/\_template.md](_template.md): 템플릿 자체를 변경하므로 템플릿 스키마 준수

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] README.md 축소 완료 (프로젝트 소개 / 주요 기능 / 기술 스택 / 관련 문서 링크 블록만 유지, 라이선스 문구 제거)
- [x] `docs/COMMANDS.md` 신규 생성 완료 (기존 README 의 명령어 섹션 전부 이전, 워크플로우별 구조 유지)
- [x] 루트 [CLAUDE.md](../../CLAUDE.md) "실행 명령어 관리 원칙" 섹션이 `docs/COMMANDS.md` 를 단일 SoT 로 가리키도록 수정
- [x] [docs/CLAUDE.md](../CLAUDE.md) 계획서 필수 구성(Scope) 규칙이 `docs/COMMANDS.md` 업데이트 필요 여부를 함께 명시하도록 수정
- [x] [docs/plans/\_template.md](_template.md) 의 Scope / DoD / 마지막 Phase 체크리스트가 `docs/COMMANDS.md` 업데이트 필요 여부를 함께 명시하도록 수정
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)
- [x] (사용자 승인 추가 범위) `src/live/CLAUDE.md`, `tests/CLAUDE.md` 의 README.md 링크 3곳을 `docs/COMMANDS.md` 타겟으로 교체 — 섹션 이전에 따른 깨진 링크 회복

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `README.md` — 대폭 축소 (변경 있음)
- `docs/COMMANDS.md` — 신규 생성 (변경 있음)
- `CLAUDE.md` (루트) — "실행 명령어 관리 원칙" 섹션 수정 (변경 있음)
- `docs/CLAUDE.md` — 계획서 Scope 규칙 부분 수정 (변경 있음)
- `docs/plans/_template.md` — Scope / DoD / 마지막 Phase 체크리스트 문구 수정 (변경 있음)
- `README.md`: 변경 있음 (대폭 축소 + 라이선스 문구 제거)
- `docs/COMMANDS.md`: 변경 있음 (신규 생성)

### 데이터/결과 영향

- 소스 코드 / 테스트 / 데이터 스키마 변경 없음
- 기존 결과물(CSV/JSON) 영향 없음
- 실행 명령어 자체는 문구 보존 → 사용자 실행 흐름 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — `docs/COMMANDS.md` 신규 생성 (기존 README 명령어 전부 이전)

**작업 내용**:

- [x] 현재 README.md 의 아래 섹션을 `docs/COMMANDS.md` 로 이전
  - 빠른 시작 (설치 + 품질 검증)
  - 워크플로우 1: 백테스트 전략 분석
  - 워크플로우 2: TQQQ 레버리지 ETF 시뮬레이션
  - 워크플로우 3: QBT Live (실매매 알림)
  - 주요 명령어 (품질 검증 / 테스트 / 코드 포맷 / 커버리지)
  - 데이터 다운로드 옵션
- [x] 문서 상단에 SoT 선언 1줄 추가 ("이 파일이 실행 명령어의 단일 SoT")
- [x] 파일 내 상대 링크는 `docs/COMMANDS.md` 기준으로 갱신 (예: `src/qbt/...` → `../src/qbt/...`)

---

### Phase 2 — README.md 축소 + 라이선스 제거

**작업 내용**:

- [x] 유지할 섹션만 남긴다
  - 프로젝트 타이틀 + 한줄 소개
  - 주요 기능 (qbt / live)
  - 기술 스택
  - 관련 문서 (명령어 → `docs/COMMANDS.md` / 상세 규칙 → 각 CLAUDE.md)
- [x] 제거 대상
  - 빠른 시작 / 워크플로우 1~3 / 주요 명령어 / 데이터 다운로드 옵션 (전부 `docs/COMMANDS.md` 로 이전됨)
  - "프로젝트 구조" 섹션 (루트 CLAUDE.md 에 이미 있음)
  - "주요 결과 파일" 섹션 (도메인 CLAUDE.md + 코드에서 파생 가능)
  - "개발 가이드" 섹션 (루트 CLAUDE.md 와 중복)
  - **"라이선스" 문구 (명시 요청)**
- [x] 포트폴리오 독자 관점에서 한눈에 "무슨 프로젝트인지" 파악 가능한 톤으로 정리

---

### Phase 3 — 규칙 문서 3종 (루트 CLAUDE.md / docs/CLAUDE.md / \_template.md) 동기화

**작업 내용**:

- [x] [루트 CLAUDE.md](../../CLAUDE.md) "실행 명령어 관리 원칙" 섹션
  - 기존: "모든 실행 명령어는 README.md 에서 단일 관리"
  - 변경: "모든 실행 명령어는 `docs/COMMANDS.md` 에서 단일 관리" + README.md 에는 명령어를 기재하지 않는다는 점 명시
- [x] [docs/CLAUDE.md](../CLAUDE.md) 계획서 필수 구성(Scope) 규칙
  - 기존: "`README.md` 업데이트 필요 여부를 반드시 명시한다"
  - 변경: "`README.md` 및 `docs/COMMANDS.md` 업데이트 필요 여부를 반드시 명시한다 (불필요 시 각각 '변경 없음' 기록)"
- [x] [docs/plans/\_template.md](_template.md)
  - Scope "변경 대상 파일(예상)" 블록에 `docs/COMMANDS.md` 항목 추가
  - 마지막 Phase 체크리스트 "필요한 문서 업데이트 (README.md 및 `docs/COMMANDS.md` 포함 여부 명시)" 로 수정
  - DoD 의 "필요한 문서 업데이트" 항목 동일하게 반영

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 변경된 문서들의 상호 링크 일관성 확인 (README ↔ docs/COMMANDS.md ↔ CLAUDE.md 양방향)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 전체 변경 파일 최종 리뷰 (README 톤, COMMANDS 링크 유효성, 규칙 문서 문구 일관성)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1019, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서 / README 포트폴리오화 + 명령어 `docs/COMMANDS.md` 단일 SoT 이전
2. 문서 / 실행 명령어 SoT 를 README.md → `docs/COMMANDS.md` 로 이전 (규칙 3종 동기화)
3. 문서 / README 축소(라이선스 제거) + 명령어 레퍼런스 분리
4. 문서 / 포트폴리오 공개 대비 README 슬림화 + 명령어 문서 신설
5. 문서 / 실행 명령어 관리 규칙 변경 — `docs/COMMANDS.md` 신규 + README/규칙문서 반영

## 7) 리스크(Risks)

- README 에 기재되어 있던 명령어를 참조하던 외부 링크(깃허브 README 스냅샷 등) 가 끊길 수 있음 → 새 SoT(`docs/COMMANDS.md`) 위치를 README 관련 문서 링크에서 명확히 가리키면 완화됨
- 루트 CLAUDE.md 의 "실행 명령어 관리 원칙" 이 다른 도메인 CLAUDE.md / 주석 등에서도 "README 에서 단일 관리"를 암묵적으로 가정하고 있을 수 있음 → 이번 Scope 는 루트 문서 3종만이므로, 후속으로 grep 해보고 걸리는 게 있으면 별도 plan 으로 분리
- 문서 전용 변경이므로 validate_project.py 에서 실패가 날 가능성은 낮지만, Ruff/Pyright/Pytest 가 문서 변경과 무관하게 깨져 있다면 이번 plan 범위를 넘어 수정하지 않고 별도 보고

## 8) 메모(Notes)

- SoT 단일화 방침: 워크플로우별 분할(`docs/commands/*.md`) 은 YAGNI 로 보류. 단일 파일로 충분.
- 라이선스 관련: 사용자는 격식 차린 문구를 원치 않음. README 최하단 "라이선스: 개인 학습 및 연구 목적" 문구 완전 제거.
- 명령어 문구 자체는 이전만 하고 보존. 새 명령어 추가/삭제/리팩토링은 이번 plan 의 비목표.

### 진행 로그 (KST)

- 2026-04-19 00:15: plan 최초 작성 (Draft)
- 2026-04-19 00:25: Phase 1~3 구현 완료 (docs/COMMANDS.md 신규, README.md 축소, CLAUDE.md 3종 동기화)
- 2026-04-19 00:30: Phase 3 종료 후 정합성 검사 중 깨진 링크 3곳 발견 → 사용자 승인(A안)으로 범위 확장: `src/live/CLAUDE.md`, `tests/CLAUDE.md` (2곳) 의 `README.md` 링크를 `docs/COMMANDS.md` 타겟으로 교체
- 2026-04-19 00:40: `poetry run black .` (146 files unchanged) + `poetry run python validate_project.py` 통과 (passed=1019, failed=0, skipped=0) → 상태 ✅ Done

---
