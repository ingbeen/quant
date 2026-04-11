# Implementation Plan: QBT Live - Step 12 RTDB 게이트웨이

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 14:05
**관련 문서**: 설계서 10장, 부록 A, TODO Step 12

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: Firebase Admin SDK 초기화 lazy 헬퍼
- [x] 목표 2: `fetch_unprocessed_fills(app)`, `mark_fills_processed(app, keys)`
- [x] 목표 3: `write_read_model(app, state, result)`, `write_chart_data(app, series)`
- [x] 목표 4: `read_device_tokens(app)`, `remove_invalid_tokens(app, tokens)`
- [x] 목표 5: 모든 외부 호출 mock 기반 테스트

## 2) 비목표

- 실제 Firebase 호출 (수동 테스트 M-12.1~12.2)
- 알림 발송 (Step 13)

## 3) 배경/맥락

### 동기

- daily_runner 가 사용하는 RTDB 진입점들을 한 모듈에 캡슐화
- Firebase Admin SDK 의존성을 lazy 로 초기화하여 테스트 환경에서 mock 주입 용이

### 설계 결정

#### D1. Firebase 초기화

- `initialize_firebase_app(credentials_path, db_url) -> firebase_admin.App` 전용 함수
- 호출자가 `App` 객체를 함수들에 전달 (의존성 주입)
- 테스트는 `unittest.mock.MagicMock` 으로 `App` 대체

#### D2. RTDB 경로 (설계서 10.2)

- `/latest/portfolio`, `/latest/signals`, `/latest/pending_orders`, `/latest/drift`
- `/latest/chart_data/{asset_id}`
- `/history/summary/`
- `/fills/inbox/{uuid}` — `processed=true` 마킹
- `/device_tokens/{device_id}`

#### D3. ActualFill 매핑

- RTDB `/fills/inbox/{uuid}` 의 dict → `ActualFill` 변환 함수 `_dict_to_actual_fill(data, key)`
- `processed=False` 인 항목만 `fetch_unprocessed_fills` 가 반환

## 4) DoD

- [x] `live/src/live/rtdb_gateway.py` 구현
- [x] `live/tests/test_rtdb_gateway.py` mock 기반 테스트
- [x] firebase_admin 미설치 환경에서도 import 가능 (lazy import)
- [x] black + validate_project 통과
- [x] TODO Step 12 체크박스 (RTDB 구현)
- [x] plan Done

## 5) 변경 범위

### 신규

- `live/tests/test_rtdb_gateway.py`

### 수정

- `live/src/live/rtdb_gateway.py` (구현)
- `docs/TODO_QBT_LIVE.md`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] mock RTDB reference 객체로 fetch / mark / write / read / remove 검증
- [x] processed 플래그 필터링 검증

### Phase 1 — 구현

- [x] Firebase 초기화 헬퍼
- [x] 6 개 공개 함수
- [x] dict ↔ ActualFill 변환 헬퍼

### Phase 2 — 문서

- [x] TODO 체크박스

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=727, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / RTDB 게이트웨이 (Step 12)`
2. `live / rtdb_gateway.py — fills/read_model/chart/tokens`
3. `live / Firebase Admin SDK 초기화 + RTDB 6종 진입점`
4. `live / Step 12 RTDB 통합 어댑터`
5. `live / fills inbox + device_tokens + chart_data 쓰기`

## 7) 리스크

- Firebase Admin SDK 의 실제 동작은 사용자 환경에서만 검증 가능
- mock 의 fidelity 가 부족할 수 있으나 기본 호출 시그니처는 검증 가능

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:05: 계획서 작성 + 구현
