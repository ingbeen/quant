# Implementation Plan: QBT Live - Step 11 GitHub Actions

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 13:57
**관련 문서**: 설계서 12장, TODO Step 11

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `.github/workflows/daily_run.yml` — 평일 KST 07:50 (`cron: '50 17 * * 1-5'`, `TZ: America/New_York`) 에 `live.cli run-daily` 실행
- [x] 목표 2: `.github/workflows/keepalive.yml` — 매월 1일 heartbeat commit
- [x] 목표 3: Poetry 캐싱 (`actions/cache@v4`) 적용
- [x] 목표 4: retry (1회 재시도) + notify-failure job 포함
- [x] 목표 5: yaml 구조 검증 테스트 (workflow 키 존재성)

## 2) 비목표

- 실제 GitHub Actions 실행 (사용자 수동 테스트 M-11.1~3)
- workflow 의 동적 동작 검증 (CI 환경 필수)

## 3) 배경/맥락

### 동기

- 매일 미국장 마감 후 KST 07:50 에 live.cli run-daily 자동 실행
- Spark 무료 한도 내 keepalive (매월 1일) 로 Firebase 활성 유지
- 실패 시 자동 retry 1회 후에도 실패하면 notify-failure 알림

### 설계 결정

#### D1. cron + timezone

- `cron: '50 17 * * 1-5'` (월~금 17:50)
- `env: TZ: America/New_York` 로 ET 17:50 = 장 마감 20분 후

#### D2. retry 전략

- retry job: 첫 실패 후 5 분 대기 후 1 회 재시도
- notify-failure job: 두 번째도 실패하면 호출 (`if: failure()`)

#### D3. 캐싱

- Poetry venv 캐시: `~/.cache/pypoetry/virtualenvs` + `pyproject.toml` 해시 키

## 4) DoD

- [x] `.github/workflows/daily_run.yml` 작성
- [x] `.github/workflows/keepalive.yml` 작성
- [x] `live/tests/test_workflows.py` 작성 — yaml 구조 검증
- [x] black + validate_project 통과
- [x] TODO Step 11 체크박스 체크
- [x] plan Done

## 5) 변경 범위

### 신규

- `.github/workflows/daily_run.yml`
- `.github/workflows/keepalive.yml`
- `live/tests/test_workflows.py`

### 수정

- `docs/TODO_QBT_LIVE.md`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 설계

- [x] `test_workflows.py`:
  - daily_run.yml: 파일 존재 / yaml 파싱 / cron / timezone / poetry cache step / retry job / notify-failure job
  - keepalive.yml: 파일 존재 / cron 매월 1일

### Phase 1 — yaml 작성

- [x] daily_run.yml — 실제 동작하는 workflow
- [x] keepalive.yml

### Phase 2 — 문서

- [x] TODO Step 11 체크박스

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=714, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / GitHub Actions daily_run + keepalive (Step 11)`
2. `live / cron 17:50 ET + retry + notify-failure`
3. `live / .github/workflows/ + Poetry 캐싱`
4. `live / Step 11 workflow yaml 작성`
5. `live / 자동 실행 스케쥴러`

## 7) 리스크

- 실제 시크릿 동작 검증은 사용자 수동 테스트에서만 가능
- yaml 문법 오류 시 GitHub UI 에서만 감지

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 13:57: 계획서 작성 + 구현
