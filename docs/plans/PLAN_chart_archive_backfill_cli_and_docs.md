# Implementation Plan: backfill-chart-archive CLI + 문서 최신화

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

**작성일**: 2026-04-14 11:35
**마지막 업데이트**: 2026-04-14 12:00
**관련 범위**: live (src/live/cli.py), tests/live/, docs/
**관련 문서**:

- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [docs/DESIGN_QBT_LIVE_FINAL.md](../DESIGN_QBT_LIVE_FINAL.md)
- [docs/CLAUDE.md](../CLAUDE.md)
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

- [x] `backfill-chart-archive` 신규 CLI 명령을 추가한다. 운영자가 수동 실행하여 자산 전체의 `/latest/chart_data/{asset_id}/archive/{YYYY}` 를 일괄 재생성 / 업로드한다.
- [x] 이 명령은 **최초 배포 시 1 회** 와 **스플릿/무상증자 감지 시 수동 대응** 두 가지 시나리오를 모두 커버한다.
- [x] 설계서에 **스플릿/무상증자 수동 대응 절차** 를 명문화하여 운영자가 절차를 명확히 알 수 있도록 한다.
- [x] 루트 `CLAUDE.md`, `docs/CLAUDE.md`, `src/live/CLAUDE.md` 를 점검하여 Plan 1/2 변경과 backfill CLI 추가를 반영한다.

## 2) 비목표(Non-Goals)

- `split_adjust.py` 자동화 모듈 구현 (사용자 결정으로 제외).
- yfinance 의 split events API 와 자동 교차검증.
- equity 불변식 자동 검증 로직.
- BufferZoneState 스플릿 어댑터.
- GitHub Actions workflow 변경 (backfill 은 운영자 수동 실행 전용).
- `README.md` 의 워크플로우 섹션 대규모 개편. 신규 명령 한 줄 추가 정도만 허용.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

Plan 2 에서 `/latest/chart_data/` 가 `meta + recent + archive/{YYYY}` 3 분할 구조로 재작성되었다. daily runner 는 **매 실행마다** `meta + recent + archive/{현재_연도}` 를 덮어쓰지만, **이전 연도 archive** 는 건드리지 않는다.

이 구조의 정상 동작을 위해 다음 두 시점에 운영자 개입이 필요하다:

1. **최초 배포 직후**: 모든 archive/{YYYY} 경로가 아직 존재하지 않는 상태. 한 번에 전체 연도를 생성해 업로드해야 앱이 줌아웃 시 과거 데이터를 읽을 수 있다.
2. **스플릿/무상증자 감지 후**: yfinance 가 과거 주가를 재조정하므로 모든 과거 연도 archive 를 다시 생성해야 한다. 운영자가 `rebuild-data` 로 CSV 를 재다운로드한 뒤, 이 CLI 로 archive 를 재업로드한다.

이 두 시나리오 모두 **동일한 작업** (자산 전체 × 모든 연도 archive 재생성 + 업로드) 이므로 하나의 CLI 명령으로 처리한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준, CLI 계층 규칙
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 규칙, 자동 복구 금지 원칙, ephemeral state repo 패턴
- [docs/CLAUDE.md](../CLAUDE.md) — plan 관리 규칙 (이 plan 의 운영 규칙)
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

- [x] `_cmd_backfill_chart_archive` 가 `src/live/cli.py` 에 추가되고 `backfill-chart-archive` 서브 커맨드로 등록된다.
- [x] 명령은 ephemeral state repo 를 사용하여 CSV 를 로드하고, `build_chart_meta` 로 `archive_years` 를 얻은 뒤, 연도별로 `build_chart_archive_year` + `write_chart_archive_year` 를 순회 호출한다. 또한 `build_chart_meta` + `write_chart_meta` 도 함께 호출하여 `meta.archive_years` 를 최신 목록으로 반영한다.
- [x] `--year` 옵션 (선택) 을 지원하여 단일 연도만 재생성 가능하도록 한다.
- [x] `--dry-run` 옵션을 지원하여 실제 RTDB 쓰기 없이 대상 연도 목록만 출력한다.
- [x] `tests/live/test_cli.py` 에 본 명령의 정상 경로 / dry-run / 단일 연도 지정 케이스 테스트가 추가된다.
- [x] 설계서 `DESIGN_QBT_LIVE_FINAL.md` 에 **스플릿/무상증자 수동 대응 절차** 섹션이 추가되고, `backfill-chart-archive` 가 대응 절차에 포함된다.
- [x] `src/live/CLAUDE.md` 의 "CLI 명령" 관련 기술 (있다면) 또는 "스플릿 대응" 섹션에 수동 대응 절차와 backfill 명령 이름이 반영된다.
- [x] `docs/CLAUDE.md` 를 재검토하여 Plan 1/2/3 변경을 반영할 부분이 있는지 확인한다 (플랜 관리 규칙 문서이므로 대부분 변경 없음 예상).
- [x] `README.md`: 필요 시 "워크플로우 3: QBT Live" 의 명령어 목록에 `backfill-chart-archive` 한 줄 추가. 변경이 필요한지 여부를 Phase 3 에서 판단 후 명시.
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/cli.py` — `_cmd_backfill_chart_archive` 추가, argparse 등록
- `tests/live/test_cli.py` — 신규 테스트 클래스 `TestCmdBackfillChartArchive`
- `docs/DESIGN_QBT_LIVE_FINAL.md` — 스플릿/무상증자 수동 대응 절차 섹션 추가 (§5 뒤 또는 §9 "실패 / 예외 대응" 근처)
- `src/live/CLAUDE.md` — 필요 시 "스플릿 대응" 절차 요약 (핵심: "현재 구조에서는 backfill-chart-archive 로 수동 대응" 정도)
- `docs/CLAUDE.md` — 재검토 후 필요 시 최소 수정
- `README.md` — 필요 시 1 줄 추가

### 데이터/결과 영향

- `/latest/chart_data/{asset_id}/archive/{YYYY}` 가 일괄 생성됨.
- `/latest/chart_data/{asset_id}/meta` 가 최신 `archive_years` 목록으로 갱신됨.
- Git 정본은 건드리지 않음 (backfill 은 RTDB 쓰기만 수행, ephemeral state repo 는 read-only 성격).

## 6) 단계별 계획(Phases)

### Phase 0 — 신규 명령 계약을 테스트로 먼저 고정 (레드)

**작업 내용**:

- [x] `tests/live/test_cli.py` 에 `TestCmdBackfillChartArchive` 클래스 추가:
  - 정상 경로: 빌더와 write 함수를 스파이로 교체 후 `main(["backfill-chart-archive"])` 실행 → `write_chart_meta` 1 회 + `write_chart_archive_year` 가 각 연도별로 1 회씩 호출됨.
  - `--year` 옵션: `main(["backfill-chart-archive", "--year", "2023"])` → `write_chart_archive_year` 는 `year=2023` 으로 단 1 회만 호출됨.
  - `--dry-run`: `main(["backfill-chart-archive", "--dry-run"])` → write 함수는 **한 번도** 호출되지 않음, stdout 에 대상 연도 목록 출력.
  - RTDB 초기화 실패: `_initialize_rtdb_app` 이 None 반환 시 공통 예외 훅이 실패 알림 발송 + exit 1.
- [x] 이 단계에서는 `_cmd_backfill_chart_archive` 가 아직 없으므로 테스트는 레드 상태.

---

### Phase 1 — backfill CLI 구현 (그린 복귀)

**작업 내용**:

- [x] `src/live/cli.py` 에 `_cmd_backfill_chart_archive` 구현:
  - `ephemeral_state_repo(push_on_success=False, commit_subcommand="backfill-chart-archive")` 컨텍스트 내에서 수행 (Git 정본 read-only).
  - `build_chart_meta(state_dir)` 로 자산별 `ChartMeta` 를 얻어 `archive_years` 합집합을 계산.
  - `args.year` 가 주어지면 해당 연도만, 아니면 `archive_years` 전체 순회.
  - `args.dry_run` 이 True 면 stdout 에 자산 × 연도 수와 대상 연도 목록을 출력 후 return 0.
  - 그렇지 않으면 `_require_rtdb_app()` → 연도마다 `build_chart_archive_year` + `write_chart_archive_year` 호출.
  - 마지막에 `write_chart_meta(rtdb_app, meta_map)` 로 meta 갱신 (archive_years 재반영).
- [x] argparse 서브커맨드 등록:
  - `--year YYYY` (int, default=None)
  - `--dry-run` (store_true)
- [x] Phase 0 의 테스트가 그린으로 전환됨을 확인.

---

### Phase 2 — 설계서 / CLAUDE.md 최신화

**작업 내용**:

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 에 "스플릿/무상증자 수동 대응 절차" 섹션 추가. 위치는 §9 "실패 / 예외 대응" 뒤 또는 §5 차트 섹션 말미. 내용:
  1. 감지: `data_validator.validate_prev_close` 가 전일 종가 대비 1% 이상 괴리 시 `ValueError` 로 run-daily 중단 → FCM/텔레그램 알림.
  2. 확인: yfinance 공시에서 스플릿/무상증자 사실 확인.
  3. 수동 보정 절차:
     - `rebuild-data {TICKER}` 로 CSV 재다운로드.
     - `qbt-live-state` 에서 `live_state.json` 의 영향받은 자산 shares/avg_price 수동 조정 (shares × ratio, avg_price / ratio). BufferZoneState 내부 가격 필드도 함께 확인.
     - git commit / push (조정 사유 + 비율 메시지 포함).
     - `backfill-chart-archive` 실행 → 전체 archive 재생성.
  4. 위 절차는 "자동 복구 금지 + 무조건 알림" 원칙에 따른 **수동 대응 전용** 임을 명시.
- [x] `src/live/CLAUDE.md` 를 재검토하여 스플릿 대응 관련 문장 / 백필 CLI 존재를 짧게 반영 (장황한 절차는 설계서 참고로 링크).
- [x] `docs/CLAUDE.md` 를 재검토하여 변경이 필요한지 확인. (plan 관리 규칙 문서이므로 변경 없음 확률 높음 — 변경 불필요 시 "변경 없음" 을 Notes 에 명시.)
- [x] `README.md` 의 "워크플로우 3: QBT Live" 섹션에 `backfill-chart-archive` 명령어 한 줄 추가 (또는 기존 명령어 표의 행 추가).

---

### Phase 3 — 최종 검증 (마지막 Phase)

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=915, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / backfill-chart-archive CLI 추가 + 스플릿 수동 대응 절차 명문화
2. live / chart_archive 백필 명령 + 설계서 스플릿 대응 섹션 반영
3. live / 차트 archive 일괄 생성 CLI + 수동 운영 절차 문서화
4. live / backfill 명령 + 스플릿/무상증자 대응 절차 문서 최신화
5. live / chart archive backfill CLI + docs 최신화

## 7) 리스크(Risks)

- **리스크 1**: backfill 중간에 네트워크 실패 시 일부 연도만 업로드되어 앱 차트가 불완전해질 수 있다.
  - **완화**: 연도 순회는 오름차순 진행하고, 실패 시 예외를 그대로 전파하여 공통 알림 훅이 처리. 재실행하면 전체 연도가 다시 덮어쓰기되므로 복구 가능. 멱등성 확보.
- **리스크 2**: `--year` 지정 시 존재하지 않는 연도 입력 시 아무 일도 안 일어날 수 있다.
  - **완화**: `meta.archive_years` 에 포함되지 않은 연도는 경고 로그 출력 후 종료 (`ValueError` 또는 WARNING 후 return 0).
- **리스크 3**: ephemeral state repo clone 이 read-only 목적인데 push_on_success=False 로 올바르게 설정되는지 확인 필요.
  - **완화**: 기존 `history` 명령과 동일한 `push_on_success=False` 패턴 사용.

## 8) 메모(Notes)

- `backfill-chart-archive` 는 GitHub Actions 자동 실행 대상이 **아니다**. 운영자가 로컬에서 실행한다 (README 의 워크플로우에서도 "수동 실행" 으로 표기).
- `--year` 없이 전체 백필 시 자산 4 × 연도 N 개 ≈ 50+ 회 write 가 발생. 각 write 가 독립 RTDB set 이므로 시간은 수 초 내외.
- 최초 1 회 backfill 이후에는 daily runner 가 `archive/{현재_연도}` 를 매일 갱신하므로 정상 운영 상태에 이를 수 있다.
- 본 plan 은 스킵을 허용하지 않는다.

### 진행 로그 (KST)

- 2026-04-14 11:35: Draft 작성
- 2026-04-14 11:45: Phase 0 완료 (TestCmdBackfillChartArchive 4 케이스 — 전체 / --year / --dry-run / RTDB 초기화 실패, 4 tests red)
- 2026-04-14 11:50: Phase 1 완료 (_cmd_backfill_chart_archive 구현 + argparse 등록, 4 tests green)
- 2026-04-14 11:55: Phase 2 완료 (DESIGN_QBT_LIVE_FINAL.md §9.1 "스플릿/무상증자 수동 대응 절차" 신설, src/live/CLAUDE.md 모듈 표 + 자동 복구 금지 섹션에 수동 대응 절차 추가, README.md 명령어 예시 추가, docs/CLAUDE.md 변경 없음 확인)
- 2026-04-14 12:00: Phase 3 완료 (black 적용, validate_project.py passed=915/failed=0/skipped=0)

---
