# Implementation Plan: 대시보드 정리 — 조용히 넘기던 자리 멈춤 · 탈 수 없는 분기 삭제 · 화면 문구의 숫자를 상수로 · main 의 try/except 삭제

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-19 23:22
**마지막 업데이트**: 2026-10-19 23:25
**관련 범위**: scripts(`backtest/app_single_backtest.py` · `app_portfolio_backtest.py` · `app_walkforward.py` · `app_parameter_stability.py` · `run_supplement_grid.py`, `data/app_proxy_comparison.py`, `tqqq/app_daily_comparison.py`, `tqqq/spread_lab/app_rate_spread_lab.py`), backtest(`constants.py` · `walkforward_verdict.py` · `parameter_stability.py`), tests(`test_walkforward_verdict.py`)
**관련 문서**: `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 11단계 「대시보드」)

---

## 1) 목표(Goal)

- [ ] 목표 1: 값 · 파일이 없으면 조용히 기본값으로 넘기던 대시보드 자리를 직접 인덱싱으로 바꿔 멈추게 한다(12-9 · 9-9) — 단일 앱 `.get` 6곳, 포트폴리오 앱 3곳, 워크포워드 앱의 「없으면 None」 로더 넷과 그 호출부
- [ ] 목표 2: 탈 수 없는 분기와 같은 값 두 번 계산을 지운다(6-7 · 6-15의 대시보드 자리)
- [ ] 목표 3: 화면 문구에 직접 적은 숫자를 상수에서 읽는다(3-12, D6) — 고원 앱 제목의 4P 숫자는 지운다. 파라미터 추이 그림의 높이를 행 수로(2-9), WFO 파라미터 목록 · 라벨을 한 벌로(3-20)
- [ ] 목표 4: 같은 것을 한 곳에 — 포트폴리오 앱의 색 함수 하나 · hex→rgba 변환 하나(5-6), 단일 앱 거래 표의 열 이름을 `COL_*` 로(4-6), 워크포워드 지표 선택지를 탐색한 전략 × 모드로(3-13, D4)
- [ ] 목표 5: 대시보드 `main()` 을 감싼 try/except 를 지운다 — 단일 · 대체 비교 · 일별 비교 · 스프레드 랩(안쪽 try 포함, D5)
- [ ] 목표 6: 화면 변화는 의도한 셋뿐이고(파라미터 추이 그림의 높이 · 부제 둘, 그 섹션 용어 설명의 예시 숫자, 고원 앱 제목), 결과 파일 변화는 0 이다

## 2) 비목표(Non-Goals)

- **7-1(차트 공용 모듈, 결정 4 (가)) · 7-7(월별 히트맵 하나로, D3 (가))** — 둘째 계획서(11단계 대시보드 ②). 3-14(포트폴리오 캔들 변환의 전일대비% 튜플)도 그쪽이다 — 7-1 이 그 함수째 공용 모듈로 옮기므로 여기서 고치면 바로 다시 옮긴다. 캐시 로더 헬퍼 `_cache_args` 두 벌의 통합(7-1 「함께 볼 것」)도 그쪽이며, 이번 변경으로 워크포워드 앱의 `_cache_args` 에서 「없는 파일은 0.0」 분기를 탈 일이 없어지는 것도 그때 포트폴리오 쪽(장부가 선택 파일이라 0.0 이 필요하다)과 합치며 정리한다
- **캐시 상한(`max_entries`)** — 버림(D7, 사용자 결정 2026-10-19). 짧게 띄우는 로컬 앱이고 해가 메모리뿐이라 상한값을 맞춰 두는 관리 비용이 더 크다
- **워크포워드 앱의 표시명 · 색 사전 자체** — 「QQQ」 같은 짧은 라벨은 이 앱의 화면 표기라 앱에 남긴다(D4 (다)). 앱 docstring · main 설명의 「QQQ와 TQQQ를 나란히」 문장은 13-C C10 과 함께 12단계 문서
- **판단 문구의 「네 파라미터」(목록 길이를 숫자로 적음)** — 12단계 문서(14절과 같은 모양). **임계값 상수를 테스트가 그 상수로 기대값을 만드는 것**(값이 바뀌어도 통과) — 정책 값 고정은 3-21(결정 14), 11단계 tests
- **고원 앱의 `except FileNotFoundError` 경고 · 포트폴리오 기여도의 「열 누락」 오류 표시 · 대체 비교의 `align_closes` 경고** — 보고서 목록 밖이고, 셋 다 화면에 알린다(마지막은 사용자가 고른 쌍이 비교 불가일 때다)
- **13-C C1 · C4 · C9 · C10(대시보드 docstring · 주석의 실오류)** — 12단계 문서

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 11단계 대시보드 줄의 첫째 계획서다. 사용자 결정(2026-10-19, 아래 Notes)대로 둘로 나눠 이 계획서는 몇 줄짜리 처방 묶음과 D4 · D5 · D6 을, 둘째는 7-1 · 7-7 을 한다
- 항목마다 지금 무엇이 문제인가 (2026-10-19 저장소 사본에서 다시 쟀다 — 스크래치 `step11f/`. 보고서 줄 번호는 기준 커밋 `40011ad` 값이라 그 커밋의 줄을 뽑아 지금 코드에 대응시켰다)

| 항목 | 지금 | 바꾸는 것 |
|---|---|---|
| 12-9 단일 | `_style_pnl_rows` 의 `.get` 둘, `summary_data.get("params" · "monthly_returns" · "yearly_returns", 기본값)`, `summary.get("calmar", 0.0)` — 결과 13개 모두 키가 있다 | 직접 인덱싱 |
| 12-9 포트폴리오 | `summary.get("display_name", 폴더명)`, 최종일 `final_row.get(f"{키}_realized_pnl" · "_unrealized_pnl", 0)` | 직접 인덱싱 |
| 12-9 · 9-9 워크포워드 | 로더 넷(요약 · 윈도우 결과 · Stitched 에쿼티 · 윈도우 상세)이 파일이 없으면 None, 호출부가 「데이터 없음」 주석 · `continue` · 빈 DataFrame 으로 넘어간다. 드로우다운 변환의 열 존재 검사 | 로더는 바로 읽고(없으면 `FileNotFoundError`) 호출부의 분기 삭제. 같은 모양 하나를 더한다: 모드 요약 표의 「N/A」 대체(보고서 목록 밖, 9-9 와 같은 모양) |
| 6-7 | 포트폴리오: 기여도의 열 존재 검사 둘(그 위에서 이미 막는다), 드로우다운 비교의 `rgb` 분기(팔레트 `Light24` 는 전부 hex). 단일: `st.stop()` 뒤 `return`. 워크포워드: 선택 상자 `None` 검사 둘 · `st.stop()` 뒤 `return` · 「요약 없음」 분기(탐색 조건이 요약 파일이다) | 삭제 |
| 6-15 | 단일: `has_trades` 를 두 함수가 각자 계산(그 식의 `"entry_date" in columns` 는 늘 참 — 두 엔진이 빈 거래도 열을 둔다), 보유 기간 히스토그램이 호출부와 같은 조건 · 같은 안내를 다시 검사. 포트폴리오: 이미 datetime 인 날짜를 다시 변환, 히트맵 색 범위의 `else 10.0`(월별 수익률이 비면 위에서 이미 돌아간다). 보고서의 `:687`(연간 초과수익 평균)은 결정 3 으로 그 섹션째 없어져 있다 | 한 번만 계산 · 중복 검사와 탈 수 없는 대체값 삭제 |
| 3-12 · D6 | 고원 앱 제목 「4P 확정 파라미터(MA=200, buy=3%, sell=5%, hold=3)」(탭마다 확정값을 상수로 이미 보인다), 고원 주석 「80%」(상수 없이 기본 인자 `0.8` 두 곳), 포트폴리오 「상대 편차 10%」(`DEFAULT_REBALANCE_POLICY`), 워크포워드 해석 문구의 1 · 1 · 0.5(판단 모듈 상수), 보완 그리드 러너의 「신호 관문(95%)」 · 「판정 일치 수(7 중)」(`SIGNAL_AGREEMENT_PASS_RATE` · `len(W_PCTS)`) — 마지막 둘은 러너라 대시보드 몫이 아니고 backtest 줄에도 3-12 가 없어 어느 단계에도 배정되지 않았다 | 4P 숫자 삭제, 나머지는 f-string 으로 상수 참조(출력 글자 같음). 고원 기준은 `DEFAULT_PLATEAU_THRESHOLD_RATIO` 새 상수 |
| 2-9 | 파라미터 추이 그림은 4행인데 높이 `250 * 5` · x축 제목 반복 `range(1, 6)` | 목록 길이로 — 높이 1,250 → 1,000px |
| 3-20 | WFO 파라미터 목록 · 라벨이 3벌(앱 차트 · 판단 모듈 · 용어 설명), 용어 설명의 「예: 100, 150, 200일」은 그리드 상수 사본. 앱은 % 환산을 `"buffer" in key` 로 가른다 | 판단 모듈의 목록을 `WFO_PARAM_SPECS` 로 공개해 차트가 쓴다(% 여부도 그 목록에서). 차트 부제가 판단 문구 라벨로 맞춰진다(「Buy Buffer (%)」 → 「Buy Buffer(%)」). 예시 숫자 삭제 |
| 3-13 · D4 | 표시명 사전 · 색 사전 · 「지표 선택」 4조합 사전이 전략 이름을 다시 적는다. 워크포워드 전략이 늘면 표시명은 원래 이름 · 색은 회색으로 넘어가고, 윈도우 상세 선택지에서는 조용히 빠진다 | 선택지는 탐색한 전략 × 두 모드(`_WINDOW_MODES`). 표시명 · 색 사전은 남기되 `.get` 대체를 직접 인덱싱으로 — 모르는 전략이면 `KeyError` |
| 4-6 | 단일 앱 거래 표 열 이름 사전 · 보유 기간의 `"holding_days"` 가 리터럴 | `COL_*` 상수(같은 표의 `"pnl_pct"` 두 곳 포함) |
| 5-6 | 포트폴리오 앱의 `_get_asset_color` ≡ `_get_experiment_color`, hex → rgba 손 변환 2곳(`_hex_to_rgba` 가 있다) | `_palette_color` 하나 · `_hex_to_rgba` |
| D5 | `main()` 을 감싼 try/except — 단일 · 대체 비교 · 일별 비교 · 스프레드 랩. 포트폴리오 · 워크포워드 · 고원 앱에는 없다. 이 저장소의 Streamlit 은 `client.showErrorDetails = full`(직접 조회)이라 잡지 않은 예외도 traceback 전체가 화면에 나와, try/except 가 더하는 것은 「오류가 발생했습니다」 한 줄이다. 스프레드 랩 안쪽 `except Exception` 은 `str(e)` 만 보여 traceback 을 숨긴다 | 넷 다 삭제(스프레드 랩 안쪽 포함), 스프레드 랩 docstring 의 「Fail-fast 정책」 세 줄(그 안쪽 try 의 설명) 삭제 |

### 설계 결정

1. **상수의 자리** — 판단 모듈 상수 셋(`PC_CONCENTRATION_THRESHOLD` · `WFE_REPRODUCIBLE_THRESHOLD` · `STITCHED_CALMAR_GOOD_THRESHOLD`)과 파라미터 목록 `WFO_PARAM_SPECS` 는 판단 모듈과 워크포워드 앱 두 파일이 쓰게 되어 `backtest/constants.py` 로 옮긴다(`src/qbt/CLAUDE.md` 3계층 규칙 — 직전 묶음의 의도 종류 묶음과 같은 판단). `CAGR_SIMILAR_THRESHOLD_PP` 는 판단 모듈만 써서 남는다. 고원 기준 `DEFAULT_PLATEAU_THRESHOLD_RATIO` 도 고원 모듈 · 고원 앱 두 파일이라 같은 자리
2. **워크포워드 지표 선택지** — `{표시명} {모드}`: (전략, 윈도우 상세 폴더, WFO CSV). 순서는 탐색 순서(폴더 이름순) × (Dynamic, Fixed) — 지금 4조합과 같은 순서 · 같은 라벨
3. **멈추는 쪽** — 결과 파일 · 키가 없으면 대시보드가 `FileNotFoundError` · `KeyError` 로 멈추고 Streamlit 이 traceback 을 보인다. 러너를 다시 돌리면 생기는 파일이다
4. **테스트** — 비율 파라미터 % 환산을 지키는 테스트 1 을 더한다(`test_ratio_params_are_described_in_percent`). 이 목록을 판단 문구와 대시보드가 함께 쓰게 되는데, 비율 여부를 뒤집어도 기존 테스트 30개가 통과했다(지금 코드에도 같은 공백). 판단 문구 테스트의 상수 import 를 `constants` 로

### 사본 재현 (착수 전 확인, 2026-10-19)

저장소 밖 사본에 이 계획서의 변경을 그대로 얹어 전제를 확인했다. 저장소 코드와 `storage/` 는 건드리지 않았다.

- **사본** — HEAD `09a4427` 을 `git archive` 로 뽑은 수정 전(`step11f/base`) · 수정 후(`step11f/exp`). 저장소 `.venv` 파이썬에 `PYTHONPATH=사본/src`, 사본을 cwd 로
- **레드 단계는 두지 않는다** — 화면 · 결과를 바꾸지 않는 정리가 대부분이고, 회귀는 화면 대조와 변형 확인으로 본다
- **품질** — Ruff 통과, black 변경 0, PyRight 0 errors(테스트 포함), 927 passed(지금 926 + 더한 1)
- **화면 대조** — 대시보드 일곱을 서버 없이 `main()` 으로 돌려 화면 요소를 기록하는 도구(`step11f/tools/capture.py`)를 새로 썼다. 지난 도구에 더한 것: 컨테이너 메서드(`col.metric` 등), Plotly 그림의 레이아웃까지 담은 전체 해시, lightweight-charts 호출 인자 전체 해시, 선택 상자 순회(포트폴리오 · 대체 비교 · 스프레드 랩은 상자마다 따로, 워크포워드는 지표 × 윈도우 조합 전부), Styler 표, 본문은 Streamlit 이 화면으로 보내는 값(`clean_text`)
  - 같은 사본을 두 번 기록해 92회 실행 · 6,041개 요소가 모두 같다(결정적)
  - 수정 전 ↔ 후: 다른 요소 89개 = 워크포워드 2개 × 44회 + 고원 1개. 파라미터 추이 그림은 레이아웃 키 셋만 다르다(높이 1,250 → 1,000, 부제 「Buy Buffer (%)」 · 「Sell Buffer (%)」 → 공백 없는 라벨, 선 데이터 해시 같음), 그 섹션 용어 설명에서 「(예: 100, 150, 200일)」 삭제, 고원 앱 제목. 나머지 5,952개는 같다 — 포트폴리오 「10%」 · 고원 「80%」 · 워크포워드 해석 문구 · 모드 요약 표 · 지표 선택지 · 색 포함. 오류 0건
- **결과 파일** — 수정 후 사본에서 보완 그리드 러너를 다시 돌려(rc=0, 52초) `storage/` 가 수정 전 사본과 바이트까지 같다(`diff -rq` 차이 0). 나머지 러너는 이 계획서가 바꾸는 코드를 지나지 않는다
- **멈추는지 확인** — 입력을 일부러 깨 수정 전 · 후를 견줬다
  - 워크포워드 결과가 있는 전략을 하나 더 두면(`buffer_zone_spy` 에 QQQ 결과 복사): 수정 전은 요약 표 · 파라미터 추이에 원래 이름 · 회색 선으로 그리고 지표 선택지에서는 빠진다. 수정 후 `KeyError: 'buffer_zone_spy'`
  - TQQQ Fully Fixed Stitched 에쿼티 파일을 빼면: 수정 전은 TQQQ 칸에 Dynamic 선만 그린다. 수정 후 `FileNotFoundError`
  - 일별 비교 CSV 를 빼면: 수정 전은 「오류가 발생했습니다」 + traceback, 수정 후는 예외가 그대로 올라간다(Streamlit 이 traceback 을 보인다)
- **변형 확인** — 화면 대조가 회귀를 잡는지: 변형 11종(포트폴리오 제목 자릿수 · 비중 채움 투명도 · 드로우다운 채움 색, 워크포워드 요약 표 Dynamic ↔ Fixed · 비율 환산 빠뜨림 · 해석 문구 상수 바꿔치기 · 선택지 모드 경로, 고원 주석 자릿수 · 고원 기준 상수 값, 단일 거래 표 색 기준 · 보유 기간 열)을 하나씩 넣어 모두 차이로 잡혔다. 테스트: `WFO_PARAM_SPECS` 의 비율 여부 뒤집기 셋(매수 · 매도 버퍼 · 이동평균)을 새 테스트가 잡는다(각 1 failed). 목록에서 한 줄 지우기는 기존 테스트가 잡는다
- **변경 규모** — 파일 12개. src +27 / −23, scripts +317 / −437(대부분 try/except 를 걷어 내며 들여쓰기만 바뀐 줄), tests +21 / −2

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 · 「스크립트 실행 규칙」(대시보드는 사용자가 띄운다 · 결과 파일은 덮어써진다) 절
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [ ] 저장소의 src · scripts · tests 가 사본(`step11f/exp`)과 같고(`diff -rq` 차이 0), 저장소 화면 기록이 사본의 수정 후 기록과 92회 · 6,041개 요소 모두 같다
- [ ] 결과 파일: 저장소에서 보완 그리드 러너를 다시 돌려 `git status` 의 `storage/` 변경이 0 이다
- [ ] `_METRIC_OPTIONS` · `_get_asset_color` · `_get_experiment_color` · `param_specs` 를 가리키는 코드 · 안내 문서가 src · scripts · tests · `docs/research` 에 0 이고, 대시보드 일곱에 `except Exception` 이 0 이다
- [ ] 새로 넣거나 고친 검사마다 결함을 일부러 넣어 실패하는 것을 봤다(변형 확인 — 테스트는 새 테스트, scripts 는 화면 대조)
- [ ] 회귀/신규 테스트 추가
- [ ] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [ ] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [ ] 자동 포맷 적용 완료
- [ ] 필요한 문서 업데이트 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절), `src/qbt/backtest/CLAUDE.md`(「2. constants.py」 카테고리에 WFO 판단 기준 · 파라미터 목록 · 고원 기준). `scripts/CLAUDE.md` 변경 없음(대시보드 서술이 그대로 참이다), `docs/COMMANDS.md` 변경 없음(실행 명령 · CLI 옵션 그대로), `README.md` 변경 없음, `tests/CLAUDE.md` 변경 없음
- [ ] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [ ] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- src: `src/qbt/backtest/{constants, walkforward_verdict, parameter_stability}.py`
- scripts: `scripts/backtest/{app_single_backtest, app_portfolio_backtest, app_walkforward, app_parameter_stability, run_supplement_grid}.py`, `scripts/data/app_proxy_comparison.py`, `scripts/tqqq/app_daily_comparison.py`, `scripts/tqqq/spread_lab/app_rate_spread_lab.py`
- tests: `tests/qbt/test_walkforward_verdict.py`
- 위 DoD 문서 줄의 문서
- `docs/COMMANDS.md`: 변경 없음 — 실행 명령 · CLI 옵션 그대로
- `README.md`: 변경 없음

### 데이터/결과 영향

- 결과 파일 변화 0 — 대시보드는 읽기만 하고, 보완 그리드 러너의 머리글은 같은 글자다(Context 「결과 파일」)
- 화면 변화: 워크포워드 파라미터 추이 그림(높이 · 부제 둘)과 그 섹션 용어 설명(예시 숫자), 고원 앱 제목. 데이터가 없거나 모르는 전략일 때는 넘어가지 않고 멈춘다

## 6) 단계별 계획(Phases)

### Phase 1 — 사본에서 검증한 코드 · 테스트 반영(그린)

**작업 내용**:

- [ ] 저장소의 src · scripts · tests · `docs/research` · `storage` 가 사본의 수정 전 기준(`step11f/base`)과 같은지 확인한다(`diff -rq`)
- [ ] 사본(`step11f/exp`)에서 검증한 파일 12개(코드 11 · 테스트 1)를 그대로 넣는다

**Validation**:

- [ ] 저장소 src · scripts · tests = 사본 `exp`(`diff -rq` 차이 0), DoD 셋째 줄의 이름 · `except Exception` 0건
- [ ] 저장소를 cwd 로 대시보드 일곱을 기록해 사본 `exp` 기록과 같다(92회 · 6,041개 요소)

---

### Phase 2 — 결과 파일 확인

**작업 내용**:

- [ ] 작업 트리의 `storage/` 변경이 0 인지 확인한 뒤 저장소에서 보완 그리드 러너를 돈다(약 1분, `docs/COMMANDS.md` 의 명령)

**Validation**:

- [ ] 러너 rc=0, `git status` 의 `storage/` 변경 0

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [ ] 문서 — `docs/AUDIT_REPORT.md`(처리 표시 · 19절), `src/qbt/backtest/CLAUDE.md`(constants 카테고리)
- [ ] 자동 포맷 적용 (`poetry run black .`)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [ ] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [ ] `/code-review xhigh` **1회차** (발견 \_\_건 — 버그 \_\_ [무거움 \_\_ · 가벼움 \_\_] · 그 외 \_\_ · 조치: \_\_)
- [ ] 수정분 검증 (수정 \_\_건 · 발견 \_\_건 — 무거움 \_\_ · 조치: \_\_ — 마지막 회차에 고친 것이 없으면 「해당 없음」)
- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

- [ ] (미작성 — `/commit` 을 실행하고 후보 5개를 **이 자리에** 번호 붙은 줄로 옮긴 뒤 이 줄을 지운다)

## 7) 리스크(Risks)

- **결과 파일 · 키가 빠지면 대시보드가 멈춘다** — 지금은 조용히 넘어가거나 틀린 화면을 낸다(Context 「멈추는지 확인」). 지금 결과로는 모든 파일 · 키가 있다(13개 단일 요약의 네 키 · 포트폴리오 5개의 `display_name` · 워크포워드 두 전략 × 두 모드 × 11개 윈도우의 상세 파일 셋을 셌다)
- **워크포워드 러너에 전략을 더하면 대시보드가 `KeyError` 로 멈춘다** — 의도한 동작이다. 표시명 · 색 사전에 한 줄씩 더하면 된다(사전 위 주석)
- **화면은 서버 없이 기록한 것이다** — 브라우저 렌더링 자체는 보지 않았다. 바뀌는 곳은 워크포워드 「파라미터 추이」 섹션과 고원 앱 제목이라, 사용자가 띄워 그 둘을 보면 된다
- **오류 화면의 머리 한 줄이 빠진다** — try/except 삭제 뒤에도 traceback 전체가 보인다(`showErrorDetails = full`). 이 설정을 바꾸면 traceback 이 줄어든다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 2-9 · 3-12 · 3-13 · 3-20 · 4-6 · 5-6 · 6-7 · 6-15 · 9-9 · 12-9, 19절 11단계 대시보드
- 사용자 결정(2026-10-19, 「추천대로」):
  - D1 결정 4 — 차트 공용 코드는 src 의 Streamlit 비의존 모듈 (가)
  - D2 — 계획서 둘: ① 이 계획서, ② 7-1 · 7-7
  - D3 — 월별 히트맵은 포트폴리오 모양으로 통일 (가) — ②
  - D4 — 워크포워드 지표 선택지만 탐색 결과로, 표시명 · 색 사전은 남기고 직접 인덱싱 (다)
  - D5 — `main()` try/except 넷 다 삭제(스프레드 랩 안쪽 포함) (가)
  - D6 — 보완 그리드 러너 머리글 둘을 상수 f-string 으로 (가)
  - D7 — 캐시 상한 두지 않음(버림) (나)
- 이 계획서 다음은 11단계 대시보드 ②(7-1 · 7-7 · 3-14 · `_cache_args`)

### 진행 로그 (KST)

- 2026-10-19 13:47: 직전 세션의 커밋 후보를 마무리했다(`PLAN_portfolio_engine_cleanup.md` Done, 사용자가 `09a4427` 로 커밋)
- 2026-10-19 22:52 전: 점검 보고서 대시보드 줄 항목을 모으고 대시보드 네 개와 판단 모듈을 읽었다. 기준 커밋 줄 번호를 지금 코드에 대응시켰다. 결정 7건을 올렸고 사용자가 「추천대로」로 답했다(Notes)
- 2026-10-19 22:52 ~ 23:20: 사본(`step11f`)에 변경을 얹었다 — 화면 기록 도구를 새로 써 결정성(두 번 기록 같음)을 확인하고, 수정 전 · 후를 대조했다(다른 요소 89개, 의도한 셋). 보완 그리드 결과 바이트 동일, 입력을 깨 멈추는지 셋, 화면 대조 변형 11종 · 테스트 변형(비율 환산 공백을 찾아 테스트 1 을 더했다), 927 passed
- 2026-10-19 23:22: 계획서 작성(Draft)
- 2026-10-19 23:25: 자체 검증 네 각도(배정 항목 대조 · 다른 로직 영향 · 실행 위험 · 목표 ↔ DoD ↔ Validation 대응) — 첫 각도에서 6-15 `:687` 이 없어진 사실과 진행 로그 시각 둘을 바로잡았고, 나머지 셋에서는 고칠 것이 없었다

---
