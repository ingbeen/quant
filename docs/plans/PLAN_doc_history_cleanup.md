# Implementation Plan: 가이드 문서 변경 이력 표현 정리 (Mypy/deprecated)

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

**작성일**: 2026-05-16 12:00
**마지막 업데이트**: 2026-05-16 12:20
**관련 범위**: 루트 문서, scripts(가이드 문서)
**관련 문서**: [루트 CLAUDE.md](../../CLAUDE.md), [scripts/CLAUDE.md](../../scripts/CLAUDE.md)

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

- [x] 목표 1: `CLAUDE.md`의 "(Mypy 제거됨)" 변경 이력 표현을 제거한다 (규칙 정의 문서의 자기 모순 해소).
- [x] 목표 2: `scripts/CLAUDE.md`의 "deprecated됨" 변경 이력 표현을 현재 정책 중심으로 재구성한다.

## 2) 비목표(Non-Goals)

- 코드/비즈니스 로직 변경 없음 (가이드 문서 텍스트 정리만).
- `docs/CLAUDE.md:88-89`의 "Phase 0(레드)/그린" 표현은 plan 운영 SoT 메타 컨텍스트로 의도된 표현 — **변경하지 않는다** (사용자 결정).
- 인접 항목(타입 체커 설정 세부, width 위젯 목록 등)의 의미 변경 없음 — 변경 이력 표현 제거/재구성에 한정.
- `docs/plans/_template.md`의 동일 표현은 plan 운영 표준이므로 범위 밖.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

루트 CLAUDE.md "주석 작성 원칙": 현재 코드의 상태와 동작만 설명하고, **과거 상태·변경 이력·계획 단계는 기록하지 않는다**. "문서 내구성 원칙"은 README.md/CLAUDE.md/주석 공통으로 적용된다.

1. **[CLAUDE.md:290](../../CLAUDE.md#L290)**: `- 타입 체커: PyRight 단일 사용 (Mypy 제거됨)` — "(Mypy 제거됨)"은 과거에 Mypy가 있었음을 전제하는 변경 이력 표현이다. 루트 CLAUDE.md는 이 원칙을 **직접 정의하는 문서**(271줄)인데 290줄이 스스로 위반하는 **자기 모순** 상태다. AI/사람이 규칙 근거로 읽을 때 신뢰성·일관성을 훼손한다.
2. **[scripts/CLAUDE.md:216](../../scripts/CLAUDE.md#L216)**: `- use_container_width 파라미터는 deprecated됨 (사용 금지)` — "deprecated됨"은 외부 라이브러리(Streamlit) 상태 변경 이력 표현이다. 현재 정책("width 파라미터만 사용")을 직접 기술하는 방식으로 재구성하면 변경 이력 표현 없이 동일 규칙을 전달할 수 있다.

두 항목 모두 런타임/비즈니스 동작에 영향이 없으며, 가이드 문서의 규칙 일관성 측면 정리다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md): "주석 작성 원칙", "문서 내구성 원칙", "수술적 변경"
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): Streamlit 앱 규칙(width 파라미터)
- [docs/CLAUDE.md](../CLAUDE.md): 계획서 운영 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `CLAUDE.md:290`에서 "(Mypy 제거됨)" 제거, 인접 의미 보존
- [x] `scripts/CLAUDE.md:216` "deprecated됨" 표현을 현재 정책 중심으로 재구성, `width="stretch"`/`width="content"` 규칙 보존
- [x] 프로젝트 전체에서 동일 성격의 잔여 "Mypy 제거"/"deprecated됨" 변경 이력 표현 부재 확인 (grep — 잔여 표현 없음)
- [x] `poetry run python validate_project.py` 통과 (passed=1027, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (146 files left unchanged)
- [x] 문서 업데이트 명시: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / `CLAUDE.md`·`scripts/CLAUDE.md` 변경 있음
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `CLAUDE.md` — L290 변경 이력 표현 제거
- `scripts/CLAUDE.md` — L216 deprecated 표현 재구성
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어/CLI 옵션 변경 없음)

### 데이터/결과 영향

- 코드/출력/테스트 영향 없음 (가이드 문서 텍스트 정리).
- AI/사람이 규칙 문서를 읽을 때의 일관성만 개선.

## 6) 단계별 계획(Phases)

> Phase 0(레드) 불요: 테스트로 고정할 인바리언트/정책 변경이 없고, 에러 처리 정책 변경도 없는 순수 문서 정리이다.

### Phase 1 — 가이드 문서 변경 이력 표현 정리(그린 유지)

**작업 내용**:

- [x] `CLAUDE.md:290` — `- 타입 체커: PyRight 단일 사용 (Mypy 제거됨)` → `- 타입 체커: PyRight 단일 사용` (하위 들여쓰기 설정 항목은 그대로 유지)
- [x] `scripts/CLAUDE.md:216` — `- use_container_width 파라미터는 deprecated됨 (사용 금지)` → `- 너비 지정은 \`width\` 파라미터로만 한다 (\`use_container_width\`는 사용하지 않는다)`. `width="stretch"`/`width="content"` 및 적용 위젯 목록은 보존
- [x] grep으로 동일 성격 잔여 표현(다른 위치의 "Mypy 제거", "deprecated됨" 변경 이력) 부재 확인 (잔여 없음)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 문서 업데이트 확정: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / `CLAUDE.md`·`scripts/CLAUDE.md` 변경 반영
- [x] `poetry run black .` 실행(자동 포맷 적용 — 146 files left unchanged)
- [x] 변경 내용 최종 검토 (인접 의미 보존 확인)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1027, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 문서 / 가이드 변경 이력 표현 정리 — CLAUDE.md(Mypy)·scripts/CLAUDE.md(deprecated)
2. 문서 / 루트 CLAUDE.md 자기 모순 해소 + scripts 가이드 현재 정책 재구성
3. 문서 / 주석 작성 원칙 준수 — 변경 이력 표현 제거
4. 문서 / 문서 내구성 정리(Mypy 제거 이력·deprecated 표현 삭제)
5. 문서 / 전수 감사 후속(P3) — 가이드 문서 변경 이력 표현 정리

## 7) 리스크(Risks)

- 매우 낮음. 동작/테스트/다른 문서 참조 무영향. 텍스트 2곳 정리.
- 재구성 문장이 기존 규칙(use_container_width 금지 + width 사용)을 누락하지 않도록 의미 보존 검토로 완화.

## 8) 메모(Notes)

- 전수 감사 후속 P3 항목. P1([PLAN_equity_equation_guard.md](PLAN_equity_equation_guard.md))·P2([PLAN_lag_input_validation.md](PLAN_lag_input_validation.md))는 ✅ Done.
- 사용자가 P3 2건(①②)을 함께 진행하기로 결정. 동일 성격(문서 변경 이력 표현 정리)이라 단일 plan으로 묶음.
- 스킵 없음 목표. 스킵 발생 시 Done 처리 금지.

### 진행 로그 (KST)

- 2026-05-16 12:00: 사용자 결정(P3 1·2번 진행) → P3 통합 plan 작성.
- 2026-05-16 12:20: Phase 1(CLAUDE.md·scripts/CLAUDE.md 정리, 잔여 표현 grep 확인) → black(146 unchanged) → validate_project.py(passed=1027, failed=0, skipped=0) 통과. 상태 Done.
