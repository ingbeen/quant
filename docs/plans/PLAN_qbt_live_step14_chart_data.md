# Implementation Plan: QBT Live - Step 14 차트 시계열 (chart_data.py)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 14:25
**관련 문서**: 설계서 7장, 부록 A, TODO Step 14

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `build_chart_series(csv_dir, user_trades)` — 자산별 전체 기간 :class:`ChartSeries` 생성
- [x] 목표 2: EMA-200 + 버퍼존 밴드 + 신호 마커 + 사용자 체결 마커 포함
- [x] 목표 3: 초기 199 일 EMA 는 ``None`` (T-14.3)
- [x] 목표 4: T-14.1, T-14.2, T-14.3 통과

## 2) 비목표

- RTDB 업로드 (Step 12 rtdb_gateway.write_chart_data)
- 신호 정확성 (Step 7 daily_runner 가 책임)
- 차트 렌더링 (앱 영역)

## 3) 배경/맥락

### 동기

- 앱 차트 화면용 자산별 전체 기간 시계열을 RTDB 에 매일 덮어쓰기 위해 일관 포맷으로 생성
- EMA / 밴드 / 신호 마커 / 사용자 체결 마커 모두 포함

### 설계 결정

#### D1. 함수 시그니처

```python
def build_chart_series(
    csv_dir: Path,
    user_trades: dict[str, list[UserTrade]] | None = None,
) -> dict[str, ChartSeries]
```

- `csv_dir`: live 의 CSV 디렉토리 (`{state-dir}/data/stock/`)
- `user_trades`: 자산별 사용자 체결 마커 (선택)
- 반환: `{asset_id: ChartSeries}` (Q-2-2XS 4 자산)

#### D2. UserTrade 타입

- 별도 dataclass `UserTrade(date: str, direction: Literal["buy", "sell"])`
- 또는 dict 도 허용

#### D3. EMA / 밴드 계산

- QBT `add_single_moving_average(df, ma_window=200, ma_type="ema")` 재사용
- 워밍업 199 일은 NaN → `None` 변환
- 밴드: `upper = ema * (1 + buy_buffer_pct)`, `lower = ema * (1 - sell_buffer_pct)`

#### D4. 신호 마커

- 본 Step 에서는 *공식 이력*이 아직 없으므로 buy_signals/sell_signals 는 빈 리스트로 초기화
- 호출자가 별도로 신호 인덱스를 주입할 수도 있으나, 본 Step 의 단순 구현 방식은 빈 리스트 + 사용자 trade 위주

#### D5. CSV 파일명

- `{state_dir}/data/stock/{TICKER}.csv` 형식 (Step 5 와 동일)
- asset_id → ticker 매핑은 Q-2-2XS 슬롯 기준 (signal_data_path / trade_data_path)

## 4) DoD

- [x] `live/src/live/chart_data.py` 구현
- [x] `UserTrade` dataclass 추가 (models.py)
- [x] `live/tests/test_chart_data.py` 작성 (T-14.1~14.3)
- [x] black + validate_project 통과
- [x] TODO Step 14 체크박스
- [x] plan Done

## 5) 변경 범위

### 신규

- `live/tests/test_chart_data.py`

### 수정

- `live/src/live/chart_data.py` (구현)
- `live/src/live/models.py` (UserTrade 추가)
- `docs/TODO_QBT_LIVE.md`

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] T-14.1: 1년치 CSV → ChartSeries dates/close/ema_200 길이 일치
- [x] T-14.2: buy_signals / sell_signals 인덱스가 dates 범위 내
- [x] T-14.3: EMA-200 초기 199 일은 None

### Phase 1 — 구현

- [x] `UserTrade` dataclass
- [x] `build_chart_series` 함수
- [x] EMA → list 변환 (NaN → None)
- [x] user_trades 인덱스 매핑

### Phase 2 — 문서

- [x] TODO Step 14

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=748, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / 차트 시계열 build_chart_series (Step 14)`
2. `live / chart_data.py — ChartSeries 빌더`
3. `live / EMA-200 + 밴드 + user_trades 마커`
4. `live / Step 14 차트 데이터 생성`
5. `live / 자산별 전체 기간 ChartSeries`

## 7) 리스크

- EMA 계산 정확성은 QBT 함수 재사용으로 보장
- user_trades 의 날짜가 dates 에 없을 때 처리 (skip)

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:25: 계획서 작성 + 구현
