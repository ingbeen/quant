# Implementation Plan: 가격 반올림 자릿수 6→4 통일 (출력 표시 한정)

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

**작성일**: 2026-09-09 17:37
**마지막 업데이트**: 2026-09-09 17:37
**관련 범위**: backtest 도메인 상수, CLI 러너(단일·포트폴리오·WFO), 백테스트 엔진, 테스트
**관련 문서**: 루트 `CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, 전역 `~/.claude/rules/python.md`

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

- [x] 목표 1: 결과 파일에 저장되는 **가격 자릿수를 6자리에서 4자리로 낮춘다**. 전역 `~/.claude/rules/python.md` 가 정한 「가격은 어떤 경우에도 소수점 4자리를 넘기지 않는다」를 이 저장소의 출력 경로에 집행한다.
- [x] 목표 2: 자릿수를 **중앙 상수 `ROUND_PRICE` 하나로 일원화**한다. 상수를 우회해 숫자 `6` 을 직접 적은 4곳을 제거하고, 앞으로 자릿수를 고칠 때 누락되는 지점이 없게 만든다.
- [x] 목표 3: 이 변경이 **성과 지표를 한 자리도 바꾸지 않음을 실측으로 증명**한다. 재실행 전후 `summary.json` 의 CAGR·MDD·Calmar·총수익률·거래수를 기계로 대조한다.

## 2) 비목표(Non-Goals)

- **입력 데이터의 자릿수는 바꾸지 않는다.** `src/qbt/utils/stock_downloader.py` 의 `.round(6)` 과 `scripts/tqqq/generate_synthetic.py` 의 6자리 6곳(135·145·146·166·175·176행)은 그대로 둔다. 이 둘을 바꾸면 백테스트 입력값이 달라져 모든 성과 수치가 변하고 `docs/research/` 의 기록이 재현되지 않는다.
- 위 결정에 따라 `scripts/data/download_data.py` 와 `scripts/tqqq/generate_synthetic.py` 는 **재실행하지 않는다**. `storage/stock/` 의 CSV 13개는 손대지 않는다.
- `generate_synthetic.py:166` 의 `scale_factor` 는 가격이 아니라 배율이므로 4자리 상한 규칙의 대상이 아니다. 손대지 않는다.
- 성과 지표(`ROUND_PERCENT`=2)·비율(`ROUND_RATIO`=4)·자본금(`ROUND_CAPITAL`=0)의 자릿수는 바꾸지 않는다.
- 대시보드 앱 6종의 코드는 수정하지 않는다. CSV를 읽어 표시만 하므로 자동으로 4자리가 보인다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

파이썬 구현 규율이 저장소별 `.claude/rules/python.md` 에서 전역 `~/.claude/rules/python.md` 한 곳으로 통합되면서(커밋 `9a2f426`·`2e20a52`), 가격 자릿수 기준이 **6자리에서 4자리 상한으로** 바뀌었다.

4자리인 이유는 전역 규칙에 적혀 있다 — 그보다 깊은 자리는 실제 시세에 존재하지 않는 **부동소수점 표현 잡음**이며(이 저장소의 `GLD_max.csv` 에 실제로 `44.490002`·`44.919998` 형태로 들어 있다), 사용자가 결과를 차트와 대조할 때 방해가 된다.

루트 `CLAUDE.md` 는 이 상태를 「알려진 불일치」로 기록하고 **「그대로 둔다」** 로 결정해 두었다. 이번 작업은 그 결정을 **부분 변경**한다 — 성과 수치에 영향이 없는 **출력 표시 경로만** 집행하고, 입력 데이터 경로는 미이행으로 남긴다.

**이 분리가 성립하는 근거(조사 실측, 2026-09-09):**

1. 반올림이 **전부 복사본에만** 걸린다. `csv_export.py:78` 이 `trades_df.copy()` 로 시작하고, 각 러너는 `*_export` 변수를 만들어 `to_csv` 직전에만 `round()` 를 적용한다. 계산 원본은 손대지 않는다.
2. **결과 파일이 다른 계산의 입력으로 되먹임되지 않는다.** `read_csv` 계열 호출을 전수 조사한 결과 `storage/results/` 를 되읽는 경로는 3개뿐이고, 그중 **가격 컬럼을 계산에 재투입하는 곳은 0건**이다.
   - `walkforward.load_wfo_results_from_csv` — 읽는 컬럼이 날짜·파라미터·성과지표뿐이고 가격 컬럼이 없다
   - `parameter_stability.load_plateau_pivot` — 성과지표 피벗만 읽는다
   - 대시보드 4종 — 표시 전용(`src/qbt/backtest/CLAUDE.md` 규약: 대시보드는 산식을 자체 수행하지 않는다)
3. 성과 지표는 `ROUND_PERCENT`(2), 자본금·손익은 `ROUND_CAPITAL`(0, 정수 변환)이라 **가격 자릿수와 무관**하다.

또한 조사 중 **상수를 우회한 하드코딩**이 드러났다. `run_walkforward.py:307` 은 `{"upper_band": 6, "lower_band": 6}` 처럼 딕셔너리 리터럴에 숫자를 직접 적어, `round(…, 6)` 패턴 검색에 걸리지 않았다. 자릿수를 고칠 때 조용히 누락되는 지점이므로 이번에 상수로 교체한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 전역 `~/.claude/CLAUDE.md` — 특히 「수술적 변경」·「기존 함수 재사용 전 검증」·「목표 주도 실행」
- 전역 `~/.claude/rules/python.md` — 「출력 데이터 반올림」과 「반올림 자릿수」 표
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」·「스크립트 실행 규칙」·「알려진 불일치 — 가격 반올림 자릿수」
- `src/qbt/CLAUDE.md` — 상수 관리 3계층, 데이터 처리 규칙
- `src/qbt/backtest/CLAUDE.md` — 백테스트 도메인 규칙, 대시보드 아키텍처
- `scripts/CLAUDE.md` — CLI 계층 책임, 메타데이터 관리
- `tests/CLAUDE.md` — 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 기능 요구사항 충족 — `ROUND_PRICE`=4, 상수 우회 하드코딩 4곳 제거
- [x] 회귀/신규 테스트 추가 — 가격 자릿수 상한을 고정하는 정책 테스트 (`tests/qbt/test_rounding_policy.py`)
- [x] **성과 지표 불변 실측 완료** — 재실행 전후 대조에서 CAGR·MDD·Calmar·총수익률·거래수 차이 0건
      (19개 파일 / 15,012개 필드)
- [x] `poetry run python validate_project.py` 통과 (passed=544, failed=0, skipped=0)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / 루트 `CLAUDE.md` 갱신 / `tests/CLAUDE.md` 참조 수정
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (축 A를 남긴 이유와 「되먹임 0건」 실측 근거를 루트 `CLAUDE.md` 「알려진 불일치」 절로 이관)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**코드 — 상수 한 줄**

- `src/qbt/backtest/constants.py` (71행) — `ROUND_PRICE` 6 → 4, 주석 동기화

**코드 — 상수를 우회한 하드코딩 4곳**

- `src/qbt/backtest/engines/backtest_engine.py` (424행) — 미청산 포지션 진입가
- `scripts/backtest/run_single_backtest.py` (219행) — 미청산 포지션 진입가(엔진 값 재반올림), (303·304행) 터미널 표 출력 포맷 `:.6f`
- `scripts/backtest/run_walkforward.py` (307행) — Stitched Equity 밴드. 숫자 대신 `ROUND_CAPITAL`·`ROUND_RATIO`·`ROUND_PRICE` 상수로 교체

**코드 — 수정 불필요(상수 경유로 자동 반영), 산출물만 변함**

- `src/qbt/backtest/csv_export.py` (89·91행) — 거래 진입가·청산가
- `scripts/backtest/run_single_backtest.py` (114·117·148·150행) — OHLC·이평선·밴드
- `scripts/backtest/run_portfolio_backtest.py` (292·340·343·367·429행) — 평균단가·OHLC·이평선·밴드·종가·체결가
- `scripts/backtest/run_walkforward.py` (231-234·238·246·247행) — 윈도우별 OHLC·이평선·밴드

**주석·테스트**

- `src/qbt/backtest/types.py` (38행) — 주석 「소수점 6자리」 → 4자리
- `tests/qbt/test_walkforward_schedule.py` (97·101·107-109행) — 테스트용 가격 생성 픽스처
- `tests/qbt/test_rounding_policy.py` (신규) — 가격 자릿수 상한 정책 고정

**문서**

- 루트 `CLAUDE.md` — 「알려진 불일치」 절을 축 B 집행 완료 / 축 A 미이행 상태로 갱신
- `README.md`: **변경 없음** — 반올림 자릿수를 언급하지 않으며 실행 방법이 바뀌지 않는다
- `docs/COMMANDS.md`: **변경 없음** — 실행 명령어와 CLI 옵션이 그대로다

### 데이터/결과 영향

**변하는 것 — 가격 컬럼의 표시 자릿수만**

| 산출물 | 대상 | 개수 |
| --- | --- | --- |
| `storage/results/backtest/*/signal.csv` | 시가·고가·저가·종가·이평선 | 13개 전략 |
| `storage/results/backtest/*/equity.csv` | 상단밴드·하단밴드 | 버퍼존 7개 |
| `storage/results/backtest/*/trades.csv` | 진입가·청산가 | 13개 전략 |
| `storage/results/backtest/*/summary.json` | 미청산 포지션 진입가 | 미청산 보유 11개 |
| `storage/results/backtest/*/walkforward_equity_*.csv` | 상단밴드·하단밴드 | WFO 2개 전략 |
| `storage/results/backtest/*/wfo_windows_*/w##_{signal,equity,trades}.csv` | OHLC·이평선·밴드·체결가 | WFO 2개 전략 |
| `storage/results/portfolio/*/equity.csv` | 자산별 평균단가 | 4개 실험 |
| `storage/results/portfolio/*/signal_{자산}.csv` | OHLC·이평선·밴드 | 4개 실험 |
| `storage/results/portfolio/*/state_log.csv` | 종가·체결가 | 4개 실험 |
| `storage/results/portfolio/*/trades.csv` | 진입가·청산가 | 4개 실험 |
| `storage/results/portfolio/*/summary.json` | 최종 평균단가·미청산 진입가 | 4개 실험 |

**변하지 않아야 하는 것 (검증 게이트)**

- 모든 `summary.json` 의 CAGR·MDD·Calmar·총수익률·거래수·승률·샤프·소르티노
- `walkforward_summary.json` 의 모드별 요약 통계
- `storage/results/backtest/param_plateau/` 전체 — `ROUND_PRICE` 미사용이므로 **재실행하지 않는다**
- `storage/stock/` 전체 — 축 A 제외
- `storage/results/tqqq/` 전체 — 축 A 영역

**출력 스키마 변경 없음.** 컬럼 구성·이름·순서는 그대로이고 값의 자릿수만 줄어든다.

**`storage/results/meta.json` 은 예외적으로 「변해도 정상」이다.** 이 파일에는 가격이 들어가지 않고 성과지표(`results_summary`)와 파라미터만 기록되지만, 재실행하면 **타임스탬프가 갱신되고 순환 저장(최근 N개)이 밀린다.** 대조할 때 이 변화를 지표 변동으로 오인하지 않는다 — 확인할 것은 `results_summary` 의 **값**이지 타임스탬프가 아니다.

## 6) 단계별 계획(Phases)

### Phase 0 — 가격 자릿수 상한을 테스트로 먼저 고정(레드)

전역 규칙의 「가격은 어떤 경우에도 소수점 4자리를 넘기지 않는다」를 코드로 못박아, 앞으로 누가 자릿수를 되돌리면 테스트가 잡게 한다. 이 저장소에는 `test_ma_type_policy.py` 로 정책을 고정하는 관용이 이미 있으므로 그 형태를 따른다.

**작업 내용**:

- [x] `tests/qbt/test_rounding_policy.py` 신규 작성 — `ROUND_PRICE <= 4` 검증. 현재 값이 6이므로 **의도적으로 실패(레드)** 한다
- [x] 해당 테스트만 직접 실행해 레드를 확인한다 (`tests/CLAUDE.md` 의 단일 파일 테스트 예외 적용)
      → `assert 6 <= 4` 로 실패 확인 (1 failed)

---

### Phase 1 — 자릿수 변경 및 상수 일원화(그린 전환)

**작업 내용**:

- [x] `constants.py:71` — `ROUND_PRICE` 6 → 4, 주석을 4자리 기준으로 동기화
- [x] `backtest_engine.py:424` — 하드코딩 `6` 제거, `ROUND_PRICE` 사용 (import 추가)
- [x] `run_single_backtest.py:219` — 하드코딩 `6` 제거, `ROUND_PRICE` 사용
- [x] `run_single_backtest.py:303,304` — 터미널 표 출력 포맷 `:.6f` → `:.{ROUND_PRICE}f`
- [x] `run_walkforward.py:307` — 딕셔너리 리터럴의 숫자를 `ROUND_CAPITAL`·`ROUND_RATIO`·`ROUND_PRICE` 상수로 교체
      (컬럼명도 문자열 리터럴에서 `COL_*` 상수로 교체. 교체 전 5개 상수의 실제 값이
      원래 리터럴과 일치함을 확인 — 값이 달랐다면 반올림이 조용히 누락됐을 지점)
- [x] `types.py:38` — 주석에서 **숫자를 제거하고 `ROUND_PRICE` 를 가리키게** 변경.
      계획서 초안은 「4자리로 정정」이었으나, 숫자를 박으면 자릿수를 다시 바꿀 때 또 어긋난다
- [x] `test_walkforward_schedule.py:97,101,107-109` — 픽스처 가격 생성 자릿수를 4로 변경
- [x] Phase 0 테스트가 그린으로 바뀌는지 확인 → 29 passed
- [x] 남은 하드코딩이 없는지 재검색 — `round(…, 6)` 패턴뿐 아니라 **딕셔너리 리터럴 `: 6` 과 포맷 문자열 `.6f` 형태까지** 함께 훑는다

**Validation**:

- [x] `ROUND_PRICE` 를 참조하는 모든 지점이 상수 경유임을 grep 으로 확인 (직접 숫자 `6` 잔존 0건, 축 A 제외분은 제외)
      → 3형태 재검색 결과 가격 자릿수로 남은 `6` 은 축 A 제외분 5건뿐.
      나머지 `: 6`·`.6f` 잔존분은 Plotly 마커 크기·개월 수·비율(%) 표시로 **가격이 아니다**

---

### Phase 2 — 재실행 및 성과 지표 불변 실측

이 Phase가 이번 작업의 **핵심 검증 게이트**다. 성과 지표가 하나라도 달라지면 「출력 표시 전용」이라는 전제가 틀린 것이므로 즉시 중단하고 원인을 규명한다.

**작업 내용**:

- [x] 재실행 전 현재 `summary.json`·`walkforward_summary.json` 전부를 스크래치패드로 백업 (20개 파일)
- [x] `run_single_backtest.py` 실행 (13개 전략)
- [x] `run_portfolio_backtest.py` 실행 (4개 실험, 정합성 5개 규칙 모두 통과)
- [x] `run_walkforward.py` 실행 (WFO 2개 전략) → 실측 소요 **67.5초**, 예상(약 6분)보다 짧았다
- [x] 백업본과 재실행 결과의 **성과 지표를 기계로 대조** — CAGR·MDD·Calmar·총수익률·거래수·승률·샤프·소르티노
- [x] 가격 컬럼이 실제로 4자리 이하로 저장됐는지 산출물에서 표본 확인
- [x] `meta.json` 은 타임스탬프 갱신분을 걷어내고 `results_summary` 의 **값만** 비교한다

**Validation**:

- [x] 성과 지표 차이 **0건** (차이가 나오면 Phase 1 로 되돌아가 원인 규명)
      → 대조 파일 19개 / 비교 필드 **15,012개** / 차이 **0건**
- [x] `storage/stock/`·`storage/results/tqqq/`·`param_plateau/` 가 변경되지 않았음을 확인 → 변경 0건

**실측 표본** — 부동소수점 잡음이 의도대로 제거됐다.

| 산출물 | 변경 전 | 변경 후 |
| --- | --- | --- |
| `signal.csv` 시가 | `44.240002` | `44.24` |
| `signal.csv` 이평선 | `43.08025` | `43.0802` |
| `trades.csv` 진입가 | `25.938059` | `25.9381` |
| `equity.csv` 상단밴드 | `52.162218` | `52.1622` |
| WFO 윈도우 `w00_signal.csv` 시가 | `43.079741` | `43.0797` |

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 루트 `CLAUDE.md` 「알려진 불일치」 절 갱신 — 출력 경로는 집행 완료, 입력 데이터만 미이행으로 남았음을 기록하고 **왜 남겼는지(성과 수치 변동·`docs/research/` 재현성)** 를 함께 적는다
- [x] `README.md` 변경 없음 확인 및 명시 → 자릿수·반올림 언급 0건
- [x] `docs/COMMANDS.md` 변경 없음 확인 및 명시 → 자릿수·반올림 언급 0건, 실행 명령 불변
- [x] 자릿수 SoT 를 가리키는 깨진 참조 2건 수정 (작업 중 발견, 사용자 승인)
      - `constants.py:68` — 루트 `CLAUDE.md` 의 사라진 절을 가리키던 헤더 주석을 걷어내고, 이 상수가 SoT임과 「저장 직전에만 적용」 계약을 남김
      - `tests/CLAUDE.md` — 삭제된 `.claude/rules/python.md` 대신 `constants.py` 의 `ROUND_*` 를 가리키게 변경
- [x] 자동 포맷 적용 — `poetry run black .` (115 files unchanged)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=544, failed=0, skipped=0) — Ruff·PyRight·Pytest 전부 통과

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 결과 파일 가격 자릿수 6→4 통일 및 반올림 상수 일원화
2. 백테스트 / 가격 반올림 4자리 집행 — 상수 우회 하드코딩 4곳 제거
3. 백테스트 / 출력 가격 자릿수를 전역 규칙(4자리 상한)에 맞춤
4. 백테스트 / ROUND_PRICE 4자리 전환 + 자릿수 정책 테스트 추가
5. 백테스트 / 가격 표시 자릿수 통일(성과 지표 불변 실측 완료)

## 7) 리스크(Risks)

| 리스크 | 완화책 |
| --- | --- |
| **성과 지표가 달라진다** — 「출력 표시 전용」 전제가 틀렸을 경우 | Phase 2 를 게이트로 둔다. 재실행 전 백업 → 기계 대조 → 차이 1건이라도 나오면 중단하고 원인 규명. 조사 단계에서 되먹임 0건을 확인했으나 실측으로 재확인한다 |
| **결과 파일 diff 가 크게 발생한다** — 13전략 + 4실험 + WFO 2전략의 CSV 전체 | `storage/results/` 는 git 추적 대상이라 되돌릴 수 있다. 실행 전 작업 트리가 clean 한지 확인한다(루트 `CLAUDE.md` 「스크립트 실행 규칙」) |
| **상수 우회 하드코딩을 또 놓친다** — `run_walkforward.py:307` 이 실제로 초기 검색을 빠져나갔다 | Phase 1 에서 `round(…, 6)`·딕셔너리 `: 6`·포맷 `.6f` 세 형태를 모두 훑는다. Phase 0 정책 테스트가 상수 값 자체를 고정한다 |
| **입력·출력 자릿수가 달라 보인다** — `storage/stock/` 은 6자리인데 `signal.csv` 는 4자리 | 의도된 상태다. 전역 규칙이 4자리를 정한 근거가 「결과를 차트와 대조할 때」이므로 출력만으로 목적이 달성된다. 루트 `CLAUDE.md` 에 명시해 다음 사람이 버그로 오인하지 않게 한다 |
| **WFO 재실행에 약 6분** | 마지막에 한 번만 실행한다. Phase 1 의 코드 수정이 끝난 뒤 Phase 2 에서 일괄 실행 |

## 8) 메모(Notes)

### 결정 사항 (2026-09-09, 사용자 승인)

- **축 A(입력 데이터)는 손대지 않는다.** `stock_downloader.py` 와 `generate_synthetic.py` 의 6자리 유지.
- **축 B(출력 표시)는 전부 4자리로 통일한다.**
- **`run_walkforward.py:307` 은 숫자만 바꾸지 않고 상수로 교체한다.** 같은 줄을 어차피 수정하므로 diff 가 늘지 않고, 다음번 자릿수 변경 때 이 줄만 누락되는 사고를 막는다.
- **재실행과 대조는 AI 가 수행한다.** 대시보드는 규칙대로 사용자가 실행한다.

### 조사 실측 (2026-09-09)

- QBT 는 yfinance 기반 **미국 시세 전용**이다. `pykrx` 호출 0건, `.KS`/`.KQ` 티커 0건 → 전역 규칙 표의 「KRX 원화 가격 정수」 행은 **이 저장소에 해당 없음**.
- `storage/results/` 를 되읽는 경로 3개 모두 가격 컬럼을 계산에 재투입하지 않는다(Context 참고).
- `run_param_plateau_all.py` 는 `ROUND_PRICE` 를 쓰지 않는다(`round(…, 2)` 3곳뿐) → 재실행 대상에서 제외.
- 미청산 포지션 진입가는 `backtest_engine.py:424` 와 `run_single_backtest.py:219` 에서 **이중으로 반올림**되고 있다. 둘 다 같은 자릿수로 맞춰야 한다.

### 작업 중 발견 — 사전 존재 상태 (이번 범위에서 고치지 않음)

`run_walkforward.py` 의 stitched equity 저장부(`walkforward_equity_*.csv`)는 round 딕셔너리에
`upper_band`·`lower_band`·`buy_buffer_pct`·`sell_buffer_pct` 를 지정하지만, **그 DataFrame 에는 이 컬럼들이 없다**
(실제 컬럼은 `Date`·`equity`·`position` 뿐). pandas 는 없는 컬럼 지정을 조용히 무시하므로 이 4개 항목은 효과가 없다.

**변경 전에도 동일했다**(git 이전 버전으로 확인). 상수 교체로 동작이 달라지지 않았고, 이후 그 DataFrame 에
밴드 컬럼이 추가되면 올바른 자릿수가 자동 적용된다. 전역 규칙 「사전 존재 데드 코드는 요청 없이 삭제하지 않는다」에 따라 남겼다.

같은 저장부의 `equity` 는 다른 저장 경로와 달리 `astype(int)` 를 거치지 않아 `10000000.0` 형태로 남는다. 이 또한 사전 존재 상태다.

### 진행 로그 (KST)

- 2026-09-09 17:37: 계획서 작성. 조사 완료(반올림 지점 전수, 되먹임 경로 3개 확인), 사용자 승인 4건 반영.
- 2026-09-09 17:41: Phase 0 완료. 정책 테스트 레드 확인 (`assert 6 <= 4`).
- 2026-09-09 17:44: Phase 1 완료. 상수 1곳 + 하드코딩 4곳 수정, 3형태 재검색으로 잔존 0건 확인.
- 2026-09-09 17:48: Phase 2 완료. 재실행 3종 후 15,012개 필드 대조에서 성과 지표 차이 0건.
  WFO 실측 소요 67.5초(예상 약 6분보다 짧음). 축 A 변경 0건 확인.
- 2026-09-09 17:52: 마지막 Phase 완료. 문서 4종 정리, 깨진 참조 2건 수정, `validate_project.py` 전부 통과.

---
