# Implementation Plan: QBT Live - Step 15 히스토리 (history.py)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 14:35
**관련 문서**: 설계서 10.1, TODO Step 15

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `save_daily_log(date, payload, history_dir)` — 일별 상세 JSON 저장
- [x] 목표 2: `append_summary(summary, history_dir)` — JSONL 1행 append
- [x] 목표 3: `append_user_trade(trade, history_dir)` — JSONL 1행 append
- [x] 목표 4: 같은 날짜 중복 호출 시 덮어쓰지 않고 누적
- [x] 목표 5: T-15.1 ~ T-15.4 통과

## 2) 비목표

- Git push (Step 11 GitHub Actions)
- 자동 정리 (설계서 10.1: 전체 영구 보존)

## 3) 배경/맥락

### 동기

- qbt-live-state 의 history/ 디렉토리에 영구 보존되는 로그
- 일별 JSON / 요약 JSONL / 사용자 체결 JSONL 3 종

### 설계 결정

#### D1. 파일 구조

- `history/daily/{YYYY-MM-DD}.json` — 1 일 상세
- `history/summary.jsonl` — 일별 요약 (1 줄당 1 일)
- `history/user_trades.jsonl` — 사용자 체결 입력 누적

#### D2. JSONL append 동작

- 같은 날짜 호출 → 덮어쓰지 않고 줄 추가 (T-15.4)
- 부모 디렉토리 자동 생성
- atomic write 는 단일 라인 append 만 적용 (전체 파일 atomic 은 불필요)

#### D3. 함수 시그니처

```python
def save_daily_log(date_iso: str, payload: dict, history_dir: Path) -> Path
def append_summary(summary: dict, history_dir: Path) -> None
def append_user_trade(trade: dict, history_dir: Path) -> None
```

## 4) DoD

- [x] `live/src/live/history.py` 구현
- [x] `live/tests/test_history.py` 작성 (T-15.1~15.4)
- [x] black + validate_project 통과
- [x] TODO Step 15 체크박스
- [x] plan Done

## 5) 변경 범위

### 신규

- `live/tests/test_history.py`

### 수정

- `live/src/live/history.py` (구현)
- `docs/TODO_QBT_LIVE.md`

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] T-15.1: save_daily_log → JSON 파일 생성 확인
- [x] T-15.2: append_summary → JSONL 1행 추가
- [x] T-15.3: append_user_trade → JSONL 1행 추가
- [x] T-15.4: 같은 날짜 2번 append → 2행 (덮어쓰기 아님)

### Phase 1 — 구현

- [x] 3 개 함수 + 디렉토리 자동 생성

### Phase 2 — 문서

- [x] TODO Step 15

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=760, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / 영구 히스토리 저장 (Step 15)`
2. `live / history.py — daily/summary/user_trades`
3. `live / JSONL append + 일별 JSON 보관`
4. `live / Step 15 히스토리 모듈`
5. `live / 영구 보존 정책 + atomic append`

## 7) 리스크

- 동시 쓰기 — 본 환경은 단일 프로세스 (GitHub Actions) 이므로 무시

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:35: 계획서 작성 + 구현
