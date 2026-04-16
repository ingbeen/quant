# Implementation Plan: live reset CLI 명령 추가

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🔄 In Progress

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-16 20:00
**마지막 업데이트**: 2026-04-16 20:00
**관련 범위**: live (cli, rtdb_gateway)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md)

---

## 0) 고정 규칙

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드" 허용, Phase 1부터는 **그린 유지**.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**.
- 스킵은 가능하면 **Phase 분해로 제거**.

---

## 1) 목표(Goal)

- [ ] `poetry run python -m live reset --capital 100000000` 명령 1 개로 전체 초기화
- [ ] state + CSV + applied_ids + history + RTDB 를 한 번에 리셋

## 2) 비목표(Non-Goals)

- `--confirm` 대화형 확인 (사용자 요청으로 제외)
- device_tokens 삭제 (기본 유지)

## 3) 배경/맥락(Context)

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지** 하고 준수합니다.

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [ ] `_cmd_reset` 함수 구현 + CLI 서브커맨드 등록
- [ ] `rtdb_gateway.delete_all_except_device_tokens` 헬퍼 추가
- [ ] 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] `README.md` 에 reset 명령 추가

## 5) 변경 범위(Scope)

- `src/live/cli.py` — `_cmd_reset` + 서브커맨드 등록
- `src/live/rtdb_gateway.py` — `delete_all_except_device_tokens`
- `tests/live/test_cli.py` — reset smoke test
- `README.md` — 명령어 추가

## 6) 단계별 계획(Phases)

### Phase 1 — 구현 (그린 유지)

- [ ] `rtdb_gateway.py`: `delete_all_except_device_tokens(app)` 함수 추가
- [ ] `cli.py`: `_cmd_reset(args)` 함수 구현
- [ ] `cli.py`: argparse 서브커맨드 `reset` 등록 (`--capital` 필수 인자)
- [ ] `tests/live/test_cli.py`: reset smoke test

### Phase 2 — 문서 + 최종 검증

- [ ] `README.md` 에 reset 명령 추가
- [ ] `poetry run black .` 실행
- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates)

1. live / reset CLI 명령 추가 — state + CSV + history + RTDB 전체 초기화
2. live / 전체 초기화 명령 (reset) 추가 + RTDB 일괄 삭제 헬퍼
3. live / python -m live reset 으로 클린 슬레이트 초기화 지원

## 7) 리스크(Risks)

- RTDB 삭제 실패 시 state repo 는 이미 push 된 상태가 될 수 있음 → ephemeral 내에서 RTDB 먼저 삭제하여 방지

## 8) 메모(Notes)

### 진행 로그 (KST)

- 2026-04-16 20:00: plan 작성 + 바로 구현 시작

---
