# Implementation Plan: MARKET_REGIMES 진행중 구간 name 자동 "진행중" 표시

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

**작성일**: 2026-04-14 01:50
**마지막 업데이트**: 2026-04-14 01:50
**관련 범위**: qbt/backtest
**관련 문서**: [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: [src/qbt/backtest/analysis.py](../../src/qbt/backtest/analysis.py) `calculate_regime_summaries` 가 `regime["end"] is None` 인 "진행중 구간" 에 대해 결과 `RegimeSummaryDict.name` 을 **"진행중"** 으로 자동 치환하도록 한다.
- [x] 목표 2: 기존 `regime["end"]` 가 문자열인 경우 `name` 은 그대로 보존한다 (과거 구간은 원래 이름 유지).
- [x] 목표 3: 회귀 테스트 추가: `end=None` → `name == "진행중"`, `end=str` → `name` 원본 보존.
- [x] 목표 4: [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md) `MarketRegimeDict` 설명에 "진행중 구간의 출력 name 은 '진행중' 으로 자동 치환" 정책을 반영한다.

## 2) 비목표(Non-Goals)

- `constants.py` 의 `MARKET_REGIMES` 값 변경은 범위 외 (원본 구간명 "회복기" 유지).
- `regime_type` / `start_date` / `end_date` 등 다른 필드 변환은 범위 외.
- 대시보드 (`app_single_backtest.py`) 의 렌더링 로직 변경은 범위 외 (데이터 계층에서 처리).
- 앱 / RTDB / live 패키지 영향 없음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **이전 plan 의 후속 이슈**: [PLAN_qbt_market_regimes_ongoing.md](PLAN_qbt_market_regimes_ongoing.md) 에서 `MarketRegimeDict.end: str | None` 과 `end=None` 자동 연장을 도입했으나, 출력되는 `RegimeSummaryDict.name` 은 여전히 constants 의 원본 이름("회복기") 을 그대로 복사한다. 사용자 요구사항은 "마지막 주기(진행중 구간) 는 name 이 '진행중' 으로 표시되어야 한다" 이다.
- **설계 결정 근거**: constants 는 수동 분류한 과거 전환점 이름 ("회복기") 을 그대로 보존하고, 서버 계산 시점에 `end is None` 일 때만 출력 name 을 "진행중" 으로 치환한다. 이렇게 하면:
  - 나중에 전환점이 확정되어 `end` 가 날짜로 채워지면 자동으로 원본 이름 ("회복기") 으로 복원된다 → 수동 전환 불필요
  - `regime_type` 컬럼이 "bull" 로 별도 저장되어 문맥 손실 없음
  - constants 수정 없이 analysis 1 곳만 변경

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] `calculate_regime_summaries` 가 `end is None` regime 에 대해 `name` 을 "진행중" 으로 치환
- [x] `end=str` 경로는 기존 동작 유지 (원본 name 보존)
- [x] `tests/qbt/test_analysis.py` 에 두 경로 회귀 테스트 추가 (진행중 경로 / 정상 경로 name 보존)
- [x] `src/qbt/backtest/CLAUDE.md` `MarketRegimeDict` 설명에 name 치환 정책 반영
- [x] `poetry run python validate_project.py` 통과 (passed=923, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `README.md` 변경 없음
- [x] plan 체크박스 최신화
- [x] 사용자 재실행 대상 Notes 명시 (`buffer_zone_tqqq`, `buffer_zone_qqq`)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py` — `calculate_regime_summaries` 에서 name 치환 분기 추가
- `src/qbt/backtest/CLAUDE.md` — `MarketRegimeDict` 설명 갱신
- `tests/qbt/test_analysis.py` — 회귀 테스트 2 건 추가 (진행중 / 정상)
- `README.md`: 변경 없음

### 데이터/결과 영향

- 기존 `storage/results/backtest/buffer_zone_{tqqq,qqq}/summary.json` 의 `regime_summaries` 마지막 엔트리 `name` 이 "회복기" 로 저장되어 있음. 사용자가 `run_single_backtest.py` 를 재실행해야 "진행중" 으로 갱신된다.
- 다른 전략은 `regime_summaries: []` 이므로 영향 없음.

## 6) 단계별 계획(Phases)

### Phase 1 — 구현 + 테스트 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/analysis.py` `calculate_regime_summaries` 내부에서 `regime["end"] is None` 이면 `regime_summary["name"]` 을 `"진행중"` 으로 할당 (단, `end=str` 인 경우 원본 `regime["name"]` 그대로)
- [x] `tests/qbt/test_analysis.py` 에 `test_regime_summaries_end_none_name_is_ongoing` 추가 (end=None → name == "진행중")
- [x] `tests/qbt/test_analysis.py` 에 `test_regime_summaries_end_str_name_preserved` 추가 (end=str → 원본 name 보존)
- [x] 기존 `test_regime_summaries_end_none_uses_equity_last_date` 테스트는 name 추가 검증으로 업데이트 또는 별도 테스트 유지

---

### Phase 2 — 문서 갱신

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` `MarketRegimeDict` 설명 라인에 "진행중 구간 (end=None) 은 출력 name 이 '진행중' 으로 자동 치환된다 (constants 원본 이름은 보존)" 추가

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `README.md` 변경 없음 확인
- [x] `poetry run black .` 실행
- [x] DoD / Phase 체크리스트 최종 업데이트
- [x] Notes 에 사용자 재실행 대상 명시

**Validation**:

- [x] `poetry run python validate_project.py` (passed=923, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / regime 진행중 구간 name "진행중" 자동 치환
2. 백테스트 / calculate_regime_summaries end=None name 표시 정책 추가
3. 백테스트 / MarketRegimeDict 진행중 구간 표시 이름 자동화
4. 백테스트 / regime_summaries 진행중 구간 name 분기 + 테스트
5. 백테스트 / regime name 표시 정책 (end=None → "진행중")

## 7) 리스크(Risks)

- **summary.json 재생성 필요**: 기존 `buffer_zone_{tqqq,qqq}/summary.json` 은 사용자가 재실행해야 name 이 "진행중" 으로 갱신된다. AI 는 scripts 를 실행하지 않는다.
- **이름 충돌**: 누군가 "진행중" 이라는 이름의 실제 regime 을 constants 에 직접 추가할 경우 의미 중복 가능 — 가능성 낮으므로 경고 수준으로만 고려.

## 8) 메모(Notes)

- 본 plan 은 [PLAN_qbt_market_regimes_ongoing.md](PLAN_qbt_market_regimes_ongoing.md) 의 후속 개선이다. 선행 plan 에서 `end=None` 자동 연장을 도입했고, 본 plan 은 출력 name 표시 정책만 추가한다.
- **사용자 재실행 필요 (plan 완료 후)**: Plan 4 와 동일하게 `scripts/backtest/run_single_backtest.py` 를 `buffer_zone_tqqq`, `buffer_zone_qqq` 2 건에 대해 재실행해야 `regime_summaries` 의 마지막 엔트리 `name` 이 "진행중" 으로 갱신된다.

### 진행 로그 (KST)

- 2026-04-14 01:50: plan 작성 시작
- 2026-04-14 02:00: analysis.py `calculate_regime_summaries` 에 `display_name = "진행중" if end is None else regime["name"]` 분기 추가
- 2026-04-14 02:05: test_analysis.py 에 진행중 name 치환 / 정상 name 보존 회귀 테스트 2 건 추가
- 2026-04-14 02:10: backtest/CLAUDE.md `MarketRegimeDict` 설명 갱신 (진행중 name 치환 정책)
- 2026-04-14 02:15: validate_project.py 통과 (923/0/0), plan Done 처리
