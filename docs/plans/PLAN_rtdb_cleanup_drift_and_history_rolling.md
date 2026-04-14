# Implementation Plan: RTDB 정리 — /latest/drift 제거 + /history/summary rolling window

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

**작성일**: 2026-04-14 10:15
**마지막 업데이트**: 2026-04-14 10:45
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

- [x] `/latest/drift` 경로를 RTDB 에서 제거한다 (중복 경로 제거).
- [x] `/history/summary/{YYYY-MM-DD}` 를 매 실행 후 최근 N 일만 유지하도록 정리 로직을 추가한다 (영구 누적 → rolling window).
- [x] 설계서 `DESIGN_QBT_LIVE_FINAL.md` 를 위 변경에 맞춰 최신화한다.

## 2) 비목표(Non-Goals)

- `chart_data` 재구조화 (별도 plan 에서 처리).
- Git 정본 (`history/summary.jsonl`, `history/daily/{date}.json`) 의 retention 변경 (Git 정본은 영구 누적 유지).
- `DriftReport` 내부 구조, `drift_pct` 계산 로직, 임계값 상수 (`DRIFT_WARNING_RATIO` / `DRIFT_CORRECTION_RATIO`) 변경.
- FCM/텔레그램 알림 본문 변경.
- 앱 코드 변경 (앱 미개발).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**문제 1 — `/latest/drift` 중복**

`/latest/drift` 의 3 개 필드(`drift_pct`, `model_equity`, `actual_equity`) 는 이미 `/latest/portfolio` 에 모두 존재한다. per_asset 정보도 포함하지 않는다 (설계서 §8.2.4 명시). 즉 `/latest/drift` 는 정보 중복이며, 독립 경로로 존재할 정당성이 없다.

**문제 2 — `/history/summary` 무한 누적**

현재 설계서 §8.2.6 은 "영구 누적되며 자동 정리되지 않는다" 고 명시한다. 앱은 최근 30~90 일만 읽을 것이라 명시되어 있음에도 RTDB 쪽은 계속 누적되어, 장기 운용 시 Spark 무료 요금제 저장 용량을 잠식한다. 전체 히스토리의 정본은 Git (`history/summary.jsonl`) 이므로 RTDB 쪽은 "앱 표시용 rolling cache" 로 축소해도 정보 손실이 없다.

**영향 범위**

- `src/live/rtdb_gateway.py`: `write_read_model` 에서 `/latest/drift` 쓰기 제거, `/history/summary` 정리 로직 추가 (신규 함수).
- `src/live/constants.py`: 유지 일수 상수 추가.
- `src/live/daily_runner.py` 또는 `src/live/cli.py`: 정리 로직 호출 지점 결정.
- `tests/live/test_rtdb_gateway.py`: 테스트 수정 및 추가.
- `docs/DESIGN_QBT_LIVE_FINAL.md`: §8.2.4 제거, §8.2.6 retention 정책 명시, §12 에서 `/latest/drift` 참조 제거.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md) — 코딩 표준, 로깅 정책, 구현 원칙 (명시적 검증, 불가능 조건 처리 등)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md) — live 도메인 규칙, 자동 복구 금지 원칙, 순수 계산/I/O 분리
- [tests/CLAUDE.md](../../tests/CLAUDE.md) — 테스트 작성 규칙, Given-When-Then, 부동소수점 비교 규칙, 외부 네트워크 격리

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `/latest/drift` 쓰기가 `write_read_model` 에서 제거되었다.
- [x] `/history/summary/` 의 retention (최근 N 일) 정리 함수가 `rtdb_gateway` 에 추가되고, daily 실행 경로에서 호출된다.
- [x] 신규/수정 테스트로 위 두 동작이 고정된다 (Given-When-Then 패턴 + `pytest.approx` 규칙 준수).
- [x] `poetry run python validate_project.py` 통과 (passed=903, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 설계서 `DESIGN_QBT_LIVE_FINAL.md` 업데이트 (§8.2.4 / §8.2.6 / §12 / 목록 다이어그램).
- [x] `README.md`: 변경 없음 (본 plan 은 내부 스키마 변경이며 사용자 가시 명령 / 워크플로우 변경 없음).
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영).

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/live/constants.py` — `RTDB_HISTORY_SUMMARY_RETENTION_DAYS` 신설
- `src/live/rtdb_gateway.py` — `write_read_model` 수정, `prune_history_summary` 신규
- `src/live/daily_runner.py` 또는 `src/live/cli.py` — prune 호출 배치 (실제 호출 지점은 Phase 1 에서 결정)
- `tests/live/test_rtdb_gateway.py` — `/latest/drift` 관련 assertion 제거, `prune_history_summary` 테스트 추가
- `tests/live/test_constants.py` — 신규 상수 노출 확인 (필요 시)
- `tests/live/test_daily_runner.py` 또는 `test_cli.py` — prune 호출 통합 테스트 (호출 지점에 따라)
- `docs/DESIGN_QBT_LIVE_FINAL.md` — §8.2.4 제거, §8.2.6 retention 정책 명시, §12 의 `/latest/drift` 참조 제거, §8.2 상단 경로 목록 수정
- `README.md`: **변경 없음**

### 데이터/결과 영향

- RTDB 경로 `/latest/drift` 가 사라진다. 앱이 미개발이므로 외부 소비자 없음.
- `/history/summary/{YYYY-MM-DD}` 가 retention 기준을 넘으면 삭제된다. Git 정본은 건드리지 않는다.
- live 서버 출력(CSV/JSON) 반올림 규칙 영향 없음.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정 (레드)

> 이 Phase 는 "RTDB 에 `/latest/drift` 가 없어야 한다" 및 "prune 이 retention 을 넘는 날짜만 삭제한다" 는 정책을 테스트로 먼저 고정한다.

**작업 내용**:

- [x] `tests/live/test_rtdb_gateway.py` 의 `TestWriteReadModel` 에서 `/latest/drift` 관련 assertion 을 "존재하지 않아야 한다" 로 변경.
- [x] `tests/live/test_rtdb_gateway.py` 에 `TestPruneHistorySummary` 클래스 신규 작성 (경계일/빈 store/비 dict/파손 키/미래 키 5 케이스).
- [x] `_MockRef.get()` 을 계층적 읽기로 보강 (부모 경로에서 즉시 자식 dict 반환).
- [x] `src/live/constants.py` 에 `RTDB_HISTORY_SUMMARY_RETENTION_DAYS = 90` 상수 추가.

이 단계 종료 시점에는 레드(실패) 상태가 유지되는 테스트가 존재해도 좋다.

---

### Phase 1 — 핵심 구현 (그린 유지)

**작업 내용**:

- [x] `src/live/rtdb_gateway.py` `write_read_model` 에서 `drift_payload` 블록 및 `/latest/drift` set 제거.
- [x] `src/live/rtdb_gateway.py` 에 `prune_history_summary(app, retention_days, today) -> None` 신규 구현. ISO 8601 파싱 실패 키는 건너뛰고, 비 dict 루트는 no-op, `entry_date < cutoff` 에만 삭제.
- [x] `rtdb_gateway.__all__` 에 `prune_history_summary` 추가.
- [x] `write_read_model` 의 docstring 갱신 (`/latest/drift` 언급 제거).
- [x] Phase 0 의 테스트가 모두 그린으로 전환됨을 확인 (27 passed).

---

### Phase 2 — prune 호출 배치 + 통합 테스트

**작업 내용**:

- [x] `src/live/cli.py` 의 `_publish_to_rtdb` 에서 `write_read_model` 호출 직후 `prune_history_summary(app, RTDB_HISTORY_SUMMARY_RETENTION_DAYS, today=execution_date)` 호출. `execution_date` 는 `DailyResult.execution_date` 를 `date.fromisoformat` 로 파싱.
- [x] `tests/live/test_cli.py::TestCmdRunDailySuccess::test_publish_to_rtdb_invokes_prune_history_summary` 통합 테스트 추가 (prune 스파이로 호출 인자 검증).

---

### Phase 3 — 문서 정리 및 최종 검증 (마지막 Phase)

**작업 내용**

- [x] `docs/DESIGN_QBT_LIVE_FINAL.md` 수정:
  - §8.2 상단 경로 목록에서 `/latest/drift` 라인 제거하고 `/history/summary` 라인에 rolling window 명시.
  - §8.2.1 은 원래 drift 스칼라 필드를 이미 포함하고 있어 내용 변경 없음 (다이어그램 설명문에서 "drift 스칼라 + assets" 로 표기 추가).
  - §8.2.4 는 "(삭제됨)" placeholder 로 대체, 제거 사유와 대안 경로 명시.
  - §8.2.6 에 retention 정책 (90 일 rolling window, cutoff 경계 규칙) 을 명시.
  - §12 에서 `/latest/drift` 언급 제거, per_asset drift 노출 위치도 `/latest/portfolio` 로 정리.
  - §8.2 상단 "drift_pct 스케일" 문장에서 `/latest/drift` 참조 제거.
- [x] `src/live/CLAUDE.md`: 변경 불필요 (구체 RTDB 경로는 설계서 SoT, 해당 문서는 모듈 책임 표 수준).
- [x] `README.md`: 변경 없음 확인.
- [x] `poetry run black .` 실행(자동 포맷 적용, 5 files unchanged).
- [x] 변경 기능 및 전체 플로우 최종 검증.
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료.
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정.

**Validation**:

- [x] `poetry run python validate_project.py` (passed=903, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. live / RTDB `/latest/drift` 중복 경로 제거 + `/history/summary` rolling window 도입
2. live / RTDB read model 중복 제거 및 history summary 보존 정책 명문화
3. live / drift 중복 경로 제거 및 history retention 90 일 정책 추가
4. live / RTDB 스키마 정리 (drift 제거 + summary rolling) + 설계서 반영
5. live / daily runner RTDB write 정리 및 history summary 자동 정리 추가

## 7) 리스크(Risks)

- **리스크 1**: prune 호출이 `run-daily` 안에서 실패하면 정상 write 이후에 중단을 유발할 수 있음.
  - **완화**: live 의 "자동 복구 금지 + 무조건 알림" 원칙에 따라, prune 예외는 억제하지 않고 정상 예외 전파. 공통 알림 훅이 처리. 단, prune 은 "소급 정리" 이므로 하루 지연되어도 정보 손실 없음 (다음 실행에서 다시 시도).
- **리스크 2**: 설계서 §8.2.4 제거 시 번호 체계가 흐트러질 수 있음.
  - **완화**: 섹션 번호는 그대로 유지하고 "(삭제됨)" 표기. 앱 계약 변화 시 참고자가 혼란 없이 찾을 수 있도록 보존.
- **리스크 3**: `/latest/drift` 제거로 기존 CI/regression 테스트가 레드로 전환.
  - **완화**: Phase 0 에서 테스트를 먼저 수정하여 "drift 가 없어야 한다" 로 고정. Phase 1 구현 후 즉시 그린 복귀.

## 8) 메모(Notes)

- `prune_history_summary` 의 retention 기본값 `90` 은 설계서 §8.2.6 의 "앱은 최근 30~90 일만 읽는다" 권고 상한.
- 실행 시점의 "오늘" 을 `DailyResult.execution_date` 기준으로 삼는 이유: 운영자가 과거 날짜로 `run-daily` 를 재실행할 경우 (historical backfill) retention 창이 그 날짜 기준으로 움직이도록. 실시간 시계 `date.today()` 를 쓰면 backfill 과 현재 시각이 어긋남.
- **스킵 정책**: 본 plan 은 스킵을 허용하지 않는다. 테스트 추가는 Phase 0 / Phase 2 로 분해한다.

### 진행 로그 (KST)

- 2026-04-14 10:15: Draft 작성
- 2026-04-14 10:25: Phase 0 완료 (상수 추가, `_MockRef` 계층 읽기 보강, TestPruneHistorySummary 5 케이스 추가, `/latest/drift` assertion 반전)
- 2026-04-14 10:35: Phase 1 완료 (`rtdb_gateway.prune_history_summary` 구현 + `write_read_model` 에서 drift 쓰기 제거, 27 tests green)
- 2026-04-14 10:40: Phase 2 완료 (`_publish_to_rtdb` 에서 prune 호출 + `test_publish_to_rtdb_invokes_prune_history_summary` 추가)
- 2026-04-14 10:45: Phase 3 완료 (설계서 최신화, black 적용, validate_project.py passed=903/failed=0/skipped=0)

---
