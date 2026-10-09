# 전체 점검 보고서 (2026-10-09 로컬 재검증판)

> **임시 문서다.** 아래 항목을 모두 처리(고침 · 버림 · 결정)하면 지운다 — 삭제는 19절의 마지막 단계다. 남길 가치가 있는 결론은 그 전에 각 정본(코드 · `docs/research/` · 안내 문서)으로 옮긴다.
>
> - **기준**: 커밋 `40011ad`(코드는 `c4a4d24` 와 같다). 모든 줄 번호는 이 커밋 기준이다.
> - **방법**: 2026-10-07 클라우드 점검(이 파일의 이전 판)의 항목을 8개 영역 — 포트폴리오 엔진 · 단일 백테스트/워크포워드 · tqqq/utils/데이터 · 대시보드 · DEFERRED · 안내 문서/계획서 · 연구 문서 · 테스트 — 에서 지금 코드 · 결과 파일로 하나씩 다시 판정하고, 독립 탐색으로 새 지적을 더했다. 재현은 저장소 밖 스크래치와 사본에서만 했다. 「메인 세션 확인」은 결과 파일로 한 번 더 잰 것이다.
> - **판정 칸**: 확인 = 주장대로 · 정정 = 사실 일부를 고쳤다 · 신규 = 이번에 찾았다. 기각 · 보류한 이전 판 항목은 표에서 빼고 20절에 이유와 함께 모았다. 이전 판 번호는 그대로 두고 새 항목은 뒤에 이어 붙였다.
> - **심각도**: 높음 = 지금 틀린 값 · 결론이 나간다 / 중간 = 잠재 오류(지금 0건)이거나 단일 출처를 크게 어긴다 / 낮음 = 정리.
> - **무게 · 닿는가**(버그): `/impl-plan` `review.md` 정의를 따른다. 무거움 = 죽는다 · 되돌릴 수 없다 · 검증을 비켜 간다 · 틀린 값이 에러 없이 나간다. 닿는다 = 지금 산출물에 나오거나, 시간 경과 · 데이터 재수집 · 설정값 변경 · 실행 환경만으로 생긴다.
> - **의도된 결정이라 뺀 것**: 입력 시세 반올림 6자리(루트 `CLAUDE.md`), `DEFAULT_TICKERS` 미변경(설계서 D43 ⑤), `periods.csv` 소비처 없음(D60), 금리 · 보수의 이전 달 대체 정책(`MAX_*_MONTHS_DIFF`), `state_log.csv` 저장 유지(부록 L.5 의 근거물), 탈락 후보(금 · EWY)의 그리드 코드 유지(D74), 정합성 위반 시 저장 후 중단.

**용어**

- **4P**: 확정 파라미터 넷(이동평균 200일 · 매수 버퍼 3% · 매도 버퍼 5% · 유지일 3, `FIXED_4P_*`).
- **버퍼존**: 이동평균 위아래에 비율 띠를 두고, 띠를 넘어야 신호를 내는 매매 규칙.
- **고원**: 성과(Calmar)가 최고값의 80% 이상으로 유지되는 파라미터 범위.
- **워크포워드(WFO)**: 과거 구간(IS)에서 그리드로 파라미터를 골라 이어지는 구간(OOS)에 적용해 보는 검증. Dynamic = 구간마다 다시 고른다, Fixed = 첫 구간 값을 끝까지 쓴다.
- **Calmar**: 연복리 수익률(CAGR) ÷ |최대 낙폭(MDD)|.
- **매매법**: 한 실험 안의 독립 장부 단위. **상계**: 같은 날 한 매매법이 팔고 다른 매매법이 산 같은 종목을 차이만 체결하는 것.
- **정합성 검사기**: 포트폴리오 실행 직후 결과가 규칙을 지켰는지 대조하는 `portfolio_validation.py`.
- **판**: 같은 실험을 어떤 시세로 돌렸는가(이어 붙인 판 = 상장 전만 대용 · 완전 실물판 · 대체 판).

---

## A. 먼저 볼 것 — 지금 틀린 값 · 결론이 나가는 곳

| # | 무엇이 틀리나 | 실측 | 항목 |
|---|---|---|---|
| 1 | 모든 결과의 첫 해 연간 수익률과 월별 표 첫 달 | QQQ B&H 실험 2005: 저장 8.39% / 실제 1.90% | 1-1 |
| 2 | 대시보드 「연간 수익률 vs QQQ」 첫 해가 기간이 다른 두 수익률을 비교 | 채택 조합 2007: 화면 −13.30%p / 같은 기간 −2.70%p | 1-2 · 결정 3 |
| 3 | 대시보드 분기 기여도에서 첫 분기 막대가 빠짐 | QQQ B&H 2005Q1 −809,019원 누락 | 2-17 |
| 4 | 연구 보고서의 워크포워드 결론이 지금 결과와 반대(12곳)이고, 운영 점검표는 「경고」인데 「정상」 | 문서 Fixed ≥ Dynamic / 지금 QQQ Dynamic 9.46 · Fixed 5.16 | 13-A R1 · R6 |
| 5 | 「WFO 가 4P 를 다시 찾는다」는 결론이 조합별 평가 기간 차이에 기댄다 | 평가 기간을 맞추면 QQQ 11개 윈도우 중 9개의 선택이 바뀌고 4P 는 한 번도 안 뽑힌다 | 1-11 · 결정 1 |
| 6 | ~~TQQQ 합성 시세가 반년 낡음~~ **처리함(2026-10-09)** — 재생성 · 단일 백테스트 재산출. 남은 것: 실행 안내(13-B D4) · TQQQ 워크포워드 재실행(결정 1 뒤) | 합성 끝 2026-03-12 → 09-24, B&H TQQQ CAGR 0.74 → 2.66 | 2-1 · 13-B D4 |
| 7 | 워크포워드 · 고원 결과가 한 달 낡은 데이터(08-21) 기준 | 다시 돌리면 대시보드 고원 4탭 중 2탭 · QQQ WFO Stitched CAGR 9.46 → 9.61 | 2-19 |
| 8 | 고원 구간이 연속 범위가 아님 | QQQ 유지일: 칠함 0 – 10 / 연속 2 – 10 | 1-3 |
| 9 | 지연진입 실행 규칙의 진입가 · 폐기선이 옛 값 | 문서 646.816 · 680.86 / 지금 646.1427 · 680.15 | 13-A R3 |
| 10 | 포트폴리오 Buy 마커 가격이 체결가가 아니라 평균 단가 | 253개 중 48개가 0.1% 넘게 다름 | 1-4 |
| 11 | 스프레드 랩 「과최적화 아님」 판정이 같은 파라미터를 기간만 달리 잰 비교 | 격차 0.3077 = 1.3511 − 1.0434(기간 차이) | 1-5 |
| 12 | 「체결 전후 비교」 표가 매수일을 빠뜨리고 사유를 틀리게 붙임 | D-1 · Q-2 · Q-2-2XS 매수 진입일 표시 0일 | 17절 DEFERRED 6 · 11 |

## B. 결정이 필요한 것

| # | 정할 것 | 선택지 | 추천(근거) |
|---|---|---|---|
| 1 | 워크포워드 · 고원 그리드의 평가 기간(1-11 · 13-A R1 · R6 · R8) | (가) 가장 긴 이동평균의 유효 구간으로 한 번만 잘라 모든 조합을 같은 기간으로 평가 — 코드는 순삭제, WFO · 고원 재실행 (나) 코드 유지 + 연구 문서에 [한계] 한 단락 | **(가)** — 같은 기간 비교가 표준이고 코드가 준다. 두 안 모두 「4P 재발견 → 동결 원칙 직접 지지」는 철회한다. 운영 점검표(§22.3)의 비교 대상은 재실행 결과를 본 뒤 정하고, 그 전에는 「현재 상태: 정상」 문구만 지운다 |
| 2 | 「체결 전후 비교」 표(DEFERRED 6 · 11) | (가) 표 섹션 · `execution_comparison.csv` 삭제(러너 약 128줄 · 앱 77줄 · CSV 4개) (나) 고친다(10 – 15줄 + 새 테스트) | **(가)** — 잃는 것은 체결일별 전일 / 당일 주수 · 비중을 숫자로 보는 화면인데, 같은 값이 `equity.csv` · `state_log.csv` 에 있다. 11 의 마커 hover 는 어느 쪽이든 장부 사유로 고친다(설계서 D40 이 받아들인 모양을 다시 연다) |
| 3 | 대시보드 「연간 수익률 vs QQQ」(1-2) | (가) 실험마다 자기 시작일로 벤치마크를 계산해 `summary.json` 에(공유 JSON · 앱 약 15줄 삭제) (나) 섹션 통째 삭제(앱 약 125줄 + 러너 + src 함수) | **(나)** — QQQ B&H 가 이미 실험으로 등록돼 같은 화면에서 비교된다. 연도별 초과수익 막대를 실제로 보고 있으면 (가) |
| 4 | 대시보드 차트 공용 코드의 자리(7-1) | (가) src 의 Streamlit 비의존 모듈(`walkforward_verdict.py` 선례) (나) `scripts/backtest/` 형제 모듈 | **(가)** — 「scripts 끼리 import 금지」 규칙은 어디에도 없지만, src 쪽이 타입 검사 · 테스트 경로가 이미 있다 |
| 5 | 스프레드 랩(1-5 · 7-2 · 8-5) | (가) 판정 블록 · 「과최적화 아님」 문구만 삭제 + 7-2 정리(약 300줄 감소) (나) 결론을 연구 문서로 옮기고 앱 · 헬퍼 · 차트 · CSV 8개 · 테스트 삭제(tqqq 영역 약 절반, 추정) | **(가)** — (나)는 「확정 후 앱만 유지」 결정을 뒤집는 것이다. 다시 볼 일이 없으면 (나) |
| 6 | `meta.json` 실행 이력(5-10 · 2-21 · 13-B D13) | (가) 기능 통째 삭제(`meta_manager` 134줄 · 테스트 391줄 · 스크립트 메타 조립 약 176줄 · 문서 44줄) (나) 출력 파일별 최신 1건만 | **(가)** — 읽는 코드 0, 이력 5칸이 한 번 실행으로 덮여 출처 기록으로도 못 쓴다. 파라미터는 `summary.json` 에, 생성 시점은 git 에 있다 |
| 7 | 고원 「저거래 제외」 필터(6-16 · 12-1) | (가) except 2줄만 삭제 (나) 필터 기능 통째 삭제 | **(가)로 정정(2026-10-09)** — 추천 (나)는 틀렸다. `전략_검증_보고서.md` G.7.2 · H.6 이 이 필터의 기준(거래 5회)을 유지하기로 확정(2026-08-30)했고, 데이터가 늘어 QQQ sell=0.15 의 거래가 4회가 되면 필터가 실제로 작동한다 |
| 8 | 포트폴리오 `trades.csv` 의 기록 전용 열(6-13) | (가) 유지하고 `order_amount` 만 반올림(2-5) (나) `hold_days_used` · `pre_shares` · `post_shares` · `order_amount` · `buy_buffer_pct` 삭제 | **(가)** — 사람이 CSV 로 보는 기록이고, 지우면 공유 타입 · 테스트 38곳이 따라 바뀐다 |
| 9 | 실행 위치 기준 경로(2-24) | (가) 그대로 (나) CLI 공통 핸들러에 「저장소 루트에서 실행하세요」 확인 약 3줄 (다) `__file__` 기준 | **(나)** — 전역 「경로 기준은 파일 위치」 규칙을 어기는 상태를 «멈추는» 쪽으로 바꾸는 가장 싼 길. (다)는 git 추적 결과에 로컬 절대경로가 실린다 |
| 10 | 반올림 상수를 `common_constants.py` 로(3-6 · 13-B D11) | (가) 옮기고 tqqq 저장도 상수 사용(가격 4 · % 열 4 — 출력 바이트 동일) (나) 그대로 | **(가)** — 루트 `CLAUDE.md` 「모든 저장 경로가 경유」가 참이 된다. % 열을 2자리로 낮추면 스프레드 랩 재계산이 깨지므로 4자리를 유지한다 |
| 11 | 시세 파일의 중복 날짜(12-5) | (가) ValueError (나) 경고 + 안정 정렬로 「첫 값 유지」를 참으로 | **(가)** — 전역 「이상 발견 시 즉시 예외」, 지금 43개 파일 0건 |
| 12 | 계획서 10개 삭제 시점(16-A) | (가) 문서 오류 4건(13-B D4 · D5 · D6 · D14)을 고친 뒤 바로 (나) 설계서 D54 순서대로 부록 M 뒤 | **(가)** — 계획서에만 있는 정보는 부록 M 의 재료가 아니다 |
| 13 | 금리 · 운용비율 파일의 출처와 갱신 방법(2-23 · 13-B D4) | **답함(2026-10-09)** | 금리 = FRED `FEDFUNDS` 월평균 ÷ 100(기존 331개월 전부 일치 확인). 운용비율 = ProShares TQQQ Summary Prospectus 의 Net 비율을 설명서 날짜 다음 달부터 적용(2010-02 0.95 · 2022-10 0.86 · 2023-10 0.88 · 2024-10 0.84 · 2025-10 0.82 — 파일과 일치). COMMANDS 순서 블록에 3줄로 적는 일이 남았다. 2024-09 한 달은 결정 19 |
| 14 | 테스트에 손으로 박은 값(3-21) | (가) 프로덕션 상수 참조 (나) 정책 값 고정으로 둔다 | 비용률 · 4P 처럼 정책인 값은 **(나)**, 단순 픽스처 값은 **(가)** |
| 15 | pytest 에 `error::RuntimeWarning`(6-9 ①) | (가) 넣는다 (나) 안 넣는다 | **(가)** — 지금 857 통과, 효과 없는 경고 픽스처를 지우는 대신 실제로 작동하는 장치 |
| 16 | `download_data.py --start/--end`(6-8) | (가) 삭제 (나) 유지 | 결과를 읽는 코드는 0이다. 손으로 쓰지 않으면 **(가)** |
| 17 | 「VERBATIM 패턴」(13-B D16) | 뜻 확인 | 뜻을 알려 주면 `scripts/CLAUDE.md` 에 한 줄, 아니면 주석 16곳과 그 줄 삭제 |
| 18 | DEFERRED 13건 고르기(17절) | 항목마다 고친다 / 버린다 | 17절 추천(고친다 8 · 버린다 5) |
| 19 | 운용비율 파일의 2024-09 값 `0.0087`(2-23) | **(가) 처리함(2026-10-09)** | `0.0088` 로 고치고 일별 비교를 다시 만들었다 — 바뀐 것은 2024-09-03 이후 시뮬 열뿐(종가 최대 0.0007). 합성 시세는 2010년 이전에만 시뮬을 써서 영향이 없다. 대체 판 `SSO_proxy` · `QLD_proxy` 는 결정 20 대로 다음 시세 갱신 때 함께 다시 만든다 |
| 20 | 대체 판 시계열 3개(`BIL_proxy` · `SSO_proxy` · `QLD_proxy`, 2026-09-24 까지) 재생성 | (가) 다음 시세 갱신 때 그리드 재실행과 함께 (나) 지금 재생성 + 두 그리드 재실행(약 3 – 4분) | **(가)** — 2026-07 금리로 9월을 채워 만든 파일이라 다시 만들면 9월(약 17거래일)만 3.63% → 3.75% 로 미세하게 바뀐다(8월은 실제 값과 같다). 지금 바꾸면 그리드 · 등록 실험 결과와 어긋나고 원인 분리가 흐려진다 |

---

## 1. 비즈니스 로직 오류

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 1-1 | 높음 | 확인 | `src/qbt/backtest/analysis.py:221-261` `calculate_monthly_returns` (+ `calculate_benchmark_yearly_returns` :379) | 월말 리샘플 뒤 `pct_change().dropna()` 로 시작일 ~ 첫 월말 수익이 빠진다. 단일 13개 결과 모두 첫 달이 없다(B&H QQQ 월 330개 / 올바르면 331개). 첫 해 저장 / 실제: B&H QQQ 1999 74.16 / 77.11, QQQ B&H 실험 2005 8.39 / 1.90, 벤치마크 QQQ 2005 8.39 / 2.65. 시작 월이 12월이면 첫 해가 통째로 없다(B&H UGL 2008 +28.54%). 범위는 JSON 19개(단일 13 · 포트폴리오 5 · 벤치마크 1)이고 읽는 곳은 대시보드 2개다. CAGR · MDD · Calmar 는 에쿼티로 계산해 안 바뀐다. → 월 · 연 모두 「에쿼티 리샘플 + 첫 행 자본을 기준점」으로 계산하는 헬퍼 하나를 두고 `calculate_yearly_returns` 가 에쿼티를 받게 한다. 월→연 복리 루프(:282-301)가 사라지고 1-6 도 함께 풀린다. 호출부 3곳, 앱은 0줄 |
| 1-2 | 높음 | 확인 (수치 정정) | `scripts/backtest/run_portfolio_backtest.py:202` `_save_benchmark_qqq_json` · `:636-647` · `scripts/backtest/app_portfolio_backtest.py:584` · `:689` | QQQ 연간 수익률을 가장 이른 시작일(2005-01-01)로 한 번 계산해 모든 실험이 함께 쓴다. 늦게 시작한 실험의 첫 해는 「몇 달 대 1년」 비교가 되고 캡션도 2005-01-01 을 보인다. 화면 / 같은 기간(1-1 까지 고친 값): 채택 조합 2007 −13.30%p / −2.70%p(5.78 − 8.48), Q-2-2XS 2007 −14.04%p / −10.38%p(5.12 − 15.50). 기존 보고서의 −2.06 은 양쪽 다 첫 월말부터 잰 값이다. docstring :208 「문제 없다」도 틀렸다. → 실험마다 자기 시작일로 계산해 각 `summary.json` 에 넣는다. 러너 함수 32줄 · 시작일 계산 · 앱 약 15줄 · `scripts/CLAUDE.md` 정책 단락이 사라진다. 대안은 결정 3 |
| 1-3 | 중간 | 확인 | `src/qbt/backtest/parameter_stability.py:82-113` `find_plateau_range` | docstring 은 「연속 범위」인데 코드는 기준 이상인 첫 값 ~ 마지막 값을 돌려준다. 자산 × 파라미터 24칸 중 8칸이 연속 범위와 다르다. 대시보드가 칠하는 QQQ 는 4탭 중 유지일 1탭: 지금 (0, 10) / 연속이면 (2, 10)(유지일 1 은 0.24 < 기준 0.256). 확정값 3 은 어느 쪽이든 고원 안이다. → 최대값 위치에서 좌우로 기준 이상인 동안만 넓힌다(약 6줄). 기준 이상 구간이 둘로 갈리면 최대값이 든 쪽을 고른다는 한 문장을 docstring 에 둔다 |
| 1-4 | 중간 | 정정 | `run_portfolio_backtest.py:457` (`entry_price = final_avg_price`) · `app_portfolio_backtest.py:1510` · `:1535` · `:1542` `_build_portfolio_markers` | 기존 보고서가 든 「보유중 $201.9」 마커는 화면에 안 나온다. 같은 진입일의 거래 행이 있으면 보유중 마커를 생략해(:1535) 미청산 16개 중 13개가 빠진다. 실제로 틀린 것은 거래 행으로 만든 Buy 마커다. `entry_price` 가 매도 시점 평균 단가라 253개 중 48개가 체결가와 0.1% 넘게 다르다(Q-2 QQQ 2005-02-17 「$32.6」, 체결가 32.45). 부작용으로 13개 자산은 「보유중」 표시가 아예 없다. → 두 문구 모두 가격을 빼거나 「평단 $X」로 바꾸고, 마커를 생략하지 말고 기존 Buy 마커에 「(보유중)」을 덧붙인다. docstring :1479 「동일 규약」 삭제. 1-12 와 함께 |
| 1-5 | 중간 | 확인 | `scripts/tqqq/spread_lab/app_rate_spread_lab.py:958-976` · `:829-858` · `:759-772` · `:1364-1391` · `:1074-1075` | 「완전 고정 WFO 이어 붙인 RMSE − 정적 RMSE」를 과최적화 격차로 읽는다. 같은 (a, b) = (−6.1, 0.37)를 다시 재면 2010-02-11 ~ 2026-02-17(4,028일) 1.0434, 2015-02-02 ~ 2026-02-17(2,777일) 1.3511 이다. 격차 0.3077 은 기간 차이일 뿐이다. (a, b) 자체도 전 기간 튜닝값(meta `ab_source=global_tuning`)이라 3자 순서 비교(:849-858)도 근거가 못 된다. → 판정 블록과 「과최적화 아님」 문구를 모두 지우고 수치 표시만 남긴다(`tqqq/constants.py:69` · `tqqq/CLAUDE.md:136` 포함). 더 큰 대안은 결정 5 |
| 1-6 | 낮음 | 확인 | `analysis.py:257` → `:264-303` `calculate_yearly_returns` | 반올림한 월 수익률로 연간 복리를 계산한다. 저장 연간값 414개 중 225개가 원값 복리와 0.01 이상 다르고 최대 0.06 이다(B&H TQQQ 2003: 원값 168.6672 / 저장 168.61). → 1-1 수정으로 함께 해소 |
| 1-7 | 낮음 | 확인 | `scripts/backtest/app_walkforward.py:687-714` `_build_wfo_candle_data` · `run_walkforward.py:228` | WFO 대시보드만 4자리로 반올림된 종가로 % 를 다시 계산한다(w04 4,018행 중 42행이 표시상 0.01 다르고, 4종 % 중 1종만 나온다). → WFO 러너도 `add_ohlc_change_pct` 로 저장하면 앱의 재계산 코드가 지워지고 4-1 도 풀린다 |
| 1-8 | 낮음 | 확인 | `src/qbt/backtest/walkforward.py:201-227` `select_best_calmar_params` · `backtest_engine.py:514` | 최적 선택이 불안정 정렬이고 동률 규칙이 없다(22개 윈도우 동률 0건). → 재계산 · 재정렬 · 탈락 로그를 지우고 거래수 필터 뒤 `idxmax()` 한 줄(첫 최대 = 그리드 입력 순서). 탈락 로그의 조건 누락(:216-218)과 3-14 의 리터럴도 함께 사라진다 |
| 1-9 | 낮음 | 확인 | `backtest_engine.py:327-332` · `walkforward.py:430-470` `build_params_schedule` | OOS 시작마다 새 전략 객체로 바꿔 유지일 대기 상태가 버려진다. 전환 40회 중 36회가 같은 파라미터이고 지금 결과 차이는 0행이다. 닿는다(OOS 시작일 직전 돌파 뒤 대기 중이면 진입 신호가 에러 없이 사라진다). → 파라미터가 같으면 schedule 에 넣지 않는다(3줄) |
| 1-10 | 낮음 | 확인 | `src/qbt/backtest/walkforward_verdict.py:131-140` `_describe_wfe` · `:249-254` | 두 모드 중 큰 값으로 「IS 성과의 약 N% 재현」을 쓴다(지금은 그 분기에 닿는 전략 0). → 「두 값 표시」는 이미 돼 있다(:129). 꼬리 문장을 낮은 값 기준으로 바꾸거나 지운다 |
| 1-11 | 높음 | 신규 · 결정 1 | `backtest_engine.py:201-203` `_run_backtest_for_grid` ← `walkforward.py:318` / 같은 모양 `scripts/backtest/run_param_plateau_all.py:250-268` | 그리드가 조합마다 다른 기간을 평가한다. 이동평균 기간별로 유효 행을 따로 잘라 QQQ 는 100일선 1999-07-30, 150일선 1999-10-11, 200일선 1999-12-21 에 시작한다. 평가 시작일을 하나로 맞추면 QQQ 11개 윈도우 중 9개에서 선택이 (150, 0.05, 0.03, 3)으로 바뀌고 확정값 (200, 0.03, 0.05, 3)은 한 번도 안 뽑힌다(메인 세션 재현, 지금 방식의 선택은 저장 결과와 11/11 일치). TQQQ 는 11개 중 5개가 바뀐다. 고원 ma_window 실험도 QQQ ma=200 이 0.32 / 0.39 로 달라진다. 「IS 가 길어지면 WFO 가 확정값을 다시 찾는다」(`전략_검증_보고서.md` G.7.3)가 이 차이에 기댄다 |
| 1-12 | 낮음 | 신규 | `app_portfolio_backtest.py:1495-1527` | 리밸런싱 부분 매도도 신호 청산과 같은 「Sell +x%」 마커로 그리고 리밸런싱 매수는 안 그린다. B&H 자산에 Sell 화살표가 줄지어 나온다(리밸런싱 거래: Q-2 126 중 107, Q-2-2XS 147 중 129, 조합 460 중 227). → `trade_type` 으로 구분한다. 1-4 와 함께 |
| 1-13 | 낮음 | 신규 | `app_single_backtest.py:325` · `app_portfolio_backtest.py:1510` · `:1542` · `app_walkforward.py:781` | 캔들은 신호 시세인데 마커의 $ 는 매매 시세다(TQQQ 탭: QQQ 시가 70.23 캔들에 「Buy $77.1」). → 마커에서 가격을 빼거나 차트 제목에 「신호: QQQ」를 쓴다 |
| 1-14 | 낮음 | 신규 | `app_portfolio_backtest.py:1077-1099` | 시작일이 다른 실험을 같은 1,000만 원 출발점에서 절대값으로 겹쳐 그린다(2007-06-22 시점 Q-2 12,469,958 · 조합 10,000,000). → 시작일이 다르다는 캡션 한 줄 |

## 2. 버그

무게 · 닿는가는 `/impl-plan` `review.md` 정의를 따른다(머리말).

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 2-1 | 높음 | 확인 | `storage/stock/TQQQ_synthetic_max.csv` · `docs/COMMANDS.md:116` | 합성 파일이 2026-03-12 에서 끝난다(원본 TQQQ · QQQ 는 2026-09-24). 다시 만들면 135행이 늘고 겹침 구간 종가가 전 구간 균일하게 약 0.587% 달라진다(최대 1.472109). 메모리 재실행: `buffer_zone_tqqq` CAGR 17.3134 → 17.5668 · 거래 13 → 14, `buy_and_hold_tqqq` CAGR 0.7403 → 2.6586. 일부러 고정했다는 근거는 없다. `tqqq_daily_comparison.csv` 도 2026-07-24 에서 끝난다. 무거움 · 닿는다. → 재생성 + 안내 수정. **처리함(2026-10-09)**: 금리를 채운 뒤 `generate_synthetic.py` · `generate_daily_comparison.py` · `run_single_backtest.py` 를 실행했다 — 합성 6,794 → 6,929행(2026-09-24 끝, 실제 구간은 `TQQQ_max.csv` 와 같음), 일별 비교 4,137 → 4,180행, `buffer_zone_tqqq` CAGR 17.31 → 17.57 · Calmar 0.23 → 0.24 · 거래 13 → 14, `buy_and_hold_tqqq` CAGR 0.74 → 2.66. 단일 백테스트 나머지 12개는 바이트 단위로 같다. 남은 것: 안내 수정(13-B D4), TQQQ 워크포워드 재실행(결정 1 뒤 4단계), 7-3 · 4-3 |
| 2-2 | 중간 | 확인 | `src/qbt/tqqq/simulation.py:299-309` `_validate_ffr_coverage` | 시작일이 29 – 31일이면 다음 달로 넘어가며 크래시한다(`2020-01-31` → ValueError). 닿지 않는다(호출부 시작일이 모두 고정된 과거 날짜). → 함수 삭제(약 70줄, 테스트 6곳). 루프의 `lookup_ffr` 이 같은 정책으로 이미 멈춘다 |
| 2-3 | 중간 | 확인 | `src/qbt/utils/parallel_executor.py:205-237` `execute_parallel` | `except: raise` 가 `with ProcessPoolExecutor` 안이라 남은 작업을 끝낸 뒤 전파한다(작업 10개 · 워커 2개에서 5.1초). 가벼움 · 닿는다. → except 안에 `executor.shutdown(wait=False, cancel_futures=True)` 한 줄(0.06초) |
| 2-4 | 중간 | 확인 | `scripts/tqqq/app_daily_comparison.py:44` `load_data(csv_path, _mtime)` | Streamlit 은 `_` 로 시작하는 인자를 캐시 키에서 뺀다(1.63.0 실측: `_mtime` 을 바꿔도 캐시 적중). CSV 를 다시 만들어도 옛 데이터가 보이고 docstring(:32 · :50)은 반대로 적혀 있다. 무거움 · 닿는다(2-1 재생성 직후). → 인자 이름을 `mtime` 으로 바꾸고 `get_file_mtime` 을 인라인 |
| 2-5 | 중간 | 확인 | `src/qbt/backtest/engines/portfolio_data.py:229-263` · `:275-276` · `run_portfolio_backtest.py:291-320` | equity.csv 의 `{자산}_current_price` · `_return_pct` · `total_pnl` · `total_return_pct` 가 반올림 없이 저장된다(채택 조합 32열이 13 – 20자리). 이 4종은 소비 화면이 지워진 잔여물이고 읽는 코드가 0 이다. → 저장에서 빼기보다 생성부를 지운다(약 30줄 + `portfolio_types.py` 명세 + `backtest/CLAUDE.md` 「파생 뷰 컬럼」). `_contribution` 은 앱과 src 가 읽으므로 남긴다. trades.csv 의 `order_amount`(9 – 13자리)는 결정 8 |
| 2-6 | 중간 | 정정 | `backtest_engine.py:500-501` `run_grid_search` | `os.cpu_count()==1` 이면 `max_workers=0` → ValueError. 죽는 곳은 여기 한 곳이다 — 그리드 러너 둘(`run_supplement_grid.py:284` · `run_combo_grid.py:301`)은 이미 `max(1, …)` 로 막혀 있다. 닿지 않는다(추정, CPU 1개 환경). → `parallel_executor` 기본값(지금 2)을 `max(1, cpu−1)` 하나로 두고 호출부 3곳의 계산을 지운다 |
| 2-7 | 낮음 | 확인 | `run_walkforward.py:281-295` `_save_results` | `_pct` 2자리 분기가 먼저 걸려 버퍼존 4자리 분기에 닿지 않는다(0.025 → 0.02, 지금 그리드 0건). 닿는다(그리드 상수 변경). → 열 이름 → 자릿수 사전 하나 |
| 2-8 | 낮음 | 확인 | `app_walkforward.py:632` `_load_window_csv_detail` · `app_single_backtest.py:108-111` | 거래 0건 윈도우의 1바이트 CSV 는 `EmptyDataError` 를 낸다. 닿지 않는다(IS 선택이 `min_trades=3` 을 강제). B&H `trades.csv` 6개는 지금 1바이트라 단일 앱의 except 를 실제로 탄다. → 2-12 를 고칠 때 「빈 표도 헤더를 쓴다」로 함께 하고 단일 앱의 except 3줄을 지운다 |
| 2-9 | 낮음 | 확인 | `app_walkforward.py:591-597` `_render_param_drift` | 4행 그림인데 높이 · x축 제목은 5행 기준이다(1,250px). → `len(param_keys)` |
| 2-10 | 낮음 | 확인 | `run_walkforward.py:301-315` | 이어 붙인 자본곡선의 equity 가 실수로 저장되고(`69596982.0`), 없는 열의 반올림 키 4개가 있다. → 정수 변환 1줄 · 키 삭제 4줄 |
| 2-11 | 낮음 | 확인 | `src/qbt/backtest/engines/portfolio_engine.py:138` · `:152-160` | 신호 캐시 키 때문에 같은 신호를 다른 매매 데이터로 드는 슬롯이 앞 슬롯의 기간으로 잘린 이동평균을 받는다. 슬롯 순서에 따라 시작일이 달라진다(SPY 신호 두 슬롯: `spy,sso` 순 2006-06-21 시작 · 113,144,510 / `sso,spy` 순 2007-04-09 · 92,424,677). 지금 설정 0건. 무거움 · 닿는다(설정). → 캐시 삭제. `backtest/CLAUDE.md:241` 「자동으로 같은 시그널」 문장도 삭제 |
| 2-12 | 낮음 | 확인 | `portfolio_engine.py:782-796` · `:805` | 거래가 0건이면 `trades_df` 열이 10개다(`portfolio_qqq_bh` 10열 / 나머지 15열). → `columns=list(PortfolioTradeRecord.__annotations__)` 1줄 |
| 2-13 | 낮음 | 확인 | `simulation.py:780-783` `calculate_validation_metrics` | 실제 누적수익률이 0 근처면 ValueError 인데 그 필드를 읽는 곳이 없다. 닿지 않는다. → 4-2 · 6-5 와 묶어 필드 4개 · 가드 2개 삭제 |
| 2-14 | 낮음 | 확인 | `src/qbt/utils/formatting.py:210-211` `TableLogger` | 헤더와 행이 1칸 어긋난다(로그 포맷의 `[%(funcName)s]` 길이 차). → 출력 메서드 하나로 모으면 보정용 공백도 지워진다 |
| 2-15 | 낮음 | 정정 | `validate_project.py:106-120` · `:168-196` | 개수 파싱이 틀릴 수 있다는 것은 추정이다(지금 출력에서는 857 · 0 · 0 으로 정확). 통과 판정 · exit code 는 정확하다. → 개수 파싱 삭제(약 70줄, 12-10 포함)는 그대로 적절 |
| 2-16 | 낮음 | 확인 | `scripts/tqqq/generate_daily_comparison.py:159-160` · `docs/research/late_entry_rally_opportunities.py:185` · `:369` | `+{x:.1f}%` 는 음수면 「+-」로 찍힌다. 닿지 않는다(누적 +38,197%). → `{x:+.1f}` |
| 2-17 | 높음 | 신규 | `app_portfolio_backtest.py:734-736` `_render_contribution_section` | 분기 기여도를 `diff().iloc[1:]` 로 구해 첫 분기 막대가 빠진다. 5개 실험 모두 해당한다(QQQ B&H 2005Q1 −809,019원 누락, 막대 합 209,895,969 / 최종 209,086,950 — 메인 세션 확인). 무거움 · 닿는다. → `quarterly.diff().fillna(quarterly)` 한 줄 |
| 2-18 | 중간 | 신규 | `@st.cache_data` 로더: `app_single_backtest.py:102-121` · `app_portfolio_backtest.py:130-228` · `:573-581` · `app_walkforward.py:127-178` · `:631-650` | 캐시 키가 경로 문자열뿐이라, 대시보드를 띄워 둔 채 러너를 다시 돌리면 옛 결과가 계속 보인다(재현). `scripts/data/app_proxy_comparison.py:51-58` 은 파일 수정 시각을 키로 넣어 막는다(저장소 관용). 무거움 · 닿는다. → 로더를 「(경로, mtime)」을 받는 공용 함수 하나로 합친다(줄 수도 준다) |
| 2-19 | 중간 | 신규 | `storage/results/backtest/buffer_zone_*/walkforward_*` · `wfo_windows_*` · `param_plateau/*.csv` | 같은 폴더에 기준일이 다른 산출물이 섞여 있다. 단일 결과 · 시세는 2026-09-24, WFO · 고원은 2026-08-21 데이터다(커밋 2026-08-30). 고원을 다시 돌리면 624칸 중 259칸이 달라지고 대시보드 QQQ 고원이 4탭 중 2탭에서 바뀐다. QQQ WFO Stitched CAGR 은 Dynamic 9.46 → 9.61, Fixed 5.16 → 5.33. → 코드 변경 없이 두 러너 재실행(결정 1 뒤에 한 번). 고원 러너는 메타데이터를 남기지 않아 기준일을 git 로그로만 알 수 있다 |
| 2-20 | 중간 | 신규 | `walkforward.py:140-146` `generate_wfo_windows` → `:373` | 데이터 종료일이 새 OOS 시작 월의 첫 거래일이면 OOS 가 1행이라 스크립트가 멈춘다(`유효 데이터 부족: 1행`). 2 – 10행이면 CAGR · WFE 가 전부 0 인 윈도우가 평균 · 중앙값에 섞인다. 다음에 실제로 닿는 날은 OOS 시작 2027-03-01. 무거움(죽는다) · 닿는다(달력). → 마지막 OOS 가 `MIN_VALID_ROWS` 미만이면 그 윈도우를 만들지 않는다(1줄) |
| 2-21 | 낮음 | 신규 | `run_portfolio_backtest.py:509` | 메타데이터를 실험마다 저장해 한 번 실행이 이력 한도 5개를 다 쓴다(`meta.json` 5건이 모두 2026-10-06 08:27:42 – 08:27:52). → 결정 6 에 따른다 |
| 2-22 | 낮음 | 신규 | `src/qbt/tqqq/visualization.py:233` · `:377` | 추세선 라벨이 「y=0.19x+-0.55」로 찍힌다(지금 화면에 나온다). → `{b:+.2f}` |
| 2-23 | 중간 | 신규 | `storage/etc/federal_funds_rate_monthly.csv`(2026-07 끝) · `tqqq_net_expense_ratio_monthly.csv`(2026-02 끝) · `COMMANDS.md:242` | 두 파일의 출처와 갱신 절차가 어디에도 없다. 금리 허용 공백이 2개월이라 2026-10-01 이후 시세가 들어오면 생성 스크립트 3개가 멈춘다(보수 파일은 2027-03 부터). 멈추는 것 자체는 의도된 정책이다. → COMMANDS 에 출처 · 단위 · 갱신 순서 3줄(출처는 결정 13). **금리는 처리함(2026-10-09)**: FRED `FEDFUNDS` 로 2026-08 `0.0363` · 2026-09 `0.0375` 를 더했다(기존 331개월은 FRED 와 전부 일치, 줄 끝 CRLF 형식 유지). 이제 2026-11 시세까지 멈추지 않는다. 운용비율 파일은 2027-02 까지 허용 범위라 그대로 두었다 |
| 2-24 | 낮음 | 신규 · 결정 9 | `src/qbt/common_constants.py:24` `STORAGE_DIR = Path("storage")` | 경로가 실행 위치 기준이다(주석에 그렇게 적혀 있다). 저장소 루트 밖에서 돌리면 입력을 못 찾는다. 전역 「경로 기준은 파일 위치」와 어긋나지만, `__file__` 기준으로 바꾸면 git 추적 결과의 경로 문자열(`meta.json` 347줄 · `summary.json` 19개)이 절대경로가 돼 공개 저장소에 로컬 경로가 실린다 |

**테스트가 막지 못하는 결함** — 무거운 결함을 막아야 할 검사가 비어 있는 것. 모두 결함을 일부러 넣어(변형) 테스트가 통과하는 것을 확인했다. `review.md` 의 검사 보강 규칙상 고칠 대상이다(계기 = 앞으로의 코드 변경).

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 2-25 | 중간 | 신규 | `tests/qbt/test_buffer_zone_dual_ticker.py:77-83` · `:125-135`, `tests/qbt/test_portfolio_backtest_scenarios.py:159-161` (+ :503-506 · :721-722 · :1038-1039) | 신호 시세와 매매 시세를 나누는 계약이 두 엔진 모두에서 검사되지 않는다. 단일 엔진: 픽스처에 매도가 없어 `trades_df` 가 0행이라 체결가 단언이 `if not trades_df.empty:` 에서 건너뛰어지고, 에쿼티 단언(`equity < 주수 × 112`)은 신호 종가로 계산해도 참이다(메인 세션이 코드로 확인). 포트폴리오: 신호 · 매매 CSV 에 같은 표를 쓴다. 체결가 · 평가 종가를 신호 시세로 바꾸는 변형 6종이 모두 857 passed. 실제 설정(`buffer_zone_tqqq` 의 QQQ → TQQQ, Q-2-2XS 의 SPY / QQQ → SSO / QLD)이 이 경로를 쓴다. → 탐침 2개로 조건부 단언을 바꾼다(변형 없이 통과, 변형 5종에서 각 1 failed 확인됨) |
| 2-26 | 중간 | 신규 | `tests/qbt/test_walkforward_verdict.py:69-402` | 결론 문구 단언이 `!=` 와 숫자 포함 꼴이라, 결론이 한쪽으로 고정돼도 문자열은 늘 달라 통과한다(변형 5종 모두 19 passed). 이 모듈 머리말이 막겠다고 적은 사고(EMA → SMA 뒤 반대 결론을 표시)가 바로 이 모양이다. → 결론 문구 자체를 단언한다(탐침 3개 확인) |
| 2-27 | 중간 | 신규 | `tests/qbt/test_analysis.py:851-937` · `:939-977` | Sharpe · Sortino · 벤치마크 연간 수익률의 값을 검증하지 않는다(`!= 0` · 0.0 경계 · 정렬만). 연율화를 `sqrt(365)` 로 바꾸거나 벤치마크 수익률을 두 배로 해도 857 passed. 이 값은 `summary.json` → 대시보드로 나간다. → 손으로 계산한 값을 `approx` 로 단언 |
| 2-28 | 중간 | 신규 | `tests/qbt/test_parameter_stability.py:121-240` `TestFindPlateauRange` · `tests/qbt/test_analysis.py:751` | 픽스처가 코드와 같은 가정(연속 구간 · 월말 시작)을 해서 1-1 · 1-3 이 그대로 통과한다(`find_plateau_range([0.20, 0.10, 0.20], 0.9) = (0.0, 2.0)`). → 1-1 · 1-3 을 고칠 때 비연속 구간 1건 · 월중 시작 1건을 재현 테스트로 먼저 넣는다 |
| 2-29 | 낮음 | 신규 | `tests/qbt/test_stock_downloader.py:310` · `test_tqqq_simulation_outputs.py:240-241` · `test_walkforward_summary.py:309-318` · `test_engine_common.py:189` | 허용오차가 반올림 단위보다 커서 반올림을 지워도 통과한다. → 반올림 결과는 `==` 로 정확 비교 |

## 3. 상수화 필요

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 3-1 | 중간 | 확인 (제안 축소) | `src/qbt/backtest/portfolio_types.py:29-70` · `portfolio_engine.py:723-729` · `:880-907` · `portfolio_methods.py:381-383` · 러너 :299-320 · :379-392 | 자산 키 열 접미사를 7개만 중앙화했고 나머지는 리터럴이다. `portfolio_methods.py:381-383` 은 이미 있는 헬퍼도 안 쓴다. → 전부 상수화는 과하다. 2-5 삭제로 접미사 4종이 먼저 사라진다. 한 줄 래퍼 7개를 `asset_col(key, suffix)` 하나로 줄이고 상수는 두 파일 이상이 쓰는 접미사만 둔다 |
| 3-2 | 중간 | 확인 | `portfolio_types.py:119-122` `AssetSlotConfig` 기본값 | 200 / 0.03 / 0.05 / 3 이 `FIXED_4P_*` 와 같은 값의 리터럴이다. → 상수 사용(4줄), `backtest/CLAUDE.md:100` 의 숫자 삭제 |
| 3-3 | 낮음 | 확인 (보강) | 결과 파일 이름: `run_single_backtest.py:107` · `137` · `171` · `193` ↔ `app_single_backtest.py:143-146` / `run_portfolio_backtest.py` ↔ `app_portfolio_backtest.py:75` · `124` · `140` · `157` · `175` · `207` · `223` · `247` / `run_walkforward.py:240` · `254` · `257` ↔ `app_walkforward.py:886-888` | 러너와 대시보드 양쪽에 리터럴이 있다. 러너만 이름을 바꾸면 `app_single_backtest.py:149` 의 `continue` 때문에 탭이 조용히 사라진다. WFO 모드 키 `"dynamic"` · `"fully_fixed"` 도 러너 :319 · :437-438, `walkforward_verdict.py:39-40`(비공개), 앱 :228 · :229 · :556 에 따로 있다. → `WALKFORWARD_*_FILENAME` 선례대로 src 상수(단일 4개 이름 · 윈도우 파일 이름 함수 1개 · 모드 키 2개) |
| 3-4 | 중간 | 확인 | 고원 결과: `run_param_plateau_all.py:48` · `327` ↔ `parameter_stability.py:23` · `47` | 경로 · 파일 패턴이 두 벌, 파라미터 이름이 4곳이다. → 이미 있는 `get_plateau_dir()` 를 러너가 쓰게 하고(5-8) src 에 `plateau_csv_path(param, metric)` 하나 |
| 3-5 | 중간 | 확인 (제안 변경) | 원본 티커 목록 | HAA · 로테이션이 쓰는 IWM · VWO · VNQ · IEF · TIP · EWY 가 COMMANDS · README 에 0건이다. → 튜플을 만들면 읽는 코드 없는 상수가 된다. COMMANDS 에 빠진 6종을 한 줄 추가 |
| 3-6 | 중간 | 확인 · 결정 10 | `src/qbt/tqqq/simulation.py:692` `_save_daily_comparison_csv` | `.round(4)` 가 가격 2열과 % 열 8개에 똑같이 걸린다. tqqq 는 `backtest.constants` 를 import 할 수 없어 `ROUND_PRICE` 단일 출처 밖이다. → `ROUND_*` 를 `common_constants.py` 로 옮긴다. 단 % 열을 2자리로 낮추면 스프레드 랩의 일일 증분 재계산이 깨진다 |
| 3-7 | 낮음 | 확인 (근거 정정) | `run_walkforward.py:182` · `184` · `291` · `293` · `295` · `477-481`, `run_single_backtest.py:202-209` · `262-267`, `run_param_plateau_all.py:116-118`, `runners.py:159-160` | 반올림 자릿수 2 · 4 를 숫자로 적었다. 근거는 루트 규칙(가격 자릿수 문장)이 아니라 `constants.py:68` 「자릿수 SoT」 주석이다. → `ROUND_PERCENT` · `ROUND_RATIO` |
| 3-8 | 낮음 | 확인 | 리밸런싱 사유 문자열: `portfolio_engine.py:95-96`(비공개), `"methods"`(`portfolio_methods.py:364` · `portfolio_validation.py:441`), `"allocation"`(러너 :82 · 앱 :82), 사유 → 문구 두 벌(앱 :399 · :1226) | → `portfolio_types` 공개 상수 + 문구 사전 하나. DEFERRED 6 을 표 삭제로 풀면 `"allocation"` 과 문구 사전 한 벌이 먼저 사라진다 |
| 3-9 | 낮음 | 확인 | 주문 의도 종류 묶음: `portfolio_engine.py:93-94` · `:395` · `:397`, `portfolio_execution.py:100` · `:187`, `portfolio_validation.py:48` | → `OrderIntent` 옆에 SELL · BUY 튜플 2개 |
| 3-11 | 낮음 | 확인 | `src/qbt/backtest/allocators/haa.py:19` | `HAA_ASSET_IDS = (*OFFENSIVE, "bil")` 리터럴이라 방어 자산 목록을 따라가지 않는다. → `tuple(dict.fromkeys((*OFFENSIVE, *DEFENSIVE)))` |
| 3-12 | 낮음 | 확인 (정정) | 화면 문구의 직접 수치 | `app_parameter_stability.py:225`(4P 값 — 같은 탭 :167-168 이 이미 상수로 보여 준다) · `:133/136`(80%), `app_portfolio_backtest.py:939`(10%), `run_supplement_grid.py:133`(95%) · `:134`(「7 중」), `app_walkforward.py:267-269` ↔ `walkforward_verdict.py:24-32`. 정정: `app_rate_spread_lab.py:486` 「1.0467」은 2026-02-08 실행의 값이고 지금 CSV 는 1.0434, 「60개월」은 6줄이다. → 4P 숫자와 스프레드 랩 고정 서술은 삭제, 나머지는 f-string 으로 상수 참조 |
| 3-13 | 낮음 | 확인 (제안 변경) | `app_walkforward.py:65` · `71` · `98` (+ :1092) | 사전 3개가 전략 이름을 다시 적는다. `STRATEGY_CONFIG` 는 스크립트 안이라 앱이 import 할 수 없다. → 앱이 이미 가진 `_discover_wfo_strategies` 결과 × 2모드로 만든다 |
| 3-14 | 낮음 | 확인 | `app_single_backtest.py:236` · `app_portfolio_backtest.py:1401`(`OHLC_CHANGE_PCT_COLUMNS`), `walkforward.py:201-234`(`"calmar"` 등), `walkforward_verdict.py:421`(365.25 → `ANNUAL_DAYS`) | 이미 있는 상수를 안 쓴다. → 상수 사용 |
| 3-15 | 낮음 | 확인 | `analysis_helpers.py:188`, `tqqq/constants.py:63`, `visualization.py:409` · `413` · `438`, `tqqq/data_loader.py:344-345`, `stock_downloader.py:139-140` · `160` | 12 · 13개월이 5곳이다. → 창 12 만 상수로 두고 13 은 창 + 1 로 파생, `aggregate_monthly` 기본값 인자 삭제 |
| 3-17 | 낮음 | 신규 | `run_portfolio_backtest.py:410-412` · `run_param_plateau_all.py:118` · `run_single_backtest.py:205` ↔ `run_walkforward.py:156-167` | 비율 지표 자릿수가 저장물마다 다르다(Calmar: 단일 · 고원 · 포트폴리오 2자리, WFO · 그리드 4자리 — 채택 조합 `summary.json` 0.62 ↔ `combo_runs.csv` 0.6165). 고원 판정도 2자리로 깎인 값에서 한다(SPY 매수 버퍼 고원: 2자리 (0.02, 0.05) / 원값 (0.01, 0.05)). → 비율 지표는 `ROUND_RATIO` 로(재산출 필요). 3-7 과 한 번에 |
| 3-18 | 낮음 | 신규 | `run_portfolio_backtest.py:341-342` · `late_entry_rally_opportunities.py:38` | `f"ma_{slot.ma_window}"` 와 `MA_COL="ma_200"` 이 `constants.ma_col_name` 을 다시 적는다. → `ma_col_name(...)` |
| 3-19 | 낮음 | 신규 | `haa.py:25` `HAA_WARMUP_ROWS = 253` | 주석의 산식(12개월 × 21거래일 + 1)을 숫자로 적어 `HAA_LOOKBACK_MONTHS` 를 따라가지 않는다. → 산식으로 |
| 3-20 | 낮음 | 신규 | `app_walkforward.py:536-541` ↔ `walkforward_verdict.py:324-329` ↔ `app_walkforward.py:605-608` | WFO 파라미터 목록 · 라벨이 3벌이고 「예: 100, 150, 200일」은 그리드 상수를 베껴 쓴 것이다. → verdict 의 목록을 공개해 재사용, 예시 숫자 삭제 |
| 3-21 | 낮음 | 신규 · 결정 14 | `tests/qbt/test_buffer_zone_dual_ticker.py:80`(0.003) · `test_engine_common.py:29-151`(99.7 / 100.3) · `test_parameter_stability.py:80-83` · `test_buffer_zone.py:200` · `test_portfolio_planning.py:620` · `test_allocators.py:563` · `test_tqqq_data_loader.py:596` | 프로덕션 상수 대신 손으로 박은 값을 쓴다. 상수가 바뀌면 테스트가 실패하므로 안전한 쪽으로 틀린다. → 상수 참조. 일부러 정책 값을 고정한 것인지는 결정 14 |

## 4. 불필요한 상수

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 4-1 | 낮음 | 확인 | `src/qbt/backtest/constants.py:97` `COL_CHANGE_PCT` | 이 열을 만드는 코드가 없다(`run_walkforward.py:23` · `228` · `235` 만 참조). → 삭제 4줄 |
| 4-2 | 낮음 | 확인 | `tqqq/constants.py:159-161` · `166` `KEY_FINAL_CLOSE_*` · `KEY_CUMULATIVE_RETURN_REL_DIFF` | 읽는 곳 0. → 2-13 과 묶어 삭제 |
| 4-3 | 낮음 | 확인 | `tqqq/constants.py:42` `DEFAULT_SYNTHETIC_INITIAL_PRICE` | 이음매 스케일이 시작 가격을 흡수한다(200 과 1.0 의 결과가 6자리 반올림 뒤 같다). → 삭제하고 1.0 |
| 4-4 | 낮음 | 확인 | `tqqq/constants.py:78-79` `WALKFORWARD_LOCAL_REFINE_A/B_DELTA` | 설명문(`app_rate_spread_lab.py:1590`) 전용이다. → 삭제 |
| 4-6 | 낮음 | 확인 (정정) | 한 파일에서만 쓰는데 공용 상수 파일에 있는 것 | tqqq: `MAX_EXPENSE_MONTHS_DIFF` · `INTEGRITY_TOLERANCE` · `DEFAULT_MIN_MONTHS_FOR_ANALYSIS` · `COL_DAILY_SIGNED` · `COL_DR_LAG1/2` · `COL_CUMUL_MULTIPLE_LOG_DIFF_*` · 스프레드 랩 전용. backtest: `CALMAR_MDD_ZERO_SUBSTITUTE` · `MIN_VALID_ROWS` · `DEFAULT_WFO_MIN_TRADES` · `COL_HOLDING_DAYS` 등. → 옮기기 전에 삭제부터: 5-1 · 5-4 로 tqqq 3개가, 6-12 로 `COL_TOTAL_RETURN_PCT` · `COL_FINAL_CAPITAL` 이 사라진다. `SPREAD_LAB_DIR` patch 는 `tests/qbt/conftest.py:161` · `:232` 두 곳이고 파생 경로가 import 때 굳어 둘 다 효과가 없다 → 2줄 삭제 |
| 4-7 | 낮음 | 확인 | `allocator_registry.py:61` · `67` `AllocatorSpec.allocator_id` · `StrategySpec.strategy_id` | dict 키와 같은 값이고 읽는 곳 0. → 칸 삭제 |
| 4-8 | 낮음 | 확인 (정정) | scripts | `run_param_plateau_all.py:68-84` `_VALID_EXPERIMENTS`(= `_EXPERIMENT_META` 의 키) → 삭제. `run_portfolio_backtest.py:73` `_CONFIG_MAP` → 인라인. `app_rate_spread_lab.py:78` `DEFAULT_STREAMLIT_COLUMNS` → 삭제. 정정: 두 그리드 러너의 같은 `DISPLAY_*` 는 14개가 아니라 12개이고, 공용화는 보류한다(7-7) |
| 4-9 | 낮음 | 신규 | `src/qbt/backtest/supplement_experiment.py:201-207` `GATE_IDS` | src · scripts 사용 0(테스트 1줄). → 삭제 |

## 5. 불필요한 함수

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 5-1 | 중간 | 확인 | `simulation.py:540-619` `_calculate_cumul_multiple_log_diff` · `analysis_helpers.py:322-396` `validate_integrity` | 같은 공식의 두 구현을 서로 대조할 뿐이다(실데이터 4,180행 최대 차 4.574e-14). → `abs = signed.abs()` 한 줄로 바꾸고 두 함수 · `INTEGRITY_TOLERANCE` 삭제(약 165줄) |
| 5-2 | 중간 | 확인 (제안 변경) | `src/qbt/backtest/strategies/buffer_zone.py:54-98` `resolve_buffer_params` · `backtest_engine.py:555-562` | 같은 4개 검사가 두 벌이다. → 검증 자리는 `BufferStrategyParams.__post_init__` 이 아니라 **`BufferZoneStrategy.__init__`** 이다. 전략 생성 9곳이 모두 거기를 지나 단일 백테스트 · 포트폴리오 슬롯 · EWY 배분 규칙 · WFO 가 함께 막힌다(`__post_init__` 은 2곳만 덮는다). 상한(< 1) 2줄을 더해야 `sell=1.5` · `buy=5.0` 이 막힌다. 넣어도 테스트 857개 통과. 그 뒤 두 곳의 검사 8줄과 `resolve_buffer_params` 삭제. 9-6 · DEFERRED 9 가 함께 풀린다 |
| 5-3 | 중간 | 확인 (자리 변경) | `scripts/data/generate_proxy_series.py:64-86` ≡ `generate_long_proxy_series.py:79-106` `_save_price_csv` · `_describe` | 글자 단위로 같다. → 자리는 `stock_downloader` 다(`download_stock_data:145-153` 도 같은 「6자리 → 검증 → 저장」). 셋이 함께 쓰면 입력 반올림 지점이 4곳에서 2곳으로 준다(루트 `CLAUDE.md` 표 갱신) |
| 5-4 | 낮음 | 확인 | `src/qbt/tqqq/spread_lab_helpers.py:88-132` `add_rate_change_lags` | 결과 열을 읽는 곳 0. → 삭제(함수 45줄 · 상수 3개 · 테스트 9곳) |
| 5-5 | 낮음 | 확인 | 「미등록 strategy_id」 검사 3벌: `portfolio_data.py:50-52` · `portfolio_engine.py:219-221` · `portfolio_planning.py:71-73` | 실제로 닿는 것은 첫째 하나다(CSV 두 개를 읽은 뒤). → `_validate_slots` 에 3줄을 넣고 가드 3곳과 `create_strategy_for_slot` 래퍼 삭제 |
| 5-6 | 낮음 | 확인 (일부 제외) | 중복 구현 | `proxy_series.py:27-32` ≡ `proxy_comparison.py:116-121`, `tqqq/data_loader.py:59-104` FFR · 보수 로더, `walkforward.py:640` `_std`(= `statistics.stdev`), `app_portfolio_backtest.py:307` · `323` 같은 색상 함수 둘과 손 변환 2곳(:779-781 · :1286-1289, 약 30줄), `generate_proxy_comparison.py` ↔ `app_proxy_comparison.py`. 제외: `portfolio_execution.py:131`(바꾸면 산식이 한 벌 더 생긴다 — 그대로 둔다) |
| 5-7 | 낮음 | 확인 | 한 줄 래퍼: `app_daily_comparison.py:28` · `download_data.py:63` · `run_walkforward.py:91` · `run_param_plateau_all.py:145` | → 인라인. `download_data` 는 `tickers = [...] if args.ticker else DEFAULT_TICKERS` 한 루프로, `run_walkforward` 는 `STRATEGY_CONFIG` 를 전략 이름 튜플로 줄이면 래퍼와 사전이 함께 없어진다 |
| 5-8 | 낮음 | 정정 | 프로덕션 호출부 없음 | `walkforward.py:486` `load_wfo_results_from_csv` · `_WFO_CSV_*` → 삭제(약 50줄). `parallel_executor.py:132` `execute_parallel` → kwargs 판과 합친다. 정정: `parameter_stability.py:250` `get_plateau_dir` 는 삭제가 아니라 **연결 누락**이다 — 러너가 같은 경로를 하드코딩한다(3-4) |
| 5-9 | 낮음 | 신규 | `scripts/tqqq/generate_daily_comparison.py:102-133` | 방금 쓴 CSV 를 다시 읽고 같은 값을 다른 이름으로 meta 에 두 번 남긴다. → 중복 필드 삭제 |
| 5-10 | 중간 | 신규 · 결정 6 | `src/qbt/utils/meta_manager.py` · `storage/results/meta.json` | 실행 이력을 쓰는 스크립트는 10개인데 읽는 코드 · 대시보드는 0 이다(메인 세션 grep 확인). 이력 5칸은 한 번 실행의 실험 5개(포트폴리오)나 14개 전략 중 마지막 5개(단일)라 이력으로도 최신 출처로도 못 쓴다. 고원 러너는 아예 저장하지 않는다 |
| 5-11 | 낮음 | 신규 | 중복 테스트: `test_portfolio_strategy_types.py:287-431`(= :82-284), `test_tqqq_data_loader.py:375-423`(= :97-154), `test_buffer_zone_execution_rules.py:428`(= :23) · `:388`(= :168), `test_tqqq_simulation_core.py:426`(= :82) · `:120` ⊂ `:228`, `test_engine_common.py:16-75` ⊂ `:124-264`, `test_buffer_zone.py:581-667` ≈ `:437`, `test_strategy_registry.py` 5곳, 동어반복(`test_portfolio_planning.py:77-172` · `test_buffer_zone_contracts.py:11-49` · `test_meta_manager.py:181-391`) | 같은 데이터에 같은 단언이거나, dataclass 를 만들고 되읽기만 한다. → 삭제(약 900줄, 추정) |

## 6. 데드코드

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 6-1 | 중간 | 확인 | `walkforward.py` `rolling_is_months` 경로 · `_first_day_months_before` | 프로덕션 호출 0(테스트 20줄). 실제로 쓰면 IS 구간만으로 이동평균을 다시 계산해 틀린 결과를 낸다(rolling 72개월 w5: 전체 기준 NaN 0행 / 그리드 재계산 199행). → 삭제(함수 21줄 · 인자 2곳 · 문서의 Rolling 언급) |
| 6-2 | 낮음 | 확인 | `portfolio_engine.py:511-513` · `:524-528` | `data.series_dfs` 를 잘라 두고 아무도 읽지 않는다. → 루프 둘(8줄)과 :505 복사 삭제 |
| 6-3 | 낮음 | 확인 | `backtest_engine.py:126-146` `_check_pending_conflict` · `PendingOrderConflictError` | 구조상 도달 불가다(:375 가 매 루프 pending 을 None 으로 만든 뒤에야 새로 넣는다). → 함수 · 예외 클래스 · 재노출 삭제, `backtest/CLAUDE.md` 「Critical Invariant」를 「구조로 보장」으로 |
| 6-4 | 낮음 | 확인 | `strategies/buffer_zone_helpers.py:19-28` `HoldState` · `buffer_zone.py:379-412` | `start_date` 는 쓰기만 하고 `buffer_pct` · `hold_days_required` 는 복사본이다. → 경과 일수 하나로(약 15줄 감소). `check_buy` 의 `current_date` 를 지우면 `WeightAllocator.target_weights(current_date)` 와 `noqa` 2줄도 함께 지울 수 있다(`haa.py:52` · `us_weakness_rotation.py:39`) |
| 6-5 | 낮음 | 확인 (정정 2) | 쓰이지 않는 인자 · 칸 | `backtest_engine.py:527` `params_schedule` · `simulation.py:408` `ffr_dict`(테스트 14곳) · `simulation.py:97` · `249-250` 고정 스프레드 float 경로 · `expense_dict` / `expense_df` 이중 · `MethodBook.initial_capital` · `AllocationAssetConfig.signal_data_path` · `portfolio_execution.py:154` `buy_buffer_pct`(저장된 값이 모두 0.0) · `run_walkforward.py:263` `strategy_name` · `run_param_plateau_all.py:113` · `120-121` · `types.py:61-62` `NotRequired` · `analysis_helpers.py:282` · `301-310` · `formatting.py` `Align.CENTER` · `indent` · `logger.py:160` `level`. 정정: `OrderIntent` 는 3칸이 아니라 4칸(`asset_id` 포함, 테스트 생성자 약 60곳이 걸려 우선순위 낮음). `PortfolioResult.display_name` 은 러너 :468 · :568 이 읽는다(`experiment_name` 만 0) |
| 6-6 | 낮음 | 확인 | `backtest/__init__.py` 8개 · `strategies/__init__.py` `__all__` 5개 · `utils/__init__.py` | 재노출을 쓰는 곳이 없다. → 비운다. `utils` 의 `get_logger` 는 외부 27곳이 쓰므로 남긴다 |
| 6-7 | 낮음 | 확인 (보강) | 도달 불가 분기 | `walkforward.py:779` · `606-619` · `540-541` · `715`, `csv_export.py:88-97`, `portfolio_engine.py:821`, `portfolio_methods.py:389`, `portfolio_data.py:240-245`, `run_portfolio_backtest.py:101` · `108-114` · `124-125` · `128` · `250-255` · `263-269` · `371` · `454`, `app_portfolio_backtest.py:1115-1117` · `748` · `776`, `run_single_backtest.py:86` · `88`, `app_single_backtest.py:666` · `815-816`, `app_walkforward.py:138-139` · `849` · `878` · `1118-1119` · `1150`, `run_walkforward.py:305`, `generate_synthetic.py:117-119` · `133-135`, `app_rate_spread_lab.py:1187`, 미사용 `logger`(`app_rate_spread_lab.py:68` · `:93`, `engine_common.py:21` · `23`, `runners.py:44` · `47`). → 삭제. 「조용히 건너뜀」(`walkforward.py:779` · `:715`)은 지우거나 RuntimeError |
| 6-8 | 낮음 | 정정 | 결과 · 메타 | `meta.json` 에서 쓰는 코드가 없는 키는 8개가 아니라 13개다(스프레드 랩 5개 포함, 파일 문자 수의 43.9%). `tqqq_rate_spread_lab` 이 가리키는 출력 파일 3개는 실제로 없다. 포트폴리오 `per_asset` 의 `win_rate` · `total_trades` · `final_avg_price` · `final_shares` 는 앱이 안 읽고 값도 오해를 부른다(`q2_2xs.sso` 거래 46 · 승률 93.48 은 리밸런싱 부분 매도까지 센 수) → 러너 :421-448 약 20줄 삭제. `download_data.py --start/--end` 결과 파일을 읽는 코드는 0 이다(`scripts/CLAUDE.md` 가 근거를 적어 둔 예외라 결정 16) |
| 6-9 | 중간 | 확인 (⑥ 확장) | tests | ① `enable_numpy_warnings` 픽스처(`conftest.py:312-340`)와 `test_numpy_warnings.py`(70줄)는 효과가 없다(픽스처를 빼도 5 passed — 테스트 본문이 스스로 경고를 켜고 numpy 기본값이 이미 warn 이다). → 삭제(사용처 2곳 · `tests/CLAUDE.md:159-171` 포함). `pytest.ini` 에 `error::RuntimeWarning` 을 넣어도 857 passed(결정 15). ② `test_portfolio_state_log.py:254` 는 픽스처 76행 중 리밸런싱 행이 0개라 늘 통과한다 → 삭제(같은 규칙을 `test_portfolio_validation.py:98-203` 과 `test_portfolio_methods.py:581` 이 덮는다). ③ `pytest.ini:48-51` 마커 3개 사용 0 → 삭제(+ `tests/CLAUDE.md:36`). ④ `conftest.py:193` 없는 픽스처 권장 · `:333` → 삭제. ⑤ `test_backtest_engine.py:141` `s._name` 은 읽는 곳이 없다 → `make_mock_strategy` 의 `name` 인자까지 삭제. ⑥ `conftest.py` 의 경로 `monkeypatch` 16줄 중 효과가 있는 것은 `meta_manager.META_JSON_PATH` 하나다(나머지 14줄을 지워도 결과 같고 실경로를 건드리지 않는다 — src 가 경로 상수를 실행 시점에 속성으로 읽는 곳이 0). → 두 픽스처를 하나로 합치고 meta 패치만 남긴다. 결정 6 으로 meta 를 지우면 둘 다 사라진다 |
| 6-10 | 낮음 | 확인 | `app_rate_spread_lab.py` 「파일 없음」 분기 8곳 | CSV 8개 모두 git 추적이고 생성 스크립트는 `c81690b` 에서 삭제됐다. → 분기를 지우고 직접 읽는다(약 80줄) |
| 6-11 | 낮음 | 신규 | `walkforward.py:566` `calculate_wfo_mode_summary(stitched_summary=None)` · `types.py:178-181` | 「이어 붙인 요약 없음」 경로는 테스트만 쓴다. → 필수 인자로 바꾸면 `NotRequired` 4개 · `.get` · `isinstance`(12-2) · 러너의 `if "stitched_cagr" in`(12-8)이 함께 사라진다 |
| 6-12 | 낮음 | 신규 | `walkforward.py:611` · `613` · `635`, `backtest_engine.py:223` · `229`, `runners.py:163` · `175-178` · `238-240` | 계산해 저장하지만 읽는 코드가 0 인 필드: `oos_calmar_std` · `oos_win_rate_mean` · `stitched_total_return_pct`, 그리드 결과의 `total_return_pct` · `final_capital`. → 삭제(상수 2개도 함께). `param_source` · `data_info` 는 출처 기록일 수 있어 남긴다 |
| 6-13 | 낮음 | 신규 · 결정 8 | 포트폴리오 `trades.csv` 의 `hold_days_used` · `trade_type` · `pre_shares` · `post_shares` · `order_amount` · `buy_buffer_pct` | 앱이 읽는 열은 `asset_id` · 진입 / 청산 날짜 · 가격 · `pnl_pct` 뿐이고 나머지는 기록만 된다. `hold_days_used` 전달 사슬이 src 4파일 약 15곳 · 테스트 38곳이다. `trade_type` 은 1-12 수정에 필요하다 |
| 6-14 | 낮음 | 신규 | `src/qbt/utils/proxy_comparison.py:163-164` · `:169` | inner join 뒤의 시작 · 끝 필터는 아무 행도 거르지 않는다(등록 20쌍에서 0행). → 3줄 삭제 |
| 6-15 | 낮음 | 신규 | `app_portfolio_backtest.py:1213` · `:1218` · `:1224` · `:1231` · `:490-491` · `:687` · `:724` · `:1330`, `app_single_backtest.py:411` · `:725` · `:667` · `:787` | 항상 있는 열의 존재 검사, 같은 값 두 번 계산, 모르는 사유를 「월초 정기」로 넘기는 분기. → 삭제. :1231 은 `monthly` 를 명시하고 모르는 값이면 RuntimeError |
| 6-16 | — | 철회 · 결정 7 | `app_parameter_stability.py:118-133` · `parameter_stability.find_plateau_range_with_trade_filter` | 「저거래 제외」 필터가 지금 제외하는 값이 0개인 것은 맞지만(QQQ 매도 버퍼 거래 수 25 / 18 / 14 / 12 / 9 / 5, 기준 5회) 데드코드가 아니다 — 연구 보고서 H.6 이 기준 5 를 유지하기로 확정한 장치다. 남긴다 |
| 6-17 | 중간 | 신규 | 늘 통과하는 테스트: `test_buffer_zone_execution_rules.py:255-290`(`assert True`) · `:347-386`(조건부), `test_buffer_zone_run.py:203-237` · `:239-281`, `test_walkforward_selection.py:95-125`(`in [100, 150]` 이 모든 행에 참) · `:310-355`(입력을 되읽음), `test_parallel_executor.py:95-137`(`init_worker_cache` 의 `clear()` 를 지워도 19 passed) | 단언이 없거나, 조건 때문에 검사 대상이 비거나, 입력을 그대로 되읽는다(실데이터 재현: hold0 은 거래 0, hold3 은 진입 0). → 실제 단언 한 줄로 바꾸거나 삭제 |
| 6-18 | 낮음 | 신규 | `tests/qbt/test_cli_helpers.py:40-152` | 예외 테스트 5개가 모두 로거 대체 경로(12-7)로만 돌아, 실제 주 경로(모듈 `logger` 감지)는 검사되지 않는다. → 테스트 모듈에 `logger` 를 두고 대체 경로 테스트(:107-129)는 12-7 과 함께 삭제 |

### 6-T. 삭제 후보에 묶인 테스트

위 삭제 · 수정 제안을 실행하면 함께 지우거나 고칠 테스트다(프로덕션 호출 수는 테스트 영역에서 다시 grep 했다).

| 삭제 후보 | 묶인 테스트 |
|---|---|
| `rolling_is_months` 경로(6-1) | `test_walkforward_windows.py:70-206` `TestRollingWfoWindows` 5개 · 137줄 |
| `load_wfo_results_from_csv`(5-8) | `test_wfo_stitched.py` 전체 221줄(5개) — `build_params_schedule` 연결은 `test_walkforward_schedule.py:447` 이 이미 고정한다 |
| `_check_pending_conflict`(6-3) | `test_buffer_zone_execution_rules.py:590-633` 1개 · 44줄 |
| `resolve_buffer_params`(5-2) | `test_buffer_zone.py:260-325` · `:335-357` 4개 — 지우지 않고 검사 대상을 전략 생성자로 바꾼다 |
| `run_buffer_strategy` 의 `params_schedule`(6-5) | `test_walkforward_schedule.py:261-397` `TestParamsSchedule` 3개 · 137줄(`TestParamsScheduleWhile` 은 프로덕션 경로라 남긴다) |
| `stitched_summary=None` 경로(6-11) | 지우지 않고 4개 테스트에 인자를 넘기게 고친다(`test_walkforward_summary.py:14` · `test_walkforward_selection.py:310` · `:358`) |
| `_validate_ffr_coverage`(2-2) | `test_tqqq_simulation_cost_model.py:190-319` `TestValidateFfrCoverage` 6개 · 130줄(6개 모두 시작일이 10 – 20일이라 2-2 의 크래시를 못 잡고, 2개는 열 이름 · 단위가 틀렸다) |
| `simulate` 고정 스프레드 float 경로(6-5) | 테스트 호출 20곳을 dict 로 바꿔야 한다(수정 범위가 가장 크다) |
| `_calculate_cumul_multiple_log_diff` · `validate_integrity`(5-1) | `test_tqqq_simulation_outputs.py:244-281` 2개 · `test_tqqq_analysis_helpers.py:207-280` 3개 |
| `add_rate_change_lags`(5-4) | `test_tqqq_spread_lab_helpers.py:205-289` 3개 · 85줄 |
| 검증 결과 필드 4개(2-13) | `test_tqqq_simulation_outputs.py:74-120` 2개 · 46줄 |
| `execute_parallel` 직접 호출(5-8) | `test_parallel_executor.py` 5개(88줄)를 kwargs 판으로 다시 쓴다 |
| `meta_manager` 전체(결정 6) | `test_meta_manager.py` 391줄 · `conftest.py:116-168` · `test_integration.py:116-125` · `:260-269` |
| 빈 equity → CAGR 0(12-4) | `test_analysis.py:401-441` 2개 → raise 테스트로 |
| verdict 안전 getter(12-3) | `test_walkforward_verdict.py:505-520` 1개 |
| `logger` 의 `level`(6-5) · 로거 대체 경로(12-7) | `test_logger.py:39-54` 1개 · `test_cli_helpers.py:107-129` 1개 |
| 계좌 단위 규칙 2 함수(7-4) | `test_portfolio_validation.py:98-203` 4개 · 106줄(19% / 21% 경계 테스트는 매매법 단위 판으로 옮긴다) |
| `GATE_IDS`(4-9) | `test_supplement_experiment.py:1371` 한 줄 |

## 7. 리팩토링

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 7-1 | 중간 | 확인 · 결정 4 | 대시보드 3개(`app_single_backtest` · `app_portfolio_backtest` · `app_walkforward`) | lightweight-charts 관련 함수가 단일 373줄 · 포트폴리오 305줄 · WFO 412줄이고 테마 · 캔들 · 이동평균 · 밴드 블록이 3벌이다. → Streamlit 에 의존하지 않는 dict 빌더 모듈 하나. 1-4 · 1-7 · 3-14 · 5-6 · 7-7 · 1-13 · 3-20 이 한 번에 정리된다 |
| 7-2 | 중간 | 확인 · 결정 5 | `app_rate_spread_lab.py`(1,690줄, 여러 줄 문자열 518줄) | 과최적화 판정 두 번, RMSE 추이 차트 두 번, `dict(zip(...))` 6회, 정적 RMSE 로딩 3회, 같은 모양 로더 5개. → 1-5 · 6-10 · 12-9 와 함께 약 300줄 감소 |
| 7-3 | 중간 | 확인 | `scripts/tqqq/generate_synthetic.py:101-129` | `qbt.utils.proxy_series.splice_proxy` 를 손으로 재구현했다. 바꾸면 결과가 저장 CSV 바이트(377,383B)까지 같다. → `splice_proxy(synthetic_df, tqqq_df)` 한 줄(약 30줄 감소). 9-8 · 6-7 일부가 함께 풀린다 |
| 7-4 | 중간 | 정정 | `src/qbt/backtest/portfolio_validation.py:90-127` · `:208-255` · `:514-522` | 정합성 규칙 2 의 두 벌은 「같은 규칙」이 아니다. 계좌 단위는 리밸런싱한 날 보유 자산 전부를, 매매법 단위는 조정을 처리한 자산만 본다. 그대로 합치면 Q-2-2XS 에서 결함 검출이 44 → 30 으로 준다. → 매매법 단위 하나로 합치되 「리밸런싱한 매매법은 보유 자산 전부, 배분 조정만 있던 날은 매매한 자산만」 보게 한다. 5개 실험 위반 0, 조합의 결함 검출 52 → 75, 테스트 4개 수정, 계좌 단위 함수 38줄 + 분기 약 8줄 삭제 |
| 7-5 | 중간 | 확인 | 버퍼존 밴드 산식 3곳: `buffer_zone_helpers.py:58-59` · `csv_export.py:175-176` · `runners.py:80-82` | → `enrich_equity_with_bands` 가 `add_buffer_zone_bands` 를 부르게 하면 행마다 apply 3줄이 사라진다(8-2 와 함께 `csv_export` 로) |
| 7-6 | 낮음 | 확인 (보강) | backtest · tqqq 계산 중복 | 유효 행 필터 3곳(`runners.py:127-130` · `walkforward.py:361-364`), MDD 두 벌(`analysis.py:181-187` · `:85-99`), Calmar 재계산 5곳(`backtest_engine.py:216`, `walkforward.py:201` · `348` · `381` · `634` — `calculate_summary` 가 이미 준다), verdict CAGR 블록 중복, MA 사전 계산 루프 3번, 누적수익률 3번(`simulation.py:660` · `739` · `754`), 시그널 CSV 반올림 블록 3러너 |
| 7-7 | 낮음 | 확인 (일부 보류) | scripts 중복 | 월별 히트맵 두 구현(`app_single_backtest.py:585-661` 77줄 · `app_portfolio_backtest.py:433-565`) → 포트폴리오 판 하나로. `run_param_plateau_all.py:182-269` 실험 블록 4개 · 피벗 두 벌. 보류: 두 그리드 러너의 공용 코드(끝난 실험의 재현용이고 공용화하면 표시 코드가 src 로 간다) |
| 7-8 | 낮음 | 확인 (보강) | 포트폴리오 엔진 | `run_portfolio_backtest` 본체 369줄, 자산 키 목록 출처 5곳, 배분 비중 두 번 채움, 메시지 전용 사전 검사 43줄. → 값 검사(`position <= 0` 등)는 남기고 메시지 전용 가드는 지운다(직접 인덱싱의 KeyError 도 멈춘다). 본체는 행 만들기를 함수로 빼는 정도 |
| 7-9 | 낮음 | 확인 (수치 정정) | tests 복붙 헬퍼 · 중복 테스트 | 본문이 같은 헬퍼: `_weekdays`(`test_allocators.py:49` = `test_supplement_experiment.py:80`), `_build_equity_df`(`test_analysis.py:854` = `:898`), `_fake_run`(combo :635 = supplement :1466), `_summary`(combo :35 = supplement :90), scenarios ≡ execution 3종, `_make_stock_df` 44줄(walkforward_schedule :18 = selection :14). `sample_monthly_df` 는 열이 달라 같은 본문이 아니다. 중복 테스트 3쌍은 확인(`test_analysis.py:35` ≡ `test_ma_type_policy.py:62` + `:83` 등). 같은 `run_walkforward` 호출 두 번은 전체의 34 – 37%(6.97초 / 20.32초)다. → 공용 헬퍼 모듈, 두 WFO 테스트는 하나로 합친다(module-scope 공유보다 단순). 그 밖의 중복은 5-11 |
| 7-10 | 낮음 | 신규 | `portfolio_validation.py:59-87` `_check_signal_execution_lag` | 행마다 `.iloc[i][col]` 로 돌아 검사기 시간의 대부분을 쓴다(채택 조합: 검사기 3.13초 중 2.56초, 벡터 비교는 0.0013초에 같은 결과). 그리드 301회가 매번 이 검사를 돈다. → 벡터 비교(코드도 준다). 9-2 와 함께 |
| 7-11 | 낮음 | 신규 | `portfolio_engine.py:412-464` `_build_params_json` · `_slot_params` | 설정을 손으로 직렬화해(53줄) `min_start_date` 가 `summary.json` 에서 빠진다 — 채택 조합이 2007-06-22 에 시작하는 이유가 결과에 없다. → `dataclasses.asdict(config)` + `json.dump(default=str)` |
| 7-12 | 낮음 | 신규 | `portfolio_data.py:42-47` · `portfolio_engine.py:158-160` · `:170-173` | `utils.data_loader.load_signal_trade_pair` 와 같은 로직이 3벌이다. → 2-11 캐시 삭제 뒤 그 함수 호출로 |
| 7-13 | 낮음 | 신규 | `portfolio_engine.py:276-286` `compute_portfolio_effective_start_date` | 이미 `date` 인 값을 다시 만들고 첫 행 하나를 얻으려고 슬라이스 · `reset_index` 를 한다. → `iloc[data.valid_start]`(약 8줄 감소) |
| 7-14 | 낮음 | 신규 | utils 6개 모듈 · `common_constants.py` | 「학습 포인트」 블록 86줄과 코드를 그대로 번역한 줄 주석이 많다(`logger.py` 주석 52 / 214줄). 전역 주석 규칙과 어긋난다. → 삭제(약 200줄, 추정), 「왜」만 남긴다 |

## 8. 구조개선

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 8-1 | 낮음 | 확인 (제안 변경) | `portfolio_configs.py:17-21` → `supplement_experiment` | 순환을 피하려고 Q-2-2XS 슬롯을 `q2_2xs_slots` 인자로 src · scripts 20곳에 넘긴다. → 새 모듈 없이, 슬롯 튜플을 `supplement_experiment` 상단 상수로 두고 `portfolio_configs` 가 가져다 쓴다(이미 그 방향으로 import 한다). 인자 20곳과 13-6 의 낡은 문구가 사라진다 |
| 8-2 | 낮음 | 확인 | `walkforward.py:46` | `runners` 에서 `enrich_equity_with_bands` 를 가져온다. → `csv_export` 로(7-5 와 함께) |
| 8-4 | 낮음 | 확인 | `src/qbt/utils/proxy_series.py` · `proxy_comparison.py` | 도메인 로직인데 `utils/CLAUDE.md` 는 「도메인 독립 기능만」이라고 한다. → 문구만 고친다 |
| 8-5 | 낮음 | 확인 | `tqqq/visualization.py` · `spread_lab_helpers.py` · `analysis_helpers.py` | 연구 대시보드 하나를 위한 코드가 src 3모듈에 걸쳐 있다. → 결정 5 에 따른다 |
| 8-6 | 낮음 | 확인 | `parallel_executor.py:17` | `from qbt.utils import get_logger` 가 패키지 초기화 순서에 기댄다. → `from qbt.utils.logger import get_logger` |
| 8-7 | 낮음 | 확인 | `docs/research/late_entry_rally_opportunities.py` | pyright 범위 밖이다. include 에 넣어도 strict 0 errors. → `pyrightconfig.json` include 1줄 |
| 8-8 | 낮음 | 신규 | `run_portfolio_backtest.py:78` · `:651-654` · `portfolio_types.py:218` · `supplement_experiment.py:405` · `:420` · `:460` · `:666` | 시작일 하한이 세 경로다(러너 상수 · 러너만 읽는 `config.min_start_date` · 엔진 `start_date` 인자). 그리드는 같은 날짜를 설정에도 넣고 인자로도 넘긴다. → 지금은 러너 2 – 3줄 수정(DEFERRED 10)만 하고, 엔진이 설정을 읽게 하는 안은 보류(엔진에 시작일 경로가 둘 생긴다) |

도메인 경계(backtest · tqqq · utils) 위반과 순환 import 는 0건이다. 보류: 8-3(결과 후처리 모듈 — 6-8 을 지우면 문제 자체가 작아진다).

## 9. 불가능 값 발생 시 중단되어야 하는데 누락된 곳

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 9-1 | 낮음 | 정정 | `portfolio_validation.py:168` · `:195` · 규칙 6 · 7 | 계좌 표만 NaN 인 합성 입력은 통과하지만, 엔진이 만든 결과는 규칙 7 이 잡는다(시세 종가 NaN 1행 → 「[규칙7] … 장부 몫 nan」). 닿지 않는다. → 뿌리는 9-12 |
| 9-2 | 낮음 | 확인 | `portfolio_validation.py:76-77` · `106-107` · `147-148` · `507-508` | 열이 없거나 상태 로그가 비면 규칙 1 · 2 · 3 · 7 을 조용히 건너뛴다(규칙 1 위반을 심고 상태 로그를 비우면 1 → 0건). 닿지 않는다. → 가드 4곳(약 9줄)을 지워 KeyError 로 멈추게 하고 :507 은 RuntimeError |
| 9-3 | 중간 | 확인 | `src/qbt/tqqq/data_loader.py:164-174` `_create_monthly_data_dict` | 월별 금리 · 보수의 NaN · 단위를 검사하지 않는다. 보수 2015-06 을 NaN 으로 두면 예외 없이 시뮬 종가 2,847 / 6,929행이 NaN, 금리를 % 단위(3.63)로 두면 0 이하 종가가 31행 생긴다. 두 파일은 손으로 고치는 파일이다. 무거움 · 닿는다(추정). → `isfinite and v < 1` 한 줄(하한 0 은 음수 금리 허용 계약과 부딪혀 넣지 않는다) |
| 9-4 | 낮음 | 정정 | `simulation.py:488` · `496-498` `simulate` | 기초자산 종가 NaN 을 `pct_change` 가 0% 인 날로 처리한다(다음 날은 2일치 수익률). 닿지 않는다(지금 입력 NaN 0건). → 뿌리는 9-12. 그 뒤 해당 분기는 삭제하거나 RuntimeError |
| 9-5 | 낮음 | 확인 | `backtest_engine.py:94-123` `_validate_backtest_inputs` | 시가 · 종가의 NaN · 0 이하를 검사하지 않는다(종가 NaN → 엉뚱한 「years <= 0」 메시지, 시가 0 → ZeroDivisionError, 돌파일 종가 NaN → 신호가 조용히 사라짐). 닿지 않는다(시세 43개 파일 NaN · 0 이하 0칸). → 9-12 |
| 9-6 | 중간 | 확인 | `portfolio_data.py:118-178` `validate_portfolio_config` · `:73-83` `_validate_slots` | 자본 0 · 음수 · NaN 이 검증을 통과해 엔진에서 엉뚱한 예외가 난다. **슬롯 파라미터는 에러 없이 돈다**: `hold_days=-1` → 최종 98,469,592(정상 106,497,267), `sell_buffer=1.5` → 228,414,443 · 매도 0건, `buy_buffer=5.0` → 거래 0건. 무거움 · 닿는다(설정 오기, 지금 0건). → 자본: `not total_capital > 0` 1줄을 넣고 `portfolio_data.py:198-200` 삭제. 파라미터: 5-2 |
| 9-7 | 낮음 | 확인 | `walkforward.py:773-795` `run_window_detail_backtests` | 이동평균 워밍업 NaN 구간을 그대로 엔진에 넣는다(44개 윈도우에서 결과 차이 0). → 선택 사항. 넣으면 윈도우 차트가 IS 시작부터 보이지 않게 된다 |
| 9-9 | 낮음 | 확인 | `app_portfolio_backtest.py:339-348` · `953-1013` · `1040-1049` · `1148-1167` · `:1264-1265`, `app_walkforward.py:302-312` · `402` · `457` | 값이 없으면 N/A · 0원으로 넘어간다. 현금 비중은 역산 + `clip` 이다(실제 cash / equity 와 최대 0.0292%p 차, Q-2 534행에서 음수를 `clip` 이 숨긴다). → 직접 인덱싱, 현금 비중은 `cash/equity` 한 줄 |
| 9-10 | 중간 | 신규 | `portfolio_data.py:79-83` `_validate_slots` | 슬롯 비중 0 을 검증이 허용하는데(메시지도 「0 이상」) 엔진은 0 을 못 다뤄 첫 매수 신호에서 「내부 불변조건 위반: BUY intent의 delta_amount <= 0」 RuntimeError 로 멈춘다(두 에이전트가 따로 재현). 무거움(죽는다) · 닿는다(설정). → `if not slot.target_weight > 0`(1줄, 비중 NaN 도 함께 막힌다) |
| 9-11 | 낮음 | 신규 | `walkforward.py:714-716` `run_stitched_equity` · `backtest_engine.py:354` · `buffer_zone.py:332` · `csv_export.py:53-64` | 윈도우 종료 자본을 못 찾으면 조용히 건너뛰어 윈도우 번호가 밀린다. 불변조건을 `assert` 로 뒀다. 닿지 않는다. → `:715` 는 `if` 삭제. 나머지는 규칙(RuntimeError)에 맞출지 판단 |
| 9-12 | 중간 | 신규 | `src/qbt/utils/data_loader.py` `load_stock_data` · `scripts/tqqq/generate_synthetic.py` | 시세 로더가 가격 NaN · 0 이하를 검사하지 않는다. 다운로더와 대용 · 대체 생성 2개는 저장 전에 검증하는데 **TQQQ 합성만 검증 없이 저장된다.** 지금 43개 파일은 이상 없다. → `validate_stock_data` 의 NaN · 0 · 음수 부분을 함수로 떼어 다운로더와 로더가 같이 쓴다(3줄). 9-1 · 9-4 · 9-5 가 한 곳에서 막힌다 |

## 10. 내부/runtime import 전수 조사와 근본 해결

- **전수(확인)**: 함수 안 import 는 190건이고 전부 `tests/` 의 28파일에 있다. src · scripts · `validate_project.py` · `docs/research/*.py` 는 0건이다(AST 집계 = `ruff --preview --select PLC0415` 집계 190).
  - 많은 순: `test_buy_and_hold.py` 23 · `test_tqqq_data_loader.py` 18 · `test_tqqq_simulation_cost_model.py` · `test_walkforward_schedule.py` · `test_parameter_stability.py` 각 14 · `test_walkforward_selection.py` 12 · `test_buffer_zone.py` 9.
  - 동적 import 1곳: `tests/qbt/test_walkforward_summary.py:267` 이 `importlib` 로 `scripts/backtest/run_walkforward.py` 를 읽는다. `scripts/backtest/__pycache__` 의 `.pyc` 가 그 부산물이다.
- **원인(확인)**: 「습관」이다. 190건을 전부 상단으로 옮긴 사본에서 `857 passed` 이고(사본의 src 를 쓰도록 `PYTHONPATH` 지정), monkeypatch 순서 · 순환 · import 시점 부작용 때문에 함수 안에 있어야 하는 import 는 0건이다. 허용하거나 요구하는 문서 규칙도 0건이다.
- **근본 해결(사본에서 확인)**
  1. **일괄 상단 이동.** 고유 이름 113개 중 이미 상단에 있는 9개를 빼면 새로 올라가는 이름은 104개, 이름 충돌 0. `ruff check --fix --select I,F811,F401` 이 144건(F811 118 · I001 28)을 고치고 남은 것 0. pyright 0 · pytest 857. 이동이 남긴 빈 줄 때문에 black 을 한 번 돌려야 한다(6파일).
  2. **재발 방지.** ruff `PLC0415`(함수 안 import 금지)를 켠다. 이 저장소의 ruff 0.8.6 에서는 preview 규칙이라 `[tool.ruff.lint]` 에 `preview = true` · `explicit-preview-rules = true` 를 두고 select 에 넣는다(`explicit-preview-rules` 를 빼면 C420 23 · E226 5 가 더 잡힌다). 이동 뒤 새로 잡히는 것은 F841 37건(튜플 언패킹 미사용 변수 — `test_buffer_zone_execution_rules.py` 23 등)뿐이다 — `_` 로 바꾼다.
  3. **동적 import 제거.** `_round_summary_for_json` 을 쓰는 곳은 러너 :323 과 그 테스트(:264-274)뿐인데, **그 테스트는 반올림을 통째로 지워도 통과한다**(아무것도 막지 않는다). → 테스트만 지우거나(가장 단순), src 로 옮길 때 3-7 의 `ROUND_*` 상수와 함께 정확 비교로 다시 쓴다. 어느 쪽이든 `importlib` · ignore · `.pyc` 부산물이 사라진다.

## 11. `# type: ignore` 전수 조사와 근본 해결

- **전수(확인)**: 152줄 = `type: ignore` 100 · `pyright: ignore` 19 · `noqa` 33. 위치는 src 6(전부 noqa) · scripts 11 · tests 135.
- **실측(메인 세션, 저장소 밖 사본)**

| 분류 | 건수 | 근거 | 해결 |
|---|---|---|---|
| 불필요 ignore | 105 | `reportUnnecessaryTypeIgnoreComment` 를 켜면 scripts 7 · tests 98 이 오류로 뜬다. 종류: `type: ignore[no-untyped-def]` 70 · `pyright: ignore[reportPrivateUsage]` 16 · `[arg-type]` 13 · 기타 6 | 삭제 |
| vendor import | 3 | `app_single_backtest.py:22` · `app_portfolio_backtest.py:27` · `app_walkforward.py:28`. `extraPaths` 에 `vendor/streamlit-lightweight-charts-v5` 를 더하면 불필요로 바뀐다(105 → 108) | `pyrightconfig.json` 1줄 + 삭제 |
| 코드 수정으로 없앨 수 있음 | 8 | `test_walkforward_schedule.py:535` · `536` · `544` · `545` · `548`(Protocol 타입으로 private 속성 접근), `test_backtest_engine.py:172` · `177` · `182`(MagicMock) | `isinstance` 로 좁히기 / `make_mock_strategy` 반환 타입을 `MagicMock` 으로 — 사본에서 pyright 0 · 해당 테스트 32 passed 확인 |
| 정당 | 3 | `test_buffer_zone.py:61` · `test_buffer_zone_contracts.py:78` · `99`(frozen dataclass 변경 시험) | `# pyright: ignore[reportAttributeAccessIssue]` 로 교체하고 `pytest.raises((AttributeError, Exception))`(모든 예외를 통과시킨다)를 `dataclasses.FrozenInstanceError` 로 좁힌다 — 사본에서 pyright 0 확인 |
| 쓰이지 않는 `noqa` | 18 | ruff `RUF100`: `ARG002` 15 · `ARG005` 3(ruff `select` 에 ARG 규칙이 없다). src 3(`allocators/` 세 파일) · tests 15 | 삭제 |
| 작동 중인 `noqa: E712` | 15 | `--ignore-noqa` 로 돌리면 E712 15건. `portfolio_validation.py:109` · `230`, `portfolio_methods.py:363`, `app_portfolio_backtest.py:1214`, tests 11 | 대상 열(`rebalanced` · `is_month_end`)은 모두 bool · 결측 0 이라 `df[df["rebalanced"]]` 로 바꾸면 사라진다. `test_portfolio_execution.py:494` 는 스칼라라 `assert not …` 꼴로 |

- **근본 해결(확인)**: 사본에서 ignore 108줄과 `noqa` 18줄을 지운 뒤 pyright 0 errors(불필요 ignore 검출 켠 채) · ruff 통과. 남는 것은 ignore 11줄과 `noqa: E712` 15줄이다.
  1. `pyrightconfig.json`: 루트에 `"reportUnnecessaryTypeIgnoreComment": "error"`, tests · scripts 환경의 같은 키 `"none"` 2줄 삭제, `extraPaths` 에 vendor 경로 추가.
  2. 주석 126줄 삭제. 재발 방지는 ruff `RUF100`.
  3. 주의: 지금 그 ignore 들이 불필요한 이유는 tests · scripts 환경이 해당 검사(`reportArgumentType` 등)를 꺼 두었기 때문이다. 그 완화를 걷으면 다시 필요해진다. 완화를 걷을 계획이 없으면 삭제가 답이다.
  4. pyright 는 mypy 식 괄호 코드(`[no-untyped-def]`)를 읽지 않고 줄 전체를 무시하므로, 남겨 두면 그 줄에 앞으로 생길 오류까지 가린다.
  5. `no-untyped-def` 70줄은 전부 tests 이고 그중 64줄이 `create_csv_file` 픽스처 인자를 받는 함수다. tests 환경이 그 검사를 꺼 두었으므로 픽스처에 타입을 붙이기보다 주석 삭제가 답이다(정정: 「tests 완화를 전부 끄면 316건」은 재현되지 않았다 — ignore 를 둔 채 220건, 지운 상태 331건).

## 12. 불필요한 fallback

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| 12-1 | 낮음 | 확인 (심각도 정정) | `app_parameter_stability.py:131-133` | `except (FileNotFoundError, KeyError)` 에서 필터 없는 고원을 칠하면서 라벨은 「저거래 제외」로 남는다. 닿지 않는다(러너가 같은 실행에서 4지표 CSV 를 함께 쓴다). → except 2줄 삭제. 더 큰 안은 6-16 |
| 12-2 | 중간 | 확인 | `walkforward.py:598-602` · `630-635` | `stitched_summary.get(..., 0.0)` · `isinstance`: 키는 항상 있고 빠지면 수익 집중도 · CAGR 이 0 으로 숨는다. → 6-11(필수 인자)로 해소 |
| 12-3 | 낮음 | 확인 | `walkforward_verdict.py:48-75` 안전 getter · `:411-419` try/except | 스키마 변경을 「데이터 없음」으로 숨긴다. → 직접 인덱싱(헬퍼 3개 약 30줄 삭제) |
| 12-4 | 낮음 | 확인 | `analysis.py:141-156` 빈 equity → CAGR 0 | 호출부 2곳 모두 빈 표가 올 수 없다. → 분기 15줄 삭제 → 예외 |
| 12-5 | 낮음 | 확인 · 결정 11 | `src/qbt/utils/data_loader.py:86-97` `load_stock_data` | 중복 날짜를 경고만 하고 지운다. 정렬이 불안정해 「첫 값 유지」도 거짓이다(같은 날짜가 2행씩인 정렬된 파일에서 1,500일 중 334일이 첫 행이 아닌 값을 남겼다). 지금 43개 파일 중복 0, 다운로더는 중복을 보지 않는다 |
| 12-6 | 낮음 | 정정 | 포트폴리오 엔진 | `portfolio_planning.py:92`, `portfolio_rebalance.py:56` · `112` · `133` · `147`(`.get(aid, 0.0)`), `portfolio_validation.py:81`(`=="nan"`), `portfolio_methods.py:177`(`max(cash, 0.0)`), `portfolio_engine.py:722` · `862` 의 「0 이하면 0 비중」 분기 → 직접 인덱싱 · 분기 삭제. 정정: 같은 줄의 EPSILON 은 불필요가 아니다(검사기 규칙 2 가 그 열을 기준에 견주므로 빼면 저장되는 비중이 달라질 수 있다) — 그대로 둔다 |
| 12-7 | 낮음 | 확인 | `cli_helpers.py:59-66` 로거 대체 경로 · `logger.py:160` | 테스트에서만 탄다. → `level` 인자를 지우면 대체 경로도 사라진다 |
| 12-8 | 낮음 | 확인 (보강) | 러너 | `run_single_backtest.py:267`(바로 위 주석 「silent default 금지」와 모순) · `:216` · `:210-211`, `run_walkforward.py:318-325` · `358-361`, `run_portfolio_backtest.py:134-138` · `250` · `414-415` · `425` · `436-439` · `569`. → 직접 인덱싱. 6-8 · DEFERRED 6 삭제안을 택하면 포트폴리오 쪽 대부분이 함께 사라진다 |
| 12-9 | 낮음 | 확인 | 대시보드 | `app_single_backtest.py:708-709` · `721-723` · `738` · `797-833`(main 의 try/except), `app_portfolio_backtest.py:252` · `814-815`, `app_walkforward.py:813` · `894-895`, `app_rate_spread_lab.py:862` · `988` · `:1037` · `.get("stitched_rmse")` 6곳 · `except Exception` 4곳(:200 · :234 · :328 · :337). → 직접 인덱싱 · try/except 삭제. `app_single_backtest.py:157-164` 의 `EmptyDataError` 처리는 지금 실제로 타므로 2-8 과 함께 |
| 12-10 | 낮음 | 확인 | `validate_project.py:71-73` · `122-124` | 파싱 실패 기본값 1. → 2-15 와 함께 삭제 |
| 12-11 | 낮음 | 신규 | `run_walkforward.py:329` `json.dump(..., default=str)` | 직렬화 못 하는 값이 섞이면 조용히 문자열이 된다(지금 값은 전부 기본 타입). → `default=str` 삭제 |

## 13. 문서 / 주석 / 코드 3자 불일치

### 13-A. 연구 보고서 결론 · 수치 ↔ 현재 결과

`전략` = `전략_검증_보고서.md`, `설계서` = `Q2_2XS_보완_전략_설계.md`, `지연` = `QQQ_지연진입_연구.md`, `상관` = `Q2_2XS_QQQ_상관계수_연구.md`.

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| R1 | 높음 | 확인 (범위가 더 넓다) | `전략` §2.5(L186-201) · §2.6 L212-213 · §12.2 L587-589 · §12.3 L627 · L631 · §20.3 L1016-1018 · §20.4 · §20.5.3-4 L1053-1084 · §21.1 L1103-1121 · §22.3 L1169 · L1174 · §25.5 L1342-1369 · §25.9 L1413 · §43 L2077 · C.3 L1636-1644 | 「Fixed ≥ Dynamic → 4P 동결 근거 유효」(QQQ 11.33 / 11.97)가 현재형으로 12곳에 있다. 지금 `walkforward_summary.json` 은 QQQ Dynamic 9.46 / Fixed 5.16, TQQQ 19.38 / 9.25 로 반대다(메인 세션 확인). 「이동평균이 11개 윈도우 전부 200」(L631)도 지금은 앞 4개가 100 이다. 현재 값이 맞는 곳은 G.8.1 표(L2891-2898) 하나다. 또 Fixed 는 첫 윈도우 값 (100, 0.03, 0.01, 5)이라 4P 가 아니다 — 「Dynamic ≈ Fixed」는 4P 동결의 근거가 될 수 없다. → §2.5 를 날짜 붙은 「WFO 현황」 한 단락으로 바꾸고, 나머지 자리는 지우지 말고 「[EMA 시절 결과 — SMA 에서는 성립하지 않는다 → §2.5]」 한 줄씩 붙인다(그 시점 결정의 근거라 이력으로 남긴다). 1-11 · R6 과 한 번에 |
| R2 | 중간 | 정정 | `전략` §2.3 · §2.4(L154-184) · 부록 A.3(L1516-1518) | 수치는 EMA · 2026-03-12 기준이다(QQQ 10.93 / −36.49 / 0.30 ↔ 지금 9.61 / −30.26 / 0.32). 정정: 「현재 · summary.json 기준」 문구는 A.3 에만 있고, A.3 은 §19.1 의 중복이 아니다(기간 · 거래 수 · 승률 · TQQQ 행은 A.3 에만 있다). → §2.3 · §2.4 표를 지우고(A.3 · §19 의 부분집합) 「EMA · 2026-03-12 기준, 표는 §19 · 부록 A」 한 줄만. A.3 제목의 「현재」를 기준일로 |
| R3 | 중간 | 확인 | `지연` 1장 L67 · L72 · 4장 L159-168 · 14.4 L674 · L686 | 진입가 646.816 · 폐기 기준 680.86 · 성과 1,021.37% / 9.49% 를 「결과 파일 값」으로 적었다. 지금은 646.1427 · 680.15 · 1,066.05% / 9.61% 다(수정주가 재조정). 스크립트를 지금 데이터로 돌리면 7 · 8 · 13장의 수익률 · 승률 · 정책 표는 그대로다. → 1장 · 14.4 에 「진입가는 수정주가라 분배금마다 내려간다 — 폐기선은 그때 진입가 ÷ 0.95」 한 문장, 4장 성과 표는 지우고 `summary.json` 을 가리킨다 |
| R4 | 낮음 | 확인 | `지연` L8 · L15-17 · L296-303 · L672, `전략` G.5 L2702-2705 | 「2026-08-28 행 결측으로 갱신 불가」는 이미 해소됐다(`QQQ_max.csv` 에 그 행이 있다). → 삭제 |
| R5 | 낮음 | 확인 (1건 정정) | 그 밖 | `전략` L1415 `split_strategy.py`(없는 파일) → 「구현 코드는 제거됨」. G.1 L2633-2635 「§14 등급표」 → §8.2. `지연` 12장 L369-378(같은 장 L347-351 과 자기모순) → 삭제. 정정: `상관` 12장 「모든 수치 재현」(L394)은 틀리지 않았다 — 커밋 `18b75fb` 의 두 파일로 전 수치가 재현된다. 빠진 것은 커밋 고정 한 구절이다. 설계서의 「커밋 전」 · 지운 실험의 현재형 · 머리말 「예비 수치」는 설계서를 지우므로 손대지 않는다(부록 M 에 옮길 때 현재형으로 다시 쓴다) |
| R6 | 높음 | 신규 | `전략` §22.3 L1167-1175 · §23.2 L1207 | 운영 점검 기준이 「Dynamic 대 Fixed」인데 Fixed 는 4P 가 아니다. 지금 결과로는 체크 1 이 「경고」(QQQ 9.46 대 5.16)이고, 체크 2 도 앞 4개 윈도우(100일선 · 매도 1%)가 고원 밖이다. 본문은 둘 다 「현재 상태: 정상」이다(메인 세션 확인). 기준 3(2.0배)에 TQQQ 가 1.98배다. → 「현재 상태」 두 구절 삭제. 비교 대상을 다시 정하는 것은 결정 1 |
| R7 | 중간 | 신규 | `전략` §23.2 L1206 · §23.4 L1233 · K.8 L4025 ↔ `설계서` 5.10 | 「−36.49% × 1.5 = −54.7%」 · 「−36%」는 EMA 값이다(지금 −30.26 → −45.4). 설계서 5.10 은 기준 1 을 Q-2-2XS 과거에 대어 「2018 · 2019 · 2020 발동」을 이미 쟀는데 K.8 은 「하지 않았다」고 적는다. → 설계서를 지우기 전에 5.10 결과를 §23 또는 부록 M 「남은 질문」으로(예비 표시) |
| R8 | 중간 | 신규 | `전략` G.7.2 L2775 · L2776 · L2778 | 이동평균 고원 실험도 기간마다 평가 시작일이 다르다(QQQ 1999-05-19 ~ 2000-05-15 — G.2 가 스스로 경고한 함정). 공통 시작일이면 QQQ 정점이 250 → 200 으로 바뀐다(고원 (200, 250) 은 그대로). 1-3 을 고치면 유지일 칸이 (0, 10) → (2, 10), 3-17 을 고치면 SPY 매수 버퍼 칸이 (0.02, 0.05) → (0.01, 0.05). 판정 칸은 그대로다. → [한계] 한 줄 또는 1-11 코드 수정에 포함 |
| R9 | 중간 | 신규 | `전략` §39.1 L1960-1972 · §53.1 L2565 | 「유지 실험 9개」가 현재형인데 공식 실험은 5개다. F-6H(§40 「최종 선정」) · Q-1 · Q-3 · Q-2-2X · Q-2-2XH 의 제거 기록이 없고, L2565 「(부록 D)」는 틀린 가리킴이다. → 부록 D 에 「이후 제거」 표 하나, §39.1 제목에 「(2026-04 당시)」 |
| R10 | 중간 | 신규 | `지연` L199-200 | EMA 시절 문장이 남았다(「2008-05-07, 2015-10-28」, 「12개 트레이드」). SMA 표에는 2008-05-07 이 없고 손실은 13개다. → 두 문장의 수치만 고친다 |
| R11 | 낮음 | 신규 | `전략` G.7.5 L2874 | 「`sell_buffer` 는 필터 기준 미확정으로 보류」 ↔ G.7.2 L2790 「확정」 · 부록 H 「유지」. → 한 칸 수정 |
| R12 | 낮음 | 신규 | `전략` 부록 K, `지연` 13.9 · 14.2 | 재현 경로가 없다. K 의 원문(계산 코드 포함)은 `1ef48c0^` 에 있는데 포인터가 없다. 지연 13.9 · 14.2 는 스크립트에 없는데 채택된 14장 규칙의 유일한 근거 표다. → K 머리말에 커밋 포인터 1줄, 지연 12장에 「13.9 · 14.2 는 일회성 측정」 1줄 |
| R13 | 낮음 | 신규 | `전략` L6 · L86 · L408 | 「모든 수치는 4P 기준」 ↔ §3 – §7 은 5P, §14 – §15 는 3P. 「수치 기준일 2026-03-12」는 부록 G 이후를 덮지 못한다. → 머리말에 기준 한 줄, L86 「모든 수치」 삭제 |
| R14 | 낮음 | 신규 | `전략` §11.3 L507-517 | 3단계 계획 중 2단계의 결과가 어디에도 없다. → §11 삭제 때 「2단계는 실행 기록 없음」 한 줄 |

영향 없음으로 확인한 것: 1-1(첫 해 누락)은 연구 문서 수치를 바꾸지 않는다(J.5 · K.5.1 의 연도별 표는 `equity.csv` 로 따로 계산했다). 1-2(QQQ 초과수익)와 1-5(스프레드 랩 판정)를 인용하는 곳도 0건이다.

### 13-B. 안내 문서 ↔ 코드

| # | 심각도 | 판정 | 위치 | 내용 → 제안 |
|---|---|---|---|---|
| D1 | 중간 | 확인 | `docs/COMMANDS.md:149-150` · `:191-192` | `--cov` 를 「커버리지 포함 전체 검증」이라 적었는데 실제로는 lint · pyright 를 끄고 테스트만 돈다(`validate_project.py:266-270`). 같은 명령이 COMMANDS 안에 두 번이다. → 「테스트 + 커버리지만」으로 고치고 「커버리지」 절(:188-197)을 지워 한 곳만 남긴다 |
| D2 | 중간 | 확인 | `COMMANDS.md:72` (· :34-35 · :47 · :78) | WFO 대상을 「`buffer_zone.py::CONFIGS`」(7개)로 적었는데 실제는 `run_walkforward.py:75-88` `STRATEGY_CONFIG` 2개다. → 선택지를 문서가 가리키지 않고 「선택지는 `--help`」 한 줄(argparse choices 가 그대로 나온다) |
| D3 | 중간 | 확인 | `COMMANDS.md:88` · `:92` · `:86` · `:90` · `:94` | 대시보드 선행 번호가 한 칸씩 밀렸고(3 · 4 → 4 · 5), WFO 대시보드에 「WFE 분포」 섹션은 없다. → 「시각화:」 주석 3줄 삭제(앱 docstring 이 정본), 선행 번호는 D4 의 순서 블록으로 대체 |
| D4 | 높음 | 확인 (심각도 상향) | `COMMANDS.md:39` · `:116` · `:228` · `:243` | 포트폴리오에 「TQQQ 합성 필요」는 틀렸다(5개 실험 중 0, 실제로 필요한 것은 `generate_proxy_series.py` 산출 4종). 반대로 TQQQ 합성은 단일 백테스트 · WFO 에 필요한데 「(선택)」이다. 이 안내를 따른 결과로 합성 파일이 실제로 반년 낡았다(2-1). 원본 티커 IWM · VWO · VNQ · IEF · TIP · EWY 안내도 0건이다. → **COMMANDS 에 「데이터를 다시 받은 뒤 다시 돌리는 순서」 블록 하나**: ① 원본 시세 ② `storage/etc` 금리 · 운용비율 ③ `generate_synthetic.py` ④ `generate_proxy_series.py` → `generate_long_proxy_series.py` → `generate_proxy_comparison.py` ⑤ `generate_daily_comparison.py` ⑥ 단일 → 워크포워드 → 고원 → 포트폴리오 → 두 그리드. 「다시 받으면 다시 실행」 5곳(COMMANDS 2 · `scripts/CLAUDE.md:131` · 생성 스크립트 docstring 2)이 이 블록으로 대체된다. 받아야 할 원본은 목록 대신 「`storage/stock/` 의 `*_max.csv` 중 생성 파일(`*_synthetic_max` · `*_proxy_max`)이 아닌 것 전부」(추적 43개 중 원본 33 · 생성 10)로 정의한다. 금리 · 운용비율의 출처는 문서 0건이라 결정 13 에서 묻는다(2-23) |
| D5 | 중간 | 확인 (제안 변경) | `src/qbt/backtest/CLAUDE.md:579-633` · `scripts/CLAUDE.md:177` · `191` · `192` · `194` · `README.md:45` | 「결과 폴더를 스캔 · 알파벳 순 탭」은 틀렸다(실제는 `CONFIGS` · `PORTFOLIO_CONFIGS` 등록 순서). 「Plotly 전용」도 틀렸다(시그널 차트는 lightweight-charts). 같은 절의 다른 문장도 코드와 어긋난다: 「산식을 자체 수행하지 않는다」(WFO 앱이 수행 — 1-7), 「포트폴리오: equity, dd」(포트폴리오 캔들 tooltip 에 없음), 「동일 규약」(1-4), 「초기 자본이 같아 절대값 비교」(시작일이 셋 — 1-14), 「각 섹션 3부분」(5개 중 4개만). → 고치지 말고 `backtest/CLAUDE.md` 「대시보드 앱 아키텍처」 절(55줄)을 지운다(CLI 계층 설명이라 자리가 틀렸고 앱 docstring 과 겹친다). `scripts/CLAUDE.md` 는 앱당 한 줄 |
| D6 | 낮음 | 확인 | `src/qbt/backtest/supplement_experiment.py:379` · `385` · `backtest/CLAUDE.md:263` | 「`build_experiment_config` 가 등록 실험과 그리드가 같은 구성임을 보장」 ↔ 등록 실험은 `build_combo_config` 만 쓴다(`portfolio_configs.py:17-21`). → 8-1 을 풀면 문구가 통째로 사라진다. `:263` 뒷문장 「그리드와 같은 시작일 하한이라 대시보드 숫자가 그리드와 같다」는 DEFERRED 10 이 고쳐지기 전에는 보장이 아니므로 삭제 |
| D7 | 낮음 | 확인 | `backtest/CLAUDE.md` 모듈 카탈로그(:13-474) | 없는 이름(`create_runner` :424 · `grid_results.csv` :24), 틀린 이름(`_enrich_equity_with_bands` :448 · 450 — 실제는 공개 함수), 누락(`walkforward_verdict.py` · `calculate_drawdown_pct_series` · `calculate_calmar`), Prettier 가 깨뜨린 이름(:61 · 62 · 374 · 421), 틀린 인자명(:192 · :365-366), 반대로 적힌 의존 화살표(:460), 없는 실험 계열(:98 · 241 · 242). → 18-D 축약으로 함께 해소(카탈로그를 모듈당 한 줄 지도로) |
| D8 | 낮음 | 확인 | `scripts/CLAUDE.md:254-262` · `:144` · `153-154` · `src/qbt/utils/CLAUDE.md:23-29` | CLI 인자 예외를 2개로 적었는데 `add_argument` 가 있는 스크립트는 5개다. 포트폴리오 결과 목록에 `state_log` · `execution_comparison` 이 없고 `load_signal_trade_pair` 도 빠졌다. → 「명령행 인자」 절 18줄을 「인자를 받는 스크립트는 `--help` 가 정본」 2 – 3줄로 |
| D9 | 낮음 | 확인 | `src/qbt/CLAUDE.md:105` · `:116` · `:148-151` · `:209-213` | 「모든 CSV 로딩은 utils/data_loader」(밖에서 `read_csv` 26곳), 「날짜는 date 객체로 통일」(tqqq 는 Timestamp), 「가격 정밀도 통일」(루트는 입력 6 / 출력 4), 「순차 유리: 워크포워드」(실제는 병렬 그리드), 「즉시 전파」(2-3). → 「데이터 정제」 5줄과 적용 사례 2줄 삭제 |
| D11 | 중간 | 신규 | 루트 `CLAUDE.md:83` | 「`ROUND_PRICE`(중앙 상수, 모든 저장 경로가 경유)」가 거짓이다(`tqqq/simulation.py:692` 직접 `.round(4)`, 포트폴리오 equity 의 미반올림 열). 항상 로드되는 문서라 에이전트가 그대로 믿는다. → 3-6 · 2-5 를 고치기 전에는 「backtest 저장 경로」로 좁힌다 |
| D12 | 중간 | 신규 | `backtest/CLAUDE.md:533-535` (· :192 · :350 · :428 · :643 · `tests/CLAUDE.md:60`) | 「Critical Invariant: pending 이 있는 동안 새 신호면 `PendingOrderConflictError`」는 구조상 도달하지 않는 검사다(6-3). → 「체결일 아침에 비운 뒤 그날 신호를 보므로 신호 시점에 pending 이 남을 수 없다(구조로 보장)」 한 줄로 |
| D13 | 중간 | 신규 | `scripts/CLAUDE.md:43` · `:159` · `backtest/CLAUDE.md:614` | 안내 문서가 사실이 아니거나 미룬 지적의 결함을 설계로 적는다. 「CSV 결과 생성 시 실행 이력 자동 저장」(고원 러너는 저장하지 않는다), 「빈 사유면 allocation」(DEFERRED 11), 「`ledger.csv` 가 있으면 섹션」(DEFERRED 4). → 결정 6 과 DEFERRED 처리 때 함께 고친다 |
| D14 | 낮음 | 신규 | `COMMANDS.md:43` | `execution_comparison` 을 늘 생기는 출력으로 적었는데 `portfolio_qqq_bh` 에는 그 파일이 없다. → 결정 2 에 따라 삭제 또는 「매도가 있을 때」 |
| D15 | 낮음 | 신규 | `src/qbt/CLAUDE.md:18` ↔ `:20` | 같은 절이 「대화형 시각화 대시보드」를 qbt 담당으로 적고 2줄 뒤 「순수 비즈니스 로직만」이라 한다. → 「담당 도메인」 목록 삭제(README 가 정본) |
| D16 | 낮음 | 신규 | `scripts/CLAUDE.md:191` | 「VERBATIM 패턴」의 뜻이 어느 문서에도 없다(코드 주석 16곳의 표식). → 뜻을 한 줄로 적거나 삭제(결정 17) |
| D17 | 낮음 | 신규 | `pytest.ini:8` · `:48-51` · `tests/CLAUDE.md:36` | 주석 「`test_*.py` 또는 `*_test.py`」 ↔ 설정은 `test_*.py` 뿐. 마커 3개는 사용 0건이다. → 주석 수정, 마커 삭제 |
| D18 | 낮음 | 신규 | 루트 `CLAUDE.md:10` | 「별도의 설계 문서가 없습니다」 ↔ `docs/research/Q2_2XS_보완_전략_설계.md`(1,704줄, 0장 세션 인계 · 15장 세션 로그)가 있다. 전역 「진행 상태 · 인계 문서 금지」와도 충돌한다. → 16-B 로 해소 |

기각: 클라우드 보고서 D10(`.claude/plan-config.json` 의 `evidence_home: "docs/"`) — `/impl-plan` 은 그 값으로 폴더만 정하고 문서 · 절은 저장소 규칙이 정한다. 고칠 것이 없다.

### 13-C. 주석 · docstring ↔ 코드

| # | 판정 | 위치 | 내용 |
|---|---|---|---|
| C1 | 확인 | `scripts/backtest/app_parameter_stability.py:181` · `:6` · `:86` | 「거래 5회 미만(예: sell=0.15) 제외」 ↔ QQQ sell=0.15 는 거래 5회라 제외되지 않고 고원 (0.07, 0.15) 안에 칠해진다. 「7자산」 ↔ 6자산. → 예시와 숫자 삭제 |
| C2 | 확인 | `run_portfolio_backtest.py:8-9` · `portfolio_types.py:106` · `195` · `202-203` | 예시 실험 `portfolio_a2` · `c1` · 「G · B 시리즈」가 없다(argparse 가 거부). → 예시 삭제 |
| C3 | 확인 | `run_single_backtest.py:97` · `129` · `163` | 「가격 · MA · 밴드 6자리」 ↔ `ROUND_PRICE` 4. → 숫자를 지우고 상수 이름으로 |
| C4 | 정정 | `app_portfolio_backtest.py:704` | 기여도를 「`run_portfolio_backtest.py` 가 계산」이라 적은 :704 만 틀렸다(실제는 `engines/portfolio_data.py:238-272`). :717 「엔진이」는 맞다 |
| C5 | 확인 (보강) | 포트폴리오 엔진 docstring | `portfolio_execution.py:61-72`(축소 방식) · `:1`, `portfolio_rebalance.py:72-73`, `portfolio_validation.py:110-111`, `portfolio_planning.py:152-153` · `199-200` · `:52`, `portfolio_engine.py:473-478`, `engines/__init__.py`, `portfolio_types.py:3` · `:306-325`(열 명세 누락), 러너 :275-280(저장 파일 목록). → 열 명세와 처리 흐름은 코드의 사본이라 고칠수록 다시 어긋난다. 명세 블록을 줄이고 계약만 남긴다 |
| C6 | 확인 | `src/qbt/backtest/types.py:17` · `:46`, `strategies/__init__.py:8`, `constants.py:31` · `tests/qbt/test_buffer_zone.py:199` | 없는 타입 `BufferStrategyResultDict`, 코드와 반대인 설명, 없는 파일 `overfitting_analysis_report.md` |
| C7 | 확인 (1곳 제외) | `tqqq/constants.py:94`, `analysis_helpers.py:63-64` · `136-137`, `common_constants.py:134`, `parallel_executor.py:51-62` · `:178` | 「영문 토큰」 아래 한글 `COL_*`, 「날짜 범위 포함」(실제는 행 인덱스), 「연간 영업일」 아래 365.25, 없는 호출부 예시. 제외: `parallel_executor.py:168` 「첫 예외만 전파」는 사실이다 |
| C8 | 확인 (스크립트 부분) | `docs/research/late_entry_rally_opportunities.py:6` · `64`, `app_rate_spread_lab.py:1246` | 「EMA200」 ↔ 실제 열은 SMA(같은 파일 :352 는 「SMA200」으로 출력한다). tests 부분은 13-T |
| C9 | 신규 | `scripts/tqqq/app_daily_comparison.py:124-130` · `:137-140` | 「차이 평균이 0 에 가깝고」 ↔ 차트는 절대차라 평균이 0 일 수 없다(0.0949). 「누적수익률 차이」 ↔ 차트는 로그차이 |
| C10 | 신규 | `app_walkforward.py` docstring :13-18 · `:1155`, `app_single_backtest.py:106`, `app_portfolio_backtest.py:1572-1579`, `app_parameter_stability.py:133` · `:136` | 화면 구성을 4섹션으로 적었지만 5섹션이다. 「Path 대신 str」의 이유가 사실이 아니다. 단계 번호 3 이 빠졌다. 6자산 선 위에 QQQ 만으로 고원을 칠하는데 라벨에 기준 자산이 없다 |

### 13-T. 테스트 주석 · docstring ↔ 코드

| 판정 | 위치 | 내용 |
|---|---|---|
| 확인 (보강) | `tests/qbt/test_buffer_zone.py:8` · `11` · `14` · `:65` · `:16` | 「8개 자산 · 8개 설정」 ↔ `CONFIGS` 7개. `:8` · `:11` 은 없는 이름 `create_runner()` 를 쓴다(실제는 `runners.create_buffer_zone_runner`). `:16` 은 4P 숫자를 복사했다 |
| 확인 | `tests/qbt/test_walkforward_selection.py:274-278` | docstring 의 10.0 / 8.0 / 0.8 은 테스트 어디에도 없는 값이다 |
| 확인 (보강) | `tests/qbt/test_analysis.py:816` · `:809` | 평범한 import 라 「fresh import」가 아니다. `:809` 「csv_export → analysis 방향이 자연스럽다」는 단언(서로 import 하지 않음)과 반대 방향이다 |
| 확인 | `tests/CLAUDE.md:152` | `mock_results_dir` 설명이 부분적이고, 그 픽스처의 패치 대부분이 효과가 없다(6-9 ⑥) |
| 신규 | `tests/qbt/test_tqqq_simulation_core.py:30` · `test_tqqq_data_loader.py:47` ↔ `:60` · `test_tqqq_simulation_cost_model.py:205` · `:291` · `test_buffer_zone_execution_rules.py:420` | 문서는 0.95 / 0.5 인데 코드는 0.0095 / 0.006, 같은 파일의 설명 둘이 서로 다름, 열 이름 「FFR」에 퍼센트 값, 사실과 다른 주석 |

## 14. 문서 내용 중 중요하지 않지만 쉽게 변경될 수치 · 리스트

| 판정 | 위치 | 내용 → 제안 |
|---|---|---|
| 확인 (줄 번호 정정) | 루트 `CLAUDE.md:62-63` · `COMMANDS.md:54` · `62` | 날짜 붙은 실측 소요 시간(약 6분 · 76초 · 123초)이 두 문서에 있다. → COMMANDS 한 곳에 범위만. 루트에는 「수 분 걸리는 러너가 있다 — 소요는 COMMANDS, 제한 시간을 늘리거나 백그라운드」 한 줄을 남긴다(루트만 항상 로드되고 그 러너는 Bash 기본 제한을 넘는다) |
| 확인 | `backtest/CLAUDE.md:36` · `38` · `100` · `574` · `611`, `scripts/CLAUDE.md:158`, 루트 `CLAUDE.md:86` | 상수값 복사(0.3% · 0.6% · 1e10 · 200 / 0.03 / 0.05 / 3 · 10,000,000원 · 2005-01-01 · 15,012개 필드). → 상수 이름만 |
| 확인 | `backtest/CLAUDE.md:150` · `157`, `tests/CLAUDE.md:139-140` | 개수(하위 모듈 5개 · 공개 API 2개 · 픽스처 3행 · 25행). → 삭제 |
| 확인 | `scripts/CLAUDE.md:55-64`, `README.md:45`, `COMMANDS.md:236-238`, `src/qbt/CLAUDE.md:177-186`, 루트 디렉토리 트리 | 목록: 메타 타입 10개, 대시보드 5개(실제 `app_*.py` 7개), 대체 티커 10종, 결과 폴더(`wfo_windows_*` · `param_plateau` 누락), 트리. → 정본(코드 상수 · glob)을 가리키는 한 줄 |
| 신규 | `README.md:23-30`, 루트 `CLAUDE.md:20`, `tests/CLAUDE.md:201-204` | 의존성 목록 사본 3곳이고 셋 다 lightweight-charts 가 빠졌다. → README 만 남긴다 |
| 신규 | `supplement_experiment.py:486` · `:735`, `combo_experiment.py:1` · `:112` · `:315`, `portfolio_validation.py:4` · `:475`, `run_portfolio_backtest.py:664` · `:673` | 코드에서 나오는 개수(「계 149」 · 「16칸」 · 「= 152」 · 「7개 규칙」)를 docstring · 로그에 적었다(지금은 모두 맞다). → 수치 삭제, 오류 메시지는 `len(...)` 으로 |
| 신규 | `src/qbt/tqqq/analysis_helpers.py:194` · `203` · `208` · `232` · `tqqq/data_loader.py:327-328` | docstring 에 「2개월」을 4번 적었다(`MAX_FFR_MONTHS_DIFF` 의 복제). → 상수 이름으로 |
| 확인 | `app_rate_spread_lab.py` 화면 문구 | 「2026.02.08 기준」 10줄, 「약 30-60분」(meta 실측 16.3초 · 10.69초와 다르고 없는 스크립트를 안내한다). → 고정 서술 블록 삭제 |
| 판정 변경 | `docs/DEFERRED_FINDINGS.md` 줄 번호 | 어긋난 것은 4개이고, 줄 번호 제거는 `/impl-plan` 항목 형식과 충돌해 채택하지 않는다(17절) |

연구 문서의 수치는 14-R 에 있다.

### 14-R. 연구 문서의 쉽게 변경될 수치

| 판정 | 위치 | 내용 → 제안 |
|---|---|---|
| 확인 | `설계서` | `passed=852` · 폴더 크기 · 실행 시간 · 줄 번호 · 「19종 · 75곳」(지금 33종 · 155토큰). → 지울 문서라 고치지 않고 부록 M 에 옮기지 않을 목록으로만 쓴다(정정: 「14M → 15M」은 단위 차이다) |
| 확인 | `지연` L152 · L688-689 | `signal.csv` 「2026-08-21, 6707행」(지금 09-24 · 6,730행). → 표의 기간 · 행 수 칸 삭제. L688-689 는 거래가 끝날 때 14.4 와 함께 |
| 확인 (제안 일부 기각) | `전략` SOFR L2348 · L2352 · L2366, UBT L2437-2441, 운용 규모 L2513 · L2578, 「테스트 6곳」 L2709, 「5,515행」 L2742 | 삭제는 과하다 — UBT 유동성 · 운용 규모는 Q-2-2XS 선정 근거다. 「현재」 · 「접근 중」 3곳에 「2026-04 기준」만 붙인다. 「5,515행」은 함정의 실측 근거라 유지 |

## 15. 문서 · 주석 내용 중 과거 상태 · 변경 이력 · 계획 단계

### 안내 문서

| 판정 | 위치 | 내용 → 제안 |
|---|---|---|
| 정정 | 루트 `CLAUDE.md:76-92` 반올림 절 | 근거를 `docs/research/` 로 옮기자는 제안은 틀렸다(research 는 전략 연구의 자리이고, 전역 규칙은 「되돌리면 무엇이 깨지는가」를 지우지 말라고 한다). → 제자리에서 줄인다: 「통일했고」 문장, 가정 절차(:90), 표를 반복하는 인용 블록(:92), 「15,012개」 수치 삭제(17줄 → 약 9줄, 추정) |
| 확인 | `backtest/CLAUDE.md:490` · `:111` · `:288` · `:302` | 「제거되었다」 → 「EMA 경로 · `ma_type` 은 없다」로 시제만. 괄호 「기존 결과 열 이름 유지」 삭제. :288 · :302 는 삭제 예정 문서(설계서)를 가리킨다 — 전역 「영구 문서는 임시 문서를 참조하지 않는다」 위반이므로 두 문장 삭제 |
| 정정 | `backtest/CLAUDE.md:240` | 이력이 아니라 「왜 체결 순서를 고정하는가」다. → 지우지 않고 「…돌면 실행마다 결과 파일이 달라진다」로 시제만 |
| 확인 | `src/qbt/tqqq/CLAUDE.md:136` · `:239` | 「(과최적화 검증 완료)」 괄호 삭제(1-5). 「git history 에서 복원」은 삭제 커밋 `c81690b` 한 단어를 넣거나 문장 삭제 |
| 확인 | `scripts/CLAUDE.md:209` · `COMMANDS.md:132`, `src/qbt/CLAUDE.md:95-99`, `tests/CLAUDE.md:171` | 「확정 후 앱만 유지」 → 「결과 열람 전용」. 「지양 접두사」 5줄은 사용 0건이라 삭제. 「기존 안전 장치 … 유지」는 픽스처 설명째 삭제 |

기각: 루트 `CLAUDE.md:60` 「2026-08-30 실측」 — 전역 규칙이 「근거가 된 사건에는 `[실측] 날짜`」를 허용한다. 표기만 맞춘다.

### 코드 주석 · docstring

- **backtest**: `strategies/strategy_common.py:9-10` · `:58`, `backtest_engine.py:316`(「B&H 첫 매수 타이밍 fix」), `walkforward_verdict.py:35`, `walkforward.py:528` · `549`(「(V2)」 — V1 없음), `supplement_experiment.py:243-244`, `run_param_plateau_all.py:47`, `run_walkforward.py:74`(「기존 전략만」), `run_portfolio_backtest.py:616`.
- **포트폴리오 엔진**: `portfolio_engine.py:186` · `413`(「기존」) · `597`(「C안」), `portfolio_methods.py:54`(「C안」), `portfolio_types.py:234`, `portfolio_validation.py:516`, `portfolio_planning.py:257-258`. → 「기존」 · 「C안」 토큰만 지우고 「왜」 문장은 현재형으로 남긴다.
- **tqqq**: `simulation.py:669`, `analysis_helpers.py:306-310`(주석 처리 코드) · `330` · `340` · `355-356`, `tqqq/constants.py:69`. 정정: `simulation.py:676-677` 은 이력이 아니다.
- **scripts**: `app_portfolio_backtest.py` 「신규 섹션」 8곳(:367 · 429 · 569 · 697 · 1351 · 1355 · 1359 · 1363), `app_walkforward.py:82`, `app_rate_spread_lab.py:139-148` · `:225` · `260` · `:1001` · `1014` · VERBATIM 번호 주석(6 · 7번 결번).
- **결정 번호(D○○)**: `supplement_experiment.py` 44회(31줄) · `combo_experiment.py` 23회(14줄) · `portfolio_configs.py` 1 · `run_supplement_grid.py` 3(:244 는 터미널 표 제목). 엔진 · 검사기 · 러너 본체는 0. → **부록 번호로 바꾸지 말고 토큰을 지운다**(대부분 번호 옆에 이유 문장이 이미 있다). 설계서가 지워지면 전부 끊기고 사용자 화면에도 뜻 없는 번호가 나간다. 16-B 와 함께.

tests 의 이력 주석은 15-T, 연구 문서의 이력은 15-R 에 있다.

### 15-R. 연구 문서의 과거 상태 · 이력

연구 보고서는 이력의 정본이다. 결론 · 수치 · 기각 사유 · 폐기 근거는 남기고, 진행 로그 · 세션 인계 · 낡은 「다음 단계」 · 같은 사실의 반복만 지운다.

| 판정 | 위치 | 내용 → 제안 |
|---|---|---|
| 확인 | `설계서` 0장(157줄) · 15장(229줄) · 10장, 「계획서」 190회 · `PLAN_` 38회 · 세션 번호 181회 | 옮기지 않고 삭제(16-B). 0장 · 15장은 전역 「진행 상태 · 인계 문서 금지」에 걸린다 |
| 확인 (2건 정정) | `전략` §2.6 · §11 · §12.1 · §20.5 L1030 · G.6 · G.8.2 · H.9 · K.8 · L.3 L4069 · L.5 L4101 | 지울 것: §2.6 · §11 · §12.1 · 「다음 단계」 절들. 남길 것: §12.2 의사결정 표 · §20.5.2(G.1 근거 3 이 인용) · H.9 의 수치 위치 표 · G.8.1 표. 정정: 「페이퍼 트레이딩」은 3번이 아니라 7곳이다. J.7 은 낡은 이력이 아니다(한계와 해소 포인터). L.3 「검토 중인 보완 전략」은 채택으로 고친다 |
| 확인 | `지연` L58-61 · L83-89 · 9장 · L287-291 · L347-351 · L543-545 | 9장은 2026-08-27 라이브 스냅숏이라 낡았다(지금 스크립트 출력: 경과 160일 · 다음 기회 696.71 이하 / 문서 132일 · 686.40, 휩소 만료 9/27 경과). → 9장은 「현재 값은 스크립트 출력」 3줄로. L58-61 은 기각된 근거의 기록이라 2줄로 줄여 남기고 G.7.4 쪽을 지운다 |

### 15-T. 테스트의 과거 상태 · 이력

- `tests/qbt/test_backtest_engine.py:92` · `107-108` `TestParamsScheduleWhile`(「if 로직에선 실패, while 로 바꾼 뒤 통과」): 테스트는 프로덕션 경로를 지키므로 남기고 이름과 두 줄만 고친다.
- `test_analysis.py:829`(「과거에는 … 무음 반환되었으나」), `test_portfolio_backtest_scenarios.py:1105-1106`(「이전에는 앱이 직접 계산했으나」).
- `NewAssetState`: 8곳이 아니라 15줄이다(`as NewAssetState` 별칭 import 7 + 사용 8, 전부 `test_portfolio_planning.py`). → `portfolio_types.AssetState` 를 상단에서 한 번 import(10절과 함께).
- 「기존 ~」 이력 문구 15줄: 클라우드 보고서의 9곳(`test_walkforward_schedule.py:264` · `270`, `test_walkforward_selection.py:208` · `235`, `test_portfolio_backtest_scenarios.py:764` · `805`, `test_tqqq_simulation_cost_model.py:547` · `559`, `test_tqqq_simulation_core.py:465`) + `test_tqqq_simulation_cost_model.py:551` · `test_walkforward_selection.py:212` · `test_walkforward_schedule.py:274` · `test_tqqq_simulation_core.py:430` · `test_parameter_stability.py:297` · `test_walkforward_windows.py:161`.
- `test_walkforward_verdict.py:66` · `408-409` 「과거 사고」: 내용은 같은 파일 머리말 :3-6 에 있다(불명이 아니다). 한 줄로 줄인다. 그 계약을 지금 테스트가 못 지키는 것은 2-26.
- 그 밖: 「새 / 이전 인터페이스」(`test_strategy_interface.py:3` · `46` · `51` · `249` · `254` · `363`), 「(정책 변경)」 · 「버그 재현」 · 주석 처리 코드(`test_buffer_zone_execution_rules.py:123` · `162` · `170` · `172` · `699-702` · `718-719`), 「(리포트 …)」(`test_buffer_zone.py:265` · `331`, `test_engine_common.py:173`), EMA 잔재(`test_walkforward_schedule.py:72` · `162` · `165`, `test_portfolio_backtest_scenarios.py:35` · `872` · `877`, `test_buffer_zone_run.py:77`), `test_portfolio_backtest_scenarios.py:954` · `test_portfolio_execution.py:262` · `test_csv_export.py:9-10` · `test_walkforward_summary.py:93`(「V2」) · `test_portfolio_strategy_types.py:23-26`.
- 결정 번호(D○○): 4파일 54줄(`test_combo_experiment.py` 16 · `test_supplement_experiment.py` 31 · `test_portfolio_methods.py` 5 · `test_portfolio_configs.py` 2). → 16-B 와 함께 토큰 삭제.

## 16. 계획서 정리

### 16-A. `docs/plans/` 10개

**결론: 문서 오류 4건만 고치면 10개 모두 정보 손실 없이 지울 수 있다.**

- 10개 모두 Done 이고 미체크 `[ ]` 는 0 이다(메인 세션 집계). 계획서를 가리키는 `.py` · 안내 문서 · 연구 보고서는 0건이다. `DEFERRED_FINDINGS.md` 14줄은 평문 출처라 깨지지 않고, 설계서 29줄은 임시 → 임시 참조다.
- 지우기 전에 고칠 4건은 계획서와 이 임시 보고서에만 적혀 있다: 13-B 의 D4 · D5 · D6 · D14.
- `docs/plans/.gitkeep` 은 남긴다(계획서 게이트 훅이 폴더 존재로 동작한다).
- 단서: 계획서의 근거 승격 목적지가 설계서(임시)다. 계획서 삭제는 안전하지만 설계서 삭제는 16-B 를 거친 뒤에만 안전하다.
- 시점은 결정 12 다(설계서 D54 는 「부록 M → 참조 정리 → 설계서 · 계획서 삭제」 순서를 정했다).

| 계획서 | 줄 | 계획서에만 있는 정보 | 지우기 전 할 일 |
|---|---|---|---|
| `PLAN_rebalance_month_end` | 298 | 없음(보고서 부록 L) | 없음 |
| `PLAN_rebalance_entering_exclusion` | 273 | 없음(보고서 :4100-4124) | 없음 |
| `PLAN_multi_method_engine` | 375 | 가치 낮은 실측 2건(규칙 6 오차 5.96e-08, 상계 주수 정정 — 대상 실험은 삭제됨) | 없음 |
| `PLAN_supplement_data_proxy` | 325 | 이음매 스케일 4개(재생성하면 다시 나온다) | 없음 |
| `PLAN_supplement_allocators` | 324 | 없음(설계서 D44 · 7.6) | 없음 |
| `PLAN_supplement_grid_judgment` | 403 | 없음(설계서 D45 – D50 · 9.5) | 없음 |
| `PLAN_long_proxy_comparison` | 398 | 없음(설계서 D58 – D61 · 8.4) | 없음 |
| `PLAN_combo_grid` | 297 | 받아들인 한계 1건(대체 판 확인이 CSV 저장 전에 돌아 기간 대조에 걸리면 판정 CSV 도 저장되지 않는다 — 멈추는 쪽) | 없음(`/impl-plan`: 받아들인 것은 옮기지 않는다) |
| `PLAN_supplement_registration` | 224 | 문서 오류 2건(D6 · D4) | D6 · D4 수정 |
| `PLAN_portfolio_lineup_cleanup` | 218 | 문서 오류 2건(D5 · D14), 결정 1건(「`state_log.csv` 는 계속 저장 — 연구 기록이 근거로 써 왔다」) | D5 · D14 수정. `state_log.csv` 유지 이유는 필요하면 러너 저장부 주석 한 줄 |

### 16-B. 설계서(`Q2_2XS_보완_전략_설계.md`, 1,704줄) 처리

설계서는 스스로 「설계서 + 진행 기록」을 표방하는 작업 문서다. 원래 계획(D53 · D54)은 결론을 `전략_검증_보고서.md` 부록 M 으로 옮긴 뒤 이 문서와 계획서를 지우는 것이고, **채택 결론(Q-2-2XS 80% + HAA 10% + 로테이션 10%)은 아직 영구 보고서에 없다**(보고서의 HAA 언급은 L.3 「검토 중인」 · L.5 둘뿐). 그래서 부록 M 전에는 지울 수 없다.

1. **부록 M(약 200줄)을 먼저 쓴다.** 결론(D75 수치는 CSV 와 일치: 이어 붙인 판 14.03 / −22.77 / 0.6165, 완전 실물판 15.06 / −22.77 / 0.6617) · 판정에서 떨어진 사실(D70) · 금 · EWY 를 뺀 이유(D51 · D74) · 국면 정의 · 후보 규칙 · 판과 판정 기준을 문장으로 · 대용 · 대체의 한계 · 뺀 후보와 사유 · 남은 질문(R7 포함). 결과는 핵심 표 4개만 싣고 CSV 경로를 가리킨다(9.5 · 9.6 · 8.4 의 CSV 사본 243줄은 옮기지 않는다).
2. **엔진 결정의 「왜 · 탈락안」**은 부록 M 한 절에 8행 표로 둔다(D16 · D17 · D18 · D29 · D33 · D34 ① · D35 · D37). 리밸런싱 결정은 부록 L 이 이미 담는다.
3. **가드의 한계**(체결일 하루 −30% · −55% 급락과 소액 계좌 정수 주에서 정상 결과도 검사기가 멈춘다 — 설계서 L179 · L678 에만 있다)는 `portfolio_validation.py` 허용 오차 상수 주석 2줄로.
4. **`state_log.csv` 를 계속 저장하는 이유**(부록 L.5 가 근거물로 쓴다 — `PLAN_portfolio_lineup_cleanup` 에만 있다)는 러너 저장 지점 주석 1줄로.
5. **옮기지 않는 것**: 0장 · 15장 · 10장, 6장 표 원문, 5장 예비 표(필요한 수치만 「예비 · 코드 미보존」 표시), CSV 사본, 실행 시간 · 폴더 크기 · 줄 번호 · 참조 개수, 체결 전후 표의 사유 표시(결정 2).
6. **결정 번호 정리**: `.py` 155토큰 · 102줄 · 8파일(고유 33종)과 `.md` 14토큰(계획서 · 설계서 제외)은 번호를 절 참조로 바꾸지 말고 **토큰을 지운다** — 번호가 이유 문장 뒤의 괄호 꼬리표다. 다시 써야 할 줄은 약 6개(`supplement_experiment.py:763` · `run_supplement_grid.py:244` 터미널 표 제목 · 테스트 4줄), 「부록 M」으로 바꿀 파일 단위 포인터 6곳(모듈 docstring 3 · `portfolio_configs.py:157` · `backtest/CLAUDE.md:288` · `302`).
7. **순서**: 부록 M → R7 반영 → 주석 2곳(3 · 4) → 번호 정리 → `grep -rnE 'D[0-9]+|설계서'` 로 0 확인 → 설계서 삭제 → 계획서 10개 삭제(결정 12) → 이 보고서 삭제.

## 17. DEFERRED_FINDINGS.md 13건 — 재현 결과와 추천

`/impl-plan` 「미룬 지적 옮기기」의 「처리」 1 · 2단계(재현 → 표)까지 했다. **3단계(고르기)는 사용자 몫이다.** 추천은 **고친다 8건(2 · 3 · 4 · 6 · 8 · 10 · 11 · 13) · 버린다 5건(1 · 5 · 7 · 9 · 12)** 이다.

- 판정 기준은 `review.md` 다. 닿는 버그는 고치고, 닿지 않는 버그와 「그 외」는 버린다. 무거운 결함을 막는 검사가 비어 있으면 앞으로의 잘못된 변경을 계기로 보고 고친다.
- 클라우드 보고서(고침 6 · 버림 7)와 갈린 것은 2 · 8 이다. 둘 다 결함을 일부러 넣어 보니 테스트 857개와 정합성 검사기가 하나도 잡지 못했다.
- 「엔진은 고치지 않는다」(설계서 D27)는 보완 전략 실험 기간의 진행 방식 결정이었고 실험은 끝났다. 고칠 때 걸리는 제약이 아니다. 추천한 수정 8건은 모두 지금 결과 수치를 바꾸지 않는다.
- 용어: **정합성 검사기** = 포트폴리오 실행 직후 결과가 규칙을 지켰는지 대조하는 `portfolio_validation.py`. **상계** = 같은 날 한 매매법이 팔고 다른 매매법이 산 같은 종목을 차이만 체결해 비용을 아끼는 것. **매매법** = 한 실험 안의 독립 장부 단위.

| # | 항목 | 재현 | 지금 산출물 | 닿는가 | 무게 | 고치는 범위 | 추천 |
|---|---|---|---|---|---|---|---|
| 1 | 검사기가 엔진이 «안 한» 일을 못 본다(규칙 1 · 2 · 7) | 재현됨. 모든 매수 0주 결함에 5개 실험이 「위반 0 · 거래 0 · 최종 자본 10,000,000」 | 0 | 닿지 않음. 계기는 엔진 코드 변경뿐이고, 엔진 결함 변형 6종을 기존 테스트가 모두 잡는다(실패 37 · 14 · 5 · 3 · 2 · 5개) | 무거움 | 엔진이 0주 사유를 기록하거나 검사기가 엔진 로직을 복제해야 한다(수십 줄, 추정) | 버린다 |
| 2 | 매매법 장부의 cash · cost · target_share 를 대조하는 검사가 없다 | 재현됨. cash · target_share 결함은 테스트가 잡는다(5 · 3개 실패). **cost 를 두 배로 기록하는 결함은 테스트 0 · 검사기 0** | 0 | cost 만 검사 보강 규칙 대상(막는 검사가 하나도 없다 — 메인 세션이 테스트 grep 으로 확인) | cost 는 무거움(틀린 「장부 비용」이 `summary.json` 과 대시보드에 나간다) | 테스트 1개(cost = Σ\|Δ주수\| × 시가 × 비용률). 운영 코드 변경 없음 | 고친다 (cost 테스트만) |
| 3 | 같은 매매 데이터를 매매법마다 다른 자산 id 로 들면 상계가 빠진다 | 재현됨. 금 매매법 id 만 `gld` → `gold` 로 바꾸면 검증 · 검사기를 통과하고 상계 2행 · 절감 487.84원이 사라진다(145,665,822.82 → 145,665,334.98) | 0 / 설정 306개 | 닿는다(설정 — 자산 id 는 사용자가 붙이는 이름) | 가벼움 | `validate_portfolio_config` 에 경로 → id 역방향 검사 약 5줄. **매매법을 가로지를 때만** 검사한다(한 매매법 안의 같은 경로 · 다른 id 는 기존 테스트가 쓰는 정당한 모양). 테스트 1개 수정 + 1개 추가 | 고친다 |
| 4 | 같은 결과 폴더에 다시 저장하면 이전 실행의 파일이 남는다 | 재현됨, 범위가 더 넓다. 낡은 파일 17 – 18개(ledger · netting · execution_comparison · signal 15개), 대시보드 시그널 선택지 19개 중 15개가 실험에 없는 자산 | 0 | 닿는다(설정 — 등록 실험의 구성을 이름은 그대로 두고 바꾸는 것, 선례 `3e9e268`) | 무거움(무관한 매매법 손익이 그 실험의 수치로 보인다) | 러너가 저장 전에 자기가 만드는 파일 패턴만 지운다(2 – 3줄). `shutil.rmtree` 는 쓰지 않는다(실험 이름이 빈 문자열이면 결과 폴더 전체를 지운다) | 고친다 |
| 5 | 배분 비중을 float 로 정확히 비교한다 | 재현됨(2.8e-16 차이에 조정 의도 2건) | 0 — 등록 배분 규칙 3종의 비중은 0 · 0.25 · 0.5 · 0.75 · 1.0 뿐 | 닿지 않음(연속값 비중을 내는 새 규칙 코드가 있어야 한다) | 가벼움 | `math.isclose` 1줄 | 버린다 |
| 6 | 「체결 전후 비교」 표가 매수만 있는 체결일을 빠뜨리고 사유를 그날 계좌 사유 하나로 붙인다 | 재현됨, 악화. 매수 진입 체결일 중 표에 나오는 날: D-1 0 / 12 · Q-2 0 / 21 · Q-2-2XS 0 / 20 · 조합 138 / 158. 조합에서 배분 규칙 진입 · 청산 94행이 「월초 정기」, 31행이 「매매법 사이 비중」. QQQ B&H 는 CSV 가 없고 재실행해도 안 생긴다 | **발생 중** | 닿는다 | 가벼움(표시만) | 고치는 안: 체결일을 `_shares` 변화일로(3 – 4줄) + 자산별 사유(10 – 15줄, 추정). CSV 형식은 그대로. 삭제 안: 러너 약 128줄 · 앱 77줄 · 결과 CSV 4개 · 문서 설명 | 고친다 — **결정 2**(삭제 안 권고) |
| 7 | EWY 배분 규칙의 매수 기록에 `hold_days_used` 가 0 으로 남는다 | 재현됨 | 0 — EWY 규칙을 쓰는 등록 실험 0, 그 열을 읽는 코드 0 | 닿지 않음(EWY 는 탈락, 결론에서도 뺐다) | 가벼움 | 배분 규칙 인터페이스 변경 | 버린다 |
| 8 | HAA 배분 규칙이 입력 시세의 거래일 정렬을 확인하지 않는다 | 재현됨(합성). 한 시세가 하루 어긋나면 예외 없이 점수가 0.0078 → −0.0237. 같은 어긋남에 로테이션 규칙은 ValueError | 0 | 검사 보강 규칙 적용. 엔진의 공통 거래일 자르기를 바꾸는 변경을 흉내 내면 예외 없음 · 검사기 위반 0 · 테스트 857개 통과인데 Calmar 가 0.5812 → 0.5860 | 무거움(틀린 순위가 에러 없이) | HAA 첫 호출에 로테이션과 같은 날짜 대조 3 – 4줄. 로테이션의 대조를 공통 함수로 옮기면 중복이 없다. 테스트 1개 | 고친다 |
| 9 | 배분 규칙 생성자가 이동평균 기간 · 버퍼 · 유지일을 검증하지 않는다 | 재현됨 | 0 | 닿지 않음(EWY 재등록과 상수 오기가 겹쳐야 한다. 상수를 잘못 바꾸면 테스트가 잡는다) | 가벼움 | 3줄. 5-2 를 `BufferZoneStrategy.__init__` 으로 풀면 덤으로 풀린다 | 버린다 |
| 10 | 등록 실험의 실제 시작일을 `min_start_date` 와 대조하지 않는다 | 재현됨. TIP 의 2006-10-02 행 하나만 빼면 러너가 예외 없이 2007-06-25 부터 돈다 | 0 — 여유 0일(유효 시작일 = `min_start_date` = 2007-06-22) | 닿는다(데이터 재수집) | 가벼움 | 러너에서 `run_with_start_check(config, config.min_start_date)` 2 – 3줄. 러너가 계산한 시작일을 넘기면 잡지 못한다 | 고친다 |
| 11 | 배분 조정 사유를 「리밸런싱한 날 + 빈 사유」로 추론한다 | 재현됨. HAA 가 비중만 조정한 17일 중 4일(2009-02-02 · 2012-06-01 · 2020-03-02 · 2022-04-01)이 「월초 정기」로 보인다 | 4일 발생 중 | 닿는다 | 가벼움(표시만) | 엔진 변경 불필요(장부에 매매법별 사유가 있다). 에쿼티 차트 마커 hover 를 장부 사유로(앱 6 – 8줄), 러너의 추론 2줄 삭제 | 고친다 (6 과 묶음. 설계서 D40 이 받아들인 모양이라 사용자 확인 필요) |
| 12 | 신호 일치율이 배분 규칙의 판단 보류 달을 판단으로 센다 | 부분. 적힌 계기(PDBC 첫 행이 한 달 늦음)를 흉내 내면 시작일 대조에서 ValueError 로 멈춘다 | 0 | 닿지 않음 | 가벼움 | 2 – 3줄 | 버린다 |
| 13 | 대체-실물 비교의 「상장 전 교차 확인」 쌍이 실제로 상장 전까지만 잘리는지 강제하지 않는다 | 재현됨. 넷째 칸이 None 이면 예외 없이 전 구간을 재고 상관이 높게 나온다(VEIEX↔EEM 0.7712 → 0.9368) | 0 — 3쌍 모두 실제로 잘린다 | 닿는다(`PAIRS` 에 쌍을 더할 때 한 칸을 빠뜨리는 것. `PAIRS` 를 보는 테스트 0) | 무거움(대체 시세 품질을 실제보다 좋게 보인다) | `align_closes` 에서 before 가 아무 행도 자르지 않으면 ValueError 2줄 + `main` 확인 2줄. 테스트 1 – 2개 | 고친다 |

**DEFERRED 본문에서 낡았거나 틀린 서술** (고를 때 참고)

- 1: 「1,619일 중 113일 · 62회 중 61회」는 지금 등록 실험으로 재현할 수 없다. 지금 채택 조합에서 놓치는 날은 판정이 넘은 195일 중 4일이다.
- 2 · 4 · 8: 본문은 「가벼운 버그」로 적었지만 틀린 금액 · 순위가 에러 없이 나가는 모양이라 무거움이다.
- 2: 「cost 는 재계산 불가」(클라우드 보고서)는 틀렸다. 상태 로그로 다시 계산하면 5개 실험 모두 장부와 차이 0 이다.
- 6: 「고치려면 `execution_comparison.csv` 형식을 바꿔야 한다」는 틀렸다(`rebalance_reason` 열이 이미 행마다 있다). 매수 진입일 표시 수치는 지금 0 이다.
- 11: 「근원 수정은 엔진 변경」은 틀렸다.
- 12: 「PDBC 가 한 달만 늦어도 첫 달이 0 비중」은 틀렸다(시작일 대조가 먼저 멈춘다).
- 자리(줄 번호)가 어긋난 항목은 3 · 4 · 6 · 12 넷이고 모두 함수 이름으로 찾아진다.

**DEFERRED_FINDINGS.md 파일 자체**

- 클라우드 보고서의 「줄 번호 빼기 · 실측과 계획서 이름 빼기 · 3 – 5줄로 축약」은 받아들이지 않는다. `review.md` 의 항목 형식(자리 = `파일:줄` + 함수 이름 · 재현할 수 있는 수준 · 출처 = 계획서 이름과 날짜)과 부딪힌다.
- 받아들일 것은 하나다: 본문의 결정 번호(D27 · D40 등)는 설계서가 지워지면 뜻을 잃으므로 이유 문장으로 바꾼다.
- 파일을 줄이는 길은 버린 항목을 바로 지우고, 고친 항목을 그 계획서가 Done 될 때 지우는 것이다.

**계획서 묶음 제안**

- **A. 포트폴리오 러너 · 대시보드**: DEFERRED 4 · 6 · 10 · 11 + 감사 1-2 · 1-4 · 1-12 · 2-5 · 2-17 · 3-8 · 6-8 · 9-9.
- **B. 설정 · 전략 파라미터 검증 한 곳**: DEFERRED 3 (+ 9 가 덤으로) + 감사 5-2 · 5-5 · 9-6 · 9-10 · 2-11.
- **C. 정합성 검사기**: DEFERRED 2 + 감사 7-4 · 7-10 · 9-2.
- **단독**: 8(같은 파일의 3-11 · 3-19 와 함께), 13(같은 모듈의 5-6 · 6-14 와 함께).

## 18. 문서 중복 · 경량화 (요청 #2 · #3)

### 18-A. 사실별 정본

| 사실 | 정본 | 나머지 문서 |
|---|---|---|
| 실행 명령 · 선행 순서 · 출력 폴더 · 소요 범위 | `docs/COMMANDS.md` | README · CLAUDE.md 는 가리키기만. 루트에는 「수 분 걸리는 러너가 있다」 한 줄만 |
| CLI 인자 선택지 | argparse(`--help`) | COMMANDS · `scripts/CLAUDE.md` 의 선택지와 CONFIGS 포인터 삭제 |
| 데이터 갱신 뒤 재생성 순서 · 받아야 할 원본 | COMMANDS 의 블록 하나(13-B D4) | 스크립트 docstring 과 `scripts/CLAUDE.md:131` 의 「다시 받으면」 삭제 |
| AI 실행 규칙 · 반올림 규칙 | 루트 `CLAUDE.md` — 규칙과 「되돌리면 무엇이 깨지는가」를 함께 | `scripts/CLAUDE.md:131` · `tests/CLAUDE.md:197` · `src/qbt/CLAUDE.md:213` 삭제 |
| 함수 · 필드 · 시그니처 · 정합성 규칙 목록 | 코드 docstring | 도메인 CLAUDE.md 는 모듈당 한 줄 지도 + docstring 에 없는 「왜」 |
| 도메인 불변조건(체결 타이밍 · 유지일 · SMA · 비용 · 리밸런싱) | `src/qbt/backtest/CLAUDE.md` 「도메인 규칙」 | tests · COMMANDS 에서 삭제. README 는 기능 한 줄 |
| 대시보드 동작 | 각 `app_*.py` docstring | `scripts/CLAUDE.md` 앱당 한 줄. `backtest/CLAUDE.md` 의 대시보드 절은 삭제 |
| vendor 포크 빌드 | `vendor/streamlit-lightweight-charts-v5/CLAUDE.md` | `backtest/CLAUDE.md:619-632` 삭제 |
| 계층 · 병렬 · 상수 배치 | `src/qbt/CLAUDE.md` | 예외 · ERROR 로그는 전역 `python.md`. utils · tests 는 가리키기만 |
| 프로젝트 소개 · 기술 스택 | `README.md` | 루트 개요 · `src/qbt/CLAUDE.md` 「담당 도메인」 삭제 |
| 결과 · 데이터 경로 | `common_constants.py` | `storage/stock` 파일명 규칙만 `src/qbt/CLAUDE.md` |
| 테스트 허용오차 · QBT 픽스처 함정 | `tests/CLAUDE.md` | conftest docstring 사본 삭제 |
| 이력 · 설계 결정의 자리 | 루트 `CLAUDE.md:10` | `docs/CLAUDE.md:12` 는 포인터 |
| 현재 성과 수치 | `storage/results/**/summary.json` | 연구 문서는 「작성 시점 값」임을 밝히고 기준일을 적는다 |
| 미룬 지적 | `docs/DEFERRED_FINDINGS.md` | 안내 문서는 그 결함을 「설계」로 적지 않는다(13-B D13) |

### 18-B. 안내 문서 중복 (같은 사실이 2곳 이상)

| # | 사실 | 위치 | 정본 |
|---|---|---|---|
| B1 | 정합성 규칙 목록(이미 서로 다르다 — README 는 6종) | `README.md:50` · `COMMANDS.md:44` · `backtest/CLAUDE.md:143` · `portfolio_validation.py:6-14` | docstring |
| B2 | 보완 · 조합 그리드 설명 | `README.md:39-40` · `COMMANDS.md:50-63` · `src/qbt/CLAUDE.md:192-198` · `scripts/CLAUDE.md:161-169` · `backtest/CLAUDE.md:286-308` · 모듈 docstring | 모듈 docstring(내용) + COMMANDS(명령 · 출력 폴더) |
| B3 | 「원본을 다시 받으면 다시 실행」 5곳 | `COMMANDS.md:228` · `243` · `scripts/CLAUDE.md:131` · 생성 스크립트 docstring 2곳 | COMMANDS 순서 블록 |
| B4 | 대시보드 동작(틀린 문장이 함께 복제됨), 「보유중」 마커 4곳 | `backtest/CLAUDE.md:556` · `579-633` · `scripts/CLAUDE.md:174-198` · `COMMANDS.md:81-94` | 앱 docstring |
| B5 | 반올림 규칙 | 루트 `CLAUDE.md:76-92` · `scripts/CLAUDE.md:131` · `tests/CLAUDE.md:197` · `src/qbt/CLAUDE.md:213`(루트와 뜻이 반대) · `test_rounding_policy.py:1-11` | 루트 + `ROUND_*` 상수 |
| B6 | FFR · 운용비율 날짜 형식 6곳 | `tqqq/CLAUDE.md:50` · `162` · `167` · `tests/CLAUDE.md:143` · `148` · `185-193` · `conftest.py:57` · `72` | `tqqq/CLAUDE.md` 「데이터 요구사항」 |
| B7 | 병렬 처리 규칙 | `src/qbt/CLAUDE.md:109-117` · `131-151` · `utils/CLAUDE.md:39-45` · `scripts/CLAUDE.md:106-109` | `src/qbt/CLAUDE.md` 「병렬 처리」 |
| B8 | 예외 · ERROR 로그 계층 | `src/qbt/CLAUDE.md:51-52` · `116-117` · `scripts/CLAUDE.md:68-80` ↔ `:218-227`(같은 문서 안 반복) · `utils/CLAUDE.md:31-37` | 전역 `python.md` + `scripts/CLAUDE.md` 2 – 3줄 |
| B9 | utils 기능 · 메타데이터 설명 | `src/qbt/CLAUDE.md:103-107` · `173-176` · `utils/CLAUDE.md:23-29` · `62-69` · `scripts/CLAUDE.md:41-67` | 결정 6 에 따른다(지우면 문서 44줄이 함께 사라진다) |
| B10 | docstring 복제 | `backtest/CLAUDE.md:314-316` · `:434-444` · `:233-247` · `:454-458` · `:421-430` | docstring |
| B11 | SMA 채택 근거 4항목 | `backtest/CLAUDE.md:493-506` ↔ `전략_검증_보고서.md` 부록 G | 규칙(SMA 고정 · 재도입 방지 테스트)만 남기고 근거는 부록 G 포인터 |
| B12 | 테스트 범위 목록 | `backtest/CLAUDE.md:640-651` · `tqqq/CLAUDE.md:248-254` · `tests/CLAUDE.md:50-77` | `tests/CLAUDE.md` |
| B13 | 실행 예시가 docstring 에 | 스크립트 19 / 19개 · 42줄의 `poetry run`(`run_portfolio_backtest.py:8-9` 는 없는 실험명), `backtest/CLAUDE.md:627-632`(npm 빌드) | 최소한 틀린 예시 2줄 삭제. npm 빌드는 vendor 문서 |
| B14 | 리밸런싱 정책 5곳 | `README.md:38` · `COMMANDS.md:42` · `backtest/CLAUDE.md:107` · `215` · `238` · `243` · `portfolio_engine.py` docstring | `backtest/CLAUDE.md` 도메인 규칙 한 곳(:243) |
| B15 | 개요 · 디렉토리 트리 · 이력 위치 규칙 | 개요(`README.md:3` · `23-31` ↔ 루트 `:14-22` ↔ `src/qbt/CLAUDE.md:9-20`), 트리(루트 · `src/qbt/CLAUDE.md:26-35` · `tests/CLAUDE.md:18-24`), 이력 규칙(루트 `:10` ↔ `docs/CLAUDE.md:12` · `18`) | README(개요) · 루트(이력 규칙) |
| B16 | QQQ 벤치마크 공유 정책 | `scripts/CLAUDE.md:160` ↔ `run_portfolio_backtest.py:631-635` | 1-2 를 고치면 사라진다 |
| B18 | 같은 앱 설명 두 벌 | `tqqq/CLAUDE.md:226-241` ↔ `scripts/CLAUDE.md:200-213`(「단일 흐름: 오차분석 → 튜닝 → 과최적화진단 → 상세분석」이 글자까지 같다) | tqqq 쪽 16줄 삭제 |
| B19 | 그 문서가 실린 뒤에야 보이는 지시 | 「작업 전에 이 문서를 반드시 읽어야」 3곳(`src/qbt/CLAUDE.md:3` · `scripts/CLAUDE.md:3` · `tests/CLAUDE.md:3`), 「루트 참고」 7곳 | 10줄 삭제(하위 CLAUDE.md 는 그 폴더 파일을 열 때 실리고 루트는 항상 로드된다) |
| B20 | 어느 CLI 프로젝트에나 맞는 일반론 | `scripts/CLAUDE.md:15-39` · `84-121`(63줄, 「로그 레벨 설정 · 환경 변수 처리」는 코드에 0건) | 4줄(모듈 레벨 logger · `@cli_exception_handler` · `__main__` 보호 · 계산은 src)만 |

이전 판 B17(전역 규칙을 다시 적은 곳)은 20절.

### 18-C. 연구 보고서 중복

| # | 판정 | 사실 | 위치 → 정본 |
|---|---|---|---|
| R-B1 | 확인 | EMA→SMA 상관 변화 표 | `상관` 1장(L51-56) = `전략` G.7.1(L2751-2756) → 상관 1장. G.7.1 은 3줄 + 링크 |
| R-B2 | 확인 | 지연진입 근거가 바뀐 경위 | `지연` 1장 · 7장 · 9장 + `전략` G.7.4 · H.7 → 지연. G.7.4 는 3줄 |
| R-B3 | 확인 (더 많다) | Q-2-2XS 성과가 세 벌이 아니라 여섯 벌(16.12 · 16.42 · 16.23 · 15.43 / −27.56 / 0.560 · 15.40 / −27.56 / 0.56 · 15.43 / −27.93 / 0.55 — 마지막이 지금 `summary.json`) | 「기준(이동평균 · 데이터 끝 · 리밸런싱 규칙) → 값」 표 하나를 L.8 에 두고 해명 주석은 그 표를 가리킨다 |
| R-B4 | 확인 (제안 수정) | 「[구 규칙]」 알림 9곳 | 표 하나로 모으면 읽는 자리에서 경고가 사라진다. 포인터 한 줄은 남기고, 규칙 · 수치를 다시 적은 3곳(`전략` L1713 · L2567, `상관` L131)만 줄인다 |
| R-B5 | 확인 | 세금 비교 | `전략` §46.3 ≈ 부록 F, `설계서` 5.9 → 부록 F |
| R-B6 | 확인 | `전략` Part 1 내부 반복 5쌍(§2.3 = §19.1 = A.3, §2.4 = §19.1 + §19.2, §2.5 = §20.3 = §21.1 = C.3 등) | §19 · §20 |
| R-B7 | 확인 | Part 2 「교정의 연대기」 4번, §32.1 ⊃ §38.1 · §39.1 · D.1 – D.7 | §32.1 에 「제거 사유」 열 → D.1 – D.7 57줄 · 부록 E 22줄 삭제. §30.2 는 유지 |
| R-B8 | 확인 | 엔진 · 리밸런싱 규칙 | 현재 규칙은 `backtest/CLAUDE.md`, 변경 근거는 부록 L.2 |
| R-B9 | 확인 (효과 작음) | 용어 정의(J.4 ≡ K.4, 밴드 산식 3곳) | 용어집 신설은 과하다. K.4 는 「J.4 와 같다」, 산식은 `backtest/CLAUDE.md` 를 가리킨다(약 −11줄) |

### 18-D. 안내 문서 경량화안

「뒤」는 구간 줄 수를 세어 낸 추정이다.

| 문서 | 지금 | 이 문서가 정본인 것 | 지울 것 | 뒤(추정) |
|---|---|---|---|---|
| 루트 `CLAUDE.md` | 92 | 계획서 규약의 저장소 값 · AI 스크립트 실행 규칙 · 반올림 정책 | 개요(:14-22), 트리 하위 설명, 소요 시간의 날짜 · 초, 반올림 절의 반복 | 약 62 |
| `README.md` | 57 | 사람용 소개 · 기술 스택 | 대시보드 나열, 워크포워드 설명 중복(:42 ↔ :49), 정합성 규칙 나열 | 약 55 |
| `docs/COMMANDS.md` | 258 | 실행 명령의 유일한 자리 + 갱신 순서 | 커버리지 절 중복, 「시각화:」 주석, 도메인 설명 주석, 선택지 포인터(약 24줄). 순서 블록 약 14줄 추가 | 약 248 |
| `docs/CLAUDE.md` | 23 | 문서 보관 정책 · research 파일명 규칙 · `plans/` 유지 | 머리말 1줄 | 약 22 |
| `docs/MEMORY.md` | 12 | 「용어는 풀어서」 한 규칙 | 없음 | 12 |
| `src/qbt/CLAUDE.md` | 222 | 계층 · 상수 3계층 · 병렬 기준 · `storage/stock` 파일명 규칙 | 결과 위치 목록(:173-207), 상수 예시, 지양 접두사, 「담당 도메인」, 데이터 정제, 테이블 출력 | 약 133 |
| `src/qbt/backtest/CLAUDE.md` | 651 | 도메인 불변조건 + 엔진의 「왜」 | 모듈 카탈로그(:13-474) → 지도, 대시보드 절(55줄), vendor 절(14줄), 테스트 범위, SMA 근거 4항, 설계서 참조 2곳 | 약 180 |
| `src/qbt/tqqq/CLAUDE.md` | 254 | 비용식 · 로그차이 정의 · 금리 · 운용비율 형식 | 모듈 구성(:14-110), CSV 형식, 앱 설명, 테스트 범위 | 약 127 |
| `src/qbt/utils/CLAUDE.md` | 106 | 모듈당 한 줄 + 보간 금지 · 이음매 규칙 | 함수 나열(:14-89), 메타 절, 제약사항 절 | 약 33 |
| `scripts/CLAUDE.md` | 262 | CLI 계층 규칙 + 앱 · 러너당 한 줄 | 일반론 63줄, 메타 절, 러너 · 앱 상세(:123-213), 인자 예외 절 | 약 60 |
| `tests/CLAUDE.md` | 204 | QBT 필수 테스트 대상 · 허용오차 표 · `yyyy-mm` 문자열 함정 | 픽스처 절(:135-173), 병렬 파라미터 표, pytest 설정 절(문서 중간 H1 포함), 플러그인 | 약 107 |
| **합계** | **2,141** | | | **약 1,040** |

`backtest/CLAUDE.md` 와 `scripts/CLAUDE.md` 의 카탈로그 · 대시보드 절 · 러너 상세는 **고치지 말고 지운다.** 13-B 의 오류 20여 곳이 전부 코드 사본에서 났다.

### 18-D-R. 연구 문서 경량화안

| 문서 | 지금 | 남길 것(이력의 정본으로서) | 지울 것 | 뒤(추정) |
|---|---|---|---|---|
| `전략_검증_보고서.md` | 4,142 | 결론과 기각 사유 전부. §12.2 의사결정 표 · §20.5.2 · 부록 A · C · D.8 · G.1 – G.4 · G.7.2 · G.8.1 표 · 부록 H · I · J.5 · **K.5 전체**(계산 코드가 저장소에 없어 유일한 실측 기록) · 부록 L | §2.3 – 2.6(−60), §11(−51), §12.1(−26), 다음 단계 4절(−24), §20.5.3 – 4(−29), §21.1 증거 2 · 3(−15), 부록 B(−51), D.1 – D.7 → §32.1 열(−55), §41.4 · 부록 E(−26), G.5 · G.6(−17), G.7.1 · G.7.4(−32), G.8(−47), H.9(−15), J.8 · K.8(−30) 등 | 약 3,620 (부록 M 을 더하면 약 3,820) |
| `Q2_2XS_보완_전략_설계.md` | 1,704 | 없음(부록 M 과 주석으로 옮긴 뒤) | 전체 | 0 |
| `QQQ_지연진입_연구.md` | 728 | 1장 결론 · 행동 규칙, 6 · 7 · 10 · 13 · 14장 | 머리말 박스, 1장 이력 박스, 4장 성과 표, 9장 → 3줄, 12장 중복 · 모순, 8장 해석 축약 | 약 654 (거래가 끝나면 약 590) |
| `Q2_2XS_QQQ_상관계수_연구.md` | 469 | 1장(EMA 대비 표 포함), 6 – 11장 | 12장 계산 코드 → 커밋 `18b75fb` 포인터(−67), 3장 표 둘(−19) | 약 379 |
| **합계** | **7,043** | | | **약 4,850** |

기각 · 보류: `전략_검증_보고서.md` 를 주제별 파일로 나누는 안(보고서 안 「§」 참조 139 · 「부록」 77, 코드 · 안내 문서에서 보고서로 9곳 — 나누면 줄 수는 그대로이고 참조만 깨진다. 먼저 줄이고 그래도 크면 Part 경계로만). J · K 와 상관 연구의 배치 통일(합치면 +380줄, 떼면 참조가 깨진다 — 그대로 둔다).

## 19. 처리 순서

1. **결정 받기** — B 절 20건(13 은 답함). 결정 1 · 2 · 12 · 18 이 뒤 단계를 가른다.
2. ~~다음 시세 다운로드 전에 TQQQ 합성 재생성~~ **처리함(2026-10-09)** — 금리 2026-08 · 09 추가 → 합성 · 일별 비교 · 단일 백테스트 재산출(2-1 · 2-23). TQQQ 워크포워드는 4단계에서 함께 재실행한다.
3. **표시 수치 바로잡기** — 1-1 · 1-6(재현 테스트 2-28 먼저) · 1-2(결정 3) · 1-3 · 2-17 · 1-4 · 1-12 · 2-18. 결과 JSON 을 재산출한다. CAGR · MDD · Calmar 는 바뀌지 않는다.
4. **워크포워드 · 고원** — 결정 1 대로 1-11 을 처리하고 WFO · 고원을 한 번 재실행한다(2-19 · 3-17 함께). 그 결과로 연구 문서 R1 · R6 · R8 을 고친다.
5. **기계적 정리 한 커밋** — 10절(import 이동 + PLC0415) · 11절(ignore · noqa 126줄 삭제 · 설정 3줄 · 코드 수정 11줄 · E712 15줄). 동작 변화 0.
6. **검사 공백 보강** — 2-25 · 2-26 · 2-27 + DEFERRED 2 · 8 · 13. 보강한 검사는 결함을 일부러 넣어 실패하는 것을 본다.
7. **설정 · 파라미터 검증 묶음** — 5-2 · 9-6 · 9-10 · 5-5 · 2-11 · DEFERRED 3(9 가 덤으로 풀린다).
8. **포트폴리오 러너 · 대시보드 묶음** — DEFERRED 4 · 6(결정 2) · 10 · 11 + 2-5 · 3-8 · 6-8 · 9-9 · 7-11.
9. **정합성 검사기 묶음** — 7-4 · 7-10 · 9-2.
10. **입력 경계 검사** — 9-12 · 9-3 · 2-20.
11. **영역별 데드코드 · 단일 출처**
    - tqqq · utils: 5-1 · 2-2 · 2-13 · 4-2 · 4-4 · 5-4 · 6-5 · 2-3 · 2-6 · 2-14 · 8-6 · 7-14 · 결정 5 · 6 · 10.
    - backtest: 6-1 · 6-3 · 6-4 · 5-8 · 6-6 · 6-11 · 6-12 · 12-3 · 12-4 · 1-8 · 1-9 · 7-5 · 7-6 · 8-2 · 3절.
    - 대시보드: 7-1(결정 4) · 5-6 · 6-15 · 12-9.
    - tests: 6-9 · 6-17 · 5-11 · 7-9.
12. **문서**
    1. COMMANDS 순서 블록(13-B D4)과 안내 문서의 실오류(D1 – D3 · D11 – D14).
    2. 안내 문서 경량화(18-D) — 위 코드 정리가 끝난 뒤에 한다(코드가 바뀌면 문서도 바뀐다).
    3. 연구 문서의 남은 실오류(13-A)와 경량화(18-C · 18-D-R).
    4. 부록 M 작성 → 설계서 처리(16-B).
    5. 계획서 10개 삭제(결정 12) · `DEFERRED_FINDINGS.md` 에서 처리가 끝난 항목 삭제.
    6. **이 보고서 삭제.**

## 20. 기각 · 보류한 이전 판 항목

표에서 뺀 이전 판 지적과 제안이다.

| 이전 판 | 처리 | 이유 |
|---|---|---|
| 3-10 실험 이름 두 번 적기 | 보류 | 이름과 폴더가 어긋나도 러너 · 앱이 같은 `result_dir` 을 읽어 틀린 값이 안 나온다. 바꾸면 테스트 7파일의 생성자를 고친다 |
| 3-16 `TQQQ_DATA_PATH` 를 공통 상수로 | 기각 | tqqq 스크립트 2개만 써서 3계층 규칙상 지금 자리가 맞다 |
| 4-5 `COL_FFR_DATE` · `COL_EXPENSE_DATE` 합치기 | 보류 | 테스트 125줄을 고쳐야 해 실익보다 비용이 크다 |
| 5-6 중 `portfolio_execution.py:131` | 기각 | 바꾸면 매도가 산식이 한 벌 더 생긴다. 틀린 값 없음 |
| 7-7 중 두 그리드 러너 공용화 | 보류 | 끝난 실험의 재현용이고, 공용화하면 표시 코드가 src 로 간다 |
| 8-3 결과 후처리 모듈 | 보류 | 6-8 을 지우면 문제 자체가 10여 줄로 준다 |
| 9-8 합성 이음매 오류 메시지 | 7-3 에 합침 | `splice_proxy` 로 바꾸면 함께 풀린다 |
| 12-6 중 EPSILON 삭제 | 기각 | 검사기 규칙 2 가 그 열을 기준에 견주므로 필요하다 |
| 2-8 빈 윈도우 CSV | 2-12 와 함께 정리 | 닿지 않는다(IS 선택이 최소 거래 3회를 강제) |
| 13-B D10 `evidence_home` | 기각 | `/impl-plan` 은 그 값으로 폴더만 정한다 |
| 15 루트 `CLAUDE.md:60` 실측 날짜 삭제 | 기각 | 전역 규칙이 근거 사건의 `[실측] 날짜` 를 허용한다 |
| 15 반올림 근거를 `docs/research/` 로 | 기각 | research 는 전략 연구의 자리이고, 「되돌리면 무엇이 깨지는가」는 규칙 옆에 둔다 |
| 17 DEFERRED 2 · 8 「버림」 | 기각 | 결함을 넣어도 테스트 · 검사기가 하나도 못 잡는다(검사 보강 규칙) |
| 17 DEFERRED 파일 자체(줄 번호 빼기 · 3 – 5줄 축약 · 설계서 · `scripts/CLAUDE.md:159` 를 DEFERRED 참조로) | 기각 | `/impl-plan` 항목 형식과 부딪힌다. 결정 번호를 이유 문장으로 바꾸는 것만 받아들인다 |
| 18-B B17 전역 규칙을 다시 적은 곳 | 기각(일부는 15절로) | `DEFERRED_FINDINGS.md:5-9` 는 `/impl-plan` 이 요구하는 머리말, `tests/CLAUDE.md:111-131` · `src/qbt/CLAUDE.md:89-93` 은 저장소 고유 내용이다. `src/qbt/CLAUDE.md:95-99`(지양 접두사) 삭제만 15절에 남겼다 |
| 18-E 보고서 파일 분할 | 보류 | 나누면 줄 수는 그대로이고 참조(§ 139 · 부록 77)만 깨진다. 먼저 줄인다 |
| 18-E J · K 와 상관 연구의 배치 통일 | 기각 | 합치면 +380줄, 떼면 참조가 깨진다 |
| 11 `enableTypeIgnoreComments: false` | 기각 | 남는 정당한 ignore 3줄은 규칙 코드를 붙이므로 필요 없다 |
| DEFERRED 10 의 「엔진이 `min_start_date` 를 읽게」 | 보류 | 엔진에 시작일 경로가 둘 생긴다. 러너 2 – 3줄 수정으로 충분하다(8-8) |
