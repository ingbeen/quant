# Implementation Plan: 설정 · 파라미터 검증 — 잘못된 설정값이 에러 없이 도는 길을 한 곳에서 막는다

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

> 상태는 🟡 Draft / 🔄 In Progress / ✅ Done. Done 조건과 기록 규칙은 `/impl-plan` 「3) 스킵 및 완료 규칙」이며 `~/.claude/hooks/plan_lint.py` 가 저장 때 검사한다.

---

**작성일**: 2026-10-10 22:26
**마지막 업데이트**: 2026-10-11 11:15
**관련 범위**: backtest(`strategies/buffer_zone.py` · `engines/backtest_engine.py` · `engines/portfolio_data.py` · `engines/portfolio_engine.py` · `engines/portfolio_planning.py` · `portfolio_types.py`), tests(`tests/qbt/`)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`, `docs/AUDIT_REPORT.md`(19절 7단계), `docs/DEFERRED_FINDINGS.md`

---

## 1) 목표(Goal)

- [x] 목표 1: 버퍼존 비율 · 유지일수의 범위 검증을 전략 생성자 한 곳에 두어, 전략을 만드는 모든 경로(단일 백테스트 · 그리드 · 워크포워드 · 포트폴리오 슬롯 · 배분 규칙)가 범위 밖 값에서 멈춘다
- [x] 목표 2: 포트폴리오 설정 검증이 총 자본 · 슬롯 비중 · `strategy_id` · 「여러 매매법이 함께 드는 매매 데이터는 자산 id 하나」를 시세를 읽기 전에 본다
- [x] 목표 3: 슬롯 순서가 시작일을 바꾸는 신호 시세 캐시를 지우고, 신호 · 매매 시세 읽기 세 벌을 공용 함수 하나로 줄인다
- [x] 목표 4: 지금 결과 파일은 하나도 바뀌지 않는다

## 2) 비목표(Non-Goals)

- **이동평균 기간(`ma_window`) 검증의 자리** — 그대로 둔다. `add_single_moving_average` 가 `window < 1` 을 막고(`tests/qbt/test_analysis.py` `test_invalid_window`), 이동평균 열은 그 함수로만 만들어진다. 전략 생성자는 열 이름만 받아 기간을 모른다
- **「신호 시세가 매매 시세보다 길어도 이동평균은 두 시세가 겹치는 기간에서 계산한다」는 동작** — 그대로 둔다. 전체 신호 시세로 먼저 계산하게 바꾸면 Q-2-2XS 계열의 시작일이 당겨져(SSO · QLD 상장일 2006-06-21 기준) 모든 결과와 연구 문서 수치가 바뀐다. 이 계획서는 슬롯 순서에 따라 그 동작이 갈리던 것만 없앤다(설계 결정 3)
- **슬롯 파라미터를 시세를 읽기 전에 검증** — 하지 않는다. 범위 밖 슬롯 파라미터는 장부를 만들 때(시세를 읽은 뒤) 전략 생성자가 멈춘다. 설정 검증에서 전략을 한 번 만들어 보면 더 일찍 멈추지만, 멈추는 것은 같고 검증 경로가 둘이 된다 (조정 — 리뷰 1 · 2회차가 연속으로 짚어 사용자 결정으로 넣었다. 진행 로그 2026-10-11 08:52)
- **`MIN_BUY_BUFFER_ZONE_PCT` · `MIN_SELL_BUFFER_ZONE_PCT` · `MIN_HOLD_DAYS` 의 자리** — 이 계획서 뒤에는 `buffer_zone.py` 한 파일만 쓰게 되어 상수 3계층 규칙상 그 파일로 가야 한다. 한 파일 전용 상수 정리는 11단계(점검 보고서 4-6)가 묶어서 하므로 그 행에 덧붙인다
- **배분 규칙 생성자의 이동평균 기간 검증**(버린 미룬 지적 9 의 나머지) — 버퍼존 비율 · 유지일수만 목표 1 로 덤으로 막힌다
- **쓰이지 않는 설정 칸**(`AllocationAssetConfig.signal_data_path` 등, 점검 보고서 6-5) — 11단계

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 점검 보고서 19절 7단계다. 대상은 5-2 · 9-6 · 9-10 · 5-5 · 2-11 · 7-12 · 3-2 와 고치기로 한 미룬 지적 「같은 매매 데이터를 매매법마다 다른 자산 id 로 들면 상계되지 않는다」다
- 대상마다 지금 무엇이 틀리는가(2026-10-10 지금 코드에서 다시 확인. 「점검 보고서 실측」은 2026-10-09 측정값을 옮긴 것이다)

| 항목 | 지금 | 근거 |
|---|---|---|
| 5-2 · 9-6(파라미터) | 같은 네 검사(이동평균 기간 · 매수 버퍼 · 매도 버퍼 · 유지일)가 `resolve_buffer_params` 와 `run_buffer_strategy` 에 두 벌이고, 전략을 만드는 9곳 중 이 검사를 지나는 것은 2곳뿐이다. 포트폴리오 슬롯 · 그리드 · 워크포워드 · EWY 배분 규칙은 검증 없이 전략을 만든다 | `grep 'BufferZoneStrategy('` src 9곳 — `runners.py` 1 · `backtest_engine.py` 2 · `walkforward.py` 4 · `strategy_registry.py` 1 · `allocators/ewy_buffer_zone.py` 1. 검사를 지나는 것은 `runners.py`(`resolve_params_for_config`)와 `run_buffer_strategy`. 점검 보고서 실측: 슬롯 `hold_days=-1` → 최종 자본 98,469,592(정상 106,497,267), `sell_buffer=1.5` → 228,414,443 · 매도 0건, `buy_buffer=5.0` → 거래 0건, 모두 예외 없음 |
| 9-6(자본) | 총 자본 0 · 음수 · NaN 이 설정 검증을 통과해 엔진 안에서 엉뚱한 예외로 멈춘다 | `validate_portfolio_config` 에 자본 검사가 없다. 자본을 보는 곳은 실행 끝의 `build_combined_equity` 하나 |
| 9-10 | 슬롯 비중 0 을 설정 검증이 허용하는데(문구도 「0 이상」) 엔진은 0 을 못 다뤄 첫 매수 신호에서 `RuntimeError`(내부 불변조건 위반)로 멈춘다 | `_validate_slots` 의 `target_weight < 0` 검사. 점검 보고서 실측(두 번 재현) |
| 5-5 | 「미등록 strategy_id」 검사가 세 벌이고, 실제로 닿는 것은 시세 두 개를 읽은 뒤의 첫째 하나다 | `portfolio_data.py` `load_and_prepare_data` · `portfolio_engine.py` 워밍업 계산 · `portfolio_planning.py` `create_strategy_for_slot`(호출처 1곳, 테스트 0곳) |
| 2-11 | 신호 시세를 「경로 · 전략 · 이동평균 기간」으로 캐시해, 같은 신호를 다른 매매 데이터로 드는 슬롯이 앞 슬롯의 매매 데이터 기간으로 잘린 이동평균을 받는다 — 슬롯 순서가 시작일을 바꾼다 | 점검 보고서 실측: SPY 신호 두 슬롯이 `spy, sso` 순이면 2006-06-21 시작 · 113,144,510, `sso, spy` 순이면 2007-04-09 · 92,424,677. 지금 설정에서는 0건(아래 실측) |
| 7-12 | 「신호 · 매매 시세를 읽고 경로가 다르면 겹치는 기간으로 자른다」가 `utils.data_loader.load_signal_trade_pair` 말고도 세 벌 있다 | `portfolio_data.py` `load_and_prepare_data` · `portfolio_engine.py` 캐시 적중 분기 · 배분 규칙 자산 분기 |
| 3-2 | `AssetSlotConfig` 기본값 200 / 0.03 / 0.05 / 3 이 `FIXED_4P_*` 와 같은 값의 숫자다 | `portfolio_types.py` `AssetSlotConfig`. `BufferZoneConfig` 는 이미 상수를 쓴다 |
| 미룬 지적 | 설정 검증이 「같은 자산 id → 같은 매매 데이터」만 보고 반대 방향은 보지 않는다. 금 매매법의 id 만 `gld` → `gold` 로 바꾸면 검증 · 검사기를 통과하고 상계 2행 · 절감 487.84원이 사라진다 | `docs/DEFERRED_FINDINGS.md` 첫 항목, 점검 보고서 17절 3번 실측 |

- **지금 설정 전부에서 새 검사에 걸리는 값** — 등록 실험 5 · 단독 그리드 149 · 조합 그리드 152, 모두 306개 설정(슬롯 1,295개, 그중 버퍼존 609개)을 만들어 셌다(스크래치 `step7/measure_configs.py`, 2026-10-10)

| 넣을 검사 | 걸리는 수 |
|---|---|
| 총 자본 0 이하 | 0 |
| 슬롯 비중 0 이하 · NaN | 0 |
| 등록되지 않은 `strategy_id` | 0 |
| 매수 · 매도 버퍼존 비율이 하한 미만이거나 1 이상, 유지일수 음수, 이동평균 기간 1 미만 | 0 |
| 여러 매매법이 함께 드는 매매 데이터(170건) 중 자산 id 가 둘 이상인 것 | 0 |
| 신호 캐시에 적중하는 슬롯 | 14 (단독 그리드 14 실행) — 그중 신호 경로 ≠ 매매 경로인 것 0 |

### 설계 결정

1. **버퍼존 비율 · 유지일수는 `BufferZoneStrategy.__init__` 이 검증한다.** 전략을 만드는 9곳이 모두 그 생성자를 지나므로 한 곳으로 충분하다. `BufferStrategyParams.__post_init__` 은 2곳만 덮는다
   - 범위: 매수 · 매도 버퍼존 비율은 하한(`MIN_*_BUFFER_ZONE_PCT`) 이상 **1 미만**, 유지일수는 `MIN_HOLD_DAYS` 이상. 비교를 `not 하한 <= 값 < 1` 꼴로 써서 NaN 도 걸린다
   - 상한 1 은 새로 넣는 것이다. 문서의 정의역이 0 ~ 1 이고(`src/qbt/backtest/CLAUDE.md` 도메인 규칙 1), 단위를 % 로 잘못 적은 값(5.0)과 밴드가 0 이하가 되는 매도 버퍼(1.5)가 지금은 에러 없이 돈다
   - 뒤따라 지우는 것: `resolve_buffer_params`(직접 호출 src 1곳 = `resolve_params_for_config`, 테스트 4곳)와 `run_buffer_strategy` 의 검사 네 줄. `resolve_params_for_config` 는 남긴다 — 호출처 5곳(`runners.py` 1 · 고원 러너 4)이 설정 → 파라미터 변환으로 쓴다
   - 이동평균 기간은 비목표 참고. `run_buffer_strategy` 의 `ma_window < 1` 줄을 지워도 `add_single_moving_average` 가 같은 값에서 멈춘다. 기존 테스트가 넣던 가짜 `ma_0` 열(이동평균 계산을 건너뛰게 한다)은 프로덕션 코드가 만들 수 없는 입력이라 픽스처에서 뺀다
   - 달라지는 것: `run_buffer_strategy` 가 범위 밖 값에서 멈추는 시점이 「데이터 처리 전」에서 「이동평균 계산 뒤 전략을 만들 때」로 늦어진다. 멈추는 것과 예외 종류(`ValueError`)는 같고 문구의 파라미터 이름이 생성자 인자(`buy_buffer_pct` 등)로 바뀐다
2. **포트폴리오 설정 검증에 넷을 넣는다** — 모두 시세를 읽기 전에 멈춘다
   - `validate_portfolio_config`: `total_capital > 0` 이 아니면 `ValueError`
   - `_validate_slots`: 슬롯 비중이 `> 0` 이 아니면 `ValueError`(지금은 `< 0` 만 막는다), `strategy_id` 가 `STRATEGY_REGISTRY` 에 없으면 `ValueError`
   - `validate_portfolio_config`: 매매 데이터 경로 하나를 둘 이상의 매매법이 들면 그 경로의 자산 id 는 하나여야 한다. 한 매매법 안에서 같은 경로를 다른 id 로 드는 것은 막지 않는다(상계는 매매법 사이의 일이고, 기존 테스트가 쓰는 모양이다). 경로는 `Path` 값으로 견준다 — 기존 정방향 검사와 같은 기준
   - 뒤따라 지우는 것: 「미등록 strategy_id」 가드 세 곳(직접 인덱싱으로), `create_strategy_for_slot` 래퍼, `build_combined_equity` 의 자본 검사(호출처는 엔진 1곳이고 설정 검증 뒤다)
3. **신호 시세 캐시를 지우고 슬롯마다 `load_and_prepare_data` 로 읽는다.** 슬롯의 이동평균은 늘 「신호 · 매매 시세가 겹치는 기간으로 자른 뒤」 계산된다 — 지금 캐시에 적중하지 않는 슬롯의 동작이고, 등록 실험과 그리드의 결과가 이 동작에서 나왔다
   - 버린 안: 이동평균을 전체 신호 시세로 먼저 계산한 뒤 자르기. 슬롯 순서 의존은 같이 사라지지만 결과가 모두 바뀐다(비목표)
   - 지금 설정에서 캐시 적중 슬롯 14개는 모두 신호 경로 = 매매 경로라 자를 것이 없다. 결과가 바뀌지 않아야 하고 마지막 Phase 에서 사본 재실행으로 확인한다
4. **신호 · 매매 시세 읽기는 `load_signal_trade_pair` 하나로** — `load_and_prepare_data` 와 배분 규칙 자산 분기가 그 함수를 부른다. 그 함수의 호출처는 지금 src 1곳(`runners.py`) · scripts 2곳이고 같은 로직이다(경로가 같으면 한 번 읽어 복사, 다르면 겹치는 기간)
5. **`AssetSlotConfig` 기본값은 `FIXED_4P_*`** — `constants.py` 는 `typing` 만 import 해 순환이 없다
6. **테스트** — 새 검사는 수정 전 실패를 먼저 본다(Phase 0). 정책 값(하한 0.01)은 결정 14 대로 테스트에 손으로 고정한다
   - `resolve_buffer_params` 의 테스트 넷은 지운다. 이동평균 기간 셋은 `test_invalid_window` 가 같은 계약을 이미 고정하고, 반환 타입 하나는 대상 함수가 없어진다. 점검 보고서 6-T 의 「지우지 않고 검사 대상을 전략 생성자로」는 이동평균 기간에는 맞지 않는다(생성자가 기간을 모른다) — 대신 생성자 범위 테스트를 새로 쓴다
   - 신호 공유 테스트(`TestQQQTQQQSharedSignal`)는 TQQQ 매매 시세를 돌파 없는 평탄한 시세로 바꾼다 — TQQQ 가 사고판다면 신호가 신호 시세에서 온 것이다(점검 보고서 2-11 의 「함께 볼 것」)
   - 캐시 키 테스트(`TestCacheKeyWithDifferentMAParams`)는 캐시가 없어지므로 이름과 설명을 「같은 신호 시세를 드는 슬롯」으로 고치고, 슬롯 순서 테스트를 같은 클래스에 더한다

### 사본 재현 (착수 전 확인, 2026-10-10)

저장소 밖 사본(스크래치 `step7/`)에 이 계획서의 변경을 그대로 적용해 전제를 확인했다. 저장소 코드는 건드리지 않았다.

- **수정 전 코드에 새 테스트만 얹으면 23 failed** — 생성자 범위 9 · 포트폴리오 슬롯 파라미터 3 · 설정 검증 8(총 자본 3 · 슬롯 비중 3 · `strategy_id` 1 · 다른 자산 id 1) · 슬롯 순서 1 · 예외 문구 패턴 2. 통과가 정답인 테스트(경계값 4 · 같은 id 통과 · 한 매매법 안 통과)는 수정 전에도 통과한다
- **수정 뒤 908 passed** (지금 885 − 지우는 테스트 4 + 새 테스트 27), Ruff 통과, PyRight 0 errors(src · tests)
- **기존 테스트 중 고쳐야 하는 것은 셋** — `resolve_buffer_params` 를 import 하는 `test_buffer_zone.py`, 예외 문구를 견주는 `test_buffer_zone_run.py` 의 파라미터 넷, 두 매매법이 더미 경로 하나를 다른 id 로 드는 `test_portfolio_methods.py` 의 정상 설정 테스트 하나. 그 밖의 테스트는 그대로 통과한다
- **변형 15종을 모두 잡는다** — 생성자 검증 줄 삭제 3 · 상한을 「1 이하」로 2 · 하한을 「초과」로 2, 총 자본 검증 삭제 · 「0 미만만」 2, 슬롯 비중을 옛 검사로 1, `strategy_id` 검증 삭제 1, 다른 자산 id 검사 삭제 · 매매법 수 조건 삭제 2, 신호 캐시 되살리기 1, 슬롯 신호를 매매 시세에서 읽기 1
- **결과 파일 변화 0** — 사본에서 러너 여섯(단일 · 포트폴리오 · 단독 그리드 · 조합 그리드 · 고원 · 워크포워드)을 모두 돌렸다. `storage/` 324개 파일 중 저장소와 다른 것은 `storage/results/meta.json` 하나이고, 그 차이는 실행 시각 · 소요 시간과 이력 항목 추가뿐이다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「스크립트 실행 규칙」
- `src/qbt/CLAUDE.md` · `src/qbt/backtest/CLAUDE.md` · `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md` · 전역 `~/.claude/rules/python-tests.md` · `~/.claude/rules/python.md`
- `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 범위 밖 버퍼존 비율 · 유지일수로는 전략을 만들 수 없고, 포트폴리오 슬롯 경로에서도 멈춘다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] 총 자본 0 이하 · 슬롯 비중 0 이하 · 미등록 `strategy_id` · 여러 매매법이 다른 자산 id 로 드는 같은 매매 데이터가 설정 검증에서 멈춘다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] 같은 신호 시세를 다른 매매 데이터로 드는 두 슬롯의 순서를 바꿔도 시작일과 자본 곡선이 같다(재현 테스트가 수정 전 실패 → 수정 후 통과)
- [x] 결과 파일 변화 0 — 사본에서 단일 · 포트폴리오 · 단독 그리드 · 조합 그리드 · 고원 · 워크포워드 러너를 다시 돌린 결과가 저장된 결과와 같다
- [x] 회귀/신규 테스트 추가
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료
- [x] 필요한 문서 업데이트 — `src/qbt/backtest/CLAUDE.md`(검증 자리 · 지운 함수 · 신호 시세 읽기) · `docs/AUDIT_REPORT.md`(처리 표시 · 19절 · 4-6 · 6-T). `README.md` · `docs/COMMANDS.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (결정 근거·실측 수치를 `.claude/plan-config.json` 의 `evidence_home` 이 정한 폴더로 이관. 그 폴더를 요청할 때만
      고치는 저장소면 반영안을 제안하고 「제안함 — 승인 · 반영 / 보류」로 적는다. `/impl-plan` 스킬 "근거 승격" 참고)
- [x] 미룬 지적 옮김 — 새로 옮긴 것 0(미조치 지적은 거르는 기준에 걸리거나 점검 보고서의 기존 행에 덧붙였다), 이 계획서가 고친 항목 하나(같은 매매 데이터 · 다른 자산 id)는 파일에서 지웠다. 고치지 않은 리뷰 지적을 거르는 기준으로 걸러 `deferred_findings` 파일로 옮겼다. 계획서 없이 읽히게 썼다.
      거른 지적은 진행 로그에 기준 번호와 함께 남기고 Done 보고에 표로 냈다
      이 계획서가 그 파일의 항목을 고쳤다면 그 항목을 지웠다
      (둘 다 없으면 「해당 없음」. `/impl-plan` 의 `review.md` 「미룬 지적 옮기기」 참고)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/strategies/buffer_zone.py` — 생성자 검증, `resolve_buffer_params` 삭제, 쓰이지 않게 되는 로거 삭제
- `src/qbt/backtest/engines/backtest_engine.py` — `run_buffer_strategy` 의 검사 네 줄과 그 상수 import 삭제
- `src/qbt/backtest/engines/portfolio_data.py` — 설정 검증 넷, `load_and_prepare_data` 를 공용 로더로, 가드 · 자본 검사 삭제
- `src/qbt/backtest/engines/portfolio_engine.py` — 신호 캐시 삭제, 배분 규칙 자산을 공용 로더로, 가드 삭제, 전략 생성 인라인
- `src/qbt/backtest/engines/portfolio_planning.py` — `create_strategy_for_slot` 삭제
- `src/qbt/backtest/portfolio_types.py` — `AssetSlotConfig` 기본값과 그 설명
- `tests/qbt/test_strategy_interface.py` · `test_buffer_zone.py` · `test_buffer_zone_run.py` · `test_portfolio_methods.py` · `test_portfolio_backtest_scenarios.py`
- `src/qbt/backtest/CLAUDE.md` · `docs/AUDIT_REPORT.md` · `docs/DEFERRED_FINDINGS.md`(첫 항목 — 착수 때 「고치는 중」, Done 때 삭제)
- `docs/COMMANDS.md`: 변경 없음 (실행 명령 · 옵션 그대로)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 없음. 새 검사는 지금 설정 306개에서 0건이고, 캐시를 지워도 달라지는 슬롯이 없다(위 실측). 확인용 재실행은 사본에서 한다 — 저장소의 `storage/` 는 건드리지 않는다

## 6) 단계별 계획(Phases)

### Phase 0 — 재현 테스트(레드)

**작업 내용**:

- [x] `test_strategy_interface.py` — 범위 밖 파라미터로 `BufferZoneStrategy` 를 만들면 `ValueError`(하한 미만 · 1 · 1 초과 · NaN · 음수 유지일), 경계값(하한 · 유지일 0 · 1 바로 아래)은 받는다
- [x] `test_portfolio_backtest_scenarios.py` — 슬롯의 `hold_days=-1` · `sell_buffer_zone_pct=1.5` · `buy_buffer_zone_pct=5.0` 에서 `run_portfolio_backtest` 가 `ValueError`
- [x] `test_portfolio_methods.py` — 총 자본 0 · 음수 · NaN, 슬롯 비중 0 · 음수 · NaN, 미등록 `strategy_id`, 두 매매법이 같은 매매 데이터를 다른 자산 id 로 듦 → 각각 `ValueError`. 같은 id 로 듦 · 한 매매법 안의 다른 id 는 통과
- [x] `test_portfolio_backtest_scenarios.py` — 같은 신호 시세 · 다른 매매 데이터인 두 슬롯의 순서를 바꿔도 유효 시작일과 날짜별 자본이 같다

**Validation**:

- [x] 새 테스트가 지금 코드에서 실패한다(통과가 정답인 경계 · 통과 케이스는 통과)

---

### Phase 1 — 버퍼존 파라미터 검증을 전략 생성자로(그린)

**작업 내용**:

- [x] `buffer_zone.py` — `BufferZoneStrategy.__init__` 에 범위 검증, `resolve_buffer_params` 삭제, `resolve_params_for_config` 가 `BufferStrategyParams` 를 직접 만든다
- [x] `backtest_engine.py` — `run_buffer_strategy` 의 검사 네 줄 삭제
- [x] `test_buffer_zone.py` — `resolve_buffer_params` 테스트 넷 삭제 · `test_buffer_zone_run.py` — 예외 문구 패턴 넷과 가짜 `ma_0` 열

**Validation**:

- [x] `poetry run pytest tests/qbt/test_strategy_interface.py tests/qbt/test_buffer_zone.py tests/qbt/test_buffer_zone_run.py tests/qbt/test_allocators.py tests/qbt/test_walkforward_schedule.py` — 전부 통과

---

### Phase 2 — 포트폴리오 설정 검증 · 신호 캐시 삭제 · 공용 로더(그린)

**작업 내용**:

- [x] `portfolio_data.py` — 설정 검증 넷, `load_and_prepare_data` 를 `load_signal_trade_pair` 로, 가드 · 자본 검사 삭제
- [x] `portfolio_engine.py` — 신호 캐시 삭제, 배분 규칙 자산을 `load_signal_trade_pair` 로, 가드 삭제, 전략 생성을 레지스트리 직접 호출로
- [x] `portfolio_planning.py` — `create_strategy_for_slot` 삭제
- [x] `portfolio_types.py` — `AssetSlotConfig` 기본값을 `FIXED_4P_*` 로
- [x] `test_portfolio_methods.py` — 두 매매법이 더미 경로 하나를 다른 id 로 들던 정상 설정 테스트의 경로를 나눈다 · `test_portfolio_backtest_scenarios.py` — 신호 공유 테스트의 매매 시세, 캐시 키 테스트의 이름 · 설명

**Validation**:

- [x] 포트폴리오 · 보완 전략 · 조합 테스트 파일 `poetry run pytest tests/qbt/test_portfolio_*.py tests/qbt/test_supplement_experiment.py tests/qbt/test_combo_experiment.py tests/qbt/test_allocators.py` — 전부 통과(Phase 0 의 테스트 포함)
- [x] 설정 306개가 새 검증을 모두 통과한다(스크래치)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

> 🔴 **체크박스와 상태를 먼저 확정하고, `/commit` 은 맨 마지막에** — 이유는 `/impl-plan` 「5) Commit Messages」.

- [x] 결과 파일 변화 0 확인(스크래치 사본) — 단일 · 포트폴리오 · 단독 그리드 · 조합 그리드 · 고원 · 워크포워드 러너를 돌려 `storage/results/` 가 저장소와 같은지(실행 시각이 드는 `meta.json` 제외)
- [x] 새 검사의 변형 확인 — 「사본 재현」의 변형 15종을 최종 코드에 다시 돌려 모두 실패하는 것을 본다
- [x] 문서 — `src/qbt/backtest/CLAUDE.md` · `docs/AUDIT_REPORT.md` · `docs/DEFERRED_FINDINGS.md`(고친 항목 삭제). `docs/COMMANDS.md` · `README.md` 변경 없음
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      대화에만 내면 그 절이 빈 채로 남는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서는 `/code-review` → 품질 검증이다. 고칠 것 · 회차 상한 · 수정분 검증은 `/impl-plan` 의 `review.md` 가 정한다.

- [x] `/code-review xhigh` **1회차** (발견 10건 — 버그 6 [무거움 4 · 가벼움 2] · 그 외 4 · 조치: 무거움 2 수정(테스트 보강) · 무거움 2 미조치(닿지 않음) · 가벼움 2 미조치 · 그 외 3 반영 · 1 미조치)
- [x] `/code-review xhigh` **2회차** (발견 9건 — 버그 7 [무거움 6 · 가벼움 1] · 그 외 2 · 조치: 무거움 1 수정(테스트 보강) · 가벼움 1 수정(사용자 결정) · 무거움 5 미조치(닿지 않음 4 · 다른 단계 행에 덧붙임 1) · 그 외 1 반영 · 1 미조치)
- [x] 수정분 검증 (2회차 수정 6 hunk · 발견 4건 + 참고 1 — 무거움 0 · 조치: 문구 발견 1건과 참고 1건은 docstring 만 사실에 맞게 고치고 코드 동일을 AST 로 확인 · 나머지 가벼움 3건은 기록)
- [x] `poetry run python validate_project.py` (passed=911, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다** — 추측으로 적은 줄은 그대로 나간다.

1. 백테스트 / 설정 · 파라미터 검증을 한 곳으로 정리와 신호 시세 캐시 삭제
2. 백테스트 / 버퍼존 파라미터 검증을 전략 생성자로 통합, 포트폴리오 설정 검증 5가지 추가, 슬롯 순서에 따라 시작일이 달라지던 신호 시세 캐시 삭제
3. 백테스트 / 범위 밖 설정값이 에러 없이 다른 결과를 내던 경로 차단
4. 백테스트 / 점검 보고서 7단계 처리 — 전략 파라미터 · 포트폴리오 설정 검증과 미룬 지적 1건 처리
5. 백테스트 / resolve_buffer_params · create_strategy_for_slot 삭제와 load_signal_trade_pair 재사용, AssetSlotConfig 기본값의 4P 상수화, 설정 검증 단계의 슬롯 파라미터 사전 확인

## 7) 리스크(Risks)

- **새 검증이 정상 실행을 멈출 수 있다** — 등록 실험 · 그리드 · 워크포워드 · 고원의 값이 새 범위에 걸리면 러너가 멈춘다. 완화: 설정 306개에서 0건을 먼저 쟀고(Context), 그리드 · 고원의 파라미터 목록은 버퍼 0.01 ~ 0.15 · 유지일 0 ~ 10 이다. 마지막 Phase 에서 사본으로 러너 여섯을 모두 돌린다
- **캐시를 지우면 결과가 바뀔 수 있다** — 캐시 적중 슬롯 14개가 모두 신호 = 매매 경로라는 실측에 기댄다. 완화: 사본에서 단독 그리드를 다시 돌려 결과 CSV 가 같은지 본다. 다르면 멈추고 보고한다
- **슬롯마다 시세를 따로 읽어 느려질 수 있다** — 캐시가 아끼던 것은 14개 실행의 CSV 한 번씩이다. 사본에서 단독 그리드를 수정 전 · 후 코드로 번갈아 두 번씩 쟀다: 수정 전 75초 · 75초, 수정 후 74초 · 74초(느려지지 않는다)
- **예외 종류가 달라지는 곳** — 설정 검증을 거치지 않고 `load_and_prepare_data` 를 직접 부르면 미등록 `strategy_id` 가 `ValueError` 대신 `KeyError` 로 멈춘다. 호출처는 엔진 1곳이고 설정 검증 뒤다(멈추는 쪽)
- **역방향 검사가 정상 설정을 막을 수 있다** — 같은 종목을 일부러 두 id 로 나눠 드는 다중 매매법 설정은 이제 막힌다. 지금 설정 306개에서 0건이고, 그 모양은 상계가 빠져 계좌 손익이 낮게 나오는 결함 그 자체다

## 8) 메모(Notes)

- 근거: `docs/AUDIT_REPORT.md` 5-2 · 9-6 · 9-10 · 5-5 · 2-11 · 7-12 · 3-2 · 17절 3번 · 19절 7단계
- 점검 보고서의 줄 번호는 기준 커밋(`40011ad`) 값이라 지금 코드와 어긋난다(예: 5-2 의 `backtest_engine.py:555-562` 는 지금 `run_buffer_strategy` 의 581 – 589줄). 이 계획서는 함수 이름으로 가리킨다

### 진행 로그 (KST)

- 2026-10-10 22:26: 계획서 작성(Draft). 대상 코드와 호출처를 읽고, 지금 설정 306개에서 새 검사에 걸리는 값이 0건임을 쟀다(Context 표)
- 2026-10-10 22:42: 사본 재현을 마쳤다(Context 「사본 재현」). 사본의 러너 소요 — 단일 4초 · 포트폴리오 12초 · 조합 그리드 130초 · 고원 41초 · 워크포워드 141초, 단독 그리드는 따로 재서 수정 전 75초 · 수정 후 74초. 사본의 변경 규모는 src 6파일 추가 79줄 · 삭제 148줄, tests 5파일 추가 193줄 · 삭제 106줄(포맷 적용 전)
- 2026-10-10 23:00: 승인 — 사용자 「승인」. 미룬 지적 첫 항목(같은 매매 데이터 · 다른 자산 id)의 출처에 「고치는 중」을 달았다. Phase 0 착수
- 2026-10-11 08:09: Phase 0 — 사본에서 검증한 테스트 5파일을 저장소에 넣었다. 수정 전 코드에서 23 failed · 148 passed (새 테스트 21 + Phase 1 에서 고칠 예외 문구 패턴 2). 사본에서 잰 23건과 같다
- 2026-10-11 08:10: Phase 1 — `buffer_zone.py` 생성자 검증 · `resolve_buffer_params` 삭제(로거도 쓰이지 않게 되어 함께), `backtest_engine.py` 의 검사 네 줄과 상수 import 삭제. 테스트 5파일 112 passed. 주석에 적은 「음수 유지일은 유지일 1 처럼 돈다」를 수정 전 코드로 쟀다 — 돌파 행 3 에서 첫 매수 신호가 `hold_days=-1` 은 행 4, `0` 은 행 3, `1` 은 행 4, `2` 는 행 5
- 2026-10-11 08:11: Phase 2 — `portfolio_data.py` · `portfolio_engine.py` · `portfolio_planning.py` · `portfolio_types.py`. 포트폴리오 · 보완 전략 · 조합 · 배분 규칙 테스트 349 passed. 설정 306개(등록 5 · 단독 그리드 149 · 조합 그리드 152)가 `validate_portfolio_config` 를 모두 통과
- 2026-10-11 08:12: 문서 — `src/qbt/backtest/CLAUDE.md`(검증 자리 · 지운 함수 둘 · 신호 시세 읽기 · 슬롯 기본값 · 같은 종목 같은 id), `docs/AUDIT_REPORT.md`(5-2 · 9-6 · 9-10 · 5-5 · 2-11 · 7-12 · 3-2 · 17절 3번 · 9번 · 4-6 · 6-T · 14절). `black` 적용 — `tests/qbt/test_portfolio_methods.py` 1파일 재포맷
- 2026-10-11 08:14: 변형 확인(최종 코드의 사본 `step7/mut`, `PYTHONDONTWRITEBYTECODE=1`, 변형마다 원본 복원 확인) — **15종 모두 잡음**. 변형 전 153 passed
  - 생성자: 매수 버퍼 검증 삭제 → 6 failed / 매도 버퍼 검증 삭제 → 6 failed / 유지일 검증 삭제 → 3 failed / 매수 상한을 「1 이하」로 → `test_out_of_range_params_raise[1.0-…-buy_buffer_pct]` / 매도 상한을 「1 이하」로 → `[0.03-1.0-…-sell_buffer_pct]` / 매수 하한을 「초과」로 → `test_boundary_params_are_accepted[0.01-0.05-3]` 외 3 / 유지일 하한을 「초과」로 → 39 failed(유지일 0 을 쓰는 테스트 전부)
  - 설정 검증: 총 자본 검증 삭제 → `test_total_capital_must_be_positive` 3 / 「0 미만만」으로 → 같은 테스트의 0.0 · NaN / 슬롯 비중을 옛 검사(0 미만만)로 → `test_slot_weight_must_be_positive` 의 0.0 · NaN / `strategy_id` 검증 삭제 → `test_unknown_strategy_id_raises` / 다른 자산 id 검사 삭제 → `test_same_trade_path_with_different_asset_id_across_methods_raises` / 그 검사에서 매매법 수 조건 삭제 → `…_within_one_method_passes` · `test_same_path_different_ma_window_no_collision`
  - 엔진: 신호 시세 캐시 되살리기 → `test_slot_order_does_not_change_start_date_or_equity` / 슬롯 신호를 매매 시세에서 읽기 → `TestQQQTQQQSharedSignal` · `TestSignalAndTradeDataSeparation`
- 2026-10-11 08:22: 결과 파일 변화 0 확인(최종 코드의 사본 `step7/final` 에서 러너 여섯 실행, 모두 exit 0) — `storage/` 324개 파일 중 저장소와 다른 것은 `storage/results/meta.json` 하나이고, 실행 시각 · 소요 시간을 빼면 사본의 이력 항목이 모두 저장소에 같은 내용으로 있다. 소요: 단일 5초 · 포트폴리오 14초 · 단독 그리드 88초 · 조합 그리드 123초 · 고원 40초 · 워크포워드 137초(변형 확인과 함께 돌았다). 저장소의 `storage/` 변경 0
- 2026-10-11 08:23: `/code-review xhigh` 1회차 — 발견 10건. 죽거나 결과 수치를 바꾸는 지적은 없다(리뷰가 전체 테스트를 따로 돌려 908 passed)
  - 고친 버그 2(검사 공백 — 그 검사가 막는 결함이 무겁다)
    - ② 슬롯 순서 테스트가 「순서를 바꿔도 같다」만 보고 시작일 자체를 고정하지 않아, 이 계획서가 바꾸지 않기로 한 「겹치는 기간으로 자른 뒤 이동평균」을 지키는 테스트가 없다(리뷰 실측: 이동평균을 먼저 계산하게 바꿔도 908개 통과) → 시작일 단언 한 줄(T 의 첫 거래일부터 이동평균 기간을 채운 날)
    - ⑥ 다른 자산 id 검사의 「매매법 수」를 매매 데이터마다 세는지 가르는 테스트가 없다(설정 단위로 바꾸면 한 매매법만 그 데이터를 두 id 로 드는 정상 설정이 막힌다) → 통과 테스트 1개
    - 같은 모양 찾기(「같다」만 보고 값 자체를 고정하지 않는 새 테스트): 신호 공유 테스트의 「마지막 매도일이 같다」 하나 — 원래 있던 단언이고 이 계획서는 픽스처만 바꿨다. 그 계약(신호 출처)은 변형 M15 가 잡는다
  - 미조치 버그 4
    - ①(가벼움) 슬롯 파라미터가 장부를 만들 때에야 검증되어, 러너의 사전 시작일 계산은 통과하고 앞 실험의 결과를 덮어쓴 뒤 멈춘다 — 멈추는 쪽이고 덮어쓴 결과는 그 실험의 맞는 결과다. 계획서 비목표(시세를 읽기 전 검증은 하지 않는다)가 받아들인 모양이고 지금 설정 306개에서 0건(거르는 기준 2)
    - ③(무거운 모양 · 닿지 않음) 총 자본 `inf` 는 검증을 통과해 수익률 NaN 이 나온다 — 자본은 `DEFAULT_INITIAL_CAPITAL` 이나 숫자로 적는 값이라 `inf` 가 들어올 계기가 없다(거르는 기준 1)
    - ④(가벼움) 생성자 예외 문구가 설정 칸 이름이 아니라 생성자 인자 이름이고 어느 슬롯인지 싣지 않는다 — 안내 문구(거르는 기준 2). ① 과 함께 풀 수 있는 모양이라 Done 보고에 올린다
    - ⑦(무거운 모양 · 닿지 않음) 다른 자산 id 검사가 경로를 `Path` 값으로 견줘 같은 파일의 다른 표기를 놓친다 — 기존 정방향 검사와 같은 한계. 설정 306개의 서로 다른 시세 경로 35개가 모두 `common_constants` 의 경로 상수이고 같은 파일을 가리키는 다른 표기 쌍은 0 이다. 어긋나려면 경로 상수를 쓰지 않는 새 설정 코드가 있어야 한다(거르는 기준 1)
  - 반영한 그 외 3: ⑤ `load_and_prepare_data` docstring 에 전제조건(등록된 `strategy_id` — 설정 검증이 먼저 본다) ⑨ `AssetSlotConfig` docstring 의 「엔진이 ValueError 로 처리」와 지운 함수를 가리키던 테스트 클래스 이름 ⑩ 전략 생성 경로 목록이 주석 · 안내 문서 · 테스트 docstring 세 곳에 있던 것 — 목록을 빼고 「모든 경로가 이 생성자를 지난다」만 남겼다
  - 미조치 그 외 1: ⑧ `MIN_*` 상수 셋이 한 파일 전용이 됨 — 비목표, 점검 보고서 4-6 에 적어 11단계에서 옮긴다(거르는 기준 3). ⑤ 의 「래퍼를 엔진에 인라인」은 하지 않았다(정리)
- 2026-10-11 08:31: 1회차 수정 뒤 — 바뀐 테스트 5파일 172 passed. 변형 확인을 최종 코드의 사본에서 다시 돌려 **17종 모두 잡음**(기존 15 + 새 2: 이동평균을 겹치는 기간으로 자르기 전에 계산 → `test_slot_order_does_not_change_start_date_or_equity`, 다른 자산 id 검사의 매매법 수를 설정 단위로 → `test_two_asset_ids_on_trade_path_held_by_only_one_of_several_methods_pass`). 변형 전 · 복원 뒤 154 passed, 사본 src 가 저장소와 같음을 확인. `black` 변경 없음
- 2026-10-11 08:45: `/code-review xhigh` 2회차(상한) — 발견 9건. 죽거나 결과 수치를 바꾸는 지적은 없다(리뷰가 따로 돌린 품질 검증 passed=909, 설정 306개 검증 통과, 지운 캐시에 적중하던 슬롯 14개는 모두 `buy_and_hold` 라 이동평균과 무관). 수정 전 사본을 스크래치 `step7/r2_before/` 에 떴다
  - 고친 버그 1(검사 공백 — 새 자리): ① 지운 `test_ma_window_one_is_valid` 만 「이동평균 기간 1 은 받는다」를 지키고 있었다 — `add_single_moving_average` 의 `window < 1` 을 `<= 1` 로 바꿔도 909개 통과. 이 계획서 설계 결정 6 의 「`test_invalid_window` 가 같은 계약을 이미 고정」은 거부 쪽(0 · 음수)에만 맞았다 → `test_analysis.py` 에 `test_window_one_is_smallest_valid_window` 추가. 변형(`<= 1`) → 그 테스트 1 failed · 909 passed, 복원 확인. 점검 보고서 6-T 행의 서술도 고쳤다
  - 사용자 결정으로 고친 버그 1(가벼움 — 1회차 ① ④ 와 같은 뿌리): ② 슬롯 파라미터가 설정 검증을 지나 장부를 만들 때에야 멈춘다. 리뷰 재현: 등록 실험 Q-2-2XS 의 SSO 슬롯에 `hold_days=-1` · `sell_buffer_zone_pct=5.0` 을 넣어도 909개 통과, 러너는 앞 실험 결과를 저장한 뒤 멈추고 문구에 슬롯이 없다. 계획서 비목표였으므로 사용자에게 올렸고 **사용자 결정: 지금 넣음**(08:52) → `_validate_slots` 가 슬롯마다 전략을 한 번 만들어 보고 ValueError 면 `asset_id` 를 붙여 다시 던진다. 검증 규칙은 생성자 한 곳 그대로다. 테스트 1개(`test_out_of_range_slot_strategy_params_raise_before_loading` — 더미 경로라 시세를 읽기 전임을 함께 고정). 실측: 등록 실험의 SSO 슬롯에 매도 버퍼 5.0 을 넣으면 러너의 사전 단계 `compute_portfolio_effective_start_date` 가 「슬롯의 전략 파라미터가 올바르지 않습니다: asset_id=sso — 매도 버퍼존 비율(sell_buffer_pct)은 0.01 이상 1 미만이어야 합니다(0.05 = 5%): 5.0」으로 멈춘다. 설정 306개는 그대로 통과
  - 미조치 버그 5
    - ③(무거운 모양 · 닿지 않음) 하한을 부동소수 그대로 견줘 산술로 만든 0.01(`0.03 - 0.02` = 0.00999…)이 거부된다 — 그리드 · 고원 · 설정의 버퍼존 값은 모두 숫자 리터럴이고(산술로 만드는 코드 grep 0건), 닿으려면 목록을 산술식으로 만드는 새 코드가 있어야 한다. 닿아도 값이 찍힌 예외로 멈춘다(거르는 기준 1)
    - ④(무거운 모양 · 닿지 않음) `run_buffer_strategy` 가 이동평균 열이 이미 든 입력에서는 기간을 검증하지 않는다(`ma_0` 열 + `ma_window=0`) — 이동평균 열은 `add_single_moving_average` 로만 만들어지고 그 함수가 0 이하를 거부하므로 그런 열은 프로덕션 코드로 생기지 않는다(리뷰도 「닿지 않는다」로 판정, 거르는 기준 1)
    - ⑤(무거운 모양) 배분 규칙 자산의 신호 경로 · 매매 경로를 가르는 테스트가 없다(그 줄을 「둘 다 매매 경로」로 바꿔도 909개 통과). 지금 설정 · 테스트의 배분 규칙 자산은 모두 신호 = 매매 경로이고, 그 설정 칸은 점검 보고서 6-5 가 11단계에서 지울지 정한다 → 미룬 지적 파일과 두 벌을 만들지 않고 6-5 행에 덧붙였다
    - ⑥ 총 자본 `inf` · ⑦ 경로의 다른 표기 — 1회차 ③ · ⑦ 과 같다(거르는 기준 1)
  - 그 외 2: ⑧ `MIN_*` 상수의 자리 — 1회차 ⑧ 과 같다(거르는 기준 3, 점검 보고서 4-6) ⑨ 점검 보고서 19절 7단계 표시와 미룬 지적 항목 삭제가 남아 있다 — 마무리 작업이라 반영
- 2026-10-11 08:57: 2회차 수정 뒤 — 변형 확인 **18종 모두 잡음**(새 1: 설정 검증의 전략 미리 만들어 보기 삭제 → `test_out_of_range_slot_strategy_params_raise_before_loading`. 유지일 검증 삭제 변형도 이제 그 테스트까지 4 failed). 변형 전 · 복원 뒤 155 passed, 사본 src 가 저장소와 같음을 확인. 최종 코드의 사본(`step7/final2`)에서 포트폴리오 러너 · 단독 그리드 · 조합 그리드를 다시 돌려 `storage/` 324개 파일 중 `meta.json` 만 다름을 확인(2회차 수정이 건드린 운영 코드는 `portfolio_data.py` 뿐이다). 품질 검증 `validate_project.py` — Ruff · PyRight 통과, Pytest passed=911, failed=0, skipped=0. `storage/` 변경 0. 수정분 검증(서브에이전트)을 띄웠다
- 2026-10-11 09:05: 수정분 검증 결과 — 2회차 수정 6 hunk 모두 ① ② ③ 에 답, **무거운 발견 0**. 수정 전 · 후 사본에서 전체 테스트 909 passed · 911 passed, 설정 306개 검증 통과(수정 전 · 후 같음), 등록 5개 실험을 엔진 함수로 돌린 결과 표 해시와 그리드 워커 301개 실행의 요약 · 위반 · 판단 비중표가 수정 전 · 후 바이트 단위로 같다. 러너 사본을 격리 폴더에서 실행: 수정 전에는 앞 실험 결과 파일 7개가 쓰인 뒤 멈추고, 수정 후에는 결과 파일 0개인 채 사전 시작일 계산에서 `asset_id` 와 함께 멈춘다. 변형 13종(미리 만들어 보는 블록 삭제 · 문구에서 `asset_id` 나 원래 문구 삭제 · 첫 슬롯만 확인 · ValueError 삼킴 · 이동평균 기간 경계 등)을 모두 잡는다. 원래 예외 문구는 새 문구 안과 `__cause__` 에 남고, ValueError 가 아닌 예외는 가려지지 않는다
  - 발견 1(가벼움 · diff 밖 기존 코드): 배분 규칙 매매법 쪽에 같은 모양이 남았다 — 규칙이 요구하는 자산 id 와 다른 설정(HAA 에서 자산 하나 뺌)은 설정 검증과 사전 시작일 계산을 통과하고, 장부를 만들 때 `create_allocator` 가 ValueError 로 멈춘다(문구에 `method_id` 는 있다). 멈추는 쪽이고 지금 설정 306개에서 0건(거르는 기준 2). 슬롯 쪽 같은 모양을 사용자가 고치기로 했으므로 Done 보고에 올린다
  - 발견 2(가벼움): 슬롯의 `ma_window=0` 은 설정 검증을 통과하고 그 슬롯의 시세를 읽은 뒤 `window는 1 이상` 으로 멈춘다(러너에서는 결과를 덮어쓰기 전) — 비목표(이동평균 기간 검증의 자리는 그대로), 거르는 기준 2. 다만 2회차에 쓴 docstring 두 곳의 「전략 파라미터 범위」가 이 값까지 본다고 읽혀 문구만 고쳤다
  - 발견 3(가벼움): 매매법이 여럿이고 두 슬롯 매매법이 같은 `asset_id` 를 들면 문구가 어느 매매법인지 가르지 못한다 — `_validate_slots` 의 다른 문구와 같은 관용이고, 지금 슬롯 매매법끼리 겹치는 id 는 `gld`(둘 다 `buy_and_hold`)뿐이다(거르는 기준 2)
  - 발견 4(가벼움): 타입이 틀린 값(`hold_days=None` 등)은 TypeError 로 `asset_id` 없이 나간다 — 멈추는 쪽이고 타입 검사가 먼저 잡는다(거르는 기준 2)
  - 참고: 설정 검증이 `StrategySpec.create_strategy` 를 슬롯마다 부르게 되어 「부작용 없이 여러 번 불려도 된다」가 생성 함수의 계약이 됐는데 `StrategySpec` 설명에 없다 → docstring 한 줄 추가
- 2026-10-11 09:09: 수정분 검증 뒤 문구만 고쳤다 — `_validate_slots` docstring(생성자가 보는 범위는 버퍼존 비율 · 유지일수이고 이동평균 기간은 여기서 보지 않는다), `TestMethodConfigValidation` docstring 의 같은 구절, `StrategySpec.create_strategy` 설명의 계약 한 줄. 세 파일 모두 docstring 을 뺀 AST 가 고치기 전 사본(`step7/r3_before`)과 같다. `black` 변경 없음. 품질 검증 `validate_project.py` 최종 — Ruff · PyRight 통과, Pytest passed=911, failed=0, skipped=0. `storage/` 변경 0
- 2026-10-11 09:10: 미룬 지적 — 새로 옮긴 것 없음. 1회차 ① ④(2회차에 사용자 결정으로 고침) · ③ · ⑦(기준 1) · ⑧(기준 3, 점검 보고서 4-6), 2회차 ③ · ④(기준 1) · ⑤(점검 보고서 6-5 행에 덧붙임 — 같은 일을 다룰 단계가 있어 두 벌을 만들지 않는다), 수정분 검증의 가벼움 4(기준 2)는 거름. 이 계획서가 고친 `DEFERRED_FINDINGS.md` 항목(같은 매매 데이터 · 다른 자산 id)을 지웠다 — 남은 항목 4
- 2026-10-11 09:10: 근거 승격 — 검증을 전략 생성자 한 곳에 두는 이유와 설정 검증이 전략을 미리 만들어 보는 이유는 `buffer_zone.py` · `portfolio_data.py` 주석과 `src/qbt/backtest/CLAUDE.md` 도메인 규칙 1, 슬롯마다 신호 시세를 따로 읽는 이유와 「겹치는 기간으로 자른 뒤 이동평균」은 엔진 주석 · `src/qbt/backtest/CLAUDE.md` 설계 특징 · 시작일을 고정한 테스트, 슬롯 비중 0 을 막는 이유와 「여러 매매법이 함께 드는 매매 데이터는 자산 id 하나」는 `portfolio_data.py` 주석 · 오류 문구, 생성 함수의 계약은 `StrategySpec` 설명, 처리 사실과 남은 일(4-6 · 6-5)은 점검 보고서
- 2026-10-11 11:15: `/commit` — 대상은 unstaged + untracked(이 계획서) 전체(17파일, staged 없음). 모두 이 계획서 한 묶음이라 분리 제안 없음. 후보 5개를 옮기고 Done

---
