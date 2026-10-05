# Implementation Plan: 장기 대체 데이터 · 대체-실물 비교 도구 (계획서 ④-1)

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

**작성일**: 2026-10-05 09:08
**마지막 업데이트**: 2026-10-05 11:06
**관련 범위**: utils(대체 비교 · 금리 누적 시계열), common_constants(경로), scripts/data(장기 대체 시계열 생성 · 비교 계산 · 비교 대시보드), storage/stock(대체 시세 · 생성 파일), storage/results/proxy_comparison, docs
**관련 문서**: `src/qbt/utils/CLAUDE.md`, `src/qbt/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/research/Q2_2XS_보완_전략_설계.md`

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

- [x] 목표 1: 대체 시세 10종(VGTSX · VTMGX · VEIEX · VGSIX · VUSTX · VFITX · VFISX · VIPSX · ^SPGSCI · GC=F)을 기존 다운로더로 `storage/stock/{TICKER}_max.csv` 에 받는다. 기존 시세는 다시 받지 않는다(D22)
- [x] 목표 2: 대체 판 전용 생성 파일을 스크립트로 만든다 — `SSO_proxy_max.csv` · `QLD_proxy_max.csv`(SPY · QQQ 2배 합성, 저장소 TQQQ 비용 모델을 배율 2 로), `BIL_proxy_max.csv`(연방기금금리 누적, 착수 전 결정 ②), `DBC_synthetic_max.csv`(S&P GSCI → DBC 이어 붙임, 착수 전 결정 ①). 가격은 소수 6자리다
- [x] 목표 3: 대체-실물 비교 모듈과 계산 스크립트 — 등록 쌍마다 전체 · 연도별 · 국면별 상관 · 수익 차 · 최대낙폭 차 · 12개월 이동 상관 최저값을 `storage/results/proxy_comparison/` CSV 로 남긴다. 비교는 기준 시세(실물)가 있던 기간에서만 한다(D57 ②)
- [x] 목표 4: 비교 대시보드(사용자가 실행) — 쌍을 고르면 누적수익 겹쳐 그리기(대체의 상장 전 구간 포함, 실물 첫 거래일 표시) · 12개월 이동 상관 · 연도별 · 국면별 표. 착수 전 결정 ③ 에 따라 저장소의 아무 두 시세나 직접 골라 비교한다
- [x] 목표 5: 금리 누적 시계열과 비교 계산의 계약을 테스트로 고정한다

## 2) 비목표(Non-Goals)

- **조합 그리드 실험(세 판) · 판정 규칙 · 완전 실물판의 원자재 · 대체 판의 대용 검증 관문(판정 일치 · 신호 일치율)** — 계획서 ④-2 (D55 – D57). 이 계획서의 비교는 시세만 보고 통과 · 탈락을 정하지 않는다
- **엔진 변경** (D27) — 배분 규칙이 실험의 공통 거래일로 자른 시세를 받아 대체 판의 HAA · 로테이션이 늦게 시작하는 것(2001-08-31 · 2001-06-18, 설계서 15장 S7) 포함
- **이어 붙인 판(지금 주 비교)의 대용 교체 · 기존 결과 · 실험 설정(`PORTFOLIO_CONFIGS`) 변경** — 같은 펀드 클래스가 더 가깝다는 발견(S7)은 ④-2 에서 판단 재료로만 쓴다
- **다운로더 변경** — 파일 이름 정리(`^` · `=`), `DEFAULT_TICKERS` 모두. 신규 티커는 인자로 하나씩 받는다(D43 ⑤ 와 같은 이유)
- **기존 생성 스크립트 변경** — `scripts/data/generate_proxy_series.py` · `scripts/tqqq/generate_synthetic.py`
- **2배 합성 비용 모델 재보정** — SSO · QLD 전용 파라미터를 맞추지 않고 TQQQ 모델을 배율 2 로 그대로 쓴다. 실물과 겹치는 20년 대조에서 연수익 차가 -0.05 · -0.03%p 였다(S7)
- **입력 가격 자릿수 통일(6 → 4자리)** — 루트 `CLAUDE.md` 「가격 반올림 자릿수」의 의도된 미이행이고 생성 파일도 입력 계층이다(D39)
- **판단(신호) 일치율 비교** — 이 도구는 시세를 비교한다. 판단 일치는 ④-2 의 그리드 러너가 잰다(D23 · D48 과 같은 분담)
- **^IRX(13주 국채 금리)** — 착수 전 결정 ② 가 연방기금금리면 쓰지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 조합 실험을 대체 판 · 이어 붙인 판 · 완전 실물판 셋으로 돌리기로 했다(D57 ①). 대체 판은 2000-08-30 부터 대체 시세가 필요한데 저장소에 없다 — S7 은 세션 임시 폴더에서만 받아 쟀다
- 대체가 실물을 얼마나 잘 따르는지 사용자가 화면으로 확인하고, 앞으로 다른 대체에도 다시 쓰려면 정식 도구가 필요하다(D57 ②). D43 ⑦(측정 스크립트를 남기지 않는다)을 이 작업부터 대체한다
- 계획서 ④ 를 둘로 나눈다 — ④-1 은 데이터와 비교 도구, ④-2 는 세 판 조합 그리드. 데이터와 비교 결과를 먼저 커밋해 ④-2 가 확인된 데이터 위에서 돈다(③-1 → ③-3 과 같은 순서)
- 글자 규칙이 막거나 되돌릴 수 없는 결과에 물리는 설계 — 해당 없음(입력은 시세 숫자이고 판정이 없다)

### 착수 전 확인한 사실 (2026-10-04 – 05, 세션 임시 폴더 · 저장소 조회, 저장소 변경 없음)

- **다운로더 검증 사전 확인** — `download_stock_data` 와 같은 가공(`history(period="max")` · 최근 2일 제외 · 6자리) 뒤 `validate_stock_data` 만 불렀다. 10종 통과: VGTSX 1996-04-29 · 7,657행 / VTMGX 1999-08-17 · 6,824 / VEIEX 1994-05-04 · 8,159 / VGSIX 1996-05-13 · 7,647 / VUSTX 1986-05-19 · 10,172 / VFITX 1991-10-28 · 8,795 / VFISX 1991-10-28 · 8,795 / VIPSX 2000-06-29 · 6,604 / ^SPGSCI 1984-01-03 · 10,771 / GC=F 2000-08-30 · 6,548 (끝은 모두 2026-10-02, 하루 최대 변동 19.32%(VGSIX 2008-12-01) 이하). **^IRX 는 실패** — 음수 9행(2020-03) · 하루 ±50% 이상 285회
- 뮤추얼 펀드 8종은 거래량이 전부 0 이고, 시가 = 종가인 날이 87.8 – 94.8% 다(기준가 하나). 엔진의 「다음 날 시가 체결」이 대체 구간에서는 사실상 「다음 날 종가 체결」이 된다. GC=F 는 거래량 0 인 날이 6.4%
- 다운로더 파일 이름은 `{ticker}_max.csv` 그대로라 `^SPGSCI_max.csv` · `GC=F_max.csv` 가 된다(`download_data.py` 가 티커를 대문자로만 바꾼다)
- **대조 실측(S7, 설계서 15장 S7 에 원본 수치)** — 같은 펀드 클래스는 월간 상관 0.9986 – 0.9994(VEIEX 0.9920), 2배 합성은 SSO 0.9998 · QLD 0.9997, GC=F → GLD 0.9921, ^SPGSCI → DBC 0.9526, 금리 합성 → BIL 0.9530(연방기금금리) · 0.9471(^IRX)
- **실제 시작일(S7)** — 대체 판에서 Q-2-2XS 단독 · 기준선 2000-08-30, 로테이션 2001-06-18, HAA · 조합 2001-08-31
- **2배 합성 재료** — `qbt.tqqq.simulation.simulate(underlying_df, leverage, expense_df, initial_price, ffr_df=, expense_dict=, funding_spread=)` 는 배율을 인자로 받는다(호출처: `scripts/tqqq/generate_synthetic.py` · `generate_daily_comparison.py`). 비용 = (연방기금금리 + softplus 스프레드) × (배율 − 1) + 운용보수. 운용보수는 TQQQ 실제값(`tqqq_net_expense_ratio_monthly.csv`, 2010-02 부터)을 `build_extended_expense_dict` 가 1999-01 까지 0.95% 로 늘린 것이다
- **연방기금금리 파일** `storage/etc/federal_funds_rate_monthly.csv` 는 1999-01 부터 2026-07 까지다. `simulate` 와 `lookup_ffr` 은 최근 달과 2개월까지 차이를 허용한다 — 기초 시세가 2026-09 를 넘으면 금리 파일을 먼저 갱신해야 한다. 모델을 맞춘 기간(TQQQ 2010 이후)의 금리 최고는 5.33%(2024-08)인데 대체 판 초기는 6.54%(2000-07)까지 간다
- 연환산 상수: `ANNUAL_DAYS = 365.25`(CAGR), `TRADING_DAYS_PER_YEAR = 252`(일일 비용 환산) — 둘 다 `common_constants.py`
- 국면 구간은 `qbt.backtest.supplement_experiment.PHASE_WINDOWS`(D48 ⑦)다
- 선례: TQQQ 합성 대 실물 비교가 계산 스크립트 `scripts/tqqq/generate_daily_comparison.py` → CSV → `scripts/tqqq/app_daily_comparison.py` 로 나뉘어 있다. TQQQ 전용 열 이름(`COL_ACTUAL_CLOSE` 등)이라 재사용할 수 없고 모양만 따른다

### 착수 전에 정할 것 (사용자 답 대기 — 답은 설계서 6장에 D58 로 적는다)

| 질문 | 현재 확인된 사실 | 선택지와 영향 | 추천 |
| --- | --- | --- | --- |
| ① 대체 판의 원자재 | 대체 판의 PDBC 자리. ^SPGSCI → DBC 월간 상관 0.9526 · 연수익 2.66 / 2.69. DBC → PDBC 0.9966(③-1 측정). DBC 는 2006-02-06 부터 | (가) ^SPGSCI 전 기간 — 파일을 만들지 않고 받은 파일 그대로. 2006 이후도 실제로 사는 상품(PDBC)과 지수가 다르다. (나) ^SPGSCI → DBC 이어 붙임(`DBC_synthetic_max.csv`) — 2006-02 부터는 PDBC 와 같은 계열 지수라 실물과 가깝다. 생성 파일 하나가 는다 | (나) |
| ② 대체 판의 BIL | ^IRX 는 다운로더 검증에서 막힌다(음수 · ±50%). 연방기금금리는 저장소에 이미 있다(D23 이 정한 BIL 대체 경로). 대조: 연방기금금리 월간 0.9530 · 연수익 1.57 / 1.39, ^IRX 0.9471 · 1.48 / 1.39 | (가) 연방기금금리 누적 — 새 데이터 없음, 월별이라 한 달 안은 같은 금리, 연 0.18%p 높다. (나) ^IRX — 금리 전용 받기 경로(검증 규칙이 다른)를 새로 만들어야 한다 | (가) |
| ③ 대시보드 범위 | 차트는 어느 쪽이든 `src` 함수로 즉석 계산한다(일별 CSV 를 저장하지 않는다) | (가) 등록 쌍 + 직접 고르기 — `storage/stock/` 의 아무 두 시세를 골라 같은 화면으로 본다. 다음 대체 후보는 코드 없이 바로 본다. (나) 등록 쌍만 — 새 쌍은 스크립트 목록에 한 줄 더하고 다시 돌린다 | (가) |

### 설계 (결정에서 구현으로)

**대체 시세 받기**

- 기존 `scripts/data/download_data.py TICKER` 로 10종을 하나씩 받는다. `^SPGSCI` · `GC=F` 는 따옴표로 감싼다. 저장 전 기존 검증(결측 · 0 · 음수 · 하루 ±50%)을 통과해야 저장된다 — 10종 모두 사전 확인에서 통과했다
- 다운로더와 파일 이름은 바꾸지 않는다 — 특수 문자가 든 티커 파일이 아직 없어 바꿀 대상이 이 둘뿐이고, 다운로더는 모든 시세가 지나는 공용 경로다

**금리 누적 시계열** (`src/qbt/utils/proxy_series.py` 에 함수 하나 추가 — 시세 가공이라 그 모듈)

- `build_rate_accrual_series(dates, annual_rates) -> DataFrame`: 첫날 종가 1.0, `C_t = C_{t−1} × (1 + r_{t−1} ÷ TRADING_DAYS_PER_YEAR)` — 전날 금리로 하루치 이자를 붙인다. 시가 = 고가 = 저가 = 종가(하루 안 움직임 없음), 거래량 0, 열은 `REQUIRED_COLUMNS`
- 입력 검증(`ValueError`): 날짜가 중복 없는 오름차순이 아님, 두 입력 길이가 다름, 2개 미만, 금리에 NaN. 음수 금리는 허용한다(가격은 양수로 남는다)
- 스크립트에서: SPY 거래일(1999-01-04 부터 — 금리 파일 첫 달) × `lookup_ffr` → 이 함수 → `rescale_to_actual`(BIL 실물) → `BIL_proxy_max.csv`

**2배 합성** (새 계산 없음 — 기존 `simulate` 를 스크립트에서 부른다)

- SPY(1999-01-04 부터) · QQQ(1999-03-10 부터) → `simulate(leverage=2.0, 운용보수 = TQQQ 확장판, 스프레드 = softplus 기본값)` → `rescale_to_actual`(SSO · QLD 실물) → `SSO_proxy_max.csv` · `QLD_proxy_max.csv`. 이음매 스케일로 가격 수준만 실물에 맞춘다(VXUS 순수판 선례, D43 ④)
- 시가는 `simulate` 가 기초 자산의 시가 갭 × 배율로 만들고, 고가 · 저가는 근사다(엔진은 시가 · 종가만 쓴다 — S5 발견)
- 비용 모델을 맞춘 설정 줄(금리 · 운용보수 · 스프레드 맵)은 `generate_synthetic.py` 와 같은 모양으로 새 스크립트에 둔다 — 그 스크립트는 고치지 않는다(비목표)

**원자재 이어 붙임** (착수 전 결정 ① 이 (나)일 때)

- `splice_proxy(^SPGSCI, DBC)` → `DBC_synthetic_max.csv`(이음매 DBC 첫 거래일 2006-02-06). 이름 규칙 `{TICKER}_synthetic_max.csv` = 상장 전은 대용, 상장 후는 실물(`src/qbt/CLAUDE.md`)

**생성 스크립트** (새 `scripts/data/generate_long_proxy_series.py`, 인자 없음)

- 저장 순서는 기존 생성 스크립트와 같다(가격 6자리 반올림 → `validate_stock_data` → 저장). `.round(6)` 을 그대로 써 루트 `CLAUDE.md` 「가격 반올림 자릿수」 표의 검색에 걸리게 하고, 그 표에 이 스크립트를 등록한다(D43 ⑥ 과 같은 이유)
- 메타 `save_metadata("long_proxy_series", …)` — 파일마다 출처 · 행 수 · 기간 · 이음매 날짜 · 스케일, 2배 합성은 배율과 비용 모델 이름
- 기존 `generate_proxy_series.py` 에 넣지 않는 이유: 그 스크립트는 이어 붙인 판(주 비교) 전용이고 입력이 다르며(TQQQ 비용 모델 · 금리 파일), 넣으면 실행할 때마다 이미 커밋한 5개 파일도 다시 써진다

**비교 모듈** (새 `src/qbt/utils/proxy_comparison.py` — 두 시세의 비교라 도메인과 무관, backtest 를 import 하지 않는다)

- `align_closes(proxy_df, base_df) -> DataFrame`: 기준(실물) 첫 거래일부터 두 시세의 끝 중 이른 날까지, **두 시세 모두 있는 날만**(시장 달력이 다른 선물 · 펀드를 메우지 않는다). 열은 날짜 · 대체 종가 · 기준 종가. `ValueError`: 날짜가 중복 없는 오름차순이 아님, 겹치는 날 2개 미만
- `summarize_pair(aligned) -> PairSummary`(frozen dataclass): 시작 · 끝 · 거래일 수, 일간 상관(종가 수익률), 월간 상관(월 마지막 거래일 종가, 첫 달 부분 수익 제외)과 개월 수, CAGR 대체 · 기준(%, `ANNUAL_DAYS` 연환산), MDD 대체 · 기준(%, 종가 고점 대비), 12개월(`TRADING_DAYS_PER_YEAR` 거래일) 이동 상관의 최저값과 그 날짜(겹치는 기간이 그보다 짧으면 None). 정의는 설계서 8.3 「측정 방법」과 같다
- `summarize_periods(aligned, periods) -> list[PeriodSummary]`: 기간(이름 · 시작 · 끝)마다 겹치는 범위로 자른 실제 시작 · 끝, 거래일 수, 일간 상관, 수익률 대체 · 기준(%, 기간 첫날 전날 종가 기준 — 전날이 없으면 첫날 종가)과 차이. 자른 범위의 거래일이 2개 미만인 기간은 결과에서 뺀다
- `calendar_year_periods(start, end)`: 연도 기간 목록(첫 해 · 마지막 해는 부분 연도)
- `rolling_correlation(aligned, window) -> Series`: 일간 수익률의 이동 상관
- `normalized_overlay(proxy_df, base_df) -> DataFrame`: 대체 전 구간과 기준을 `align_closes` 첫날 종가 1.0 으로 함께 맞춘다 — 대체의 상장 전 구간도 같은 눈금에 보인다

**비교 계산 스크립트** (새 `scripts/data/generate_proxy_comparison.py`, 인자 없음)

- 등록 쌍(스크립트 로컬 상수 — 묶음 · 대체 경로 · 기준 경로)
  - **대체 판 대체 ↔ 실물 (13)**: SSO_proxy ↔ SSO · QLD_proxy ↔ QLD · GC=F ↔ GLD · VUSTX ↔ TLT · VFITX ↔ IEF · VFISX ↔ SHY · BIL_proxy ↔ BIL · VIPSX ↔ TIP · VTMGX ↔ VEA · VEIEX ↔ VWO · VGSIX ↔ VNQ · VGTSX ↔ VXUS · 원자재(결정 ① 의 파일) ↔ PDBC
  - **이어 붙인 판 기존 대용 ↔ 실물 (4)**: EFA ↔ VEA · SHY ↔ BIL · DBC ↔ PDBC · VXUS_proxy(EFA 75% + EEM 25%) ↔ VXUS
  - **상장 전 교차 확인 (4)** — 기준이 실물이 아니라 다른 대체다: VTMGX ↔ EFA(2001-08 부터) · VGTSX ↔ VXUS_proxy(2003-04 부터) · VEIEX ↔ EEM(2003-04 부터) · ^SPGSCI ↔ DBC(2006-02 부터)
- 기간: 연도(`calendar_year_periods`) + 국면(`PHASE_WINDOWS`)
- 출력: `storage/results/proxy_comparison/summary.csv`(쌍마다 한 행) · `periods.csv`(쌍 × 기간). 한글 헤더(`DISPLAY_` 상수), UTF-8 BOM, 상관 4자리 · % 2자리. 메타 `"proxy_comparison"`
- 결과 폴더 경로 상수 `PROXY_COMPARISON_RESULTS_DIR` 은 스크립트와 대시보드가 함께 쓰므로 `common_constants.py` 에 둔다(상수 배치 규칙)

**비교 대시보드** (새 `scripts/data/app_proxy_comparison.py` — 사용자가 실행한다)

- 전체 표(`summary.csv`) → 쌍 선택(등록 쌍, 결정 ③ 이 (가)면 「직접 고르기」로 `storage/stock/` 의 두 CSV)
- 선택한 쌍: 누적수익 겹쳐 그리기(로그 눈금, 대체 전 구간, 기준 첫 거래일 세로선) · 12개월 이동 상관(최저점 표시) · 연도별 표 · 국면별 표
- 등록 쌍의 표는 `periods.csv` 를 읽고, 차트와 직접 고른 쌍은 같은 `src` 함수로 즉석 계산한다 — 계산은 `src` 하나라 화면과 CSV 가 갈리지 않고, 쌍 21개 × 수천 일의 일별 CSV 를 저장하지 않는다
- 섹션마다 「무엇을 보나 · 읽는 법」 짧은 설명(한글 — `docs/MEMORY.md` 「전략 용어는 풀어서」). Plotly, `width` 규칙(`scripts/CLAUDE.md`)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」 · 「가격 반올림 자릿수」 절 (값이 아니라 **판단 근거**)
- `docs/MEMORY.md`
- `docs/CLAUDE.md`
- `src/qbt/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `.claude/rules/python.md` (전역 `~/.claude/rules/python.md`)
- `docs/research/Q2_2XS_보완_전략_설계.md` 0장 「세션 인계 규칙」 · 6장 D22 · D23 · D27 · D39 · D43 · D55 – D57 · 15장 S7

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 금리 누적 시계열과 비교 함수의 계약(산식 · 겹치는 날 맞추기 · 기간 자르기 · 이동 상관 · 입력 검증 · 입력 불변)이 테스트로 고정되고 통과한다
- [x] 대체 시세 10종이 `storage/stock/` 에 있고, 종목마다 시작일 · 끝날 · 행 수를 진행 로그에 도구 출력 그대로 남겼다
- [x] 생성 파일이 실측 검증을 통과한다 — 이음매 종가 = 실물 종가 · 2배 합성 · 금리 합성 수익률이 산식과 같다 · 이어 붙인 원자재의 이음매 이후 줄이 DBC 와 같다 · 두 번 생성한 파일이 바이트까지 같다
- [x] 비교 CSV 가 생성되고, S7 임시 측정과 끝날이 같은 쌍(SSO · QLD · GLD · TLT 대조)의 값이 S7 과 같다 · 두 번 실행한 CSV 가 바이트까지 같다
- [x] 기존 결과 파일이 바뀌지 않았다 — `storage/results/` 에서 바뀐 것은 `meta.json` 과 `proxy_comparison/` 뿐이다
- [x] 사용자가 대시보드를 확인했다(확인 지점 2) — 사용자가 화면 대신 특이사항 요약으로 확인하기로 하고 「진행」(진행 로그 09:51 · 10:21)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 있음(대체 시세 받기 · 장기 대체 생성 · 비교 계산 · 비교 대시보드), `scripts/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md`(입력 반올림 지점 표) 변경 있음, `README.md` 변경 있음(대시보드 목록에 대체 데이터 비교)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관.
      `/impl-plan` 스킬 "근거 승격" 참고. 이 작업의 목적지는 `docs/research/Q2_2XS_보완_전략_설계.md` — 그 문서 0.1)
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 스킬 "미룬 지적 옮기기" 참고)
      — 옮김 1건(교차 확인 쌍 자르기 강제 없음), 거른 지적은 진행 로그, 이 계획서가 고친 파일 항목 0건
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/utils/proxy_comparison.py` (새 파일)
- `src/qbt/utils/proxy_series.py` — `build_rate_accrual_series` 추가
- `src/qbt/common_constants.py` — 대체 시세 10개 · 생성 파일 3 – 4개 경로, `PROXY_COMPARISON_RESULTS_DIR`
- `scripts/data/generate_long_proxy_series.py` · `scripts/data/generate_proxy_comparison.py` · `scripts/data/app_proxy_comparison.py` (새 파일)
- `tests/qbt/test_proxy_comparison.py` (새 파일), `tests/qbt/test_proxy_series.py` (금리 누적 테스트 추가)
- `storage/stock/` — 신규 10개, 생성 3 – 4개
- `storage/results/proxy_comparison/` (새 폴더: `summary.csv` · `periods.csv`), `storage/results/meta.json`
- `docs/COMMANDS.md` — 변경 있음: 대체 시세 10종 받기(특수 문자 티커는 따옴표), 장기 대체 생성 · 비교 계산 명령, 비교 대시보드, 「원본 · 금리 파일을 다시 받으면 생성 · 비교를 다시 돌린다」
- `scripts/CLAUDE.md` — 「데이터 수집 (data/)」에 두 스크립트와 대시보드, 「메타데이터 관리」 지원 타입에 `long_proxy_series` · `proxy_comparison`
- `src/qbt/utils/CLAUDE.md` — 모듈 구성에 `proxy_comparison.py`, `proxy_series.py` 에 금리 누적
- `src/qbt/CLAUDE.md` — 디렉토리 구조의 utils 목록, 「분석 결과」에 `proxy_comparison/`
- 루트 `CLAUDE.md` — 「가격 반올림 자릿수」 입력 지점 표에 새 생성 스크립트
- `README.md` — 「Streamlit + Plotly 대시보드」 목록에 대체 데이터 비교
- `docs/research/Q2_2XS_보완_전략_설계.md` — D58(착수 전 결정), 대체 판 대조 결과(비교 CSV 에서), 0.2 · 0.3 · 15장

### 데이터/결과 영향

- 기존 실험 결과 파일(`storage/results/portfolio/` · `portfolio_grid/` 등) 영향 없음 — 엔진 · 실험 설정 무변경, 새 데이터를 읽는 실험 설정이 아직 없다
- 기존 `storage/stock/` 파일은 바뀌지 않는다(새 티커만 받는다)
- 신규 파일은 git 추적 대상이다(`storage/stock/` · `storage/results/` 가 추적됨). 비교 CSV 는 요약 두 개라 작다

## 6) 단계별 계획(Phases)

### Phase 0 — 금리 누적 · 비교 계약을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `tests/qbt/test_proxy_series.py` 에 `build_rate_accrual_series` 테스트 추가 (작은 합성 입력, 파일 · 네트워크 없음) — 첫 종가 1.0 · 전날 금리로 하루치 이자 · 시가 = 고가 = 저가 = 종가 · 거래량 0 · 음수 금리 허용 · 입력 검증(오름차순 아님 · 길이 다름 · 2개 미만 · NaN) · 입력 불변
- [x] `tests/qbt/test_proxy_comparison.py` 작성
  - `align_closes`: 기준 첫 거래일 앞 대체 행 제외 · 두 시세 모두 있는 날만 · 끝은 이른 쪽 · 겹치는 날 2개 미만과 오름차순 아님 → `ValueError` · 입력 불변
  - `summarize_pair`: 손으로 계산한 값(작은 예)과 일치 — 일간 · 월간 상관, CAGR(`ANNUAL_DAYS`), MDD, 이동 상관 최저값과 날짜, 기간이 창보다 짧으면 None. 같은 시세끼리는 상관 1 · 차이 0
  - `summarize_periods`: 겹치는 범위로 자르기 · 전날 종가 기준 수익률 · 전날이 없으면 첫날 기준 · 거래일 2개 미만 기간 제외
  - `calendar_year_periods` · `rolling_correlation` · `normalized_overlay`(첫 겹치는 날 1.0, 대체의 앞 구간 포함)

**Validation**:

- [x] `pytest tests/qbt/test_proxy_comparison.py tests/qbt/test_proxy_series.py` 가 함수 부재로 실패한다(레드) — `ImportError: cannot import name 'build_rate_accrual_series'` · `ModuleNotFoundError: No module named 'qbt.utils.proxy_comparison'`

---

### Phase 1 — 함수 · 경로 상수(그린)

**작업 내용**:

- [x] `src/qbt/utils/proxy_series.py` — `build_rate_accrual_series`
- [x] `src/qbt/utils/proxy_comparison.py` — Context 「비교 모듈」
- [x] `src/qbt/common_constants.py` — 경로 상수(Scope)

**Validation**:

- [x] 두 테스트 파일 통과 — 68 passed (`-W error` 로도 같음, 금리 누적 9 · 비교 27 추가)
- [x] 변형 확인 2건 — ① 금리 누적을 전날이 아니라 그날 금리로 ② `align_closes` 를 두 시세 모두 있는 날이 아니라 기준 날짜 전부(대체는 앞 값 채움)로 → 각각 테스트가 실패하는 것을 보고 되돌린다(사본 대조로 변형이 남지 않았는지 확인, `PYTHONDONTWRITEBYTECODE=1` — S6 발견) — ① 1 failed(`test_close_accrues_previous_day_rate`) ② 2 failed(`test_keeps_only_dates_in_both` · `test_anchor_moves_when_proxy_lacks_base_first_date`), 복원 후 사본과 동일 · 68 passed

---

### Phase 2 — 받기 · 생성 · 비교 계산 · 실측 검증

**작업 내용**:

- [x] `git status storage/` 로 미커밋 변경이 없는지 확인한 뒤 10종을 하나씩 받는다 — `env -u VIRTUAL_ENV poetry run python scripts/data/download_data.py <TICKER>`(`docs/MEMORY.md`). 실패한 티커가 있으면 멈추고 보고한다(보간 금지)
- [x] 종목마다 시작일 · 끝날 · 행 수를 진행 로그에 남기고 사전 확인(Context)과 다르면 함께 적는다
- [x] `scripts/data/generate_long_proxy_series.py` 작성 · 실행
- [x] 실측 검증(세션 스크래치 스크립트, 수치는 진행 로그)
  - 생성 파일마다 이음매 날짜 · 스케일, 이음매 종가 = 실물 종가
  - SSO · QLD 합성: 같은 입력으로 `simulate` 를 직접 부른 수익률과 파일 수익률의 최대 차이(6자리 반올림 수준)
  - BIL 합성: 금리 산식으로 다시 계산한 수익률과의 최대 차이
  - 원자재 이어 붙임(결정 ① 이 (나)일 때): 이음매 이후 줄 = DBC CSV 줄(바이트)
  - 생성을 한 번 더 돌려 파일이 바이트까지 같다
- [x] `scripts/data/generate_proxy_comparison.py` 작성 · 실행 → 비교 CSV
  - SSO · QLD · GLD · TLT 대조(끝날이 S7 과 같은 2026-09-24)의 일간 · 월간 상관 · CAGR · MDD 가 S7 값과 같다(다르면 원인을 적고 보고한다 — 다운로드 시점 수정주가 재조정 등)
  - 두 번 실행한 CSV 가 바이트까지 같다
  - `git status storage/results` — `meta.json` · `proxy_comparison/` 외 변경 없음
- [x] **확인 지점 1** — 비교 결과 표(쌍마다 전체 지표, 연도 · 국면 중 상관이 가장 낮은 구간)를 사용자에게 보고한다

**Validation**:

- [x] 위 실측 검증 항목 전부 통과(수치는 진행 로그)

---

### Phase 3 — 비교 대시보드

**작업 내용**:

- [x] `scripts/data/app_proxy_comparison.py` — Context 「비교 대시보드」
- [x] **확인 지점 2** — 실행 명령과 볼 지점을 안내하고 사용자가 화면을 확인한다(대시보드는 사용자가 실행 — 루트 `CLAUDE.md`)

**Validation**:

- [x] 사용자 확인 완료(받은 의견과 반영 내용은 진행 로그)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **`/commit` 이 «맨 마지막»인 것은 의도다.** 그 스킬은 「후보 뒤에는 아무것도 덧붙이지 말 것」으로
> 끝나므로 **호출하는 순간 그 턴이 거기서 닫힌다.** 중간에 두면 뒤에 적힌 항목이 그 벽 너머에 남는다 —
> 실제로 두 번 그렇게 샜다(`[실측] 2026-09-14` 후보를 계획서에 안 옮김 · `2026-09-16` 옮기고 체크박스를 안 닫음).
> **체크박스와 상태를 먼저 확정하고, 커밋 후보를 마지막에 만든다.**

- [x] 필요한 문서 업데이트 — Scope 대로(`docs/COMMANDS.md` 포함)
- [x] 근거 승격 — 설계서 D58 · 대체 판 대조 결과 · 0.2 · 0.3(다음은 ④-2) · 15장
- [x] 자동 포맷 적용 (`env -u VIRTUAL_ENV poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      `/commit` 은 계획서를 모르고 「후보 뒤에 아무것도 덧붙이지 말 것」으로 끝나므로,
      **대화에만 내면 그 절이 빈 채로 남는다.** 체크박스 갱신이 diff 에 더 들어가지만
      커밋 메시지의 내용을 바꾸지 않는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.
> **고칠 것이 0 인 회차에서 끝낸다** — 고칠 것은 닿는 버그다(`/impl-plan` 「고칠지는 «닿는가»로 가른다」).
> 2회차에도 무거운 버그가 나오면 사용자에게 보고하고 3회차 여부를 묻는다 — 나머지는 목록만 남기고
> 고치지 않는다. 닿는가와 무게의 정의는 `/impl-plan` 의 「코드 리뷰」 절이 SoT 다.
> **뒤에 리뷰 회차가 오지 않는 수정은 고치기 «전»에 바꿀 파일을 스크래치에 복사해 두고, 고친 뒤 수정분 검증을
> 거친다** — 절차는 `/impl-plan` 의 「지적을 고칠 때」다.

- [x] `/code-review xhigh` **1회차** (발견 15건 — 버그 6 [무거움 4 · 가벼움 2] · 그 외 9 · 조치: 무거움 2 수정(금리 · 운용보수 첫 달 · 비교 함수 입력 검사, 변형 확인) · 무거움 1 사용자에게 올림(^SPGSCI 가 현물 지수 — 데이터 선택) · 무거움 1 닿지 않음 · 가벼움 2 지금 산출물 0건)
- [x] `/code-review xhigh` **2회차** (발견 15건 — 버그 6 [무거움 4 · 가벼움 2] · 그 외 9 · 조치: 무거움 2 수정(교차 확인을 실물 상장 전으로 자름 · 대체 판 원자재 쌍을 ^SPGSCI → DBC 로) · 가벼움 1 수정(겹쳐 그리기 선 끊김, 지금 16군데) · 무거움 2 닿지 않음(1개는 1회차 수정 자리) · 가벼움 1 닿지 않음 — 2회차에 무거움이 나와 사용자에게 보고)
- [x] 수정분 검증 (수정 3건 · 발견 9건 — 무거움 1 · 조치: 무거움 1 은 코드가 아니라 설계서 8.4 가 수정 전 수치를 실은 것이라 근거 승격을 새 CSV 로 다시 함 · 가벼움 8 은 고치지 않고 보고)
- [x] `poetry run python validate_project.py` (passed=797, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

1. 데이터 / 장기 대체 시세 10종 · 대체 판 생성 파일과 대체-실물 비교 도구 추가
2. 데이터 / 2000-08 이전부터 전 기간 대체하는 대체 판 데이터 생성과 실물 대비 상관 비교 대시보드 도입
3. 데이터 / 같은 펀드 뮤추얼 클래스 · 2배 합성 · 금리 누적 대체 시세와 전체 · 연도별 · 국면별 비교 계산 구축
4. 데이터 / Q-2-2XS 보완 조합 실험의 세 판 구성을 위한 장기 대체 데이터 준비와 대체 정확도 검증
5. 데이터 / 계획서 ④-1 장기 대체 데이터 · 비교 도구 구현과 조합 실험 방향 결정(D51 – D61) 기록

## 7) 리스크(Risks)

- **다운로드 실패 · 검증 실패** — 사전 확인은 통과했지만 받는 시점 응답이 다를 수 있다. 완화: 멈추고 보고한다(보간 · 우회 금지). 네트워크 오류는 전역 「외부 요청이 실패하면」 진단 순서를 따른다
- **뮤추얼 펀드의 시가 = 기준가** — 대체 판에서 대체 구간의 체결이 다음 날 종가가 된다. 완화: 이 계획서는 바꾸지 않고(종가만 비교한다) 설계서에 사실을 남겨 ④-2 의 해석 재료로 넘긴다(받아들임 — 엔진 무변경 D27)
- **2배 합성의 모델 범위 밖 구간** — 2000 – 2001 금리(최고 6.54%)가 모델을 맞춘 기간의 최고(5.33%)보다 높고, 2006-06 이전은 실물로 대조할 수 없다. 완화: 대시보드 · 설계서에 「대조할 실물 없음」으로 표시한다(받아들임 — 확인 수단이 없다)
- **금리 파일이 짧아지는 계기** — 기초 시세를 다시 받아 끝이 금리 파일 마지막 달보다 2개월 넘게 뒤면 생성이 기존 검증 오류로 멈춘다(막는 쪽). 완화: `docs/COMMANDS.md` 에 「금리 파일을 먼저 갱신」을 적는다
- **특수 문자 파일 이름**(`^SPGSCI_max.csv` · `GC=F_max.csv`) — 셸에서 따옴표가 필요하다. 완화: `docs/COMMANDS.md` 명령을 따옴표로 적는다
- **원본을 다시 받으면 생성 파일 · 비교 CSV 가 낡는다** — 수정주가 재조정으로 과거 값도 바뀐다(S5 발견). 완화: 메타에 생성 시각을 남기고 `docs/COMMANDS.md` 에 다시 돌리는 순서를 적는다. 결과 비교 중에는 다시 받지 않는다(D22)
- **S7 값과 차이** — 같은 날 받아도 yfinance 응답이 다를 수 있다. 완화: Phase 2 에서 차이와 원인을 적고 보고한다(설계서 0.1 「예비 수치와 정식 수치를 섞지 않는다」 — 승격은 비교 CSV 값으로)
- **시장 달력 차이** — 선물(GC=F)과 펀드는 거래일이 실물 ETF 와 다를 수 있다. 완화: 비교는 두 시세 모두 있는 날만 쓴다(메우지 않는다). 엔진은 실험의 공통 거래일로 자르므로 ④-2 에서도 같은 방식이다

## 8) 메모(Notes)

- 결정 근거는 설계서 6장 D22 · D23 · D27 · D39 · D43 · D55 – D57 에 있다. 착수 전 결정 ① – ③ 의 답은 D58 로 적고, 이 계획서에서 정한 세부(새 생성 스크립트로 분리 · 일별 CSV 미저장 · 다운로더 무변경 · 금리 누적 산식)는 Done 전에 설계서로 옮긴다
- 계획서 ④-2(세 판 조합 그리드)가 이 계획서의 출력(대체 시세 · 생성 파일 경로 상수)을 쓴다

### 진행 로그 (KST)

- 2026-10-05 09:08: 계획서 작성 (S7). 착수 전 사실 확인 — Context 「착수 전 확인한 사실」. 착수 전 결정 ① – ③ 사용자 답 대기
- 2026-10-05 09:12: 계획서 자체 검증 — 원자재 이음매 2006-02-06(DBC 첫 거래일)이 ^SPGSCI 시세에 있다(1행). 세션 임시 폴더의 2배 합성 파일(S7 측정용)의 하루 최대 변동은 SSO 29.03%(2008-10-13) · QLD 33.65%(2001-01-03)로 다운로더 검증 한도 50% 안이고, 가격 최저값이 양수다(15.087103 · 4.598824) — 생성 파일이 `validate_stock_data` 에 막히지 않을 것으로 본다
- 2026-10-05 09:19: 사용자 답 — 착수 전 결정 ① – ③ 모두 추천대로(① ^SPGSCI → DBC 이어 붙임 ② 연방기금금리 누적 ③ 등록 쌍 + 직접 고르기), 계획서 승인. 설계서 D58 로 기록. Phase 0 착수
- 2026-10-05 09:24: Phase 0 · 1 완료. 계획과 달라진 점 — `summarize_pair` 에 `rolling_window` 인자(기본 `ROLLING_WINDOW_DAYS` = 252)를 두었다(테스트가 짧은 창으로 최저값 · 날짜를 고정하려고). 상관이 정의되지 않는 경우(값 2쌍 미만 · 분산 0)는 None 으로 낸다(numpy 경고 대신 명시). 수익률은 `pct_change` 대신 `종가 ÷ 전날 종가 − 1` 로 계산한다(결측을 앞 값으로 메우는 기본값을 피함). 날짜 순서 검사는 `proxy_series` 의 비공개 함수를 가져오지 않고 모듈 안에 같은 모양으로 두었다(PyRight strict 의 비공개 사용 금지)
- 2026-10-05 09:30: Phase 2 다운로드 — `git status storage/` 깨끗한 상태에서 10종 전부 exit=0. 시작일 · 끝날 · 행 수가 사전 확인과 모두 같다: VGTSX 1996-04-29 · 7,657 / VTMGX 1999-08-17 · 6,824 / VEIEX 1994-05-04 · 8,159 / VGSIX 1996-05-13 · 7,647 / VUSTX 1986-05-19 · 10,172 / VFITX 1991-10-28 · 8,795 / VFISX 1991-10-28 · 8,795 / VIPSX 2000-06-29 · 6,604 / ^SPGSCI 1984-01-03 · 10,771 / GC=F 2000-08-30 · 6,548 (끝 전부 2026-10-02)
- 2026-10-05 09:30: 생성 · 실측 검증 (스크래치 `verify_long_proxy.py`)
  - 생성: SSO_proxy 1999-01-04 – 2026-09-24 · 6,974행 / QLD_proxy 1999-03-10 – 2026-09-24 · 6,929 / BIL_proxy 1999-01-04 – 2026-09-24 · 6,974 / DBC_synthetic 1984-01-03 – 2026-10-02 · 10,771
  - 이음매 종가 = 실물 종가: SSO 2006-06-21 3.637148 · QLD 0.982446 · BIL 2007-05-30 69.960968 · DBC 2006-02-06 19.185097 (4개 모두 같음). 스케일(메타) SSO 5.418769
  - 2배 합성 수익률 − `simulate` 직접 호출 수익률 최대 |차이|: SSO 6.564e-07 · QLD 2.464e-06 (6자리 반올림 수준, 날짜 같음). 최저 종가 QLD 0.302408 · SSO 0.821395 (2009-03-09)
  - BIL 금리 누적 수익률 − 산식 최대 |차이| 1.791e-08 (첫 금리 0.0463, 마지막 0.0363)
  - 원자재: 이음매 2006-02-06 이후 5,197줄 = DBC CSV 줄(바이트, 머리글 포함), 이음매 앞 5,574행 거래량 0, GSCI 수익률 최대 |차이| 1.459e-07
  - 생성 2회차 shasum 4개 동일. `meta.json` 은 `long_proxy_series` 키 추가뿐(기존 키 변경 0, 실행 2회라 항목 2개)
- 2026-10-05 09:30: 비교 계산 — 계획과 달라진 점: 표 열 이름(`DISPLAY_*`)과 행 변환 함수 `pair_summary_record` · `period_summary_records`, `PairSummary.cagr_diff` · `mdd_diff` 를 `src` 비교 모듈에 더했다(테스트 2개) — 계산 스크립트(CSV)와 대시보드가 같은 열 · 같은 값을 쓰게 하려고. 결과 summary 21쌍 · periods 665행. S7 과 끝날이 같은 4쌍(SSO · QLD · GC=F → GLD · VUSTX → TLT)의 일간 · 월간 상관 · CAGR · MDD 가 S7 값과 모두 같다. 2회차 shasum 2개 동일, `storage/results` 변경은 `meta.json` · `proxy_comparison/` 뿐
- 2026-10-05 09:30: 확인 지점 1 보고 — 요약 표(쌍별 전체 지표 · 상관이 가장 낮은 구간)를 대화에 냈다. 눈에 띈 것: 상장 전 교차 확인 3쌍의 12개월 상관이 모두 2005-06-14 에 0.72 – 0.76 으로 떨어진다(월간은 0.978 – 0.9952, 원인 미확인 — 해외 뮤추얼 기준가 시각 차이로 보임). `DBC_synthetic → PDBC` 는 비교 기간이 PDBC 상장 뒤라 `DBC → PDBC` 와 같다
- 2026-10-05 09:32: Phase 3 대시보드 작성 — 계획과 달라진 점 2건. ① 등록 쌍의 기간별 표도 `periods.csv` 를 읽지 않고 직접 고른 쌍과 같은 `src` 함수로 즉석 계산한다(경로가 하나라 등록 · 직접 고르기가 같은 화면을 쓴다). `periods.csv` 는 숫자 기록 · 에이전트 조회용으로 남는다. ② 열 종류(상관 = 비율, 나머지 = %) 목록 `RATIO_DISPLAY_COLUMNS` · `PERCENT_DISPLAY_COLUMNS` 를 `src` 비교 모듈에 두어 스크립트와 대시보드가 같이 쓴다(자릿수 상수는 CLI 가 고른다). 이 리팩터 뒤 비교 CSV 를 다시 만들어 바이트 동일을 확인했다
  - `summarize_pair` 의 최저 날짜를 `idxmin` 대신 `np.argmin` 위치로 찾게 고쳤다 — `idxmin` 반환 타입이 날짜로 추론되지 않아 PyRight 오류(값 · 테스트 결과 동일, 70 passed)
  - **규칙 이탈 기록**: 위 PyRight 오류는 새 파일들에 Ruff · PyRight 를 직접 돌려 찾았다. 이 저장소는 중간 Phase 에서 직접 실행은 pytest 만 허용한다(전역 python 규칙 · 고정 규칙 「품질 검증은 마지막 Phase 에서만」). 이후로는 마지막 Phase 의 `validate_project.py` 로만 검사한다
- 2026-10-05 09:51: 확인 지점 2 — 사용자가 「화면으로 전체를 보기 힘들다, 실제로 쓸 대체 중 전체 · 연도별 · 국면별 특이사항만」을 요청. 결과를 보기 전에 기준을 고정해 CSV 에서 뽑았다(스크래치 `flag_notables.py`) — 대상: 대체 판 13쌍 + 교차 확인 4쌍. 전체 특이 = 월간 상관 < 0.99 · |CAGR 차| ≥ 0.2%p · |MDD 차| ≥ 2%p · 12개월 상관 최저 < 0.8, 연도 · 국면 특이 = |수익률 차| ≥ 2%p · 일간 상관 < 그 쌍 전체 일간 상관 − 0.1
  - 걸린 것 없음 · 무시 수준: QLD 합성 · VTMGX · VGSIX · VGTSX, SSO 합성(미국 약세 2009-11 294.43 / 296.46), VEIEX(CAGR 차 -0.26)
  - 수준 차이: GC=F 연 +0.48%p, BIL 합성 연 +0.19%p(일간 상관은 잡음), VFISX 일간 상관만 낮음
  - 주의: VUSTX → TLT 2008 22.55 / 33.95(-11.4) · 2009 -11.98 / -21.81(+9.82) · 금융위기 -4.91 · 미국 약세 2009-11 +6.41 / VFITX → IEF MDD -15.48 / -23.92 · 2011 -5.84 · 2022 +4.73 / ^SPGSCI → DBC 2009 +34.12 · 2008 -11.0 · 미국 약세 2009-11 +56.68(대체 판에서는 2006-02 이전만 씀, 그 구간은 대조 불가) / VIPSX → TIP 2008 -2.83 / 0.05(HAA 피신 신호라 부호 차이가 판단을 바꿀 수 있음)
  - 판단거리(④-2 로 넘김): 대체 판이 실물이 2002 부터 있는 TLT · IEF 까지 전 기간 대체라 2008 의 TLT 방어 효과가 약하게 나온다 — 「대체만으로 돌린 세계」 대 「실물이 생기면 실물로 잇는 긴 판」
- 2026-10-05 10:21: 사용자 결정 — 대체 판은 전 기간 대체 그대로(완전 실물판과 다를 수 있음을 사용자가 인지). 설계서 D59. 사용자 질문 「이어 붙인 판의 SHY → BIL 월간 상관 0.3312 를 써도 되나」에 답함 — 이어 붙인 판은 2007-06-22 시작이라 BIL 매매는 전부 실물(BIL 상장 2007-05-30), SHY 가격은 HAA 점수 계산 기간에만 231번 중 11번 섞인다(D49). BIL 쌍 관문(SHY 를 BIL 자리에 전 구간, 2008-05-29 부터 220달)에서 신호 일치율 0.9955 · 판정 일치 7/7(`proxy_gate.csv`)
- 2026-10-05 10:23: 사용자 「진행」 — 확인 지점 2 를 특이사항 요약으로 확인한 것으로 하고 마지막 Phase 착수. 대시보드 자체에 대한 수정 요청은 없었다
- 2026-10-05 10:40: 마지막 Phase — 문서 갱신(`docs/COMMANDS.md` · `scripts/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/CLAUDE.md` · 루트 `CLAUDE.md` 입력 반올림 지점 표 · README), 근거 승격(설계서 8.4 · D60 · 10장 · 13장 · 0.2 · 0.3 · 15장 S7), black 4개 파일 재포맷
- 2026-10-05 10:40: `/code-review xhigh` 1회차 — 발견 15건. 무게 분류(`/impl-plan` 「버그의 무게」 · 「닿는가」)
  - 무거움 · 수정 (1) `scripts/data/generate_long_proxy_series.py` `main` — 2배 합성 시작을 금리 파일 첫 달로만 정해, 금리 파일을 1999 앞으로 늘리면(데이터 확장 계기) 운용보수 사전(1999-01 부터 고정) 부족으로 `simulate` 가 멈춘다(죽는다). 모양: 「입력 둘이 각자 기간을 갖는데 시작을 하나에서만 정한다」 — diff 에서 1곳(금리 누적은 금리만 쓰므로 해당 없음). 금리 · 운용보수가 둘 다 있는 첫 달로 고쳤다. 생성 파일 4개 shasum 동일(지금은 둘 다 1999-01)
  - 무거움 · 수정 (2) `src/qbt/utils/proxy_comparison.py` `summarize_pair` · `summarize_periods` · `rolling_correlation` — 입력 표의 열 · 날짜 순서를 검사하지 않아, 날짜가 어긋난 표를 받으면 전날 종가 · 월 묶음이 조용히 틀린다(검사가 약해 틀린 수익률이 통과 — 「비켜 간다」). 모양: 「공개 비교 함수가 align_closes 결과라는 전제를 확인하지 않음」 — 3곳 모두 `_require_aligned` 로. 테스트 6개 추가, 변형(날짜 순서 검사를 뺌) → 3 failed, 복원 후 사본과 동일 · 76 passed, 비교 CSV shasum 동일
  - 무거움 · 사용자에게 올림 (3) `DBC_synthetic_max.csv` 의 2006-02 이전 구간인 ^SPGSCI 는 S&P GSCI **현물** 지수로 보인다(Yahoo 이름 「S&P GSCI」, 총수익 지수는 별도 티커 ^SPGSCITR · 과거 데이터 없음). 선물 교체 손익과 담보 이자가 빠져 투자 수익과 체계적으로 다르다 — 2009 50.3% / DBC 16.19%(콘탱고 해에 현물이 큼), 2022 8.71% / 19.34%. 데이터 선택(D58 ①) 문제라 코드로 고치지 않고 사용자 판단을 받는다
  - 무거움 · 닿지 않음 (4) `build_rate_accrual_series` 가 금리 범위를 보지 않아 % 단위(5.0) · inf 금리가 통과한다 — 금리 파일 단위를 사람이 바꿔야 생긴다(같은 파일을 쓰는 TQQQ 합성도 함께 틀린다). 거름 기준 1
  - 가벼움 · 고치지 않음 (5) `_correlation` 의 분산 0 판정이 `std == 0.0` 정확 비교라 0 이 아닌 상수 수익률이면 None 대신 약 0 — 저장 파일은 6자리 반올림이라 수익률이 정확히 일정하지 않다(지금 산출물 0건, 거름 기준 1) (6) 대시보드가 행 0개인 `summary.csv` 에서 `int(None)` 오류 — 막는 쪽, 지금 0건(거름 기준 2)
  - 그 외 9 — 목록만: 일부만 겹친 국면을 자른 범위로 이름 그대로 냄(실제 날짜 · 거래일 수는 표에 있음, `phase_metrics` 는 None 으로 뺌) · 월간 상관의 마지막 부분 월 포함(8.3 과 같은 정의, docstring 불완전) · 금리 누적 날짜 오류 메시지의 조치 안내가 맞지 않음 · 대시보드 요약 표(과거 계산)와 즉석 계산이 재다운로드 뒤 갈릴 수 있음 · `align_closes` 가 `extract_overlap_period` 를 다시 구현했고 시작 · 끝 필터는 교집합이 이미 보장 · 날짜 순서 검사 함수 중복 · 반올림 · 국면 변환 · 이름 규칙 두 벌 · 대시보드 재계산 두 번(성능) · 시세 비교 도구가 `supplement_experiment` 를 import
- 2026-10-05 11:01: `/code-review xhigh` 2회차 — 발견 15건
  - 무거움 · 수정 (1) `scripts/data/generate_proxy_comparison.py` `PAIRS` — 「상장 전 교차 확인」 쌍을 전 구간으로 재 요약 수치 대부분(76.5% · 66.8% · 91.9%)이 실물 상장 뒤에서 나왔는데 대시보드는 「실물이 없는 구간의 비교」라고 설명(확인 안 된 것을 확인됐다고 함). 모양: 「묶음 이름이 약속한 구간과 실제 비교 구간이 다름」 — 교차 확인 3쌍. `align_closes(before=)` 를 더하고 쌍마다 실물 경로를 넣어 상장 전까지만 잰다. 요약 CSV 에 「비교 제한(이날 앞까지)」 열, 대시보드는 등록 쌍을 고를 때 그 값을 넘긴다. 테스트 2개
  - 무거움 · 수정 (2) 같은 파일 — 대체 판 묶음의 `DBC_synthetic → PDBC` 가 이어 붙인 판의 `DBC → PDBC` 와 수치가 같다(비교가 PDBC 상장 뒤라 GSCI 구간을 한 번도 안 잼). 모양: 「대체 판 쌍의 비교 구간에 대체가 들어가지 않음」 — 이 1쌍(나머지 대체 판 쌍은 원본 시세 · 전 구간 합성이라 해당 없음). `^SPGSCI → DBC` 로 바꾸고 교차 확인 묶음에서 옮김 → 20쌍
  - 가벼움 · 수정 (3) `scripts/data/app_proxy_comparison.py` `_overlay_chart` — 날짜 합집합의 NaN 에서 선이 끊긴다(지금 GC=F → GLD 16군데). `connectgaps=True`
  - 닿지 않음: `_correlation` 의 `std == 0.0` 정확 비교(1회차와 같음) · 금리 inf 통과(1회차와 같음) · `_require_aligned` 가 `normalized_overlay` 결과(같은 열 · NaN)를 통과시킴 — 1회차 수정 자리이고 새 호출 코드가 있어야 생긴다
  - 그 외 9 — 목록만: 월간 상관의 마지막 부분 월 · 차이 열이 반올림 전 값의 차이라 반올림된 두 값의 차와 끝자리가 다를 수 있음 · 금리 누적 오류 메시지 · `align_closes` 의 시작 · 끝 필터 무효과 · `_save_price_csv` · `_describe` 복사 · 날짜 검사 중복 · 반올림 함수 두 벌 · 요약 파일 이름 · 인코딩이 스크립트와 대시보드에 따로(상수 중복) · 대시보드 재계산 두 번
  - 수정 전 사본(스크래치 `r2/`) → 테스트 78 passed, 비교 CSV 재생성(20쌍 · 기간 559행, 두 번 실행 shasum 동일). S7 과 같은 4쌍 값 그대로. 교차 확인 3쌍은 실물 상장 전만: VTMGX → EFA 2001-08-27 – 2007-07-25 월간 0.9884 · CAGR 13.26 / 13.22, VGTSX → VXUS_proxy 2003-04-14 – 2011-01-27 0.9951 · 12.91 / 14.04(-1.13), VEIEX → EEM 2003-04-14 – 2005-03-09 0.9622 · 52.78 / 51.53
- 2026-10-05 11:01: 수정분 검증(맥락 없는 서브에이전트, 수정분과 겨냥한 지적만) — hunk 15개 전부 ① · ② · ③ 답. before 를 주지 않으면 20쌍 `align_closes` 결과가 수정 전과 같고 교차 확인이 아닌 17쌍의 `summarize_pair` 도 같다(실측). 발견 9건: 무거움 1 = 설계서 8.4 가 수정 전 수치(21쌍 · 교차 확인 전 구간)를 「summary.csv 그대로」라고 실음 → 코드 수정이 아니라 근거 승격을 새 CSV 로 다시 했다(8.4 표 20행 · 교차 확인 문장 · D60 ⑥ · `src/qbt/utils/CLAUDE.md`). 가벼움 8 — 고치지 않음: before 로 다 잘렸을 때 오류 메시지가 before 를 말하지 않음(멈춤) · 교차 확인 쌍에 실물 경로가 있어야 한다는 것을 강제하는 장치 없음(지금 0건, 쌍을 잘못 더하면 전 구간 비교가 에러 없이 나감) · 주석이 VEIEX/EEM 에 반만 맞음 · 열 없는 옛 summary.csv 로 대시보드 KeyError(멈춤) · 잘린 끝의 부분 국면 · 교차 확인 겹쳐 그리기에 before 세로선 없음 · connectgaps 가 진짜 공백도 이음(지금 최대 공백 7일) · `DBC_synthetic_max.csv` 를 읽는 쌍이 없어짐. 이 서브에이전트가 돌린 품질 검증은 Ruff · PyRight 통과 · Pytest 797 passed 라고 보고(내 실행 기록은 Validation 에)
- 2026-10-05 11:01: 2회차에 무거운 버그가 나와 규칙대로 멈추고 사용자에게 보고 — 3회차 여부와 ^SPGSCI 처리(1회차 무거움 (3), 설계서 0.4)를 묻는다
- 2026-10-05 11:02: Stop 훅(계획서 미완료 종료 검사)이 걸려, 훅 안내대로 상태를 「사용자 결정 대기」로 바꿨다 — 사용자 답 전에는 Done · 커밋 후보로 넘어가지 않는다(3회차 여부는 사용자가 정한다)
- 2026-10-05 11:06: 사용자 「추천대로」 — ^SPGSCI 는 그대로 쓰고 한계로 기록(설계서 D61, 8.4 · 13장), 3회차 리뷰는 돌리지 않음. 리뷰 수정 뒤 black 재적용(1개 파일, 포맷만) → 생성 파일 4개 shasum 동일, 품질 검증 passed=797 · failed=0 · skipped=0
- 2026-10-05 11:06: 미룬 지적 옮기기 — 옮김 1건: 2회차 수정분 검증의 「교차 확인 쌍을 상장 전까지 자르도록 강제하는 장치 없음」(무거운 모양, 계기 = `PAIRS` 상수에 교차 확인 쌍 추가, 지금 0건) → `docs/DEFERRED_FINDINGS.md`. 사용자가 받아들인 것: ^SPGSCI 현물 지수(D61) — 옮기지 않음. 거른 것(기준 번호 · 근거):
  - 1회차 (4) · 2회차 같은 지적 — 금리 % 단위 · inf 통과: 기준 1(금리 파일 단위를 사람이 바꿔야 생김, 같은 파일의 TQQQ 합성도 함께 틀림)
  - 1회차 (5) · 2회차 같은 지적 — `std == 0.0` 정확 비교: 기준 1(저장 파일이 6자리 반올림이라 수익률이 정확히 일정하지 않음, 지금 0건)
  - 1회차 (6) — 행 0개 summary.csv 의 `int(None)`: 기준 2(멈춤, 지금 0건)
  - 2회차 — `_require_aligned` 가 `normalized_overlay` 결과를 통과시킴: 기준 1(새 호출 코드가 있어야 생김)
  - 수정분 검증 — before 로 다 잘렸을 때 메시지 · 열 없는 옛 summary.csv 의 KeyError: 기준 2(멈춤) / 주석이 VEIEX · EEM 에 반만 맞음 · 잘린 끝의 부분 국면(날짜 · 거래일 수는 표에 있음) · before 세로선 없음 · connectgaps 가 진짜 공백도 이음(지금 최대 공백 7일) · DBC_synthetic 을 읽는 쌍 없음: 기준 3(그 외)
  - 1 · 2회차 그 외 18건: 기준 3
  - 이 계획서가 `docs/DEFERRED_FINDINGS.md` 의 항목을 고친 것은 없다
