# Implementation Plan: Buy & Hold 팩토리 패턴 도입 + TQQQ Buy & Hold 추가

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-20 17:00
**마지막 업데이트**: 2026-02-20 17:00
**관련 범위**: backtest, scripts, tests
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

- [ ] 기존 QQQ Buy & Hold를 유지하면서 TQQQ Buy & Hold 벤치마크 전략 추가
- [ ] 팩토리 패턴(`BuyAndHoldConfig` + `create_runner`)을 도입하여 향후 티커 추가 시 한 줄 추가로 확장 가능하게 구조 개선
- [ ] 기존 `buy_and_hold` → `buy_and_hold_qqq` + `buy_and_hold_tqqq`로 네이밍 통일

## 2) 비목표(Non-Goals)

- `run_buy_and_hold()` 핵심 로직 변경 (매수/에쿼티 계산 로직은 그대로 유지)
- 새로운 비용 모델이나 거래 정책 도입
- 버퍼존 전략 변경
- 대시보드 앱 코드 변경 (Feature Detection 기반이므로 결과 폴더만 있으면 자동 탐색)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 Buy & Hold 전략은 QQQ 단일 티커에 하드코딩되어 있음
- TQQQ Buy & Hold 벤치마크가 없어서 버퍼존 전략(QQQ 시그널 + TQQQ 매매)의 성과를 TQQQ 단순 보유 대비 비교 불가
- 새 티커 추가 시 파일 복사가 필요한 구조 → 코드 중복 및 유지보수 부담

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] `BuyAndHoldConfig` + `CONFIGS` + `create_runner` 팩토리 구현
- [ ] `run_buy_and_hold()` 반환 타입 `SummaryDict`로 변경, `BuyAndHoldResultDict` 제거
- [ ] `common_constants.py`에 `BUY_AND_HOLD_QQQ_RESULTS_DIR` + `BUY_AND_HOLD_TQQQ_RESULTS_DIR` 추가
- [ ] `run_single_backtest.py`에서 CONFIGS 기반 자동 등록
- [ ] 기존 테스트 업데이트 + TQQQ B&H / 팩토리 테스트 추가
- [ ] `conftest.py` mock fixture 업데이트
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] 필요한 문서 업데이트 (CLAUDE.md 등)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/common_constants.py` | `BUY_AND_HOLD_RESULTS_DIR` → `BUY_AND_HOLD_QQQ_RESULTS_DIR` + `BUY_AND_HOLD_TQQQ_RESULTS_DIR` |
| `src/qbt/backtest/strategies/buy_and_hold.py` | 팩토리 패턴 전면 리팩토링 (BuyAndHoldConfig, CONFIGS, create_runner) |
| `src/qbt/backtest/strategies/__init__.py` | export 목록 업데이트 |
| `src/qbt/backtest/types.py` | docstring 업데이트 (BuyAndHoldResultDict 참조 제거) |
| `scripts/backtest/run_single_backtest.py` | STRATEGY_RUNNERS를 CONFIGS 루프 기반으로 변경 |
| `tests/conftest.py` | mock fixture에서 새 디렉토리 상수 패치 |
| `tests/test_strategy.py` | 기존 테스트 수정 + 팩토리/TQQQ 테스트 추가 |
| `src/qbt/backtest/CLAUDE.md` | buy_and_hold 섹션 문서 업데이트 |
| `CLAUDE.md` (루트) | 디렉토리 구조 표에서 buy_and_hold → buy_and_hold_qqq + buy_and_hold_tqqq |

### 데이터/결과 영향

- 기존 `storage/results/backtest/buy_and_hold/` 폴더 → 더 이상 사용하지 않음 (수동 삭제 필요)
- 새 결과 폴더: `buy_and_hold_qqq/`, `buy_and_hold_tqqq/`
- `--strategy buy_and_hold` CLI 인자 → `--strategy buy_and_hold_qqq` 또는 `--strategy buy_and_hold_tqqq`로 변경

## 6) 단계별 계획(Phases)

### Phase 1 — 핵심 구현 (그린 유지)

**작업 내용**:

#### 1.1 `common_constants.py` — 결과 디렉토리 상수 변경

- [ ] `BUY_AND_HOLD_RESULTS_DIR` 제거
- [ ] `BUY_AND_HOLD_QQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buy_and_hold_qqq"` 추가
- [ ] `BUY_AND_HOLD_TQQQ_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buy_and_hold_tqqq"` 추가

#### 1.2 `buy_and_hold.py` — 팩토리 패턴 구현

- [ ] `STRATEGY_NAME`, `DISPLAY_NAME`, `TRADE_DATA_PATH` 모듈 상수 제거
- [ ] `BuyAndHoldResultDict` 제거
- [ ] `run_buy_and_hold()` 반환 타입을 `SummaryDict`로 변경 (`strategy` 필드 제거)
- [ ] `BuyAndHoldConfig` frozen dataclass 추가
- [ ] `CONFIGS: list[BuyAndHoldConfig]` 리스트 추가 (QQQ + TQQQ)
- [ ] `create_runner(config) -> Callable[[], SingleBacktestResult]` 팩토리 함수 추가
- [ ] 기존 `run_single()` 함수 제거 (create_runner로 대체)
- [ ] import 업데이트: `BUY_AND_HOLD_QQQ_RESULTS_DIR`, `BUY_AND_HOLD_TQQQ_RESULTS_DIR`, `TQQQ_SYNTHETIC_DATA_PATH` 추가

#### 1.3 `strategies/__init__.py` — export 업데이트

- [ ] `BuyAndHoldConfig`, `create_runner` (또는 `create_buy_and_hold_runner`) 추가
- [ ] 기존 `BuyAndHoldParams`, `run_buy_and_hold` export 유지

#### 1.4 `run_single_backtest.py` — 전략 레지스트리 변경

- [ ] STRATEGY_RUNNERS에서 `buy_and_hold.STRATEGY_NAME: buy_and_hold.run_single` 제거
- [ ] `buy_and_hold.CONFIGS` 루프로 자동 등록:
  ```python
  for config in buy_and_hold.CONFIGS:
      STRATEGY_RUNNERS[config.strategy_name] = buy_and_hold.create_runner(config)
  ```
- [ ] `--strategy` choices는 `STRATEGY_RUNNERS.keys()` 기반이므로 자동 갱신

#### 1.5 `types.py` — docstring 업데이트

- [ ] 모듈 docstring에서 `BuyAndHoldResultDict` 참조 제거
- [ ] `SingleBacktestResult.strategy_name` 주석에 `buy_and_hold_qqq`, `buy_and_hold_tqqq` 추가

#### 1.6 `conftest.py` — mock fixture 업데이트

- [ ] `mock_results_dir`에서:
  - `buy_and_hold_dir` → `buy_and_hold_qqq_dir` + `buy_and_hold_tqqq_dir`
  - `BUY_AND_HOLD_RESULTS_DIR` 패치 → `BUY_AND_HOLD_QQQ_RESULTS_DIR` + `BUY_AND_HOLD_TQQQ_RESULTS_DIR` 패치
  - return dict 키 업데이트
- [ ] `mock_storage_paths`에서: 동일 변경

#### 1.7 `test_strategy.py` — 테스트 업데이트 및 추가

- [ ] `TestRunBuyAndHold.test_normal_execution`: `summary["strategy"]` 검증 제거
- [ ] `TestRunSingle.test_buy_and_hold_run_single_returns_result` → `create_runner` 기반으로 변경:
  - `BuyAndHoldConfig`로 테스트 config 생성
  - `runner = buy_and_hold.create_runner(config)`
  - `result.strategy_name == "buy_and_hold_qqq"` 등 검증
- [ ] TQQQ B&H runner 테스트 추가 (`test_buy_and_hold_tqqq_run_single_returns_result`)
- [ ] `CONFIGS` 정합성 테스트 추가 (`test_configs_completeness`):
  - CONFIGS에 최소 2개 항목
  - strategy_name 유일성
  - display_name 유일성

---

### Phase 2 — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - `BuyAndHoldResultDict` 참조 제거
  - `BuyAndHoldConfig`, `CONFIGS`, `create_runner` 문서화
  - 전략 식별 상수 → CONFIGS 기반으로 설명 변경
  - `buy_and_hold_tqqq` 추가 설명
- [ ] `CLAUDE.md` (루트) 디렉토리 구조 업데이트:
  - `buy_and_hold/` → `buy_and_hold_qqq/` + `buy_and_hold_tqqq/`
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Buy & Hold 팩토리 패턴 도입 + TQQQ Buy & Hold 전략 추가
2. 백테스트 / create_runner 팩토리로 Buy & Hold 전략 확장 (QQQ + TQQQ)
3. 백테스트 / Buy & Hold 전략 Config 기반 팩토리 전환 + TQQQ 합성데이터 벤치마크
4. 백테스트 / BuyAndHoldConfig + create_runner 팩토리 도입으로 멀티 티커 B&H 지원
5. 백테스트 / Buy & Hold 구조 개선: 팩토리 패턴 + TQQQ 벤치마크 전략 추가

## 7) 리스크(Risks)

1. **기존 결과 폴더 전환**: `storage/results/backtest/buy_and_hold/` → 더 이상 사용하지 않음. 사용자가 수동 삭제 후 재실행 필요. 대시보드 자동탐색 시 오래된 폴더가 남아있으면 혼동 가능.
   - 완화: `--strategy all` 재실행으로 새 폴더 자동 생성

2. **CLI 인자 변경**: `--strategy buy_and_hold` → `--strategy buy_and_hold_qqq`. 기존 자동화 스크립트가 있다면 수정 필요.
   - 완화: 기본값 `all`을 사용하는 경우 영향 없음

3. **TQQQ 합성 데이터 부재**: `TQQQ_synthetic_max.csv`가 없으면 TQQQ B&H 실행 시 FileNotFoundError.
   - 완화: 기존 버퍼존 전략도 동일 데이터를 사용하므로 이미 알려진 선행 조건

## 8) 메모(Notes)

- Phase 0 불필요 판단: 핵심 계산 로직(매수/에쿼티) 변경 없음. `strategy` 필드 제거는 편의 기능 변경이지 정책/인바리언트 변경이 아님.
- `BuyAndHoldConfig`는 `frozen=True`로 불변 보장
- 향후 SPY, VOO 등 추가 시 `CONFIGS`에 한 줄 추가 + `common_constants.py`에 결과 디렉토리 추가만 필요

### 진행 로그 (KST)

- 2026-02-20 17:00: 계획서 작성 완료 (Draft)
