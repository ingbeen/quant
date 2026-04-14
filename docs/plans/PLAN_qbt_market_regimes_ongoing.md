# Implementation Plan: QBT MARKET_REGIMES 진행중 구간 자동 연장 (end: null)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-14 01:20
**마지막 업데이트**: 2026-04-14 01:20
**관련 범위**: qbt/backtest
**관련 문서**: [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: [src/qbt/backtest/types.py](../../src/qbt/backtest/types.py) `MarketRegimeDict.end` 타입을 `str | None` 으로 확장하여 "진행중" 구간을 표현할 수 있게 한다.
- [x] 목표 2: [src/qbt/backtest/analysis.py](../../src/qbt/backtest/analysis.py) `calculate_regime_summaries` 가 `end is None` 인 regime 에 대해 `equity_df` 의 마지막 거래일을 자동으로 종료일로 사용하도록 분기 추가.
- [x] 목표 3: [src/qbt/backtest/constants.py](../../src/qbt/backtest/constants.py) `MARKET_REGIMES` 의 마지막 bull 구간 `end` 를 `None` 으로 변경하여 "회복기 (진행중)" 으로 만든다.
- [x] 목표 4: `tests/qbt/test_analysis.py` 에 `end=None` 경로 회귀 테스트를 추가한다.
- [x] 목표 5: 사용자가 재실행해야 할 스크립트 / 대상 파일을 plan Notes 에 명시한다.

## 2) 비목표(Non-Goals)

- MARKET_REGIMES 의 regime_type 자동 분류 로직 추가는 범위 외 (수동 분류 유지).
- `app_single_backtest.py` / `app_portfolio_backtest.py` 등 대시보드 코드 수정은 범위 외 (summary.json 읽기만 함).
- `run_single_backtest.py` 의 스크립트 실행은 AI 가 수행하지 않음 (루트 CLAUDE.md "스크립트 실행 규칙"). 기존 `storage/results/backtest/buffer_zone_{tqqq,qqq}/summary.json` 의 `regime_summaries` 재생성은 사용자 담당.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **MARKET_REGIMES 공백**: [src/qbt/backtest/constants.py:95-97](../../src/qbt/backtest/constants.py#L95-L97) 의 마지막 구간은 `{"start": "2025-05-13", "end": "2026-02-17", "regime_type": "bull", "name": "회복기"}` 로 정의되어 있다. 오늘 (2026-04-14) 기준으로 2026-02-18 ~ 2026-04-14 구간이 **공백** 이며, regime 기반 성과 집계에서 최신 구간이 누락된다. 이 데이터는 "QQQ 기준 수동 분류" 이지만 매번 수동 업데이트를 해야 한다는 운영 부담이 있다.
- **"진행중" 표현 부재**: `MarketRegimeDict.end` 가 `str` 필수 타입이므로 "아직 진행중인 마지막 구간" 을 표현할 수 없다. `end=None` 을 허용하면 `calculate_regime_summaries` 가 자동으로 `equity_df` 마지막 거래일까지 슬라이스하여 자연스럽게 연장된다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — QBT 본체 수정 승인 필요, 상수/타입/문서 일관성, 출력 반올림 규칙, 테스트 원칙
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md) — 상수 관리, 구현 원칙
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) — `MARKET_REGIMES` / `MarketRegimeDict` / `calculate_regime_summaries` 정의
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then 패턴, 엣지 케이스 테스트

## 4) 완료 조건(Definition of Done)

- [x] `MarketRegimeDict.end` 가 `str | None` 으로 확장
- [x] `calculate_regime_summaries` 가 `end is None` 에 대해 `equity_df` 마지막 거래일을 사용하여 슬라이스
- [x] `MARKET_REGIMES` 마지막 구간의 `end` 가 `None` 으로 변경되어 "진행중" 의미를 갖는다
- [x] 신규/갱신 테스트 추가: `end=None` 경로 / 정상 경로 회귀 모두 통과
- [x] `poetry run python validate_project.py` 통과 (passed=921, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화
- [x] 사용자 재실행 대상 Notes 명시

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/types.py` — `MarketRegimeDict.end: str | None`
- `src/qbt/backtest/analysis.py` — `calculate_regime_summaries` end=None 분기
- `src/qbt/backtest/constants.py` — `MARKET_REGIMES` 마지막 구간 end=None
- `src/qbt/backtest/CLAUDE.md` — `MarketRegimeDict` 설명 갱신 (`end` 타입 변경, 진행중 구간 의미 추가)
- `tests/qbt/test_analysis.py` — `end=None` 경로 테스트 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- **영향 받는 summary.json**: `storage/results/backtest/buffer_zone_tqqq/summary.json`, `storage/results/backtest/buffer_zone_qqq/summary.json` 의 `regime_summaries` 항목. 이 파일들을 갱신하려면 사용자가 `run_single_backtest.py` 를 해당 전략에 대해 재실행해야 한다.
- **다른 전략**: `regime_summaries: []` 이므로 영향 없음 (QQQ 시그널 전략만 regime 분석 수행).
- **대시보드**: `app_single_backtest.py` 가 summary.json 읽기만 하므로 재실행 후 자동 반영.
- **live 패키지**: MARKET_REGIMES 미사용 → 영향 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — 정책 테스트 먼저 고정 (레드 허용)

**작업 내용**:

- [x] `tests/qbt/test_analysis.py` 에 `end=None` regime 을 포함한 fixture 로 `calculate_regime_summaries` 호출 → 마지막 거래일까지 슬라이스 되는지 검증하는 테스트 추가 (레드)
- [x] 기존 end=str 경로 테스트가 모두 그대로 통과해야 한다는 전제 유지

---

### Phase 1 — 구현 (그린 전환)

**작업 내용**:

- [x] `src/qbt/backtest/types.py` `MarketRegimeDict.end` 를 `str | None` 으로 수정, docstring 갱신
- [x] `src/qbt/backtest/analysis.py` `calculate_regime_summaries` 내부에서 regime 의 end 가 None 이면 `equity_df` 마지막 거래일 (ISO 문자열) 을 사용하도록 분기 추가
- [x] Phase 0 테스트 통과 확인

---

### Phase 2 — 상수 / 문서 갱신

**작업 내용**:

- [x] `src/qbt/backtest/constants.py` `MARKET_REGIMES` 마지막 구간의 `end` 를 `None` 으로 변경 (구간명은 "회복기" 유지, 의미는 "회복기 진행중")
- [x] `src/qbt/backtest/CLAUDE.md` `MarketRegimeDict` 설명에 `end: str | None` 과 "진행중 구간은 end=None, equity_df 마지막 거래일까지 자동 연장" 정책 반영

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `README.md` 변경 없음 확인
- [x] `poetry run black .` 실행
- [x] DoD / Phase 체크리스트 최종 업데이트
- [x] Notes 에 사용자 재실행 대상 (`buffer_zone_tqqq`, `buffer_zone_qqq`) 명시

**Validation**:

- [x] `poetry run python validate_project.py` (passed=921, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / MARKET_REGIMES 진행중 구간 자동 연장 (end=None)
2. 백테스트 / MarketRegimeDict.end None 허용 + 마지막 구간 연장 정책
3. 백테스트 / calculate_regime_summaries end=None 분기 + 상수 갱신
4. 백테스트 / 시장 구간 정의 진행중 표현 허용 및 문서 반영
5. 백테스트 / regime summaries 진행중 구간 처리 + 회귀 테스트

## 7) 리스크(Risks)

- **기존 summary.json 불일치**: `storage/results/backtest/buffer_zone_{tqqq,qqq}/summary.json` 의 `regime_summaries` 는 재실행 전까지 과거 포맷 유지. 사용자가 재실행해야 갱신됨. AI 는 실행하지 않음 (루트 CLAUDE.md 준수).
- **직렬화 호환**: `MarketRegimeDict` 는 Python 내부 TypedDict 이며 JSON 직렬화 시 `end` 가 `null` 로 저장된다. 기존 regime_summaries 는 `start_date` / `end_date` 필드만 포함하므로 스키마 충돌 없음.
- **PyRight strict**: `end: str | None` 변경 후 기존 코드가 `end` 를 문자열로 가정하는 곳이 있으면 타입 에러 발생 가능 → 변경 후 validate_project.py 로 전수 확인.

## 8) 메모(Notes)

- 본 plan 은 전수 분석 결과 파생 4 종 중 네 번째이자 마지막이다. 선행: [PLAN_live_drift_pct_ratio_storage.md](PLAN_live_drift_pct_ratio_storage.md).
- **사용자 재실행 필요 (plan 완료 후)**: `storage/results/backtest/buffer_zone_tqqq/summary.json` 과 `storage/results/backtest/buffer_zone_qqq/summary.json` 의 `regime_summaries` 를 갱신하려면 사용자가 `scripts/backtest/run_single_backtest.py` 를 해당 전략 2 건에 대해 재실행해야 한다. AI 는 scripts 를 실행하지 않는다.
- 사용자 승인 이력: 2026-04-14 사용자 대화에서 본 plan 의 QBT 본체 수정 범위 (types.py, analysis.py, constants.py, backtest/CLAUDE.md, test_analysis.py) 에 대해 명시적 승인 받음.

### 진행 로그 (KST)

- 2026-04-14 01:20: plan 작성 시작
- 2026-04-14 01:30: types.py end: str | None, analysis.py end=None 분기, constants.py 마지막 구간 end=None 구현
- 2026-04-14 01:35: tests/qbt/test_analysis.py end=None 경로 + 빈 equity_df 엣지 2 건 추가, backtest/CLAUDE.md 갱신
- 2026-04-14 01:40: validate_project.py 통과 (921/0/0), plan Done 처리
