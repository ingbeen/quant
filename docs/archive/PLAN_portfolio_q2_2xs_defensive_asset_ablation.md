# Implementation Plan: Q-2-2XS 방어자산 대조 실험 2종 추가 (현금안 / 전량주식안)

> **아카이브됨 (2026-08-23)**: 계획대로 구현·실행하여 결론을 얻은 뒤 실험 2종을 제거했다.
> 두 실험 모두 Calmar 0.48로 기존 Q-2-2XS(0.59)보다 열등하여 유지할 이유가 없었다.
> 성과 수치는 `docs/strategy_validation_report.md` 부록 D.8에 기록되어 있다.
> 아래 본문의 체크리스트/수치는 제거 시점 이전 기준이며, 참고용 이력으로만 읽는다.

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

**작성일**: 2026-08-23 12:07
**마지막 업데이트**: 2026-08-23 12:15
**관련 범위**: backtest (portfolio_configs), tests
**관련 문서**: [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] 목표 1: 기존 `portfolio_q2_2xs`의 방어자산(GLD 15% + TLT 15%)을 **현금 30%** 로 대체한 실험 설정을 추가한다.
- [x] 목표 2: 동일 30%를 **주식(SSO/QLD)에 전량 배분**한 실험 설정(SSO 50% / QLD 50%)을 추가한다.
- [x] 목표 3: 기존 `portfolio_q2_2xs`를 포함한 3개 실험이 동일 기간에서 나란히 비교되도록 `PORTFOLIO_CONFIGS`에 등록한다.
- [x] 목표 4: 신규 실험 2종의 자산 구성 계약(비중 합, 자산 집합, 시그널/매매 경로)을 테스트로 고정한다.

## 2) 비목표(Non-Goals)

- **포트폴리오 엔진 로직 변경 없음**: 현금 잔여분 유지·리밸런싱은 엔진에 이미 구현되어 있으며 본 작업에서 손대지 않는다.
- **현금 이자(무위험 수익) 반영 없음**: 엔진은 미투자 현금에 이자를 붙이지 않는다. 이 정책 변경은 본 plan의 범위 밖이며, 필요 시 별도 plan으로 다룬다.
- **기존 `portfolio_q2_2xs` 설정 수정 없음**: 대조군으로 보존한다. `src/live/`의 `LIVE_PORTFOLIO_ID`가 이 실험명을 참조하므로 수정 시 실매매 구성까지 바뀐다.
- **`src/live/` 변경 없음**: 신규 실험은 백테스트 비교 목적이며 실매매 대상이 아니다.
- **백테스트 실행 및 결과 해석 없음**: `scripts/` 스크립트 실행은 사용자가 수행한다. 본 plan은 설정 추가까지만 다룬다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

[docs/research/RESEARCH_q2_2xs_qqq_correlation.md](../research/RESEARCH_q2_2xs_qqq_correlation.md)는 Q-2-2XS의 낮은 QQQ 상관(일별 0.708)이
자산 분산(GLD·TLT 30%)이 아니라 **하락장에서 주식을 비우는 타이밍 신호**에서 발생했다고 결론지었다.
해당 연구는 "방어자산 30%의 상관 저감 효과는 관측되지 않았다"고 기록한다.

그러나 상관계수는 방어자산이 기여할 수 있는 여러 효과 중 하나일 뿐이며,
**수익률·최대낙폭 관점에서 GLD·TLT 30%가 실제로 기여하는 몫**은 아직 분리 측정되지 않았다.

이를 확인하려면 동일한 주식 타이밍 로직을 유지한 채 방어자산 슬롯만 교체한 대조군이 필요하다.

| 실험 | 방어자산 30% 처리 | 확인하려는 것 |
| --- | --- | --- |
| 기존 `portfolio_q2_2xs` | GLD 15% + TLT 15% (B&H) | 기준선 |
| 신규 (현금안) | 현금 30% (무수익) | 방어자산을 "아무것도 안 하는 자산"으로 바꿨을 때의 손실분 |
| 신규 (전량주식안) | SSO/QLD에 흡수 (각 50%) | 방어자산 대신 주식 비중을 키웠을 때의 수익·낙폭 변화 |

세 실험의 차이가 곧 방어자산 30%의 순기여분이다.

### 사전 확인된 사실 (설계 근거)

- 목표 비중 합이 1.0 미만이면 잔여분이 현금으로 유지된다 — [portfolio_types.py:130](../../src/qbt/backtest/portfolio_types.py#L130), [portfolio_data.py:60-65](../../src/qbt/backtest/engines/portfolio_data.py#L60-L65)
- 리밸런싱 목표 금액은 `현금 포함 총 에쿼티 × target_weight`로 계산되므로, 현금 잔여분이 있어도 주식 비중이 목표로 복원된다 — [portfolio_rebalance.py:111](../../src/qbt/backtest/engines/portfolio_rebalance.py#L111)
- 신규 2종의 유효 시작일은 SSO/QLD 데이터 시작일(2006-06-21)에 의해 결정되며, GLD(2004-11-18)·TLT(2002-07-30)는 그보다 이르다. 따라서 **방어자산 제거로 백테스트 기간이 달라지지 않아** 기존 실험과 동일 기간 비교가 성립한다.
- `benchmark_qqq.json` 기준일은 전체 configs의 유효 시작일 최솟값 기반이며, 그 최솟값은 `portfolio_d1`(QQQ 단일)이 결정한다. 신규 실험 추가로 벤치마크 기준일은 변하지 않는다 — [run_portfolio_backtest.py:572-577](../../scripts/backtest/run_portfolio_backtest.py#L572-L577)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md) (루트)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/CLAUDE.md](../CLAUDE.md)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 신규 실험 2종이 `PORTFOLIO_CONFIGS`에 등록되고 `get_portfolio_config()`로 조회된다
- [x] 기존 `portfolio_d1` / `portfolio_q2` / `portfolio_q2_2xs` 설정이 변경되지 않았다
- [x] 회귀/신규 테스트 추가
- [x] `poetry run python validate_project.py` 통과 (passed=1033, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(README.md / `docs/COMMANDS.md` / CLAUDE.md / plan 등 — 각각 변경 여부 명시)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_configs.py`: 신규 config 2개 정의 + `PORTFOLIO_CONFIGS` 등록 + 모듈 docstring의 Q 시리즈 설명 보완
- `tests/qbt/test_portfolio_configs.py`: 신규 실험 2종 계약 테스트 추가 + 모듈 docstring 테스트 계약 목록 갱신
- `README.md`: **변경 없음** (실험 목록을 기재하지 않음)
- `docs/COMMANDS.md`: **변경 없음** (`--experiment` 값은 `PORTFOLIO_CONFIGS` 참조로만 안내하며 실험명을 하드코딩하지 않음 — [docs/COMMANDS.md:50](../COMMANDS.md))
- `src/qbt/backtest/CLAUDE.md`: **변경 없음** (문서 내구성 원칙에 따라 실험 목록을 문서에 복제하지 않고 `portfolio_configs.py` 참조로 처리 중)

### 신규 실험 정의

| 항목 | 현금안 | 전량주식안 |
| --- | --- | --- |
| `experiment_name` | `portfolio_q2_2xs_cash` | `portfolio_q2_2xs_full` |
| `display_name` | `Q-2-2XS-CASH (SSO 35% / QLD 35% / 현금 30%)` | `Q-2-2XS-FULL (SSO 50% / QLD 50%)` |
| 자산 슬롯 | sso 0.35, qld 0.35 | sso 0.50, qld 0.50 |
| target_weight 합 | 0.70 (잔여 0.30 = 현금) | 1.00 |
| 전략 | 두 슬롯 모두 `buffer_zone` (기본값) | 동일 |
| 시그널 / 매매 경로 | SPY→SSO, QQQ→QLD (기존 Q-2-2XS와 동일) | 동일 |
| `total_capital` | `DEFAULT_INITIAL_CAPITAL` | 동일 |

버퍼존 파라미터(`ma_window`, `buy/sell_buffer_zone_pct`, `hold_days`, `ma_type`)는 기존 Q-2-2XS와 동일하게 `AssetSlotConfig` 기본값을 사용한다. 대조 실험의 목적상 **주식 타이밍 로직은 3개 실험에서 동일해야** 하기 때문이다.

### 데이터/결과 영향

- 출력 스키마 변경 없음 (기존 포트폴리오 결과 컬럼 규칙 그대로)
- 신규 결과 디렉토리 2개 생성: `storage/results/portfolio/portfolio_q2_2xs_cash/`, `.../portfolio_q2_2xs_full/`
- 기존 실험 결과 파일 덮어쓰기 없음
- `benchmark_qqq.json` 기준일 변화 없음 (Context의 사전 확인된 사실 참고)
- 대시보드(`app_portfolio_backtest.py`, `app_portfolio_debug.py`)는 `PORTFOLIO_CONFIGS`를 순회하여 결과 폴더를 탐색하므로, 백테스트 실행 후 신규 실험이 자동 노출된다 — 코드 변경 불필요

## 6) 단계별 계획(Phases)

### Phase 0 — 신규 실험 계약을 테스트로 먼저 고정(레드)

> 신규 실험의 자산 구성/비중은 이후 모든 비교 결과의 전제가 되는 계약이므로 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `tests/qbt/test_portfolio_configs.py` 모듈 docstring의 테스트 계약 목록에 신규 항목 추가
- [x] `portfolio_q2_2xs_cash` 계약 테스트 추가 (레드 허용)
  - [x] target_weight 합 == 0.70 (현금 30% 확보)
  - [x] asset_ids == {"sso", "qld"} (방어자산 미포함)
  - [x] 두 슬롯 모두 `strategy_id == "buffer_zone"`
  - [x] 시그널/매매 경로가 기존 Q-2-2XS와 동일 (SPY→SSO, QQQ→QLD)
- [x] `portfolio_q2_2xs_full` 계약 테스트 추가 (레드 허용)
  - [x] target_weight 합 == 1.00, 각 슬롯 0.50
  - [x] asset_ids == {"sso", "qld"}
  - [x] 두 슬롯 모두 `strategy_id == "buffer_zone"`
- [x] 3개 실험의 주식 타이밍 파라미터 동일성 테스트 추가 (`ma_window`/버퍼/`hold_days`/`ma_type`가 sso·qld 슬롯에서 세 실험 모두 일치)
- [x] 기존 `portfolio_q2_2xs` 계약 테스트가 그대로 통과하는지 확인 (대조군 보존 회귀 방지)

**Validation**:

- [x] `poetry run pytest tests/qbt/test_portfolio_configs.py` — 신규 테스트가 `get_portfolio_config` ValueError로 실패(레드)하고, 기존 테스트는 통과 (실행 결과: failed=6, passed=11)

---

### Phase 1 — 신규 config 정의 및 등록(그린 전환)

**작업 내용**:

- [x] `src/qbt/backtest/portfolio_configs.py`에 `_CONFIG_Q2_2XS_CASH` 정의
- [x] `src/qbt/backtest/portfolio_configs.py`에 `_CONFIG_Q2_2XS_FULL` 정의
- [x] `PORTFOLIO_CONFIGS`에 두 config 등록 (기존 항목 순서 유지, 뒤에 추가)
- [x] 모듈 docstring의 "Q 시리즈" 설명에 방어자산 대조 실험 취지를 한 줄 보완 (구체 수치·실험 ID 나열은 문서 내구성 원칙에 따라 지양)
- [x] 미사용 import 발생 여부 확인 (본 변경으로 생긴 orphan만 정리)

**Validation**:

- [x] `poetry run pytest tests/qbt/test_portfolio_configs.py` — Phase 0 테스트 전부 통과(그린) (실행 결과: passed=17, failed=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 문서 업데이트 여부 최종 확인
  - [x] `README.md`: 변경 없음 확인
  - [x] `docs/COMMANDS.md`: 변경 없음 확인 (실행 명령어/CLI 옵션 변화 없음)
  - [x] `src/qbt/backtest/CLAUDE.md`: 변경 없음 확인
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1033, failed=0, skipped=0) — Ruff/PyRight/Pytest 전부 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / Q-2-2XS 방어자산 대조 실험 2종 추가 (현금 30% / 주식 100%)
2. 백테스트 / 방어자산 기여도 분리 측정용 포트폴리오 실험 설정 추가
3. 백테스트 / 포트폴리오 실험에 현금안·전량주식안 대조군 추가 + 계약 테스트 보강
4. 백테스트 / GLD·TLT 30% 대체 실험 설정 추가 (엔진 변경 없음)
5. 백테스트 / Q 시리즈 확장 — 방어자산 ablation 실험 설정 및 테스트 추가

## 7) 리스크(Risks)

| 리스크 | 완화책 |
| --- | --- |
| 현금 이자 0% 가정으로 현금안이 실제보다 불리하게 측정된다 | Non-Goals에 명시. 결과 해석 시 "이자 0% 하한선"임을 전제로 읽고, 필요하면 별도 plan에서 무위험 수익률 반영을 검토한다 |
| 기존 `portfolio_q2_2xs` 수정 시 `src/live/`의 `LIVE_PORTFOLIO_ID`가 참조하는 실매매 구성이 함께 바뀐다 | 기존 config를 건드리지 않고 신규 config만 추가. Phase 0에 대조군 보존 회귀 테스트 포함 |
| 신규 실험의 버퍼존 파라미터가 기존과 달라지면 방어자산 효과와 타이밍 파라미터 효과가 섞여 비교가 무의미해진다 | 세 실험의 sso·qld 슬롯 파라미터 동일성을 Phase 0 테스트로 고정 |
| 실험명 오타로 `--experiment` 실행이나 결과 폴더 탐색이 어긋난다 | `experiment_name`과 `result_dir`을 `_make_result_dir(experiment_name)` 패턴으로 일치시키고, 기존 config와 동일한 작성 규칙을 따른다 |

## 8) 메모(Notes)

### 사전 검증 기록 (임시 설정 기반, 공식 결과 아님)

계획 수립 단계에서 임시 config로 엔진 동작을 확인했다. **`storage/results/`에 저장되지 않은 스크래치 실행**이며, 공식 수치는 사용자가 `scripts/backtest/run_portfolio_backtest.py`를 실행한 결과를 기준으로 한다.

현금 30% 구성의 리밸런싱 동작 확인 (2006-06-21 ~ 2026-07-24, 5,054 거래일):

- 리밸런싱 체결 31회 (월간 정기 24회 + 일간 긴급 7회)
- 주식 2종 동시 보유일(3,929일) 기준 현금 비중: 평균 0.2829 / 최소 0.2264 / 최대 0.3609
- 비중 초과 시 매도(예: 2007-07-03 sso 0.369→0.350), 비중 미달 시 현금으로 매수(예: 2007-11-02 sso 0.316→0.349) 양방향 모두 정상 동작
- 현금 비중이 30%에 고정되지 않고 범위를 갖는 이유는 리밸런싱이 목표 대비 10%(월초)/20%(긴급) 편차 초과 시에만 발동하기 때문 (의도된 설계)

3개 구성 성과 미리보기 (동일 기간, 현금 이자 0% 가정):

| 구성 | CAGR | 총수익률 | MDD | 칼마 | 거래 | 리밸 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 기존 Q-2-2XS | 16.10% | 1,908.14% | -27.67% | 0.58 | 189 | 99 |
| 현금안 | 13.72% | 1,224.12% | -29.11% | 0.47 | 61 | 31 |
| 전량주식안 | 18.68% | 3,018.37% | -39.37% | 0.47 | 32 | 17 |

기존 Q-2-2XS 재현값이 `storage/results/portfolio/portfolio_q2_2xs/summary.json`의 공식 값(CAGR 16.10%, 총수익률 1908.14%, MDD -27.67%)과 일치하여 검증 환경의 정합성을 확인했다.

### 해석상 유의점

현금안은 수익률이 낮을 뿐 아니라 MDD도 기존보다 나빴다. 이는 GLD·TLT가 **상관 저감**에는 기여하지 않았더라도(연구 문서 결론) **낙폭 완충**에는 기여했음을 시사한다. 두 효과는 별개의 지표이므로 연구 문서 결론과 모순되지 않으며, 본 실험이 그 구분을 수치로 분리해 준다.

### 진행 로그 (KST)

- 2026-08-23 12:07: plan 최초 작성. 엔진 변경 불필요함을 코드 확인 + 임시 실행으로 검증 완료.
- 2026-08-23 12:10: Phase 0 완료. 신규 계약 테스트 6개 추가 → 레드 확인(failed=6, passed=11).
- 2026-08-23 12:13: Phase 1 완료. config 2종 정의 + PORTFOLIO_CONFIGS 등록 → 그린 전환(passed=17).
- 2026-08-23 12:15: 마지막 Phase 완료. `black .` 재포맷 대상 없음(147 files unchanged), `validate_project.py` passed=1033 / failed=0 / skipped=0. 상태 Done 확정.

---
