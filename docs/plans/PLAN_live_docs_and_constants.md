---
상태: Done
작성일: 2026-04-12 20:00
마지막 업데이트: 2026-04-12 20:00
---

# Plan: live 문서/주석 정리 + 상수화

## Goal

live 도메인의 문서/주석/코드 불일치, 과거 참조 제거, 하드코딩 수치 수정, 상수화를 수행한다.

## Non-Goals

- 코드 동작 변경 (비즈니스 로직, 테스트 결과에 영향 없음)
- cli.py 구조 분리 (별도 예외 규칙 추가로 대체)

## Context

live/ 전수 분석에서 발견된 문서/주석/상수 이슈를 일괄 수정한다.

영향받는 규칙:

- [CLAUDE.md](../../CLAUDE.md) — 주석 작성 원칙, 상수 관리 원칙
- [live/CLAUDE.md](../../live/CLAUDE.md) — live 도메인 가이드

## Definition of Done

- [x] live/CLAUDE.md 폴더 구조에 누락 파일 3개 추가
- [x] live/CLAUDE.md CLI 계층 예외 규칙 추가
- [x] daily_runner.py step 번호 중복 수정
- [x] notifier.py _format_pct docstring 수정
- [x] history.py (T-15.4) 과거 참조 제거
- [x] cli.py "6 종" 하드코딩 수정
- [x] constants.py NOTIFICATION_TITLE 상수 추가
- [x] notifier.py 리터럴 → NOTIFICATION_TITLE 적용
- [x] constants.py GIT_BOT_NAME, GIT_BOT_EMAIL 상수 추가
- [x] git_state.py 리터럴 → 상수 적용
- [x] `poetry run python validate_project.py` passed=0 failed=0 skipped=0
- [ ] README.md 변경 없음

## Scope

| 파일 | 변경 내용 |
|------|----------|
| `live/CLAUDE.md` | 폴더 구조 + CLI 예외 규칙 |
| `live/src/live/daily_runner.py` | 주석 번호 |
| `live/src/live/notifier.py` | docstring + 상수 적용 |
| `live/src/live/history.py` | 주석 |
| `live/src/live/cli.py` | docstring + argparse help |
| `live/src/live/constants.py` | 상수 3개 추가 |
| `live/src/live/git_state.py` | 상수 적용 |

## Phase 1 — 문서/주석 정리 + 상수화 (단일 Phase)

1. live/CLAUDE.md 폴더 구조에 `__main__.py`, `git_state.py`, `balance_adjust.py` 추가
2. live/CLAUDE.md에 CLI 계층 예외 규칙 추가
3. daily_runner.py step 5 중복 → 순차 번호 재정리
4. notifier._format_pct docstring 범위 수정
5. history.py append_summary docstring에서 `(T-15.4)` 제거
6. cli.py docstring과 argparse help에서 "6 종" / "(6종)" 제거
7. constants.py에 NOTIFICATION_TITLE, GIT_BOT_NAME, GIT_BOT_EMAIL 추가
8. notifier.py에서 "QBT Live" / "[QBT Live]" / "[QBT Live 실패]" → NOTIFICATION_TITLE 활용
9. git_state.py에서 기본 인자 → 상수 적용

Validation: `poetry run python validate_project.py`

## Risks

- 없음 (코드 동작 변경 없음)

## Commit Messages (Final candidates)

1. `live / 문서·주석 정리 + NOTIFICATION_TITLE·GIT_BOT 상수화`
2. `live / 문서 불일치 수정 + 하드코딩 리터럴 상수화`
3. `live / CLAUDE.md 구조 보완 + 주석·상수 정리`
4. `live / 문서 3자 불일치 + 상수화 + CLI 예외 규칙 추가`
5. `live / 주석·문서 정비 + 알림 제목·git bot 상수화`
