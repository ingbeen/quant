# Implementation Plan: chart_data 재구조화 — meta + recent + archive/{YYYY} + 마커 날짜화

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

**작성일**: 2026-04-14 10:50
**마지막 업데이트**: 2026-04-14 11:30
**관련 범위**: live (src/live/), tests/live/, docs/
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [루트 CLAUDE.md](../../CLAUDE.md)

위 문서들에 기재된 규칙을 모두 숙지하고 준수한다.

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

- [x] RTDB `/latest/chart_data/{asset_id}` 를 **단일 payload 전체 덮어쓰기** 에서 **meta + recent + archive/{YYYY}** 3종 구조로 재구성한다.
- [x] 차트 마커(`buy_signals` / `sell_signals` / `user_buys` / `user_sells`) 의 표현을 **`dates` 배열 인덱스 → ISO 8601 날짜 문자열** 로 전환하여 분할 독립성을 확보한다.
- [x] recent = "최근 6개월", archive 는 **연도 단위** 고정, recent 와 archive 는 **구간 중복 허용** (앱이 Map 으로 dedupe).
- [x] daily runner 는 매 실행 시 `recent` + `archive/{현재_연도}` 만 갱신하고, 과거 연도 archive 는 건드리지 않는다 (backfill CLI 는 Plan 3 에서 담당).
- [x] 설계서 `DESIGN_QBT_LIVE_FINAL.md` §8.2.5 를 새 스키마로 재작성한다.

## 2) 비목표(Non-Goals)

- 이전 연도 archive 일괄 생성(backfill) CLI 작성 — Plan 3 에서 처리.
- 스플릿/무상증자 수동 대응 문서화 — Plan 3 에서 처리.
- `docs/CLAUDE.md` / `src/live/CLAUDE.md` 에 대한 수정 — Plan 3 에서 일괄 처리.
- `build_chart_series` 의 MA/밴드 계산 수학 변경 — 기존 `add_single_moving_average` 재사용 유지.
- 앱 코드 변경 (앱 미개발).
- Git 정본 `history/*.jsonl` 포맷 변경.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

현재 [src/live/chart_data.py:58](../../src/live/chart_data.py#L58) 의 `build_chart_series` 는 CSV 전체 (~13 년) 를 자산별 단일 `ChartSeries` 로 만들고, [src/live/rtdb_gateway.py:277](../../src/live/rtdb_gateway.py#L277) 의 `write_chart_data` 가 `/latest/chart_data/{asset_id}` 전체를 매일 `set()` 으로 덮어쓴다.

**구조적 비효율**:

- 과거 12 년치 데이터는 실제로는 거의 변하지 않는데 매일 풀 재생성 / 풀 업로드된다.
- 앱이 "최초 진입 시 최근 몇 달 → 줌아웃 시 과거 구간 점진 로드 → 전체 보기" 사용 패턴을 가질 예정인데, 현재 구조는 이 패턴에 맞지 않는다 (항상 전체 풀로드).
- 마커를 `dates` 배열 인덱스로 저장하므로 **데이터 분할 시 인덱스가 무너진다**. 분할하려면 마커를 위치 독립적 표현으로 바꿔야 한다.

**선택 근거** (이전 설계 논의에서 확정):

- recent 크기: **6 개월**
- archive 단위: **연도** (자산 4 × 13년 = 52 키 수준, 호출 수·크기 균형)
- recent 와 archive 경계: **중복 허용** (서버 단순성 + 앱 Map dedupe 로 자동 해결)
- 스플릿/무상증자 시 archive 전체 재생성은 Plan 3 에서 수동 CLI 로 대응.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준, 데이터 불변성, 명시적 검증
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 규칙, 순수 계산/I/O 분리, QBT 본체 수정 금지
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then, 부동소수점 비교, 외부 네트워크 격리

## 4) 완료 조건(Definition of Done)

- [x] `ChartSeries` 가 "slice" (dates 배열 범위와 그에 대응하는 값들 + ISO 날짜 마커) 개념을 지원하도록 재정의된다. `ChartMeta` 타입이 신규 추가된다.
- [x] `build_chart_meta(state_dir)`, `build_chart_recent(state_dir, months)`, `build_chart_archive_year(state_dir, year)` 3개 빌더가 `chart_data.py` 에 존재한다. 기존 `build_chart_series` 는 제거된다.
- [x] `rtdb_gateway.write_chart_meta`, `write_chart_recent`, `write_chart_archive_year` 가 존재하며, 기존 `write_chart_data` 는 제거된다.
- [x] daily runner 의 호출 경로 (`_publish_to_rtdb`) 가 `meta + recent + archive/{current_year}` 를 순차 쓰기한다.
- [x] 마커 4종이 ISO 날짜 문자열 배열로 저장됨이 단위 테스트로 고정된다.
- [x] recent 가 정확히 지정된 개월 수만큼 자르고, archive 가 지정 연도의 데이터만 포함함이 단위 테스트로 고정된다.
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 설계서 `DESIGN_QBT_LIVE_FINAL.md` §8.2.5 재작성.
- [x] `README.md`: 변경 없음 (사용자 가시 명령 / 워크플로우 변경 없음).
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/models.py` — `ChartSeries` 필드 정의 수정 (마커 `list[int]` → `list[str]`), `ChartMeta` dataclass 신설
- `src/live/constants.py` — `CHART_RECENT_MONTHS = 6` 신설
- `src/live/chart_data.py` — `build_chart_series` 제거, `build_chart_meta` / `build_chart_recent` / `build_chart_archive_year` 신설, 공통 내부 헬퍼 추출
- `src/live/rtdb_gateway.py` — `write_chart_data` 제거, `write_chart_meta` / `write_chart_recent` / `write_chart_archive_year` 신설
- `src/live/cli.py` — `_publish_to_rtdb` 의 차트 쓰기 플로우 교체 (3 경로 순차 호출)
- `tests/live/test_chart_data.py` — 기존 테스트 전면 재작성
- `tests/live/test_rtdb_gateway.py` — 기존 `TestWriteChartData` 전면 재작성, 3 종 write 함수 테스트 추가
- `tests/live/test_cli.py` — `_publish_to_rtdb` 관련 통합 테스트 갱신
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §8.2.5 재작성, §8.2 상단 경로 목록의 chart_data 라인 갱신
- `README.md`: **변경 없음**

### 데이터/결과 영향

- RTDB `/latest/chart_data/{asset_id}` 하위 구조가 전면 변경된다 (단일 blob → meta / recent / archive/{YYYY}).
- 마커 타입이 정수 인덱스 배열에서 ISO 날짜 문자열 배열로 바뀐다.
- 앱 미개발이므로 외부 계약 파괴 리스크 없음.
- 과거 연도 archive 는 Plan 3 의 backfill CLI 로 생성되기 전까지는 **존재하지 않는 상태** 로 둔다. daily runner 는 올해 archive 와 recent 만 관리.

## 6) 단계별 계획(Phases)

### Phase 0 — 스키마 / 정책을 테스트로 먼저 고정 (레드)

> 이 Phase 에서는 새 스키마의 불변조건을 테스트로 먼저 작성한다. 구현은 아직 없으므로 레드 상태가 정상.

**작업 내용**:

- [x] `src/live/constants.py` 에 `CHART_RECENT_MONTHS: Final[int] = 6` 추가.
- [x] `tests/live/test_chart_data.py` 를 새 계약으로 재작성:
  - `build_chart_meta` 는 자산별 `{first_date, last_date, ma_window, recent_months, archive_years}` 를 돌려준다.
  - `build_chart_recent` 는 `CHART_RECENT_MONTHS` 개월 범위로 자른 slice 를 돌려준다. dates 길이와 값 배열 길이가 일치해야 한다. 마커는 해당 범위 안에 있는 날짜만 ISO 문자열로 포함한다.
  - `build_chart_archive_year(year)` 는 해당 연도의 거래일만 포함한다. 연도를 벗어난 날짜는 포함하지 않는다. 마커도 연도 내로 한정된다.
  - 마커 4종은 모두 `list[str]` (ISO 날짜).
  - recent 와 archive/{같은_연도} 는 구간이 **겹쳐도 무방** 하다 (중복 허용 정책 테스트).
- [x] `tests/live/test_rtdb_gateway.py` 의 `TestWriteChartData` 를 전면 재작성:
  - `write_chart_meta` 는 `/latest/chart_data/{asset_id}/meta` 에 쓴다.
  - `write_chart_recent` 는 `/latest/chart_data/{asset_id}/recent` 에 쓴다.
  - `write_chart_archive_year(year=...)` 는 `/latest/chart_data/{asset_id}/archive/{YYYY}` 에 쓴다.
  - 3 함수 모두 자산별로 순회해 각 경로에 `set()` 을 호출한다.
- [x] 이 Phase 종료 시점에서는 `build_chart_series` / `write_chart_data` 가 아직 존재하여 기존 import 가 깨지지 않도록 유지한다. 새 함수는 아직 없으므로 새 테스트가 레드.

---

### Phase 1 — chart_data 모델 + 빌더 재구성 (그린 복귀)

**작업 내용**:

- [x] `src/live/models.py` 수정:
  - `ChartSeries` 의 마커 4 필드를 `list[int]` → `list[str]` 로 교체.
  - `ChartMeta` dataclass 신설: `first_date: str`, `last_date: str`, `ma_window: int`, `recent_months: int`, `archive_years: list[int]`.
- [x] `src/live/chart_data.py` 전면 재작성:
  - 공통 내부 헬퍼: 자산 슬롯 순회 + CSV 로드 + MA/밴드 계산 + NaN → None 변환. 날짜 범위(`start`, `end`) 필터링을 지원.
  - `build_chart_meta(state_dir)`: 자산별 `ChartMeta` 생성. 전체 CSV 1 회만 훑어 first/last 날짜와 archive 연도 목록을 계산.
  - `build_chart_recent(state_dir, user_trades, signal_history, months)`: 자산별 `ChartSeries` (최근 `months` 개월 slice). 마커는 해당 범위 내 날짜만 ISO 문자열로.
  - `build_chart_archive_year(state_dir, user_trades, signal_history, year)`: 자산별 `ChartSeries` (해당 연도 slice). 마커도 연도 내.
  - 기존 `build_chart_series` 제거.
- [x] 기존 `chart_data.py` 의 `_ticker_for_chart`, `_to_optional_float_list` 는 공통 헬퍼에서 재사용 가능하면 유지.
- [x] Phase 0 의 `test_chart_data.py` 가 그린으로 전환됨을 확인.

---

### Phase 2 — rtdb_gateway write 함수 3분할 (그린 유지)

**작업 내용**:

- [x] `src/live/rtdb_gateway.py`:
  - `write_chart_data` 삭제.
  - `write_chart_meta(app, meta: dict[str, ChartMeta]) -> None` 추가.
  - `write_chart_recent(app, recent: dict[str, ChartSeries]) -> None` 추가.
  - `write_chart_archive_year(app, year: int, year_map: dict[str, ChartSeries]) -> None` 추가.
  - `__all__` 갱신.
- [x] Phase 0 의 `test_rtdb_gateway.py::TestWriteChartData` (재작성본) 이 그린이 됨을 확인.

---

### Phase 3 — CLI 호출 플로우 전환 (그린 유지)

**작업 내용**:

- [x] `src/live/cli.py::_publish_to_rtdb` 수정:
  - 기존 `build_chart_series` + `write_chart_data` 호출 제거.
  - 신규: `build_chart_meta` + `write_chart_meta` + `build_chart_recent` + `write_chart_recent` + `build_chart_archive_year(current_year)` + `write_chart_archive_year` 순차 호출.
  - `current_year = execution_date.year`.
  - `history.load_user_trades` / `history.load_signal_history` 는 recent / archive 양쪽에 동일한 값을 전달.
- [x] `tests/live/test_cli.py::TestCmdRunDailySuccess::test_publish_to_rtdb_invokes_prune_history_summary` 와 유사 스타일로 `_publish_to_rtdb_writes_chart_meta_recent_archive` 같은 이름의 통합 테스트 추가 (3 경로가 모두 호출되는지 스파이로 검증).

---

### Phase 4 — 설계서 업데이트 및 최종 검증 (마지막 Phase)

**작업 내용**

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` §8.2.5 재작성:
  - `/latest/chart_data/{asset_id}/meta` 섹션 추가 (payload 예시 + 필드 표).
  - `/latest/chart_data/{asset_id}/recent` 섹션 추가 (payload 예시 + 필드 표 + 마커는 ISO 날짜).
  - `/latest/chart_data/{asset_id}/archive/{YYYY}` 섹션 추가 (payload 예시 + 필드 표).
  - recent 와 archive 경계 중복 허용 정책 명시.
  - 앱 로딩 플로우 요약 (초기 recent → 줌아웃 시 archive 병합 → 전체 보기).
- [x] §8.2 상단 경로 목록에서 `/latest/chart_data/{asset_id}` 라인을 새 구조 반영으로 갱신.
- [x] §5 "차트: TradingView Lightweight Charts" 섹션도 마커 타입 변경에 맞춰 갱신 (list[int] → list[str]).
- [x] `README.md`: 변경 없음 확인.
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=911, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / chart_data 재구조화 (meta + recent + archive/{YYYY}) + 마커 날짜화
2. live / chart_data 분할 저장 + 앱 점진 로딩 지원 구조 도입
3. live / RTDB chart_data 3 분할 + 마커 인덱스 → ISO 날짜 전환
4. live / 차트 RTDB 스키마 재설계 (meta/recent/archive) + 설계서 반영
5. live / chart_data 빌더/게이트웨이 분할 + 마커 표현 독립화

## 7) 리스크(Risks)

- **리스크 1**: 기존 `ChartSeries` 를 사용하는 코드가 사라지고 새 구조로 교체되는 과정에서 누락 호출이 남을 수 있다.
  - **완화**: `build_chart_series` / `write_chart_data` 를 명시적으로 삭제하여 컴파일(타입체크) 단계에서 누락을 잡는다.
- **리스크 2**: 테스트용 CSV 가 MA window 보다 짧은 경우 워밍업 처리가 기존과 달라질 수 있다.
  - **완화**: Phase 0 에서 MA 워밍업 경계 케이스 테스트를 명시적으로 추가하고, 기존 `slot.ma_window - 1` 로직을 공통 헬퍼에 유지.
- **리스크 3**: recent 와 archive 경계에서 같은 날짜가 두 곳에 존재하여 앱이 중복 렌더링할 가능성.
  - **완화**: 설계서에서 "앱은 Map 으로 dedupe" 를 명시하는 것으로 해결 (앱 구현은 본 plan 범위 밖).
- **리스크 4**: 날짜 파싱 / timezone 처리 실수로 "6 개월" 경계가 애매해질 수 있다.
  - **완화**: CSV 의 날짜는 이미 naive `datetime.date` 이므로 `last_date - relativedelta(months=CHART_RECENT_MONTHS)` 방식으로 단순 계산. 또는 `last_date.replace(month=...)` 로 근사 계산 후 테스트로 명시. Phase 0 에서 방식을 확정.

## 8) 메모(Notes)

- recent / archive 경계 계산 시 `dateutil.relativedelta.relativedelta(months=6)` 를 쓸지, 단순 `timedelta(days=30*6)` 근사를 쓸지는 Phase 1 구현 시 결정. 정확한 "달력 기반 6 개월" 을 원하면 `relativedelta`. 의존성이 이미 들어있는지 확인 후 선택.
- `archive_years` 는 CSV 의 first_date / last_date 사이의 연도 범위를 단순 생성. 해당 연도에 거래일이 한 건이라도 있으면 포함.
- Phase 3 의 통합 테스트는 `_publish_to_rtdb` 직접 호출 + rtdb_gateway 함수 스파이 스타일 (Plan 1 의 prune 통합 테스트와 동일 패턴).
- 본 plan 은 스킵을 허용하지 않는다. 모든 테스트는 Phase 0 / Phase 1~3 로 분해되어 항상 그린 상태로 수렴한다.

### 진행 로그 (KST)

- 2026-04-14 10:50: Draft 작성
- 2026-04-14 11:00: Phase 0 완료 (CHART_RECENT_MONTHS 상수 추가, test_chart_data.py 전면 재작성 with 3 빌더 테스트, TestWriteChartData 교체 with 3 write 함수 테스트)
- 2026-04-14 11:10: Phase 1 완료 (models.py ChartMeta 추가 + ChartSeries 마커 list[str] 전환, chart_data.py 전면 재작성 with 공통 헬퍼 + 3 빌더, 14 tests green)
- 2026-04-14 11:20: Phase 2 완료 (rtdb_gateway write_chart_meta / write_chart_recent / write_chart_archive_year 구현, 44 tests green)
- 2026-04-14 11:25: Phase 3 완료 (_publish_to_rtdb 전환 + test_publish_to_rtdb_writes_chart_meta_recent_archive 통합 테스트 추가, 49 tests green)
- 2026-04-14 11:30: Phase 4 완료 (설계서 §5 / §8.2 경로 목록 / §8.2.5 재작성, black 적용, validate_project.py passed=911/failed=0/skipped=0)

---
