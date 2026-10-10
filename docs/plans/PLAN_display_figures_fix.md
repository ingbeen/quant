# Implementation Plan: 결과 · 대시보드 표시 수치 바로잡기 — 첫 해 수익률 · QQQ 비교 섹션 삭제 · 고원 범위 · 분기 기여도 · 마커 · 대시보드 캐시

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-09 21:56
**마지막 업데이트**: 2026-10-10 08:59
**관련 범위**: backtest(`analysis` · `parameter_stability`), scripts(러너 2 · 대시보드 4), tests, storage/results(단일 · 포트폴리오 `summary.json`), docs
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`

---

## 1) 목표(Goal)

- [x] 목표 1: **첫 해 수익률** — 월별 수익률에 시작일 ~ 첫 월말 구간을 넣고, 연간 수익률을 반올림한 월 수익률의 복리가 아니라 에쿼티에서 직접 계산한다(감사 보고서 1-1 · 1-6)
- [x] 목표 2: **「연간 수익률 vs QQQ」 섹션 삭제** — 대시보드 섹션 · 러너의 `benchmark_qqq.json` 저장 · src `calculate_benchmark_yearly_returns` · 그 파일과 테스트를 지운다(1-2, 결정 3 (나) — 2026-10-09 사용자 「진행」으로 추천안 확정)
- [x] 목표 3: **고원 구간** — 「최대값을 포함한 연속 범위」로 고친다(1-3). 「저거래 제외」 필터는 **남기고**, 필터가 실패하면 라벨은 그대로 둔 채 필터 없이 칠하는 except 와 틀린 캡션 예시만 지운다(12-1 · 13-C C1 — 결정 7 은 (가)로 되돌린다, 아래 「설계 결정」)
- [x] 목표 4: **대시보드 표시** — 분기 기여도 첫 분기 누락(2-17), 포트폴리오 시그널 차트 마커(리밸런싱 부분 매매를 신호 매매처럼 그림 · 평균 단가를 체결가처럼 표시 — 1-4 · 1-12), 신호 시세 캔들 위의 매매 시세 가격(1-13), 시작일이 다른 실험의 에쿼티 겹쳐 그리기(1-14)
- [x] 목표 5: **대시보드 캐시** — 대시보드를 띄워 둔 채 러너를 다시 돌려도 새 결과가 보이게 한다(2-18)
- [x] 목표 6: **결과 재산출** — 단일 14개 · 포트폴리오 5개의 `summary.json` 을 다시 만들고, 바뀐 것이 월별 · 연간 수익률뿐임을 확인한다

## 2) 비목표(Non-Goals)

- **워크포워드 · 고원 재실행과 그리드 평가 기간**(1-11 · 2-19, 결정 1) — 다음 계획서. 이 계획서는 고원 «화면»의 범위 함수만 고치고 고원 CSV(`param_plateau/`)는 다시 만들지 않는다. 그래서 `docs/research/전략_검증_보고서.md` G.7.2 표의 고원 칸도 그 계획서에서 고친다
- **포트폴리오 러너 · 대시보드 묶음**(DEFERRED 4 · 6 · 10 · 11, 결정 2, 6-8 의 `per_asset` 칸 정리) — 별도 계획서. `open_position.entry_price` 는 이 계획서 뒤로 화면이 읽지 않게 되지만 칸 정리는 그 계획서에서 한다
- **대시보드 차트 공용 모듈**(7-1, 결정 4) — 별도 계획서. 마커 문구는 세 앱에서 각자 고친다
- **연구 문서 수치** — 1-1 은 연구 문서 수치를 바꾸지 않는다(감사에서 확인: 연도별 표는 `equity.csv` 로 따로 계산했다)
- **그 밖의 감사 보고서 항목** — 같은 함수 안이라도 이 목표와 무관한 정리(6-15 · 12-9 등)는 하지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`docs/AUDIT_REPORT.md` 「A. 먼저 볼 것」의 1 · 2 · 3 · 8 · 10 번과 그 관련 항목이다(2026-10-09 재검증).

- **1-1 첫 해 누락** — `analysis.calculate_monthly_returns` 가 월말 리샘플 뒤 `pct_change().dropna()` 를 해 시작일 ~ 첫 월말 수익이 빠진다. 단일 13개 결과 모두 첫 달이 없고(B&H QQQ 월 330개 / 올바르면 331개), 첫 해 저장 / 실제: B&H QQQ 1999 74.16 / 77.11, QQQ B&H 실험 2005 8.39 / 1.90(1월 −6.00% 누락). 시작 월이 12월이면 첫 해가 통째로 없다(B&H UGL 2008). CAGR · MDD · Calmar 는 에쿼티로 계산해 영향이 없다
- **1-6** — `calculate_yearly_returns` 가 2자리로 반올림한 월 수익률을 복리한다. 저장 연간값 414개 중 225개가 원값 복리와 0.01 이상 다르다(최대 0.06)
- **1-2** — QQQ 연간 수익률을 가장 이른 시작일(2005-01-01)로 한 번 계산해 모든 실험이 같이 쓴다. 채택 조합 2007 초과수익: 화면 −13.30%p / 같은 기간 −2.70%p. 사용자 결정 3 (나): QQQ B&H 가 이미 실험으로 등록돼 같은 화면에서 비교되므로 섹션째 지운다
- **1-3** — `parameter_stability.find_plateau_range` 는 docstring 이 「연속 범위」인데 기준 이상인 첫 값 ~ 마지막 값을 돌려준다. QQQ 유지일: 칠함 (0, 10) / 연속이면 (2, 10)(유지일 1 = 0.24 < 기준 0.256). 매도 버퍼 탭의 「저거래 제외」 필터는 실패하면(`except (FileNotFoundError, KeyError)`) 필터 없이 칠하면서 라벨은 「저거래 제외」로 남기고, 캡션의 예시(「sell=0.15 제외」)는 틀렸다(QQQ sell=0.15 는 거래 5회로 기준 이상)
- **2-17** — 분기 기여도를 `diff().iloc[1:]` 로 구해 첫 분기 막대가 빠진다(QQQ B&H 2005Q1 −809,019원, 막대 합 209,895,969 / 최종 209,086,950)
- **1-4 · 1-12 · 1-13 마커**
  - 포트폴리오 `trades.csv` 의 `entry_price` 는 매도 시점 평균 단가라 Buy 마커 253개 중 48개가 체결가와 0.1% 넘게 다르다. 미청산 마커는 진입일에 거래 행이 있으면 생략돼 13개 자산은 「보유중」 표시가 아예 없다
  - 리밸런싱으로 일부만 판 거래(`trade_type == "rebalance"`, Q-2 126 중 107)도 신호 청산과 같은 「Sell +x%」로 그려 B&H 자산에 Sell 화살표가 줄지어 나온다
  - 캔들은 신호 시세인데 마커의 $ 는 매매 시세다(TQQQ 탭: QQQ 캔들에 TQQQ 체결가)
- **1-14** — 시작일이 다른 실험(2005-01-03 ×3 · 2007-04-09 · 2007-06-22)을 같은 1,000만 원 출발점에서 겹쳐 그린다
- **2-18** — 백테스트 대시보드 3개에서 파일을 읽는 `@st.cache_data` 로더 13곳(단일 2 · 포트폴리오 7 · WFO 4, 벤치마크 로더를 지우면 12곳)은 캐시 키가 경로 문자열뿐이라 대시보드를 띄워 둔 채 러너를 다시 돌리면 옛 결과가 계속 보인다. 같은 저장소의 `scripts/data/app_proxy_comparison.py:51-58` 은 파일 수정 시각을 키로 넣어 막는다

### 설계 결정

- **월별 · 연간 수익률**: 기간 말 에쿼티 앞에 «첫 행 에쿼티»를 기준점으로 둔다. 첫 달 = 첫 월말 / 첫 행 − 1, 첫 해 = 첫 연말 / 첫 행 − 1, 그 뒤는 직전 기간 말 대비. 두 함수가 같은 비공개 헬퍼(기간 말 에쿼티 + 기준점)를 쓴다. `calculate_yearly_returns` 는 월별 리스트 대신 `equity_df` 를 받는다(호출부 2곳 · 월→연 복리 루프 삭제). 반올림은 지금처럼 반환 리스트를 만들 때 한다 — 이 리스트는 곧바로 `summary.json` 으로 나간다
- **고원 범위**: 최대값 위치에서 좌우로 기준 이상인 동안만 넓힌다. 기준 이상 구간이 여럿이면 최대값(같은 값이 여럿이면 앞쪽)이 든 구간이다
- **저거래 필터는 지우지 않는다** — 감사 보고서 결정 7 의 추천 (나)(필터 삭제)는 「QQQ 에서 지금 제외하는 값이 0개」만 보고 낸 것인데, `docs/research/전략_검증_보고서.md` G.7.2 · H.6 이 이 필터의 기준(거래 5회)을 **유지하기로 확정**(2026-08-30)했고 그 표가 「대시보드와 동일한 함수로 판정했다」고 적는다. 데이터가 늘어 QQQ sell=0.15 의 거래가 4회가 되면 필터가 실제로 작동한다. 그래서 (가)(except 만 삭제)로 되돌린다 — 계획서 자체 검증에서 찾았다
- **마커**: 세 앱의 Buy 마커에서 가격을 뺀다(「Buy」 · 「Buy (보유중)」). 포트폴리오의 진짜 체결가는 `trades.csv` 에 없어(`state_log.csv` 를 읽어야 한다) 바로잡으려면 범위가 커지고, 단일 · WFO 의 TQQQ 탭은 체결가가 맞아도 다른 종목 캔들 위에 놓인다. 단일 대시보드는 거래 표에 진입가가 따로 있다. 포트폴리오는 `trade_type == "rebalance"` 거래의 마커를 그리지 않는다(리밸런싱일은 에쿼티 차트 마커가 이미 보인다). 미청산 진입일에 Buy 마커가 이미 있으면 그 문구에 「(보유중)」을 붙인다
- **캐시**: 파일을 읽는 캐시 로더마다 `mtime: float` 인자(본문에서 쓰지 않는 캐시 키)를 두고 호출부가 파일 수정 시각을 넘긴다 — `app_proxy_comparison.py` 관용 그대로. 없을 수 있는 파일(`ledger.csv` · `execution_comparison.csv` · WFO 결과)은 없으면 0.0 을 넘긴다(파일이 생기면 키가 바뀐다). `_build_color_map` 은 파일을 읽지 않으므로 대상이 아니다
- **결과 재산출**: 바뀌는 것은 `summary.json` 의 `monthly_returns` · `yearly_returns` 뿐이어야 한다. 그 밖의 키와 CSV 는 바이트 단위로 같아야 한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」(결과 파일 덮어쓰기 · 대시보드는 사용자가 실행 · `download_data.py` 금지)
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 월별 수익률의 첫 달이 시작일 ~ 첫 월말, 연간 수익률의 첫 해가 시작일 ~ 첫 연말이고, 연간 수익률이 에쿼티 비율과 같다(재현 테스트가 수정 전 실패 · 수정 후 통과)
- [x] `calculate_benchmark_yearly_returns` · `_save_benchmark_qqq_json` · 「연간 수익률 vs QQQ」 섹션 · `storage/results/portfolio/benchmark_qqq.json` 이 없고, `src` · `scripts` · `tests` · 살아있는 문서에 그 이름이 남지 않는다(`grep` 0건, `docs/plans/` · 설계서 · 감사 보고서 제외)
- [x] 고원 범위가 최대값을 포함한 연속 범위다(재현 테스트가 수정 전 실패 · 수정 후 통과). 매도 버퍼 탭의 except 와 캡션의 틀린 예시가 없다(필터는 그대로)
- [x] 분기 기여도 막대 합이 최종 기여와 같다(5개 실험, 결과 파일로 계산)
- [x] 포트폴리오 마커: 리밸런싱 거래 마커 0, Buy 마커에 가격 없음, 미청산 자산마다 「보유중」 마커 1개(5개 실험, 함수를 불러 확인). 단일 · WFO 마커에도 가격 없음
- [x] 파일을 읽는 캐시 로더 12곳(단일 2 · 포트폴리오 6 · WFO 4) 모두 수정 시각 인자가 있다(`grep`)
- [x] 결과 재산출: 단일 14 · 포트폴리오 5 의 `summary.json` 에서 `monthly_returns` · `yearly_returns` 밖의 값이 그대로이고, 그 밖의 결과 CSV 는 git diff 0. 첫 달 · 첫 해가 에쿼티 비율과 같다
- [x] 대시보드 확인 안내 — 완료 보고에 실행 명령과 볼 지점을 적는다(사용자가 실행)
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `src/qbt/backtest/CLAUDE.md`(변경 있음) · `scripts/CLAUDE.md`(변경 있음) · `docs/AUDIT_REPORT.md`(처리 표시) · `docs/COMMANDS.md`(변경 없음 — 실행 명령 · 옵션 그대로) · `README.md`(변경 없음) · `tests/CLAUDE.md`(변경 없음)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
- [x] 미룬 지적 옮김 — 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `docs/DEFERRED_FINDINGS.md` 로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py` — 월별 · 연간 수익률(헬퍼 하나 + 두 함수), `calculate_benchmark_yearly_returns` 삭제
- `src/qbt/backtest/parameter_stability.py` — `find_plateau_range` 연속 범위
- `scripts/backtest/run_single_backtest.py` — 연간 수익률 호출부
- `scripts/backtest/run_portfolio_backtest.py` — 연간 수익률 호출부, `_save_benchmark_qqq_json` 삭제와 `main` 의 전 실험 시작일 계산 정리(실험마다 자기 시작일만 계산), 쓰이지 않게 되는 import 정리
- `scripts/backtest/app_portfolio_backtest.py` — 벤치마크 섹션 · 로더 · 상수 삭제, 분기 기여도, 마커, 에쿼티 비교 캡션, 캐시 로더
- `scripts/backtest/app_single_backtest.py` · `scripts/backtest/app_walkforward.py` — 마커 문구, 캐시 로더
- `scripts/backtest/app_parameter_stability.py` — 매도 버퍼 탭의 except 삭제, 캡션의 틀린 예시 삭제, 모듈 docstring · 주석의 「7자산」
- `tests/qbt/test_analysis.py` — 월별 · 연간 재현 테스트, 연간 테스트를 에쿼티 입력으로, 벤치마크 테스트 삭제
- `tests/qbt/test_parameter_stability.py` — 비연속 재현 테스트
- `src/qbt/backtest/CLAUDE.md` · `scripts/CLAUDE.md` — 함수 설명 · 벤치마크 정책 단락 · 마커 문구 · 섹션 목록
- `docs/AUDIT_REPORT.md` — 처리한 항목 표시
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · CLI 옵션 그대로)
- `README.md`: 변경 없음 (벤치마크 섹션 · 마커 문구를 적은 곳이 없다)

### 데이터/결과 영향

- `storage/results/backtest/*/summary.json`(14) · `storage/results/portfolio/*/summary.json`(5) — `monthly_returns` 에 첫 달이 생기고 `yearly_returns` 첫 해 값과 반올림 차가 바뀐다. 그 밖은 그대로
- `storage/results/portfolio/benchmark_qqq.json` — 삭제
- `storage/results/meta.json` — 러너 실행 이력이 늘어난다
- 대시보드: 히트맵 첫 달 칸이 생기고, 포트폴리오 실험 탭의 「연간 수익률 vs QQQ」 섹션이 사라진다

## 6) 단계별 계획(Phases)

### Phase 0 — 수익률 · 고원 정책을 테스트로 먼저 고정(레드)

**작업 내용**:

- [x] `tests/qbt/test_analysis.py` — 월중 시작 에쿼티의 첫 달이 「첫 월말 / 첫 행 − 1」인 월별 테스트, 연간 테스트를 `equity_df` 입력으로 다시 쓰기(월중 시작 첫 해 · 12월 시작 첫 해 · 연말 비율 = 연간 값(월 반올림 복리와 다른 경로) · 여러 해 오름차순 · 1행 이하 빈 리스트), 기존 월별 리스트 입력 테스트와 일관성 테스트 삭제
- [x] `tests/qbt/test_parameter_stability.py` — 비연속 재현 테스트(QQQ 유지일 실측 값 → (2, 10), 최대값이 둘로 갈린 구간 → 앞쪽 최대값의 구간)

**Validation**:

- [x] `poetry run pytest tests/qbt/test_analysis.py tests/qbt/test_parameter_stability.py` — 실패가 새 재현 테스트뿐이다(레드)

---

### Phase 1 — 계산 수정과 벤치마크 삭제(그린 유지)

**작업 내용**:

- [x] `analysis.py` — 기간 말 에쿼티 + 기준점 헬퍼, `calculate_monthly_returns` · `calculate_yearly_returns(equity_df)`, `calculate_benchmark_yearly_returns` 삭제
- [x] 러너 2곳의 호출부, `run_portfolio_backtest.py` 의 `_save_benchmark_qqq_json` · 전 실험 시작일 계산 · 쓰이지 않는 import 삭제
- [x] `parameter_stability.py` — `find_plateau_range` 연속 범위
- [x] 테스트 정리 — `TestCalculateBenchmarkYearlyReturns` 삭제

**Validation**:

- [x] `poetry run pytest tests/qbt/test_analysis.py tests/qbt/test_parameter_stability.py` — 전부 통과(Phase 0 레드 해소)

---

### Phase 2 — 대시보드 표시(그린 유지)

**작업 내용**:

- [x] `app_portfolio_backtest.py` — 벤치마크 섹션 · 로더 · 상수 · 호출 삭제, 분기 기여도 첫 분기, 마커(리밸런싱 제외 · 가격 제거 · 보유중), 에쿼티 비교 차트에 「실험마다 시작일이 다르다」 캡션, 캐시 로더 수정 시각 인자
- [x] `app_single_backtest.py` · `app_walkforward.py` — Buy 마커 가격 제거, 캐시 로더 수정 시각 인자
- [x] `app_parameter_stability.py` — 매도 버퍼 탭의 except 삭제(필터가 실패하면 그대로 멈춘다), 캡션의 틀린 예시 삭제, docstring · 주석의 「7자산」

**Validation**:

- [x] 스크래치에서 앱 모듈을 import 해 확인 — 포트폴리오 5개 실험의 마커(리밸런싱 0 · `$` 0 · 미청산 자산마다 보유중 1), 분기 기여도 막대 합 = 최종 기여
- [x] `grep` — 파일을 읽는 캐시 로더 12곳 모두 수정 시각 인자, 마커 문구에 `$` 0건

---

### Phase 3 — 결과 재산출과 대조

**작업 내용**:

- [x] 재산출 전 결과 사본(스크래치) → `run_single_backtest.py` · `run_portfolio_backtest.py` 실행 → `benchmark_qqq.json` 삭제
- [x] 대조 스크립트(스크래치) — `summary.json` 의 두 키 밖 값 동일, 결과 CSV git diff 0, 첫 달 · 첫 해 = 에쿼티 비율

**Validation**:

- [x] 대조 결과 — 바뀐 키는 `monthly_returns` · `yearly_returns` 뿐, CSV 차이 0, 첫 달 · 첫 해 일치(수치는 진행 로그)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 문서 — `src/qbt/backtest/CLAUDE.md`(월별 · 연간 · 벤치마크 함수 설명, 마커 문구, 섹션 목록) · `scripts/CLAUDE.md`(벤치마크 정책 단락 · 마커 문구 · 섹션 목록) · `docs/AUDIT_REPORT.md`(처리 표시 · 결정 7 정정). `docs/COMMANDS.md` 변경 없음
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 15건 — 버그 5 [무거움 1 · 가벼움 4] · 그 외 10 · 조치: 버그 2 수정 · 그 외 8 반영 · 미조치 5)
- [x] `/code-review xhigh` **2회차** (발견 10건 — 버그 4 [무거움 0 · 가벼움 4] · 그 외 6 · 조치: 버그 3 수정 · 그 외 3 반영 · 미조치 4)
- [x] 수정분 검증 (수정 6건 · 발견 6건 — 무거움 0 · 조치: 고치지 않고 기록)
- [x] `poetry run python validate_project.py` (passed=863, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 첫 해 수익률 · 고원 범위 · 대시보드 표시 수치 수정
2. 백테스트 / 월별 · 연간 수익률의 시작 구간 누락과 고원 범위 오류 수정, QQQ 비교 섹션 삭제
3. 백테스트 / 월별 · 연간 수익률 첫 구간 포함과 에쿼티 기반 연간 계산, 고원 연속 범위, 포트폴리오 마커 · 분기 기여도 · 대시보드 캐시 수정과 결과 재산출
4. 백테스트 / 대시보드가 틀린 첫 해 수익률 · 기간이 다른 QQQ 비교 · 평균 단가 마커를 보이던 문제 해소
5. 백테스트 / 점검 보고서 3단계 표시 수치 바로잡기 — summary.json 18개 재산출과 벤치마크 JSON 삭제

## 7) 리스크(Risks)

- **대시보드는 이 세션이 띄우지 않는다**(루트 `CLAUDE.md`) — 화면 동작은 앱 함수를 불러 확인하고, 최종 확인은 사용자가 한다. 완화: Phase 2 Validation 에서 마커 · 기여도 함수를 실제 결과 파일로 돌린다
- **캐시 키 실수** — 수정 시각을 넘기지 않은 로더가 남으면 옛 결과가 계속 보인다. 완화: `grep` 으로 12곳 전수 확인
- **결과 재산출이 다른 값까지 바꿀 위험** — 완화: Phase 3 대조 스크립트가 두 키 밖 값과 CSV 를 전부 비교한다. `download_data.py` 는 돌리지 않는다
- **리뷰 범위가 넓어질 위험** — 착수 시점에 미커밋 변경(금리 · 운용비율 파일, 합성 · 일별 비교 · TQQQ 결과 재산출, 감사 보고서)이 있으면 `/code-review` 가 그 3만여 줄까지 본다. 완화: 착수 전에 사용자가 그 변경을 먼저 커밋한다
- **마커 정보 감소** — Buy 마커에서 가격이 빠지고 리밸런싱 매매 마커가 사라진다. 가격은 거래 표(단일) · 캔들 툴팁에 있고, 리밸런싱일은 에쿼티 차트 마커로 보인다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md`(2026-10-09 로컬 재검증판) 1-1 · 1-2 · 1-3 · 1-4 · 1-6 · 1-12 · 1-13 · 1-14 · 2-17 · 2-18 · 2-28 · 12-1 · 13-C C1, 결정 3 · 7((가)로 정정)
- 사용자 결정(2026-10-09): 감사 보고서 「B. 결정이 필요한 것」 20건을 추천안대로 확정(「진행」)

### 진행 로그 (KST)

- 2026-10-09 21:56: 계획서 작성(Draft)
- 2026-10-09 22:11 이전(시각 미측정): 자체 검증 — ① 결정 7 을 (가)로 정정(연구 보고서 G.7.2 · H.6 이 저거래 필터 기준 5 를 유지하기로 확정한 기록을 찾았다 — 필터 삭제를 계획에서 뺐다) ② 캐시 로더 수를 「15곳」에서 파일을 읽는 12곳으로 정정(`_build_color_map` 은 파일을 읽지 않고, 벤치마크 로더는 지운다)
- 2026-10-09 22:11: 승인 — 사용자 「승인」. 착수 전 미커밋 변경은 사용자가 커밋함(`7da7c48`, 작업 트리 깨끗). Phase 0 착수
- (아래 다섯 줄은 22:11 – 22:19 사이의 일이고, 단계마다 시각을 재지 않아 기록 시각 22:19 로 적는다)
- 2026-10-09 22:19: Phase 0 — 재현 테스트 추가. 수정 전 실행: 9 failed · 53 passed, 실패는 전부 새 테스트(월별 2 · 연간 5 · 고원 2)
- 2026-10-09 22:19: Phase 1 — `analysis.py`(헬퍼 `_period_end_returns_pct` + 두 함수, 벤치마크 함수 삭제) · `parameter_stability.py` · 러너 2곳. 쓰이지 않게 된 import 3개(`PORTFOLIO_RESULTS_DIR` · `QQQ_DATA_PATH` · `load_stock_data`) 정리. 59 passed(벤치마크 테스트 3개 삭제)
- 2026-10-09 22:19: Phase 2 — 대시보드 4개. 캐시 로더는 계획의 「`mtime` 인자」를 「파일 경로 + 수정 시각」 인자와 호출부 헬퍼 `_cache_args` 로 구현했다(파일 이름이 로더와 호출부 두 곳에 적히지 않게). 앱 함수를 불러 확인: 포트폴리오 5개 실험의 Sell 마커 = 신호 거래 수(0 · 11 · 19 · 18 · 233, 리밸런싱 0 · 0 · 107 · 129 · 227 은 마커 없음), `$` 0, 보유중 16 / 16, 분기 막대 합 = 최종 기여(5 / 5). 단일 마커 163 · WFO 마커 1,736 에 `$` 0. 캐시 로더 12곳 시그니처 확인
- 2026-10-09 22:19: Phase 3 — 재산출. 바뀐 `summary.json` 18개(단일 13 · 포트폴리오 5 — 계획서의 「단일 14」는 잘못 센 값이다), 바뀐 CSV 0. 두 키 밖 값 동일 18 / 18, 첫 달 · 첫 해 = 에쿼티 비율 18 / 18, 전 연도 일치 18 / 18. 첫 해 전 → 후: B&H QQQ 1999 74.16 → 77.11, QQQ B&H 실험 2005 8.39 → 1.90, Q-2-2XS 2007 4.97 → 5.12, 채택 조합 2007 5.71 → 5.78, B&H UGL 2008 없음 → 28.54. `benchmark_qqq.json` 삭제
- 2026-10-09 22:19: 문서(`backtest/CLAUDE.md` · `scripts/CLAUDE.md`) 갱신, 지운 이름 grep 0건(`src` · `scripts` · `tests` · 안내 문서). black: 1 file reformatted
- 2026-10-10 08:16: `/code-review xhigh` 1회차 — 발견 15건. 리뷰가 돌린 품질 검증: passed=858, failed=0, skipped=0
  - 고친 버그 2: ① 시작일이 그 달 · 해의 마지막 거래일이면 길이 0 인 첫 기간이 0.00% 로 나감(가벼움 · 닿는다 — 시작일은 데이터가 정한다) → 첫 행이 첫 기간의 유일한 행이면 그 기간을 내지 않음 + 경계 테스트 2개. 변형 확인: 그 두 줄을 빼면 `test_month_end_start_has_no_zero_length_first_month` · `test_year_end_start_has_no_zero_length_first_year` · `test_yearly_is_equity_ratio_not_compound_of_rounded_monthly` 3 failed, 되돌리면 통과(사본과 `diff -q` 동일) ④ 헬퍼가 날짜 오름차순을 전제(무거운 모양 · 닿지 않음 — 엔진 출력은 정렬돼 있다. 다만 이번 변경이 새로 들인 전제라 `sort_index()` 한 줄로 없앴다)
  - 반영한 그 외 8: ⑦ 마커 함수의 틀린 주석과 불필요한 가드(거래 0건 실험의 `trades.csv` 에도 `asset_id` · `trade_type` 열이 있다) ⑧ 러너 주석의 `Buy $XX.X` ⑨ 거래 유형 값 `TRADE_TYPE_SIGNAL` · `TRADE_TYPE_REBALANCE` 를 `backtest/constants.py` 에 두고 엔진(`portfolio_execution.py` 1줄, 동작 변화 없음)과 앱이 함께 씀 — Scope 밖 파일 2개가 더해졌다 ⑩ 캐시 로더를 저장소 관용(`path: Path, mtime: float`)으로 — 단일 앱은 헬퍼 없이, 포트폴리오 · WFO 는 없을 수 있는 파일 때문에 `_cache_args`(경로를 문자열로 바꾸지 않음) 유지 ⑫ 테스트의 실수 리스트 `==` 비교를 `pytest.approx` 로 ⑬ `전략_검증_보고서.md` G.7.2 의 QQQ `hold_days` 고원 칸 (0, 10) → (2, 10) — 비목표로 미뤘던 것을 리뷰 지적으로 당겼다(같은 CSV 를 새 함수로 다시 재니 QQQ · SPY 8칸 중 이 칸만 다르다) ⑭ `docs/AUDIT_REPORT.md` 처리 표시 ⑮ Scope 에 `README.md` 줄
  - 미조치 5(미룬 지적으로 옮기지 않는다): ② 매도 버퍼 탭의 except 삭제로 원시 예외가 뜬다 — 계획이 의도한 「멈추는 쪽」(기준 2) ③ 저거래 필터가 가운데 값을 빼면 끊긴 범위가 이어진다 — 닿지 않음: 거래 수는 매도 버퍼가 커질수록 줄어(QQQ 25 · 18 · 14 · 12 · 9 · 5) 제외되는 값이 범위 끝에만 온다(기준 1) ⑤ 값이 전부 NaN 인 시리즈에서 ValueError — 닿지 않음: 고원 러너 출력이 깨져야 하고 멈추는 쪽이다(기준 1 · 2) ⑥ `REDUCE_TO_TARGET` 이 보유 전량을 팔면 그 포지션의 마커가 사라진다 — 닿지 않음: 목표 비중이 양수인 자산을 줄이는 주문이라 전량이 되려면 목표 금액이 1주 값보다 작아야 하고, 5개 실험의 리밸런싱 거래 463행 중 0건(기준 1) ⑪ 수정 시각 키로 캐시에 옛 세대가 남는다 — 성능(기준 3)
  - 수정 뒤 확인: 러너 2개 재실행 → 결과 파일 261개 해시 전부 동일, 마커 · 기여도 · 첫 해 대조 스크립트 그대로 통과
- 2026-10-10 08:49: `/code-review xhigh` 2회차(상한) — 발견 10건. 수정 전 사본을 스크래치에 떠 두었다
  - 고친 버그 3: ① 고원 판정의 부동소수 비교 — 정확히 80% 인 값이 빠져 고원이 잘린다(0.05 × 0.8 = 0.04000000000000001, 실제 TLT 유지일 행이 (2, 7) 대신 (2, 2)). 가벼움(고원이 좁게 나오는 쪽) · 닿는다(고원 재실행) → 비교에 `EPSILON` 여유 ③ 러너가 유효 시작일을 루프 안에서 하나씩 계산해, 뒤 실험의 데이터 문제를 앞 실험 결과를 덮어쓴 뒤에야 만난다 — 가벼움 · 닿는다 → 실행 전에 대상 실험 전부 계산 ④ 값이 전부 NaN 이면 ValueError — docstring 계약(없으면 None)을 `if not max_val > 0` 로 복원(닿지 않음이나 같은 줄의 0줄짜리 수정)
  - 반영한 그 외 3: ⑤ `sort_index()` 를 고정하는 테스트 ⑧ 첫 기간 특수 처리를 `equity.iloc[1:]` 로 단순화(`count()` 집계와 분기 삭제) ⑨ 단일 앱 히트맵 docstring 의 「복리」
  - 미조치 4: ② 저거래 필터가 가운데 값을 빼면 끊긴 범위가 이어진다 — 닿지 않음(1회차와 같은 판정, 기준 1) ⑥ `_cache_args` 가 두 앱에 한 벌씩 — 그 외(기준 3, 감사 보고서 7-1 행에 남김) ⑦ 캐시 상한 없음 — 성능(기준 3, 같은 행) ⑩ `TRADE_TYPE_REBALANCE` 가 한 파일에서만 쓰이는데 도메인 상수 파일에 있다 — 그 외(기준 3). 짝인 값을 갈라 놓지 않으려고 그대로 두고 감사 보고서 3-8 행에 남김
  - 변형 확인(각 한 줄을 바꿔 실패를 보고 되돌림, 사본과 `diff -q` 동일): `- EPSILON` 제거 → `test_find_plateau_range_keeps_value_exactly_at_threshold` 1 failed / `if max_val <= 0` 복귀 → `test_find_plateau_range_returns_none_for_all_nan` 1 failed / `.sort_index()` 제거 → `test_row_order_does_not_change_result` 1 failed / `equity.iloc[1:]` 제거 → 경계 테스트 3 failed
  - 수정 뒤: 러너 2개 재실행 → 결과 파일 261개 해시 전부 동일. 새 함수로 다시 잰 QQQ · SPY 고원 8칸이 보고서 G.7.2 표와 일치
- 2026-10-10 08:49: 수정분 검증(`general-purpose` 서브에이전트, 수정분 diff 와 겨냥한 지적만 전달) — hunk 8개 모두 ① ② ③ 에 답. 정상 입력에서 결과가 바뀌는 경우 0(실제 equity 18개 × 월 · 연 72건 불일치 0, 경계 17종 불일치 0, 무작위 40,000건 불일치 0). 실제 고원 CSV 24행 중 바뀐 것은 TLT 유지일 1행이고 새 값이 정의에 맞다. 2자리 · 4자리 값에서 `EPSILON` 여유로 기준 미달이 통과하는 입력 0(쌍 4,504,500개 전수). 발견 6건(무거움 0) — 규칙대로 고치지 않는다
  - 거른 발견(미룬 지적으로 옮기지 않는다): ① 반올림 안 된 아주 작은 값(최대 1.2e-12 이하 등)에서는 여유 때문에 미달 값이 고원에 든다 — 닿지 않음: 대시보드 경로는 2자리 CSV(기준 1) ② 전부 NaN 이면 죽던 것이 None — 닿지 않음 · 계약대로(기준 1) ③ NaN 에쿼티에서 동작이 바뀜(달을 말없이 버림 → NaN 출력 · 빈 결과 → IndexError) — 닿지 않음: 마지막 에쿼티가 NaN 이면 `calculate_summary` 가 먼저 멈춘다(기준 1) ④ 테스트가 여유의 크기를 고정하지 않는다(0.005 로 바꿔도 통과) — 닿지 않음: 여유는 전역 상수 `EPSILON`(1e-12)이라 그 값이 0.002 를 넘도록 바뀌어야 한다(기준 1) ⑤ 기준이 16384 이상이면 여유가 듣지 않는다 — 닿지 않음: Calmar 범위 밖(기준 1) ⑥ 선계산이 막는 것은 시작일 계산의 실패까지다(하한 적용 뒤 행 부족 등은 여전히 루프 안) — 막는 쪽(기준 2)
- 2026-10-10 08:49: 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=863, failed=0, skipped=0
- 2026-10-10 08:49: 근거 승격 — 월별 · 연간 수익률의 기준점과 길이 0 구간 규칙 · 고원의 연속 범위와 부동소수 여유 · 마커에 가격을 적지 않는 이유는 각 함수 docstring · 주석에, 고원 표의 바뀐 칸은 `전략_검증_보고서.md` G.7.2 에, 처리 표시와 남은 정리 거리는 `docs/AUDIT_REPORT.md` 에 있다. 저거래 필터를 지우지 않는 근거는 이미 보고서 H.6 에 있다. 미룬 지적: 옮길 것 없음(위 거름 기록)
- 2026-10-10 08:59: `/commit` — 대상은 unstaged 전체(staged · untracked 없음) 37파일. 바뀐 `summary.json` 18개의 최상위 키 차이가 `monthly_returns` · `yearly_returns` 뿐임을 다시 확인(18 / 18). 후보 5개를 Commit Messages 절에 옮기고 Done

---
