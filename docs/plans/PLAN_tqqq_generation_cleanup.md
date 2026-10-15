# Implementation Plan: TQQQ 시뮬레이션 · 생성 스크립트 정리 — 반올림 상수 한 곳 · 시세 저장 함수 한 벌 · 쓰이지 않는 검사와 인자 삭제

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-14 22:15
**마지막 업데이트**: 2026-10-15 07:48
**관련 범위**: tqqq(`simulation.py` · `constants.py` · `data_loader.py` · `analysis_helpers.py` · `visualization.py`), utils(`stock_downloader.py` · `proxy_comparison.py`), `common_constants.py`, backtest(`constants.py` 와 반올림 상수를 가져오는 모듈 넷 — import 만), scripts(TQQQ 합성 · 일별 비교 · 대용 · 장기 대체 · 대체-실물 비교 생성, 다운로드, 대체-실물 비교 · 스프레드 랩 대시보드의 import, 러너 여섯의 import), `pyrightconfig.json`, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, 루트 `CLAUDE.md`(「가격 반올림 자릿수」), `docs/AUDIT_REPORT.md`(19절 11단계 tqqq · utils 줄)

---

## 1) 목표(Goal)

- [x] 목표 1: 반올림 자릿수 상수를 공통 상수로 옮겨 tqqq 일별 비교 저장도 같은 상수를 쓴다 — 루트 `CLAUDE.md` 의 「`ROUND_PRICE` 를 모든 저장 경로가 경유」가 참이 된다 (결정 10 · 3-6 · 13-B D11)
- [x] 목표 2: 시세 파일을 저장하는 「가격 반올림 → 검사 → 저장」을 함수 하나로 — 다운로더 · 대용 · 장기 대체 · TQQQ 합성이 같이 쓰고, 합성의 저장 전 검사를 테스트가 지킨다 (5-3 · 2026-10-11 사용자 결정)
- [x] 목표 3: TQQQ 합성의 손 이어 붙이기를 공용 함수(`splice_proxy`)로 바꾸고 쓰지 않는 시작 가격 상수를 지운다 (7-3 · 9-8 · 4-3 · 6-7 의 합성 스크립트 두 곳)
- [x] 목표 4: 시뮬레이션 엔진의 중복 · 쓰이지 않는 경로를 지운다 — 같은 공식의 두 번째 구현과 그 대조 검사(5-1), 기간 커버리지 사전 검사(2-2), 읽는 곳 없는 검증 지표 4칸(2-13 · 4-2), 인자 이중 경로(6-5 의 tqqq 부분), 누적수익률 세 번 계산(7-6 의 tqqq 부분), 시가 결측 메움(6-7)
- [x] 목표 5: 같은 일을 하는 두 벌을 하나로 — 월별 데이터 로더(5-6), 대체-실물 비교 표 반올림(5-6), 다운로드 스크립트의 한 줄 래퍼(5-7 의 `download_data.py`)
- [x] 목표 6: 부호 서식 「+-」(2-16 · 2-22), tqqq 상수의 자리(4-6 의 tqqq 시뮬레이션 부분), 연구 스크립트의 타입 검사(8-7), utils 안내 문서의 원칙 문구(8-4)
- [x] 목표 7: 결과 파일이 바뀌지 않는다 — 생성 스크립트 다섯과 러너 여섯의 출력이 수정 전과 바이트까지 같다

## 2) 비목표(Non-Goals)

- **스프레드 랩 앱만 쓰는 코드** — 결정 5(1-5 · 7-2 · 8-5 · 6-10) · 4-4 와 함께 다음 계획서로 한다. 19절이 이 줄에 둔 **5-4**(`add_rate_change_lags`) · **3-15**(12 · 13개월 상수) · **6-5 의 `analysis_helpers.aggregate_monthly`**(금리 없는 경로)도 그쪽으로 옮긴다 — 셋 다 스프레드 랩 앱 하나만 쓰는 코드이고 그 계획서가 같은 파일(`spread_lab_helpers.py` · `visualization.py` 의 금리-오차 차트 · `aggregate_monthly`)을 고친다. 같은 이유로 14절의 `analysis_helpers.py` 「2개월」 · 15절의 그 파일 주석 처리 코드 · 13-C C7 의 그 파일 두 곳 · 4-6 의 스프레드 랩 전용 상수도 그쪽이다
- **5-7 의 `run_walkforward.py` · `run_param_plateau_all.py` 래퍼** — 11단계 backtest 로 옮긴다(그 계획서가 같은 러너를 고친다). 이 계획서는 `download_data.py` 만 한다
- **`COL_EXPENSE_DATE` · `COL_EXPENSE_VALUE` · `DEFAULT_PRE_LISTING_EXPENSE_RATIO` 의 자리** — `tqqq/data_loader.py` 한 파일만 쓰지만 점검 보고서 4-6 목록에 없고 테스트 37줄이 import 한다. 같은 열 상수의 정리를 테스트 비용으로 보류한 20절 4-5 와 같은 이유로 그대로 둔다
- **`qbt/tqqq/__init__.py` 의 재노출** — 점검 보고서에 tqqq 몫이 없다
- **`build_extended_expense_dict` docstring 의 「2010-02 · 1999-01 ~ 2010-01」(14절의 `tqqq/data_loader.py`)** — 그 함수는 이번에 고치지 않는다. 12단계
- **저장소에서 생성 스크립트를 돌리는 것** — 결과가 같으므로 다시 만들 필요가 없고, 돌리면 대체 판 3개(`SSO_proxy` · `QLD_proxy` · `BIL_proxy`)가 결정 19 · 20 이 「다음 시세 갱신 때」로 미룬 재생성을 앞당긴다. 확인은 사본에서만 한다
- **입력 시세 자릿수(6자리)를 4자리로** — 루트 `CLAUDE.md` 의 의도된 미이행 그대로다. 6 을 상수 하나(`ROUND_INPUT_PRICE`)로 모을 뿐이다
- **안내 문서 경량화(18-B · 18-D)** — 12단계. 이번에는 이 변경으로 거짓이 되는 문장만 고친다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계 tqqq · utils 줄의 둘째 묶음이다(첫 묶음 = 실행 이력 · utils, `7812d30`). B 절 결정 20건은 2026-10-09 에 모두 추천안대로 확정됐다(결정 10 = 반올림 상수를 공통 상수로)
- 대상마다 지금 무엇이 문제인가 (2026-10-12 저장소 사본에서 다시 쟀다. 스크래치 `step11b/`)

| 항목 | 지금 | 재현 |
|---|---|---|
| 결정 10 · 3-6 · D11 반올림 상수 | `ROUND_*` 가 `backtest/constants.py` 에 있어 tqqq 는 쓸 수 없다(도메인 경계). 일별 비교 저장이 `.round(4)` 를 숫자로 적어 가격 2열과 % 열 8개에 똑같이 건다. 그래서 루트 `CLAUDE.md` 의 「`ROUND_PRICE`(모든 저장 경로가 경유)」가 거짓이다 | `ROUND_*` 를 가져오는 파일 15개(import 26줄). 리터럴 반올림은 일별 비교 1곳 · 입력 6자리 4곳 |
| 3-6 의 % 열 자릿수 | % 열을 백분율 기본(2자리)으로 낮추면 안 되는지 | 일별 비교의 % 열을 2자리로 저장하면 스프레드 랩의 월별 「일일 증분 오차 월합」이 4자리 대비 중앙값 0.0119%p 달라진다(그 값의 절대 중앙값 0.1040%) — 200개월 중 9개월에서 부호가 뒤집힌다. 4자리를 유지한다 |
| 5-3 시세 저장 | 「가격 6자리 반올림 → 검사 → 저장」이 다운로더 · 대용 생성 · 장기 대체 생성(`_save_price_csv` 두 벌이 글자 단위로 같다) · TQQQ 합성 네 곳에 있다. 합성의 저장 전 검사(10단계에서 넣음)는 스크립트 안이라 그 줄을 지워도 품질 검증이 통과한다 | 2026-10-11 10단계 사본 확인(점검 보고서 5-3 행) |
| 7-3 · 4-3 TQQQ 합성 | `splice_proxy` 와 같은 이어 붙이기를 손으로 다시 짰다(접합 · 스케일 · 병합 · 정렬 30줄). 시작 가격 상수 200 은 이음매 스케일이 흡수한다 | 시작 가격 200 · 1.0 어느 쪽이든 `splice_proxy` 결과를 6자리로 저장하면 지금 저장 파일과 바이트까지 같다(377,383B) |
| 5-1 abs 로그차이 | 같은 누적배수 로그차이를 가격 비율로 한 번(`_calculate_cumul_multiple_log_diff`), 누적수익률로 한 번(signed) 계산하고, 둘을 대조하는 검사(`validate_integrity` · `INTEGRITY_TOLERANCE`)를 둔다 | 실데이터 4,180행에서 두 값의 최대 차 4.574e-14, 4자리 반올림 뒤 다른 칸 0, RMSE 1.0270736637 로 같다 |
| 2-2 커버리지 사전 검사 | `_validate_ffr_coverage` 가 기간의 달을 날짜째 하나씩 늘려 세어, 시작일이 29 – 31일이면 다음 달에 그 날짜가 없어 죽는다. 같은 정책을 날마다 비용을 계산할 때 `lookup_ffr` 이 다시 본다 | 2020-01-31 에 시작하는 `simulate` → `ValueError: day is out of range for month`. 닿지 않는다(호출부 시작일 1999-03-10 · 2010-02-11 · 1999-01-04) |
| 2-13 · 4-2 검증 지표 | 종가 3칸 · 누적수익률 상대차이 1칸과 그 0 나눗셈 가드 둘 — 읽는 곳 0 | 호출처 집계(그 키 상수는 `simulation.py` · `constants.py` 에만) |
| 6-5 `simulate` 인자 | `ffr_df` / `ffr_dict` 택일, `expense_df` / `expense_dict` 이중, 스프레드 고정값(float) 경로 | 운영 호출 3곳 중 `ffr_dict` 를 넘기는 곳 0 · float 스프레드 0 · `expense_df` 와 `expense_dict` 를 둘 다 넘기는 곳 2(그때 `expense_df` 는 비었는지만 본다) |
| 6-7 시가 결측 | `simulate` 가 시가를 `fillna(initial_price)` 로 채워 첫날 말고도 시가 결측을 시작 가격으로 메운다 | 셋째 날 기초 시가가 결측인 입력 → 결과 시가 30.0(시작 가격). 닿지 않는다(시세 로더가 결측 가격을 막는다) |
| 7-6 누적수익률 | `simulation.py` 가 같은 누적수익률을 세 번 계산한다(검증 지표의 곱 · 지표용 시계열 · CSV 저장) | 코드 확인 |
| 5-6 두 벌 | `load_ffr_data` ≡ `load_expense_ratio_data`(메시지만 다르다), 대체-실물 비교 스크립트 `_round` ≡ 대시보드 `_round_for_display`(글자 단위로 같다 — 반올림 상수가 backtest 에 있어 utils 로 못 옮겼다) | 코드 확인 |
| 4-6 상수 자리 | `MAX_EXPENSE_MONTHS_DIFF` 는 `tqqq/data_loader.py` 만 쓰고, 이번에 커버리지 검사를 지우면 `MAX_FFR_MONTHS_DIFF` 도 그렇다. `COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE` · `_MEAN` · `_MAX` 는 일별 비교 스크립트의 로그 문구에만 쓴다 | 파일별 사용처 집계 |
| 2-16 · 2-22 부호 서식 | `+{x:.1f}%` · `x+{b:.2f}` 는 음수면 「+-」로 찍힌다 | `-1.23` → `+-1.2%`. 연구 스크립트(`late_entry_rally_opportunities.py`)의 두 곳은 이미 `:+.1f` 다 — 남은 곳은 일별 비교 스크립트 둘 · 추세선 라벨 둘 |
| 8-7 연구 스크립트 | `docs/research/late_entry_rally_opportunities.py` 가 타입 검사 범위 밖이다 | include 에 넣어도 pyright strict 0 errors(Ruff · black 은 이미 본다) |

### 설계 결정

1. **반올림 상수는 `common_constants.py` 에 둔다** (결정 10)
   - `ROUND_PRICE` · `ROUND_CAPITAL` · `ROUND_PERCENT` · `ROUND_RATIO` 블록을 그대로 옮기고, 가져오던 15개 파일의 import 를 바꾼다. 값은 그대로다
   - 일별 비교 저장: 종가 2열은 `ROUND_PRICE`, % 열(일일 · 누적 수익률 · 로그차이)은 `simulation.py` 의 `ROUND_DAILY_COMPARISON_PERCENT = 4` — 백분율 기본(2자리)보다 깊어야 하는 이유를 상수 주석에 둔다(위 재현). 바이트가 같다
2. **시세 저장은 `stock_downloader.save_stock_csv(df, path, *, check_price_spikes=True)` 하나다** (5-3)
   - 복사본의 가격 열을 6자리로 반올림 → 검사 → 상위 폴더를 만들고 저장. 검사에 걸리면 파일을 쓰지 않는다
   - 급등락 검사는 레버리지 합성만 끈다(`check_price_spikes=False`) — 그때도 시세 표 검사(`validate_price_series` — 중복 날짜 · 가격 결측 · 0 · 음수)는 한다. 3배 합성은 하루 50% 를 넘는 날이 있다(2001-01-03)
   - 입력 자릿수 6 은 그 모듈의 `ROUND_INPUT_PRICE` 하나다 — 루트 `CLAUDE.md` 표의 「입력 — 미이행」 지점이 네 파일에서 이 함수 하나로 준다
3. **TQQQ 합성은 `simulate(시작 가격 1.0)` → `splice_proxy` → `save_stock_csv(급등락 검사 끔)` 이다** (7-3 · 4-3)
4. **`simulate` 는 월별 값 딕셔너리 셋을 받는다** (6-5 · 2-2)
   - `simulate(underlying_df, leverage, initial_price, *, ffr_dict, expense_dict, funding_spread)` — 셋 다 `{"YYYY-MM": 값}`. 호출부가 `create_ffr_dict` · `create_expense_dict` · `build_extended_expense_dict` · `build_monthly_spread_map` 으로 만든다
   - 커버리지 사전 검사를 지운다 — 둘째 거래일부터 날마다 세 값을 조회하고, 허용 개월 수를 넘게 비면 그 자리에서 ValueError 다(같은 정책, 메시지에 빈 달이 나온다)
   - 스프레드 고정값(float) 경로를 지운다 — 운영은 늘 월별 딕셔너리다. 스프레드의 NaN · inf · 0 이하 검사는 그대로다
   - 시가는 첫날만 시작 가격으로 둔다 — 다른 날의 결측은 메우지 않는다(6-7)
5. **누적배수 로그차이는 signed 하나로 계산한다** (5-1 · 7-6)
   - 누적수익률(%)을 한 번 계산해 signed 로그차이를 내고, 지표(평균 · RMSE · 최대)와 CSV 의 abs 열은 그 절댓값이다. 두 번째 구현 · 대조 검사 · `INTEGRITY_TOLERANCE` 를 지운다
   - 검증 지표에서 읽는 곳 없는 4칸과 0 나눗셈 가드 둘, 그 키 상수 넷을 지운다(2-13 · 4-2). 누적수익률은 누적 시계열의 마지막 값이다(전에는 일일 수익률의 곱 — 같은 값)
6. **두 벌을 하나로** (5-6 · 5-7)
   - `tqqq/data_loader.load_monthly_data(path)` 하나가 금리 · 운용비율 파일을 읽는다. 값 검사는 지금처럼 딕셔너리를 만들 때 한다
   - 대체-실물 비교 표 반올림은 `proxy_comparison.round_for_display` 하나 — 계산 스크립트와 대시보드가 같이 쓴다(반올림 상수가 공통 상수가 되어 utils 에 둘 수 있다)
   - `download_data.py` 는 티커 목록 하나를 도는 루프다(`_download_single` 삭제)
7. **상수 자리** (4-6 의 tqqq 시뮬레이션 부분)
   - `MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF` 를 `tqqq/data_loader.py` 로 — 같은 파일의 `MAX_FFR_VALUE` · `MAX_EXPENSE_VALUE` 옆이다(월별 값 검사 기준이 한 곳)
   - `COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE` · `_MEAN` · `_MAX` 를 지우고 일별 비교 스크립트의 로그 문구에 그대로 적는다 — 3계층 규칙은 로그 출력을 세지 않아 쓰는 곳이 0 이다
   - `tqqq/constants.py` 의 머리 「내부 계산용 영문 토큰」 아래 한글 열 이름(13-C C7) — 머리 문구를 사실대로
8. **그 밖** — 「+-」 네 곳은 `:+` 서식(2-16 · 2-22), `pyrightconfig.json` include 에 연구 스크립트(8-7), `src/qbt/utils/CLAUDE.md` 의 「도메인 로직과 독립적인 기술적 기능만」을 실제 담당(시세 수집 · 대용 가공 · 대체 비교 포함)으로(8-4)

### 사본 재현 (착수 전 확인, 2026-10-12 – 14)

저장소 밖 사본(스크래치 `step11b/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **레드 단계는 두지 않는다** — 이 묶음은 결과를 바꾸지 않는 정리다. 동작이 바뀌는 두 곳은 수정 전 코드에서 재현했다: 2020-01-31 시작 → ValueError(2-2), 셋째 날 시가 결측 → 시작 가격으로 메움(6-7). 새 테스트가 무엇을 잡는지는 변형 확인으로 본다
- **수정 뒤 931 passed** (지금 941 − 지운 20 + 더한 10 — 지운 것: 커버리지 사전 검사 6 · 고정 스프레드 1 · 검증 지표 가드 2 · abs 로그차이 사전 검증 2 · 무결성 검사 3 · 월별 로더 6(8 → 2), 더한 것: 저장 함수 5 · 월말 시작일 1 · 금리 공백 1 · 시가 결측 1 · 로그차이 지표 1 · 대체 비교 반올림 1), Ruff 통과, PyRight 0 errors(연구 스크립트 포함)
- **변형 확인** — 새로 넣거나 고친 검사에 결함을 한 종씩 넣은 14종을 테스트가 모두 잡는다(급등락 검사를 끈 저장의 시세 표 검사 삭제 · 급등락 플래그 무시 두 방향 · 저장 전 반올림 삭제 · 원본을 바로 반올림 · 시가 결측 메움 · 지표를 signed 로 · CSV abs 열에 signed · % 열 2자리 · 종가 반올림 빠뜨림 · 금리를 조회하지 않고 아무 달 값 · 스프레드 0 이하 검사 삭제 · 대체 비교 표의 비율 · % 자릿수 뒤바뀜 · % 열 반올림 빠뜨림). 첫 실행에서 「% 열 2자리」가 통과했다 — 테스트가 기대값을 같은 상수로 계산해 상수를 바꾸면 기대값도 바뀌었다. 4자리는 정책 값이라 테스트에 손으로 고정했다(결정 14)
- **결과 파일** — 생성 스크립트 다섯(합성 · 일별 비교 · 대용 · 장기 대체 · 대체-실물 비교)이 다시 쓴 13개 파일이 수정 전 사본의 출력과 바이트까지 같다. 러너 여섯(단일 · 워크포워드 · 고원 · 포트폴리오 · 두 그리드)도 같은 시세로 돌린 수정 전 · 후 결과 274개가 같다(모두 종료 코드 0)
  - 사본의 조합 그리드 결과 3개는 저장소와 다르다 — 사본에서 생성 스크립트를 다시 돌려 대체 판 3개가 결정 19 · 20 이 「다음 시세 갱신 때」로 미룬 새 값이 됐기 때문이다(수정 전 사본에서 같은 시세로 다시 돌리면 수정 후와 같다). 저장소에서 생성 스크립트를 돌리지 않는 이유다(비목표)
- **대시보드 둘(import 가 바뀐 대체-실물 비교 · 스프레드 랩)** — 서버 없이 `main()` 을 한 번 실행해 수정 전 · 후 모두 예외 0건(8단계에 허락받은 확인 방식). 수정 후 스프레드 랩은 새 월별 로더로 금리 333개월을 읽었다
- **import 만 바뀐 파일** — 수정 전 · 후를 import · docstring 을 뺀 AST 로 견주면 러너 여섯 · `backtest` 의 `analysis.py` · `csv_export.py` · `runners.py` · `engines/backtest_engine.py` · 테스트 둘이 같다
- **변경 규모(포맷 적용 뒤)** — src +154 / −489, 스크립트 +72 / −164, 테스트 +306 / −490

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」 · 「가격 반올림 자릿수」 절
- `src/qbt/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `_calculate_cumul_multiple_log_diff` · `validate_integrity` · `INTEGRITY_TOLERANCE` · `_validate_ffr_coverage` · `FundingSpreadSpec` · `DEFAULT_SYNTHETIC_INITIAL_PRICE` · `load_ffr_data` · `load_expense_ratio_data` · `_save_price_csv` 를 가리키는 코드가 src · scripts · tests 에 0 이다
- [x] `ROUND_*` 는 `common_constants.py` 에만 정의되고, 저장 경로에 반올림 자릿수를 숫자로 적은 곳이 없다(입력 6자리는 `ROUND_INPUT_PRICE` 하나)
- [x] 생성 스크립트 다섯 · 러너 여섯의 결과 파일이 수정 전과 같다(사본 재실행)
- [x] 새로 넣거나 고친 검사마다 결함을 일부러 넣어 테스트가 실패하는 것을 봤다(변형 확인)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`, 루트 `CLAUDE.md`(「가격 반올림 자릿수」 표), `src/qbt/tqqq/CLAUDE.md`(모듈 구성 · 검증 임계값 · abs 로그차이 함수), `src/qbt/utils/CLAUDE.md`(원칙 문구 · 다운로더 · 대체 비교), `scripts/CLAUDE.md`(대용 생성의 저장 문장), `tests/CLAUDE.md`(자릿수 SoT 경로). `docs/COMMANDS.md` · `README.md` 변경 없음 — 실행 명령 · CLI 옵션이 그대로이고 두 문서에 바뀌는 이름이 없다
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 해당 없음: 새로 옮긴 것 0(미조치 지적은 모두 거르는 기준에 걸린다 — 진행 로그), 이 계획서가 고친 파일 항목 0(남은 1건은 11단계 tests 배정 그대로). 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py` — 반올림 상수 블록 추가
- `src/qbt/backtest/constants.py` — 반올림 상수 블록 삭제
- `src/qbt/backtest/analysis.py` · `csv_export.py` · `runners.py` · `engines/backtest_engine.py` — 반올림 상수 import 만
- `src/qbt/tqqq/simulation.py` — 인자 · 커버리지 검사 · abs 두 번째 구현 · 검증 지표 4칸 · 누적수익률 중복 · 시가 메움 · 저장 자릿수
- `src/qbt/tqqq/constants.py` — 쓰지 않는 상수 삭제, 월 차이 상수 둘을 로더로, 머리 문구
- `src/qbt/tqqq/data_loader.py` — 월별 로더 하나, 월 차이 상수 둘
- `src/qbt/tqqq/analysis_helpers.py` — 무결성 검사와 그것만 쓰던 로거 삭제
- `src/qbt/tqqq/visualization.py` — 추세선 라벨 부호
- `src/qbt/utils/stock_downloader.py` — `save_stock_csv` · `ROUND_INPUT_PRICE`, 다운로더가 그 함수로 저장
- `src/qbt/utils/proxy_comparison.py` — `round_for_display`
- `scripts/tqqq/generate_synthetic.py` · `generate_daily_comparison.py`, `scripts/data/generate_proxy_series.py` · `generate_long_proxy_series.py` · `generate_proxy_comparison.py` · `app_proxy_comparison.py` · `download_data.py`, `scripts/tqqq/spread_lab/app_rate_spread_lab.py`(로더 이름만), `scripts/backtest/` 러너 여섯(반올림 상수 import 만)
- `pyrightconfig.json` — include 에 연구 스크립트
- `tests/qbt/test_tqqq_simulation_core.py` · `test_tqqq_simulation_cost_model.py` · `test_tqqq_simulation_outputs.py` · `test_tqqq_analysis_helpers.py` · `test_tqqq_data_loader.py` · `test_integration.py` · `test_stock_downloader.py` · `test_proxy_comparison.py` · `test_rounding_policy.py` · `test_csv_export.py`
- 위 DoD 문서 줄의 문서
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션 변경 없음
- `README.md`: 변경 없음

### 데이터/결과 영향

- 결과 파일 · 시세 파일은 바뀌지 않는다 — 저장소에서 생성 스크립트 · 러너를 다시 돌리지 않는다(비목표)
- `simulate` · 월별 로더의 인자 · 이름이 바뀐다. 호출처는 이 계획서가 모두 고친다(src · scripts · tests)

## 6) 단계별 계획(Phases)

### Phase 1 — 사본에서 검증한 코드 반영(그린)

**작업 내용**:

- [x] 저장소의 src · scripts · tests · `pyrightconfig.json` 이 사본의 수정 전 기준과 같은지 확인한다(`diff -rq`)
- [x] 설계 결정 1 – 8 — 사본에서 검증한 파일을 그대로 넣는다

**Validation**:

- [x] 사라질 이름을 가리키는 코드가 0건(DoD 첫 줄의 `grep`)
- [x] `poetry run pytest tests/qbt/test_tqqq_simulation_core.py tests/qbt/test_tqqq_simulation_cost_model.py tests/qbt/test_tqqq_simulation_outputs.py tests/qbt/test_tqqq_data_loader.py tests/qbt/test_stock_downloader.py tests/qbt/test_proxy_comparison.py tests/qbt/test_integration.py` — 전부 통과(132 passed)

---

### 마지막 Phase — 결과 불변 확인 · 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 저장소의 src · scripts · tests · `pyrightconfig.json` 이 사본에서 검증한 코드와 같은지 `diff -rq` 로 확인한다 — 같으면 사본의 재현(결과 동일 · 변형 14종 · AST 대조)이 최종 코드의 결과다
- [x] 문서 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절), 안내 문서 다섯
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 10건 — 버그 1 [무거움 1 · 가벼움 0] · 그 외 9 · 조치: 고칠 것 0 — 무거움 1 미조치(닿지 않음, 기준 1) · 그 외 6 반영(누적수익률 단언 · 자릿수 SoT 문장 · 반올림 비교를 approx 로 · 저장 전 검사 docstring · 타입 검사 범위를 폴더로 · 로더 오류 문구) · 그 외 3 미반영)
- [x] 수정분 검증 (1회차 반영분 9 hunk · 발견 4건 — 무거움 0 · 가벼움 1 · 그 외 3 · 조치: 절차대로 고치지 않음 — 넷 다 거름(기준 3), 진행 로그)
- [x] `poetry run python validate_project.py` (passed=931, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 데이터 / TQQQ 시뮬레이션 · 생성 스크립트 정리
2. 데이터 / 반올림 상수 공통화, 시세 저장 함수 단일화, TQQQ 합성의 splice_proxy 전환과 시뮬레이션 중복 계산 · 미사용 검사 삭제
3. 데이터 / 결과 파일 변화 없이 같은 일을 하던 두 벌과 읽는 곳 없는 검증 코드 제거
4. 데이터 / 점검 보고서 11단계 tqqq 시뮬레이션 · 생성 스크립트 묶음 처리 — 결정 10 · 5-3 · 7-3 · 5-1 · 2-2
5. 데이터 / ROUND_* 의 common_constants 이동, save_stock_csv 도입, simulate 월별 딕셔너리 인자, validate_integrity · _validate_ffr_coverage 삭제

## 7) 리스크(Risks)

- **`simulate` · 월별 로더의 인자 · 이름이 바뀐다** — 호출처는 src · scripts · tests 에만 있고 모두 고친다(사라질 이름 `grep` 0). 대시보드 둘(대체-실물 비교 · 스프레드 랩)은 import 와 함수 하나만 바뀐다 — 타입 검사가 scripts 를 포함하고, 사본에서 서버 없이 한 번 실행해 예외 0건을 확인했다(Context). 화면 모양은 바뀌지 않는다(표 반올림 자릿수 · 읽는 파일이 같다)
- **금리 공백의 오류 문구가 바뀐다** — 커버리지 사전 검사의 「필요 기간 …에서 …의 FFR 데이터가 없으며」 대신 날마다 조회하는 `lookup_ffr` 의 「필요 월 …의 FFR 데이터가 없으며」가 나온다. 멈추는 조건은 같다(첫 거래일만 조회하지 않는다 — 그날은 비용을 계산하지 않는다)
- **시가 결측이 결측으로 남는다** — 합성 저장 전 시세 표 검사가 멈춘다. 일별 비교 · 장기 대체는 시가를 쓰지 않거나(일별 비교) 같은 검사를 지난다
- **결과를 바꾸지 않는 변경이라 재실행으로는 회귀가 드러나지 않는다** — 완화: 사본에서 생성 스크립트 · 러너 재실행 뒤 바이트 대조, 변형 확인, AST 대조
- **스크래치 사본에서 포맷 도구가 저장소 설정을 못 찾은 일이 있었다**(2026-10-12, 진행 로그) — 사본을 만드는 스크립트가 `cd` 실패 · 설정 파일 부재에서 멈추게 했다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 결정 10 · 3-6 · 13-B D11 · 5-3 · 7-3 · 9-8(20절) · 4-3 · 5-1 · 2-2 · 2-13 · 4-2 · 6-5 · 6-7 · 7-6 · 5-6 · 5-7 · 4-6 · 2-16 · 2-22 · 8-4 · 8-7 · 13-C C7 · 13-T, 19절 11단계
- 점검 보고서의 줄 번호는 기준 커밋(`40011ad`) 값이라 지금 코드와 어긋난다. 이 계획서는 함수 이름으로 가리킨다
- 이 계획서가 일부만 처리하는 항목: 6-5(tqqq `simulate` 만 — `aggregate_monthly` 는 스프레드 랩, backtest · 포트폴리오 인자는 backtest) · 6-7(합성 스크립트 두 곳 · `simulate` 시가만) · 7-6(tqqq 누적수익률만) · 5-6(월별 로더 · 대체 비교 반올림만) · 5-7(`download_data.py` 만) · 4-6(tqqq 시뮬레이션 상수만) · 13-C C7(`tqqq/constants.py` 만) · 13-T(`test_tqqq_simulation_core.py` 의 설명 숫자 · 비용 모델 테스트의 열 이름 — 커버리지 테스트째 없어진다)
- 11단계 다음 계획서: 스프레드 랩 → backtest → 대시보드 → tests

### 진행 로그 (KST)

- 2026-10-12 18:25: 이전 세션 여덟의 로그 · 점검 보고서 · 미룬 지적 파일 · 계획 절차를 읽고, 대상 코드 · 테스트와 호출처를 읽었다. 사본(`step11b/base`) 기준 941 passed
- 2026-10-12 18:39: 사본에 변경을 얹어 생성 스크립트 다섯의 결과가 같음을 확인했다. 이어서 테스트 패치 스크립트가 단언에 걸려 멈춘 뒤, `cd` 가 실행되지 않은 채 `black .` 이 스크래치 상위 폴더에서 돌아 저장소 설정(줄 길이 120)을 못 찾고 사본 · 새 파일 351개를 기본값(88)으로 다시 포맷했다. 저장소는 건드리지 않았다(변경 0 확인). 수정 전 사본을 저장소에서 다시 뜨고 새 파일을 다시 썼으며, 사본 만들기를 `cd` 실패 · 설정 파일 부재에서 멈추는 스크립트 하나로 묶었다
- 2026-10-14 22:05: 사본 재구성 — 931 passed, Ruff · PyRight 통과, 생성 결과 13개 파일 동일, AST 대조, 변형 14종(첫 실행에서 「% 열 2자리」를 못 잡아 테스트의 기대값을 손으로 고정)
- 2026-10-14 22:15: 계획서 작성(Draft)
- 2026-10-14 22:20: 러너 여섯을 사본에서 돌렸다 — 조합 그리드 결과 3개가 저장소와 달랐고, 원인은 사본에서 다시 만든 대체 판 3개(결정 19 · 20)였다. 수정 전 사본에서 같은 시세로 조합 그리드를 돌려 수정 후와 274개 모두 같음을 확인했다. 대시보드 둘을 서버 없이 실행해 수정 전 · 후 모두 예외 0건
- 2026-10-14 22:16: 승인 — 사용자 「승인」(계획서대로 한 커밋). 저장소의 src · scripts · tests · `docs/research` · `pyrightconfig.json` 이 사본의 수정 전 기준과 같음을 확인했다(`diff -rq` 차이 0 — 저장소에만 있는 `tests/live` 는 지난 테스트의 `__pycache__` 만 남은 git 무시 폴더)
- 2026-10-14 22:17: Phase 1 — 사본에서 바뀐 파일 38개를 그대로 넣었다(지운 · 새로 만든 파일 없음). 저장소의 src · scripts · tests · `pyrightconfig.json` 이 수정 후 사본과 같다(`diff -rq` 차이 0) — 그래서 사본 재현(결과 287개 동일 · 변형 14종 · AST 대조 · 대시보드 둘)은 최종 코드의 결과다. 사라질 이름 0건, `ROUND_*` 정의는 `common_constants.py` 에만, 저장 경로의 숫자 반올림 0건. 관련 테스트 132 passed
- 2026-10-14 22:20: 문서 — `docs/AUDIT_REPORT.md`(결정 10, 2-2 · 2-13 · 2-16 · 2-22 · 3-6 · 4-2 · 4-3 · 5-1 · 5-3 · 7-3 · 8-4 · 8-7 · D11 처리 표시, 4-6 · 5-6 · 5-7 · 6-5 · 6-7 · 7-6 · 13-C C7 · 13-T · 15절의 일부 처리, 3-15 · 5-4 를 스프레드 랩으로 옮김, 6-T 네 행, 19절 11단계 tqqq · utils 줄과 backtest 줄), 루트 `CLAUDE.md`(반올림 표 두 행), `src/qbt/tqqq/CLAUDE.md`(상수 범주 · 월별 로더 · `simulate` 의 월별 값 조회 · 무결성 검사 · 검증 임계값 · abs 로그차이), `src/qbt/utils/CLAUDE.md`(원칙 문구 · 시세 표 검사의 사용처 · `save_stock_csv` · 대체 비교 반올림), `scripts/CLAUDE.md`(대용 생성의 저장 문장), `tests/CLAUDE.md`(자릿수 SoT). `black` 변경 없음(134 files left unchanged). 리뷰 전 사본은 스크래치 `step11b/r1_before/`
- 2026-10-14 22:30: `/code-review xhigh` 1회차 — 발견 10건. 버그 1 [무거움 1] · 그 외 9. 고칠 것(닿는 버그) 0 이라 회차는 여기서 끝난다. 반영한 그 외 6 은 뒤에 리뷰 회차가 없으므로 고치기 전 사본(`step11b/r1fix_before/`)을 떴다
  - 고치지 않은 버그 1(기준 1): ①(무거운 모양) 지운 두 번째 구현이 하던 가드 둘(두 시계열 길이 같음 · 첫 종가 > 0)이 없어져, 중복 날짜가 든 시뮬 결과나 첫 종가 0 인 실제 시세를 넣으면 `calculate_validation_metrics` 가 예외 없이 엇갈린 날짜끼리 비교하거나 inf 를 낸다(리뷰어가 스크래치에서 재현). 그런 입력은 시세 로더(`validate_price_series` — 중복 날짜 · 0 이하 가격에서 멈춤)를 지나야 하고, `simulate` 는 입력 날짜를 그대로 쓴다 — 지금 호출처(일별 비교 스크립트)는 둘 다 로더로 읽은 시세다. 닿게 하려면 로더를 거치지 않는 새 호출 코드가 필요하다
  - 반영한 그 외 6: ② 누적수익률(`cumulative_return_*`)을 보는 테스트가 없었다 — 더한 단언이 변형 둘(`/ 100` 빠뜨림 · 실제와 시뮬 뒤바뀜)을 잡는다 ④ `tests/CLAUDE.md` 가 자릿수 상수의 자리를 `common_constants.py` 하나로 적었다 — 한 모듈 전용 둘(입력 시세 · 일별 비교 % 열)이 그 모듈에 있다는 것과, 정책 자릿수는 테스트가 숫자로 고정한다는 것(이번 변형 확인의 교훈)을 적었다 ⑤ 새 테스트 셋의 반올림 결과 비교를 `pytest.approx`(반올림 단위보다 훨씬 작은 허용오차)로 ⑥ `validate_price_series` docstring 의 「생성 스크립트가 저장 전에 직접 부른다」 — 이제 `save_stock_csv` 를 거친다 ⑨ 타입 검사 범위를 연구 스크립트 한 파일 대신 `docs/research` 폴더로(지금 .py 는 그 하나라 검사 대상은 같다, PyRight 0 errors) ⑩ 월별 로더의 파일 없음 오류에 할 일(git 이 추적하는 파일이니 되살리기)
  - 반영하지 않은 그 외 3(기준 3): ③ 대체 비교 반올림 테스트가 기대값을 `ROUND_RATIO` · `ROUND_PERCENT` 로 만든다 — 그 두 상수는 모든 결과 파일의 자릿수 SoT 라 바꾸면 따라가는 것이 맞고, 열 종류와 자릿수의 대응은 변형 둘(자릿수 뒤바뀜 · % 열 빠뜨림)이 잡는다. 일별 비교의 % 열은 「4 미만이면 안 되는」 정책 값이라 숫자로 고정한 것과 다르다 ⑦ 스프레드 검사를 날마다 한다(성능 · 자리) ⑧ `simulate` 의 `funding_spread` 이름이 딕셔너리 둘과 다르다(이름 — PyRight 가 float 를 막는다)
- 2026-10-14 22:33: 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=931, failed=0, skipped=0. 1회차 수정분(9 hunk — 테스트 5 · docstring 1 · 오류 문구 1 · 안내 문서 1 · 타입 검사 설정 1)의 수정분 검증을 서브에이전트에 맡겼다
- 2026-10-14 22:36: 최종 확인 — 결과를 돌린 사본(`step11b/exp`)과 지금 저장소를 import · docstring 을 뺀 AST 로 대조해 실행 코드가 다른 곳은 월별 로더의 오류 문구(src)와 테스트 셋뿐이다(1회차 반영분). 결과에 닿지 않는 자리라 사본의 재현(결과 287개 동일 · 변형 14종 · 대시보드 둘)이 최종 코드에도 성립한다. 저장소 `storage/` 변경 0
- 2026-10-14 22:36: 근거 승격 — 남길 「왜」는 코드와 살아있는 문서에 있다: % 열을 4자리로 두는 이유는 `ROUND_DAILY_COMPARISON_PERCENT` 주석, 금리 공백을 사전 검사 없이 날마다 조회로 막는 것은 `src/qbt/tqqq/CLAUDE.md`, 합성만 급등락 검사를 끄는 이유는 `save_stock_csv` docstring · 합성 스크립트 주석 · `src/qbt/utils/CLAUDE.md`, 입력 자릿수의 자리는 루트 `CLAUDE.md` 표, 정책 자릿수를 테스트가 숫자로 고정하는 이유는 `tests/CLAUDE.md`. 처리 사실과 재현 수치는 점검 보고서 해당 행
- 2026-10-14 22:50: 수정분 검증 결과(1회차 반영분 9 hunk) — 무거움 0 · 가벼움 1 · 그 외 3. hunk 마다 세 물음(맞던 입력의 결과 변화 · 같은 모양 · 위험한 쪽으로의 변화)에 답이 있고, 세 물음 모두 「없음 / 아니오」인 hunk 가 7, 같은 모양이 남은 것이 둘이다. 타입 검사 범위를 폴더로 바꾼 것은 오류를 넣은 탐침 파일 둘(폴더 바로 아래 · 하위 폴더)을 수정 후 설정만 잡았다(수정 전 122 files · 0 errors ↔ 탐침 넣고 수정 후 124 · 4)
  - 거른 가벼움 1(기준 3 — 검사 보강, 막는 결함이 무겁지 않다): 누적수익률 단언이 실제 쪽 변형(`/ 100` 빠뜨림 · 첫날 값 · 최솟값)은 못 잡는다 — 테스트의 실제 마지막 날 누적수익률이 정확히 0 이라서다(시뮬 쪽 · 맞바꿈 변형은 잡는다). 이 값을 쓰는 곳은 일별 비교 스크립트의 DEBUG 로그 한 줄이다
  - 거른 그 외 3(기준 3): ① 같은 파일 `load_comparison_data` 등의 기존 오류 문구에 할 일이 없다(diff 밖 기존 코드) ② `tests/CLAUDE.md` 의 「정책 값」이 어느 상수인지 정하지 않는다 — `ROUND_RATIO` 를 4 → 5 로 바꿔도 테스트가 통과한다(수정 전과 같다) ③ `test_stock_downloader.py` 의 `== 200.0` 한 곳(정확히 표현되는 값)
- 2026-10-14 22:51: 마무리 — 미룬 지적: 새로 옮긴 것 0. 1회차 ① 은 기준 1, 1회차의 반영하지 않은 그 외 3 · 수정분 검증 4 는 기준 3. 미룬 지적 파일의 남은 1건(표시용 열의 테스트 공백)은 이 계획서의 대상이 아니다(11단계 tests). 이 계획서를 지워도 잃는 것이 없다 — 근거 승격(22:36)과 처리 사실 · 재현 수치(점검 보고서 해당 행)

---
