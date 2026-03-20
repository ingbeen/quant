# Implementation Plan: 포트폴리오 실험 E/F/G/H 시리즈 추가

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

**작성일**: 2026-03-20 00:00
**마지막 업데이트**: 2026-03-20 01:30
**관련 범위**: backtest, scripts
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

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

- [x] E 시리즈 5개 실험 추가 (E-1~E-5: SPY + GLD + TLT, 레버리지 없음)
- [x] F 시리즈 4개 실험 추가 (F-1~F-4: SPY + TQQQ + GLD + TLT, 레버리지 혼합)
- [x] H 시리즈 3개 실험 추가 (H-1~H-3: TQQQ 60% + 방어 자산)
- [x] G 시리즈 4개 실험 추가 (G-1~G-4: SPY/GLD/TLT, 버퍼존 vs B&H 팩토리얼)
- [x] `AssetSlotConfig.always_invested` 필드 추가 (G 시리즈 B&H 처리)
- [x] `portfolio_strategy.py`에 `always_invested` 처리 로직 추가
- [x] 기존 9개 실험 동작 불변 보장

## 2) 비목표(Non-Goals)

- 기존 A/B/C/D 시리즈 실험 수정
- 대시보드(`app_portfolio_backtest.py`) 수정 (자동 탐색으로 신규 실험 자동 표출)
- G 시리즈 비교 해설 추가 (추후 대시보드 업데이트에서 처리)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 기존 A/B/C/D 시리즈 9개 실험만 구현됨
- TLT 포함 조합, 레버리지 혼합 조합, TQQQ 60% 집중 조합 등 추가 실험 필요
- G 시리즈: GLD/TLT에 버퍼존 vs B&H 각각 적용하여 전략 기여도 격리
  - 현재 엔진이 전 자산에 버퍼존만 강제 적용하므로 `always_invested` 필드 추가 필요

### always_invested 설계 결정

- `AssetSlotConfig.always_invested: bool = False` 추가
- `always_invested=True` 자산의 동작:
  1. 초기 진입: day 0에 buy pending_order 생성 (capital = total_capital × target_weight)
  2. 매도 신호 무시: 버퍼존 하향 돌파에도 매도하지 않음 (항상 투자 상태 유지)
  3. 리밸런싱 참여: 월 첫 거래일 리밸런싱에는 정상 참여 (signal_state="buy" 유지)
- `G-1`: 모든 자산 `always_invested=False` (E-1과 동일 구성, 별도 결과 디렉토리)
- `G-2`: GLD만 `always_invested=True`
- `G-3`: TLT만 `always_invested=True`
- `G-4`: GLD+TLT 모두 `always_invested=True`

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- 루트 `CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] E/F/H 시리즈 12개 실험 config 추가 및 PORTFOLIO_CONFIGS 등록
- [x] G 시리즈 4개 실험 config 추가 및 PORTFOLIO_CONFIGS 등록
- [x] `AssetSlotConfig.always_invested: bool = False` 추가 + 기존 코드 호환성 유지
- [x] `portfolio_strategy.py` always_invested 처리 로직 구현
- [x] always_invested 관련 테스트 추가 (초기 진입, 매도 무시, 리밸런싱 참여)
- [x] `run_portfolio_backtest.py` docstring 업데이트 (9개→25개)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; 수 기록 필요)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/portfolio_types.py` — AssetSlotConfig.always_invested 추가
- `src/qbt/backtest/portfolio_strategy.py` — always_invested 처리 로직
- `src/qbt/backtest/portfolio_configs.py` — E/F/G/H 시리즈 16개 config 추가
- `scripts/backtest/run_portfolio_backtest.py` — docstring 업데이트
- `tests/test_portfolio_strategy.py` (신규) — always_invested 테스트

### 데이터/결과 영향

- 신규 실험 결과는 `storage/results/portfolio/{experiment_name}/`에 저장
- 기존 실험 결과 변경 없음 (기존 configs 수정 없음)
- `AssetSlotConfig` frozen dataclass에 `always_invested` 필드 추가 → 기존 인스턴스는 기본값 `False` 사용 (호환)

## 6) 단계별 계획(Phases)

### Phase 1 — E/F/H 시리즈 추가 (엔진 수정 없음)

**작업 내용**:

- [x] `portfolio_configs.py`: TLT_DATA_PATH import 추가
- [x] `portfolio_configs.py`: E-1~E-5, F-1~F-4, H-1~H-3 config 정의 (12개)
- [x] `portfolio_configs.py`: PORTFOLIO_CONFIGS 리스트에 12개 추가
- [x] `run_portfolio_backtest.py`: docstring 업데이트 (9개→25개)

---

### Phase 2 — G 시리즈 추가 (always_invested 엔진 변경)

**작업 내용**:

- [x] `portfolio_types.py`: `AssetSlotConfig.always_invested: bool = False` 추가
- [x] `portfolio_strategy.py`:
  - 초기 상태 설정: always_invested=True 자산의 signal_state를 "buy"로 초기화
  - day 0에 buy pending_order 생성 (capital = total_capital × target_weight)
  - 시그널 루프: always_invested=True 자산은 매도 신호 무시 (signal_state "buy" 유지)
  - params_json: always_invested 필드 포함
- [x] `portfolio_configs.py`: G-1~G-4 config 정의 (4개) + PORTFOLIO_CONFIGS 등록
- [x] `tests/test_portfolio_strategy.py` (신규): always_invested 관련 테스트 추가
  - always_invested=True 자산이 즉시 매수됨 (day 1에 포지션 보유)
  - always_invested=True 자산이 매도 신호에도 매도하지 않음
  - always_invested=False 자산은 기존 동작 그대로

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=386, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 포트폴리오 / E/F/G/H 시리즈 16개 실험 추가 + always_invested 엔진 구현
2. 포트폴리오 / 25개 실험 체계 완성 (E/F/G/H 시리즈 + always_invested B&H 처리)
3. 백테스트 / 포트폴리오 실험 9개→25개 확장 + G시리즈 always_invested 팩토리얼
4. 포트폴리오 / TLT 포함 조합 + 레버리지 혼합 + B&H 기여도 격리 실험 추가
5. 포트폴리오 / AssetSlotConfig.always_invested 추가 + E/F/G/H 시리즈 구현

## 7) 리스크(Risks)

- `always_invested` 초기 매수 자본 계산: `total_capital × target_weight`로 고정하면 여러 자산이 동시에 매수될 때 shared_cash가 부족할 수 있음. → 가용 현금 내에서 target_weight 비례로 매수하는 방식 채택
- G-1 결과가 E-1과 동일: 의도된 설계이나 중복 실행 비용 발생 → 허용 (G 시리즈 비교 기준선 역할)
- `AssetSlotConfig` frozen dataclass 변경: 기존 인스턴스는 `always_invested=False` 기본값 사용, 호환성 유지

## 8) 메모(Notes)

- TLT_DATA_PATH: `common_constants.py`에 이미 존재 확인 (`STOCK_DIR / "TLT_max.csv"`)
- 실행 권장 순서(사용자 문서 기준): H → E → F → G
- G-1과 E-1은 동일 구성(SPY 60% / GLD 25% / TLT 15%, 전부 버퍼존)이나 별도 결과 디렉토리 사용

### 진행 로그 (KST)

- 2026-03-20 00:00: 계획서 초안 작성 완료
- 2026-03-20 01:30: 버그 수정 (portfolio_strategy.py first_trade_date NameError) + 임포트 정렬 수정 + 테스트 카운트 업데이트 + validate 통과 (passed=386, failed=0, skipped=0)
