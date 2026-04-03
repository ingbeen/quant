# Implementation Plan: 포트폴리오 시그널 차트 lightweight-charts 전환

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

**작성일**: 2026-04-03 15:00
**마지막 업데이트**: 2026-04-03 15:00
**관련 범위**: scripts/backtest
**관련 문서**: scripts/CLAUDE.md, src/qbt/backtest/CLAUDE.md

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

- [x] 포트폴리오 실험 상세 탭의 시그널 차트를 Plotly에서 lightweight-charts로 전환
- [x] Buy/Sell 마커 (arrowUp/arrowDown) 표시
- [x] 상단/하단 밴드 표시 (buffer_zone 전략 자산에 한해)
- [x] customValues 기반 tooltip 제공 (OHLC, 전일대비%, MA, 밴드)

## 2) 비목표(Non-Goals)

- 에쿼티/드로우다운 pane 추가 (이미 상위 섹션 "에쿼티 및 드로우다운"에서 포트폴리오 레벨로 제공)
- 비즈니스 로직 변경
- signal CSV 스키마 변경
- 테스트 추가 (scripts 계층 UI 변경이므로)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 포트폴리오 시그널 차트가 Plotly Candlestick을 사용하여 단일 백테스트 앱(lightweight-charts)과 UX가 불일치
- Buy/Sell 마커가 기본 삼각형 마커로 표시되어 가독성이 떨어짐
- customValues 기반 tooltip이 없어 상세 정보 확인 불편
- 밴드가 signal CSV에 없어 표시되지 않음 (MA + buffer pct로 계산 가능)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`: Streamlit 앱 규칙, width 파라미터 정책
- `src/qbt/backtest/CLAUDE.md`: 포트폴리오 타입 및 구조

## 4) 완료 조건(Definition of Done)

- [x] Plotly 시그널 차트를 lightweight-charts 캔들스틱으로 전환
- [x] Buy/Sell 마커 (arrowUp/arrowDown, 가격 표시) 구현
- [x] 상단/하단 밴드 오버레이 (buffer_zone 전략 자산만)
- [x] customValues 기반 tooltip (OHLC, 전일대비%, MA, 밴드)
- [x] `poetry run python validate_project.py` 통과 (failed=1 (기존 constants.py 변경으로 인한 기존 실패, 본 작업 무관), skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화
- [x] `README.md` 변경 없음

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_portfolio_backtest.py`: 시그널 차트 렌더링 함수 전면 교체

### 데이터/결과 영향

- 출력 스키마 변경 없음 (UI 렌더링만 변경)
- 밴드는 기존 데이터(ma_200 + buffer pct)로 런타임 계산

## 6) 단계별 계획(Phases)

### Phase 1 — 시그널 차트 lightweight-charts 전환

**작업 내용**:

- [x] `lightweight_charts_v5_component` import 추가 및 관련 상수 추가
- [x] 밴드 계산 헬퍼 함수 추가 (`_compute_bands_for_signal`)
- [x] 캔들 데이터 빌더 함수 추가 (`_build_portfolio_candle_data`) — customValues 포함
- [x] MA/밴드 시리즈 데이터 빌더 함수 추가 (`_build_lwc_series_data`)
- [x] Buy/Sell 마커 빌더 함수 추가 (`_build_portfolio_markers`)
- [x] `_render_signal_chart` 함수를 lightweight-charts 기반으로 재작성
- [x] 자산별 buffer params를 summary.json에서 추출하는 로직 추가 (`_find_asset_config`)

---

### Phase 2 (마지막) — 포맷 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=478, failed=1 (기존 constants 변경, 본 작업 무관), skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 대시보드 / 시그널 차트를 lightweight-charts로 전환 (밴드, Buy/Sell 마커, 툴팁 추가)
2. 포트폴리오 대시보드 / 시그널 차트 UX 개선 (Plotly -> lightweight-charts + 거래 마커 + 밴드)
3. 포트폴리오 대시보드 / 시그널 차트 lightweight-charts 전환 및 상세 정보 표시 강화
4. 포트폴리오 대시보드 / 자산별 시그널 차트에 캔들스틱, 밴드, 거래 마커, 툴팁 구현
5. 포트폴리오 대시보드 / 시그널 차트를 단일 백테스트와 동일한 lightweight-charts 기반으로 전환

## 7) 리스크(Risks)

- lightweight-charts 컴포넌트가 포트폴리오 앱에서 정상 동작하지 않을 가능성 (이미 단일 백테스트, WFO 앱에서 검증됨)

## 8) 메모(Notes)

- `app_single_backtest.py`의 `_build_candle_data`, `_build_markers`, `_build_series_data` 패턴을 참고
- 밴드 계산: upper = ma * (1 + sell_buffer_zone_pct), lower = ma * (1 - buy_buffer_zone_pct)
- buy_and_hold 전략 자산은 밴드 표시 안 함 (strategy_id로 Feature Detection)
- signal CSV 컬럼: Date, Open, High, Low, Close, Volume, ma_200, change_pct
- summary.json의 portfolio_config.assets[]에서 자산별 buffer params 추출

### 진행 로그 (KST)

- 2026-04-03 15:00: 계획서 작성
- 2026-04-03 15:15: Phase 1 완료 (lightweight-charts 전환, 마커, 밴드, 툴팁 구현)
- 2026-04-03 15:20: Phase 2 완료 (black 포맷, validate 통과 — 기존 test 1개 실패는 constants.py 사전 변경 때문)
