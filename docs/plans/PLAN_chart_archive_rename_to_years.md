# Implementation Plan: 차트 RTDB 경로 archive → years rename + recent 슬라이스 폐지

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-04-29 22:30
**마지막 업데이트**: 2026-04-29 23:15
**관련 범위**: live (chart_data, rtdb_gateway, models, cli, constants)
**관련 문서**: [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/COMMANDS.md](../COMMANDS.md)

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

- [x] 목표 1: 차트 RTDB 경로의 중간 키 `archive` 를 `years` 로 rename 한다 (`/charts/prices/{asset_id}/archive/{YYYY}` → `/charts/prices/{asset_id}/years/{YYYY}`, `/charts/equity/archive/{YYYY}` → `/charts/equity/years/{YYYY}`).
- [x] 목표 2: 차트 meta 페이로드 필드 `archive_years` 를 `years` 로 rename 한다 (자산별 / equity 양쪽).
- [x] 목표 3: `recent` 슬라이스 (`/charts/*/recent`, `recent_months` 필드, `build_*_recent` / `write_*_recent` 함수 군) 를 폐지한다 (앱은 이미 새 경로 전용으로 배포되어 데드 코드 상태).
- [x] 목표 4: 코드 식별자/CLI 명령어/문서/주석을 새 명명으로 정합화한다 (`build_chart_archive_year` → `build_chart_year_slice`, CLI `backfill-chart-archive` → `backfill-chart-years` 등).

## 2) 비목표(Non-Goals)

- `docs/DESIGN_QBT_LIVE_FINAL.md` 갱신은 본 plan 의 비목표. 사용자가 앱 측 갱신본을 서버 프로젝트로 직접 복사한다 (프롬프트 §5 명시).
- RTDB 의 기존 `/charts/*/archive/*`, `/charts/*/recent` 노드를 삭제하기 위한 별도 1회용 cleanup CLI 추가는 비목표. 사용자가 코드 배포 후 `python -m live reset --capital N` 1회 실행으로 정리한다 (본 plan §8 Notes 참고).
- yfinance OHLC 조회용 `fetch_recent_ohlc` / `DEFAULT_RECENT_FETCH_DAYS` 는 차트의 `recent` 슬라이스와 무관한 별개 개념이므로 변경 비대상.
- 앱 측 plan / 앱 코드 갱신은 본 plan 의 비목표 (앱은 이미 `/charts/*/years/{YYYY}` 전용으로 배포 완료).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 직전 작업으로 차트 RTDB 시계열 경로는 `archive/{YYYY}` 에 단일화되었으나, "archive" 라는 명칭은 본래 "recent 와 대비되는 보관 데이터" 의미였다. 현재 연도(daily runner 가 매일 갱신 중) 까지 archive 에 들어가 명칭이 의미와 어긋난다.
- 동시에 `recent` 슬라이스는 앱 측 배포 완료 시점부터 데드 코드가 되었다 (앱은 `/charts/*/years/{YYYY}` 만 읽음). 서버는 여전히 `build_*_recent`, `write_*_recent` 호출과 `/charts/*/recent` 갱신 로직을 유지하여 RTDB 에 무용한 노드를 매일 재기록 중이다.
- 새 합류 개발자 / 향후 본인이 코드를 다시 볼 때의 혼란을 막기 위해, 의미 일치성과 코드 일관성을 동시에 회복한다.
- 개발 단계라 RTDB 데이터 / state repo 의 history / live_state 폐기가 가능하므로 (프롬프트 §4 명시), 마이그레이션 안정화 기간 / 양립 코드 경로는 두지 않는다. `reset --capital N` 1회 실행으로 마무리한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 [CLAUDE.md](../../CLAUDE.md): 코딩 표준 / 로깅 정책 / 출력 데이터 반올림 규칙 / 문서 내구성 원칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md): live 도메인 핵심 원칙 (장애 시 자동 복구 금지, model/actual 분리, 순수 계산 분리)
- [tests/CLAUDE.md](../../tests/CLAUDE.md): 테스트 작성 규칙 (Given-When-Then, mock 정책)
- [docs/CLAUDE.md](../CLAUDE.md): plan 운영 규칙

## 4) 완료 조건(Definition of Done)

> Done은 “서술”이 아니라 “체크리스트 상태”로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] RTDB 경로가 `/charts/prices/{asset_id}/years/{YYYY}` / `/charts/equity/years/{YYYY}` 로만 쓰인다 (코드/테스트의 어느 곳에도 `/charts/*/archive/*`, `/charts/*/recent` 가 남지 않음)
- [x] meta 페이로드 필드가 `years: list[int]` 로 갱신되며, `archive_years` / `recent_months` 필드는 모델/페이로드에서 제거됨
- [x] `recent` 슬라이스 빌더(`build_chart_recent`, `build_equity_recent`) 와 RTDB writer (`write_chart_recent`, `write_equity_recent`) 가 코드에서 완전히 제거됨
- [x] CLI 명령어가 `backfill-chart-years` 로 노출되며, `backfill-chart-archive` 는 더 이상 등록되지 않음 (alias 도 두지 않음)
- [x] 함수 식별자가 `build_chart_year_slice` / `build_equity_year_slice` / `write_chart_year_slice` / `write_equity_year_slice` 로 변경됨
- [x] 영향받는 docstring / 주석 / `src/live/CLAUDE.md` / `docs/COMMANDS.md` 가 새 명명/경로/필드명으로 정합화됨
- [x] 회귀/신규 테스트 갱신 (기존 `archive` / `recent` 어서션을 모두 새 명명/경로로 교체, 폐지된 함수의 테스트 제거)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트
  - [x] `README.md`: 변경 없음 (archive/recent/backfill-chart 관련 언급 없음을 grep 으로 확인)
  - [x] `docs/COMMANDS.md`: 변경 있음 (workflow 3 의 `backfill-chart-archive` 관련 라인을 `backfill-chart-years` 로 갱신)
  - [x] `src/live/CLAUDE.md`: 변경 있음 (모듈 표 / 핵심 원칙 §1 의 archive·recent 언급을 새 명명으로 갱신)
  - [x] `docs/DESIGN_QBT_LIVE_FINAL.md`: 본 plan 비대상 (사용자가 앱 측 갱신본 직접 복사)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일

**구현 코드 (src/live/)**:

- `src/live/chart_data.py`
  - 모듈 docstring 갱신 (`meta + recent + archive/{YYYY} 3 분할` → `meta + years/{YYYY} 2 분할`)
  - `__all__` 갱신: `build_chart_recent`, `build_equity_recent` 제거 / `build_chart_archive_year`→`build_chart_year_slice`, `build_equity_archive_year`→`build_equity_year_slice` rename
  - `build_chart_recent`, `build_equity_recent` 함수 본체 제거
  - `build_chart_archive_year` → `build_chart_year_slice` (이름만 변경, 동작 동일)
  - `build_equity_archive_year` → `build_equity_year_slice` (이름만 변경, 동작 동일)
  - `build_chart_meta` / `build_equity_chart_meta` 가 반환하는 메타에서 `recent_months` 제거, `archive_years` → `years` 로 키 rename
  - `CHART_RECENT_MONTHS` import 제거
- `src/live/rtdb_gateway.py`
  - 모듈 docstring 의 RTDB 경로 목록 갱신 (`/recent`, `/archive/{YYYY}` → `/years/{YYYY}`)
  - `__all__` 갱신: `write_chart_recent`, `write_equity_recent` 제거 / `write_chart_archive_year`→`write_chart_year_slice`, `write_equity_archive_year`→`write_equity_year_slice` rename
  - `write_chart_recent`, `write_equity_recent` 함수 본체 제거
  - `write_chart_archive_year` → `write_chart_year_slice` (경로 `archive` → `years`)
  - `write_equity_archive_year` → `write_equity_year_slice` (경로 `archive` → `years`)
- `src/live/models.py`
  - `ChartMeta`: `recent_months` 필드 제거, `archive_years: list[int]` → `years: list[int]` rename
  - `EquityChartMeta`: `recent_months` 필드 제거, `archive_years: list[int]` → `years: list[int]` rename
  - `ChartSeries`, `EquityChartSeries` docstring 의 RTDB 경로 표현 갱신
  - 섹션 헤더 주석 (`# ChartMeta / ChartSeries — 차트 시계열 (meta + recent + archive/{YYYY})`) 갱신
- `src/live/cli.py`
  - chart_data import 정리 (recent 함수 제거, archive_year → year_slice rename)
  - rtdb_gateway 사용처에서 `write_chart_recent` / `write_equity_recent` 호출 제거
  - `_cmd_run_daily` 의 차트 갱신 블록에서 recent 갱신 로직 제거, `build_chart_archive_year` → `build_chart_year_slice`, `write_chart_archive_year` → `write_chart_year_slice` rename
  - `_cmd_reset` 의 차트 재생성 블록에서 recent 갱신 로직 제거, archive→years rename, 메타의 `archive_years` → `years` 참조 갱신, 변수명 `archive_years` (set) / `archive_map` 도 `years` (set) / `year_map` 으로 정리
  - `_cmd_backfill_chart_archive` → `_cmd_backfill_chart_years` 로 함수명 rename, docstring/help 텍스트 갱신, `meta.archive_years` → `meta.years` 참조 갱신, 내부 변수명 `archive_map` → `year_map` 정리
  - argparse subcommand `backfill-chart-archive` → `backfill-chart-years` 로 등록명 변경 (commit_subcommand 문자열 포함)
  - `_NOTIFY_FAILURE_COMMANDS` 등 allow-list / 알림 정책 docstring 에서 `backfill-chart-archive` 언급을 `backfill-chart-years` 로 갱신
- `src/live/constants.py`
  - `CHART_RECENT_MONTHS: Final[int] = 6` 상수 제거
  - 위 상수 위 주석 블록(line 158-160) 제거 또는 갱신
  - line 160 의 `archive/{YYYY}` 어휘 정리 (해당 상수 제거 시 자동 해소)

**테스트 코드 (tests/live/)**:

- `tests/live/test_models.py`
  - `ChartMeta` / `EquityChartMeta` 어서션에서 `recent_months` 제거, `archive_years` → `years` 로 갱신, 직렬화 결과 dict 의 키도 동일 변경
- `tests/live/test_chart_data.py`
  - `build_chart_recent`, `build_equity_recent` 호출/검증 테스트 케이스 제거
  - `build_chart_archive_year`, `build_equity_archive_year` import / 호출 → 새 명명으로 갱신
  - `CHART_RECENT_MONTHS` import / 사용 모두 제거 (관련 어서션 케이스 정비)
  - meta 의 `archive_years` / `recent_months` 어서션을 `years` 단일 필드 어서션으로 정리
- `tests/live/test_rtdb_gateway.py`
  - `write_chart_recent`, `write_equity_recent` import / 테스트 케이스 제거
  - `write_chart_archive_year`, `write_equity_archive_year` import → 새 명명으로 갱신
  - 경로 어서션 `/charts/prices/sso/archive/2026` 등 → `/charts/prices/sso/years/2026` 로 갱신
  - meta 어서션의 `archive_years` / `recent_months` → `years` 단일 키로 정리
- `tests/live/test_cli.py`
  - `_cmd_reset` / `_cmd_run_daily` / `_cmd_backfill_chart_*` 관련 어서션 갱신 (recent 호출 제거, archive→years 명명 반영, CLI 커맨드 이름 갱신)
- `tests/live/test_alert_coverage.py`
  - allow-list 검증 테스트가 있다면 `backfill-chart-archive` → `backfill-chart-years` 로 갱신
- `tests/live/test_state.py`
  - "archive" 또는 "recent" 단어가 본 작업과 무관한 컨텍스트(`pd.DataFrame.reset_index` 등)인지 grep 으로 확인하고, 차트 관련이라면 갱신
- `tests/live/test_data_fetcher.py`
  - `fetch_recent_ohlc` 는 yfinance 의 "최근 N일 OHLC" 의미로 본 작업과 무관 — 변경 비대상

**문서**:

- `docs/COMMANDS.md`
  - line 150, 154, 156-158 의 `backfill-chart-archive` / archive 어휘를 `backfill-chart-years` / years 로 갱신
- `src/live/CLAUDE.md`
  - 폴더 구조 표의 `chart_data.py` 행 ("(meta + recent + archive/{YYYY})") 갱신
  - 모듈 표의 `chart_data.py` / `cli.py` 행 갱신
  - 핵심 원칙 §1 (장애 시 자동 복구 금지) 의 `backfill-chart-archive` 언급 → `backfill-chart-years`
  - 스플릿 / 무상증자 수동 대응 절차의 5번 (`backfill-chart-archive`) 갱신
- `README.md`: 변경 없음 (관련 언급 없음 — grep 으로 확인됨)
- `docs/DESIGN_QBT_LIVE_FINAL.md`: 본 plan 비대상 (사용자가 앱 측 갱신본 직접 복사)

### 데이터/결과 영향

- **RTDB 페이로드 스키마 변경**:
  - `/charts/prices/{asset_id}/meta`: `recent_months` 제거, `archive_years: list[int]` → `years: list[int]`
  - `/charts/equity/meta`: 동일
  - `/charts/prices/{asset_id}/years/{YYYY}` 노드 추가 (기존 `archive/{YYYY}` 와 동일 페이로드 구조)
  - `/charts/equity/years/{YYYY}` 노드 추가
- **RTDB 기존 노드 정리 (사용자 1회 작업)**:
  - 코드 배포 후 사용자가 `python -m live reset --capital <원하는금액>` 1회 실행
  - reset 의 7번 단계가 `/charts` 통째 삭제하므로 `/charts/*/archive/*`, `/charts/*/recent` 가 한 번에 정리됨
  - reset 8번 단계에서 새 경로(`/charts/*/years/{YYYY}`) 로 재생성됨
- **state repo 영향 (reset 부수효과)**:
  - `live_state.json` 새 초기값으로 덮어쓰기 (보유 자산 / shared_cash 초기화)
  - `applied_*_ids.json` 3개 삭제
  - `history/` 디렉토리 통째 삭제 (영구 히스토리 손실)
  - CSV 전체 재다운로드
  - git 원격 리포의 과거 커밋 히스토리는 보존됨 (force-push 아님)
  - 프롬프트 §4 "개발 단계라 데이터 보존 불필요" 정책에 부합

## 6) 단계별 계획(Phases)

### Phase 1 — 모델 / RTDB 게이트웨이 / 차트 빌더 (recent 폐지 + archive→years rename)

**작업 내용**:

- [x] `src/live/models.py`: `ChartMeta` / `EquityChartMeta` 의 `recent_months` 제거, `archive_years` → `years` rename, `ChartSeries` / `EquityChartSeries` docstring 갱신, 섹션 헤더 주석 갱신
- [x] `src/live/rtdb_gateway.py`: 모듈 docstring 의 RTDB 경로 목록 갱신, `__all__` 갱신, `write_chart_recent` / `write_equity_recent` 제거, `write_chart_archive_year` → `write_chart_year_slice` (경로 `archive` → `years`), `write_equity_archive_year` → `write_equity_year_slice` (경로 `archive` → `years`)
- [x] `src/live/chart_data.py`: 모듈 docstring 갱신, `__all__` 갱신, `build_chart_recent` / `build_equity_recent` 함수 제거, `build_chart_archive_year` → `build_chart_year_slice`, `build_equity_archive_year` → `build_equity_year_slice`, `build_chart_meta` / `build_equity_chart_meta` 가 반환하는 메타에서 `recent_months` 제거 / `archive_years` → `years` 로 키 rename, `CHART_RECENT_MONTHS` import 제거
- [x] `src/live/constants.py`: `CHART_RECENT_MONTHS` 상수 및 위 주석 블록 제거
- [x] 위 변경에 영향받는 import / 의존 모듈을 컴파일 단위로 확인하여 미해결 참조 없음을 확인 (cli.py 갱신은 Phase 2 에서 수행하지만, 이 단계에서 chart_data / rtdb_gateway 자체는 단독으로 import 가능해야 함)

**Validation**:

- [x] `poetry run python -c "from live import chart_data, rtdb_gateway, models, constants"` 으로 import 성공 (이름 변경/제거 누락 시 즉시 ImportError 로 노출)

---

### Phase 2 — CLI 갱신 (run-daily / reset / backfill rename)

**작업 내용**:

- [x] `src/live/cli.py` import 갱신: `build_chart_recent`, `build_equity_recent`, `write_chart_recent`, `write_equity_recent` 제거 / 새 명명 import 로 교체
- [x] `_cmd_run_daily` 의 차트 갱신 블록 (line 311 부근): recent 갱신 라인 2개 제거, `build_chart_archive_year` → `build_chart_year_slice`, `write_chart_archive_year` → `write_chart_year_slice`, equity 측도 동일
- [x] `_cmd_reset` 의 차트 재생성 블록 (line 457-475): recent 갱신 라인 2개 제거, `archive_years` (set) → `years` (set) 변수명 정리, `meta.archive_years` → `meta.years` 참조 갱신, `build_chart_archive_year` / `write_chart_archive_year` rename, `archive_map` → `year_map` 변수명 정리, docstring 의 8번 단계 설명 갱신
- [x] `_cmd_backfill_chart_archive` → `_cmd_backfill_chart_years` 함수 rename, docstring 갱신 (`archive` → `years`, recent 언급 제거), 내부 `meta.archive_years` → `meta.years`, `archive_map` → `year_map` 정리
- [x] argparse subcommand 등록 (`p_backfill = sub.add_parser("backfill-chart-archive", ...)`) 의 이름과 help 메시지를 `backfill-chart-years` 로 갱신
- [x] `ephemeral_state_repo(commit_subcommand="backfill-chart-archive")` 의 commit_subcommand 문자열을 `"backfill-chart-years"` 로 갱신
- [x] 모듈 docstring (line 8 부근의 명령어 목록) 및 `_NOTIFY_FAILURE_COMMANDS` 주변 docstring 의 `backfill-chart-archive` 언급을 `backfill-chart-years` 로 갱신
- [x] CLI 동작 수동 확인: `poetry run python -m live --help` 로 `backfill-chart-years` 가 노출되고 `backfill-chart-archive` 는 등록되지 않음을 확인

**Validation**:

- [x] `poetry run python -m live --help` 출력에서 `backfill-chart-years` 노출 + `backfill-chart-archive` 미등록 확인

---

### Phase 3 — 테스트 갱신

**작업 내용**:

- [x] `tests/live/test_models.py`: `archive_years` → `years` 갱신, `recent_months` 어서션 제거, 직렬화 결과 dict 의 키 변경 반영
- [x] `tests/live/test_chart_data.py`: `build_chart_recent` / `build_equity_recent` 테스트 케이스 제거, `build_chart_archive_year` / `build_equity_archive_year` → 새 명명, `CHART_RECENT_MONTHS` 사용 제거, meta 어서션 `archive_years` / `recent_months` → `years` 단일 키로 정리
- [x] `tests/live/test_rtdb_gateway.py`: `write_chart_recent` / `write_equity_recent` 테스트 케이스 제거, `write_chart_archive_year` / `write_equity_archive_year` → 새 명명, 경로 어서션 `/archive/` → `/years/` 갱신, meta 어서션 정리
- [x] `tests/live/test_cli.py`: reset / run-daily / backfill 관련 어서션을 새 명명·경로로 갱신, recent 호출 어서션 제거
- [x] `tests/live/test_alert_coverage.py`: `backfill-chart-archive` 언급을 `backfill-chart-years` 로 갱신 (allow-list 검증 등)
- [x] `tests/live/test_state.py`: archive/recent 단어의 컨텍스트 확인 후 차트 관련이면 갱신, `pd.DataFrame.reset_index` 등 무관 사용은 그대로

**Validation**:

- [x] `poetry run pytest tests/live/ -x` 통과 (491 passed, 0 failed, 0 skipped — 마지막 Phase 에서 validate_project.py 로 통합 재검증)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `docs/COMMANDS.md`: workflow 3 의 `backfill-chart-archive` 라인 (line 150, 154, 156-158) 을 `backfill-chart-years` 로 갱신, "차트 archive 재생성" 등 문구를 "차트 years 재생성" 으로 정리
- [x] `src/live/CLAUDE.md`: 폴더 구조 표의 `chart_data.py` 행 ("meta + recent + archive/{YYYY}") 갱신, 모듈 표의 `chart_data.py` / `cli.py` 행 갱신, 핵심 원칙 §1 의 `backfill-chart-archive` 언급 갱신, 스플릿/무상증자 수동 대응 절차 5번 갱신
- [x] README.md 는 grep 결과 archive/recent/backfill-chart 관련 언급 없음 — 변경 없음으로 최종 확인 (DoD 체크박스에 명시 완료)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1010, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / 차트 RTDB 경로 archive→years rename + recent 슬라이스 폐지
2. live / 차트 시계열 경로/모델/CLI 를 years 명명으로 통일 (recent 폐지 동반)
3. live / chart_data RTDB 스키마 갱신 — archive/recent 폐지 후 years 단일화
4. live / 차트 archive→years rename, recent 데드 코드 제거
5. live / 차트 시계열 인터페이스 정리 — years 슬라이스 단일화 + 명명 정합화

## 7) 리스크(Risks)

- **리스크 1**: cli.py 의 변수명/심볼 rename 누락으로 NameError 발생 가능 — Phase 2 끝에서 `python -m live --help` 1회로 import 단계 검증, Phase 3 에서 pytest 로 동작 검증, 마지막 Phase 에서 validate_project.py 로 최종 통합 검증.
- **리스크 2**: 사용자가 코드 배포 후 `reset` 을 실행하지 않으면 RTDB 의 기존 `/charts/*/archive/*` 와 `/charts/*/recent` 노드가 그대로 남아 RTDB 가 비대해짐 — 앱은 새 경로만 읽으므로 기능적 영향은 없으나, 본 plan §8 Notes 에 reset 절차를 명시하여 누락을 방지.
- **리스크 3**: state repo 의 `live_state.json` / `history/` / `applied_*_ids.json` 이 reset 으로 사라지는 손실 — 프롬프트 §4 "개발 단계라 데이터 보존 불필요" 정책에 부합. 운영 단계 진입 후에는 동일 마이그레이션 패턴을 사용해선 안 됨 (별도 cleanup CLI 가 필요).
- **리스크 4**: 앱 측이 새 경로 전용으로 배포되었다는 전제가 깨질 경우 (예: 일부 사용자 기기가 구버전 앱을 유지) — 본 plan 의 책임 범위 밖. 사용자 확인된 전제로 진행.
- **리스크 5**: 테스트가 archive/recent 어휘를 코멘트/문자열로 다수 포함하여 grep 누락 가능성 — Phase 3 에서 `tests/live/` 전체에 대해 archive/recent 잔존 grep 을 마지막에 한 번 더 수행.

## 8) 메모(Notes)

### 사용자 1회 작업 (코드 배포 후)

코드 배포 / merge 완료 후 사용자가 다음을 1회 실행:

```
poetry run python -m live reset --capital <원하는금액>
```

이 1회 실행으로 다음이 처리됨:
- RTDB `/charts` 전체 삭제 → 기존 `/charts/*/archive/*` 및 `/charts/*/recent` 노드 정리
- 새 경로 `/charts/*/years/{YYYY}` 로 차트 재생성
- state repo (`live_state.json` / `history/` / `applied_*_ids.json`) 도 함께 초기화됨 (수용 가능)

이후 daily runner 가 새 경로로 정상 갱신되는지 확인:
- `/charts/prices/{asset_id}/years/{현재_연도}` 갱신 여부
- `/charts/equity/years/{현재_연도}` 갱신 여부
- `/charts/prices/{asset_id}/meta.years` 가 `list[int]` 로 채워지는지
- 기존 `/charts/*/archive/*`, `/charts/*/recent` 노드가 RTDB 에 남아있지 않은지
- 앱 차트 화면이 정상 표시되는지 (4개 자산 + equity)

### 명명 컨벤션 결정 (질문4 i 채택)

- `build_chart_year_slice` / `write_chart_year_slice` (단어 "slice" 추가)
- 의미: RTDB 의 `years/` 컨테이너 안에 있는 "단일 연도 슬라이스" 를 빌드/쓰기
- 메타의 복수형 필드(`years: list[int]`) 와 짝을 이룸 ("복수 = 메타의 연도 목록 / 단수 = 단일 연도 슬라이스")

### DESIGN 문서 처리

- `docs/DESIGN_QBT_LIVE_FINAL.md` 는 사용자가 앱 측 갱신본 (`C:\android_workspace\qbt-live-app\docs\DESIGN_QBT_LIVE_FINAL.md`) 을 서버 프로젝트로 직접 복사 예정.
- 본 plan 작성 시점에 해당 파일은 modified 상태 (`git status` 기준) 이며, 사용자 의지대로 처리됨.
- 본 plan 의 코드 변경 / 테스트 갱신 / `src/live/CLAUDE.md` / `docs/COMMANDS.md` 갱신은 DESIGN 문서의 최종 형태와 독립적으로 진행 가능.

### 참고 링크

- 앱 측 plan (사용자 머신): `C:\android_workspace\qbt-live-app\docs\plans\PLAN_chart_archive_rename_to_years.md`
- 직전 작업 (recent 폐지) 프롬프트 (사용자 머신): `C:\android_workspace\qbt-live-app\docs\plans\PLAN_chart_recent_to_archive_only.md`

### 진행 로그 (KST)

- 2026-04-29 22:30: plan 초안 작성 (질문 1=A, 2=reset 활용, 3=ㄱ, 4=i 결정 반영)
- 2026-04-29 23:00: Phase 1 (models / rtdb_gateway / chart_data / constants) 완료, import 검증 통과
- 2026-04-29 23:05: Phase 2 (cli.py — run-daily / reset / backfill 갱신) 완료, `python -m live --help` 에서 `backfill-chart-years` 노출 확인
- 2026-04-29 23:10: Phase 3 (테스트 갱신) 완료, `pytest tests/live/` 491 passed 통과
- 2026-04-29 23:15: 마지막 Phase (문서 정합화 + black + validate_project.py) 완료, 1010 passed / 0 failed / 0 skipped

---
