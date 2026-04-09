# PLAN: 전략 필터 제거 + UGL/UBT 추가

## 메타

- 작성일: 2026-04-09 10:00
- 상태: 진행 중

---

## Goal

1. `DEFAULT_PORTFOLIO_EXPERIMENTS`와 `DEFAULT_SINGLE_BACKTEST_STRATEGIES`를 `constants.py`에서 제거
2. 각 모듈(buffer_zone.py, buy_and_hold.py, portfolio_configs.py)의 CONFIGS에 선언된 것만 실행/시각화하도록 변경
3. buffer_zone / buy_and_hold CONFIGS에 UGL/UBT 추가 (GLD/TLT 시그널 기반 2x 레버리지)
4. 미사용 전략(spy, iwm, efa, eem) 및 미활성 포트폴리오 실험 제거

## Non-Goals

- 새로운 전략 로직 추가 (기존 버퍼존/B&H 패턴 재사용)
- 스크립트 실행 (사용자만 실행)
- 대시보드 UI 변경
- README.md 변경 없음

## Context

### 영향받는 규칙

- [루트 CLAUDE.md](../../CLAUDE.md): 상수 관리, 코딩 표준
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): 전략 CONFIGS 패턴
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): CLI 계층 규칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): 테스트 작성 원칙

해당 문서들에 기재된 규칙을 모두 숙지하고 준수한다.

### 배경

현재 `constants.py`에 `DEFAULT_SINGLE_BACKTEST_STRATEGIES`와 `DEFAULT_PORTFOLIO_EXPERIMENTS`가 필터 리스트로 존재한다.
스크립트들은 CONFIGS 전체를 등록한 후 이 필터로 활성 전략/실험만 골라 실행한다.
이 구조를 단순화하여, CONFIGS 자체가 활성 목록이 되도록 변경한다.

## Definition of Done

- [ ] `constants.py`에서 `DEFAULT_PORTFOLIO_EXPERIMENTS`, `DEFAULT_SINGLE_BACKTEST_STRATEGIES` 제거
- [ ] `buffer_zone.py` CONFIGS: spy/iwm/efa/eem 제거, ugl/ubt 추가 (6개)
- [ ] `buy_and_hold.py` CONFIGS: spy/iwm/efa/eem 제거, ugl/ubt 추가 (6개)
- [ ] `portfolio_configs.py`: 활성 5개만 남기고 나머지 제거
- [ ] 스크립트 5개에서 필터링 로직 제거
- [ ] 테스트 코드 업데이트
- [ ] `poetry run python validate_project.py` passed, failed=0, skipped=0

## Scope

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/constants.py` | DEFAULT_* 상수 2개 제거 |
| `src/qbt/backtest/strategies/buffer_zone.py` | CONFIGS 정리 + UGL/UBT 추가, 미사용 import 제거 |
| `src/qbt/backtest/strategies/buy_and_hold.py` | CONFIGS 정리 + UGL/UBT 추가, import 추가/제거 |
| `src/qbt/backtest/portfolio_configs.py` | 활성 5개만 남기고 나머지 제거, 미사용 import 제거 |
| `scripts/backtest/run_single_backtest.py` | 필터링 로직 제거 |
| `scripts/backtest/app_single_backtest.py` | 필터링 로직 제거 |
| `scripts/backtest/run_portfolio_backtest.py` | 필터링 로직 제거 |
| `scripts/backtest/app_portfolio_backtest.py` | 필터링 로직 제거 |
| `scripts/backtest/app_portfolio_debug.py` | 필터링 로직 제거 |
| `tests/test_portfolio_configs.py` | TestDefaultPortfolioExperiments 제거, 제거된 시리즈 테스트 제거/수정 |
| `tests/test_buffer_zone.py` | spy 참조 -> 다른 config으로 변경 |
| `tests/test_buy_and_hold.py` | cross-asset 테스트 업데이트 |

## Phases

### Phase 1: 비즈니스 로직 변경

1. `constants.py`: DEFAULT_* 2개 제거
2. `buffer_zone.py`: CONFIGS 정리 + UGL/UBT 추가
3. `buy_and_hold.py`: CONFIGS 정리 + UGL/UBT 추가
4. `portfolio_configs.py`: 활성 5개만 남기기

### Phase 2: 스크립트 필터링 로직 제거

5개 스크립트에서 필터링 import/로직 제거

### Phase 3: 테스트 업데이트 + 검증

테스트 코드 업데이트 후 `validate_project.py` 실행

## Risks

- 제거되는 포트폴리오 실험 결과 CSV가 storage에 남아있을 수 있음 -> 무해 (앱이 탐색할 뿐 에러 없음)
- run_param_plateau_all.py에 cross-asset 참조가 있을 수 있음 -> 확인 필요

---

## Commit Messages (Final candidates)

1. 백테스트 / 전략 필터 제거 + UGL/UBT 추가 (CONFIGS 단순화)
2. 백테스트 / DEFAULT_*_STRATEGIES 제거, CONFIGS를 활성 목록으로 전환 + UGL/UBT
3. 백테스트 / 필터 상수 제거 + 미사용 전략 정리 + 2x 레버리지 ETF(UGL/UBT) 추가
4. 백테스트 / CONFIGS 직접 사용으로 전환 + spy/iwm/efa/eem 제거 + ugl/ubt 추가
5. 백테스트 / 전략/실험 필터 리스트 제거 및 CONFIGS 단순화 + UGL/UBT 신규 등록
