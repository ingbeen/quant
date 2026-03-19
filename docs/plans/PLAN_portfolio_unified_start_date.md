# Implementation Plan: 포트폴리오 실험 공통 시작일 정렬

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

**작성일**: 2026-03-19 00:00
**마지막 업데이트**: 2026-03-19 13:40
**관련 범위**: backtest, scripts
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md

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

- [ ] 포트폴리오 백테스트 7개 실험이 항상 동일한 시작일에서 출발하도록 구현한다.
- [ ] 글로벌 시작일 = 전체 7개 PORTFOLIO_CONFIGS 기준 유효 시작일의 최대값 (MA 워밍업 완료 후 가장 늦은 시작일)
- [ ] 단일 실험 실행 시에도 동일한 글로벌 시작일이 적용되어 전체 실험과 일관된 기간을 보장한다.

## 2) 비목표(Non-Goals)

- 개별 실험의 4P 파라미터 변경 없음
- 대시보드(`app_portfolio_backtest.py`) 코드 변경 없음
- 다른 백테스트 전략(buffer_zone, buy_and_hold 등) 변경 없음
- 시작일 고정 상수 하드코딩 (동적 계산 방식 사용)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- C-1 실험은 QQQ + TQQQ(합성) 데이터만 사용하여 1999년부터 시작됨
- A/B 시리즈 실험은 GLD를 포함하며 GLD 상장일(2004년 11월 18일) 이후부터만 시작 가능
- 각 실험의 시작일이 다르면 성과 지표(CAGR, MDD 등) 비교가 부적절함
- 예: C-1은 닷컴버블(2000~2002) 구간을 포함하고 A/B는 제외 → 단순 성과 비교 불가

### 현재 시작일 결정 로직

`portfolio_strategy.py`의 `run_portfolio_backtest()`에서:
1. 전 자산 trade_df의 날짜 교집합(`common_dates_set`) 계산
2. 교집합 날짜에서 MA 워밍업(200일 EMA 수렴) 완료 시점(`valid_start`) 결정
3. 해당 인덱스 이후 데이터만 사용

문제: C-1은 GLD가 없으므로 교집합이 1999년부터, 나머지는 2004년부터 → 시작일 상이

### 해결 방안

1. `portfolio_strategy.py`에 `compute_portfolio_effective_start_date(config)` 함수 추가
   - 해당 config의 데이터를 로딩하고 MA 워밍업 후 첫 유효 날짜 반환
2. `run_portfolio_backtest(config, start_date=None)` 파라미터 추가
   - `start_date`가 주어지면 `valid_start` 이후 추가로 해당 날짜 이후 데이터만 사용
3. `run_portfolio_backtest.py` (CLI)에서:
   - 전체 PORTFOLIO_CONFIGS 기준 각 실험의 유효 시작일 계산
   - max(유효 시작일) = 글로벌 시작일
   - 모든 실험에 해당 글로벌 시작일 전달

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md): 코딩 표준, 아키텍처 원칙
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): portfolio_strategy.py 설계 원칙
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md): CLI 계층 규칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족: 7개 실험이 동일한 시작일로 실행됨
- [x] 회귀/신규 테스트 추가: `start_date` 파라미터 계약 + `compute_portfolio_effective_start_date` 계약
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=378, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (CLAUDE.md: `portfolio_strategy.py` 섹션, `scripts/CLAUDE.md` 업데이트)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_strategy.py` — `start_date` 파라미터 + `compute_portfolio_effective_start_date` 함수 추가
- `scripts/backtest/run_portfolio_backtest.py` — 글로벌 시작일 계산 + 전달
- `tests/test_portfolio_strategy.py` — 신규 테스트 2개 추가
- `src/qbt/backtest/CLAUDE.md` — `portfolio_strategy.py` 섹션 업데이트

### 데이터/결과 영향

- 기존 A/B 시리즈 결과: 시작일 동일하거나 소폭 변동 가능 (MA 워밍업 기준으로 이미 2004년 시작)
- C-1 결과: 1999년 → 2004년으로 시작일 이동 → CAGR, MDD 수치 변경
- 실험 재실행 필요: `run_portfolio_backtest.py` 재실행하면 업데이트됨

## 6) 단계별 계획(Phases)

### Phase 0 — 계약/정책을 테스트로 먼저 고정 (레드)

> `start_date` 파라미터와 `compute_portfolio_effective_start_date` 함수가 아직 없으므로 레드 테스트.

**작업 내용**:

- [ ] `tests/test_portfolio_strategy.py`에 `TestStartDateConstraint` 클래스 추가
  - `test_start_date_filters_early_data`: `start_date` 이전 데이터가 equity_df에 포함되지 않음 검증
  - `test_start_date_is_none_uses_natural_start`: `start_date=None`이면 기존 동작 유지 검증
- [ ] `tests/test_portfolio_strategy.py`에 `TestComputeEffectiveStartDate` 클래스 추가
  - `test_returns_date_object`: 반환값이 `date` 객체인지 검증
  - `test_effective_start_is_after_ma_warmup`: 반환된 날짜가 MA 워밍업 완료 이후인지 검증

**Validation**: 의도적 실패(RED) — 구현 전이므로 ImportError 또는 TypeError 예상

---

### Phase 1 — 핵심 구현 (그린 유지)

**작업 내용**:

- [ ] `src/qbt/backtest/portfolio_strategy.py`에 `compute_portfolio_effective_start_date(config: PortfolioConfig) -> date` 추가
  - 전 자산 데이터 로딩 + 교집합 계산 + MA 워밍업 적용 후 첫 유효 날짜 반환
  - 내부 중복 로직은 기존 `run_portfolio_backtest()` 코드 재활용
- [ ] `run_portfolio_backtest(config, start_date: date | None = None)` 파라미터 추가
  - `valid_start` 필터링 이후, `start_date`가 주어지면 해당 날짜 이후 데이터만 사용
  - `start_date`가 `None`이면 기존 동작과 동일
- [ ] `scripts/backtest/run_portfolio_backtest.py`에 글로벌 시작일 계산 로직 추가
  - `PORTFOLIO_CONFIGS` 전체를 대상으로 각 실험의 유효 시작일 계산
  - `global_start_date = max(유효 시작일 목록)` 계산
  - 모든 `run_portfolio_backtest(config)` 호출에 `start_date=global_start_date` 전달
  - 로그: `global_start_date` 값 출력

**Validation** (그린 유지):
- Phase 0 테스트가 통과해야 함
- 기존 테스트가 모두 통과해야 함 (회귀 없음)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md`의 `portfolio_strategy.py` 섹션 업데이트
  - `run_portfolio_backtest` 시그니처에 `start_date` 파라미터 추가
  - `compute_portfolio_effective_start_date` 함수 문서화
- [ ] `scripts/CLAUDE.md`의 `run_portfolio_backtest.py` 설명 업데이트 (글로벌 시작일 계산 설명 추가)
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=378, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 실험 공통 시작일 정렬 (글로벌 start_date 계산 + 적용)
2. 백테스트 / 포트폴리오 C-1 시작일 보정 — 7개 실험 동일 기간 비교 보장
3. 백테스트 / portfolio_strategy에 start_date 파라미터 추가 + 글로벌 시작일 동기화
4. 백테스트 / 포트폴리오 실험 기간 정합성 개선 (run_portfolio_backtest start_date)
5. 백테스트 / compute_portfolio_effective_start_date 추가 + CLI 글로벌 시작일 적용

## 7) 리스크(Risks)

- C-1 기존 결과 파일(`storage/results/portfolio/portfolio_c1/`)이 변경됨 → 재실행 필요
- `compute_portfolio_effective_start_date()`가 `run_portfolio_backtest()` 내부 로직 일부를 중복 → 유지보수 부담. 단, 경량 함수이므로 허용 수준
- 글로벌 시작일 계산 시 전체 데이터 로딩(7개 config) → 실행 시간 약간 증가 (수초 수준, 허용 범위)

## 8) 메모(Notes)

- GLD 상장일: 2004-11-18 (NYSE Arca). MA-200 EMA 워밍업 후 실질 시작일은 약 2005년 중반 예상
- `compute_portfolio_effective_start_date()`는 데이터를 로딩하고 MA 계산까지 하므로 일부 연산 중복이 있음. 성능 트레이드오프 허용 (CLI 레벨에서만 호출)
- `start_date` 필터는 `common_dates_set` 교집합 후, MA 워밍업 후 적용 (순서 중요)
  - 즉: 교집합 → MA 워밍업 → `start_date` 필터 순

### 진행 로그 (KST)

- 2026-03-19 00:00: 계획서 작성 완료
- 2026-03-19 13:40: Phase 0~마지막 Phase 완료, validate_project.py passed=378, failed=0, skipped=0
