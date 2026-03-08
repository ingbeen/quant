# Implementation Plan: hold_days=2 실험 (실험 1 + 실험 2)

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

**작성일**: 2026-03-08 19:00
**마지막 업데이트**: 2026-03-08 19:30
**관련 범위**: backtest, common_constants, tests
**관련 문서**: `docs/overfitting_analysis_report.md` §17.4

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

- [x] cross-asset 공통 hold_days를 0→2로 변경하여 실험 1(QQQ 기준선)과 실험 2(교차 자산 재검증) 실행 환경을 구성한다
- [x] `buffer_zone_qqq_3p`를 `buffer_zone_qqq_4p`로 리네이밍한다 (hold_days=2 추가로 파라미터 4개)
- [x] 테스트 및 문서를 동기화하여 코드 정합성을 유지한다

## 2) 비목표(Non-Goals)

- 스크립트 실행 (사용자가 직접 실행)
- 실험 결과 분석 및 보고서 업데이트
- cross-asset Buy & Hold 벤치마크 추가 (별도 작업)
- hold_days 범위 확장 탐색 (실험 3, 4)
- 실험 결과에 따른 파라미터 최종 확정 판단

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

overfitting_analysis_report.md §15.3에서 hold_days 제거(0)의 부작용이 확인되었다:
- Calmar 33% 하락 (0.300 → 0.200)
- MDD 12.7%p 악화 (-36.49% → -49.18%)
- 승률 16%p 하락 (71.43% → 55.56%)

§16에서 hold_days 존재의 학술적 근거가 S등급으로 재평가되었고, §17.2에서 hold_days=2를 경제적 논거에 기반하여 사전 결정하는 것을 권고하였다.

이에 따라 §17.4의 실험 1(QQQ 기준선)과 실험 2(교차 자산 재검증)를 수행하기 위해, cross-asset 공통 hold_days를 0→2로 변경해야 한다.

**실험 1**: hold_days=2 QQQ 기준선 확보
- 파라미터: MA=200, buy=3%, sell=5%, hold=2, recent=0
- 통과 기준: Calmar ≥ 0.240 (hold=3의 80%)

**실험 2**: hold_days=2 교차 자산 재검증
- 대상: SPY, IWM, EFA, GLD (+EEM, TLT)
- 비교 대상: 기존 hold=0 결과 (보고서 §15에 기록됨)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `_CROSS_ASSET_HOLD_DAYS` 상수가 0→2로 변경됨
- [x] `buffer_zone_qqq_3p` → `buffer_zone_qqq_4p` 리네이밍 완료 (strategy_name, display_name, 결과 디렉토리 경로, 상수명)
- [x] 테스트가 변경된 hold_days=2를 반영함
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] CLAUDE.md 문서 업데이트 (루트, backtest)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py` — `BUFFER_ZONE_QQQ_3P_RESULTS_DIR` → `BUFFER_ZONE_QQQ_4P_RESULTS_DIR` 리네이밍
- `src/qbt/backtest/strategies/buffer_zone.py` — `_CROSS_ASSET_HOLD_DAYS` 0→2 변경, `buffer_zone_qqq_3p` → `buffer_zone_qqq_4p` 리네이밍
- `tests/test_buffer_zone.py` — `test_three_param_config_sets_hold_days_zero` 테스트 수정 (hold_days=2 검증)
- `CLAUDE.md` (루트) — 디렉토리 구조 및 설정 목록 업데이트
- `src/qbt/backtest/CLAUDE.md` — 설정 목록 업데이트

### 데이터/결과 영향

- 기존 `storage/results/backtest/buffer_zone_qqq_3p/` 결과는 더 이상 참조되지 않음 (수동 삭제 가능)
- 새 결과는 `storage/results/backtest/buffer_zone_qqq_4p/`에 저장됨
- cross-asset 6개(SPY, IWM, EFA, EEM, GLD, TLT) 결과는 동일 경로에 hold_days=2 결과로 덮어써짐
- 기존 hold=0 결과 수치는 overfitting_analysis_report.md §15에 보존되어 있으므로 비교 가능

## 6) 단계별 계획(Phases)

### Phase 1 — 코드 변경 + 테스트 수정 (그린 유지)

**작업 내용**:

- [x] `src/qbt/common_constants.py`: `BUFFER_ZONE_QQQ_3P_RESULTS_DIR` → `BUFFER_ZONE_QQQ_4P_RESULTS_DIR` 리네이밍 (경로: `"buffer_zone_qqq_3p"` → `"buffer_zone_qqq_4p"`)
- [x] `src/qbt/backtest/strategies/buffer_zone.py`:
  - [x] `_CROSS_ASSET_HOLD_DAYS = 0` → `_CROSS_ASSET_HOLD_DAYS = 2` 변경
  - [x] 모듈 docstring의 `buffer_zone_qqq_3p` → `buffer_zone_qqq_4p` 업데이트
  - [x] CONFIGS 내 QQQ 3P config:
    - `strategy_name`: `"buffer_zone_qqq_3p"` → `"buffer_zone_qqq_4p"`
    - `display_name`: `"버퍼존 전략 (QQQ 3P)"` → `"버퍼존 전략 (QQQ 4P)"`
    - `result_dir`: `BUFFER_ZONE_QQQ_3P_RESULTS_DIR` → `BUFFER_ZONE_QQQ_4P_RESULTS_DIR`
  - [x] import문: `BUFFER_ZONE_QQQ_3P_RESULTS_DIR` → `BUFFER_ZONE_QQQ_4P_RESULTS_DIR`
- [x] `tests/test_buffer_zone.py`:
  - [x] `test_three_param_config_sets_hold_days_zero` 수정:
    - 메서드명: `test_cross_asset_config_sets_hold_days_two`
    - `get_config("buffer_zone_spy")` → hold_days=2 검증
    - docstring 업데이트
    - assert: `params.hold_days == 0` → `params.hold_days == 2`

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `CLAUDE.md` (루트) 업데이트:
  - 디렉토리 구조: `buffer_zone_qqq_3p/` → `buffer_zone_qqq_4p/`
  - 주석: `# 버퍼존 전략 (QQQ 3P) 결과` → `# 버퍼존 전략 (QQQ 4P) 결과`
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - CONFIGS 설명: `buffer_zone_qqq_3p (고정 파라미터)` → `buffer_zone_qqq_4p (고정 파라미터)`
  - `BUFFER_ZONE_QQQ_3P_RESULTS_DIR` → `BUFFER_ZONE_QQQ_4P_RESULTS_DIR`
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / cross-asset hold_days를 0→2로 변경 + qqq_3p→qqq_4p 리네이밍
2. 백테스트 / hold_days=2 실험 환경 구성 (학술 근거 기반 사전 결정)
3. 백테스트 / hold_days=2 적용 및 buffer_zone_qqq_4p 리네이밍
4. 백테스트 / cross-asset 확인 기간 hold_days=2 설정 + 네이밍 정리
5. 백테스트 / 실험1·2 사전 작업: hold_days 0→2, qqq_3p→qqq_4p

## 7) 리스크(Risks)

- **기존 3P 결과 폴더 잔존**: `storage/results/backtest/buffer_zone_qqq_3p/`가 참조되지 않는 고아 폴더로 남음 → 사용자가 수동 삭제하거나 무시 (완화: Non-Goal로 명시)
- **대시보드 탭 변경**: `buffer_zone_qqq_3p` 탭이 사라지고 `buffer_zone_qqq_4p` 탭이 추가됨 → 자동 탐색 방식이므로 스크립트 재실행 후 자동 반영

## 8) 메모(Notes)

### 실험 실행 안내 (사용자용)

코드 변경 완료 후 사용자가 직접 실행해야 하는 명령:

```bash
# 실험 1: QQQ hold_days=2 기준선
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_qqq_4p

# 실험 2: 교차 자산 재검증 (SPY, IWM, EFA, GLD + EEM, TLT)
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_spy
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_iwm
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_efa
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_gld
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_eem
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_tlt

# 또는 전체 일괄 실행
poetry run python scripts/backtest/run_single_backtest.py
```

### 비교 기준값 (overfitting_analysis_report.md §15에서 발췌)

| 전략 | hold=0 CAGR% | hold=0 MDD% | hold=0 Calmar | hold=0 거래수 | hold=0 승률% |
|---|---|---|---|---|---|
| QQQ (3P) | 9.80 | -49.18 | 0.200 | 18 | 55.56 |
| SPY | 9.38 | -27.01 | 0.350 | 13 | 76.92 |
| IWM | 2.59 | -46.83 | 0.060 | 26 | 30.77 |
| EFA | 5.59 | -26.10 | 0.210 | 14 | 57.14 |
| EEM | 4.57 | -51.41 | 0.090 | 21 | 38.10 |
| GLD | 9.04 | -44.55 | 0.200 | 10 | 30.00 |
| TLT | 1.06 | -43.17 | 0.020 | 14 | 50.00 |

QQQ 5P (hold=3) 기준: CAGR 11.02%, MDD -36.49%, Calmar 0.300

실험 1 통과 기준: QQQ hold=2 Calmar ≥ 0.240 (hold=3의 80%)

### 진행 로그 (KST)

- 2026-03-08 19:00: 계획서 작성
- 2026-03-08 19:30: 전체 작업 완료 (Phase 1~2, validate_project passed=479/failed=0/skipped=0)

---
