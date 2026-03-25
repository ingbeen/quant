# Implementation Plan: 포트폴리오 구조 정리 — 죽은 설정·상수 제거 + 가독성·확장성 개선

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

**작성일**: 2026-03-25 00:00
**마지막 업데이트**: 2026-03-25 00:00
**관련 범위**: backtest, scripts
**관련 문서**:
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [ ] `rebalance_threshold_rate` 설정 필드 제거 — 설정 정의와 런타임 동작을 일치시킨다
- [ ] 분할 매수매도 전략 잔재 상수 제거 — 코드베이스에 "존재하지 않는 전략"의 상수가 남아 있지 않게 한다
- [ ] `signal_state` 타입 강화 — `str`에서 `Literal["buy", "sell"]`로 명시화한다
- [ ] 포트폴리오 엔진 주석 개선 — 각 단계가 "왜" 필요한지 설명한다
- [ ] UI 색상 처리 일반화 — 실험 구성이 늘어나도 의도하지 않은 fallback이 발생하지 않도록 한다

## 2) 비목표(Non-Goals)

- 단일 백테스트(`backtest_engine.py`) 로직 변경 (포트폴리오 전용 변경)
- `run_portfolio_backtest` 함수 분리 (현재 헬퍼 함수 분리 구조로 충분)
- 리밸런싱 임계값을 실험별로 다르게 설정하는 기능 추가
- E/F/G/H 시리즈 이외의 신규 실험 추가
- 포트폴리오 엔진 핵심 로직(리밸런싱 판정, 2패스 체결) 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1: `rebalance_threshold_rate` — 설정값이 런타임에서 무시됨**

`PortfolioConfig.rebalance_threshold_rate`는 설정 구조에서 중요한 파라미터처럼 보이지만,
`run_portfolio_backtest`에서 `_check_rebalancing_needed` 호출 시 항상 모듈 레벨 상수
(`MONTHLY_REBALANCE_THRESHOLD_RATE`, `DAILY_REBALANCE_THRESHOLD_RATE`)를 명시적으로 전달한다.
`_check_rebalancing_needed`의 `threshold=None` fallback 경로는 데드 코드다.

결과: 사용자가 `rebalance_threshold_rate`를 바꿔도 실제 동작이 달라지지 않는다.
단, `params_json`에 기록되어 있어 혼동을 유발한다.

**문제 2: 분할 매수매도 잔재 상수**

`docs/archive/backtest_removed_modules.md`에 "이 상수들도 함께 삭제됨"이라 기록했지만
실제 코드에 남아 있음:
- `common_constants.py`: `SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR`, `SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR`
- `constants.py`: `SPLIT_TRANCHE_MA_WINDOWS`, `SPLIT_TRANCHE_WEIGHTS`, `SPLIT_TRANCHE_IDS`
  + "단일 백테스트 활성 전략 필터" 섹션 주석이 두 번 중복됨

코드 전체에서 이 상수들을 참조하는 곳이 없음 (정의만 남아 있음).

**문제 3: `signal_state` — `str` 타입으로 선언됨**

`_AssetState.signal_state: str`이 `"buy"/"sell"` 중 하나여야 한다는 제약이
타입 힌트에 드러나지 않는다. `Literal["buy", "sell"]`로 강화하면 PyRight가
잘못된 값을 조기에 감지할 수 있다.

**문제 4: UI 색상 — E/F/G/H 시리즈 미등록**

`app_portfolio_backtest.py`의 `_EXPERIMENT_COLORS`에는 A/B/C/D 실험 색상만 있다.
현재 `PORTFOLIO_CONFIGS`는 E/F/G/H 시리즈를 포함하므로, 이 실험들은
`_EXPERIMENT_COLOR_FALLBACK = "#888888"`(회색)으로 표시된다.

또한 `_ASSET_COLORS`에 `tlt`, `iwm`, `efa`, `eem` 자산이 없어서
이 자산들이 fallback 색상으로 표시된다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) — 포트폴리오 도메인 규칙
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md) — CLI/대시보드 규칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙
- [루트 CLAUDE.md](../../CLAUDE.md) — 공통 규칙 (상수 관리, 코딩 표준 등)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] `rebalance_threshold_rate` 필드가 `PortfolioConfig`에서 제거됨
- [ ] 모든 `PortfolioConfig` 인스턴스에서 `rebalance_threshold_rate` 인자 제거됨
- [ ] `params_json`에 `monthly_rebalance_threshold_rate` / `daily_rebalance_threshold_rate` 상수값이 명시적으로 기록됨
- [ ] `SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR`, `SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR` 제거됨
- [ ] `SPLIT_TRANCHE_MA_WINDOWS`, `SPLIT_TRANCHE_WEIGHTS`, `SPLIT_TRANCHE_IDS` 제거됨
- [ ] `constants.py` 중복 섹션 주석 정리됨
- [ ] `_AssetState.signal_state` 타입이 `Literal["buy", "sell"]`로 강화됨
- [ ] E/F/G/H 시리즈 실험 색상 및 누락 자산 색상 추가됨
- [ ] 관련 테스트가 변경 사항을 반영하도록 업데이트됨
- [ ] 회귀/신규 테스트 추가 (필요 시)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

**비즈니스 로직**:
- `src/qbt/backtest/portfolio_types.py` — `PortfolioConfig.rebalance_threshold_rate` 필드 제거
- `src/qbt/backtest/portfolio_configs.py` — `_DEFAULT_REBALANCE_THRESHOLD` 로컬 상수 + 모든 config 인자 제거
- `src/qbt/backtest/engines/portfolio_engine.py` — 4가지 변경:
  1. `_check_rebalancing_needed`: `threshold` 파라미터를 필수(non-optional)로 변경, fallback 경로 제거
  2. `params_json`: `rebalance_threshold_rate` 제거 → `monthly_rebalance_threshold_rate` / `daily_rebalance_threshold_rate` 상수값 추가
  3. `_AssetState.signal_state: str` → `Literal["buy", "sell"]`
  4. 메인 루프 단계 주석 개선 ("왜"로 변경)
- `src/qbt/common_constants.py` — `SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR`, `SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR` 제거
- `src/qbt/backtest/constants.py` — `SPLIT_TRANCHE_*` 3개 상수 + 중복 섹션 주석 제거

**스크립트**:
- `scripts/backtest/app_portfolio_backtest.py` — `_EXPERIMENT_COLORS` E/F/G/H 추가, `_ASSET_COLORS` 누락 자산 추가

**테스트**:
- `tests/test_portfolio_configs.py` — `rebalance_threshold_rate` 관련 항목 정리 (현재 직접 테스트 없음, 영향 확인)
- `tests/test_portfolio_strategy.py` — `rebalance_threshold_rate` 관련 항목 정리

### 데이터/결과 영향

- `params_json` 키 변경: `rebalance_threshold_rate` → `monthly_rebalance_threshold_rate` / `daily_rebalance_threshold_rate`
  - 기존 실행 결과 `summary.json`의 스키마가 변경됨
  - 새로 `run_portfolio_backtest.py`를 실행하면 새 스키마로 저장됨
  - 대시보드는 `summary.json`에서 `rebalance_threshold_rate`를 표시하지 않으므로 UI 영향 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 구조 변경: 죽은 설정·상수 제거 + 타입 강화 (그린 유지)

**작업 내용**:

- [ ] `portfolio_types.py`: `PortfolioConfig`에서 `rebalance_threshold_rate: float` 필드 제거
  - docstring에서 해당 필드 설명 제거
  - `PortfolioResult.config` 기본값 생성자에서도 `rebalance_threshold_rate` 제거
- [ ] `portfolio_configs.py`:
  - `_DEFAULT_REBALANCE_THRESHOLD = 0.10` 로컬 상수 제거
  - 모든 `PortfolioConfig(...)` 인스턴스에서 `rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD` 인자 제거
- [ ] `portfolio_engine.py` — `rebalance_threshold_rate` 관련:
  - `_check_rebalancing_needed` 시그니처: `threshold: float | None = None` → `threshold: float`
    (fallback 로직 제거, 호출자가 항상 명시적으로 전달하도록 강제)
  - `params_json`에서 `"rebalance_threshold_rate": config.rebalance_threshold_rate` 제거
  - `params_json`에 `"monthly_rebalance_threshold_rate": MONTHLY_REBALANCE_THRESHOLD_RATE` 추가
  - `params_json`에 `"daily_rebalance_threshold_rate": DAILY_REBALANCE_THRESHOLD_RATE` 추가
- [ ] `portfolio_engine.py` — `signal_state` 타입 강화:
  - `from typing import Literal` import 추가 (이미 있으면 생략)
  - `_AssetState.signal_state: str` → `signal_state: Literal["buy", "sell"]`
  - 초기화 시 `signal_state="sell"` 유지 (값은 동일, 타입만 강화)
- [ ] `common_constants.py`:
  - `SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR` 제거
  - `SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR` 제거
  - "분할 매수매도 전략 결과 디렉토리" 주석 제거
- [ ] `constants.py`:
  - `SPLIT_TRANCHE_MA_WINDOWS`, `SPLIT_TRANCHE_WEIGHTS`, `SPLIT_TRANCHE_IDS` 3개 상수 제거
  - "분할 매수매도 트랜치 설정" 섹션 주석 블록(라인 116-125) 제거
  - 중복된 "단일 백테스트 활성 전략 필터" 섹션 구분선 정리 (하나만 유지)
- [ ] `test_portfolio_configs.py`: 변경 후 테스트 통과 여부 확인 (직접 `rebalance_threshold_rate` 검증 없으므로 config 생성 테스트만 확인)
- [ ] `test_portfolio_strategy.py`: `rebalance_threshold_rate` 관련 항목 확인 및 정리

---

### Phase 2 — 가독성·확장성 개선 (그린 유지)

**작업 내용**:

- [ ] `portfolio_engine.py` — 메인 루프 주석 개선:
  - `# 7-1. pending_order 체결 ... — 2패스 방식`: "매도를 먼저 처리해야 그 대금을 같은 날 매수 자본으로 사용할 수 있다"
  - `# 1패스: 전 자산 sell pending_order 먼저 체결`: "매도 대금을 shared_cash에 먼저 합산"
  - `# 2패스: 전 자산 buy pending_order 체결`: "매도 완료 후 확보된 현금으로 매수 진행"
  - `# 7-2. 에쿼티 계산`: "체결 완료 후 당일 종가 기준으로 에쿼티를 계산한다 (종가는 당일에만 사용)"
  - `# 7-3. 시그널 판정`: "종가 기반 시그널은 i+1일 시가에 체결된다 (lookahead 방지)"
  - `# 7-4. 이중 트리거 리밸런싱 판정`: "월 첫날(10%)은 정기 리밸런싱, 매일(20%)은 급격한 편차에 대한 긴급 리밸런싱"
  - `_check_rebalancing_needed` docstring에서 `threshold` 파라미터 설명 갱신 (fallback 문구 제거)
- [ ] `app_portfolio_backtest.py` — 색상 처리 확장:
  - `_EXPERIMENT_COLORS`에 E/F/G/H 시리즈 색상 추가:
    - E 시리즈: 보라색 계열 5개 (e1~e5)
    - F 시리즈: 청록색 계열 4개 (f1~f4)
    - G 시리즈: 갈색/베이지 계열 4개 (g1~g4)
    - H 시리즈: 분홍색 계열 3개 (h1~h3)
  - `_ASSET_COLORS`에 누락 자산 추가: `"tlt"`, `"iwm"`, `"efa"`, `"eem"`

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - `portfolio_types.py` 섹션에서 `rebalance_threshold_rate` 설명 제거
  - `portfolio_engine.py` 섹션에서 `_check_rebalancing_needed` 파라미터 설명 갱신
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 구조 정리 — 죽은 설정·상수 제거 + 타입·가독성 개선
2. 백테스트 / rebalance_threshold_rate 제거 + Split 잔재 상수 정리 + signal_state Literal 강화
3. 백테스트 / 설정-동작 불일치 해소 + 폐기 모듈 상수 완전 제거
4. 백테스트 / 구조 정리(동작 동일) — 죽은 필드/상수 제거 + UI 색상 확장
5. 백테스트 / 포트폴리오 코드 정합성 복원 — 아카이브 문서와 실제 코드 동기화

## 7) 리스크(Risks)

- **`rebalance_threshold_rate` 필드 제거 → frozen dataclass 하위 호환성**:
  `PortfolioConfig`에서 `rebalance_threshold_rate` 인자를 전달하는 코드가 남아 있으면
  TypeError가 발생한다. 참조 전수 확인 필요.
- **`_check_rebalancing_needed` 시그니처 변경**:
  `threshold=None`으로 호출하는 외부 코드(테스트 포함)가 있으면 TypeError.
  테스트에서 이 함수를 직접 호출하는 케이스 확인 필요.
- **`SPLIT_BUFFER_ZONE_*` 상수 제거**:
  grep 결과 참조 없음으로 확인했지만, 혹시 동적 참조(`getattr`, 문자열 포맷팅)가 있으면 런타임 오류.
  정적 분석(PyRight)으로 검출되지 않을 수 있으므로 주의.

## 8) 메모(Notes)

### 결정 사항

- **`rebalance_threshold_rate` 처리**: B안 (필드 제거). 모든 실험이 동일한 0.10을 사용하며,
  설정값이 실제로 런타임에 사용되지 않아 "설정을 바꿔도 동작이 달라지지 않는" 상태가 정확성 문제.
  `params_json`에는 두 모듈 상수값을 명시적으로 기록하여 실제 동작 파라미터를 추적 가능하게 함.
- **`signal_state` 타입**: A안 (`Literal` 강화만). enum 생성 없이 타입 힌트만 강화.
  포트폴리오 엔진 전용이므로 싱글 백테스트에 영향 없음.
- **함수 분리**: 현재 헬퍼 함수 분리 구조가 충분하므로 추가 분리 없음. 주석 개선으로 가독성 확보.

### 확인이 필요한 사항

- `test_portfolio_strategy.py`에서 `_check_rebalancing_needed`를 `threshold=None`으로 직접 호출하는지 확인
- `PortfolioConfig` 인스턴스를 생성하는 곳이 `portfolio_configs.py`와 테스트 이외에 있는지 확인

### 진행 로그 (KST)

- 2026-03-25 00:00: 계획서 작성 완료
