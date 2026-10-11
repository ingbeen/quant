# Implementation Plan: 포트폴리오 러너 · 대시보드 정리 — 낡은 파일 · 틀린 표시 · 읽는 곳 없는 결과를 걷어낸다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-11 12:32
**마지막 업데이트**: 2026-10-11 14:03
**관련 범위**: scripts(`backtest/run_portfolio_backtest.py` · `backtest/app_portfolio_backtest.py` · `backtest/app_single_backtest.py` · `tqqq/app_daily_comparison.py` · `data/download_data.py`), backtest(`engines/` · `csv_export.py` · `constants.py` · `portfolio_types.py` · `portfolio_validation.py` · `supplement_experiment.py`), utils(`stock_downloader.py`), tests(`tests/qbt/`), storage(`results/portfolio/` · `results/backtest/buy_and_hold_*/`)
**관련 문서**: `scripts/CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `docs/COMMANDS.md`, `docs/AUDIT_REPORT.md`(19절 8단계), `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 포트폴리오 러너가 낡은 결과 파일을 남기지 않고, 설정이 시작일을 정한 실험이 그날 시작하지 못하면 멈춘다 (미룬 지적 2건)
- [x] 목표 2: 「체결 전후 비교」 표를 지우고, 리밸런싱 마커의 사유를 매매법별 장부 사유로 보인다 (미룬 지적 2건 · 결정 2)
- [x] 목표 3: 읽는 코드가 없는 결과(에쿼티 표의 파생 열 넷 · 자산별 요약의 네 칸 · 기간 지정 다운로드)를 지우고, 남는 결과는 형식을 맞춘다 (체결 금액 정수 · 거래가 없어도 같은 헤더 · 설정 전체가 담긴 `portfolio_config`)
- [x] 목표 4: 포트폴리오 대시보드가 없는 값을 N/A · 0 으로 넘기지 않고, TQQQ 일별 비교 대시보드가 CSV 를 다시 만들면 새로 읽는다
- [x] 목표 5: 성과 수치는 하나도 바뀌지 않는다 — 바뀌는 결과 파일은 아래 「데이터/결과 영향」에 적은 것뿐이다

## 2) 비목표(Non-Goals)

- **워크포워드 대시보드의 「값이 없으면 넘어간다」 세 곳**(점검 보고서 9-9 의 `app_walkforward.py` 부분) — 하지 않는다. 그 셋은 「파일이 없으면 None」을 돌려주는 로더의 호출부이고, 같은 로더의 나머지 호출부는 12-9(11단계 대시보드)가 고친다. 한 번에 고쳐야 로더가 한 모양이 된다 → 9-9 행에 적어 11단계로 넘긴다
- **자산 열 이름 헬퍼 일곱을 `asset_col(key, suffix)` 하나로 통합**(3-1 의 제안) — 하지 않는다. 호출부가 src · scripts 47곳(tests 0곳)인데, 통합하면 줄어드는 것은 한 줄 래퍼 여섯이고 호출부 47곳이 모두 길어진다(`asset_shares_col(key)` → `asset_col(key, ASSET_COL_SUFFIX_SHARES)`). 이 계획서는 3-1 이 짚은 실제 어긋남 — 이미 있는 헬퍼를 쓰지 않는 세 줄(`portfolio_methods.py` `summarize_methods`) — 만 고친다 (승인 때 사용자가 고른다)
- **엔진이 배분 조정에 사유 값을 적게 바꾸기** — 하지 않는다. 장부(`ledger.csv`)에 매매법별 사유가 이미 있어 대시보드만 고치면 된다(17절 11번의 정정). 엔진을 바꾸면 채택 조합의 `equity.csv` · `state_log.csv` · `ledger.csv` 사유 열이 바뀐다
- **`min_start_date` 를 엔진이 읽게 하기 · 칸 이름 바꾸기**(8-8 의 보류안) — 러너만 고친다
- **`TRADE_TYPE_REBALANCE` 를 쓰는 파일로 옮기기** — 한 파일(`portfolio_execution.py`)만 쓰지만 `TRADE_TYPE_SIGNAL`(두 파일)과 같은 열의 값 한 쌍이라 `constants.py` 에 함께 둔다. 3계층 규칙을 글자대로 따르면 쌍이 두 파일로 갈린다(3-8 이 남긴 「자리를 함께 정한다」의 답)
- **`meta.json` 의 쓰이지 않는 키**(6-8 의 앞부분) — 결정 6(실행 이력 기능 삭제, 11단계)이 통째로 지운다
- **러너 · 엔진의 그 밖의 정리** — `_CONFIG_MAP` 인라인(4-8) · `f"ma_{…}"`(3-18) · 상태 로그가 빈 경우의 분기(6-7 의 한 줄) · 주석의 없는 실험 이름(13-C C2)은 11 · 12단계에 그대로 둔다
- **`download_data.py` 의 한 줄 래퍼 인라인**(5-7) — 11단계. 이 계획서는 기간 인자만 지운다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 8단계다. 미룬 지적 파일에 남은 4건이 모두 이 단계 대상이고, 결정 2(「체결 전후 비교」 표 삭제) · 8(거래 기록 열은 두고 체결 금액만 반올림) · 16(기간 지정 다운로드 삭제)이 걸려 있다
- 대상마다 지금 무엇이 틀리는가 (2026-10-11 지금 코드 · 결과 파일에서 다시 쟀다. 스크래치 `step8/`)

| 항목 | 지금 | 근거 |
|---|---|---|
| 미룬 지적 「낡은 장부」(17절 4번) | 러너는 실험 구성에 따라 생기는 파일(`signal_{자산 키}.csv` · `ledger.csv` · `netting.csv`)을 지우지 않는다. 대시보드는 파일이 있으면 그린다 | 재현: 채택 조합 결과 폴더(22개 파일)에 매매법 하나짜리 Q-2-2XS 를 다시 저장 → 이번 실행이 쓰지 않은 파일 17개가 남고, 대시보드 시그널 선택지 19개 중 15개가 실험에 없는 자산이며 「매매법별 손익」 섹션이 그려진다 |
| 미룬 지적 「체결 전후 비교」(17절 6번 · 결정 2) | 매수만 있는 체결일이 표에서 빠지고 사유가 그날 계좌 사유 하나로 붙는다. 매도가 없는 실험은 파일이 없어 「재실행하세요」가 뜬다 | 17절 6번 실측. 같은 값(체결일의 주수 · 비중)은 `equity.csv` · `state_log.csv` 에 있다 → 표 · CSV 를 지운다 |
| 미룬 지적 「시작일 미대조」(17절 10번 · 8-8) | 러너의 시작일은 max(데이터 기준, 2005-01-01, `min_start_date`)라, 시세가 바뀌어 데이터 기준일이 늦어지면 조용히 늦게 시작한다 | 재현: TIP 의 2006-10-02 행 하나를 뺀 시세로 채택 조합 실행 → exit 0, 「기간: 2007-06-25 ~ 2026-09-24」(설정은 2007-06-22). 지금 여유는 0일(데이터 기준일 = 2007-06-22) |
| 미룬 지적 「배분 조정 사유」(17절 11번) | 에쿼티 차트의 리밸런싱 마커가 계좌 사유 하나만 보인다. 계좌 사유는 그날 리밸런싱한 매매법 중 설정 순서상 첫 매매법의 사유다 | 채택 조합: 리밸런싱한 날 105일 중 4일(2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-04-01)은 Q-2-2XS 정기 리밸런싱과 HAA 의 비중 조정이 겹쳤는데 「월초 정기」만 보인다. 장부에는 HAA 가 사유 없이 조정한 날 17일이 모두 있다. 슬롯 매매법이 사유 없이 리밸런싱한 행은 0 |
| 2-5 | `equity.csv` 의 `{자산}_current_price` · `{자산}_return_pct` · `total_pnl` · `total_return_pct` 가 반올림 없이 저장된다 | 읽는 코드: src · scripts 0곳(테스트 4개만). 다섯 실험에서 4 · 10 · 10 · 32 · 4열 |
| 6-13(결정 8) | `trades.csv` 의 `order_amount` 가 소수 9 – 13자리로 저장된다 | 예: `10038047.23998209`. 읽는 코드 0곳 — 사람이 보는 기록이라 열은 둔다 |
| 6-8 | `summary.json` `per_asset` 의 `total_trades` · `win_rate` · `final_shares` · `final_avg_price` 를 읽는 코드가 없고, 거래 수 · 승률은 리밸런싱 부분 매도까지 센 수다 | 대시보드가 읽는 칸은 `asset_id` · `target_weight` · `open_position` |
| 7-11 | 설정을 손으로 옮겨 적어(53줄) `min_start_date` 가 `summary.json` 에 없다 — 채택 조합이 2007-06-22 에 시작하는 이유가 결과에 없다 | `_build_params_json` · `_slot_params`. 읽는 코드는 대시보드의 `st.json` 하나 |
| 2-12 · 2-8 | 거래가 없는 결과의 `trades.csv` 헤더가 다르다 | `portfolio_qqq_bh` 10열(나머지 15열), 단일 백테스트 B&H 6개는 줄바꿈 한 글자뿐이라 단일 대시보드가 `EmptyDataError` 를 잡아 넘긴다 |
| 9-9 | 포트폴리오 대시보드가 `summary.json` 의 값이 없으면 N/A · 0 으로 넘어가고, 현금 비중을 「1 − 자산 비중 합」을 0 에서 잘라 그린다 | 음수라 잘린 행: Q-2 534 · Q-2-2XS 574 · 채택 조합 18. `cash / equity` 와 최대 0.0292%p 차 |
| 2-4 | TQQQ 일별 비교 대시보드의 캐시 키에서 파일 수정 시각이 빠진다 | Streamlit 1.63.0 실측: 인자 이름이 `_mtime` 이면 값을 1.0 → 2.0 으로 바꿔도 본문 실행 1회, `mtime` 이면 2회 |
| 3-8 | 리밸런싱 사유 문자열이 엔진(비공개 상수) · `portfolio_methods.py` · `portfolio_validation.py` · 러너 · 대시보드에 따로 적혀 있다 | `grep '"monthly"\|"methods"\|"allocation"'` |
| 12-8 | 러너가 늘 있는 값에 `.get` · 존재 검사를 쓴다 | `s.get("start_date", "")` · `_find_last_entry_date` 의 닿지 않는 분기 둘 |
| 결정 16 | `download_data.py --start/--end` 로 받은 파일(`{TICKER}_{START}_…csv`)을 읽는 코드가 없다 | `load_stock_data` 호출부는 모두 `*_max.csv` 경로 상수 |

- **낡은 파일을 지우는 규칙을 지금 결과 폴더에 대 본 것**(글자 규칙이 삭제에 물리는 자리): 지우는 것은 실험 결과 폴더 바로 아래의 `signal_*.csv` · `ledger.csv` · `netting.csv` 다. 지금 다섯 폴더에서 걸리는 파일은 27개(시그널 25 · 장부 1 · 상계 1)이고 모두 러너가 같은 실행에서 다시 쓰는 파일이다 — 러너가 만들지 않은 파일은 0개. 결과 폴더는 git 이 추적하므로 잘못 지워도 되돌릴 수 있다. 폴더째 지우지 않는 이유는 실험 이름이 비면 `result_dir` 이 결과 폴더 전체가 되기 때문이다(17절 4번)

### 설계 결정

1. **러너는 저장 전에 「구성에 따라 생기는 파일」만 지운다** — `signal_*.csv` · `ledger.csv` · `netting.csv`. 늘 쓰는 파일(`equity` · `trades` · `state_log` · `summary`)은 덮어쓰이므로 지우지 않는다
2. **「체결 전후 비교」는 통째로 지운다**(결정 2) — 러너의 표 생성 함수 · 저장 · 사유 상수, 대시보드의 로더 · 섹션, 결과 CSV 4개, 문서 설명. 지금 있는 CSV 4개는 이 계획서가 한 번 지운다(러너는 그 파일을 더는 모른다)
3. **설정에 `min_start_date` 가 있으면 러너는 `run_with_start_check(config, config.min_start_date)` 로 돌린다** — 그리드 워커 둘이 쓰는 함수다(직접 호출 2곳: `run_grid_case` · `run_combo_case`). 실제 첫 거래일이 그날이 아니면 ValueError
   - 러너가 계산한 시작일과 견주지 않는다 — 계산값은 데이터가 늦어지면 함께 늦어져 같아진다(17절 10번)
   - 달라지는 뜻: `min_start_date` 는 「이 날짜보다 앞서지 않는다」에서 「이 날짜에 시작한다」가 된다. 그리드가 같은 칸을 그렇게 쓴다. 2005-01-01 하한은 이 칸이 없는 실험에만 건다
   - 멈추는 시점은 그 실험을 돌린 직후 · 저장 전이다. 앞 실험의 결과는 이미 저장됐지만 그 실험들의 맞는 결과다
4. **리밸런싱 마커의 hover 는 장부 사유로 만든다** — 매매법이 여럿이면 그날 리밸런싱한 매매법마다 「매매법 이름: 사유」를 한 줄씩, 매매법이 하나면 계좌 사유 그대로(장부 = 계좌). 문구 사전은 대시보드에 하나(「월초 정기」 · 「매매법 사이 비중」 · 빈 사유 = 「배분 조정」), 모르는 사유는 KeyError 로 멈춘다
   - 사유 값 `"monthly"` · `"methods"` 는 `backtest/constants.py` 의 공개 상수로 올려 엔진 · 요약 · 검사기 · 대시보드가 같이 쓴다. 점검 보고서는 `portfolio_types.py` 를 제안했지만, 3계층 규칙의 「도메인 안 두 파일 이상 → `constants.py`」와 바로 옆 선례(`TRADE_TYPE_*`)를 따른다
5. **에쿼티 표의 파생 열은 기여 손익(`{자산}_contribution`)만 남긴다** — 대시보드와 매매법 요약이 읽는다. `build_combined_equity` 는 드로우다운과 그 열만 더하고 `initial_capital` 인자가 없어진다(호출처 1곳). 열이 없을 때의 0 대체 분기(6-7)와 메시지용 가드(7-8)는 함수가 줄면서 함께 사라진다 — 열이 없으면 KeyError 로 멈춘다
6. **거래 표는 행이 없어도 열을 갖는다** — 두 엔진이 `pd.DataFrame(거래, columns=거래 기록 타입의 키)` 로 만든다(`TradeRecord` 9열 · `PortfolioTradeRecord` 14열. 키 순서는 지금 CSV 헤더와 같다). `prepare_trades_for_csv` 는 빈 표에도 `holding_days` 를 붙이고, `order_amount` 를 `ROUND_CAPITAL` 로 반올림해 정수로 바꾼다. 단일 대시보드의 `EmptyDataError` 처리 3줄은 지운다
7. **`params_json` 은 `dataclasses.asdict(config)` 로 만든다** — 경로 · 날짜는 `dict_factory` 에서 문자열로 바꾼다. 점검 보고서의 `json.dump(default=str)` 는 쓰지 않는다 — 직렬화하지 못하는 값을 조용히 문자열로 바꾸는 대체라 12-11 이 지우려는 모양이고, 값이 처음부터 JSON 값이면 저장하는 쪽 둘(`summary.json` · `meta.json`)을 고칠 필요가 없다. 리밸런싱 규칙 두 칸은 엔진 상수라 설정에 없으므로 함께 적는다
   - 바뀌는 모양: 슬롯 목록의 키 `assets` → `asset_slots`, 더해지는 칸 `result_dir` · `min_start_date` · 빈 쪽 목록(`asset_slots` 또는 `methods`)
8. **자산별 요약은 `asset_id` · `target_weight` · `open_position` 만 쓴다** — 미청산 진입일 함수(`_find_last_entry_date`)는 닿지 않는 분기 둘을 지워 세 줄이 된다(최종일에 보유 중인 자산에만 부른다)
9. **대시보드는 `summary.json` 을 직접 인덱싱한다**(9-9) — 요약 추출 헬퍼 둘과 「매매법별 손익」 섹션 · 비교 표 · 요약 지표의 `.get(…, 기본값)` · 빈 값 분기. 형 변환(`int(…)` · `float(…)`)은 그대로 둔다. 현금 비중은 `cash / equity`
10. **기간 지정 다운로드는 CLI 인자와 `download_stock_data` 의 인자를 함께 지운다**(결정 16) — CLI 만 지우면 src 인자가 테스트 둘만 부르는 죽은 인자로 남는다

### 사본 재현 (착수 전 확인, 2026-10-11)

저장소 밖 사본(스크래치 `step8/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **수정 전 코드에 새 테스트만 얹으면 7 failed · 901 passed** — 새 단언 5(빈 거래 표의 열 3 · 체결 금액 1 · `params_json` 1)와 키 이름이 바뀌는 기존 테스트 2
- **수정 뒤 908 passed** (지금 911 − 지우는 테스트 6 + 새 테스트 3), Ruff 통과, PyRight 0 errors
- **변형 14종 중 13종을 잡는다** — 체결 금액 반올림 · 정수 변환 삭제, 빈 표를 변환 없이 반환, 빈 표에 `holding_days` 안 붙임, 두 엔진의 빈 표 열 삭제(계좌 · 자산별), `params_json` 의 문자열 변환 삭제 · 날짜만 누락 · `min_start_date` 누락 · 리밸런싱 칸 누락, 기여 손익에서 미실현 누락, `"methods"` 값 변경
  - 못 잡는 하나: `"monthly"` 상수의 값 자체를 바꾸는 것. 결함이 아니다 — 엔진과 대시보드가 같은 상수를 써서 함께 바뀐다
- **결과 파일** — 사본에서 러너 여섯(단일 · 포트폴리오 · 단독 그리드 · 조합 그리드 · 고원 · 워크포워드)을 모두 돌렸다. `storage/` 324개 파일 중 저장소와 다른 것은 22개이고 모두 아래 「데이터/결과 영향」에 적은 것이다
  - `equity.csv` 5개: 지운 열을 빼면 글자 단위로 같다(열 18 → 14 · 48 → 38 · 48 → 38 · 159 → 127 · 18 → 14, 새 열 0)
  - `trades.csv` 5개: 4개는 `order_amount` 밖이 같고 새 값 = 옛 값의 정수 반올림, `portfolio_qqq_bh` 는 헤더만 10열 → 15열
  - `summary.json` 5개: 바뀐 최상위 키는 `per_asset`(네 칸 삭제, 나머지 같음) · `portfolio_config` 둘
  - 단일 백테스트 B&H `trades.csv` 6개: 줄바꿈 한 글자 → 버퍼존 결과와 같은 헤더 한 줄
  - `meta.json`: 실행 이력
  - 그리드 CSV · 워크포워드 · 고원 · `signal_*` · `state_log` · `ledger` · `netting` 은 같다
- **미룬 지적 재현(수정 전 → 후)**
  - 낡은 파일: 남는 파일 17개 → 0개(옛 `execution_comparison.csv` 하나는 설계 결정 2 로 따로 지운다), 시그널 선택지 19개 → 4개, 장부 파일 있음 → 없음
  - 시작일: exit 0 · 2007-06-25 시작 → exit 1 「실제 시작일 2007-06-25 가 묶음 시작일 2007-06-22 와 다릅니다 …」, 결과 파일 0개
  - 사유: 채택 조합 105일의 hover 가 6종 — HAA 「배분 조정」이 보이는 날 17일(가려졌던 4일 포함). Q-2 59일 · Q-2-2XS 73일은 「리밸런싱 (월초 정기)」 그대로
- **대시보드** — 앱 모듈을 화면 없이 불러(서버 · 포트 없음) 확인했다. 직접 인덱싱하는 키는 다섯 실험 모두에 있고 시그널 파일 키 = `per_asset` 키다. 대시보드 넷(포트폴리오 · 단일 · TQQQ 일별 비교 · 워크포워드)의 `main()` 을 새 결과에서 한 번씩 실행해 예외 0건. 수정한 단일 대시보드를 옛 결과(1바이트 `trades.csv`)에 대면 `EmptyDataError` 로 멈춘다 → 결과 재산출이 같은 계획서 안에 있어야 한다
- **변경 규모(포맷 적용 뒤)** — src 11파일 +73 / −206, scripts 5파일 +203 / −428, tests 5파일 +111 / −145. 러너 629 → 466줄, 포트폴리오 대시보드 1,541 → 1,466줄
- **소요** — 단일 4초 · 포트폴리오 12초 · 단독 그리드 82초 · 조합 그리드 127초 · 고원 41초 · 워크포워드 139초

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」 · 「가격 반올림 자릿수」 절
- `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 구성이 바뀐 실험을 같은 폴더에 다시 저장해도 이전 실행의 시그널 · 장부 · 상계 파일이 남지 않는다(사본 재현으로 확인)
- [x] `min_start_date` 가 있는 실험이 그날 시작하지 못하면 러너가 저장 전에 멈춘다(사본 재현으로 확인)
- [x] 「체결 전후 비교」의 코드 · 결과 CSV · 문서 설명이 없다
- [x] 리밸런싱 마커 hover 가 매매법별 사유를 보인다 — 채택 조합에서 HAA 「배분 조정」 17일이 모두 보인다(결과 파일로 확인)
- [x] 거래가 없는 결과의 `trades.csv` 가 거래가 있는 결과와 같은 헤더를 갖고, `order_amount` 가 정수다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] `summary.json` 의 `portfolio_config` 에 `min_start_date` 가 있다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] 결과 파일 변화가 「데이터/결과 영향」에 적은 것뿐이다 — 저장소에서 다시 만든 결과가 사본 결과와 같다(`meta.json` 제외)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `docs/COMMANDS.md` · `docs/AUDIT_REPORT.md`. `README.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 새로 옮긴 것 0(미조치 지적은 거르는 기준에 걸리거나 사용자가 정했다 — 받아들임 1 · 점검 보고서 3-3 행에 덧붙임 1), 이 계획서가 고친 항목 넷은 파일에서 지웠다. 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/run_portfolio_backtest.py` — 낡은 파일 삭제, 표 생성 삭제, 시작일 대조, 자산별 요약 · 진입일 함수 단순화, 직접 인덱싱
- `scripts/backtest/app_portfolio_backtest.py` — 표 섹션 · 로더 삭제, 사유 hover, 직접 인덱싱, 현금 비중
- `scripts/backtest/app_single_backtest.py` — `EmptyDataError` 처리 삭제
- `scripts/tqqq/app_daily_comparison.py` — 캐시 키 인자 이름, 한 줄 래퍼 인라인
- `scripts/data/download_data.py` · `src/qbt/utils/stock_downloader.py` — 기간 인자 삭제
- `src/qbt/backtest/constants.py` — 리밸런싱 사유 상수 둘, `COL_ORDER_AMOUNT`
- `src/qbt/backtest/csv_export.py` — 빈 표의 열, 체결 금액 반올림
- `src/qbt/backtest/engines/backtest_engine.py` · `portfolio_engine.py` · `portfolio_data.py` · `portfolio_execution.py` · `portfolio_methods.py` — 거래 표의 열, `params_json`, 파생 열 삭제, 상수 사용, 헬퍼 사용
- `src/qbt/backtest/portfolio_validation.py` — 사유 상수 사용
- `src/qbt/backtest/portfolio_types.py` · `supplement_experiment.py` — docstring(열 명세 · `min_start_date` · 13-B D6 의 두 문장)
- `tests/qbt/test_csv_export.py` · `test_buy_and_hold.py` · `test_portfolio_strategy_types.py` · `test_portfolio_backtest_scenarios.py` · `test_stock_downloader.py`
- `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `docs/AUDIT_REPORT.md` · `docs/DEFERRED_FINDINGS.md`(착수 때 「고치는 중」, Done 때 삭제)
- `docs/COMMANDS.md`: 변경 있음 — 포트폴리오 출력 목록의 `execution_comparison` 삭제(13-B D14), 「데이터 다운로드 옵션」의 `--start` · `--end` 예시 삭제
- `README.md`: 변경 없음

### 데이터/결과 영향

- 성과 수치(CAGR · MDD · Calmar · 자본 곡선 · 거래)는 바뀌지 않는다. 바뀌는 파일은 아래뿐이고, 저장소에서 러너 둘(`run_single_backtest.py` · `run_portfolio_backtest.py`)을 다시 돌려 만든다 — 그리드 · 워크포워드 · 고원은 결과가 같아 저장소에서 다시 돌리지 않는다

| 파일 | 수 | 바뀌는 것 |
|---|---|---|
| `storage/results/portfolio/*/equity.csv` | 5 | 파생 열 삭제(`*_current_price` · `*_return_pct` · `total_pnl` · `total_return_pct`) |
| `storage/results/portfolio/*/trades.csv` | 5 | `order_amount` 정수(4개), `portfolio_qqq_bh` 는 헤더가 15열로 |
| `storage/results/portfolio/*/summary.json` | 5 | `per_asset` 네 칸 삭제, `portfolio_config` 형식 |
| `storage/results/portfolio/*/execution_comparison.csv` | 4 | 삭제 |
| `storage/results/backtest/buy_and_hold_*/trades.csv` | 6 | 빈 파일 → 헤더 한 줄 |
| `storage/results/meta.json` | 1 | 실행 이력 |

## 6) 단계별 계획(Phases)

### Phase 0 — 재현 테스트(레드)

**작업 내용**:

- [x] `test_csv_export.py` — 행이 없는 거래 표도 입력 열 + `holding_days` 로 변환된다 · `order_amount` 가 반올림된 정수다
- [x] `test_buy_and_hold.py` · `test_portfolio_strategy_types.py` — 거래가 없는 결과의 `trades_df` 열이 거래 기록의 열 그대로다(단일 9열 · 포트폴리오 14열, 자산별 표 포함)
- [x] `test_portfolio_backtest_scenarios.py` — `params_json` 이 설정의 모든 칸을 JSON 값으로 담는다(`min_start_date` · 경로 · 리밸런싱 두 칸). `test_portfolio_strategy_types.py` 의 `params_json` 테스트 둘은 키 이름을 새 모양으로
- [x] 지우는 테스트 — 파생 열 넷의 테스트 4개(`TestPortfolioHoldingViewColumns` — 기여 손익 테스트 하나는 남기고 클래스 이름을 맞춘다), 기간 지정 다운로드 테스트 2개

**Validation**:

- [x] 새 단언과 키 이름을 고친 테스트가 지금 코드에서 실패한다(사본에서 7 failed)

---

### Phase 1 — 결과 표의 열과 설정 직렬화(그린)

**작업 내용**:

- [x] `constants.py` — `REBALANCE_REASON_MONTHLY` · `REBALANCE_REASON_METHODS` · `COL_ORDER_AMOUNT`
- [x] `csv_export.py` — `add_holding_days` 가 빈 표에도 열을 붙이고, `prepare_trades_for_csv` 가 빈 표를 같은 길로 변환하며 `order_amount` 를 정수로
- [x] `backtest_engine.py` · `portfolio_engine.py` — 거래 표를 거래 기록 타입의 키로 만든다. `portfolio_engine.py` 는 `params_json` 을 `asdict` 로(`_build_params_json` · `_slot_params` 삭제), 사유 상수 사용
- [x] `portfolio_data.py` — `build_combined_equity` 가 드로우다운과 기여 손익만 더한다
- [x] `portfolio_execution.py` · `portfolio_methods.py` · `portfolio_validation.py` — 상수 · 헬퍼 사용
- [x] `portfolio_types.py` · `supplement_experiment.py` — docstring

**Validation**:

- [x] `poetry run pytest tests/qbt/test_csv_export.py tests/qbt/test_buy_and_hold.py tests/qbt/test_portfolio_*.py tests/qbt/test_supplement_experiment.py tests/qbt/test_combo_experiment.py tests/qbt/test_allocators.py` — 전부 통과(Phase 0 의 테스트 포함)

---

### Phase 2 — 포트폴리오 러너 · 대시보드와 그 밖의 스크립트(그린)

**작업 내용**:

- [x] `run_portfolio_backtest.py` — 낡은 파일 삭제, 표 생성 · 사유 상수 삭제, `run_with_start_check`, 자산별 요약 · `_find_last_entry_date`, 직접 인덱싱
- [x] `app_portfolio_backtest.py` — 표 섹션 · 로더 · 요약 추출 헬퍼 삭제, `_build_rebalance_hover_texts`, 직접 인덱싱, 현금 비중
- [x] `stock_downloader.py` · `download_data.py` — 기간 인자 삭제
- [x] `app_daily_comparison.py` — `mtime` 인자 · 인라인. `app_single_backtest.py` — `EmptyDataError` 처리 삭제

**Validation**:

- [x] `poetry run pytest tests/qbt/test_stock_downloader.py` — 통과
- [x] 사본(최종 코드)에서 미룬 지적 재현 셋 — 낡은 파일 0개 · 시작일이 어긋나면 exit 1 · HAA 「배분 조정」 17일

---

### 마지막 Phase — 결과 재산출 · 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 결과 재산출(저장소) — `git status --short storage/` 가 비어 있는지 확인 → `execution_comparison.csv` 4개 삭제 → `run_single_backtest.py` · `run_portfolio_backtest.py` 실행 → 바뀐 파일이 「데이터/결과 영향」의 26개뿐인지(`git status`), 사본 결과와 같은지(`meta.json` 제외) 대조
- [x] 결과 불변 확인(사본) — 최종 코드의 사본에서 러너 여섯을 돌려 그리드 · 워크포워드 · 고원 결과가 저장소와 같은지
- [x] 새 검사의 변형 확인 — 「사본 재현」의 변형을 최종 코드에 다시 돌린다
- [x] 대시보드 확인(화면 없음) — 앱 모듈을 불러 대시보드 넷의 `main()` 을 저장소의 새 결과에서 한 번씩 실행해 예외가 없는지 본다. Streamlit 서버를 띄우지 않는다(포트 · 상주 프로세스 없음) — 화면 확인은 사용자 몫이고 Done 보고에 볼 지점을 적는다
- [x] 문서 — `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `docs/COMMANDS.md` · `docs/AUDIT_REPORT.md`(처리 표시 · 19절 · 넘긴 항목) · `docs/DEFERRED_FINDINGS.md`(고친 4건 삭제). `README.md` 변경 없음
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 11건 — 버그 5 [무거움 0 · 가벼움 5] · 그 외 6 · 조치: 가벼움 2 수정(사용자 결정 — 시작일을 실행 전에 확인 · 러너 맥락의 문구) · 가벼움 3 미조치(닿지 않음 2 · 막는 쪽 1) · 그 외 3 반영 · 3 미조치)
- [x] `/code-review xhigh` **2회차** (발견 9건 — 버그 5 [무거움 3 · 가벼움 2] · 그 외 4 · 조치: 무거움 1 수정(검사 공백 — 매매법 여럿 설정의 params_json 테스트) · 무거움 2 사용자에게 올림(같은 자리 두 번 → 그대로 · 낡은 파일 삭제의 테스트 → 11단계 3-3 과 함께) · 가벼움 2 미조치(닿지 않음 1 · 막는 쪽 1) · 그 외 2 반영 · 2 미조치)
- [x] 수정분 검증 (2회차 수정 3 hunk · 발견 5건 — 무거움 0 · 조치: 문서 문구 1건은 사용자 결정(그대로 둠)에 맞춰 사실대로 고침 · 나머지 4건 기록)
- [x] `poetry run python validate_project.py` (passed=909, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 포트폴리오 러너 · 대시보드 정리와 미룬 지적 4건 처리
2. 백테스트 / 낡은 결과 파일 삭제, 등록 실험 시작일의 실행 전 대조, 「체결 전후 비교」 표 삭제, 리밸런싱 사유의 매매법별 표시
3. 백테스트 / 대시보드가 낡은 장부 · 가려진 사유를 에러 없이 보이던 경로 차단과 읽는 곳 없는 결과 열 삭제
4. 백테스트 / 점검 보고서 8단계 처리 — 결과 파일 형식 정리(파생 열 · 체결 금액 · 빈 거래 헤더 · 설정 칸)와 기간 지정 다운로드 삭제
5. 백테스트 / build_combined_equity 축소, params_json 의 asdict 전환, 거래 표 열 고정, TQQQ 일별 비교 캐시 키 수정

## 7) 리스크(Risks)

- **코드와 결과 파일이 잠깐 어긋난다** — 단일 대시보드는 `EmptyDataError` 처리를 지운 뒤 옛 1바이트 `trades.csv` 를 만나면 멈춘다(사본 실측). 완화: 결과 재산출을 같은 계획서의 마지막 Phase 에서 하고, 재산출 뒤 대시보드 넷을 화면 없이 한 번씩 실행해 본다
- **낡은 파일 삭제가 엉뚱한 파일을 지울 수 있다** — 지우는 것은 결과 폴더 바로 아래의 세 패턴뿐이고 지금 다섯 폴더에서 러너가 만들지 않은 파일은 0개다(Context). 결과 폴더는 git 이 추적한다
- **`min_start_date` 의 뜻이 「하한」에서 「그날 시작」으로 바뀐다** — 지금 이 칸을 쓰는 등록 실험은 하나이고 데이터 기준일과 같아(2007-06-22) 결과가 같다. 앞으로 시세를 다시 받아 그날 시작하지 못하면 러너가 멈춘다 — 그때 할 일은 오류 문구대로 묶음 시작일(`MAIN_START_DATE`)을 다시 재고 그리드를 다시 돌리는 것이다(조용히 다른 기간으로 도는 것을 멈추는 쪽으로 바꾼다)
- **직접 인덱싱은 옛 형식의 `summary.json` 에서 멈춘다** — 대시보드가 읽는 키는 다섯 실험 모두에 있다(사본 실측). 형식이 다른 옛 파일을 만나면 N/A 대신 KeyError 가 난다 — 러너를 다시 돌리라는 신호다
- **`portfolio_config` 의 키 이름이 바뀐다** — 읽는 코드는 대시보드의 `st.json`(그대로 펼쳐 보임) 하나다. `meta.json` 의 실행 이력에도 같은 모양이 들어간다(읽는 코드 0)
- **사유 문구 사전에 없는 사유가 생기면 대시보드가 멈춘다** — 엔진이 내는 사유는 상수 둘과 빈 값뿐이다. 새 사유를 엔진에 더하면 사전에도 더해야 하고, 빠뜨리면 틀린 문구 대신 KeyError 가 난다
- **대시보드 변경은 pytest 밖이다** — scripts 는 테스트가 불러올 수 없다. 완화: 결과 파일로 계산한 대조(사유 17일 · 키 존재 · 현금 비중)와 화면 없는 실행. 화면 모양(문구 줄바꿈 등)은 사용자 확인이 필요하다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 17절 4 · 6 · 10 · 11번, 2-4 · 2-5 · 2-8 · 2-12 · 3-1 · 3-8 · 6-8 · 6-13 · 7-11 · 8-8 · 9-9 · 12-8 · 13-B D6 · D13 · D14, 결정 2 · 8 · 16, 19절 8단계
- 같은 줄을 고치면서 함께 풀리는 다른 단계의 항목: 6-7 의 러너 여덟 자리(표 함수 안 넷 · 진입일 함수 둘 · `entry_date is not None`)와 `portfolio_data.py` · `portfolio_engine.py` 한 자리씩, 6-15 의 hover 블록 네 줄, 7-8 의 `portfolio_data.py` 가드, 12-9 중 단일 대시보드의 `EmptyDataError`, 5-7 중 `app_daily_comparison.py` 의 한 줄 래퍼 — 점검 보고서의 그 행들에 처리 사실을 적는다
- 점검 보고서의 줄 번호는 기준 커밋(`40011ad`) 값이라 지금 코드와 어긋난다. 이 계획서는 함수 이름으로 가리킨다

### 진행 로그 (KST)

- 2026-10-11 12:32: 계획서 작성(Draft). 이전 세션 넷의 로그 · 점검 보고서 · 미룬 지적 파일을 읽고, 대상 코드와 호출처를 읽은 뒤 사본 재현을 마쳤다(Context 「사본 재현」). 미룬 지적 4건의 출처에 「고치는 중」을 달았다
- 2026-10-11 12:54: 승인 — 사용자 「승인 — 헬퍼는 최소 수정」(비목표의 3-1 통합은 하지 않는다) · 「대시보드를 화면 없이 한 번 실행해 예외만 확인하는 검증을 써도 됨」. Phase 0 착수
- 2026-10-11 12:54: Phase 0 — 사본에서 검증한 테스트 5파일을 저장소에 넣었다. 수정 전 코드에서 7 failed · 77 passed(그 5파일만 실행). 사본에서 잰 7건과 같다
- 2026-10-11 12:54: Phase 1 — src 10파일(`constants.py` · `csv_export.py` · 엔진 다섯 · `portfolio_types.py` · `portfolio_validation.py` · `supplement_experiment.py`). 포트폴리오 · 보완 전략 · 조합 · 배분 규칙 · CSV 변환 · 매수 후 보유 테스트 378 passed
- 2026-10-11 12:55: Phase 2 — scripts 5파일과 `stock_downloader.py`. `test_stock_downloader.py` 10 passed. 저장소의 src · scripts · tests 가 사본에서 검증한 코드와 같음을 `diff -rq` 로 확인했다(차이 0) — 그래서 사본 재현의 미룬 지적 셋(낡은 파일 17 → 0 · 시작일이 어긋나면 exit 1 · HAA 「배분 조정」 17일) · 변형 14종 · 러너 여섯 재실행은 최종 코드의 결과다
- 2026-10-11 12:55: 결과 재산출(저장소) — `git status --short storage/` 0줄 확인 → `execution_comparison.csv` 4개 삭제 → `run_single_backtest.py`(exit 0 · 4초) · `run_portfolio_backtest.py`(exit 0 · 12초, 다섯 실험 모두 「정합성 검증 통과」). `storage/` 변경 26개(수정 22 · 삭제 4) = 「데이터/결과 영향」 표. 저장소 결과와 사본 결과의 차이는 `meta.json` 과 사본에만 남은 `execution_comparison.csv` 4개뿐이다(파일 수 320 / 324)
- 2026-10-11 12:56: 대시보드 확인(화면 없음, 저장소의 새 결과) — 넷(포트폴리오 · 단일 · TQQQ 일별 비교 · 워크포워드)의 `main()` 이 끝까지 돌고 앱이 띄운 오류 0건. 포트폴리오 대시보드가 직접 인덱싱하는 키는 다섯 실험 모두에서 빠진 것 0, HAA 「배분 조정」이 보이는 날 17, TQQQ 일별 비교의 로더는 수정 시각을 바꾸면 다시 읽는다(2회)
- 2026-10-11 12:58: 문서 — `docs/COMMANDS.md`(출력 목록 · 다운로드 옵션), `scripts/CLAUDE.md`(시작일 정책 · 낡은 파일 삭제 · 실험별 탭 · 다운로드 인자), `src/qbt/CLAUDE.md`(시세 파일 이름), `src/qbt/backtest/CLAUDE.md`(`min_start_date` · 에쿼티 표의 열 · 거래 표의 열 · `params_json` · 등록 실험의 시작일 대조 · 대시보드 절), `docs/AUDIT_REPORT.md`(8단계 처리 표시 · 넘긴 항목). `black` 변경 없음(136 files left unchanged)
- 2026-10-11 13:20: `/code-review xhigh` 1회차 — 발견 11건(첫 실행은 사용 한도로 끊겨 13:18 에 다시 돌렸다). 버그 5 [무거움 0 · 가벼움 5] · 그 외 6. 수정 전 사본을 스크래치 `step8/r1_before/` 에 떴다
  - 사용자에게 올린 버그 2(같은 뿌리): ① 설정에 `min_start_date` 가 있는 실험의 시작일 대조가 그 실험을 돌린 뒤에 걸려, 시세를 다시 받으면 앞 실험 넷의 결과는 새 데이터로 덮어써진 뒤 멈춘다 — `main()` 의 3번 주석은 「시세 문제는 앞 실험 결과를 덮어쓰기 전에 드러난다」고 적는다 ④ 그때의 오류 문구가 그리드 용어(「묶음 시작일을 다시 재세요」)라 러너를 돌린 사람이 무엇을 고칠지 모른다. 둘 다 멈추는 쪽이고 지금 산출물 0건(거르는 기준 2)이지만, 7단계에서 같은 모양(앞 실험 결과를 덮어쓴 뒤 멈춤)을 사용자가 고치기로 했다
  - 고치지 않은 버그 3: ② 빈 사유를 「배분 조정」으로 읽는 것 — 슬롯 매매법이 사유 없이 리밸런싱하는 엔진 경로가 없다(지금 0행, 리밸런싱 의도와 매매법 사이 이전은 늘 사유를 적는다). 새 엔진 코드가 있어야 닿는다(기준 1) ⑥ 낡은 파일을 지운 뒤 저장이 중간에 실패하면 폴더가 반쯤 갱신된다 — 디스크 고장이나 저장 코드의 새 결함이 있어야 닿고 러너는 오류로 끝난다(기준 1) ⑦ 직접 인덱싱이 안내 없는 KeyError 로 멈춘다 — 멈추는 쪽이고 계획서 리스크가 받아들였다(기준 2)
  - 반영한 그 외 3: ⑤ 신호 차트 자리의 `per_asset` 두 번 조회(점검 보고서 6-15 `:1330`) → 위에서 직접 인덱싱한 값을 쓴다 ⑧ 이번 변경으로 사실과 달라진 시작일 설명 — 같은 모양을 찾아 5곳(`run_with_start_check` · `compute_portfolio_effective_start_date` · `run_portfolio_backtest` 의 docstring, `src/qbt/backtest/CLAUDE.md` 두 줄, `scripts/CLAUDE.md` 한 줄) ⑩ 매매법 이름표가 두 함수에 따로 있던 것 → `_method_display_names` 하나. docstring 만 바꾼 두 파일은 docstring 을 뺀 AST 가 수정 전 사본과 같다. 대시보드는 화면 없이 다시 끝까지 돌고(오류 0) 사유 17일 · 마커 수가 같다
  - 반영하지 않은 그 외 3: ③ 미룬 지적 두 항목에 고치지 않은 부분이 남는다(②와 같은 미래 엔진 경로 · 엔진이 `min_start_date` 를 읽지 않는 것) — 둘 다 새 코드가 있어야 닿고(기준 1), 엔진 쪽은 점검 보고서 20절이 보류로 정했으며 `PortfolioConfig` 설명이 「엔진은 읽지 않는다」를 계약으로 적는다. Done 때 항목을 지운다 ⑨ 연구 문서 두 곳의 옛 서술 — 지연진입 문서 L296-303 은 점검 보고서 R4 가, 설계서는 16-B 가 지운다(기준 3) ⑪ 새 테스트에 포함되는 옛 빈 표 테스트 — 지금도 참이다(기준 3)
- 2026-10-11 13:31: 사용자 결정 「실행 전에 멈춤」(1회차 ① ④) → 러너가 실행 전에 계산해 둔 데이터 기준 시작일이 설정의 `min_start_date` 보다 늦은 실험을 모아, 어느 결과도 쓰기 전에 ValueError 로 멈춘다. 문구에 할 일(묶음 시작일 상수 재측정 → 두 그리드 재실행 → 러너)을 적었다. 실행 뒤 대조(`run_with_start_check`)는 안전장치로 둔다. 같은 모양 찾기(실행 뒤에야 걸리는 데이터 확인이 앞 실험 결과를 덮어쓴 뒤 멈춤): diff 안 1곳(이것). diff 밖의 배분 규칙 자산 구성 불일치는 7단계 수정분 검증이 이미 판정했다(거르는 기준 2)
  - 확인(사본, 결과 폴더를 비우고 러너 전체 실행): TIP 2006-10-02 행을 뺀 시세 — 수정 전 exit 1 · 앞 실험 넷의 결과 파일 27개가 쓰인 뒤 멈춤, 수정 후 exit 1 · 결과 파일 0개. 정상 시세 — exit 0, 다섯 실험 모두 정합성 통과, 포트폴리오 결과가 저장소와 같다. 러너는 테스트가 불러올 수 없는 스크립트라 이 사본 실행이 변형 확인이다(수정 전 = 확인을 지운 변형). 전체 테스트 908 passed
- 2026-10-11 13:36: `/code-review xhigh` 2회차(상한) — 발견 9건. 버그 5 [무거움 3 · 가벼움 2] · 그 외 4. 수정 전 사본을 스크래치 `step8/r2_before/` 에 떴다. 리뷰가 화면 없이 hover 함수를 돌려 KeyError 0 · 리밸런싱 마커 59 · 73 · 105 · HAA 「배분 조정」 17일 · 현금 + 자산 비중 합 0.999708 – 1.00028 을 따로 확인했다
  - 고친 무거움 1(검사 공백): ⑥ `params_json` 테스트가 매매법 하나짜리 줄임 표기만 봐서, 매매법이 여럿인 설정(`methods` 안의 슬롯 · 배분 자산 · 신호용 시세)의 경로가 문자열로 바뀌지 않는 회귀를 못 잡는다 — 그러면 러너가 `summary.json` 을 쓰다 멈춘다(죽는다) → `TestTwoMethodNetting::test_params_json_holds_nested_method_fields_as_plain_json`(JSON 왕복 뒤 견준다 — `asdict` 는 튜플을 튜플로 두므로 메모리 값은 `()` 이고 저장 모양은 `[]`). 변형: 매매법 안 경로만 변환하지 않음 → 새 테스트 1 failed(기존 `TestParamsJson` 은 통과 — 공백이 실제였다) / 변환 함수를 통째로 뺌 → 둘 다 실패. 복원 뒤 108 passed, 엔진 파일은 수정 전 사본과 같다. 같은 모양 찾기(새 테스트가 매매법 하나짜리만 봄): 빈 거래 표의 열 · 기여 손익 테스트는 매매법 수에 따라 갈리는 코드 경로가 없어 0곳
  - 사용자에게 올린 것 2: ① 실행 전 시작일 확인이 「데이터는 더 일찍 시작하지만 `min_start_date` 행 하나가 빠진」 경우를 놓쳐, 그때는 실행 뒤 대조가 앞 실험 결과를 덮어쓴 뒤 멈춘다 — 1회차에 고친 자리에서 또 나온 지적이라(지적을 고칠 때 1) 고치지 않고 올린다. 닿으려면 시세가 2007-06-22 보다 앞으로 늘어나는 것과 그날 행 하나만 빠지는 것이 겹쳐야 한다 ⑦(무거움 · 검사 공백) 낡은 파일 삭제 · 실행 전 시작일 확인 · 리밸런싱 사유 문구가 테스트가 불러올 수 없는 스크립트에만 있어 회귀 테스트가 없다 — 그중 낡은 파일 삭제는 미룬 지적 「낡은 장부」(무거움)를 막는 장치다. 테스트로 지키려면 그 로직을 src 로 옮겨야 한다(구조 변경)
  - 고치지 않은 버그 2: ② `_json_safe_dict` 가 dataclass 칸에 직접 담긴 경로 · 날짜만 바꿔, 튜플 · 리스트 안의 경로 칸이 생기면 저장 중 TypeError — 지금 설정에 그런 칸이 0개이고 새 설정 칸 코드가 있어야 닿는다(기준 1) ③ 옛 1바이트 `trades.csv` 가 남은 체크아웃에서 단일 대시보드가 멈춘다 — 멈추는 쪽이고 계획서 리스크가 받아들였다, 지금 결과 0개(기준 2)
  - 반영한 그 외 2: ④ 실행 전 시작일 확인과 그 이유(사용자 결정)를 `scripts/CLAUDE.md` 에 ⑤ `DEFAULT_PORTFOLIO_START_DATE` 주석에 「`min_start_date` 가 있는 실험은 이 하한 대신 그 날짜」
  - 반영하지 않은 그 외 2: ⑧ 신호 차트 자리의 `next(…, None)` · `portfolio_config` 의 `.get` — 점검 보고서 12-9 · 6-15(11단계)가 다룬다(기준 3) ⑨ `prepare_trades_for_csv` 의 앞쪽 복사 — 원래 있던 복사이고 성능(기준 3)
- 2026-10-11 13:51: 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=909, failed=0, skipped=0. `storage/` 변경 26개 그대로. 수정분 검증(서브에이전트)을 띄웠다
- 2026-10-11 13:57: 수정분 검증 결과 — 2회차 수정 3 hunk 모두 ① ② ③ 에 답, **무거운 발견 0**. 엔진 파일은 수정 전 사본과 같다(sha). 변형 9종(사본, 원본 복원 sha 확인): 매매법 안 경로 미변환 · 신호용 시세만 · 배분 자산만 · 슬롯 매매법 안만 · `methods` 를 빈 값으로 → 새 테스트만 실패(기존 `TestParamsJson` 통과 — 공백이 실제였다), 변환 함수 제거 · 최상위 칸만 변환 → 둘 다 실패, 날짜 미변환 → 기존 테스트만 실패(서로 보완), 신호 경로 ↔ 매매 경로 뒤바꿈 → 둘 다 통과
  - 발견 1(가벼움 · diff 안): `scripts/CLAUDE.md` 의 「앞 실험의 결과를 새 시세로 덮어쓴 뒤 멈추지 않게」가 실행 전 확인이 놓치는 경우(2회차 ①)까지 보장하는 것처럼 읽힌다 — 사본 합성 시세로 실측(데이터는 더 일찍 시작하고 `min_start_date` 행만 빠짐 → 실행 전 확인 통과, 실행 뒤 대조에서 멈춤). 2회차 ① 의 사용자 결정에 따라 문구를 정한다
  - 발견 2(가벼움 · diff 밖): 그 경우 `run_with_start_check` 문구가 「데이터가 늦게 시작해」라고 진단한다 — 실제는 행 하나가 빠진 것. 멈추는 쪽(기준 2)
  - 발견 3(가벼움 · 테스트 공백): 두 `params_json` 테스트 모두 신호 경로 = 매매 경로라 두 칸을 뒤바꿔 적는 변형을 못 잡는다 — `asdict` 경로로는 생길 수 없고 칸을 손으로 옮겨 적는 방식으로 돌아가야 생긴다, `portfolio_config` 는 표시용이다(기준 1)
  - 발견 4(가벼움): 튜플 안의 경로 칸 — 2회차 ② 와 같다(기준 1)
  - 발견 5(가벼움 · 문서): `docs/DEFERRED_FINDINGS.md` 「시작일 미대조」 본문이 옛 동작을 적는다 — 「고치는 중」 항목이라 Done 때 지운다
- 2026-10-11 14:02: 사용자 결정 — 2회차 ① 「그대로 두고 문구만」(`scripts/CLAUDE.md` 의 실행 전 확인 설명을 「데이터가 늦게 시작하는 경우를 덮어쓰기 전에 잡는다」로 좁히고, 행 하나만 빠진 경우는 실행 뒤 대조에서 멈춘다는 것과 받아들인 이유를 적었다 — 수정분 검증 발견 1 도 이것으로 풀린다), 2회차 ⑦ 「11단계 3-3 과 함께」(점검 보고서 3-3 행에 덧붙였다), 「3회차 없이 마무리」. 고친 미룬 지적 4건을 `docs/DEFERRED_FINDINGS.md` 에서 지웠다(머리말만 남음). `black` 변경 없음. 품질 검증 `validate_project.py` 최종 — Ruff · PyRight 통과, Pytest passed=909, failed=0, skipped=0. `storage/` 변경 26개 그대로
- 2026-10-11 14:02: 미룬 지적 — 새로 옮긴 것 없음. 1회차 ② ⑥(기준 1) · ⑦(기준 2), 2회차 ②(기준 1) · ③(기준 2), 수정분 검증 발견 2(기준 2) · 3 · 4(기준 1) · 5(Done 때 지우는 항목)는 거름. 2회차 ①은 사용자가 받아들였고 ⑦은 점검 보고서 3-3 행에 덧붙였다(같은 일을 다룰 단계가 있어 두 벌을 만들지 않는다)
- 2026-10-11 14:02: 근거 승격 — 낡은 파일을 지우는 이유 · 폴더째 지우지 않는 이유 · `min_start_date` 의 뜻과 두 번 대조하는 이유(사용자 결정)는 `scripts/CLAUDE.md` 와 러너 주석, `min_start_date` 계약은 `PortfolioConfig` 설명과 `src/qbt/backtest/CLAUDE.md`, 리밸런싱 마커가 장부 사유를 쓰는 이유 · 거래 표의 열 · `params_json` 의 모양 · 기여 손익만 남긴 파생 열은 `src/qbt/backtest/CLAUDE.md`, 체결일별 전후 표를 두지 않는 이유는 `src/qbt/backtest/CLAUDE.md` 대시보드 절, 다운로더가 늘 전체 기간을 받는 이유는 `src/qbt/CLAUDE.md`, 사유 상수를 `constants.py` 에 둔 이유와 처리 사실 · 넘긴 일(9-9 의 워크포워드 대시보드 → 12-9, 낡은 파일 삭제의 테스트 → 3-3)은 점검 보고서
- 2026-10-11 14:03: `/commit` — 대상은 unstaged + untracked(이 계획서) 전체(코드 · 문서 28파일 + `storage/` 26개, staged 없음). 모두 이 계획서 한 묶음이라 분리 제안 없음. 후보 5개를 옮기고 Done

---
