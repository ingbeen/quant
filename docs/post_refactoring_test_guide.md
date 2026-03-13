# 리팩토링 후 스크립트 실행 테스트 가이드

> 작성일: 2026-03-13
> 대상: 8개 계획서에 걸친 대규모 리팩토링 후 영향받는 전체 스크립트 10개
> 목적: 리팩토링 후 모든 스크립트의 정상 동작 검증

---

## 관련 계획서 목록

| 계획서 | 상태 | 주요 변경 |
|--------|------|----------|
| `PLAN_backtest_cleanup.md` | Done | 폐기 전략/실험 모듈 삭제 (6모듈+5스크립트+4테스트) |
| `PLAN_backtest_4p_transition.md` | Done | 4P 고정 파라미터 전환 + 고원 대시보드 구현 |
| `PLAN_tqqq_spread_lab_cleanup.md` | Done | Spread Lab 일회성 스크립트/모듈 삭제 |
| `PLAN_tqqq_refactoring.md` | Done | TQQQ 도메인 Dead Code 삭제 + 모듈 재구성 |
| `PLAN_post_refactoring_consistency.md` | Done | 문서-코드 정합성 복원 + ATR dead code 제거 |
| `PLAN_post_refactoring_consistency_v2.md` | Done | 14건 불일치 수정 (dead code + 문서 보정) |
| `PLAN_backtest_refactoring.md` | Done | BufferZoneConfig 간소화 + Dead Code 제거 |
| `PLAN_type_ignore_cleanup.md` | Done | type: ignore 33개 정리 (cast 도입) |

---

## 1. 데이터 다운로드

```bash
# 전체 종목 일괄 다운로드
poetry run python scripts/data/download_data.py

# 특정 종목만 다운로드
poetry run python scripts/data/download_data.py QQQ
poetry run python scripts/data/download_data.py TQQQ --start 2010-02-11
```

**예상 결과**: `storage/stock/` 에 `{TICKER}_max.csv` 저장. 검증(결측치/0값/음수/급등락) 통과 후 저장. 종료코드 0.

**리팩토링 영향**: 없음 (직접 변경 없음). 단, 후속 스크립트의 데이터 소스이므로 최신 데이터 확보 목적으로 실행 권장.

---

## 2. 단일 백테스트 (가장 핵심)

```bash
# 전체 전략 실행 (버퍼존 8개 + Buy&Hold 8개 = 16개)
poetry run python scripts/backtest/run_single_backtest.py

# 개별 전략 실행
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_tqqq
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_qqq
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_spy
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_iwm
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_efa
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_eem
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_gld
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_tlt
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_qqq
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_tqqq
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_spy
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_iwm
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_efa
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_eem
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_gld
poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold_tlt
```

**예상 결과**: 각 전략별로 `storage/results/backtest/{strategy_name}/` 하위에 4개 파일 생성:
- `signal.csv` -- OHLC + MA + 전일대비%
- `equity.csv` -- 에쿼티 곡선 + 밴드 + 드로우다운
- `trades.csv` -- 거래 내역 + 보유기간
- `summary.json` -- 요약 지표 + 파라미터 + 월별 수익률 + regime_summaries(QQQ 시그널 전략만)

종료코드 0. 콘솔에 성과 요약 테이블 출력.

**리팩토링 영향** (핵심 확인 포인트):
- **4P 고정 파라미터 적용 확인**: 모든 버퍼존 전략이 MA=200, buy=0.03, sell=0.05, hold=3으로 실행되는지 확인 (summary.json 내 파라미터 값)
- **BufferZoneConfig 간소화**: `grid_results_path` 제거, `override_*` -> 직접 파라미터명으로 변경 (`PLAN_backtest_refactoring`)
- **buffer_zone_qqq_4p 삭제**: `--strategy buffer_zone_qqq_4p`는 더 이상 유효하지 않음 (에러 예상)
- **Donchian/ATR 전략 삭제**: `--strategy donchian_channel_tqqq` / `--strategy buffer_zone_atr_tqqq`는 에러 예상
- **cross-asset 6개 전략**: hold_days=3으로 변경됨 (기존 2 -> 3)
- **open_position**: 포지션 보유 중인 전략은 summary.json에 `open_position` 포함

---

## 3. 워크포워드 검증 (WFO)

```bash
# 전체 전략 WFO (buffer_zone_tqqq + buffer_zone_qqq)
poetry run python scripts/backtest/run_walkforward.py

# 개별 전략 WFO
poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_tqqq
poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_qqq
```

**예상 결과**: 각 전략 결과 디렉토리에 3-Mode WFO 결과 저장:
- `walkforward_dynamic.csv` + `walkforward_dynamic_stitched_equity.csv`
- `walkforward_sell_fixed.csv` + `walkforward_sell_fixed_stitched_equity.csv`
- `walkforward_full_fixed.csv` + `walkforward_full_fixed_stitched_equity.csv`
- `walkforward_summary.json`

종료코드 0. 콘솔에 WFO 모드별 요약 통계 출력.

**리팩토링 영향**:
- **ATR 파라미터 제거**: `run_walkforward()`, `run_grid_search()` 시그니처에서 ATR 파라미터 삭제됨 (`PLAN_post_refactoring_consistency`)
- **buffer_zone_atr_tqqq 분기 제거**: `--strategy buffer_zone_atr_tqqq`는 에러 예상 (`PLAN_backtest_cleanup`)
- WFO 대상은 `buffer_zone_tqqq`와 `buffer_zone_qqq` 2개만 유효

---

## 4. 파라미터 고원 분석

```bash
# 전체 4개 파라미터 분석
poetry run python scripts/backtest/run_param_plateau_all.py

# 개별 파라미터 분석
poetry run python scripts/backtest/run_param_plateau_all.py --experiment hold_days
poetry run python scripts/backtest/run_param_plateau_all.py --experiment sell_buffer
poetry run python scripts/backtest/run_param_plateau_all.py --experiment buy_buffer
poetry run python scripts/backtest/run_param_plateau_all.py --experiment ma_window
```

**예상 결과**: `storage/results/backtest/param_plateau/` 에 결과 저장:
- 피벗 CSV: `param_plateau_{param}_{metric}.csv` (예: `param_plateau_buy_buffer_calmar.csv`)
- 상세 CSV: `param_plateau_all_detail.csv`
- 메트릭: calmar, cagr, mdd, trades, win_rate

종료코드 0. 각 실험당 여러 자산에 대해 파라미터 범위를 순회하며 백테스트 실행.

**리팩토링 영향**:
- **신규 스크립트**: 기존 `run_hold_days_plateau.py` + `run_param_plateau.py` 2개가 1개로 통합됨 (`PLAN_backtest_4p_transition`)
- **BufferZoneConfig 필드명 변경**: `replace()` 호출에서 `override_*` -> 직접 파라미터명으로 변경 (`PLAN_backtest_refactoring`)
- **hold_days 결과도 param_plateau/ 로 통합** (기존 hold_days_plateau/ 에서 이동)
- **소요 시간이 길 수 있음**: 파라미터 범위 순회 + 자산별 백테스트 반복

---

## 5. TQQQ 합성 데이터 생성

```bash
poetry run python scripts/tqqq/generate_synthetic.py
```

**예상 결과**: `storage/stock/TQQQ_synthetic_max.csv` 생성. QQQ 데이터 기반으로 TQQQ 합성 가격 시뮬레이션. 종료코드 0.

**리팩토링 영향**:
- `simulate()` 함수의 `funding_spread`가 필수 인자로 변경됨 (`PLAN_tqqq_refactoring`) - 스크립트 내에서 명시적으로 전달하고 있어야 함
- `types.py` -> `simulation.py` 인라인 통합
- `DEFAULT_FUNDING_SPREAD` 삭제 (필수 인자화)

---

## 6. TQQQ 일별 비교 데이터 생성

```bash
poetry run python scripts/tqqq/generate_daily_comparison.py
```

**선행 조건**: `generate_synthetic.py` 실행 완료 (TQQQ_synthetic_max.csv 필요), 실제 TQQQ 데이터 (`TQQQ_max.csv`) 존재

**예상 결과**: `storage/results/tqqq/tqqq_daily_comparison.csv` 생성. 실제 TQQQ vs 시뮬레이션 TQQQ 일별 비교 데이터. 종료코드 0.

**리팩토링 영향**:
- `simulate()` 함수 시그니처 변경 (funding_spread 필수)
- `_compute_softplus_spread`, `_validate_ffr_coverage` private 전환
- softplus 동적 스프레드 모델 사용 (a=-6.1, b=0.37)

---

## 7. Streamlit 대시보드 - 단일 백테스트

```bash
poetry run streamlit run scripts/backtest/app_single_backtest.py
```

**선행 조건**: `run_single_backtest.py` 실행 완료 (결과 CSV/JSON 존재)

**예상 결과**: 브라우저에서 대시보드 열림. 전략별 동적 탭 자동 생성. 각 탭에 lightweight-charts 캔들차트 + MA/밴드 오버레이 + 거래 마커 + 에쿼티 차트.

**리팩토링 영향**:
- **Donchian Channel 코드 삭제**: `upper_channel`/`lower_channel` 처리 코드 제거됨 (`PLAN_post_refactoring_consistency_v2`)
- **type: ignore 정리**: `cast()` 도입으로 타입 안정성 향상 (`PLAN_type_ignore_cleanup`)
- **display_name 필수**: summary.json에 `display_name` 없으면 ValueError
- **open_position 마커**: 보유 중 포지션이 있으면 `"Buy $XX.X (보유중)"` 마커 표시

---

## 8. Streamlit 대시보드 - 파라미터 고원 안정성

```bash
poetry run streamlit run scripts/backtest/app_parameter_stability.py
```

**선행 조건**: `run_param_plateau_all.py` 실행 완료 (param_plateau/ CSV 존재)

**예상 결과**: 브라우저에서 대시보드 열림. 4개 탭 (MA Window / Buy Buffer / Sell Buffer / Hold Days). 각 탭에 7자산 Calmar 라인차트 + 확정값 마커 + 고원 구간 하이라이트 + 보조 지표 expander.

**리팩토링 영향**:
- **전면 재작성됨**: 기존 grid_results.csv 기반 -> 고원 분석 CSV 기반 (`PLAN_backtest_4p_transition`)
- **parameter_stability.py 모듈 변경**: 고원 데이터 분석 모듈로 변환, `constants.py`의 `FIXED_4P_*` 참조
- **type: ignore 정리**: `cast()` 도입 (`PLAN_type_ignore_cleanup`)
- **주의**: hold_days 실험 결과가 `param_plateau/`에 없으면 해당 탭이 정상 동작하지 않을 수 있음 (hold_days 실험을 별도 실행 필요: `--experiment hold_days`)

---

## 9. Streamlit 대시보드 - TQQQ 일별 비교

```bash
poetry run streamlit run scripts/tqqq/app_daily_comparison.py
```

**선행 조건**: `generate_daily_comparison.py` 실행 완료 (tqqq_daily_comparison.csv 존재)

**예상 결과**: 브라우저에서 대시보드 열림. 실제 TQQQ vs 시뮬레이션 가격 비교 차트, 오차 히스토그램, 시계열 오차 추이.

**리팩토링 영향**: 직접적 변경 없음. 하지만 `visualization.py`의 차트 함수가 사용되며, 데이터 소스인 `tqqq_daily_comparison.csv`가 리팩토링된 `simulate()` 함수로 생성되므로 간접 영향 확인 필요.

---

## 10. Streamlit 대시보드 - Spread Lab (금리-오차 분석)

```bash
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

**선행 조건**: 결과 CSV 8개가 `storage/results/tqqq/` 및 `storage/results/tqqq/spread_lab/`에 존재 (이미 생성되어 있음, CSV 생성 스크립트는 삭제됨)

**예상 결과**: 브라우저에서 대시보드 열림. 단일 흐름: 오차분석 -> 튜닝 -> 과최적화진단 -> 상세분석. 기존 CSV를 로드하여 시각화.

**리팩토링 영향**:
- **import 경로 변경**: `analysis_helpers` -> `spread_lab_helpers`로 변경됨 (`PLAN_tqqq_refactoring`)
- **삭제된 스크립트 참조 수정**: docstring에서 삭제된 스크립트(tune, validate, generate) 참조를 git history 복원 안내로 변경 (`PLAN_post_refactoring_consistency_v2`)
- **`DEFAULT_TOP_N_CROSS_VALIDATION`**: constants.py에서 삭제, 앱 내 로컬 상수로 이동 (`PLAN_tqqq_refactoring`)
- **type: ignore 정리**: `cast()` 도입 (`PLAN_type_ignore_cleanup`)

---

## 추가: 자동화 테스트 (스크립트 아님, 검증용)

```bash
# 전체 품질 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py

# 테스트만 실행
poetry run python validate_project.py --only-tests

# 커버리지 포함
poetry run python validate_project.py --cov
```

**예상 결과**: `passed=334, failed=0, skipped=0` (최신 validation 기준)

---

## 실행 우선순위 권장 순서

| 순서 | 스크립트 | 이유 |
|------|---------|------|
| 0 | `validate_project.py` | 코드 무결성 먼저 확인 |
| 1 | `download_data.py` | 최신 데이터 확보 |
| 2 | `generate_synthetic.py` | TQQQ 합성 데이터 (후속 스크립트 의존) |
| 3 | `run_single_backtest.py` | 핵심 - 4P 고정 파라미터 적용 확인 |
| 4 | `generate_daily_comparison.py` | TQQQ 비교 데이터 |
| 5 | `run_walkforward.py` | WFO 검증 (ATR 제거 확인) |
| 6 | `run_param_plateau_all.py` | 고원 분석 (소요 시간 길 수 있음) |
| 7 | `app_single_backtest.py` | 대시보드 시각화 확인 |
| 8 | `app_daily_comparison.py` | TQQQ 대시보드 확인 |
| 9 | `app_parameter_stability.py` | 고원 대시보드 확인 (6번 선행) |
| 10 | `app_rate_spread_lab.py` | Spread Lab 대시보드 확인 |
