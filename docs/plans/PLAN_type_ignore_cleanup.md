# Implementation Plan: type: ignore 정리

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

**작성일**: 2026-03-13 15:00
**마지막 업데이트**: 2026-03-13 15:30
**관련 범위**: backtest, tqqq, scripts, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 목표 1: 해결 가능한 `# type: ignore` 33개를 `cast()`, 타입 명시, 또는 불필요 주석 제거로 정리
- [x] 목표 2: 해결 불가능한 10개는 유지 (외부 라이브러리 한계, 테스트 의도)
- [x] 목표 3: 기존 런타임 동작에 영향 없음 보장

## 2) 비목표(Non-Goals)

- 런타임 로직 변경 (cast()는 런타임 no-op)
- pyrightconfig.json 설정 변경
- 새 테스트 추가 (타입 어노테이션만 변경)
- 해결 불가능한 type: ignore 제거 시도

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 프로젝트 전체에 43개의 `# type: ignore` 존재
- 33개는 `cast()` 또는 타입 명시로 근본 해결 가능
- 7개는 pyrightconfig.json에서 이미 해당 규칙이 "none"으로 설정되어 불필요
- 불필요한 type: ignore는 코드 가독성을 저하시키고 실제 타입 문제를 숨길 수 있음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] 해결 가능한 type: ignore 33개 정리 완료 (실제 31개 해결 + 2개는 이미 타입 정합하여 cast 불필요)
- [x] 해결 불가능한 10개 유지 확인
- [x] `poetry run python validate_project.py` 통과 (passed=334, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/parameter_stability.py` (1개 수정)
- `src/qbt/backtest/walkforward.py` (5개 수정)
- `scripts/backtest/app_single_backtest.py` (20개 수정)
- `scripts/backtest/app_parameter_stability.py` (2개 수정)
- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` (8개 수정)
- `tests/test_backtest_walkforward.py` (7개 제거)

### 데이터/결과 영향

- 없음 (`cast()`는 런타임 no-op, 타입 어노테이션만 변경)

## 6) 단계별 계획(Phases)

### Phase 1 — src/qbt/ 비즈니스 로직 (strict mode, 최고 우선순위)

**작업 내용**:

- [x] `parameter_stability.py:98` - `pd.Series` → `pd.Series[float]` + `from __future__ import annotations`
- [x] `walkforward.py:510` - `cast(list[WfoWindowResultDict], ...)` 적용
- [x] `walkforward.py:589, 621, 622, 626` - `cast(float, ...)` 적용 (4개)

---

### Phase 2 — scripts/ CLI/앱 계층

**작업 내용**:

- [x] `app_single_backtest.py:121` - `cast(dict[str, Any], json.load(f))` 적용
- [x] `app_single_backtest.py:222-232` - itertuples 속성 `cast(float, ...)` (6개)
- [x] `app_single_backtest.py:320, 331` - itertuples 속성 `cast(date, ...)` (2개)
- [x] `app_single_backtest.py:332` - itertuples 속성 `cast(float, ...)` (1개)
- [x] `app_single_backtest.py:377, 386` - itertuples 속성 `cast(float, ...)` (2개)
- [x] `app_single_backtest.py:727, 850` - 불필요한 `[type-arg]` ignore 제거 (pyrightconfig에서 이미 suppress)
- [x] `app_single_backtest.py:741` - `cast(int, row.name)` 적용
- [x] `app_parameter_stability.py:107-108` - `cast()` 적용 (2개)
- [x] `app_rate_spread_lab.py:627, 933, 981-985` - `cast()` 적용 (6개) + `950, 1293` - 이미 타입 정합하여 타입 명시만 (2개)

---

### Phase 3 — tests/ 불필요한 ignore 제거

**작업 내용**:

- [x] `test_backtest_walkforward.py:517, 602, 701, 798, 843, 954, 1009` - 불필요한 `[arg-type]` ignore 제거 (7개, pyrightconfig에서 `reportArgumentType: "none"`)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트 / type: ignore 33개 정리 (cast 도입 + 불필요 주석 제거)
2. 프로젝트 / 타입 안정성 개선 - cast() 적용 및 불필요한 type: ignore 제거
3. 프로젝트 / PyRight strict 모드 호환성 향상 (type: ignore → cast 전환)
4. 프로젝트 / 타입 어노테이션 리팩토링 (동작 동일, type: ignore 최소화)
5. 프로젝트 / type: ignore 정리 + 타입 명시성 강화

## 7) 리스크(Risks)

- 리스크 1: cast() 추가 시 import 누락 → Validation에서 즉시 감지 가능
- 리스크 2: 불필요한 type: ignore 제거 시 실제로 필요했던 경우 → Validation에서 즉시 감지 가능
- 완화책: 모든 변경은 런타임 동작 무관, Validation 실패 시 즉시 롤백

## 8) 메모(Notes)

### 해결 불가능한 type: ignore 10개 (유지)

| 파일 | 규칙 | 사유 |
|------|------|------|
| `app_single_backtest.py:22` | `import-untyped` | lightweight_charts_v5 타입 스텁 미제공 |
| `app_single_backtest.py:795, 918` | `call-overload` | Streamlit st.dataframe 타입 스텁 한계 |
| `app_single_backtest.py:619-621, 626, 821` | `arg-type` | Plotly go.Heatmap/go.Bar 타입 스텁 불완전 |
| `test_buffer_zone.py:61` | `misc` | frozen dataclass 의도적 할당 (예외 테스트) |
| `test_backtest_walkforward.py:1037` | `attr-defined` | importlib 동적 모듈 로딩 |

### 진행 로그 (KST)

- 2026-03-13 15:00: 계획서 작성 완료, 구현 시작
