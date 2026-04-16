# Implementation Plan: live / MA 근접도 표시 티커를 시그널 기준으로 변경

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

**작성일**: 2026-04-16 22:00
**마지막 업데이트**: 2026-04-16 22:00
**관련 범위**: live (notifier, constants)
**관련 문서**: `src/live/CLAUDE.md`, `tests/CLAUDE.md`

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

- [ ] 일일 리포트 본문의 MA 근접도 표시에서 trade 티커(SSO, QLD) 대신 signal 티커(SPY, QQQ)를 사용한다

## 2) 비목표(Non-Goals)

- `DailyResult.ma_distances` dict의 key 변경 (내부 데이터 구조는 `asset_id` 유지)
- RTDB 저장 구조 변경 (`/latest/signals/{asset_id}` 경로 유지)
- history 저장 구조 변경 (`daily/{date}.json`의 `ma_distances` key 유지)
- 시그널 항목("시그널: SSO buy") 등 다른 알림 본문 항목의 티커 표시 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- MA 근접도는 signal 데이터(SPY, QQQ)로 계산된다 (설계상 SSO/QLD는 signal=SPY/QQQ, trade=SSO/QLD 비대칭)
- 그런데 알림 본문에는 `asset_id.upper()` = SSO, QLD로 표시되어, 사용자가 실제 MA 기준 티커를 알 수 없다
- 예: `MA 근접도: SSO +2.56%, QLD +1.19%` → 사용자가 "SSO의 MA 근접도"로 오해할 수 있음
- signal 티커 기준으로 표시하면 `MA 근접도: SPY +2.56%, QQQ +1.19%`가 되어 데이터 출처와 일치한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/live/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] MA 근접도 표시가 signal 티커 기준으로 출력됨 (SPY, QQQ, GLD, TLT)
- [ ] `build_asset_signal_ticker_map()` 헬퍼 함수 추가 및 테스트
- [ ] 기존 notifier 테스트 수정 + 신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] README.md 변경 없음
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/constants.py`: `build_asset_signal_ticker_map()` 헬퍼 추가
- `src/live/notifier.py`: `_build_daily_body()` 내 MA 근접도 표시 로직 변경
- `tests/live/test_notifier.py`: 기존 테스트 수정 + 신규 테스트 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- 알림 본문의 MA 근접도 라인만 변경 (내부 데이터 구조 불변)
- RTDB / history / DailyResult 구조 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 헬퍼 함수 추가 + notifier 수정 + 테스트 (그린 유지)

**작업 내용**:

- [ ] `src/live/constants.py`에 `build_asset_signal_ticker_map()` 추가
  - 반환: `dict[str, str]` — `{asset_id: signal_ticker}` (예: `{"sso": "SPY", "qld": "QQQ", "gld": "GLD", "tlt": "TLT"}`)
  - `get_live_portfolio_config()` + `extract_ticker_from_path(slot.signal_data_path)` 활용
- [ ] `src/live/notifier.py`의 `_build_daily_body()` 수정
  - `build_asset_signal_ticker_map()` 호출하여 매핑 구성
  - MA 근접도 라인에서 `aid.upper()` 대신 `signal_ticker_map.get(aid, aid.upper())` 사용
- [ ] `tests/live/test_notifier.py` 수정
  - `test_body_contains_ma_distance_line`: `"SSO"` → `"SPY"` 검증으로 변경
  - 신규: `test_ma_distance_uses_signal_tickers` — SPY/QQQ 표시 및 SSO/QLD 미표시 검증

---

### Phase 2 (마지막) — 포맷 적용 및 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 알림 본문 MA 근접도 표시를 signal 티커 기준으로 변경 (SPY, QQQ)
2. live / MA 근접도에 signal 티커(SPY/QQQ) 표시 — trade 티커(SSO/QLD) 대신
3. live / 리포트 MA 근접도 티커를 시그널 데이터 출처와 일치시킴
4. live / notifier MA 근접도 라벨을 asset_id 에서 signal ticker 로 교체
5. live / 일일 알림 MA 근접도 표시 티커 수정 (SSO→SPY, QLD→QQQ)

## 7) 리스크(Risks)

- 리스크 낮음: 표시(display)만 변경하며 내부 데이터 구조/계산 로직은 불변
- `build_asset_signal_ticker_map()` 은 `get_live_portfolio_config()` 에 의존하므로, 포트폴리오 구성이 바뀌면 자동 반영됨

## 8) 메모(Notes)

- GLD, TLT는 signal_data_path == trade_data_path이므로 표시가 동일하게 유지됨
- `build_signal_trade_map()` (기존)은 `{signal_ticker: trade_ticker}` 방향이고, 신규 함수는 `{asset_id: signal_ticker}` 방향으로 용도가 다름

### 진행 로그 (KST)

- 2026-04-16 22:00: 계획서 작성 완료
