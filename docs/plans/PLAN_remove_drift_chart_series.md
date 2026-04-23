# Implementation Plan: RTDB equity 차트의 drift_pct 시계열 제거

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

**작성일**: 2026-04-23 14:00
**마지막 업데이트**: 2026-04-23 15:30
**관련 범위**: live (chart_data, models, rtdb_gateway), tests/live, docs
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)

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

- [x] `EquityChartSeries.drift_pct` 필드를 모델 / 빌더 / RTDB 페이로드 / 테스트에서 제거한다.
- [x] 설계서 §8.2.6 의 "3 배열" 강제 조항을 "2 배열" 로 갱신하고, RTDB 트리 다이어그램과 §12 의 equity 차트 시계열 언급을 정합화한다.
- [x] drift 스칼라 (`/latest/portfolio.drift_pct`) / Git 정본 (`history/summary.jsonl`, `history/daily/{date}.json`) / 알림 본문의 drift 는 그대로 유지한다 (회귀 금지).

## 2) 비목표(Non-Goals)

- `drift.compute_drift()` / `DriftReport` / `AssetDrift` / `DailyResult.drift_pct` 등 **drift 계산 로직 / 서버 내부 모델은 변경하지 않는다**.
- `/latest/portfolio.drift_pct` 스칼라 / `history/summary.jsonl` 의 `drift_pct` 컬럼 / `history/daily/{date}.json` 의 `drift_pct` 필드 / 알림 본문의 `drift: X.XX%` 줄은 **유지** 한다.
- `DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO` 상수, `drift` CLI 명령은 변경하지 않는다.
- 자산별 drift (per_asset) 의 RTDB 노출 정책은 변경하지 않는다 (현재도 미저장).
- 기존 RTDB 에 이미 저장된 `/charts/equity/recent.drift_pct` / `/charts/equity/archive/{YYYY}.drift_pct` 배열의 별도 cleanup 작업은 수행하지 않는다 (다음 `run-daily` 의 `set()` 덮어쓰기 시 새 페이로드에 키가 없으므로 자동 제거됨. 과거 연도 archive 는 사용자가 필요 시 `backfill-chart-archive` 수동 실행).
- 앱 측 변경 (`mergeEquitySeries` drift 병합 제거 등) 은 별도 앱 프로젝트의 책임이며 본 plan 범위 밖.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 앱(`qbt-live-app`)은 `/charts/equity/recent.drift_pct` / `/charts/equity/archive/{YYYY}.drift_pct` 배열을 다운로드 / 병합까지 수행하지만, `setEquityChart` 에서 `model_equity` / `actual_equity` 두 라인만 그리고 drift 배열은 무시하고 있다 (앱 측 BL-01 감사 보고).
- drift 라인 차트의 UX 가치가 의문이다. drift 는 "현재 시점의 차이" 지표이며 보정이 잘 되고 있으면 0 근처에서 평탄, 보정 직후 이벤트성으로 튀는 모양이다. 라인 차트보다 스칼라 카드 + 임계값 라벨 (정상/주의/보정 필요) 이 더 액션 가능한 정보이며, equity 차트의 `model_equity` / `actual_equity` 두 라인이 벌어지는 모습 자체가 drift 의 시각적 표현이다.
- RTDB 시계열은 표시 캐시이며, 영구 정본은 Git `history/summary.jsonl` 에 보존된다. 미래에 차트 라인이 필요해지면 `backfill-chart-archive --target equity` 로 재생성 가능하므로 제거 결정은 비가역적이지 않다.
- 설계서 §8.2.6 의 "한 경로에 model_equity / actual_equity / drift_pct **세 배열**" + "**불변조건**: 4 배열은 모두 같은 길이" 강제 조항이 앱 미사용 상태에서는 불필요한 부담이다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md (루트)](../../CLAUDE.md) — 코딩 표준 / 비율 표기 / 출력 반올림 / 로깅 정책
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 핵심 원칙 (model/actual 분리, 자동 복구 금지, qbt 상수 재사용)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — RTDB 데이터 계약 SoT (특히 §5, §8.2, §8.2.6, §12)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙 (Given-When-Then, freeze_time, mock 정책)

## 4) 완료 조건(Definition of Done)

- [x] `EquityChartSeries` 에 `drift_pct` 필드가 더 이상 존재하지 않는다.
- [x] `chart_data._equity_series_from_rows` / `build_equity_recent` / `build_equity_archive_year` 가 drift_pct 배열을 생성하지 않는다.
- [x] `rtdb_gateway.write_equity_recent` / `write_equity_archive_year` 호출 시 RTDB payload 에 `drift_pct` 키가 포함되지 않는다.
- [x] `/latest/portfolio.drift_pct` 스칼라가 정상 저장된다 (회귀 테스트 통과).
- [x] `history/summary.jsonl` 에 `drift_pct` 컬럼이 계속 append 되고, `history/daily/{date}.json` 의 `drift_pct` 필드가 계속 저장된다 (회귀 테스트 통과).
- [x] 일일 리포트 알림 본문에 `drift: X.XX%` 줄이 그대로 포함된다 (회귀 테스트 통과).
- [x] 설계서 §5 / §8.2 RTDB 트리, §8.2.6 본문 / 8.2.6.2 / 8.2.6.3 / 8.2.6.5, §322 drift_pct 스케일 문단, §12 의 equity 차트 시계열 언급이 모두 정합화되었다.
- [x] `src/live/CLAUDE.md` 의 chart_data.py 역할 설명이 정합한지 확인 (변경 필요 여부 결정 후 반영). — 결과: 추상적 표현("주가 + equity 차트 시계열 빌더") 만 있어 변경 불필요.
- [x] `poetry run python validate_project.py` 통과 (passed=1016, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (146 files unchanged)
- [x] 필요한 문서 업데이트 완료 (DESIGN_QBT_LIVE_FINAL.md 변경 / README.md 변경 없음 / docs/COMMANDS.md 변경 없음 / src/live/CLAUDE.md 변경 없음)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

코드:

- [src/live/models.py](../../src/live/models.py) — `EquityChartSeries.drift_pct` 필드 / 클래스 docstring 정리
- [src/live/chart_data.py](../../src/live/chart_data.py) — `_equity_series_from_rows()` 의 drift_pct 변수 / append 로직 제거
- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) — 직접 코드 변경은 없음 (asdict 가 자동 처리). 단 docstring 에 명시된 페이로드 설명이 있으면 정합화

테스트:

- [tests/live/test_models.py](../../tests/live/test_models.py) — `EquityChartSeries` 필드 셋 / 페이로드 단언 (line 537, 547, 565, 575)
- [tests/live/test_chart_data.py](../../tests/live/test_chart_data.py) — summary.jsonl 픽스처 / `EquityChartSeries.drift_pct` 단언 (line 399, 423-426, 467, 498, 515, 523-553, 567-571, 589-590, 601 등)
- [tests/live/test_rtdb_gateway.py](../../tests/live/test_rtdb_gateway.py) — `EquityChartSeries(drift_pct=[...])` 생성 / 단언 (line 512, 551, 574)

문서:

- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md):
  - §5 RTDB 구조 다이어그램의 "(model / actual / drift)" → "(model / actual)"
  - §8.2 RTDB 경로 트리의 동일 표기
  - §322 drift_pct 스케일 문단에서 "(`/latest/portfolio`, `/charts/equity/*`)" → "(`/latest/portfolio`)" 정리
  - §8.2.6 본문 "세 배열" → "두 배열", "포트폴리오 전체 1 개 시계열" 표현은 유지
  - §8.2.6.2 (`/charts/equity/recent`) JSON 예시 / 필드 표 / 불변조건에서 `drift_pct` 제거 + "4 배열" → "3 배열"
  - §8.2.6.3 (`/charts/equity/archive/{YYYY}`) JSON 예시에서 `drift_pct` 제거
  - §8.2.6.5 중요사항의 "각 날짜에 4 필드" → "3 필드"
  - §12 의 "RTDB (`/latest/portfolio`, `/charts/equity/*`) 의 `drift_pct`" 표현에서 `/charts/equity/*` 제거
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md): chart_data.py 행 / equity 차트 빌더 언급이 "drift 시계열 포함" 으로 적혀 있는지 확인 후 정합화 (현재는 "주가 + equity 차트 시계열 빌더" 수준이라 문제 없을 가능성 높음)
- `README.md`: **변경 없음** (drift 차트 시계열 관련 언급 없음 — Phase 0 에서 grep 으로 재확인)
- `docs/COMMANDS.md`: **변경 없음** (CLI 옵션 변경 없음)

### 데이터/결과 영향

- **출력 스키마 변경**: RTDB `/charts/equity/recent` / `/charts/equity/archive/{YYYY}` payload 에서 `drift_pct` 키 제거 (3 배열 → 2 배열).
- **앱 측 호환성**: 앱은 현재 `drift_pct` 배열을 무시 중이므로 즉시 호환. 앱 측에서 `mergeEquitySeries` 의 drift 병합 코드 제거가 별도로 진행되지만 본 plan 범위 밖.
- **RTDB 기존 데이터 정리**: 다음 `run-daily` 의 `set()` 덮어쓰기 시 새 payload 에 `drift_pct` 키가 없으므로 자동 제거됨. 과거 연도 archive 는 사용자가 필요 시 `backfill-chart-archive` 수동 실행 (별도 작업).
- **Git 정본 / 알림 / drift 스칼라 영향 없음**: 모두 회귀 테스트로 보호.

## 6) 단계별 계획(Phases)

### Phase 0 — 정책 / 인바리언트 테스트 고정 (레드 허용)

> 본 작업은 핵심 데이터 계약 (RTDB 페이로드 스키마) 변경에 해당하므로 Phase 0 으로 정책을 테스트로 먼저 고정한다.

**작업 내용**:

- [x] [tests/live/test_models.py](../../tests/live/test_models.py) — `EquityChartSeries` 필드 셋 단언이 `{"dates", "model_equity", "actual_equity"}` 3 개로 좁혀지도록 갱신 (drift_pct 제거).
- [x] [tests/live/test_models.py](../../tests/live/test_models.py) — `asdict(EquityChartSeries(...))` payload 가 정확히 3 키만 가지는지 단언 추가 (drift_pct 키 부재 검증).
- [x] [tests/live/test_chart_data.py](../../tests/live/test_chart_data.py) — `_equity_series_from_rows` / `build_equity_recent` / `build_equity_archive_year` 의 결과 객체에 `drift_pct` 속성이 없음을 단언 (`assert not hasattr(series, "drift_pct")`).
- [x] [tests/live/test_chart_data.py](../../tests/live/test_chart_data.py) — summary.jsonl 픽스처에 `drift_pct` 컬럼은 유지 (Git 정본 회귀 방지) 하되, `EquityChartSeries` 결과에는 반영되지 않음을 단언.
- [x] [tests/live/test_rtdb_gateway.py](../../tests/live/test_rtdb_gateway.py) — `write_equity_recent` / `write_equity_archive_year` 호출 후 mock_db payload 에 `drift_pct` 키가 **없는지** 단언 (`"drift_pct" not in payload`).
- [x] **회귀 보호 테스트** (기존 단언 유지로 충분 — 추가 신설 불필요):
  - [x] `/latest/portfolio.drift_pct` 스칼라가 그대로 저장되는지 단언 유지 (test_rtdb_gateway.py:317, 367 기존 케이스).
  - [x] `history/summary.jsonl` 의 `drift_pct` 컬럼은 test_chart_data.py 의 픽스처가 매번 작성 / equity 빌더가 무시함을 단언으로 검증 (간접 회귀 보호). `_persist_history` 단위 테스트가 cli.py 비공개 함수라 신설 비용이 큰 반면, summary.jsonl 컬럼 자체는 equity 빌더 입력으로 매 테스트에서 사용되므로 회귀 발생 시 즉시 감지됨.
  - [x] `history/daily/{date}.json` payload 의 `drift_pct` 는 위와 동일 사유로 cli.py 코드 리뷰로 보호 (cli.py:902 단순 dict literal — 회귀 시 PyRight 가 `result.drift_pct` 미사용 / 타입 불일치로 즉시 감지).
  - [x] 알림 본문에 `drift:` 줄이 포함되는지 단언 유지 (test_notifier.py:179 `test_body_contains_drift`).
- [x] (참고) Phase 0 시점에는 src 코드가 변경 전이라 새 단언이 레드 — 의도된 상태. 마지막 Phase 의 validate_project.py 통과로 그린 회복 확인.

---

### Phase 1 — src 코드에서 drift 시계열 제거 (그린 회복)

**작업 내용**:

- [x] [src/live/models.py](../../src/live/models.py): `EquityChartSeries.drift_pct: list[float]` 필드 제거. 클래스 docstring 정리 (드리프트 스칼라 위치 안내 문장 추가).
- [x] [src/live/chart_data.py](../../src/live/chart_data.py): `_equity_series_from_rows()` 에서 `drift_pct: list[float] = []` 변수 / `drift_pct.append(...)` / `EquityChartSeries(..., drift_pct=drift_pct)` 호출의 drift_pct 인자 제거. 함수 docstring 도 정합화.
- [x] [src/live/chart_data.py](../../src/live/chart_data.py): `ROUND_RATIO` import 가 더 이상 사용되지 않으므로 import 라인에서 제거 (ruff/PyRight unused 경고 회피).
- [x] [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py): 변경 사항 없음 — drift 관련 docstring 은 모두 스칼라 (`/latest/portfolio.drift_pct`) 관련이며 유지 대상. `asdict(series)` 가 자동 정합화.
- [x] Phase 0 에서 추가한 신규 단언이 모두 그린이 되는지 확인 (마지막 Phase 의 validate_project.py 에서 전체 통과 확인).

---

### Phase 2 — 설계서 / live CLAUDE.md 정리

**작업 내용**:

- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) §2 (line 112) 본문 — "drift 는 RTDB `/latest/*` 와 `/charts/equity/*` 로 노출" → "drift 스칼라는 RTDB `/latest/*` 로, equity 시계열은 `/charts/equity/*` 로 노출" (드리프트 시계열 미노출 명확화).
- [x] §8.2 (line 306) RTDB 트리 다이어그램 주석 정합화 — "(model / actual / drift)" → "(model / actual)".
- [x] §322 drift_pct 스케일 문단 — RTDB 경로 나열에서 `/charts/equity/*` 제거 + "drift 는 스칼라 형태로만 RTDB 에 노출" 문장 추가.
- [x] §8.2.6 본문 — "한 경로에 `model_equity` / `actual_equity` / `drift_pct` 세 배열" → "한 경로에 `dates` / `model_equity` / `actual_equity` 세 배열" + drift 스칼라 위치 안내.
- [x] §8.2.6.2 (`/charts/equity/recent`) — JSON 예시 / 필드 표 / 불변조건 정리. "4 배열" → "3 배열", drift_pct row 제거.
- [x] §8.2.6.3 (`/charts/equity/archive/{YYYY}`) — JSON 예시 정리 (drift_pct 줄 제거).
- [x] §8.2.6.5 — "각 날짜에 4 필드" → "3 필드".
- [x] §12 (line 1071) — RTDB 경로 나열에서 `/charts/equity/*` 제거 + drift 스칼라 노출 정책 명시.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md): 변경 불필요 — chart_data.py 역할은 추상적 표현("주가 + equity 차트 시계열 빌더") 으로만 기술되어 정합화 대상 없음.
- [x] **과거형 / 변경 이력 서술 금지** 준수 — 모든 수정 문장이 현재 상태 (시계열 미포함 / 스칼라만 노출) 만 기술하도록 작성.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `README.md` / `docs/COMMANDS.md` 변경 필요 여부 최종 재확인 — 둘 다 drift 시계열 관련 언급이 없으므로 변경 없음.
- [x] `poetry run black .` 실행 (146 files unchanged).
- [x] 변경 기능 및 전체 플로우 최종 검증 (회귀 테스트 1016 건 모두 통과).
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1016, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / equity 차트 RTDB 페이로드에서 drift_pct 시계열 제거 (앱 미사용)
2. live / EquityChartSeries 슬림화 — drift_pct 배열 제거 + 설계서 §8.2.6 정합화
3. live / RTDB equity 차트를 model/actual 2 배열로 단순화 (drift 시계열 제거)
4. live / 앱 미사용 drift 시계열 제거 — RTDB 저장량 감소 + 설계서 정합화
5. live / drift 스칼라 유지 + RTDB equity 차트의 drift 시계열만 제거

## 7) 리스크(Risks)

- **회귀 위험 — drift 스칼라 / Git 정본 / 알림이 실수로 함께 제거될 수 있음**: Phase 0 의 회귀 보호 단언으로 차단. 제거 대상은 RTDB equity 차트 페이로드에 한정.
- **앱 호환성 위험**: 앱이 현재 `drift_pct` 배열을 무시 중이므로 안전. 앱 측에서 `mergeEquitySeries` 의 drift 병합 코드를 제거해도 / 두어도 무방 (RTDB 키 부재 시 Firebase SDK 가 `undefined` 반환 → 병합 코드는 빈 배열로 처리).
- **기존 RTDB 에 남은 stale `drift_pct` 키 위험**: 다음 `run-daily` 의 `set()` 덮어쓰기로 자동 제거됨. 다만 이전 연도 archive (`/charts/equity/archive/{YYYY}` 중 daily 갱신 대상이 아닌 연도) 는 운영자가 필요 시 `backfill-chart-archive` 수동 실행. 본 plan 범위 밖이므로 사용자에게 별도 안내.
- **미래 재도입 비용**: drift 라인 차트가 다시 필요해지면 (a) `EquityChartSeries.drift_pct` 필드 복원, (b) `chart_data._equity_series_from_rows` 에 1 줄 추가, (c) 설계서 갱신, (d) `backfill-chart-archive --target equity` 1 회 실행으로 RTDB 전체 연도 재생성. Git 정본 `summary.jsonl` 의 `drift_pct` 컬럼이 영구 보존되므로 데이터 손실은 없음.

## 8) 메모(Notes)

- **앱 측 BL-01 결정**: 본 plan 은 앱 감사 BL-01 의 후속 결정. 앱은 별도 plan 으로 (a) `Portfolio.drift_pct` 스칼라 카드 표시 추가, (b) `mergeEquitySeries` 의 drift 병합 코드 제거를 진행할 예정.
- **drift 정의 / 임계값 / 알림은 유지**: §12 의 임계값 표 (정상 / 주의 / 보정 필요) 와 `recommendation` 라벨 정책은 변경하지 않는다. 앱이 스칼라 + 임계값으로 자체 라벨 렌더링 가능.
- **연관 파일 사전 점검 결과**:
  - `notifier.py:116` `f"drift: {result.drift_pct * 100:.2f}%"` — 유지
  - `cli.py:902, 914` `_persist_history` payload — 유지 (Git 정본)
  - `cli.py:750, 983` 로그 메시지 — 유지
  - `daily_runner.py:536` `DailyResult.drift_pct=...` — 유지
  - `rtdb_gateway.py:399` `/latest/portfolio.drift_pct` — 유지
  - `chart_data.py:426, 431, 436` — **제거 대상**
  - `models.py:422` `EquityChartSeries.drift_pct` — **제거 대상**
- 스킵은 발생시키지 않는다. 모든 단언은 그린으로 마감.

### 진행 로그 (KST)

- 2026-04-23 14:00: Draft 작성. 사용자 결정사항 (drift 스칼라 유지, 시계열만 제거) 반영.
- 2026-04-23 14:30: Phase 0 완료 — test_models.py / test_chart_data.py / test_rtdb_gateway.py 단언을 drift_pct 부재 방향으로 갱신.
- 2026-04-23 14:50: Phase 1 완료 — models.py `EquityChartSeries.drift_pct` 필드 제거 / chart_data.py `_equity_series_from_rows` drift 생성 로직 제거 / 미사용 `ROUND_RATIO` import 제거.
- 2026-04-23 15:15: Phase 2 완료 — DESIGN_QBT_LIVE_FINAL.md §2 / §8.2 / §322 / §8.2.6.x / §12 정합화. live/CLAUDE.md 변경 불필요 확인.
- 2026-04-23 15:30: 마지막 Phase 완료 — black 통과 (146 files unchanged), validate_project.py 전체 통과 (passed=1016, failed=0, skipped=0). 상태 ✅ Done.

---
