# Implementation Plan: QBT Live - Step 8 fill 자동 매칭 + drift (drift.py)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**Done 처리 규칙**: DoD 모두 [x] + failed=0 + skipped=0.

---

**작성일**: 2026-04-11 13:40
**관련 문서**: 설계서 6장, 14장, 부록 A

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `classify_fill(fill, state) -> Literal["system_fill", "personal_trade"]`
- [x] 목표 2: `apply_fills_idempotent(state, fills, applied_ids) -> tuple[LiveState, dict[str, str]]`
- [x] 목표 3: `compute_drift(state, closes) -> DriftReport`
- [x] 목표 4: T-8.1 ~ T-8.8 전체 통과

## 2) 비목표

- RTDB 통신 (Step 12)
- CLI 통합 (Step 10)

## 3) 배경/맥락

### 동기

- 사용자가 앱에서 입력한 체결(`ActualFill`) 을 pending_order 와 매칭하여 자동 분류
- idempotency (중복 방지) 로 한 fill 이 두 번 반영되지 않도록
- model vs actual 차이를 `DriftReport` 로 요약 (설계서 14장)

### 설계 결정

#### D1. `classify_fill` 로직

설계서 6.1 그대로:

```python
def classify_fill(fill, state) -> str:
    asset = state.assets.get(fill.asset_id)
    if asset and asset.pending_order:
        pending_is_buy = asset.pending_order["intent_type"] in (
            "ENTER_TO_TARGET", "INCREASE_TO_TARGET"
        )
        fill_is_buy = fill.direction == "buy"
        if pending_is_buy == fill_is_buy:
            return "system_fill"
    return "personal_trade"
```

#### D2. `apply_fills_idempotent` 동작

- 입력 `applied_ids: dict[str, str]` (ID → ISO 타임스탬프)
- `fill.rtdb_key` 가 이미 `applied_ids` 에 있으면 skip
- 없으면 actual 축 갱신:
  - `direction="buy"`: `actual_shares += fill.actual_shares`, `actual_avg_entry_price` 는 가중평균, `actual_entry_date` = fill.trade_date
  - `direction="sell"`: `actual_shares -= fill.actual_shares`. 0 이 되면 entry 초기화.
  - `shared_cash_actual` 을 fill.actual_price × actual_shares 만큼 가감 (slippage 없음, 사용자가 입력한 실제 체결가)
- `applied_ids` 에 `fill.rtdb_key` 추가 (현재 KST 타임스탬프)
- 새 state 와 새 applied_ids 반환 (입력 불변)

#### D3. `compute_drift` 반환

- `model_equity = shared_cash_model + sum(model_shares * close)`
- `actual_equity = shared_cash_actual + sum(actual_shares * close)`
- `drift_pct = abs(actual - model) / model * 100`
- `per_asset` : 자산별 `AssetDrift`
- `recommendation`: "정상" / "주의" / "보정 필요" (설계서 14장 임계값)

## 4) DoD

- [x] `live/src/live/drift.py` 구현
- [x] `live/tests/test_drift.py` 작성 및 통과 (T-8.1 ~ T-8.8)
- [x] QBT 본체 수정 없음
- [x] black + validate_project 통과
- [x] TODO Step 8 체크박스
- [x] plan Done

## 5) 변경 범위

### 수정

- `live/src/live/drift.py` (구현)
- `docs/TODO_QBT_LIVE.md`

### 신규

- `live/tests/test_drift.py`

### README

- 변경 없음

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] `test_drift.py`:
  - T-8.1: classify_fill SSO pending(매수) + SSO 매수 fill → system_fill
  - T-8.2: classify_fill SSO pending(매수) + QLD 매도 fill → personal_trade
  - T-8.3: classify_fill pending 없음 + GLD 매수 fill → personal_trade
  - T-8.4: apply_fills_idempotent 새 fill 반영 → actual 변경
  - T-8.5: apply_fills_idempotent 같은 fill 두 번 → 한 번만 반영
  - T-8.6: compute_drift model=actual → drift 0%
  - T-8.7: compute_drift model≠actual → 올바른 % 계산
  - T-8.8: compute_drift 5% 초과 → recommendation "보정 필요"
  - 추가: apply_fills_idempotent 가 원본 state 를 변경하지 않음 (불변성)
  - 추가: 매도 시 actual_shares 감소 및 0 도달 시 entry 초기화

### Phase 1 — 구현

- [x] `classify_fill`
- [x] `apply_fills_idempotent`
- [x] `compute_drift`
- [x] drift 임계값은 `DRIFT_WARNING_RATIO`, `DRIFT_CORRECTION_RATIO` 사용 (% 로 비교 — 값 그대로 × 100)

### Phase 2 — 문서 동기화

- [x] TODO Step 8 체크박스

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=678, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / fill 자동 매칭 + drift 계산 (Step 8)`
2. `live / drift.py — classify/apply/compute`
3. `live / idempotency + drift 리포트`
4. `live / system_fill/personal_trade 분류 + AssetDrift`
5. `live / Step 8 T-8.1~T-8.8`

## 7) 리스크

- actual_avg_entry_price 가중평균 정확성 — 부분 매수/매도 시나리오 엣지
- 매도 시 현금 갱신 방향 — fill.actual_price × actual_shares (slippage 없음)

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 13:40: 계획서 작성
