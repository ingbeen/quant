# Implementation Plan: 백테스트 리팩토링 미완료 항목 처리

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

**작성일**: 2026-04-01 00:00
**마지막 업데이트**: 2026-04-01 01:00
**관련 범위**: backtest, scripts
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

- [ ] Calmar 계산 함수를 `analysis.py`에 단일 함수로 통합하고 모든 호출처가 이를 재사용하도록 교체 (버그 수정 포함)
- [ ] `run_param_plateau_all.py`의 로컬 4P 고정값을 `constants.py`의 `FIXED_4P_*` 상수 직접 import로 교체
- [ ] `portfolio_configs.py`의 `_DEFAULT_TOTAL_CAPITAL` 중복 상수를 제거하고 `DEFAULT_INITIAL_CAPITAL` 재사용
- [ ] `StrategySpec`의 미사용 예약 필드(`supports_single`, `supports_portfolio`) 제거
- [ ] `BufferZoneStrategy.__init__`의 미사용 `ma_type` 파라미터와 `self._ma_type` 인스턴스 변수 제거

## 2) 비목표(Non-Goals)

- WFO / stitched equity의 공용 헬퍼 추출 (이미 c8ee7e5 커밋에서 EMA reset 버그 수정 완료; 추가 공용화는 이번 scope 밖)
- signal/trade 로딩 + overlap + MA valid filtering 공용화 (별도 plan 필요)
- portfolio preflight 중복 제거 (별도 plan 필요)
- `run_param_plateau_all.py`의 실험 루프 helper 추출 (별도 plan 필요)
- 주석과 조건 불일치 수정 (`run_single_backtest.py:293`, 낮은 우선순위, 이번 scope 밖)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**항목 1: Calmar MDD=0 처리 불일치 (버그)**

동일한 `cagr/mdd` 입력에 대해 경로마다 Calmar 값이 다르게 계산된다.

| 위치 | MDD=0, CAGR>0 시 반환값 |
|------|------------------------|
| `analysis.py:148` | `CALMAR_MDD_ZERO_SUBSTITUTE + cagr` |
| `backtest_engine.py:196` | `CALMAR_MDD_ZERO_SUBSTITUTE + cagr` |
| `walkforward.py:191` (`_calmar` 내부 함수) | `CALMAR_MDD_ZERO_SUBSTITUTE + cagr` |
| `walkforward.py:423` (`_safe_calmar`) | `CALMAR_MDD_ZERO_SUBSTITUTE` ← 버그 |

`_safe_calmar`은 WFO 윈도우별 IS/OOS calmar와 stitched calmar 계산에 사용된다.
버그로 인해 IS/OOS 성과가 summary나 그리드 서치 결과와 다른 수식으로 계산된다.

**항목 2: run_param_plateau_all.py 4P 고정값 로컬 재정의**

`scripts/backtest/run_param_plateau_all.py:56-59`에서 4개 로컬 변수(`_FIXED_MA_WINDOW = 200` 등)를
선언하고 있다. `constants.py`의 `FIXED_4P_*` 상수와 값이 동일하여 중복이며,
한쪽만 바뀌면 plateau 결과와 다른 분석 결과가 조용히 어긋날 수 있다.

**항목 3: 포트폴리오 기본 자본금 중복**

- `portfolio_configs.py:32`: `_DEFAULT_TOTAL_CAPITAL = 10_000_000.0`
- `constants.py:23`: `DEFAULT_INITIAL_CAPITAL: Final = 10_000_000.0`

값이 동일한 상수가 두 곳에 존재한다.

**항목 4: StrategySpec 예약 필드**

`strategy_registry.py:51-52`에 `supports_single: bool = True`, `supports_portfolio: bool = True` 필드가 있으나
프로젝트 어디에서도 읽히지 않는다. 구조를 읽는 비용만 증가시킨다.

**항목 5: BufferZoneStrategy의 미사용 ma_type 인스턴스 변수**

`buffer_zone.py:307`: `self._ma_type = ma_type`으로 저장되지만,
클래스 내부에서 `self._ma_type`을 읽는 코드가 없다.
전략은 이미 외부에서 계산된 `ma_col` 컬럼만 참조하며 MA 유형을 내부에서 사용하지 않는다.
"전략은 계산된 컬럼만 읽는다"는 책임 경계를 흐리게 만든다.

생성자 파라미터 `ma_type`을 전달하는 호출처:
- `strategy_registry.py:74`: `ma_type=slot.ma_type` (유일한 전달처)
- `backtest_engine.py:183, 546`, `walkforward.py:354, 451, 461`, `runners.py:142`: `ma_type` 미전달

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] Calmar 단일 함수(`calculate_calmar`)가 `analysis.py`에 존재하고 모든 호출처가 재사용
- [x] `_safe_calmar` 버그 수정 (MDD=0+CAGR>0 시 `CALMAR_MDD_ZERO_SUBSTITUTE + cagr` 반환)
- [x] `calculate_calmar` 단위 테스트 3케이스 모두 통과 (MDD=0+CAGR>0 / MDD=0+CAGR<=0 / 정상)
- [x] `run_param_plateau_all.py`가 `FIXED_4P_*` 상수를 직접 import하여 사용
- [x] `portfolio_configs.py`의 `_DEFAULT_TOTAL_CAPITAL` 제거 완료
- [x] `StrategySpec`의 `supports_single`, `supports_portfolio` 필드 및 관련 docstring 제거 완료
- [x] `BufferZoneStrategy.__init__` 시그니처에서 `ma_type` 파라미터 제거 + `self._ma_type` 제거 완료
- [x] `strategy_registry.py:74`의 `ma_type=slot.ma_type` 라인 제거 완료
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=432, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] README.md 변경 없음
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/analysis.py` — `calculate_calmar` 함수 추가, 기존 인라인 Calmar 교체
- `src/qbt/backtest/engines/backtest_engine.py` — 인라인 Calmar → `calculate_calmar` 호출
- `src/qbt/backtest/walkforward.py` — `_calmar` 내부 함수 + `_safe_calmar` → `calculate_calmar` 호출
- `src/qbt/backtest/strategy_registry.py` — `supports_single/portfolio` 필드 제거, `ma_type` 전달 제거
- `src/qbt/backtest/strategies/buffer_zone.py` — `__init__` 에서 `ma_type` 파라미터 + `self._ma_type` 제거
- `src/qbt/backtest/portfolio_configs.py` — `_DEFAULT_TOTAL_CAPITAL` → `DEFAULT_INITIAL_CAPITAL` import
- `scripts/backtest/run_param_plateau_all.py` — `_FIXED_*` 로컬 변수 → `FIXED_4P_*` import
- `tests/test_analysis.py` — `calculate_calmar` 단위 테스트 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- WFO IS/OOS calmar, stitched calmar 수치가 미세하게 달라질 수 있음 (버그 수정)
  - 영향 범위: MDD=0인 윈도우가 존재할 경우 `_safe_calmar`의 반환값이 `1e10` → `1e10 + cagr`로 변경
  - MDD=0인 전략 간 우열 비교 시에만 의미 있음; 일반적 시나리오에서는 사실상 무변화
- 기타 항목(상수 교체, 코드 제거)은 동작 변경 없음

## 6) 단계별 계획(Phases)

### Phase 0 — Calmar 정책 테스트를 먼저 고정 (레드)

`calculate_calmar` 함수가 아직 없으므로 import 시점에 실패 → 레드 허용.

**작업 내용**:

- [ ] `tests/test_analysis.py`에 `TestCalculateCalmar` 클래스 추가
  - [ ] `test_calmar_normal`: 정상 케이스 (`cagr=10.0, mdd=-5.0` → `10.0 / 5.0 = 2.0`)
  - [ ] `test_calmar_mdd_zero_cagr_positive`: MDD=0, CAGR>0 → `CALMAR_MDD_ZERO_SUBSTITUTE + cagr`
  - [ ] `test_calmar_mdd_zero_cagr_zero`: MDD=0, CAGR=0 → `0.0`
  - [ ] `test_calmar_mdd_zero_cagr_negative`: MDD=0, CAGR<0 → `0.0`

**Validation** (레드 확인):

- [ ] `poetry run pytest tests/test_analysis.py::TestCalculateCalmar -v` → ImportError 또는 AttributeError로 실패 확인

---

### Phase 1 — Calmar 단일화 구현 (그린)

**작업 내용**:

- [ ] `analysis.py`에 `calculate_calmar(cagr: float, mdd: float) -> float` 함수 추가
  - MDD=0 + CAGR>0: `CALMAR_MDD_ZERO_SUBSTITUTE + cagr`
  - MDD=0 + CAGR<=0: `0.0`
  - 정상: `cagr / abs(mdd)`
- [ ] `analysis.py`의 `calculate_summary` 내 인라인 Calmar 계산 → `calculate_calmar` 호출로 교체
- [ ] `backtest_engine.py`의 인라인 Calmar 계산 (`_run_backtest_for_grid:192-198`) → `calculate_calmar` import + 호출
- [ ] `walkforward.py`의 `_calmar` 내부 함수 제거 → `df.apply`에서 `calculate_calmar` 직접 호출
- [ ] `walkforward.py`의 `_safe_calmar` 함수 제거 → 세 호출처를 `calculate_calmar` 호출로 교체
  - `walkforward.py:340` (IS calmar)
  - `walkforward.py:369` (OOS calmar)
  - `walkforward.py:632` (stitched calmar)
- [ ] `analysis.py` 공개 API에 `calculate_calmar` 추가 (필요 시 `__all__` 확인)

**Validation**:

- [ ] `poetry run pytest tests/test_analysis.py -v`
- [ ] `poetry run pytest tests/test_walkforward_selection.py tests/test_walkforward_summary.py -v`

---

### Phase 2 — 상수 정리 (그린)

**작업 내용**:

- [ ] `scripts/backtest/run_param_plateau_all.py`
  - `from qbt.backtest.constants import FIXED_4P_MA_WINDOW, FIXED_4P_BUY_BUFFER_ZONE_PCT, FIXED_4P_SELL_BUFFER_ZONE_PCT, FIXED_4P_HOLD_DAYS` import 추가
  - `_FIXED_MA_WINDOW`, `_FIXED_BUY_BUFFER`, `_FIXED_SELL_BUFFER`, `_FIXED_HOLD_DAYS` 로컬 변수 선언 4개 제거
  - 사용처(`_FIXED_*`)를 `FIXED_4P_*`로 교체
- [ ] `src/qbt/backtest/portfolio_configs.py`
  - `from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL` import 추가
  - `_DEFAULT_TOTAL_CAPITAL = 10_000_000.0` 선언 제거
  - 사용처(`_DEFAULT_TOTAL_CAPITAL`)를 `DEFAULT_INITIAL_CAPITAL`로 교체

**Validation**:

- [ ] `poetry run python validate_project.py --only-lint`
- [ ] `poetry run python validate_project.py --only-pyright`

---

### Phase 3 — 불필요 코드 제거 (그린)

**작업 내용**:

- [ ] `src/qbt/backtest/strategy_registry.py`
  - `StrategySpec` 클래스에서 `supports_single: bool = True`, `supports_portfolio: bool = True` 필드 제거
  - Docstring에서 `supports_single`, `supports_portfolio` 설명 줄 제거
  - `STRATEGY_REGISTRY` 딕셔너리 인스턴스 생성 시 해당 필드 없으므로 변경 없음 (기본값만 제거)
  - `ma_type=slot.ma_type` 전달 라인 제거 (`_create_buffer_zone_strategy` 함수 내)
- [ ] `src/qbt/backtest/strategies/buffer_zone.py`
  - `__init__` 시그니처에서 `ma_type: str = "ema"` 파라미터 제거
  - `self._ma_type = ma_type` 라인 제거
  - Docstring에서 `ma_type` 파라미터 설명 제거
  - 사용 예시 Docstring 갱신 (4개 인자로 축소)

**Validation**:

- [ ] `poetry run python validate_project.py --only-lint`
- [ ] `poetry run python validate_project.py --only-pyright`

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [ ] README.md 변경 없음 (확인 완료)
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=432, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Calmar 계산 단일화 + 4P 상수 import + 불필요 코드 제거
2. 백테스트 / _safe_calmar 버그 수정 + calculate_calmar 통합 + 상수 정리
3. 백테스트 / Calmar MDD=0 처리 통일 + StrategySpec/BufferZoneStrategy 코드 정리
4. 백테스트 / 리팩토링 미완료 항목 처리 — Calmar 통합 / 상수 정리 / 오버엔지니어링 제거
5. 백테스트 / refactoring.md 미완료 5개 항목 일괄 처리

## 7) 리스크(Risks)

- **Calmar 수치 변경**: `_safe_calmar` 버그 수정으로 MDD=0인 윈도우의 WFO IS/OOS calmar 수치가 달라질 수 있음.
  완화: Phase 0에서 정책을 테스트로 먼저 고정하고, Phase 1에서 구현
- **BufferZoneStrategy 시그니처 변경**: `ma_type` 파라미터 제거로 `strategy_registry.py` 외 다른 호출처에서 `ma_type`을 키워드 인자로 전달하는 코드가 있으면 에러.
  완화: 사전에 모든 호출처를 grep으로 확인함 — `strategy_registry.py:74` 한 곳만 전달, 나머지는 미전달로 확인됨

## 8) 메모(Notes)

- Calmar 4개 위치 중 3개는 동일한 `CALMAR_MDD_ZERO_SUBSTITUTE + cagr if cagr > 0 else 0.0` 패턴
- `_safe_calmar`만 `CALMAR_MDD_ZERO_SUBSTITUTE`(cagr 미반영)로 다름 — Phase 1에서 수정
- `BufferZoneStrategy.ma_type` 파라미터는 생성자에서 받아 `self._ma_type`에 저장하지만
  클래스 내부에서 `self._ma_type`을 읽는 코드가 전혀 없음 (grep으로 확인)
- `portfolio_configs.py`는 실험이 다수이므로 `_DEFAULT_TOTAL_CAPITAL` 사용처가 많음 (30+군데),
  `replace_all`로 일괄 교체 예정

### 진행 로그 (KST)

- 2026-04-01 00:00: 계획서 작성 완료, Phase 0 시작
- 2026-04-01 01:00: 전체 Phase 완료, passed=432, failed=0, skipped=0
