# Implementation Plan: RTDB 경로 재구성 — `/charts/*` 분리 + equity 차트 신규 + `/history/summary/` 제거

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

**작성일**: 2026-04-17 16:30
**마지막 업데이트**: 2026-04-17 17:40
**관련 범위**: live (RTDB 경로 트리 / 차트 빌더 / CLI 파이프라인)
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py)
- [src/live/chart_data.py](../../src/live/chart_data.py)
- [src/live/cli.py](../../src/live/cli.py)
- [src/live/models.py](../../src/live/models.py)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)

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

- [x] 주가 차트 경로를 `/latest/chart_data/{asset_id}/*` → `/charts/prices/{asset_id}/*` 로 이동한다 (payload 스키마 / 필드명 / 값 / 갱신 주기 불변, **경로만** 이동).
- [x] equity 차트(`/charts/equity/`) 를 신규 추가한다. 주가 차트와 동일한 **meta + recent + archive/{YYYY} 3 분할 구조** 이며, 한 경로에 `model_equity` / `actual_equity` / `drift_pct` 세 배열을 같은 날짜 인덱스로 저장한다. 데이터 소스는 Git 정본 `history/summary.jsonl`.
- [x] RTDB `/history/summary/` 를 제거한다 (쓰기 로직 + rolling prune + reset 초기화 대상 모두 제거). Git 정본 `history/summary.jsonl` 은 **영구 유지**.
- [x] [live/models.py](../../src/live/models.py) 에 `EquityChartMeta` / `EquityChartSeries` dataclass 를 추가한다 (주가 차트 `ChartMeta` / `ChartSeries` 와 동일 패턴, 필드 구성은 equity 전용).
- [x] `backfill-chart-archive` CLI 에 `--target prices|equity|all` 인자를 추가한다 (기본값 `all`).

## 2) 비목표(Non-Goals)

- **주가 차트 payload 스키마 변경 금지**: `dates` / `close` / `ma_value` / `upper_band` / `lower_band` / 마커 4 종 모두 필드명 / 타입 / 값 동일.
- **자산 ID 규칙 변경 금지**: 소문자 유지 (`sso`, `qld`, `gld`, `tlt`).
- **`CHART_RECENT_MONTHS = 6` 상수 변경 금지**: equity 차트도 동일 상수 재사용.
- **MA / 밴드 계산 로직 변경 금지**: `add_single_moving_average` 재사용 유지.
- **Git 정본 `history/summary.jsonl` 포맷 변경 금지**: 영구 append-only, schema 불변.
- **`/fills/inbox/` / `/balance_adjust/inbox/` / `/fill_dismiss/inbox/` / `/device_tokens/` 변경 금지**.
- **`/history/fills/` / `/history/balance_adjusts/` / `/history/signals/` 신설 금지**: Plan 3 소관.
- **`daily_runner.run_daily()` 순수 계산 변경 금지**: I/O 는 CLI 계층에서만.
- **공통 예외 훅 / ephemeral shallow clone 메커니즘 변경 금지**.
- **점진적 마이그레이션 / 양쪽 경로 동시 유지 금지**: 앱 미구현 + reset 으로 RTDB 전체 재생성 가능 → Breaking change 허용.
- **앱(Android) / RTDB 외부 계약 문서화 외 앱 구현 연동**.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **`/latest/` 의 의미 혼재** — `/latest/` 는 개념적으로 "오늘의 스냅샷 (매일 덮어쓰기)" 이어야 하는데, 현재 `/latest/chart_data/{asset_id}/` 는 자산별 수년치 시계열(meta + recent + archive/{YYYY}) 을 담고 있어 실제로는 "과거 전체" 데이터다. 같은 `/latest/` 아래에 "오늘 1 일치" (portfolio / signals / pending_orders) 와 "수년치 시계열" (chart_data) 이 섞여 있어 네임스페이스 의미가 모호하다.
2. **equity 전 구간 시계열 미노출** — 현재 앱이 `model_equity` / `actual_equity` / `drift_pct` 시계열을 전 구간으로 조회할 경로가 없다. `/history/summary/` 가 일별 요약을 90 일만 rolling 으로 저장하지만, 사용자가 equity 차트로 전체 운영 기간을 조망하려면 더 긴 범위가 필요하다. Git 정본(`history/summary.jsonl`) 에는 전 구간이 있으나 앱은 Git 을 읽지 않는다.
3. **`/history/summary/` 역할 모호** — equity 시계열 기능이 추가되면 `/history/summary/` 의 역할은 equity + drift 차트로 완전히 흡수된다. 과거 요약 조회가 90 일 rolling 으로만 제공되고, 전 구간이 `/charts/equity/` 에 이미 있다면 `/history/summary/` 는 순수 중복이 된다.

앱 구현이 아직 시작되지 않았고 `reset` CLI 로 RTDB 를 언제든 재생성할 수 있으므로, 지금이 경로를 정리할 가장 좋은 시점이다.

### 최종 RTDB 구조 (이 plan 적용 후)

```
/latest/                          ← "오늘의 스냅샷" (1 일치만)
├── portfolio
├── signals/{asset_id}
└── pending_orders/{asset_id}

/charts/                          ← "시계열 데이터" (과거 전체)
├── prices/{asset_id}/            ← 주가 차트 (이동된 기존 chart_data)
│   ├── meta
│   ├── recent
│   └── archive/{YYYY}
└── equity/                       ← equity 차트 (신규)
    ├── meta
    ├── recent
    └── archive/{YYYY}

/history/                         ← 이벤트 이력 (Plan 3 소관, 본 plan 에서는 touch 안 함)

/fills/inbox/{uuid}               ← 변경 없음
/balance_adjust/inbox/{uuid}      ← 변경 없음
/fill_dismiss/inbox/{uuid}        ← 변경 없음
/device_tokens/{device_id}        ← 변경 없음
```

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준 / 로깅 / 장애 대응 원칙 / 출력 정밀도(`ROUND_CAPITAL` / `ROUND_RATIO`)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 아키텍처 / 자동 복구 금지 + 무조건 알림 / QBT 본체 수정 금지 / 순수 계산·I/O 분리 / qbt 상수 재사용 원칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — Given-When-Then / 파일 I/O 격리 / 결정적 테스트 / 외부 네트워크 mock
- [docs/CLAUDE.md](../CLAUDE.md) — Phase 구성 / Done 판정 / Commit Messages 규칙
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) — §1.1 아키텍처, §5 차트, §8.2 RTDB 경로, §8.3 역할 분리

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 주가 차트 쓰기 경로가 `/charts/prices/{asset_id}/*` 로 이동되었고 `/latest/chart_data/*` 는 더 이상 쓰지 않는다.
- [x] `/charts/equity/{meta|recent|archive/{YYYY}}` 3 경로가 매 `run-daily` 실행 후 존재하고, recent / archive/{현재_연도} 는 매일 재생성된다.
- [x] `/charts/equity/recent` 의 `dates` / `model_equity` / `actual_equity` / `drift_pct` 배열 길이가 모두 동일하다.
- [x] `/charts/equity/` payload 의 반올림 규칙이 준수된다 (`model_equity` / `actual_equity` 는 `ROUND_CAPITAL = 0` 자리, `drift_pct` 는 `ROUND_RATIO = 4` 자리).
- [x] `/history/summary/` 쓰기 블록 / `prune_history_summary` 함수 / `RTDB_HISTORY_SUMMARY_RETENTION_DAYS` 상수가 모두 제거되었다.
- [x] `reset` CLI 실행 후 RTDB 에 `/latest/chart_data/*` 와 `/history/summary/*` 가 존재하지 않는다 (`delete_all_except_device_tokens` 의 삭제 경로 목록에 `/charts` 추가 + `_HISTORY_SUMMARY_PATH` 제거).
- [x] [live/models.py](../../src/live/models.py) 에 `EquityChartMeta` / `EquityChartSeries` dataclass 가 추가되고 `__all__` 에 포함되었다.
- [x] `backfill-chart-archive --target prices|equity|all --year YYYY` 옵션이 동작한다 (기본값 `all`).
- [x] 신규 단위 테스트가 추가되었다 (모델 / 빌더 / gateway / CLI 통합).
- [x] 기존 `/latest/chart_data/` 및 `/history/summary/` 관련 테스트가 신규 경로로 수정되거나 삭제되었다.
- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 의 §1.1 / §5 / §8.2 / §8.3 이 갱신되었다.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 가 갱신되었다 (`chart_data.py` 역할 표).
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) Phase A 의 수동 확인 절차가 신규 경로 기준으로 갱신되었다.
- [x] `poetry run python validate_project.py` 통과 (passed=962, failed=0, skipped=0).
- [x] `poetry run black .` 실행 완료 (마지막 Phase).
- [x] `README.md` 변경 없음 (실행 명령어 / 환경변수 불변).
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py)
  - 내부 경로 상수 교체: `_CHART_DATA_PATH = "/latest/chart_data"` 제거, `_CHART_PRICES_PATH = "/charts/prices"` 와 `_CHART_EQUITY_PATH = "/charts/equity"` 추가.
  - `write_chart_meta` / `write_chart_recent` / `write_chart_archive_year` — 경로만 `/charts/prices/*` 로 변경, 함수 시그니처는 유지.
  - `write_read_model` — `/history/summary/{date}` 쓰기 블록 제거.
  - `prune_history_summary` 함수 제거 (+ `__all__` 에서 제거).
  - `delete_all_except_device_tokens` — `paths_to_delete` 목록에서 `_HISTORY_SUMMARY_PATH` 제거, `/charts` 최상위 추가.
  - `write_equity_meta` / `write_equity_recent` / `write_equity_archive_year` 3 신규 함수 추가 (+ `__all__`).
  - `_HISTORY_SUMMARY_PATH` / `_CHART_DATA_PATH` 모듈 상수 삭제.
- [src/live/chart_data.py](../../src/live/chart_data.py)
  - `build_equity_meta(state_dir)` 신규 — `history/summary.jsonl` 파싱 → `EquityChartMeta`.
  - `build_equity_recent(state_dir, months=None)` 신규 — 최근 N 개월 슬라이스 → `EquityChartSeries`.
  - `build_equity_archive_year(state_dir, year)` 신규 — 연도 슬라이스 → `EquityChartSeries`.
  - 주가 차트 빌더(`build_chart_meta` / `build_chart_recent` / `build_chart_archive_year`) 는 **변경 없음** (경로 변경은 gateway 소관).
- [src/live/models.py](../../src/live/models.py)
  - `EquityChartMeta` dataclass 추가: `first_date: str`, `last_date: str`, `recent_months: int`, `archive_years: list[int]` (주가 차트 `ChartMeta` 에서 `ma_window` 제외).
  - `EquityChartSeries` dataclass 추가: `dates: list[str]`, `model_equity: list[float]`, `actual_equity: list[float]`, `drift_pct: list[float]`.
  - `__all__` 에 2 개 추가.
- [src/live/constants.py](../../src/live/constants.py)
  - `RTDB_HISTORY_SUMMARY_RETENTION_DAYS` 상수 제거.
  - `CHART_RECENT_MONTHS` 는 주가 / equity 공용으로 유지 (주석 1 줄 갱신 — "주가 및 equity 차트 공통").
  - 필요 시 주석 문구에서 `/latest/chart_data/` 언급을 `/charts/*` 로 업데이트.
- [src/live/cli.py](../../src/live/cli.py)
  - `_publish_to_rtdb`
    - `rtdb_gateway.prune_history_summary` 호출 제거 + 관련 import 제거 (`RTDB_HISTORY_SUMMARY_RETENTION_DAYS`).
    - equity 차트 3 쓰기 호출 추가 (`write_equity_meta` / `write_equity_recent` / `write_equity_archive_year(year=current_year)`). 주가 차트와 동일한 순서로 이어 실행.
  - `_cmd_backfill_chart_archive`
    - `--target prices|equity|all` 인자 추가 (기본값 `all`).
    - 대상에 따라 주가 archive 또는 equity archive 또는 둘 다 재생성.
    - `--dry-run` 출력 메시지에 target 포함.
  - `_cmd_reset` — 경로 목록은 gateway 내부에서 처리되므로 cli 변경 거의 없음. 로깅 문구 필요 시 업데이트.
- [tests/live/test_rtdb_gateway.py](../../tests/live/test_rtdb_gateway.py)
  - `write_chart_meta` / `write_chart_recent` / `write_chart_archive_year` 테스트의 기대 경로를 `/charts/prices/*` 로 수정.
  - `write_equity_meta` / `write_equity_recent` / `write_equity_archive_year` 3 함수에 대한 신규 테스트.
  - `prune_history_summary` 테스트 삭제.
  - `write_read_model` 테스트에서 `/history/summary` 쓰기 검증 assert 삭제.
  - `delete_all_except_device_tokens` 테스트의 삭제 경로 목록 assert 갱신.
- [tests/live/test_chart_data.py](../../tests/live/test_chart_data.py)
  - equity 빌더 3 함수에 대한 신규 테스트 클래스 (summary.jsonl fixture 주입 → meta/recent/archive 슬라이스 정확성 검증).
- [tests/live/test_cli.py](../../tests/live/test_cli.py)
  - `run-daily` 통합 테스트의 RTDB mock assert 에서 `/charts/prices/*` / `/charts/equity/*` 경로 검증 추가.
  - `backfill-chart-archive --target` 옵션별 동작 테스트 신규.
  - `prune_history_summary` 관련 assert 삭제.
- [tests/live/test_models.py](../../tests/live/test_models.py)
  - `EquityChartMeta` / `EquityChartSeries` dataclass 생성 + `asdict` 검증 스모크 테스트 1 건씩.
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
  - §1.1 다이어그램의 `/history/summary` 제거, `/charts/*` 노드 추가.
  - §5 차트 섹션 경로 변경(131–138행).
  - §8.2 상단 트리(253–265행) 재작성: `/latest/chart_data/*` 제거, `/charts/prices/*` 및 `/charts/equity/*` 추가, `/history/summary/{YYYY-MM-DD}` 제거.
  - §8.2.5 제목/본문을 `/charts/prices/{asset_id}/` 로 변경.
  - §8.2.6 `/history/summary/` 섹션 삭제 (섹션 번호는 "(삭제됨)" 플레이스홀더로 유지하여 뒤 번호 유지 — §8.2.4 와 동일 패턴).
  - §8.2.x `/charts/equity/` 신설 섹션 추가 (meta / recent / archive payload 표 포함).
  - §8.3 역할 분리 표의 `/latest/*` / `/history/*` 행을 `/latest/*` / `/charts/*` / `/history/*` (이벤트 이력) 로 업데이트.
  - §9.1 스플릿 대응 절차의 `backfill-chart-archive` 명령 예시에 `--target` 옵션 추가.
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
  - 모듈별 역할 표에서 `rtdb_gateway.py` 설명의 `/history/summary` 언급 제거.
  - `chart_data.py` 설명에 equity 빌더 포함 문구 추가.
- [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md)
  - Phase A 수동 확인 절차:
    - `/charts/prices/{sso|qld|gld|tlt}/` 존재 확인 항목 추가 (이동 검증).
    - `/charts/equity/{meta|recent|archive/{현재_연도}}` 존재 + 배열 길이 동일 확인 항목 추가.
    - `/latest/chart_data/*` / `/history/summary/*` 부존재 확인 항목 추가.
    - `backfill-chart-archive --target equity --year YYYY` 수동 실행 확인 항목 추가.
- `README.md`: **변경 없음** (실행 명령어 / 환경변수 / 외부 계약 불변).

### 데이터/결과 영향

- **Breaking change (RTDB 한정)**: 최상위 경로 트리가 `/latest/chart_data` → `/charts/prices`, `/history/summary` 제거, `/charts/equity` 신규로 변경. 앱 미구현이므로 현재 소비자가 없음. `reset` CLI 로 재생성 가능.
- **Git 정본 영향 없음**: `qbt-live-state` 의 `history/summary.jsonl` 포맷 / 내용 불변. CSV 불변.
- **RTDB 용량 변화**: `/history/summary/` rolling 90 일 키 × 4 필드 제거(축소). `/charts/equity/` 는 전 구간 + 연도별 archive (약 10 년 × 252 거래일 × 3 필드 + 연도 archive) → 전체 용량은 증가 예상이나 Firebase Spark 한도(1 GB DB) 대비 충분히 여유.
- **출력 정밀도**: equity 차트는 새 출력 경로이므로 저장 규칙을 plan 에서 명시 (ROUND_CAPITAL / ROUND_RATIO). 내부 계산 정밀도 변경 없음.

## 6) 단계별 계획(Phases)

> 이 plan 은 인바리언트 / 지표 정의 / 에러 정책을 변경하지 않는다. 자동 복구 금지 / 무조건 알림 / 순수 계산·I/O 분리 / 반올림 규칙 모두 그대로 유지한다. 따라서 Phase 0 (레드) 은 두지 않고, 변경을 "뺄셈 → 덧셈 → 문서" 순으로 Phase 1 / Phase 2 / 마지막 Phase 로 나눈다. 각 Phase 는 끝나는 시점에 테스트가 그린이 되도록 설계한다.

---

### Phase 1 — 주가 차트 경로 이동 + `/history/summary/` RTDB 제거 ("뺄셈")

**목표**: RTDB 에서 (a) 주가 차트 경로를 `/latest/chart_data/*` → `/charts/prices/*` 로 옮기고, (b) `/history/summary/` 관련 쓰기 / prune / reset 초기화를 모두 제거한다. 구현이 끝나면 equity 차트를 제외한 모든 기능은 기존과 동일하게 동작해야 한다.

**작업 내용**:

- [x] [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) 내부 경로 상수 교체:
  - `_CHART_DATA_PATH` 삭제, `_CHART_PRICES_PATH = "/charts/prices"` 추가.
  - `_HISTORY_SUMMARY_PATH` 삭제.
- [x] `write_chart_meta` / `write_chart_recent` / `write_chart_archive_year` 의 내부 경로를 `_CHART_PRICES_PATH` 기준으로 변경.
- [x] `write_read_model` 에서 `/history/summary/{date}` 쓰기 블록 제거.
- [x] `prune_history_summary` 함수 및 관련 주석 제거 (+ `__all__`).
- [x] `delete_all_except_device_tokens` 의 `paths_to_delete` 목록 업데이트 (`_HISTORY_SUMMARY_PATH` 제거, `/charts` 추가).
- [x] [src/live/constants.py](../../src/live/constants.py) 에서 `RTDB_HISTORY_SUMMARY_RETENTION_DAYS` 상수 제거.
- [x] [src/live/cli.py](../../src/live/cli.py) 의 `_publish_to_rtdb` 에서 `prune_history_summary` 호출 및 관련 import 제거.
- [x] 테스트 갱신 (test_rtdb_gateway.py / test_cli.py).
- [x] 변경 후 관련 테스트 그린 확인 (`pytest tests/live/test_rtdb_gateway.py tests/live/test_cli.py` 79 건 통과).

---

### Phase 2 — equity 차트 신규 추가 + `backfill-chart-archive --target` ("덧셈")

**목표**: `/charts/equity/` 3 분할 경로를 도입하고 daily runner 가 매 실행마다 meta + recent + 현재 연도 archive 를 재생성하도록 한다. 과거 연도 archive 는 backfill CLI 의 `--target` 옵션으로 재생성 가능.

**작업 내용**:

- [x] [src/live/models.py](../../src/live/models.py) 에 `EquityChartMeta` / `EquityChartSeries` dataclass 추가 (+ `__all__`).
- [x] [src/live/chart_data.py](../../src/live/chart_data.py) 에 `_load_summary_rows` / `_equity_series_from_rows` 내부 헬퍼 + `build_equity_meta` / `build_equity_recent` / `build_equity_archive_year` 3 공개 빌더 추가.
  - 반올림: `model_equity` / `actual_equity` → `ROUND_CAPITAL`, `drift_pct` → `ROUND_RATIO`.
  - 빈 / 누락 summary.jsonl / 손상 JSONL 은 `RuntimeError` 전파.
- [x] [src/live/rtdb_gateway.py](../../src/live/rtdb_gateway.py) 에 `_CHART_EQUITY_PATH` 상수와 `write_equity_meta` / `write_equity_recent` / `write_equity_archive_year` 3 함수 추가 (+ `__all__`).
- [x] [src/live/cli.py](../../src/live/cli.py) 의 `_publish_to_rtdb` 에 equity 차트 쓰기 3 호출 추가 (주가 차트 쓰기 이후, 신규 fills 마킹 이전 순서).
- [x] `_cmd_backfill_chart_archive` 에 `--target prices|equity|all` 인자 추가 (기본값 `all`). `--year` 가 주가 / equity archive_years 어디에도 없으면 WARNING 후 `return 0`. `--dry-run` 출력에 target / 주가 연도 / equity 연도 포함.
- [x] 신규/갱신 테스트:
  - test_models.py: `EquityChartMeta` / `EquityChartSeries` 필드 구성 + `asdict` roundtrip.
  - test_chart_data.py: `TestBuildEquityMeta` / `TestBuildEquityRecent` / `TestBuildEquityArchiveYear` 신규 (9 건).
  - test_rtdb_gateway.py: `TestWriteEquityMeta` / `TestWriteEquityRecent` / `TestWriteEquityArchiveYear` 신규 (4 건) + `TestDeleteAllExceptDeviceTokens` 추가.
  - test_cli.py: `_publish_to_rtdb` equity assert 추가, backfill `--target prices|equity|all` 시나리오 4 종 테스트.
- [x] 변경 후 전체 live 테스트(447 건) 그린 확인.

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md) 갱신:
  - §1.1 다이어그램 `/history/summary` 제거 + `/charts/prices`, `/charts/equity` 추가.
  - §2 / §5 본문 경로 표기 갱신 + §5 에 equity 섹션 안내 추가.
  - §8.2 상단 트리 재작성.
  - §8.2.5 전체를 `/charts/prices/{asset_id}/` 로 제목 / 본문 갱신.
  - §8.2.6 `/charts/equity/` 신설 (5 하위 절 포함 — meta / recent / archive / 경계 중복 정책 / 중요 사항).
  - §8.3 역할 분리 표 `/charts/*` 로 갱신.
  - §9 / §9.1 / §12 의 경로 표기 갱신 + `backfill-chart-archive --target` 옵션 안내 추가.
- [x] [src/live/CLAUDE.md](../../src/live/CLAUDE.md) 의 `chart_data.py` 역할 요약 갱신 (주가 + equity 병기).
- [x] [docs/TEST_QBT_LIVE_MANUAL.md](../TEST_QBT_LIVE_MANUAL.md) Phase A 갱신 — 7 번 항목 `/charts/prices/*` 로, 8 번 항목 `/charts/equity/*` 신설 (구 `/history/summary/` 섹션 대체). `--target equity --year YYYY` 확인 포함.
- [x] `README.md` 변경 없음 재확인.
- [x] `poetry run black .` 실행 (3 파일 자동 포맷).
- [x] `poetry run python validate_project.py` 통과.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정 (`상태: ✅ Done`).

**Validation**:

- [x] `poetry run python validate_project.py` (passed=962, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / RTDB `/charts/*` 재구성 (주가 이동 + equity 신규 + `/history/summary` 제거)
2. live / RTDB 경로 트리 전면 개편 — `/charts/prices` + `/charts/equity` 도입, `/history/summary` 삭제
3. live / equity 차트 3 분할 신규 + 주가 차트 `/charts/prices` 이동 + RTDB 요약 경로 제거
4. live / 차트 데이터 RTDB 경로 재설계 — equity 시계열 추가 및 `backfill-chart-archive --target` 옵션
5. live / `/latest/chart_data` → `/charts/prices` 이동 + equity 차트 추가 + 설계서/테스트 갱신

## 7) 리스크(Risks)

- **리스크 1** — Breaking change: 앱이 구버전 경로(`/latest/chart_data/*`, `/history/summary/*`) 를 이미 구독 중이면 화면이 깨진다.
  - 완화: 앱 미구현이 전제. 배포 직전 앱/프론트 코드베이스(별도 리포) 에서 경로 참조 여부를 재확인하고, 참조가 있다면 이 plan 을 중단하고 마이그레이션 전략을 재검토한다.
- **리스크 2** — `history/summary.jsonl` 손상 시 equity 차트 생성 불가.
  - 완화: 기존 `load_user_trades` / `load_signal_history` 와 동일 패턴으로 `json.JSONDecodeError` → `RuntimeError("손상된 JSONL ...")` 전파. 공통 예외 훅이 실패 알림 발송. 자동 복구 / 부분 파싱은 도입하지 않음 (원칙 1).
- **리스크 3** — `_publish_to_rtdb` 내부에서 equity 차트 쓰기 중 일부만 성공하고 도중 실패.
  - 완화: 다음 `run-daily` 가 meta / recent / archive/{현재_연도} 를 전체 재생성하므로 자동 수렴. 트랜잭션 / 롤백 / 재시도는 도입하지 않음 (원칙 1).
- **리스크 4** — `backfill-chart-archive` 의 `--target all` 로 과거 연도 equity archive 전체 재생성 시 summary.jsonl 이 대용량인 경우 (10 년+) RTDB 쓰기 레이턴시 증가.
  - 완화: 현재 연간 252 거래일 × 3 필드 × float 로 1 년 archive 당 수십 KB 수준. Firebase Spark 한도에 비해 충분. 필요 시 `--year` 로 단일 연도씩 쪼개 실행 가능.
- **리스크 5** — `delete_all_except_device_tokens` 의 경로 목록 업데이트 실수로 `/device_tokens` 이 삭제되면 FCM 알림이 끊어진다.
  - 완화: Phase 1 의 `test_delete_all_except_device_tokens` 에서 `/device_tokens` 가 삭제 목록에 **없음** 을 assert. 테스트로 강제.

## 8) 메모(Notes)

- **Plan 1 과 독립**: 서로 touch 영역이 다르므로(Plan 1 은 Git `history/states/`, Plan 2 는 RTDB 트리 + equity 차트) 순서 무관.
- **Plan 3 보다 먼저 적용**: Plan 2 에서 `/history/summary/` 를 제거한 뒤 Plan 3 가 `/history/` 하위에 신규 3 경로(fills / balance_adjusts / signals) 를 추가한다. Plan 2 → Plan 3 순서가 자연스럽다.
- `CHART_RECENT_MONTHS` 상수는 주가 / equity 공용으로 유지. 두 차트 모두 "최근 6 개월" 의미가 동일.
- equity 빌더의 데이터 소스가 `history/summary.jsonl` 이므로, CLI 에서 `_persist_history` (append summary) 가 `_publish_to_rtdb` (equity 차트 쓰기) 보다 먼저 호출되어야 한다. 현재 `_cmd_run_daily` 순서(`_persist_history` → `_publish_to_rtdb`) 가 이를 이미 만족한다.
- 앱(Android) 구현은 본 plan 범위 밖. 앱 연동은 별도 작업 항목으로 관리.

### 진행 로그 (KST)

- 2026-04-17 16:30: plan 초안 작성 (상태 → 🟡 Draft).
- 2026-04-17 16:35: Phase 1 착수 (상태 → 🔄 In Progress).
- 2026-04-17 17:00: Phase 1 완료 — 주가 차트 `/charts/prices/*` 이동 + RTDB `/history/summary/` 관련 코드(쓰기 / prune / 상수 / CLI 호출) 제거. 기존 테스트 녹색 유지 확인 (79 건).
- 2026-04-17 17:20: Phase 2 완료 — `EquityChartMeta` / `EquityChartSeries` dataclass, equity 빌더 3 종, `write_equity_*` gateway 3 종, `_publish_to_rtdb` equity 호출 추가, `backfill-chart-archive --target` 인자 추가. 신규 테스트 17 건 포함 live 전체 447 건 녹색.
- 2026-04-17 17:40: 문서 갱신 (DESIGN §1.1 / §2 / §5 / §8.2 / §8.3 / §9 / §12, live CLAUDE.md, TEST_QBT_LIVE_MANUAL.md) + `black` + `validate_project.py` 통과 (passed=962, failed=0, skipped=0). 상태 → ✅ Done.

---
