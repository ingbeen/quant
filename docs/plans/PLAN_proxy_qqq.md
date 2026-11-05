# Implementation Plan: QQQ 상장 전 구간을 나스닥100 지수로 채운 1배 합성 시세와 합성 생성 스크립트 하나로 합치기 (합성 시세 연장 계획 1)

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-11-05 09:19
**마지막 업데이트**: 2026-11-05 10:02
**관련 범위**: utils(대용 시세 · 대용 비교), scripts/data(다운로드 · 합성 생성), storage(stock · results), docs
**관련 문서**: CLAUDE.md, docs/MEMORY.md, docs/CLAUDE.md, docs/COMMANDS.md, README.md, scripts/CLAUDE.md, src/qbt/CLAUDE.md, src/qbt/utils/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, tests/CLAUDE.md, docs/DEFERRED_FINDINGS.md, docs/research/합성_시세_연장.md

---

## 1) 목표(Goal)

- [x] 목표 1: `^NDX`(나스닥100 지수, 1985-10-01 부터)를 받아 `QQQ_synthetic_max.csv` 를 만든다 — 이음매(실물 QQQ 첫 거래일 1999-03-10) 앞은 그날 종가 비율로 맞춘 지수이고 시가는 그날 종가(결정 3), 그날부터는 `QQQ_max.csv` 행 그대로
- [x] 목표 2: 합성 시세를 스크립트 하나(`scripts/data/generate_synthetic.py`)가 모두 만든다 — QQQ 1배 대용 합성과 기존 QLD · TQQQ 합성. 기존 `scripts/tqqq/generate_synthetic.py` 는 옮기며 지운다. 사용자는 새 시세를 받을 때 `download_data.py`(인자 없음)와 이 스크립트 둘만 돌린다 (사용자 요청 2026-11-05)
- [x] 목표 3: 생성할 때마다 검증 ①(지수 ↔ 실물 QQQ, 겹치는 기간)을 CSV 로 저장하고 콘솔에 직전 저장값과 나란히 낸다. 불변 조건 ⑥(이음매 뒤 행 = 실물)을 어기면 저장 전에 멈춘다 — 검증 숫자로는 멈추지 않는다(결정 9)
- [x] 목표 4: 결정 · 측정 · 재는 법을 연구 문서로 옮겨, 이 계획서와 `HANDOFF.md` 를 지워도 잃는 것이 없게 한다

## 2) 비목표(Non-Goals)

- QLD · TQQQ 합성을 `QQQ_synthetic_max.csv` 기준으로 늘리기, 1999년 전 금리, 상품 하나의 레버리지 합성을 `src/qbt/tqqq` 로 옮기기(`docs/DEFERRED_FINDINGS.md` 의 합성 스크립트 항목) — 계획 2. 이 계획은 레버리지 합성 코드를 새 스크립트로 «그대로» 옮기고, 그 코드는 계속 `QQQ_max.csv` 를 읽는다
- 기존 전략 · 포트폴리오가 새 파일을 읽게 바꾸기 — 계획 5 (결정 10). 이 계획 뒤에도 모든 러너는 지금 파일을 읽는다
- 나스닥100 지수의 배당 보정 — 하지 않는다 (결정 2)
- 대시보드 — 두지 않는다 (결정 9)
- `^NDX` 말고 다른 시세 다시 받기 — 결과 변화의 원인을 가를 수 없게 된다(루트 `CLAUDE.md`)
- 검증 ⑤ 를 저장소 코드로 남기기 — S1
- `splice_proxy` 고치기 — 합성 TQQQ · QLD 가 쓰고, 그 상장 전 구간은 실물 QQQ 의 진짜 시가로 만든 것이라 바뀌면 안 된다
- 완료된 계획서(`PLAN_q2_2xs_lightweight.md`)의 옛 경로 — 그때의 기록이라 고치지 않는다
- git 조작 — 커밋은 사용자가 한다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 사용자 요청(2026-11-04): 「최대한 테스트 기간을 늘리는게 중요해」 · 「일단 QQQ를 나스닥100지수와 비교해서 QQQ_synthetic_max를 만들고」 · 「기존 TQQQ_synthetic_max 만드는것처럼 기존etf와의 얼마나 동일한지 항상 검증이 들어가야돼」. 지금 QQQ 계열 버퍼존은 1999-12-21 에 시작한다(연구 문서 1장)
- 사용자 요청(2026-11-05, 계획 승인과 함께): 「특정 스크립트 하나만 실행하면 시뮬레이션 실행될수 있도록 했으면 좋겠어. 즉, 나는 새로운 데이터를 받을때 download_data.py와 특정 스크립트만 실행할꺼야.」 · 「특정 스크립틑 기존 QLD, TQQQ도 같이.」 · 「그리고 만약 generate_synthetic에 통합하든 generate_synthetic를 지우든 하자.」
- 범위는 연구 문서 7장 1행 — 1배 대용 부품과 검증 ① · ⑤ · ⑥, `^NDX` 받기, `QQQ_synthetic_max.csv`, 결정 3 측정과 확정 — 에 위 2026-11-05 요청을 더한 것이다. `HANDOFF.md` 4절의 「모든 계획」 · 「계획 1」 항목은 Risks 에 넣었다
- 이 계획이 만든 1배 부품(이어 붙이기 · 시가 처리 · ⑥ 검사 · ① 비교)을 계획 3(SPY ← VFINX) · 계획 4(TLT ← VUSTX)가 대상 표에 한 줄씩 더해 쓴다

### 스크립트 자리 — 옮기고 지운다 (R1)

- 사용자가 두 안을 모두 허락했다(「통합하든 … 지우든」). `scripts/data/generate_synthetic.py` 로 옮겨 합치고 `scripts/tqqq/`(그 파일 하나뿐)를 지운다 — 사용자가 돌릴 두 스크립트가 `scripts/data/` 에 모이고, 1배 합성까지 만드는 스크립트가 `tqqq/` 에 있으면 폴더 이름이 틀린다
- 옛 경로를 가리키는 곳 (2026-11-05 `git grep`): `docs/COMMANDS.md` 2줄, `docs/DEFERRED_FINDINGS.md` 1줄(합성 스크립트 항목의 자리), `scripts/CLAUDE.md` 1줄(스크립트 지도), 스크립트 자기 docstring, 완료 계획서 `PLAN_q2_2xs_lightweight.md` 2줄(고치지 않음), `HANDOFF.md` 1줄. 설정 파일(`pyproject` · `pyrightconfig` · `validate_project.py`)은 가리키지 않는다
- 새 스크립트가 읽는 시세는 모두 `DEFAULT_TICKERS` 에 있어야 사용자의 두 단계가 끝까지 간다 — 지금 읽는 것은 `QQQ` · `TQQQ` · `QLD`(목록에 있음)와 `^NDX`(S3 로 넣는다). 지금 `storage/stock` 의 원본 시세는 `DEFAULT_TICKERS` + `^NDX` 와 같다

### 착수 전 측정 (2026-11-05, scratchpad — 저장소 파일은 읽기만)

측정 코드는 `/private/tmp/claude-501/-Users-yubeen-Workspace-quant/b3c545e6-a18d-47fc-9b23-c4a00361bfc8/scratchpad/probe/` 에 있다(임시 — 재는 법은 근거 승격 때 연구 문서 9장으로 옮긴다).

**`^NDX` 의 사실** — yfinance `history(period="max")` 그대로 2026-11-05 에 받았다.

- 10,354행, 1985-10-01 ~ 2026-11-04. 이음매 1999-03-10 이 있고, 그 앞이 3,396행(1985-10-01 ~ 1999-03-09)이다
- 이음매 앞: 시가 = 전날 종가(상대 차 1e-6 미만)인 날 2,974 / 3,395 (87.6%). 시가 · 종가가 고가 · 저가 밖인 날 0. **전날 종가가 그날 고가 · 저가 밖인 날 117** — 시가를 전날 종가로 바꾸면 그 117일은 시가가 고가 · 저가 밖에 놓인다
- 전 구간: 가격 0 이하 · 결측 · 중복 날짜 0, 하루 50% 이상 움직인 날 0 (최대 18.77%, 2001-01-03) — 다운로더의 급등락 검사를 통과한다
- 다시 받아도 과거 값이 그대로다 — `ee6d23d` 에 있던 `^NDX_max.csv`(2026-11-01 커밋, 1985-10-01 ~ 2026-10-30, 10,351행)와 오늘 받은 값(6자리 반올림)이 10,351일 모두 시가 · 고가 · 저가 · 종가 · 거래량까지 같다. 지수라 배당 조정이 없다

**검증 ① 재현** — `ee6d23d` 의 `proxy_comparison.py` 를 그대로 불러 저장소 `QQQ_max.csv` 와 견줬다. 연구 문서 5.1 의 `^NDX ↔ QQQ` 행과 모든 값이 같다.

| 겹치는 기간 | 일간 상관 | 월간 상관 | 연 수익 (지수 / QQQ) | 최악 낙폭 (지수 / QQQ) | 12개월 상관 최저 |
|---|---|---|---|---|---|
| 1999-03-10 ~ 2026-10-29 (6,954일) | 0.98037 | 0.99930 | 10.14% / 10.71% | -82.90% / -82.96% | 0.9326 (2000-12-11) |

연도별 일간 상관이 가장 낮은 해는 2000 (0.9347) · 1999 (0.9650) · 2004 (0.9753) 다.

**검증 ⑤ — 시가만 바꿔 버퍼존 4P 를 돌렸다.** 저장소 엔진 `run_buffer_strategy` · `FIXED_4P_*`, 신호는 저장소 QQQ 종가(이동평균은 자르기 전 전체 기간으로 계산), 매매 시세는 1배 `QQQ_max.csv` · 2배 `QLD_synthetic_max.csv` · 3배 `TQQQ_synthetic_max.csv` 이고 그 시가 칸만 바꿨다. 세 방식 모두 거래 12건 · 신호 날짜가 같다 — 신호는 종가로 내므로 체결 가격만 달라진다. 괄호는 실제 시가 대비 차이(%p).

2004-01-02 ~ 2026-10-29 (실제 시가가 있는 구간):

| 시가 칸 | 1배 연 수익 | 1배 최악 낙폭 | 2배 연 수익 | 2배 최악 낙폭 | 3배 연 수익 | 3배 최악 낙폭 |
|---|---|---|---|---|---|---|
| 실제 시가 | 10.44% | -26.43% | 16.48% | -46.37% | 20.37% | -62.09% |
| 시가 = 그날 종가 | 9.97% (-0.47) | -27.71% (-1.28) | 15.56% (-0.92) | -48.35% (-1.98) | 18.91% (-1.46) | -63.56% (-1.47) |
| 시가 = 전날 종가 | 10.22% (-0.22) | -29.50% (-3.07) | 16.08% (-0.40) | -51.48% (-5.11) | 19.88% (-0.49) | -67.57% (-5.48) |

1986-07-16 ~ 1999-03-09 (이 계획이 채울 구간, `^NDX` 1배, 거래 9건 — 진짜 시가가 없어 정답이 없다):

| 시가 칸 | 연 수익 | 최악 낙폭 |
|---|---|---|
| 받은 그대로 | 12.65% | -36.29% |
| 시가 = 그날 종가 | 10.90% | -42.18% |
| 시가 = 전날 종가 | 12.69% | -36.40% |

- 「받은 그대로」는 그 구간에서 「전날 종가」와 거의 같다(87.6% 의 날이 같은 값이라)
- 2004년 이후 「전날 종가」의 깊은 낙폭은 폭락한 날 종가에 판 두 번에서 나온다 — 2015-08-24 신호 (1배 거래 손익 실제 +82.67% → +76.18%), 2020-03-12 신호 (1배 +4.42% → -1.32%, 3배 -8.03% → -21.93%). 실제로는 다음 날 아침 반등한 시가에 팔렸다
- 1배 거래별 진입가 대비 손익 (실제 / 그날 종가 / 전날 종가, %): -7.87 / -7.48 / -6.37 · 2.12 / 3.43 / 4.28 · 10.95 / 8.91 / 10.63 · 20.13 / 17.36 / 21.05 · 6.63 / 10.46 / 5.74 · 82.67 / 75.16 / 76.18 · -10.13 / -8.85 / -10.89 · 44.51 / 46.40 / 48.16 · 4.42 / 5.39 / -1.32 · 65.80 / 62.35 / 60.68 · 45.58 / 37.53 / 49.68 · 8.85 / 6.93 / 8.22

### 지운 코드 되살리기 — 호출처 · 지운 이유 (전역 「기존 함수 재사용 전 검증」)

- `ee6d23d` 의 `src/qbt/utils/proxy_comparison.py`: 그 시점 호출처는 `scripts/data/generate_proxy_comparison.py`(계산) · `app_proxy_comparison.py`(표시) 둘이다. 둘 다 `b53ec85` 경량화에서 보완 전략(부록 M) 묶음과 함께 지웠다 — 함수 결함이 아니라 쓰던 묶음의 철회다. 지금 코드와 맞춰 봤다: 가져다 쓰는 `require_strictly_increasing_dates` · `ANNUAL_DAYS` · `ROUND_PERCENT` · `ROUND_RATIO` · `TRADING_DAYS_PER_YEAR` 는 그대로 있고, 위 재현이 5.1 과 같다
- 되살리지 않는 것: `normalized_overlay`(대시보드 전용 — 결정 9 로 대시보드가 없다), `align_closes` 의 `before`(상장 전 교차 확인 쌍 전용 — 계획 1 ~ 4 의 대조는 모두 실물과 직접 한다), 국면 표 `PHASE_WINDOWS`(지운 보완 실험의 것 — S2), 스크립트의 묶음 · 쌍 표
- 표시 이름은 연구 문서 용어로 바꾼다 — 「대체 · 기준」 → 「대용 · 실물」
- 겹치는 날 맞추기는 이미 `utils/data_loader.py` 의 `extract_overlap_period`(src 호출처 1: `load_signal_trade_pair`)가 한다. 되살리는 `align_closes` 는 두 종가를 한 표로 묶고 2일 미만이면 멈추는 일까지 해 비교 함수 다섯이 그 표를 받는다 — 되살린 그대로 둔다(5.1 재현이 이 코드로 맞았다)
- `splice_proxy`(지금 호출처 1: `scripts/tqqq/generate_synthetic.py`, 테스트 `test_proxy_series.py`)는 그대로 쓰고 고치지 않는다 — 시가는 이어 붙이기 «전에» 대용 쪽에서 바꾼다
- `run_buffer_strategy`(직접 호출 1: `scripts/backtest/run_param_plateau_all.py`, 테스트 4개 파일)는 ⑤ 측정에만 썼다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절, 「스크립트 실행 규칙」, 「가격 반올림 자릿수」, `docs/MEMORY.md`
- `docs/CLAUDE.md` · `scripts/CLAUDE.md` · `src/qbt/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `src/qbt/tqqq/CLAUDE.md` · `tests/CLAUDE.md`
- 전역 `~/.claude/rules/python.md` · `~/.claude/rules/python-tests.md`
- `docs/research/합성_시세_연장.md` — 3장 결정 · 5장 검증 설계 · 6장 사실 · 9장 재현 방법

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] `storage/stock/^NDX_max.csv` 를 `download_data.py "^NDX"` 로 받았다 — 다른 시세는 받지 않았다 (10,353행, 1985-10-01 ~ 2026-11-03)
- [x] 합성 시세를 `scripts/data/generate_synthetic.py` 하나가 모두 만든다 — `scripts/tqqq/` 가 없고, 옛 경로를 가리키는 추적 파일은 완료 계획서와 커밋 `ee6d23d` 안의 경로를 가리키는 기록(`src/qbt/tqqq/CLAUDE.md:55`)뿐이다. 그 스크립트가 읽는 시세가 모두 `DEFAULT_TICKERS` 에 있다(원본 시세 8개 = `DEFAULT_TICKERS` 8개)
- [x] `QQQ_synthetic_max.csv` — 1985-10-01 시작, 행 수가 이음매 앞 `^NDX` 3,396 + `QQQ_max.csv` 6,954 = 10,350 과 같다(따로 센다), 이음매 앞 시가 = 그날 종가 · 거래량 0
- [x] 검증 ⑥ — 저장된 파일의 1999-03-10 이후 줄이 `QQQ_max.csv` 의 데이터 줄과 글자까지 같다(`diff` 0줄). 합성 함수가 이음매 뒤 행이 실물과 다르면 저장 전에 `RuntimeError` 로 멈추는 테스트가 있고, 그 검사를 지우면 테스트가 실패함을 확인했다
- [x] 검증 ① — `storage/results/proxy_validation/` 에 요약 · 연도별 CSV 가 생겼고, 첫 생성의 요약 값이 연구 문서 5.1 의 `^NDX ↔ QQQ` 행과 같다(저장 자릿수 안에서). 두 번째 생성의 콘솔에 직전 값이 이번 값과 나란히 나온다(13줄 모두 「같음」)
- [x] 검증 ⑤ — 측정 결과(Context)를 사용자에게 보였고 결정 3 을 확정받았다 (2026-11-05 「추천대로 진행」 — 시가 = 그날 종가)
- [x] 옮긴 레버리지 합성이 같은 파일을 만든다 — 새 스크립트로 만든 `TQQQ_synthetic_max.csv` · `QLD_synthetic_max.csv` 가 커밋된 파일과 바이트 단위로 같다(`git status` 에 `M` 없음)
- [x] 기존 산출물 불변 — `git status --short storage` 에 새 파일(`??`)만 있고 `M` 0건 (기존 러너가 읽는 시세 · 코드 경로가 바뀌지 않아 러너는 다시 돌리지 않는다)
- [x] 되살린 비교 함수와 새 함수의 테스트가 있다 — `test_proxy_comparison.py` 되살림, `test_proxy_series.py` 의 `TestBuildProxySynthetic` 5건
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 있음(워크플로우 2 · 「시세를 다시 받은 뒤」 ① · ③), `README.md` 변경 있음(기능 한 줄), `scripts/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `docs/DEFERRED_FINDINGS.md`(자리) 변경 있음, 루트 `CLAUDE.md` 변경 있음(디렉터리 구조 한 줄), `src/qbt/CLAUDE.md` 변경 있음(시세 파일 이름 한 줄), `src/qbt/tqqq/CLAUDE.md` · `tests/CLAUDE.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (연구 문서 3장 결정 3 · 9 · 11, 5장 ① · ⑤, 6.2 · 6.6 · 6.7, 7장 1행, 8장 두 행, 9장 넷. `HANDOFF.md` 1 · 2 · 4 · 6절. 리뷰가 드러낸 「월별 금리 파일은 손으로 갱신」 틈은 연구 문서 결정 11 · COMMANDS · `scripts/CLAUDE.md` · `HANDOFF.md` 2절)
- [x] 미룬 지적 옮김 — 해당 없음: 고치지 않은 리뷰 지적 13건 중 버그 3건은 거르는 기준 1 · 2, 그 외 10건은 기준 3 이라 옮긴 것이 없다(진행 로그 표). 이 계획서가 그 파일에서 지운 항목은 없고, 합성 스크립트 항목의 자리만 새 경로로 고쳤다(그 항목은 계획 2 가 처리한다)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 새 파일
  - `src/qbt/utils/proxy_comparison.py` — `ee6d23d` 에서 줄여 되살린다 (대용 ↔ 실물 비교 · 연도별 비교 · 표시용 행 · 반올림)
  - `scripts/data/generate_synthetic.py` — 합성 시세 생성 하나: ① 1배 대용 합성(대상 표에 QQQ 한 줄) + 검증 ① 저장 · 표시, ② 레버리지 합성(옛 스크립트 본문을 그대로 옮김)
  - `tests/qbt/test_proxy_comparison.py` — 되살린 함수의 테스트만 되살린다
- 지우는 파일: `scripts/tqqq/generate_synthetic.py` (폴더째)
- 고치는 파일
  - `src/qbt/utils/proxy_series.py` — 대용 합성 한 상품을 만드는 함수(이음매 앞 시가 = 그날 종가 → `splice_proxy` → ⑥ 검사)
  - `src/qbt/common_constants.py` — `NDX_DATA_PATH` · `QQQ_SYNTHETIC_DATA_PATH` · `PROXY_VALIDATION_RESULTS_DIR`
  - `scripts/data/download_data.py` — `DEFAULT_TICKERS` 에 `^NDX` (S3)
  - `tests/qbt/test_proxy_series.py` — 새 함수의 테스트
- 문서: `docs/COMMANDS.md` · `README.md` · `scripts/CLAUDE.md` · `src/qbt/utils/CLAUDE.md` · `docs/DEFERRED_FINDINGS.md` · `docs/research/합성_시세_연장.md` · `HANDOFF.md`(커밋 안 된 임시 문서)
- `docs/COMMANDS.md`: 변경 있음 — 워크플로우 2 를 「합성 시세 (QQQ · QLD · TQQQ)」 명령 하나로, 「시세를 다시 받은 뒤 다시 돌리는 순서」 ① 을 인자 없는 `download_data.py` 로(원본 시세가 모두 `DEFAULT_TICKERS` 에 있다), ③ 블록의 합성 줄을 새 경로로

### 데이터/결과 영향

- 새 시세: `storage/stock/^NDX_max.csv` · `QQQ_synthetic_max.csv`
- 새 결과: `storage/results/proxy_validation/summary.csv`(대상마다 한 행) · `years.csv`(대상 × 연도)
- 기존 시세 · 결과: 바뀌지 않는다 — `TQQQ_synthetic_max.csv` · `QLD_synthetic_max.csv` 는 같은 코드 · 같은 입력으로 다시 만들어 바이트 단위로 같아야 하고, 새 파일을 읽는 러너는 없다

## 6) 단계별 계획(Phases)

### Phase 0 — 테스트 먼저 (레드)

**작업 내용**:

- [x] `tests/qbt/test_proxy_comparison.py` 를 `ee6d23d` 에서 되살린다 — `TestAlignCloses` 의 `before` 3건과 `TestNormalizedOverlay` 2건을 빼고, 표시 이름 상수를 바뀐 이름으로
- [x] `tests/qbt/test_proxy_series.py` 에 새 함수의 테스트 — 이음매 앞 시가 = 그날 종가 / 이음매 앞 고가 · 저가 · 종가 수익률 · 날짜는 대용 그대로 / 이음매부터 실물 행 그대로 / 입력 불변 / 이음매 뒤 행이 실물과 다르면 `RuntimeError`(`splice_proxy` 를 이음매 날 시가를 덮어쓰는 함수로 바꿔치기해 합성 함수를 부른다 — 검사 «호출»을 지워도 잡히게)

**Validation**:

- [x] 새 테스트가 import 실패 또는 실패로 레드 (`pytest` 두 파일만) — 두 파일 모두 수집 단계 `ImportError`

---

### Phase 1 — 구현과 생성 (그린)

**작업 내용**:

- [x] `proxy_comparison.py` 를 줄여 되살린다 (Context 「되살리지 않는 것」 제외, 표시 이름 바꿈)
- [x] `proxy_series.py` 에 대용 합성 함수와 ⑥ 검사를 더한다 — `build_proxy_synthetic` · `_require_rows_from_seam_equal_actual`
- [x] `common_constants.py` 에 경로 상수 셋, `download_data.py` 의 `DEFAULT_TICKERS` 에 `^NDX`
- [x] `scripts/data/generate_synthetic.py` — ① 1배 대용: 대상마다 읽기 → 합성(⑥ 포함) → `save_stock_csv` → 검증 ①(전체 · 연도별) → 모든 대상을 모아 CSV 저장(한글 열 이름이라 `utf-8-sig`) → 저장 전에 읽어 둔 직전 값과 저장한 값을 같은 글자로 나란히 콘솔. ② 레버리지: 옛 스크립트 본문을 그대로 옮긴다(계속 `QQQ_max.csv` 를 읽는다 — 옛 본문과 `diff` 0, 57줄). 1배를 먼저 만든다
- [x] `scripts/tqqq/generate_synthetic.py` 를 지우고 `scripts/tqqq/` 를 없앤다
- [x] `download_data.py "^NDX"` 를 돌리고 새 합성 스크립트를 돌린다 — `^NDX_max.csv` 10,353행(1985-10-01 ~ 2026-11-03), 합성 종료코드 0

**Validation**:

- [x] Phase 0 테스트 통과 (`pytest` 두 파일만) — 56 passed
- [x] `QQQ_synthetic_max.csv` 의 첫날 · 행 수(따로 센 10,350) · 이음매 앞 시가 · 거래량 대조 — 첫날 1985-10-01, 10,350 = `^NDX` 이음매 앞 3,396 + `QQQ_max.csv` 6,954, 이음매 앞 시가 ≠ 종가 0줄 · 거래량 ≠ 0 0줄
- [x] ⑥ — 1999-03-10 이후 줄과 `QQQ_max.csv` 데이터 줄의 `diff` 0줄
- [x] ① — 요약 CSV 값이 5.1 과 같다 (저장 자릿수 안에서: 일간 0.9804 · 월간 0.9993 · CAGR 10.14 / 10.71 · MDD -82.9 / -82.96 · 12개월 최저 0.9326 2000-12-11, 연도별 최저 2000 0.9347 · 1999 0.965 · 2004 0.9753)
- [x] ⑥ 검사를 지운 변형에서 그 테스트가 실패하고, 되돌리면 통과한다 (`PYTHONDONTWRITEBYTECODE=1`) — 검사 호출 줄을 지우면 `test_stops_when_rows_from_seam_differ` 1 failed · 21 passed, 되돌리면 22 passed
- [x] `git status --short storage` 에 새 파일만 있다 — `TQQQ_synthetic_max.csv` · `QLD_synthetic_max.csv` 가 `M` 이 아니다 (`??` 셋: `proxy_validation/` · `QQQ_synthetic_max.csv` · `^NDX_max.csv`)

---

### Phase 2 — 문서와 근거 승격

**작업 내용**:

- [x] `docs/COMMANDS.md` — 워크플로우 2 · 「시세를 다시 받은 뒤」 ① · ③
- [x] `scripts/CLAUDE.md` 스크립트 지도와 규칙 「합성 시세는 모두 `generate_synthetic.py` 하나가 만들고, 야후 원본 시세는 모두 `DEFAULT_TICKERS` 에 둔다」(`tqqq/` 절 삭제), `README.md` 기능 목록 한 줄, `src/qbt/utils/CLAUDE.md` 모듈 지도(`proxy_comparison.py` · `proxy_series.py`)와 규칙(1배 대용 구간 시가), `docs/DEFERRED_FINDINGS.md` 합성 스크립트 항목의 자리(`scripts/data/generate_synthetic.py:234` `_generate_leveraged_synthetics`). 루트 `CLAUDE.md` 변경 있음(디렉터리 구조의 scripts 하위 폴더 `data · backtest`), `src/qbt/CLAUDE.md` 변경 있음(시세 파일 이름의 `_synthetic_max` 설명에 대용 지수), `src/qbt/tqqq/CLAUDE.md` · `tests/CLAUDE.md` 변경 없음(옛 스크립트 경로를 가리키지 않는다 — `tqqq/CLAUDE.md:55` 의 경로는 커밋 `ee6d23d` 안의 기록)
- [x] 연구 문서 — 3장 결정 3(사용자 결정) · 9(기준선 = 직전 저장값) · 11(새 행, 합성 생성 실행), 5장 ① 의 연도별 표 · ⑤ 기준선(6.7), 6.2 `^NDX` 사실 두 줄, 6.6 되살린 코드, 6.7(새 절), 7장 1행, 8장 가짜 시가 · 측정 코드 행, 9장 ① 의 저장소 경로 · ⑥ · 6.2 · 6.7 재는 법
- [x] `HANDOFF.md` — 2절에서 결정 3 행 지우기, 4절 「모든 계획」에 결정 11 규칙 · 계획 2 의 금리 파일 읽는 곳 경로 · 계획 3 의 「UPRO 를 목록에 넣을지」를 결정 11 로, 6절에 2026-11-05 원문과 읽은 뜻 셋 (1절은 Done 때)

---

### 마지막 Phase — 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 자동 포맷 적용 (`poetry run black .`) — 1파일(`proxy_series.py` 의 긴 줄 하나)
- [x] 새 합성 스크립트를 한 번 더 돌려 시세 · 검증 파일이 바이트 단위로 같고, 콘솔의 직전 값이 이번 값과 같은지 본다 — `QQQ` · `TQQQ` · `QLD` 합성과 `summary.csv` · `years.csv` 가 첫 생성 사본과 `cmp` 같음, 콘솔 13줄 모두 「같음」
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 13건 — 버그 3 [무거움 0 · 가벼움 3] · 그 외 10 · 조치: 고칠 것 0 — 회차 종료. 그 외 2건은 문서 · 주석만 고쳤다: 사용자 요청 R1 의 흐름을 틀리게 적은 문장(월별 금리 · 운용비율 갱신을 빠뜨림 — DoD 의 문서 정확성)과 전역 주석 문체 규칙 위반 4줄. 목록은 진행 로그)
- [x] 수정분 검증 — 해당 없음 (리뷰 지적을 버그로 고친 것 없음 · 고친 2건은 문서 문장과 주석이고 동작 변경 없음 — 고친 뒤 테스트 · 품질 검증을 다시 돌림)
- [x] `poetry run python validate_project.py` (passed=744, failed=0, skipped=0 — Ruff · PyRight 통과)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 합성시세 / 나스닥100 지수로 1985년부터 채운 QQQ 합성 시세와 합성 생성 스크립트 통합
2. 합성시세 / QQQ_synthetic_max 생성 · 대용 ↔ 실물 검증 표 저장 · 합성 생성의 scripts/data/generate_synthetic.py 일원화
3. 합성시세 / 다운로드와 합성 생성 두 단계만으로 QQQ · TQQQ · QLD 합성을 갱신하는 흐름 구성
4. 합성시세 / 상장 전 구간 시가를 그날 종가로 둔 1배 대용 합성과 이음매 뒤 실물 불변 검사 추가
5. 합성시세 / 합성 시세 연장 계획 1 — ^NDX 수집, 대용 비교 모듈 복원, 시가 방식 측정의 연구 문서 기록

## 7) 리스크(Risks)

- **다른 시세가 함께 받아지는 위험** — 이 계획에서는 `download_data.py` 를 인자 없이 돌리지 않고 `"^NDX"` 하나만 받는다. 지수의 끝날(2026-11-03)이 실물(2026-10-29)보다 늦어도 합성 파일의 끝날은 이음매 뒤 실물 행이 정한다 (`HANDOFF.md` 4절). 사용자의 두 단계(인자 없는 다운로드)는 결과 비교가 끝난 뒤의 운용 흐름이다
- **옮긴 레버리지 합성이 달라질 위험** — 본문을 그대로 옮기고, 다시 만든 두 파일을 커밋된 파일과 바이트 단위로 대조한다
- **합성 입력이 `DEFAULT_TICKERS` 에서 빠지는 위험** — 빠지면 사용자의 두 단계에서 그 시세만 낡은 채 남고 에러는 없다(지수 · 펀드의 과거 값은 거의 그대로라 끝날만 뒤처진다). 이를 막는 검사는 없다 — 테스트가 scripts 를 부르지 않는다. 규칙을 `scripts/CLAUDE.md` 에 두고 `HANDOFF.md` 4절 「모든 계획」에 넣어 계획 2 ~ 4 가 따르게 한다
- **되살린 코드가 지금 코드와 어긋날 위험** — 가져다 쓰는 이름이 그대로임을 확인했고, 5.1 을 그 코드로 재현했다. `proxy_series.py` 는 `b53ec85` 에서 함수 둘이 빠졌지만 `require_strictly_increasing_dates` 는 그대로다
- **파일 이름 · 경로 규칙** — `{TICKER}_synthetic_max.csv`, 경로 상수는 `common_constants.py` (`src/qbt/CLAUDE.md` 「시세 파일 이름」)
- **검증 숫자가 생성을 막는 위험** — 결정 9 대로 생성을 멈추는 것은 ⑥ 위반뿐이다. ① 은 저장 · 표시만 한다
- **급등락 검사** — 1배 합성은 켠 채 저장한다(`^NDX` 최대 18.77%). 레버리지 합성은 지금처럼 끈다(`check_price_spikes=False`, 옮긴 그대로)
- **대상 표 → 저장 경로 한 줄을 테스트가 지키지 못한다** — `docs/DEFERRED_FINDINGS.md` 의 「합성 스크립트가 상품 표를 저장 경로로 잇는 한 줄」과 같은 모양이다. 1배 합성 한 상품은 src 함수가 만들어 테스트가 지키고, 스크립트에는 표를 도는 줄과 저장 줄만 남긴다. 1배 대상이 하나라 섞일 상대가 없고, 계획 3 에서 SPY 가 붙을 때 다시 본다. 레버리지 쪽은 계획 2 가 그 항목을 처리한다
- **QQQ 를 다시 받으면 대용 구간의 가격 수준이 바뀐다** — QQQ 는 배당 조정으로 과거 종가가 바뀌어 이음매 비율이 달라진다. 수익률은 그대로다. 사용자의 두 단계에서 합성 스크립트가 다시 만든다
- **2004년 이후 측정이 1986 ~ 1999 를 대표하지 못할 위험** — 그래서 채울 구간 자체(`^NDX` 1배)의 세 방식도 함께 보였다. 그 구간에는 정답이 없다(연구 문서 8장 「가짜 시가」)

## 8) 메모(Notes)

### 결정 (사용자 「추천대로 진행」 2026-11-05)

- **Q1. 결정 3 — 1985 ~ 1999 구간의 시가 = 그날 종가.** 그 구간의 나스닥100 지수 기록에는 진짜 시가가 없다(87.6% 의 날 시가 칸이 전날 종가). 버퍼존은 신호 다음 날 시가에 사고팔아 시가 칸이 체결 가격을 정한다. 「그날 종가」는 원칙(「성과를 가장 덜 좋게 만드는 방식」)에 연 수익은 모든 경우, 낙폭은 채울 구간에서 맞는다. 택하지 않은 안: 받은 그대로(채울 구간에서 「전날 종가」와 거의 같다), 전날 종가(2004년 이후 낙폭이 가장 깊지만 폭락한 날 두 번 때문이고, 채울 구간에서는 가장 좋게 잡으며 117일은 시가가 고가 · 저가 밖에 놓인다). 측정은 Context
- **Q2. 콘솔에 나란히 낼 기준선 = 직전 저장값.** 덮어쓰기 전에 지금 있는 검증 CSV 를 읽어 「직전 · 이번」으로 낸다. 숫자가 CSV 한 곳에만 있고 이력은 git 에 있다. 첫 생성은 직전 값이 없어 이 계획서 검증에서 5.1 과 대조한다. 택하지 않은 안: 연구 때 잰 고정값을 코드 상수로(숫자가 두 벌), 기준선 없이 VSCode diff 로
- **S1 ~ S6** (아래) 그대로

### R1. 합성 생성 스크립트 하나 (사용자 요청 2026-11-05)

- 요청 원문은 Context. 사용자가 「통합」과 「지우기」를 모두 허락해, 자리는 `scripts/data/generate_synthetic.py` 로 정했다(Context 「스크립트 자리」)
- 계획서 범위가 넓어졌다 — Goal 2, DoD 2 · 7번째 줄, Scope 의 새 스크립트 · 지우는 파일 · COMMANDS ①, Phase 1 · 2 의 해당 줄, Risks 의 세 줄. 레버리지 합성의 «내용»은 바꾸지 않는다(계획 2)

### 정해 둔 것

- **S1. 검증 ⑤ 는 한 번만 잰다** — 착수 전 측정(위 Context, 저장소 엔진 사용)이 그 기록이고, 숫자와 재는 법을 연구 문서 6 · 9장에 옮긴다. 저장소 코드로 남기지 않는다 — ⑤ 를 맡은 계획은 1 뿐이고(연구 문서 7장), 실물 QQQ 로 재므로 대용을 바꿔도 값이 바뀌지 않는다
- **S2. 검증 ① 의 「국면별 수익 차」를 연도별 표로 낸다** — 지운 국면 표(`PHASE_WINDOWS`)는 보완 실험용이라 11개 중 10개가 2009년 이후에 시작한다. 연도별 표가 연구 문서 6.5 의 「일간 지표는 구간을 나눠 낸다」도 맡는다(2000년 일간 상관 0.9347). 연구 문서 5장 ① 의 「국면별」을 「연도별」로 고친다
- **S3. `^NDX` 를 `DEFAULT_TICKERS` 에 넣는다** — 인자 없는 다운로드가 합성 파일의 재료까지 받게 한다(R1 이 이것을 요구한다). 다시 받아도 과거 값이 그대로임을 확인했다(Context)
- **S4. 이름 · 자리** — 합성 스크립트 `scripts/data/generate_synthetic.py`(R1, 1배 대상 표에 계획 3 · 4 가 한 줄씩 붙는다), 결과 `storage/results/proxy_validation/summary.csv` · `years.csv`
- **S5. ⑤ 는 세전만 냈다** — 전략 성과가 아니라 같은 신호 · 같은 거래 12건에서 체결 가격만 다른 데이터 처리 방식을 고르는 비교라서다
- **S6. 결정 3 의 방식은 대용 구간에만 건다** — 이음매 뒤 실물 행과 기존 합성 TQQQ · QLD 는 그대로다

### 진행 로그 (KST)

- 2026-11-05 09:19: 계획서 작성. 착수 전 측정(Context)은 scratchpad 에서 저장소 엔진 · 파일을 읽기만 해서 했다 — 5.1 재현 일치, ⑤ 측정, `^NDX` 재다운로드 불변 확인. Q1 · Q2 와 계획 승인을 사용자에게 묻고 멈춤
- 2026-11-05 09:33: 사용자 「추천대로 진행하되, 특정 스크립트 하나만 실행하면 시뮬레이션 실행될수 있도록 …」 — Q1 = A(그날 종가) · Q2 = A(직전 저장값) · S1 ~ S6 승인, R1 요청을 범위에 더해 계획서를 고쳤다(무엇이 바뀌었는지는 R1). 상태 In Progress
- 2026-11-05 09:38: Phase 0 — 두 테스트 파일이 수집 단계 `ImportError` 로 레드
- 2026-11-05 09:45: Phase 1 — 구현 뒤 두 파일 56 passed. ⑥ 변형(검사 호출 줄 삭제)에서 `test_stops_when_rows_from_seam_differ` 1 failed, 사본으로 되돌려 `cmp` 같음 · 22 passed. 옮긴 레버리지 본문은 옛 스크립트와 `diff` 0(57줄). `^NDX` 하나만 받아(10,353행) 합성 생성 종료코드 0 — `QQQ_synthetic_max.csv` 10,350행, 이음매 뒤 `diff` 0줄, TQQQ · QLD 합성은 `M` 아님
- 2026-11-05 09:50: Phase 2 — 문서 · 연구 문서 · `HANDOFF.md`. 연구 문서 결정 3 을 「시가 = 그날 종가」 사용자 결정으로, 결정 9 에 기준선 뜻, 결정 11(새 행)
- 2026-11-05 09:55: 마지막 Phase — black 1파일, 두 번째 생성에서 합성 셋 · 검증 CSV 둘이 첫 생성 사본과 `cmp` 같음 · 콘솔 13줄 「같음」. `/code-review xhigh` 1회차 13건 — 버그 3(가벼움) · 그 외 10, 고칠 것 0
- 2026-11-05 09:58: 리뷰가 짚은 「두 명령만」 흐름의 틈을 실측 — 금리 파일 끝 2026-09 · `MAX_FFR_MONTHS_DIFF` 2 → 2026-12 시세부터 레버리지 합성이 멈춘다(운용비율은 끝 2026-02 · 허용 12개월 → 2027-03 시세부터). COMMANDS · `scripts/CLAUDE.md` · 연구 문서 결정 11 에 적고, 금리 자동 받기 여부를 `HANDOFF.md` 2절 열린 질문으로 넣었다. 주석 4줄을 간결체로 고쳤다. 고친 뒤 `validate_project.py` 744 passed · failed 0 · skipped 0, 경고 9건은 기존 pandas `resample` 경고(새 테스트 두 파일 경고 0)
- 2026-11-05 09:58: 거른 리뷰 지적 13건 (옮기지 않음 — Done 보고 표로 냄)
  1. `main` 이 1배 합성을 먼저 저장해, 레버리지가 금리 파일 낡음으로 멈추면 기준일이 다른 파일이 남고 반대로 1배가 멈추면 레버리지가 다시 만들어지지 않는다 — 가벼운 버그, 기준 2: 멈출 때 ERROR 와 종료코드 1 로 알리고 틀린 값을 내보내지 않는다. 지금 `QQQ_synthetic_max.csv` 를 읽는 러너가 없다
  2. 워크플로우 2 의 「두 명령만」이 월별 파일 갱신을 빠뜨린다 — 그 외(문서), 기준 3. 사용자 요청 흐름을 틀리게 적은 문장이라 DoD 로 고쳤다
  3. 1배 대상마다 합성 저장이 검증 계산보다 먼저라, 검증이 예외를 내면 새 합성에 낡은 검증 표가 남는다 — 가벼운 버그, 기준 1 · 2: 검증 쪽 예외는 겹치는 날 2일 미만뿐인데 이음매 날이 대용에 있어야 합성이 만들어지므로 대용이 이음매 날에 끝나는 대상이어야 남는다(QQQ 는 겹침 6,954일, 계획된 VFINX · VUSTX 는 지금까지 이어진다). 남아도 ERROR 로 멈춘다
  4. ⑥ 검사가 1배 합성에만 있고 레버리지의 `splice_proxy` 직접 호출에는 없다 — 그 외, 기준 3: `splice_proxy` 의 이음매 뒤 행은 `TestSpliceProxy.test_rows_from_seam_equal_actual` 가 지키고, 레버리지 ⑥ 은 계획 2 범위(연구 문서 7장)
  5. `DEFAULT_TICKERS` 를 손으로 맞추게 되어 COMMANDS ① 의 자동 루프보다 약하다 — 그 외, 기준 3: 지금 원본 8 = 목록 8. 빠져도 그 시세 끝날만 뒤처진다. 사용자에게 선택지로 보고
  6. 콘솔 표에 대용 첫날 · 비교 달 수가 없다 — 그 외(표시), 기준 3: 합성 앞 행 수는 매번 로그에 나오고 CSV 에 대용 첫날이 있다
  7. `align_closes` 가 한쪽에만 있는 날을 빼고 그 수를 내지 않는다 — 그 외, 기준 3: `^NDX ↔ QQQ` 는 0일. 금 대용(계획 4)을 위해 `HANDOFF.md` 4절에 적었다
  8. ⑥ `RuntimeError` 메시지에 다른 첫 행 · 열이 없다 — 그 외(메시지), 기준 3
  9. 직전 CSV 를 읽을 때 `str()` 이 잘린 행의 NaN 을 `nan` 으로 만든다 — 가벼운 버그, 기준 1 · 2: 그 CSV 는 이 스크립트가 쓰고, 손으로 행을 잘라야 나며, 콘솔 표시만 「바뀜」으로 틀린다
  10. 비교 함수가 src 에서 한글 표시 열로 행을 만든다(`COL → DISPLAY` 관용과 다름) — 그 외(관용), 기준 3: `ee6d23d` 의 검증된 코드를 되살린 모양
  11. `QQQ_max.csv` 를 두 번 읽는다 — 그 외(성능), 기준 3
  12. `TestBuildProxySynthetic` 에 경계 조건 테스트가 없다 — 그 외, 기준 3: 지적한 변형(이어 붙인 뒤 시가 바꾸기)은 `test_rows_from_seam_equal_actual`(실물 시가 ≠ 종가)과 ⑥ 검사가 잡는다
  13. 새 주석 4줄이 전역 주석 문체(간결체)와 다르다 — 그 외, 기준 3. 사용자 규칙이라 고쳤다

---
