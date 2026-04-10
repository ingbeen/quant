# Implementation Plan: csv_export ↔ analysis runtime import 근본 해결

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

**작성일**: 2026-04-10 10:55
**마지막 업데이트**: 2026-04-10 11:05
**관련 범위**: backtest, tests
**관련 문서**: 루트 CLAUDE.md, src/qbt/backtest/CLAUDE.md, tests/CLAUDE.md

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

- [x] `src/qbt/backtest/analysis.py`의 함수 내부 runtime import (`from qbt.backtest.csv_export import add_holding_days`)를 제거하고 top-level import로 정리한다.
- [x] 의존 방향을 명확히 한다: `csv_export`는 `analysis`를 import하지 않는 단방향 의존을 보장한다 (`analysis` → `csv_export.add_holding_days` 단방향 사용).
- [x] 기존 테스트가 모두 통과하고, 의존 방향 회귀 방지 테스트가 추가된다.

## 2) 비목표(Non-Goals)

- `add_holding_days` 함수의 동작 변경 없음 (시그니처/반환값/계산식 불변).
- `prepare_trades_for_csv` 등 csv_export의 다른 함수 동작 변경 없음.
- 다른 모듈의 runtime import는 본 plan 범위 밖 (조사 결과 src/qbt 내 유일한 사례).

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `src/qbt/backtest/analysis.py:326`에서 `calculate_regime_summaries` 함수 내부에 `from qbt.backtest.csv_export import add_holding_days`를 runtime import로 수행 중. 이는 src/qbt 전체에서 유일한 함수 내 import 사례이다 (tests/는 픽스처 패치 사유로 의도된 패턴이라 제외).
- 해당 runtime import가 도입된 정확한 시점/사유는 코드/문서에 기록되어 있지 않으나, "순환 의존 방지"를 의도한 방어적 선택으로 보인다.
- 그러나 실제 import 그래프 확인 결과:
  - `analysis.py` top-level: `qbt.backtest.constants`, `qbt.backtest.types`, `qbt.common_constants`, `qbt.utils`만 import
  - `csv_export.py` top-level: `qbt.backtest.constants`, `qbt.common_constants`만 import
  - **두 모듈 사이에 순환 가능 경로가 존재하지 않는다.**
- runtime import는 (1) 가독성 저하, (2) 정적 분석 오작동 여지, (3) "왜 여기서만 함수 내부 import?"라는 인지 부담을 만든다. 근본 해결이 가능하므로 정리한다.

### 의존 방향 결정

저장 계층(`csv_export`)이 계산 계층(`analysis`)에 의존하는 방향이 자연스럽다. 하지만 현재 `add_holding_days`는 csv_export에 정의되어 있고 csv_export 내부의 `prepare_trades_for_csv`도 이 함수를 사용한다. 단순히 import 위치만 top-level로 옮기면 된다 — `analysis.py`가 `csv_export.add_holding_days`를 top-level import하고, `csv_export`가 `analysis`를 import하지 않으면 순환은 발생하지 않는다.

→ 따라서 본 plan은 **함수 위치 이동 없이 import 위치만 정리**하는 최소 변경 방식으로 진행한다. 이렇게 하면 `csv_export.prepare_trades_for_csv`의 동작이나 의존성도 일체 변하지 않는다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `src/qbt/backtest/analysis.py`에 `add_holding_days` runtime import가 더 이상 존재하지 않으며, top-level import로 변경되었다.
- [x] `src/qbt/backtest/analysis.py` 내부에 `from qbt.backtest.<x> import` 형태의 함수 내부 import가 0건이다.
- [x] `src/qbt/backtest/csv_export.py`는 여전히 `analysis`를 import하지 않는다 (단방향 의존 보장).
- [x] 의존 방향 회귀 방지 테스트 2건 추가 (`test_analysis_module_has_no_runtime_imports_to_csv_export`, `test_csv_export_does_not_depend_on_analysis`)
- [x] `poetry run python validate_project.py` 통과 (passed=503, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 도메인 CLAUDE.md 업데이트 — runtime import 관련 표현이 없어 추가 변경 불필요
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py` — runtime import 제거, top-level import 추가
- `tests/test_analysis.py` — 의존 방향 회귀 방지 테스트 추가
- `src/qbt/backtest/CLAUDE.md` — `analysis.calculate_regime_summaries` 항목에서 "csv_export.add_holding_days를 runtime import" 표현 제거 또는 수정
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 스키마 변경 없음.
- 정상 입력/결과 동일 (import 위치만 이동).

## 6) 단계별 계획(Phases)

### Phase 0 — 의존 방향 회귀 방지 테스트 작성 (레드)

**작업 내용**:

- [x] `tests/test_analysis.py`에 다음 회귀 테스트 추가:
  - `test_analysis_module_has_no_runtime_imports_to_csv_export` — `inspect.getsource(calculate_regime_summaries)`에 `import` 키워드를 포함한 라인이 함수 내부에 없는지 검증
  - `test_csv_export_does_not_depend_on_analysis` — `qbt.backtest.csv_export` 모듈을 import한 뒤 `csv_export.__dict__`에 `analysis` 모듈 또는 `calculate_summary` 등의 심볼이 포함되지 않음을 검증 (역방향 의존 부재 보장)
- [x] 새 테스트는 의도적으로 실패(레드) 상태로 둘 수 있다 (validate는 마지막 Phase에서만 실행).

---

### Phase 1 — analysis.py runtime import 제거 (그린 전환)

**작업 내용**:

- [x] `src/qbt/backtest/analysis.py` top-level에 `from qbt.backtest.csv_export import add_holding_days` 추가
- [x] `calculate_regime_summaries` 함수 내부의 runtime import 라인 제거
- [x] 상단 주석 정리 (필요 시 "csv_export 의존 사유" 한 줄 명시)

---

### Phase 2 — 도메인 문서 정리

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`의 `analysis.calculate_regime_summaries` 설명을 확인 — runtime import 관련 표현이 없으므로 추가 변경 불필요
- [x] `analysis ↔ csv_export` 의존 방향이 단방향(`csv_export` → `analysis` 사용 안 함, `analysis` → `csv_export.add_holding_days` 사용)임을 회귀 테스트로 고정 (Phase 0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 확인 (README.md 변경 없음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=503, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / analysis.py runtime import 제거 (csv_export.add_holding_days top-level화)
2. 백테스트 / analysis ↔ csv_export 의존 방향 정리 + 회귀 방지 테스트
3. 백테스트 / 함수 내부 import 제거하여 분석/저장 계층 분리 명확화
4. 백테스트 / 단방향 의존 보장 (analysis → csv_export, 역방향 차단)
5. 백테스트 / runtime import 정리 + 도메인 문서 동기화

## 7) 리스크(Risks)

- 만약 `csv_export.py`의 향후 변경이 `analysis`에 의존하게 되면 순환이 발생할 수 있음 → 회귀 방지 테스트로 차단.
- top-level import 변경으로 `analysis` 모듈 import 시점에 `csv_export`가 함께 로드되지만, 두 모듈 모두 가벼우므로 성능 영향 없음.

## 8) 메모(Notes)

- src/qbt 내 다른 함수 내부 import는 조사 결과 발견되지 않음 (테스트 파일은 픽스처 패치 사유로 의도된 패턴이며 제외).
- `add_holding_days`의 함수 위치 이동(예: csv_export → analysis)은 단순 import 정리로 충분히 해결되므로 본 plan에서는 수행하지 않는다 (YAGNI).

### 진행 로그 (KST)

- 2026-04-10 10:55: Plan 작성
- 2026-04-10 11:00: Phase 0 회귀 테스트 2건 추가 + Phase 1 import 정리 완료
- 2026-04-10 11:03: Ruff B011 (assert False) 위반 1건 발견 → 리스트 컴프리헨션으로 교체
- 2026-04-10 11:05: 마지막 Phase 완료 — black + validate_project 통과 (passed=503, failed=0, skipped=0)

---
