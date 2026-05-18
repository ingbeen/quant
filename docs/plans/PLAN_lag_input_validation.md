# Implementation Plan: spread_lab lag 입력 검증 — 매핑 외 lag silent skip 차단

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

**작성일**: 2026-05-16 11:20
**마지막 업데이트**: 2026-05-16 11:40
**관련 범위**: tqqq
**관련 문서**: [src/qbt/tqqq/CLAUDE.md](../../src/qbt/tqqq/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: `add_rate_change_lags`(spread_lab_helpers.py)에서 `lag_list`에 `lag_col_map`에 없는 값이 포함되면 `ValueError`로 즉시 중단한다 (매핑 외 lag 값이 조용히 누락되는 silent skip 차단).

## 2) 비목표(Non-Goals)

- 전수 감사에서 거론된 P3 항목(CLAUDE.md/scripts/CLAUDE.md 문서 표현 정리)은 본 plan 범위 밖 (사용자가 P2만 진행하기로 결정).
- `lag_col_map` 지원 범위 확장(lag 3, 4 등 추가)은 범위 밖 — YAGNI. 현재 지원 값(1, 2)에 대한 입력 검증만 추가.
- `prepare_monthly_data` 등 동일 모듈의 다른 함수 변경 없음.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

[src/qbt/tqqq/spread_lab_helpers.py:121-125](../../src/qbt/tqqq/spread_lab_helpers.py#L121-L125) 의 `add_rate_change_lags`:

```python
lag_col_map = {1: COL_DR_LAG1, 2: COL_DR_LAG2}
for lag in lag_list:
    col_name = lag_col_map.get(lag)
    if col_name:
        result[col_name] = result[COL_DR_M].shift(lag)
```

`lag_list`에 매핑(`{1, 2}`)에 없는 값(예: 3)이 포함되면 `lag_col_map.get(lag)`가 `None`을 반환하고 `if col_name:` 분기가 **조용히 skip**한다. 결과 컬럼이 누락되어도 예외/경고가 없다.

현재 유일한 호출처는 [scripts/tqqq/spread_lab/app_rate_spread_lab.py:1645](../../scripts/tqqq/spread_lab/app_rate_spread_lab.py#L1645) 의 `add_rate_change_lags(monthly_df)` 로, `lag_list` 미지정 → 기본값 `[1, 2]`만 사용하므로 **현재 실발생은 없다**. 그러나 `lag_list`가 공개 파라미터로 노출되어 있어, 향후 확장/오용 시 결과가 비결정적으로 누락된다.

루트 CLAUDE.md "불가능 조건 처리" 구분 기준: **입력 파라미터 검증(외부에서 잘못된 값 전달 가능) → ValueError**. `lag_list`는 외부에서 전달되는 입력 파라미터이므로 `ValueError`가 적합하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md): "불가능 조건 처리", "명시적 검증", "수술적 변경", 문서화(docstring 코드 일치)
- [src/qbt/tqqq/CLAUDE.md](../../src/qbt/tqqq/CLAUDE.md): spread_lab_helpers 역할(`add_rate_change_lags`: 금리 변화 lag 컬럼 생성)
- [tests/CLAUDE.md](../../tests/CLAUDE.md): Given-When-Then, 예외 테스트 규칙(예외 타입 고정 + 키워드 match), 경계 조건

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `add_rate_change_lags` 매핑 외 lag 값 입력 → `ValueError` 발생
- [x] 매핑 외 lag 예외 회귀 테스트 추가 (정상 케이스 회귀 유지 + 예외 케이스 신규)
- [x] `add_rate_change_lags` docstring의 `Raises`/`lag_list` 설명이 실제 동작과 일치
- [x] `poetry run python validate_project.py` 통과 (passed=1027, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (1 file reformatted, 145 unchanged)
- [x] 문서 업데이트 명시: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / CLAUDE.md 변경 없음
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/spread_lab_helpers.py` — `add_rate_change_lags` 매핑 외 lag 입력 검증 + docstring 갱신
- `tests/qbt/test_tqqq_spread_lab_helpers.py` — 매핑 외 lag → ValueError 테스트 추가
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어/CLI 옵션 변경 없음)

### 데이터/결과 영향

- 출력 스키마 변경 없음.
- 정상 입력(기본값 `[1,2]` 또는 명시 `[1,2]`) 동작 불변 → 기존 결과 재생성 불필요.
- 비정상 입력(매핑 외 lag 값 포함)에 대해서만 즉시 실패로 동작 변경.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 에러 처리 정책 변경(중단 조건 추가)에 해당하므로 본 Phase를 둔다.

**작업 내용**:

- [x] `tests/qbt/test_tqqq_spread_lab_helpers.py`의 `TestAddRateChangeLags`에 매핑 외 lag 값(예: `[1, 3]`) 입력 시 `ValueError` 기대 테스트 추가 (레드 허용)
- [x] 예외 메시지 키워드 정책 고정: `match="lag"` (핵심 키워드 부분 매칭)
- [x] 기존 정상 테스트(`test_lag_columns_created_correctly`, `test_original_dataframe_not_modified`) 회귀 유지 확인

---

### Phase 1 — 핵심 구현/수정(그린 유지)

**작업 내용**:

- [x] `spread_lab_helpers.py::add_rate_change_lags` — `lag_list` 내 값 중 `lag_col_map`에 없는 값이 있으면 `ValueError`로 즉시 실패. `lag_col_map`을 SSoT로 사용하여 검증 후, 정상 경로는 직접 인덱싱(`lag_col_map[lag]`)으로 컬럼 생성.
- [x] docstring 갱신: `lag_list` 설명에 지원 값(1, 2) 명시, `Raises`에 매핑 외 lag 케이스 추가 (코드-주석 일치)
- [x] Phase 0 테스트 그린 전환 확인 (대상 테스트 파일 한정 pytest 실행 — 6 passed)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 문서 업데이트 확정: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / CLAUDE.md 변경 없음
- [x] `poetry run black .` 실행(자동 포맷 적용 — 1 file reformatted, 145 unchanged)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1027, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / spread_lab lag 입력 검증 — 매핑 외 lag silent skip 차단(ValueError) + 테스트
2. TQQQ시뮬레이션 / add_rate_change_lags 외부 입력 검증 추가 및 docstring 정합화
3. TQQQ시뮬레이션 / lag_list silent skip 차단(불가능 조건 처리 정책 적용)
4. TQQQ시뮬레이션 / 금리 변화 lag 생성 입력 검증 강화 + 회귀 테스트
5. TQQQ시뮬레이션 / spread_lab_helpers 방어 강화 + 예외 케이스 테스트 추가

## 7) 리스크(Risks)

- `add_rate_change_lags`에 입력 검증을 추가하므로, 비기본 `lag_list`를 쓰는 숨은 호출처가 있으면 실패 → grep으로 호출처 전수 확인 완료(`app_rate_spread_lab.py:1645` 단일, `lag_list` 미지정 = 기본값 `[1,2]`)로 완화.
- 기존 테스트는 `lag_list=[1, 2]`만 사용하므로 회귀 영향 없음.

## 8) 메모(Notes)

- 본 plan은 프로젝트 전수 감사 후속 중 사용자가 **P2 단일 항목만** 진행하기로 결정한 데 따른 것.
- P1(포트폴리오 정합성 가드)은 [PLAN_equity_equation_guard.md](PLAN_equity_equation_guard.md)로 완료(✅ Done).
- P3(CLAUDE.md/scripts/CLAUDE.md 문서 표현 정리)는 본 plan 범위 밖. 추후 결정 시 별도 plan으로 진행.
- 스킵 없음 목표. 스킵 발생 시 Done 처리 금지.

### 진행 로그 (KST)

- 2026-05-16 11:20: 전수 감사 → 재검증 → 사용자 결정(P2만 진행) → P2 전용 plan 작성.
- 2026-05-16 11:40: Phase 0(테스트 선작성) → Phase 1(검증 구현 + docstring 갱신, 대상 테스트 6 passed) → black(1 reformatted) → validate_project.py(passed=1027, failed=0, skipped=0) 통과. 상태 Done.
