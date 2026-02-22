# Implementation Plan: ATR 트레일링 스탑 전략 (buffer_zone_atr_tqqq)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-22 23:30
**마지막 업데이트**: 2026-02-22 23:30
**관련 범위**: backtest (strategies, walkforward, constants, types)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [ ] ATR 트레일링 스탑을 포함한 새 전략 파일 `buffer_zone_atr_tqqq.py` 생성
- [ ] 매도 조건을 "하단밴드 하향돌파 **OR** ATR 스탑 발동"으로 확장
- [ ] ATR 시그널 소스는 QQQ(signal_df) 고정
- [ ] ATR 기준가는 `highest_close_since_entry` 고정
- [ ] WFO 파이프라인에서 ATR 전략 실행 가능하도록 통합
- [ ] 기존 `buffer_zone_tqqq` 전략은 변경 없음 (비교용 보존)

## 2) 비목표(Non-Goals)

- 기존 `buffer_zone_tqqq.py` 수정 (새 파일로 분리)
- `atr_source = "trade"` 옵션 (QQQ 고정으로 합의 완료)
- `highest_high_since_entry` 옵션 (1차는 highest_close 고정)
- 매수 로직 변경 (매수는 기존과 동일)
- WFO 재실행 (Plan 구현 후 별도 실행)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

TQQQ WFO Stitched MDD -62%로 목표 -50% 미달. 현재 매도 규칙은 "하단밴드 하향돌파"뿐이라, 2020년 3월 코로나 같은 급락에서 밴드 도달 전까지 포지션을 보유하며 큰 손실 발생.

ATR 트레일링 스탑은 변동성 기반 비상 브레이크로, 급락 시 밴드보다 먼저 작동하여 MDD를 줄이는 것이 목표.

### 핵심 설계 결정 (합의 완료)

| 항목 | 결정 | 근거 |
|------|------|------|
| ATR 시그널 소스 | QQQ (signal_df) | 전략의 모든 신호가 QQQ 기반, 레버리지 ETF 노이즈 회피 |
| ATR period 그리드 | {14, 22} | Wilder 표준(14) + Chandelier Exit 표준(22) |
| ATR multiplier 그리드 | {2.5, 3.0} | Chandelier Exit 기본(3.0) + 약간 공격적(2.5) |
| 기준가 | highest_close_since_entry | 전략 전체가 close 기반, 시그널 일관성 |
| 매도 조건 | 하단밴드 OR ATR 스탑 | 둘 중 먼저 걸리는 쪽 실행 |

### WFO 탐색 공간

기존 버퍼존 5차원 (432개) + ATR 2차원 (4개) = **5 × 4 = 1,728개** (관리 가능한 범위)

- sell_fixed 모드: sell_buf=0.05 고정이므로 432/3 × 4 = **576개**

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- 루트 `CLAUDE.md` (상수 관리, 아키텍처 원칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] ATR 계산 함수 구현 (`_calculate_atr`)
- [ ] ATR 트레일링 스탑 감지 함수 구현 (`_detect_atr_stop_signal`)
- [ ] `run_buffer_strategy()`에 ATR 스탑 OR 조건 통합
- [ ] `BufferStrategyParams`에 ATR 관련 필드 추가 (`atr_period`, `atr_multiplier`)
- [ ] `buffer_zone_atr_tqqq.py` 전략 파일 생성
- [ ] WFO 그리드에 ATR 파라미터 포함
- [ ] `run_walkforward.py`에서 ATR 전략 실행 지원
- [ ] 결과 디렉토리 `storage/results/backtest/buffer_zone_atr_tqqq/` 지원
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] 필요한 문서 업데이트
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — ATR 계산 함수, ATR 스탑 감지 함수, `run_buffer_strategy()` ATR OR 조건 추가, `BufferStrategyParams` 필드 추가, `run_grid_search()` ATR 파라미터 지원
- `src/qbt/backtest/strategies/buffer_zone_atr_tqqq.py` — **신규 생성**: ATR 전략 설정 파일
- `src/qbt/backtest/constants.py` — ATR 기본값 상수, WFO ATR 그리드 리스트
- `src/qbt/backtest/types.py` — `WfoWindowResultDict`에 ATR 파라미터 필드 추가 (선택적)
- `src/qbt/common_constants.py` — `BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR` 경로 추가
- `scripts/backtest/run_walkforward.py` — STRATEGY_CONFIG에 ATR 전략 추가
- `tests/test_buffer_zone_helpers.py` — ATR 관련 테스트 추가
- `tests/test_backtest_walkforward.py` — ATR 파라미터 포함 WFO 테스트

### 데이터/결과 영향

- 새 결과 디렉토리: `storage/results/backtest/buffer_zone_atr_tqqq/`
- 기존 `buffer_zone_tqqq` 결과에는 영향 없음
- grid_results.csv에 `atr_period`, `atr_multiplier` 컬럼 추가 (ATR 전략만)
- walkforward_*.csv에 `best_atr_period`, `best_atr_multiplier` 컬럼 추가 (ATR 전략만)

## 6) 단계별 계획(Phases)

### Phase 0 — ATR 정책/인터페이스 테스트 선행 작성(레드)

**작업 내용**:

- [ ] `BufferStrategyParams`에 ATR 필드 추가:
  - `atr_period: int | None = None` (None이면 ATR 미사용)
  - `atr_multiplier: float | None = None`
- [ ] `constants.py`에 ATR 상수 추가:
  - `DEFAULT_ATR_PERIOD: Final = 22`
  - `DEFAULT_ATR_MULTIPLIER: Final = 3.0`
  - `DEFAULT_WFO_ATR_PERIOD_LIST: Final = [14, 22]`
  - `DEFAULT_WFO_ATR_MULTIPLIER_LIST: Final = [2.5, 3.0]`
- [ ] `common_constants.py`에 결과 디렉토리 경로 추가
- [ ] 테스트 추가 (레드):
  - ATR 계산 정확성 (수동 계산과 비교)
  - ATR 스탑 발동 조건 (close < highest_close - ATR × multiplier)
  - ATR 스탑 미발동 (정상 변동 범위)
  - ATR None이면 기존 매도 로직만 작동 (하위 호환)
  - ATR OR 밴드: 밴드가 먼저 걸리는 케이스 / ATR이 먼저 걸리는 케이스

---

### Phase 1 — ATR 핵심 로직 구현(그린 유지)

**작업 내용**:

- [ ] `_calculate_atr()` 함수 구현:
  - 입력: signal_df (QQQ), period
  - True Range = max(high-low, |high-prev_close|, |low-prev_close|)
  - ATR = True Range의 EMA(period) 또는 Wilder smoothing
  - 반환: ATR Series
- [ ] `_detect_atr_stop_signal()` 함수 구현:
  - 입력: close, highest_close_since_entry, atr_value, multiplier
  - 조건: `close < highest_close_since_entry - atr_value * multiplier`
  - 반환: bool
- [ ] `run_buffer_strategy()`에 ATR 스탑 통합:
  - 포지션 보유 중(`position > 0`) 매도 로직에서:
    - 기존: `_detect_sell_signal()` 하나만 체크
    - 변경: `_detect_sell_signal() OR _detect_atr_stop_signal()` (params.atr_period가 None이 아닌 경우만)
  - `highest_close_since_entry` 상태 변수 관리 (매수 체결 시 초기화, 매일 갱신)
- [ ] `run_grid_search()`에 ATR 파라미터 리스트 지원 추가
- [ ] Phase 0 레드 테스트 통과 확인

---

### Phase 2 — 전략 파일 + WFO 통합(그린 유지)

**작업 내용**:

- [ ] `buffer_zone_atr_tqqq.py` 신규 생성:
  - `STRATEGY_NAME = "buffer_zone_atr_tqqq"`
  - `DISPLAY_NAME = "버퍼존 전략 ATR (TQQQ)"`
  - OVERRIDE 상수 (기존 5개 + ATR 2개)
  - `resolve_params()`, `run_single()` (buffer_zone_tqqq.py와 동일 구조, ATR 파라미터 포함)
- [ ] `run_walkforward.py`의 STRATEGY_CONFIG에 ATR 전략 추가
- [ ] `--strategy` 선택지에 `buffer_zone_atr_tqqq` 추가
- [ ] WFO 실행 시 ATR 파라미터 그리드 전달 로직

---

### Phase 3 — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트 (ATR 전략 설명 추가)
- [ ] 루트 `CLAUDE.md` 디렉토리 구조 업데이트
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / ATR 트레일링 스탑 전략 (buffer_zone_atr_tqqq) 신규 추가
2. 백테스트 / ATR 스탑 + 밴드 OR 매도 전략 구현 및 WFO 통합
3. 백테스트 / Chandelier Exit 기반 ATR 비상 브레이크 전략 추가
4. 백테스트 / MDD 개선용 ATR 트레일링 스탑 전략 및 WFO 파이프라인 확장
5. 백테스트 / buffer_zone_atr_tqqq 전략 생성 + ATR 매도 로직 + 테스트

## 7) 리스크(Risks)

- `run_buffer_strategy()` 수정으로 기존 전략 회귀 위험 → ATR 파라미터가 None이면 기존 동작 보장 (하위 호환 테스트 필수)
- WFO 탐색 공간 증가 (432 → 1,728)로 실행 시간 증가 → 병렬 처리로 대응 (기존 `run_grid_search` 인프라 활용)
- ATR 계산에 충분한 데이터 필요 (최소 period+1일) → IS 시작 부분에서 ATR이 NaN인 구간 처리
- `highest_close_since_entry` 상태 관리 복잡도 증가 → 명확한 초기화/갱신 규칙 + 테스트로 고정

## 8) 메모(Notes)

- 참고: `buffer_zone_tqqq_improvement_log.md` Session 12~15 합의 내용
- Chandelier Exit 표준: (22, 3.0) — 22-day High − ATR(22) × 3
- ATR 시그널 소스 합의: QQQ 고정 (Session 15에서 GPT는 A/B 테스트 제안했으나, 사용자가 QQQ 고정으로 결정)
- Plan 1(WFE/PC)과 Plan 2(min_trades)가 완료된 상태에서 이 Plan을 시작해야 진단 도구로 ATR 효과를 정확히 측정 가능
- 대시보드 자동 탐색: `buffer_zone_atr_tqqq/` 폴더가 생성되면 `app_single_backtest.py`가 자동으로 탭 추가 (Feature Detection 기반)

### 진행 로그 (KST)

- 2026-02-22 23:30: Plan 작성 완료 (Draft)

---
