# Implementation Plan: EMA 계산 경로 완전 제거

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-08-30 09:43
**마지막 업데이트**: 2026-08-30 10:37
**관련 범위**: 백테스트(analysis, constants, types, strategies, engines, walkforward, runners), live(cli, chart_data), scripts, tests
**관련 문서**: 루트 `CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `src/live/CLAUDE.md`, `tests/CLAUDE.md`, `docs/research/전략_검증_보고서.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 `/impl-plan` 스킬을 따릅니다.

- 품질 검증 명령은 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `ma_type` 파라미터와 EMA 계산 분기를 코드베이스에서 완전히 제거하여, 이동평균이 **SMA 한 가지만** 존재하도록 만든다.
- [x] 목표 2: 제거 이후 EMA 경로가 되살아나지 않도록 계약 테스트로 고정한다.
- [x] 목표 3: 백테스트 산출물(`summary.json`의 `params`)에서 `ma_type` 키를 제거하고, 관련 문서를 실제 코드와 일치시킨다.

## 2) 비목표(Non-Goals)

- **백테스트 수치 변경 없음.** 이미 SMA로 계산되고 있으므로 이 작업으로 결과값은 바뀌지 않는다. 바뀌는 것은 `summary.json`의 **스키마(`params.ma_type` 키 소멸)** 뿐이다.
- **`storage/results/` 재생성은 이 계획의 범위가 아니다.** SMA 전환(`f836ab5`)에서 이미 필요해진 별도 작업이며, 본 작업 완료 후 실행한다(§8 Notes에 목록).
- `ma_window`(200)를 비롯한 전략 파라미터 변경
- `live` 알림 시스템 재설계 및 알림 전용 프로젝트 분리
- verify-lab 리포 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`f836ab5`에서 기본값을 SMA로 전환할 때, 사용자 결정에 따라 **`ma_type` 파라미터 자체는 남겨두었다**(테스트 15곳 재작성 비용 회피). 그 결과 다음 상태가 되었다.

- 프로덕션 계산 경로는 100% SMA이지만, `Literal["ema", "sma"]` 타입과 `elif ma_type == "ema"` 분기가 그대로 살아 있다.
- 값이 사실상 하나뿐인 파라미터가 함수 시그니처와 두 개의 설정 dataclass에 남아 있다.
- 테스트 6곳이 여전히 `ma_type="ema"`를 명시하여, **프로덕션이 쓰지 않는 경로를 검증**하고 있다.

이 프로젝트는 이동평균을 SMA 한 가지로 확정했다(근거: `docs/research/전략_검증_보고서.md` 부록 G, `src/qbt/backtest/CLAUDE.md` 「1-1」). **선택지가 없는 파라미터는 파라미터가 아니므로 제거한다.**

### 사용자 결정 (2026-08-30)

| 항목 | 결정 |
| --- | --- |
| 제거 범위 | **완전 제거** — `ma_type` 파라미터·필드·상수를 모두 삭제 |
| 결과 파일 표기 | **남기지 않음** — `summary.json`의 `params.ma_type`도 삭제. 과거 EMA 결과는 git history(`f836ab5` 이전)가 보관 |

### 사전 조사 결과 (수치)

| 항목 | 수 | 비고 |
| --- | --- | --- |
| `add_single_moving_average` 호출 | **30곳** | 이 중 `ma_type` 인자를 넘기는 곳 **25곳** |
| 인자 없이 호출(수정 불필요) | 4곳 | `test_analysis.py` 3곳, `test_integration.py` 1곳 |
| `DEFAULT_BUFFER_MA_TYPE` 참조 | 정의 1 + 사용 10곳 | src 6, tests 4 |
| `ma_type` 필드/키 참조 | 필드 정의 2, params 기록 2, 캐시 키 1, docstring 3 | — |
| **대시보드(`scripts/backtest/app_*.py`)의 `ma_type` 참조** | **0곳** | **결과 스키마를 바꿔도 대시보드는 깨지지 않음** |
| `"지원하지 않는 ma_type"` ValueError 테스트 | **0곳** | 분기 삭제 시 깨지는 테스트 없음 |

**orphan import 판정** (본 변경으로 미사용이 되는 것만 정리한다):

| 파일 | `Literal` 사용 | 조치 |
| --- | --- | --- |
| `analysis.py` | L36이 유일 | **import 삭제** |
| `strategies/buffer_zone.py` | L125가 유일 | **import 삭제** |
| `portfolio_types.py` | L80 `signal_state`에서도 사용 | **import 유지** |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」, 「패키지 간 의존 관계」
- `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md` — 백테스트 도메인 규칙
- `src/live/CLAUDE.md` — **live 수정 원칙**(아래 주의 참고)
- `tests/CLAUDE.md` — 테스트 작성 규칙
- `.claude/rules/python.md` — 타입 힌트·Docstring·주석 규칙

> **[주의] live 패키지 수정에 대하여**: `src/live/CLAUDE.md`는 "QBT 본체 수정 금지"를 규정하나, 이번 작업은 **반대 방향**이다. qbt의 `add_single_moving_average` 시그니처가 바뀌므로 이를 호출하는 live 2곳이 함께 수정되지 않으면 **live가 즉시 깨진다.** 루트 `CLAUDE.md` 「리팩토링 시 영향도 고려」가 정한 대로 동반 수정한다.

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `add_single_moving_average`에서 `ma_type` 파라미터와 EMA 분기가 제거됨
- [x] `DEFAULT_BUFFER_MA_TYPE` 상수, `AssetSlotConfig.ma_type`, `BufferZoneConfig.ma_type` 필드가 제거됨
- [x] `ma_type` 인자를 넘기던 호출 25곳이 모두 정리됨 (src 7 + live 2 + scripts 2 + tests 14)
- [x] `summary.json`의 `params`에서 `ma_type` 키가 제거됨 (`runners.py`, `portfolio_engine.py`)
- [x] EMA 경로 부활을 막는 계약 테스트가 존재함
- [x] orphan `Literal` import 2곳 정리 (`analysis.py`, `buffer_zone.py`)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 `poetry run black .`)
- [x] 문서 업데이트 여부 명시 — `README.md` / `docs/COMMANDS.md` 각각 변경 여부 기록
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (제거 결정과 이유를 `docs/research/전략_검증_보고서.md` 부록 G에 추기, 운영 규칙은 `src/qbt/backtest/CLAUDE.md` 「1-1」 갱신)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**src/qbt/ — 9파일**

| 파일 | 위치 | 변경 |
| --- | --- | --- |
| `backtest/analysis.py` | L14 | `from typing import Literal` 삭제 (orphan) |
| | L36 | `ma_type` 파라미터 삭제 |
| | L50 | docstring의 `ma_type` 항목 삭제 |
| | L61 | 로그 문자열에서 `type={ma_type}` 제거 |
| | L72~84 | `if/elif/else` 분기 → `rolling(window).mean()` 단일 경로. **`ValueError("지원하지 않는 ma_type")` 삭제** |
| `backtest/constants.py` | L32 | `DEFAULT_BUFFER_MA_TYPE` 삭제 |
| `backtest/portfolio_types.py` | L108, L121 | docstring + `ma_type` 필드 삭제 (`Literal` import는 L80이 쓰므로 유지) |
| `backtest/strategies/buffer_zone.py` | L12, L125 | `Literal` import(orphan) + `ma_type` 필드 삭제 |
| `backtest/strategy_registry.py` | L81, L86 | docstring + 위치 인자 `slot.ma_type` 제거 |
| `backtest/runners.py` | L125, L159 | 호출 인자 제거 + **`params_json`의 `"ma_type"` 키 삭제** |
| `backtest/walkforward.py` | L35, L305, L690, L758 | import + 호출 인자 3곳 제거 |
| `backtest/engines/backtest_engine.py` | L31, L474, L570 | import + 호출 인자 2곳 제거 |
| `backtest/engines/portfolio_engine.py` | L105, L512 | **캐시 키에서 `::{slot.ma_type}` 제거** + `params_json` 키 삭제 |

**src/live/ — 2파일** (동반 수정, §3 주의 참고)

| 파일 | 위치 | 변경 |
| --- | --- | --- |
| `live/cli.py` | L789 | `ma_type=slot.ma_type` 인자 제거 |
| `live/chart_data.py` | L90 | 동일 |

**scripts/ — 1파일**

| 파일 | 위치 | 변경 |
| --- | --- | --- |
| `backtest/run_param_plateau_all.py` | L177, L251 | `ma_type="sma"` 인자 제거 |

**tests/ — 6파일**

| 파일 | 위치 | 변경 |
| --- | --- | --- |
| `test_ma_type_policy.py` | 전체 | **재작성.** 선언 검증 3건(상수·슬롯·설정 기본값)은 대상이 사라지므로 삭제. 계산 검증 2건은 인자 없이 유지 + 파라미터 부활 방지 테스트 추가 |
| `test_walkforward_schedule.py` | L139, L149, L187, L229 | `DEFAULT_BUFFER_MA_TYPE` import·인자 제거 |
| | L281, L312, L313, L361, L362 | `ma_type="ema"` 인자 제거 (5곳) |
| `test_buffer_zone_run.py` | L317, L383 | `ma_type="ema"` 인자 제거 |
| `test_buffer_zone_execution_rules.py` | L673, L731, L772 | `ma_type="ema"` 인자 제거 |
| `test_buffer_zone.py` | L476, L622, L667 | `assert "ma_type" in result.params_json` 삭제 |
| `test_portfolio_backtest_scenarios.py` | L650, L661 | `ma_type="sma"` 인자 제거 + 주석 조정 |

> `test_analysis.py`(L56·L91·L115)와 `test_integration.py`(L77)는 이미 인자 없이 호출하므로 **수정 불필요**.

**문서 — 3파일**

| 파일 | 변경 |
| --- | --- |
| `src/qbt/backtest/CLAUDE.md` | L37 상수 목록에서 `DEFAULT_BUFFER_MA_TYPE` 삭제 / L51 "단일 이동평균(SMA/EMA) 계산" → SMA 단일 표기 / L101 슬롯 파라미터에서 `ma_type` 삭제 / 「1-1」 절의 "`ma_type` 파라미터에 `"ema"`가 남아 있으나" 문장 갱신 |
| `docs/research/전략_검증_보고서.md` | 부록 G에 "G.6 EMA 계산 경로 제거" 추기 |
| `src/qbt/CLAUDE.md` | L32는 유형 언급이 없어 **변경 불필요** (확인만) |

- `README.md`: **변경 없음 예상** — EMA/SMA 및 `ma_type` 언급이 없음을 최종 Phase에서 재확인
- `docs/COMMANDS.md`: **변경 없음 예상** — 실행 명령어·CLI 옵션이 바뀌지 않음

### 데이터/결과 영향

- **백테스트 수치는 바뀌지 않는다.** 이미 SMA로 계산 중이며 이 작업은 계산 경로를 건드리지 않는다.
- **`summary.json` 스키마가 바뀐다** — `params.ma_type` 키가 사라진다. 대시보드는 이 키를 읽지 않으므로(조사 결과 참조 0곳) 표시 오류는 발생하지 않는다. 다만 **기존 결과 파일과 신규 결과 파일의 스키마가 달라지므로**, 본 작업 후 §8의 재실행으로 통일한다.
- `portfolio_engine.py` L105의 **시그널 캐시 키 형식이 바뀐다**. 캐시는 실행 중에만 유지되는 in-memory 구조이므로 영속 데이터 영향은 없다.

## 6) 단계별 계획(Phases)

### Phase 0 — 계약 고정(레드)

> 해당 사유: **에러 처리 정책 변경**(`ValueError("지원하지 않는 ma_type")` 삭제)과 **공개 함수 시그니처 변경**에 해당하므로 Phase 0을 둔다.

**작업 내용**:

- [x] `tests/qbt/test_ma_type_policy.py`를 제거 후 형태로 재작성
      - 삭제: `DEFAULT_BUFFER_MA_TYPE == "sma"`, `slot.ma_type == "sma"`, `config.ma_type == "sma"` (검증 대상이 사라짐)
      - 유지: 이동평균 계산 결과가 SMA와 일치 / 워밍업 구간이 NaN — **단, `ma_type` 인자 없이 호출**
      - 추가: `inspect.signature(add_single_moving_average)`에 `ma_type`이 **없음**을 검증 (이 시점 레드)
- [x] 이 시점의 레드/그린 상태를 진행 로그에 기록

---

### Phase 1 — qbt 코어에서 제거(그린 유지)

**작업 내용**:

- [x] `analysis.py` — 파라미터·EMA 분기·ValueError·docstring·로그·orphan import 정리
- [x] `constants.py` — `DEFAULT_BUFFER_MA_TYPE` 삭제
- [x] `portfolio_types.py` / `strategies/buffer_zone.py` — 필드 삭제 (+ buffer_zone의 orphan `Literal` import)
- [x] `strategy_registry.py` / `runners.py` / `walkforward.py` / `engines/backtest_engine.py` / `engines/portfolio_engine.py` — 호출 인자·import·캐시 키·params_json 정리
- [x] Phase 0 테스트 그린 전환 확인

---

### Phase 2 — live · scripts · 나머지 테스트 정리(그린 유지)

**작업 내용**:

- [x] `src/live/cli.py` L789, `src/live/chart_data.py` L90 인자 제거
- [x] `scripts/backtest/run_param_plateau_all.py` L177·L251 인자 제거
- [x] 테스트 5파일의 `ma_type` 인자·import·assert 정리 (§5 표 참조)
- [x] 전체 테스트 실행하여 회귀 없음 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 4곳 갱신 (L37 / L51 / L101 / 「1-1」 절)
- [x] `docs/research/전략_검증_보고서.md` 부록 G에 「G.6 EMA 계산 경로 제거」 추기 — 제거 결정·범위·`params.ma_type` 소멸 사실
- [x] `src/qbt/CLAUDE.md` 변경 불필요 확인
- [x] `README.md` / `docs/COMMANDS.md` 변경 여부 최종 확인 및 기록
- [x] 잔여 `ema` 문자열 전수 확인 (`grep -rni "ema" src/ scripts/ --include=*.py`) — 검색 결과가 비어야 한다
- [x] 자동 포맷 적용 — `poetry run black .`
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1030, failed=0, skipped=0) — Ruff/PyRight/Pytest 전부 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / EMA 계산 경로 완전 제거 — ma_type 파라미터 삭제
2. 백테스트 / 이동평균을 SMA 단일 경로로 단순화 (선택지 없는 파라미터 제거)
3. 백테스트 / ma_type 파라미터·상수·필드 제거 + 결과 스키마 정리
4. 백테스트 / EMA 분기 제거 및 계약 테스트 추가 (동작 동일)
5. 백테스트 / 이동평균 유형 파라미터 폐기 — SMA 확정 반영

## 7) 리스크(Risks)

| 리스크 | 완화책 |
| --- | --- |
| **live 패키지 동반 파손** — qbt 시그니처 변경이 live 2곳을 즉시 깨뜨린다 | Phase 2에서 반드시 함께 수정한다. `tests/live/` 전체 통과를 그린 조건에 포함 |
| **`summary.json` 스키마 변경** | 대시보드 참조 0곳을 사전 확인했다. 기존 결과와 스키마가 섞이는 문제는 §8 재실행으로 해소 |
| `test_ma_type_policy.py`가 통째로 무의미해질 수 있음 | 선언 검증만 삭제하고 **계산 계약 + 파라미터 부활 방지**로 재구성한다. 파일을 지우면 "SMA만 쓴다"를 고정하는 장치가 사라진다 |
| 캐시 키 변경으로 인한 오동작 | in-memory 캐시이며 실행 단위로 초기화된다. 포트폴리오 백테스트 전체 테스트로 확인 |
| 호출처 25곳 중 누락 발생 | 마지막 Phase에서 `grep -rni "ema" src/ scripts/ --include=*.py` 결과가 **완전히 비어야 함**을 체크리스트로 강제 |
| PyRight strict에서 orphan import 미검출 | Ruff가 `F401`로 잡는다. `validate_project.py`에 포함되어 있음 |

## 8) 메모(Notes)

- **기준 커밋**: `f836ab5` (SMA 전환 완료 시점).
- **이 작업으로 백테스트 수치는 바뀌지 않는다.** 그러나 `f836ab5`의 SMA 전환 때문에 **결과 재생성은 이미 필요한 상태**다. 본 작업 완료 후 아래를 실행한다(순서 무관하나 4번을 마지막에 두면 `benchmark_qqq.json`이 최신 상태로 마감된다).

  | # | 스크립트 | 갱신 대상 | 현재 상태 |
  | --- | --- | --- | --- |
  | 1 | `run_single_backtest.py` | `results/backtest/` buffer_zone 12개 | 1개만 SMA, 11개 EMA |
  | 2 | `run_walkforward.py` | buffer_zone_tqqq · buffer_zone_qqq의 `walkforward_*` | 전부 EMA |
  | 3 | `run_param_plateau_all.py` | `results/backtest/param_plateau/` | 전부 EMA |
  | 4 | `run_portfolio_backtest.py` | `results/portfolio/` 36개 + `benchmark_qqq.json` | 1개만 SMA, 35개 EMA |

  `download_data.py`·`generate_synthetic.py`·`generate_daily_comparison.py`는 MA에 의존하지 않아 재실행 대상이 아니다.

- **[중요] 재실행 전에 `download_data.py`를 돌리지 않는다.** 주가 CSV는 현재 2026-08-21까지다. 데이터를 갱신한 뒤 재생성하면 결과 변화에 "MA 유형"과 "데이터 추가"라는 두 원인이 섞여 SMA 전환의 효과를 분리할 수 없게 된다. **현재 데이터로 기준을 통일한 뒤** 데이터 갱신은 별도로 수행한다.

- **현재 결과 폴더는 EMA/SMA가 혼재한다.** 특히 `results/backtest/buffer_zone_qqq/`는 같은 폴더 안에서 `signal.csv`·`equity.csv`·`trades.csv`·`summary.json`이 SMA(`f836ab5`)인 반면 `walkforward_*`·`wfo_windows_*`는 EMA(`ac230c9`)다. `app_walkforward.py`를 열면 두 기준이 섞여 표시된다.

- **`ma_type` 부활 방지 테스트를 두는 이유**: 파라미터를 제거해도 누군가 "옵션이 있으면 편하다"며 되살릴 수 있다. 이 프로젝트는 EMA/SMA 선택 자체를 과최적화 자유도로 카운트하므로(검증 보고서 §5.3), 선택지를 코드 수준에서 봉인하는 것이 결정의 일부다.

- **자체 검증 결과 (2026-08-30, 누락 점검)**:

  | 점검 항목 | 결과 |
  | --- | --- |
  | `AssetSlotConfig(...)` / `BufferZoneConfig(...)` 생성자에 `ma_type`을 넘기는 곳 | **1곳뿐** — `test_portfolio_backtest_scenarios.py:661`. §5 표에 이미 포함 |
  | `dataclasses.replace()`로 `ma_type`을 교체하는 곳 | **0곳** (`run_param_plateau_all.py`의 `replace`는 다른 필드만 다룸) |
  | `src/live/CLAUDE.md`의 `ma_type`·EMA 언급 | **없음** — live 문서 수정 불필요 |
  | `ma_col_name(window)` | `window`만 사용하므로 영향 없음 |
  | `analysis.py`의 `if window < 1` 검증 | **유지 대상** — 이번에 삭제하는 것은 `ma_type` ValueError 하나뿐 |

  프로덕션·테스트를 통틀어 **필드를 명시적으로 전달하는 지점이 1곳뿐**이므로, 필드 삭제로 인한 `TypeError` 전파 위험은 그 한 곳으로 한정된다.

### 진행 로그 (KST)

- 2026-08-30 09:43: 계획서 작성. 사전 조사 완료(`add_single_moving_average` 호출 30곳 중 인자 전달 25곳, 대시보드 `ma_type` 참조 0곳, ValueError 테스트 0곳, orphan `Literal` 2곳). 사용자 결정 2건 반영(완전 제거 / 결과 파일 표기 없음).
- 2026-08-30 09:47: 자체 검증 완료. 생성자 전달 1곳·`replace` 0곳·live 문서 무관을 확인하여 누락 없음을 확정.
- 2026-08-30 10:05: Phase 0 완료. `test_ma_type_policy.py` 재작성 — 시그니처 검증 1건 레드, 계산 검증 2건 그린.
- 2026-08-30 10:10: Phase 1 완료. qbt 코어 9파일 정리 후 `grep`으로 `ma_type` 완전 소멸 확인. Phase 0 테스트 그린 전환(3 passed).
- 2026-08-30 10:20: Phase 2 완료. **예상 밖 회귀 2건 발생 → 수정**(아래 항목 참조). 전체 1030 passed.
- 2026-08-30 10:37: 마지막 Phase 완료. 문서 4종 갱신, 부록 G.6 승격, 잔여 EMA 표현 12곳 정리, `black` 적용, `validate_project.py` 통과(1030/0/0). **상태 Done**.

### 계획 대비 실제 — 차이 기록

**① 예상 밖 회귀 2건 (Phase 2)**

계획서는 `test_buffer_zone_execution_rules.py`의 3곳을 "`ma_type="ema"` 인자 제거"로만 봤으나, 인자를 지우자 두 테스트가 실패했다.

- `test_backtest_end_consistency`, `test_first_valid_signal_detection`
- 원인: 두 테스트가 7~10행의 짧은 합성 데이터를 `window=3`으로 쓰면서 **EMA의 "1행째부터 값이 나옴" 특성에 의존**하고 있었다. SMA로는 앞 2행이 NaN이 되어 **첫 유효 행에서 이미 가격이 밴드 위**에 있어 상향돌파가 감지되지 않았다.
- 조치: 앞부분에 평탄 구간(종가 90 반복)을 추가해 워밍업 이후 밴드 아래에서 출발하도록 데이터를 보강했다. 검증 의도(마지막 날 포지션 유지 / 첫 유효 구간 신호 감지)는 그대로 유지된다.
- 이 사실은 부록 G.6에 승격했다.

**② 잔여 EMA 표현 12곳 (마지막 Phase)**

계획서의 "잔여 `ema` 문자열 전수 확인" 체크가 실제로 누락을 잡아냈다. `ma_type` 식별자는 모두 제거됐으나 주석·docstring에 EMA 서술이 남아 있었다.

- `walkforward.py` 6곳 ("EMA 연속성 보장" → "MA 연속성 보장", EMA 재귀 특성 설명 → 워밍업 설명)
- `backtest_engine.py` 3곳 — 그중 **L470은 실행 시 출력되는 로그**(`"이동평균 사전 계산 (EMA): ..."`)여서 사실과 다른 값을 찍고 있었다
- `analysis.py` 모듈 docstring, `portfolio_types.py` "EMA-200 시그널 소스"

**③ `docs/COMMANDS.md` 변경 발생**

계획서는 "변경 없음 예상"이라 적었으나, L44의 슬롯 파라미터 나열에 `ma_type`이 포함되어 있어 **실제로는 수정했다**. `README.md`와 `docs/DESIGN_QBT_LIVE_FINAL.md`는 예상대로 변경 없음.

---
