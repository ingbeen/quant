# Implementation Plan: 포트폴리오 실험 필터 상수화 + F-5~F-7H 추가

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

**작성일**: 2026-04-03 16:30
**마지막 업데이트**: 2026-04-03 17:00
**관련 범위**: backtest, scripts
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 포트폴리오 실험 활성 필터 상수 `DEFAULT_PORTFOLIO_EXPERIMENTS` 추가 (`DEFAULT_SINGLE_BACKTEST_STRATEGIES` 패턴 적용)
- [x] 신규 실험 6개(F-5, F-5H, F-6, F-6H, F-7, F-7H) 추가
- [x] `run_portfolio_backtest.py` 및 `app_portfolio_backtest.py`에서 필터 적용

## 2) 비목표(Non-Goals)

- 기존 25개 PortfolioConfig 정의 삭제 (코드에 유지, 필터로만 비활성화)
- 포트폴리오 엔진 로직 변경
- 기존 결과 데이터 삭제/마이그레이션

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `run_portfolio_backtest.py`의 `--experiment all`은 25개 전체 실험을 실행하여 불필요한 시간 소모
- `app_portfolio_backtest.py`도 디스크에 존재하는 모든 결과를 표시하여 비교가 어려움
- CAGR 15% 목표에 맞는 공격적 비중(TQQQ 25~35%) 구간에서 GLD/TLT BZ의 보험 효과를 정량적으로 확인하는 실험이 필요

### 설계 결정

`DEFAULT_SINGLE_BACKTEST_STRATEGIES` 패턴 적용:
- `constants.py`에 `DEFAULT_PORTFOLIO_EXPERIMENTS: Final[list[str]]` 추가
- 활성 실험 12개 = 유지 6개(A-2, B-3, D-1, D-2, E-2, F-1) + 추가 6개(F-5, F-5H, F-6, F-6H, F-7, F-7H)
- `run_portfolio_backtest.py`: `--experiment all` 시 활성 실험만 실행, CLI choices도 활성 실험만 노출
- `app_portfolio_backtest.py`: 탐색된 실험을 `DEFAULT_PORTFOLIO_EXPERIMENTS`로 필터링
- 글로벌 시작일 계산: 활성 실험(DEFAULT_PORTFOLIO_EXPERIMENTS) 기준으로 변경

신규 실험 상세:

| 실험 | experiment_name | SPY | TQQQ | GLD | TLT | GLD/TLT 전략 |
|------|----------------|-----|------|-----|-----|-------------|
| F-5 | portfolio_f5 | 35% | 25% | 20% | 20% | 전체 BZ |
| F-5H | portfolio_f5h | 35% | 25% | 20% | 20% | GLD/TLT B&H |
| F-6 | portfolio_f6 | 30% | 30% | 20% | 20% | 전체 BZ |
| F-6H | portfolio_f6h | 30% | 30% | 20% | 20% | GLD/TLT B&H |
| F-7 | portfolio_f7 | 25% | 35% | 20% | 20% | 전체 BZ |
| F-7H | portfolio_f7h | 25% | 35% | 20% | 20% | GLD/TLT B&H |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `DEFAULT_PORTFOLIO_EXPERIMENTS` 상수가 `constants.py`에 정의됨
- [x] 신규 6개 PortfolioConfig가 `portfolio_configs.py`에 정의되고 `PORTFOLIO_CONFIGS`에 포함됨
- [x] `run_portfolio_backtest.py`가 `DEFAULT_PORTFOLIO_EXPERIMENTS`로 필터링하여 실행
- [x] `app_portfolio_backtest.py`가 `DEFAULT_PORTFOLIO_EXPERIMENTS`로 필터링하여 표시
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=479, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (README.md 변경 없음)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/constants.py` — `DEFAULT_PORTFOLIO_EXPERIMENTS` 상수 추가
- `src/qbt/backtest/portfolio_configs.py` — F-5~F-7H 6개 config 추가 + PORTFOLIO_CONFIGS 리스트 확장
- `scripts/backtest/run_portfolio_backtest.py` — 활성 실험 필터 적용
- `scripts/backtest/app_portfolio_backtest.py` — 활성 실험 필터 적용 + 신규 실험 색상 추가
- `tests/test_portfolio_configs.py` — PORTFOLIO_CONFIGS 개수 업데이트 + 신규 테스트
- `README.md`: 변경 없음

### 데이터/결과 영향

- 기존 결과 파일에 영향 없음 (필터는 실행/표시만 제어)
- 신규 실험 실행 시 `storage/results/portfolio/portfolio_f5/` 등 새 디렉토리 생성

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 + 설정 추가 + 스크립트 수정 + 테스트 업데이트

**작업 내용**:

- [x] `src/qbt/backtest/constants.py`에 `DEFAULT_PORTFOLIO_EXPERIMENTS` 상수 추가
- [x] `src/qbt/backtest/portfolio_configs.py`에 F-5~F-7H 6개 config 추가
- [x] `PORTFOLIO_CONFIGS` 리스트에 신규 6개 config 추가 (총 31개)
- [x] `scripts/backtest/run_portfolio_backtest.py` 수정:
  - `_CONFIG_MAP` → `_ACTIVE_CONFIG_MAP` (활성 실험만 포함)
  - `--experiment all` 시 활성 실험만 실행
  - CLI choices를 활성 실험 이름으로 제한
  - 글로벌 시작일 계산을 활성 실험 기준으로 변경
- [x] `scripts/backtest/app_portfolio_backtest.py` 수정:
  - `_discover_experiments()` 결과를 `DEFAULT_PORTFOLIO_EXPERIMENTS`로 필터링
  - `_EXPERIMENT_COLORS`에 신규 실험 색상 추가
- [x] `tests/test_portfolio_configs.py` 수정:
  - `test_portfolio_configs_count`: 25 → 31
  - F-5~F-7H 관련 불변조건 테스트 추가 (target_weight 합, TQQQ signal path, B&H strategy_id 등)
  - `DEFAULT_PORTFOLIO_EXPERIMENTS` 불변조건 테스트 추가

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실험 필터 상수화 + F-5~F-7H 6개 실험 추가
2. 백테스트 / DEFAULT_PORTFOLIO_EXPERIMENTS 도입 및 활성 실험 12개 구성
3. 백테스트 / 포트폴리오 실험 활성 필터 적용 + TQQQ 25~35% 구간 팩토리얼 실험 추가
4. 백테스트 / 포트폴리오 실험 상수 필터링 체계 구축 + F 시리즈 확장
5. 백테스트 / 포트폴리오 활성 실험 필터(DEFAULT_PORTFOLIO_EXPERIMENTS) + F-5~F-7H 추가

## 7) 리스크(Risks)

- **글로벌 시작일 변경**: 활성 실험 기준으로 시작일을 재계산하므로, 기존 결과와 기간이 달라질 수 있음 → 신규 실행 시 자동 재계산되므로 문제 없음
- **기존 결과 불일치**: 비활성화된 실험의 결과 파일이 디스크에 남아있을 수 있으나, 필터에 의해 무시됨

## 8) 메모(Notes)

- `DEFAULT_SINGLE_BACKTEST_STRATEGIES` 패턴을 동일하게 적용
- F-5H, F-6H, F-7H의 "H"는 GLD/TLT가 Buy & Hold 전략임을 의미 (G 시리즈 팩토리얼 설계와 동일 패턴)
- 기존 config은 코드에 유지되므로 나중에 `DEFAULT_PORTFOLIO_EXPERIMENTS`에 다시 추가하면 활성화 가능

### 진행 로그 (KST)

- 2026-04-03 16:30: Plan 작성 완료
- 2026-04-03 17:00: Phase 1~2 완료, 전체 검증 통과 (passed=479, failed=0, skipped=0)
