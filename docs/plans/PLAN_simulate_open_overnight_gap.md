# Implementation Plan: simulate() Open 가격 오버나이트 갭 반영

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

**작성일**: 2026-02-16 16:46
**마지막 업데이트**: 2026-02-16 17:05
**관련 범위**: tqqq, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `simulate()` 함수의 Open을 기초 자산의 오버나이트 갭 × 레버리지로 계산하여 현실성 향상
- [x] Open을 `simulate()`의 필수 입력 컬럼으로 승격 (Date, Open, Close 필수)
- [x] 기존 Close 계산 로직은 일절 변경하지 않음

## 2) 비목표(Non-Goals)

- High, Low 시뮬레이션 개선 (현재 0.0 유지)
- Close 가격 계산 로직 변경
- 비용 모델 (funding spread, expense ratio) 변경
- 벡터화 시뮬레이션 경로의 Open 반영 (Close만 다루므로 무관)
- Open 미포함 시 폴백 동작 (프로덕션 코드에서 Open 없는 호출처 없음)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 `simulate()` 함수는 합성 데이터의 Open을 단순히 전일 Close로 설정한다 (`simulation.py:843`):

```python
df[COL_OPEN] = df[COL_CLOSE].shift(1).fillna(initial_price)
```

실제 시장에서는 장 마감과 다음 날 장 시작 사이에 **오버나이트 갭(overnight gap)**이 존재한다.
QQQ 실제 데이터를 보면 시가(Open)와 전일 종가(Close)가 다르다:

| 날짜 | QQQ 전일 Close | QQQ Open | 갭 |
|------|--------------|----------|-----|
| 1999-03-11 | 43.129 | 43.445 | +0.73% |
| 1999-03-12 | 43.340 | 43.181 | -0.37% |

합성 TQQQ의 Open에 이 오버나이트 갭을 레버리지 배율로 반영하면 현실성이 향상된다.

### 핵심 수식

```
QQQ 오버나이트 수익률(t) = QQQ_Open(t) / QQQ_Close(t-1) - 1
TQQQ_Open(t) = TQQQ_Close(t-1) × (1 + QQQ 오버나이트 수익률(t) × leverage)
```

- **비용 배분 없음**: 일일 비용은 이미 Close-to-Close 수익률에 전액 반영되어 있으므로, 오버나이트 구간에 별도 비용을 적용하지 않는다.
- **Close 불변**: Close 계산은 기존과 완전히 동일하다. Open 변경은 Close에 영향을 주지 않는다.
- **자기 일관성**: `(TQQQ_Open(t)/TQQQ_Close(t-1)) × (TQQQ_Close(t)/TQQQ_Open(t)) = TQQQ_Close(t)/TQQQ_Close(t-1)` 항등식이 성립한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `simulate()` 필수 컬럼에 Open 추가 (Date, Open, Close)
- [x] 오버나이트 갭 기반 Open 계산 구현
- [x] Close 계산 로직 변경 없음 확인
- [x] 기존 테스트에 Open 컬럼 추가 (프로덕션 데이터와 일치)
- [x] 오버나이트 갭 Open 전용 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=275, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/tqqq/simulation.py`: `simulate()` 필수 컬럼 확장 + Open 계산 로직 변경
- `tests/test_tqqq_simulation.py`: 기존 테스트에 Open 추가 + 오버나이트 갭 테스트 신규
- `tests/test_integration.py`: 기존 테스트 데이터가 이미 Open 포함 → 변경 없음 (확인만)

### 데이터/결과 영향

- `TQQQ_synthetic_max.csv`: 합성 구간(1999~2010)의 Open 값이 변경됨 (Close 불변)
- CSV 재생성은 plan 범위에 포함하지 않음 (사용자가 스크립트 재실행으로 수행)

## 6) 단계별 계획(Phases)

### Phase 0 — 오버나이트 갭 Open 정책 테스트 (레드)

**작업 내용**:

- [x] `tests/test_tqqq_simulation.py`에 `TestSimulateOvernightOpen` 클래스 추가
- [x] 테스트 1: `test_open_reflects_overnight_gap` — 오버나이트 갭이 레버리지 배율로 반영되는지 확인
- [x] 테스트 2: `test_first_day_open_equals_initial_price` — 첫날 Open = initial_price 확인
- [x] 테스트 3: `test_close_unchanged_after_open_improvement` — Close가 기존 로직과 동일함을 확인
- [x] 테스트 4: `test_open_required_column` — Open 컬럼 누락 시 ValueError 발생 확인

---

### Phase 1 — simulate() Open 계산 로직 구현 + 기존 테스트 보정 (그린 유지)

**작업 내용**:

#### 1-1. `simulate()` 필수 컬럼에 Open 추가

- [x] `simulation.py:763` — `required_cols`에 `COL_OPEN` 추가

#### 1-2. 기초 자산 Open 보존 및 df 생성 변경

- [x] `simulation.py:797` — df 생성 시 Open 포함

#### 1-3. 기초 자산 Close 보존 + Open 계산 변경

- [x] `simulation.py:838~843` — 기초 자산 Close 보존 후 오버나이트 갭 기반 Open 계산
  ```python
  # leveraged_prices 계산 완료 후, Close 덮어쓰기 전에 기초 자산 Close 보존
  underlying_close_series = df[COL_CLOSE].copy()

  # 시뮬레이션 Close로 덮어쓰기 (기존 코드)
  df[COL_CLOSE] = leveraged_prices

  # 변경 전
  # df[COL_OPEN] = df[COL_CLOSE].shift(1).fillna(initial_price)

  # 변경 후: 오버나이트 갭 기반 Open 계산
  # 기초 자산의 오버나이트 수익률: QQQ_Open(t) / QQQ_Close(t-1) - 1
  underlying_overnight_return = df[COL_OPEN] / underlying_close_series.shift(1) - 1
  # 시뮬레이션 Open: TQQQ_Close(t-1) × (1 + 오버나이트수익률 × leverage)
  leveraged_open = df[COL_CLOSE].shift(1) * (1 + underlying_overnight_return * leverage)
  # 첫날은 initial_price (shift(1)로 NaN 발생 → fillna)
  df[COL_OPEN] = leveraged_open.fillna(initial_price)
  ```

#### 1-4. 기존 테스트에 Open 컬럼 추가

- [x] `TestSimulate.test_normal_simulation` — underlying_df에 Open 추가
- [x] `TestSimulate.test_leverage_effect` — underlying_df에 Open 추가
- [x] `TestSimulate.test_invalid_leverage` — underlying_df에 Open 추가
- [x] `TestSimulateValidation.test_invalid_numeric_params_raise` — underlying_df에 Open 추가
- [x] `TestSimulateValidation.test_missing_required_columns_raises` — Open 누락은 TestSimulateOvernightOpen.test_open_required_column에서 커버
- [x] `TestSimulateValidation.test_empty_dataframe_raises` — columns에 Open 추가
- [x] `TestVectorizedSimulation._create_test_data` — underlying_df에 Open 추가
- [x] `TestCalculateStitchedWalkforwardRmse`, `TestCalculateFixedAbStitchedRmse`, `TestRunWalkforwardValidation` fixture — Open 추가 완료
- [x] Phase 0 테스트 전부 통과 확인

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=275, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / simulate() Open 가격에 기초 자산 오버나이트 갭 반영
2. TQQQ시뮬레이션 / 합성 Open 가격 현실성 향상 (오버나이트 갭 레버리지 적용)
3. TQQQ시뮬레이션 / 기초 자산 시가 기반 오버나이트 갭 Open 계산 추가
4. TQQQ시뮬레이션 / Open 가격 시뮬레이션 개선 및 필수 컬럼 승격
5. TQQQ시뮬레이션 / simulate() 오버나이트 갭 Open 반영 및 테스트 추가

## 7) 리스크(Risks)

- **기초 자산 Close 덮어쓰기**: `simulate()` 내부에서 `df[COL_CLOSE]`를 시뮬레이션 값으로 덮어쓰므로, 기초 자산 원본 Close를 별도 보존해야 한다. 미보존 시 오버나이트 수익률 계산이 잘못됨.
  - 완화: `underlying_close_series = df[COL_CLOSE].copy()`로 덮어쓰기 전 보존
- **기존 테스트 회귀**: Open을 필수 컬럼으로 승격하면 Open 없이 호출하던 기존 테스트가 깨짐.
  - 완화: Phase 1에서 모든 기존 테스트의 underlying_df에 Open 추가

## 8) 메모(Notes)

- 비용 배분: 오버나이트 구간에 별도 비용을 적용하지 않는다. 일일 비용은 Close-to-Close에 이미 전액 반영되어 있고, Open은 순수하게 기초 자산의 가격 갭만 레버리지로 확대한다.
- High/Low는 현재 0.0으로 유지 (Non-Goal)

### 진행 로그 (KST)

- 2026-02-16 16:46: 계획서 초안 작성
- 2026-02-16 17:05: 전체 구현 완료, validate_project.py 통과 (passed=275, failed=0, skipped=0)
