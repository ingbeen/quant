# Implementation Plan: 프로젝트 전수 분석 기반 일괄 품질 개선

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

**작성일**: 2026-04-18 12:25
**마지막 업데이트**: 2026-04-18 12:35
**관련 범위**: qbt/backtest, live, scripts, docs, README
**관련 문서**: [CLAUDE.md](../../CLAUDE.md), [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md), [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [src/live/CLAUDE.md](../../src/live/CLAUDE.md), [docs/CLAUDE.md](../CLAUDE.md)

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

- [x] 목표 1: csv_export.py 내부 문자열 리터럴을 상수화하여 자기 정의 상수 활용 + qbt 상수 재사용 원칙 준수
- [x] 목표 2: qbt/live 파일 docstring·주석의 과거 이력(“기존/변경”) 및 실제 처리 순서와의 불일치 제거
- [x] 목표 3: live의 `_format_pct` 를 `ROUND_PERCENT` 기반으로 통일, cli.py 의 함수 내부 `import shutil` 을 top-level 로 이동
- [x] 목표 4: README.md 내 전략명 직접 나열 제거(“코드 참조” 스타일로 통일)
- [x] 목표 5: `validate_project.py` 통과 유지 (기능/동작 변경 없음)

## 2) 비목표(Non-Goals)

- 비즈니스 로직·수식·신호 정의·체결 타이밍 등 **실행 결과가 달라지는 변경은 하지 않는다**.
- 새 테스트 추가는 하지 않는다(동작 동등성을 유지하는 리팩토링/주석 정리만 수행).
- Agent 분석에서 `의도된 예외` 또는 `사실 오류` 로 재검증된 항목은 손대지 않는다.
  - notifier.py / rtdb_gateway.py 의 `logger.error/warning` 사용(알림 채널 예외로 명시됨)
  - live `live_csv_path` 의 ticker: str (식별자, 경로 아님)
  - cli.py:310-312 “이전 연도 archive” 표현(관계어, 변경 이력 아님)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 전수 분석 결과 `의도치 않은 규칙 위반` 이 확정되어, 문서 내구성 / 상수 중복 / 과거 이력 주석 / docstring 실제 코드 불일치가 남아 있다.
- 특히 [src/live/daily_runner.py:2-5](../../src/live/daily_runner.py) 파일 docstring 은 실제 처리 순서(fill_dismiss / balance_adjust / **model_sync** 포함) 를 반영하지 못하고 오래된 상태로 남아 있어, 문서→코드 독해를 오도할 위험이 높다.
- [src/qbt/backtest/csv_export.py](../../src/qbt/backtest/csv_export.py) 는 `OHLC_CHANGE_PCT_COLUMNS` / `BUFFER_BAND_COLUMNS` 상수를 선언해 두고도 본문에서 리터럴을 직접 사용해 자기 모순 상태이다.
- [README.md](../../README.md) 는 전략명 나열(59,61 줄) 과 “README 에 직접 명시하지 않습니다”(343 줄) 가 공존해 자기 모순이며, `portfolio_configs` / `buffer_zone.CONFIGS` 변경 시 깨지기 쉽다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [CLAUDE.md](../../CLAUDE.md)
- [src/qbt/CLAUDE.md](../../src/qbt/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [src/live/CLAUDE.md](../../src/live/CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/CLAUDE.md](../CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] csv_export.py 리팩토링: `OHLC_CHANGE_PCT_COLUMNS` / `BUFFER_BAND_COLUMNS` 및 신규 개별 상수(`COL_OPEN_PCT` 등)가 내부 사용부에 실제 적용
- [x] `BUFFER_BAND_COLUMNS` 가 `qbt.backtest.constants` 의 `COL_UPPER_BAND` / `COL_LOWER_BAND` 기반으로 재정의
- [x] runners.py 파일 docstring 에서 "기존/변경" 과거 이력 제거 (현재 구조만 설명)
- [x] walkforward.py 의 "기존 동작" → "기본 동작" 으로 표현 교체
- [x] daily_runner.py 파일 docstring 이 실제 `run_daily` 처리 순서(fill_dismiss / balance_adjust / **model_sync** 포함) 와 일치
- [x] notifier.py `_format_pct` 가 `ROUND_PERCENT` 를 사용하도록 교체
- [x] cli.py `import shutil` 을 module top-level 로 이동
- [x] README.md 의 전략명 직접 나열 제거 (“코드 참조” 스타일로 통일)
- [x] `poetry run python validate_project.py` 통과 (passed=1019, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (146 files left unchanged)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/csv_export.py` — 신규 상수 추가, 리터럴 사용부 교체
- `src/qbt/backtest/runners.py` — 파일 docstring 의 과거 이력 제거
- `src/qbt/backtest/walkforward.py` — "기존 동작" 표현 교체
- `src/live/daily_runner.py` — 파일 docstring 의 처리 순서 최신화
- `src/live/notifier.py` — `_format_pct` 에서 `ROUND_PERCENT` 사용
- `src/live/cli.py` — `_cmd_reset` 내부 `import shutil` 을 top-level 로 이동
- `README.md` — 전략명 예시 제거, `--strategy <strategy_name>` 스타일로 통일
- `README.md`: **변경 있음**

### 데이터/결과 영향

- 출력 스키마 변경 없음.
- 기능/산식/로직 변경 없음 → 결과 CSV / JSON 변화 없음.
- `_format_pct` 는 `ROUND_PERCENT = 2` 이므로 현재 출력과 완전 동일.

## 6) 단계별 계획(Phases)

### Phase 1 — csv_export 상수화 (qbt 내부, 동작 불변)

**작업 내용**:

- [x] `src/qbt/backtest/csv_export.py` 에 `COL_OPEN_PCT`, `COL_HIGH_PCT`, `COL_LOW_PCT`, `COL_CLOSE_PCT` 개별 상수 추가 (값: 기존 리터럴 동일)
- [x] `OHLC_CHANGE_PCT_COLUMNS` 를 신규 개별 상수 튜플로 재정의
- [x] `qbt.backtest.constants.COL_UPPER_BAND` / `COL_LOWER_BAND` 를 import 하여 `BUFFER_BAND_COLUMNS = (COL_UPPER_BAND, COL_LOWER_BAND)` 로 재정의
- [x] `add_ohlc_change_pct` 내 리터럴(131~134) 을 신규 상수로 교체
- [x] `add_buffer_zone_bands` 내 리터럴(167~168) 을 `COL_UPPER_BAND` / `COL_LOWER_BAND` 로 교체
- [x] csv_export.py `add_ohlc_change_pct` 빈 DataFrame 분기(126~128) 도 상수 튜플 반복문이 그대로 동작하는지 확인

---

### Phase 2 — qbt 주석/docstring 정리 (동작 불변)

**작업 내용**:

- [x] `src/qbt/backtest/runners.py` 파일 docstring 에서 "기존/변경" 과거 이력 제거. 현재 구조만 한 단락으로 요약
- [x] `src/qbt/backtest/walkforward.py` docstring 의 `(기존 동작)` → `(기본 동작)` 2 곳 교체
- [x] `select_best_calmar_params` 내부 주석 "필터링 전 1위 기록 (탈락 로그용)" 는 현재 코드 설명이므로 유지 (과거 이력 아님)

---

### Phase 3 — live 주석/코드 정리 (동작 불변)

**작업 내용**:

- [x] `src/live/daily_runner.py` 파일 docstring(라인 2~5) 의 처리 순서를 실제 `run_daily` 구현 순서와 일치시킨다 (fills → fill_dismiss → balance_adjust → **model_sync** → 전일 pending 체결 → equity → 시그널/리밸런싱 → 익일 pending → drift)
- [x] `src/live/notifier.py` 의 `_format_pct` 를 `f"{value * 100:+.{ROUND_PERCENT}f}%"` 형태로 교체, `from qbt.backtest.constants import ROUND_PERCENT` import 추가
- [x] `src/live/cli.py` `_cmd_reset` 함수 내부 `import shutil` 제거, 파일 상단 표준 라이브러리 블록에 `import shutil` 추가
- [x] `_cmd_reset` docstring 의 "9 단계 순서" 설명은 현재 코드 흐름과 일치하므로 그대로 유지

---

### Phase 4 — README 정리

**작업 내용**:

- [x] `README.md` line 59~61 의 전략명 예시 제거 → `--strategy <strategy_name>` 형식 + "전략명은 `src/qbt/backtest/strategies/buffer_zone.py::CONFIGS` / `src/qbt/backtest/strategies/buy_and_hold.py::CONFIGS` 참고" 로 통일
- [x] `README.md` line 80 의 `all / buffer_zone_tqqq / buffer_zone_qqq` 예시도 동일 원칙으로 추상화
- [x] 343 줄의 선언("실험 목록은 변경 빈도가 높아 ...") 과 상단 설명이 서로 일관되게 남는지 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 완료 확인 (README.md 포함)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1019, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 공통 / csv_export 상수화 + 문서·주석 내구성 정리 (전수 분석 후속)
2. 공통 / qbt·live docstring 실측 일치화 + 과거 이력 제거
3. 공통 / 규칙 위반 일괄 정리 — 상수 중복 / 과거 이력 / README 나열 제거
4. 공통 / 문서·주석 내구성 강화 + 표현 일관화 (동작 불변 리팩토링)
5. 공통 / 프로젝트 전수 분석 반영 — 상수/문서/주석 정리

## 7) 리스크(Risks)

- 리스크: csv_export.py 내부 리터럴 교체 시 대시보드/테스트가 컬럼명을 문자열로 직접 기대하는 구간이 있을 수 있음 → 개별 상수 값이 기존 리터럴과 100% 동일하게 유지되므로 호환성 유지. `validate_project.py` 로 즉시 검증.
- 리스크: daily_runner.py 파일 docstring 수정 시 실제 코드 순서를 잘못 요약할 위험 → `run_daily` 함수 docstring(이미 최신) 을 SoT 로 하여 정렬한다.
- 리스크: `import shutil` 이동이 순환 참조를 유발 가능성 → shutil 은 표준 라이브러리, 순환 없음. 위험 없음.

## 8) 메모(Notes)

- 본 plan 은 "전수 분석 → 재검증 → 사용자 승인(모든 추천안)" 단계를 거친 뒤 일괄 실행하는 품질 개선 배치이다.
- Agent 분석에서 부정확했던 항목(live 경로 문자열/Path 혼용, notifier logger 원칙 차이, runners.py deferred 주석 등) 은 재검증 결과 제외됨.
- live CLAUDE.md §QBT 본체 수정 원칙: 본 plan 은 "live 작업 중 QBT 본체 수정" 이 아닌, **프로젝트 전체 품질 개선의 일환** 이며 사용자가 전체 항목 추천안을 명시 승인하였으므로 qbt 본체 주석/상수 정리가 허용된다.

### 진행 로그 (KST)

- 2026-04-18 12:25: plan 초안 작성.
- 2026-04-18 12:30: Phase 1~4 구현 완료 (csv_export 상수화, runners/walkforward 주석 정리, daily_runner docstring 최신화, notifier `_format_pct` 교체, cli.py `import shutil` 이동, README 전략명 나열 제거).
- 2026-04-18 12:35: `poetry run black .` (146 files left unchanged) + `poetry run python validate_project.py` (passed=1019, failed=0, skipped=0) 통과. 상태 Done 전환.

---
