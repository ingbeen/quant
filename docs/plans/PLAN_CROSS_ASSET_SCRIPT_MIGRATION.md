# Implementation Plan: 교차 자산 스크립트 마이그레이션 + 문서 정리

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-07 15:00
**마지막 업데이트**: 2026-03-07 16:30
**관련 범위**: scripts, backtest, tests, docs
**관련 문서**: cross_asset_validation_plan.md (§9 구현 방안), PLAN_BUFFER_ZONE_UNIFIED_MODULE.md

**선행 조건**: `PLAN_BUFFER_ZONE_UNIFIED_MODULE` 완료 (buffer_zone.py 통합 모듈 존재)

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

- [x] 모든 스크립트를 `buffer_zone.py` 통합 모듈로 마이그레이션
- [x] `run_single_backtest.py`에 cross-asset 전략 레지스트리 자동 등록 + regime_summaries 분기 추가
- [x] 기존 모듈(`buffer_zone_tqqq.py`, `buffer_zone_qqq.py`) 삭제
- [x] 기존 테스트(`test_buffer_zone_tqqq.py`, `test_buffer_zone_qqq.py`) → `test_buffer_zone.py`로 통합
- [x] CLAUDE.md 문서 업데이트 (루트, backtest 도메인, scripts)

## 2) 비목표(Non-Goals)

- `buffer_zone_helpers.py` 핵심 로직 변경
- `buffer_zone_atr_tqqq.py` 변경 (ATR 전용, 독립 유지)
- `donchian_channel_tqqq.py` 변경 (독립 프레임워크)
- 대시보드(`app_single_backtest.py`) 코드 수정 (Feature Detection 기반, 자동 호환)
- 데이터 다운로드 (사용자가 직접 실행)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `PLAN_BUFFER_ZONE_UNIFIED_MODULE` 완료 후 상태:
  - `buffer_zone.py` 통합 모듈 존재 (9개 CONFIGS)
  - `buffer_zone_tqqq.py`, `buffer_zone_qqq.py` 원본 모듈도 병존 (코드 중복)
  - 스크립트가 여전히 기존 개별 모듈을 직접 import
- 4개 스크립트가 `buffer_zone_tqqq`, `buffer_zone_qqq` 모듈의 `STRATEGY_NAME`, `GRID_RESULTS_PATH`를 참조
- `run_single_backtest.py`의 regime_summaries가 무조건 `MARKET_REGIMES`(QQQ 기준) 적용 → cross-asset 전략에 부적합

### 스크립트별 현재 참조 패턴

| 스크립트 | 참조 속성 | 용도 |
|---|---|---|
| `run_single_backtest.py` | `.STRATEGY_NAME`, `.run_single` | 전략 레지스트리 등록 |
| `run_grid_search.py` | `.STRATEGY_NAME`, `.GRID_RESULTS_PATH` | STRATEGY_CONFIG 딕셔너리 |
| `run_walkforward.py` | `.STRATEGY_NAME`, `.GRID_RESULTS_PATH.parent` | STRATEGY_CONFIG 딕셔너리 |
| `run_cpcv_analysis.py` | `.STRATEGY_NAME`, `.GRID_RESULTS_PATH.parent` | STRATEGY_CONFIG 딕셔너리 |

### regime_summaries 분기 로직

- `MARKET_REGIMES`는 QQQ 기준 19개 구간 (수동 분류)
- QQQ 시그널 전략 (signal_path == QQQ_DATA_PATH): `MARKET_REGIMES` 적용
- cross-asset 전략 (signal_path != QQQ_DATA_PATH): 빈 리스트 (`[]`)
- 판별 기준: `SingleBacktestResult.data_info["signal_path"]`와 `QQQ_DATA_PATH` 비교

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 4개 스크립트가 `buffer_zone.py` 통합 모듈만 참조 (기존 개별 모듈 import 제거)
- [x] `run_single_backtest.py`의 전략 레지스트리에 CONFIGS 기반 자동 등록
- [x] `run_single_backtest.py`의 regime_summaries 분기 로직 구현
- [x] `buffer_zone_tqqq.py`, `buffer_zone_qqq.py` 삭제
- [x] `test_buffer_zone_tqqq.py`, `test_buffer_zone_qqq.py` 삭제
- [x] `test_buffer_zone.py`에 기존 테스트 케이스 통합 (resolve_params 폴백, run_single 구조)
- [x] `__init__.py`에서 삭제된 모듈 참조 제거
- [x] CLAUDE.md 문서 업데이트 (루트 디렉토리 구조, backtest 도메인, scripts)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=479, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**삭제:**

- `src/qbt/backtest/strategies/buffer_zone_tqqq.py`
- `src/qbt/backtest/strategies/buffer_zone_qqq.py`
- `tests/test_buffer_zone_tqqq.py`
- `tests/test_buffer_zone_qqq.py`

**수정:**

- `scripts/backtest/run_single_backtest.py` — 전략 레지스트리 + regime_summaries 분기
- `scripts/backtest/run_grid_search.py` — import 변경 + STRATEGY_CONFIG 구성
- `scripts/backtest/run_walkforward.py` — import 변경 + STRATEGY_CONFIG 구성
- `scripts/backtest/run_cpcv_analysis.py` — import 변경 + STRATEGY_CONFIG 구성
- `src/qbt/backtest/strategies/__init__.py` — 삭제된 모듈 참조 제거
- `tests/test_buffer_zone.py` — 기존 테스트 통합 추가
- `CLAUDE.md` (루트) — 디렉토리 구조 업데이트
- `src/qbt/backtest/CLAUDE.md` — 전략 모듈 설명 업데이트
- `scripts/CLAUDE.md` — 스크립트 설명 업데이트

**영향 없음 (코드 수정 불필요):**

- `scripts/backtest/app_single_backtest.py` — Feature Detection 기반, 자동 호환
- `scripts/backtest/run_wfo_stitched_backtest.py` — buffer_zone_atr_tqqq만 사용
- `scripts/backtest/run_atr_comparison.py` — buffer_zone_atr_tqqq만 사용
- `scripts/backtest/run_wfo_comparison.py` — buffer_zone_atr_tqqq만 사용
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — 핵심 엔진, 변경 없음
- `src/qbt/backtest/strategies/buffer_zone.py` — Plan 1에서 생성 완료

### 데이터/결과 영향

- 기존 결과 파일 영향 없음 (출력 포맷 동일)
- cross-asset 전략 결과: `storage/results/backtest/buffer_zone_{ticker}/` 에 저장 (사용자 실행 후)
- `summary.json`의 `regime_summaries`: cross-asset은 빈 리스트 → 대시보드에서 "데이터가 없습니다" 표시

## 6) 단계별 계획(Phases)

### Phase 1 — 스크립트 마이그레이션 (Green)

**작업 내용:**

- [x] `scripts/backtest/run_single_backtest.py` 변경
  - [x] import 변경: `buffer_zone_tqqq`, `buffer_zone_qqq` → `buffer_zone`
  - [x] 전략 레지스트리: `buffer_zone.CONFIGS` 기반 자동 등록 (`for _config in buffer_zone.CONFIGS`)
  - [x] regime_summaries 분기 로직 추가:
    - `data_info["signal_path"] == str(QQQ_DATA_PATH)` → `MARKET_REGIMES` 적용
    - 그 외 → 빈 리스트 (`[]`)
  - [x] `--strategy` choices에 cross-asset 전략명 자동 포함 (STRATEGY_RUNNERS.keys() 기반이므로 자동)
- [x] `scripts/backtest/run_grid_search.py` 변경
  - [x] import 변경: `buffer_zone_tqqq`, `buffer_zone_qqq` → `buffer_zone`
  - [x] STRATEGY_CONFIG 구성: `buffer_zone.get_config()` 기반으로 `signal_path`, `trade_path`, `grid_results_path` 참조
  - [x] grid search 대상은 기존 전략(buffer_zone_tqqq, buffer_zone_qqq)만 유지 (cross-asset은 그리드 서치 불필요)
- [x] `scripts/backtest/run_walkforward.py` 변경
  - [x] import 변경: `buffer_zone_tqqq`, `buffer_zone_qqq` → `buffer_zone`
  - [x] STRATEGY_CONFIG 구성: `buffer_zone.get_config()` 기반으로 `signal_path`, `trade_path`, `result_dir` 참조
  - [x] WFO 대상은 기존 전략만 유지 (cross-asset은 WFO 불필요)
- [x] `scripts/backtest/run_cpcv_analysis.py` 변경
  - [x] import 변경: `buffer_zone_tqqq`, `buffer_zone_qqq` → `buffer_zone`
  - [x] STRATEGY_CONFIG 구성: `buffer_zone.get_config()` 기반으로 `signal_path`, `trade_path`, `result_dir` 참조
  - [x] CSCV 분석 대상은 기존 전략만 유지 (cross-asset은 CSCV 불필요)

---

### Phase 2 — 기존 모듈 삭제 + 테스트 통합 (Green)

**작업 내용:**

- [x] `src/qbt/backtest/strategies/buffer_zone_tqqq.py` 삭제
- [x] `src/qbt/backtest/strategies/buffer_zone_qqq.py` 삭제
- [x] `src/qbt/backtest/strategies/__init__.py`에서 삭제된 모듈 참조 제거
  - `buffer_zone_tqqq`, `buffer_zone_qqq` import 제거
  - `buffer_zone` 모듈 export는 Plan 1에서 추가 완료
- [x] `tests/test_buffer_zone_tqqq.py` 삭제
- [x] `tests/test_buffer_zone_qqq.py` 삭제
- [x] `tests/test_buffer_zone.py`에 기존 테스트 케이스 통합
  - [x] `TestResolveParamsForConfig`에 TQQQ/QQQ 폴백 체인 테스트 추가 (기존 test_buffer_zone_tqqq.py의 3개 테스트 이전)
    - OVERRIDE 없고 grid 없을 때 DEFAULT 사용
    - OVERRIDE 값이 최우선
    - grid_results.csv 존재 시 grid_best 사용
  - [x] `TestCreateRunner`에 TQQQ/QQQ run_single 구조 검증 추가 (기존 test_buffer_zone_tqqq.py, test_buffer_zone_qqq.py의 run_single 테스트 이전)
    - buffer_zone_tqqq config로 run_single 실행 → SingleBacktestResult 구조 검증
    - buffer_zone_qqq config로 run_single 실행 → SingleBacktestResult 구조 검증

---

### Phase 3 — 문서 업데이트 + 최종 검증

**작업 내용**

- [x] `CLAUDE.md` (루트) 업데이트
  - [x] 디렉토리 구조에 `buffer_zone.py` 추가, `buffer_zone_tqqq.py`/`buffer_zone_qqq.py` 제거
  - [x] `storage/results/backtest/` 하위에 cross-asset 결과 디렉토리 추가
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - [x] `strategies/buffer_zone.py` 섹션 추가 (BufferZoneConfig, CONFIGS, create_runner, resolve_params_for_config)
  - [x] `strategies/buffer_zone_tqqq.py`, `strategies/buffer_zone_qqq.py` 섹션 삭제
  - [x] `strategies/__init__.py` 설명 업데이트
- [x] `scripts/CLAUDE.md` 업데이트
  - [x] `run_single_backtest.py` 설명 업데이트 (cross-asset 전략 자동 등록, regime_summaries 분기)
  - [x] `--strategy` 옵션 설명에 cross-asset 전략명 추가
- [x] `tests/CLAUDE.md` 업데이트
  - [x] 테스트 파일 목록에 `test_buffer_zone.py` 추가, `test_buffer_zone_tqqq.py`/`test_buffer_zone_qqq.py` 제거
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 스크립트 buffer_zone 통합 모듈 마이그레이션 + 기존 개별 모듈 삭제
2. 백테스트 / cross-asset 전략 레지스트리 자동 등록 + regime_summaries 분기 추가
3. 백테스트 / 버퍼존 개별 모듈(tqqq/qqq) 삭제 + 스크립트/테스트 통합 마이그레이션
4. 백테스트 / 교차 자산 검증 스크립트 마이그레이션 + CLAUDE.md 문서 업데이트
5. 백테스트 / buffer_zone 통합 완료: 스크립트 전환 + 레거시 모듈 제거 + 문서 정리

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|---|---|---|
| 기존 모듈 삭제 시 미발견 참조로 import 에러 | 높음 | Phase 1(스크립트 전환) 완료 후 Phase 2(삭제) 진행. validate_project.py로 검증 |
| grid_search/walkforward/cpcv 스크립트의 STRATEGY_CONFIG 구조 변경 | 중간 | `get_config()` 기반으로 동일 속성 참조. 기존 dict 구조와 호환 |
| regime_summaries 분기 로직에서 경로 비교 부정확 | 중간 | `str(QQQ_DATA_PATH)` 문자열 비교로 명확한 판별. 기존 data_info 구조 활용 |
| __init__.py에서 삭제된 모듈 참조 남아있으면 import 에러 | 높음 | Phase 2에서 명시적으로 제거. grep으로 잔여 참조 확인 |
| CLAUDE.md 업데이트 누락 | 낮음 | Phase 3에서 루트/backtest/scripts/tests 4개 문서 명시적 체크 |

## 8) 메모(Notes)

### 핵심 결정 사항

- **grid_search/walkforward/cpcv 대상**: cross-asset 전략은 파라미터 고정이므로 그리드 서치, WFO, CSCV 분석 대상에서 제외. 기존 전략(buffer_zone_tqqq, buffer_zone_qqq, buffer_zone_atr_tqqq)만 유지
- **regime_summaries 판별**: `data_info["signal_path"]` 기반. QQQ 시그널 전략만 MARKET_REGIMES 적용
- **대시보드 호환성**: `app_single_backtest.py`는 Feature Detection 기반이므로 코드 수정 없이 cross-asset 전략 자동 표시
  - cross-asset 전략의 regime_summaries = 빈 리스트 → "데이터가 없습니다" 자동 표시
  - hold_days_used=0, recent_sell_count=0 → 항상 0인 컬럼 (노이즈 수준)

### 스크립트 마이그레이션 패턴

**run_single_backtest.py (Before):**
```python
from qbt.backtest.strategies import buffer_zone_qqq, buffer_zone_tqqq
STRATEGY_RUNNERS = {
    buffer_zone_tqqq.STRATEGY_NAME: buffer_zone_tqqq.run_single,
    buffer_zone_qqq.STRATEGY_NAME: buffer_zone_qqq.run_single,
    ...
}
```

**run_single_backtest.py (After):**
```python
from qbt.backtest.strategies import buffer_zone
# Buffer zone: CONFIGS 기반 자동 등록
for _config in buffer_zone.CONFIGS:
    STRATEGY_RUNNERS[_config.strategy_name] = buffer_zone.create_runner(_config)
```

**run_grid_search.py (Before):**
```python
from qbt.backtest.strategies import buffer_zone_qqq, buffer_zone_tqqq
STRATEGY_CONFIG = {
    buffer_zone_tqqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "grid_results_path": buffer_zone_tqqq.GRID_RESULTS_PATH,
    },
    ...
}
```

**run_grid_search.py (After):**
```python
from qbt.backtest.strategies import buffer_zone
_tqqq = buffer_zone.get_config("buffer_zone_tqqq")
_qqq = buffer_zone.get_config("buffer_zone_qqq")
STRATEGY_CONFIG = {
    _tqqq.strategy_name: {
        "signal_path": _tqqq.signal_data_path,
        "grid_results_path": _tqqq.grid_results_path,
    },
    _qqq.strategy_name: {
        "signal_path": _qqq.signal_data_path,
        "grid_results_path": _qqq.grid_results_path,
    },
}
```

### 참고 문서

- `cross_asset_validation_plan.md` §9.3 영향받는 파일, §9.4 작업 순서
- `PLAN_BUFFER_ZONE_UNIFIED_MODULE.md` (선행 Plan)

### 진행 로그 (KST)

- 2026-03-07 15:00: Plan 초안 작성
- 2026-03-07 16:30: Phase 1~3 완료. validate_project.py 통과 (passed=479, failed=0, skipped=0)

---
