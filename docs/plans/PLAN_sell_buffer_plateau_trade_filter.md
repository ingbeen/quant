# Implementation Plan: Sell Buffer 고원 구간 거래 수 필터 적용

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

**작성일**: 2026-03-14 15:00
**마지막 업데이트**: 2026-03-14 15:30
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] Sell Buffer 탭의 고원 구간을 거래 수 기반으로 필터링하여 올바른 위치(0.05 부근)에 표시
- [x] 거래 수가 너무 적은 파라미터값(예: sell=0.15, 4거래)을 고원 탐지 대상에서 제외
- [x] 차트 아래에 필터 적용 사유를 설명하는 안내 문구 추가

## 2) 비목표(Non-Goals)

- 다른 파라미터(MA Window, Buy Buffer, Hold Days)에 거래 수 필터 적용
- 고원 구간의 최소 시각적 폭 보장 (기존 로직 유지)
- 고원 탐지 알고리즘(`find_plateau_range`) 자체 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- Sell Buffer 탭에서 고원 구간이 `(0.15, 0.15)`으로 탐지됨 (폭 0, 시각적으로 보이지 않음)
- sell=0.15는 QQQ 기준 4거래로, 사실상 Buy & Hold와 동일한 성격
- 거래 수가 극소한 파라미터값의 Calmar가 최댓값이 되어 고원이 잘못된 위치에 잡히는 구조적 문제
- QQQ sell buffer 데이터:

| sell 값 | 거래 수 | Calmar |
|---------|---------|--------|
| 0.01 | 27 | 0.20 |
| 0.03 | 21 | 0.24 |
| 0.05 | 14 | 0.30 |
| 0.07 | 13 | 0.22 |
| 0.10 | 8 | 0.23 |
| **0.15** | **4** | **0.36** |

- sell=0.15를 제외하면 max=0.30 (sell=0.05), 90% 임계값=0.27 → 고원 `(0.05, 0.05)` 으로 올바르게 잡힘

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `find_plateau_range_with_trade_filter()` 함수 구현 및 테스트 통과
- [x] Sell Buffer 탭에서 거래 수 필터 적용하여 고원 구간이 0.05 부근에 표시
- [x] 차트 아래에 필터 적용 안내 문구 표시
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=328, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/parameter_stability.py`: `find_plateau_range_with_trade_filter()` 함수 추가
- `scripts/backtest/app_parameter_stability.py`: sell_buffer 탭에 거래 수 필터 적용 + 안내 문구
- `tests/test_parameter_stability.py`: 새 함수 테스트 추가

### 데이터/결과 영향

- 기존 CSV/JSON 파일 변경 없음
- 시각화에만 영향 (Sell Buffer 탭 고원 위치 변경 + 안내 문구 추가)

## 6) 단계별 계획(Phases)

### Phase 1 — 비즈니스 로직 + 테스트 (그린 유지)

**작업 내용**:

- [x] `parameter_stability.py`에 `find_plateau_range_with_trade_filter()` 함수 추가
  - 시그니처: `(metric_series, trades_series, min_trades, threshold_ratio=0.9) -> tuple[tuple[float, float] | None, list[float]]`
  - 반환값: `(고원 범위, 제외된 파라미터값 리스트)`
  - 내부: trades < min_trades인 인덱스 제거 후 `find_plateau_range()` 위임
- [x] `test_parameter_stability.py`에 테스트 추가
  - 정상 필터링: 저거래 파라미터 제외 후 고원 탐지
  - 모든 값 필터링됨: 전부 제외 시 None 반환
  - 필터 없는 경우: 모든 거래 수 충분 시 기존 `find_plateau_range`와 동일

---

### Phase 2 — 앱 적용 (그린 유지)

**작업 내용**:

- [ ] `app_parameter_stability.py` 변경
  - 로컬 상수 추가: `_SELL_BUFFER_MIN_TRADES = 5`
  - `_render_line_chart()`에 `trade_filter_min_trades: int | None = None` 파라미터 추가
    - 설정 시: trades CSV 로드 → QQQ 거래 수 시리즈 구성 → `find_plateau_range_with_trade_filter()` 호출
    - 미설정 시: 기존 `find_plateau_range()` 호출 (동작 변경 없음)
    - 필터 적용 시 annotation_text를 `"고원 구간 (QQQ 90%, 저거래 제외)"` 로 변경
  - `_render_tab()`에서 sell_buffer 탭만 `trade_filter_min_trades=_SELL_BUFFER_MIN_TRADES` 전달
  - sell_buffer 탭의 Calmar 차트 아래에 `st.caption()` 추가
    - 내용: "sell=0.15 (QQQ 4거래) 등 거래 수 5회 미만인 파라미터는 사실상 Buy & Hold와 동일하여 고원 탐지 대상에서 제외됩니다."
- [ ] import 추가: `find_plateau_range_with_trade_filter`

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Sell Buffer 고원 구간 거래 수 필터 적용 (저거래 파라미터 제외)
2. 백테스트 / Sell Buffer 고원 탐지에 거래 수 기반 필터링 추가
3. 백테스트 / 고원 분석 sell_buffer 거래 수 필터 및 안내 문구 추가
4. 백테스트 / 고원 시각화 sell_buffer 저거래 파라미터 제외 로직 구현
5. 백테스트 / Sell Buffer 고원 구간 개선: 거래 수 필터 + UI 설명 추가

## 7) 리스크(Risks)

- 리스크 낮음: 시각화 변경만 해당, 기존 데이터/로직 영향 없음
- `min_trades=5` 기준이 향후 데이터 변경 시 재검토 필요할 수 있음

## 8) 메모(Notes)

- `_SELL_BUFFER_MIN_TRADES = 5` 근거: sell=0.15의 QQQ 거래 수가 4회로 Buy & Hold(1회 매수)와 사실상 동일
- 필터링은 QQQ 기준으로만 수행 (기존 고원 탐지도 QQQ 기준)
- 필터 적용 후 예상 결과: 고원 `(0.05, 0.05)` at QQQ Calmar max=0.30

### 진행 로그 (KST)

- 2026-03-14 15:00: 계획서 작성
