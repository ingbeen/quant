# Implementation Plan: 포트폴리오 정합성 가드 — 빈 value_cols 무력화 차단

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

**작성일**: 2026-05-16 10:30
**마지막 업데이트**: 2026-05-16 11:00
**관련 범위**: backtest
**관련 문서**: [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md), [tests/CLAUDE.md](../../tests/CLAUDE.md), [루트 CLAUDE.md](../../CLAUDE.md)

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

- [x] 목표 1: `_check_equity_equation`(portfolio_validation.py)에서 `value_cols`가 빈 리스트이면 내부 불변조건 위반 `RuntimeError`로 즉시 중단한다 (silent pass로 정합성 가드가 무력화되는 것을 차단).

## 2) 비목표(Non-Goals)

- 전수 감사에서 거론된 다른 항목(spread_lab_helpers lag 검증, CLAUDE.md/scripts/CLAUDE.md 문서 표현 정리)은 **본 plan 범위 밖** (사용자가 P1만 진행하기로 결정).
- 규칙 1~4 및 규칙 5의 등식 산식/판정 기준 변경 없음. 가드 추가만 수행.
- 빈 `equity_df`(행 0개) 처리 정책 변경은 범위 밖 — `value_cols`(컬럼 부재)만 대상.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

[src/qbt/backtest/portfolio_validation.py:166-173](../../src/qbt/backtest/portfolio_validation.py#L166-L173) 의 `_check_equity_equation`은 포트폴리오 백테스트 결과의 정합성 가드(규칙 5: `equity = cash + sum(자산 평가액)`)이다.

```python
value_cols = [c for c in equity_df.columns if c.endswith(ASSET_COL_SUFFIX_VALUE)]
violations: list[str] = []
for _, row in equity_df.iterrows():
    computed = float(row["cash"]) + sum(float(row[vc]) for vc in value_cols)
```

`value_cols`가 빈 리스트이면 `sum(...) = 0.0`이 되어 `computed = cash + 0.0`으로 계산된다. 자산 평가액 컬럼이 누락된 비정상 입력에서도, `cash == equity`인 행에서는 위반이 감지되지 않아 **검증 가드가 무방비로 통과**한다. 정상 흐름에서는 `portfolio_engine`이 항상 자산별 `_value` 컬럼을 생성하므로 발생 불가하나, **내부 불변조건에 대한 명시적 방어가 없다**. 정합성 가드 함수가 조용히 통과되는 것은 백테스트 결과 신뢰성에 직접 영향을 준다.

루트 CLAUDE.md "불가능 조건 처리": 내부 로직 불변조건(코드 흐름상 절대 도달 불가) 위반은 `RuntimeError`로 즉시 실패시키고, 메시지에 "내부 불변조건 위반" 접두사 + 위반 변수/값을 포함한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md): "불가능 조건 처리", "명시적 검증", "수술적 변경"
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md): portfolio_validation 5개 정합성 규칙
- [tests/CLAUDE.md](../../tests/CLAUDE.md): Given-When-Then, 예외 테스트 규칙(예외 타입 고정 + 키워드 match), 경계 조건

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `_check_equity_equation` 빈 `value_cols` 입력 → `RuntimeError("내부 불변조건 위반 ...")` 발생
- [x] 빈 `value_cols` 예외 회귀 테스트 추가 (정상 케이스 회귀 유지 + 예외 케이스 신규)
- [x] `poetry run python validate_project.py` 통과 (passed=1026, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (146 files left unchanged)
- [x] 문서 업데이트 명시: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / CLAUDE.md 변경 없음
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/portfolio_validation.py` — `_check_equity_equation` 빈 value_cols 가드 추가
- `tests/qbt/test_portfolio_validation.py` — 빈 value_cols → RuntimeError 테스트 추가 (필요 시 `import pytest` 추가)
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어/CLI 옵션 변경 없음)

### 데이터/결과 영향

- 출력 스키마 변경 없음.
- 정상 입력 동작 불변 (정상 흐름에서 빈 value_cols 발생 불가) → 기존 결과 재생성 불필요.
- 비정상 입력(자산 평가액 컬럼 전무)에 대해서만 즉시 실패로 동작 변경.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 에러 처리 정책 변경(중단 조건 추가)에 해당하므로 본 Phase를 둔다.

**작업 내용**:

- [x] `tests/qbt/test_portfolio_validation.py`의 `TestCheckEquityEquation`에 빈 `value_cols`(= `*_value` 컬럼 전무) 입력 시 `RuntimeError` 기대 테스트 추가 (레드 허용)
- [x] 예외 메시지 키워드 정책 고정: `match="내부 불변조건 위반"`
- [x] 기존 정상/위반 테스트(`test_equity_matches_equation`, `test_equity_mismatch_detected`) 회귀 유지 확인

---

### Phase 1 — 핵심 구현/수정(그린 유지)

**작업 내용**:

- [x] `portfolio_validation.py::_check_equity_equation` — `value_cols`가 빈 리스트이면 루프 진입 전 `RuntimeError("내부 불변조건 위반: ...")` 발생. 메시지에 접미사 상수와 실제 컬럼 목록 포함. 정상 경로 동작은 불변.
- [x] Phase 0 테스트 그린 전환 확인 (대상 테스트 파일 한정 pytest 실행 — 12 passed)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 문서 업데이트 확정: `README.md` 변경 없음 / `docs/COMMANDS.md` 변경 없음 / CLAUDE.md 변경 없음
- [x] `poetry run black .` 실행(자동 포맷 적용 — 146 files left unchanged)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1026, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 정합성 가드 — 빈 value_cols 무력화 차단(RuntimeError) + 테스트
2. 백테스트 / _check_equity_equation 내부 불변조건 위반 즉시 중단 추가
3. 백테스트 / 등식 검증 silent pass 차단 및 회귀 테스트 보강
4. 백테스트 / portfolio_validation 방어 강화(불가능 조건 처리 정책 적용)
5. 백테스트 / 정합성 검증 가드 무력화 방지 + 예외 케이스 테스트 추가

## 7) 리스크(Risks)

- 정합성 가드에 예외를 추가하므로, 기존 테스트 픽스처가 비정상적으로 빈 `value_cols` equity_df를 사용했다면 회귀 실패 가능 → Phase 0에서 기존 테스트 회귀 확인으로 완화. (현 `test_portfolio_validation.py`의 등식 테스트는 `qqq_value` 등 `_value` 컬럼을 포함하므로 영향 없음.)
- 실호출 경로(`validate_portfolio_result`)는 정상 PortfolioResult를 받아 항상 `_value` 컬럼이 채워지므로 동작 변화 없음.

## 8) 메모(Notes)

- 본 plan은 프로젝트 전수 감사 후속 중 사용자가 **P1(높음) 단일 항목만** 진행하기로 결정한 데 따른 것.
- 함께 거론되었던 P2(spread_lab_helpers lag 검증), P3(CLAUDE.md/scripts/CLAUDE.md 문서 표현 정리)는 본 plan에서 제외. 추후 별도 결정 시 별도 plan으로 진행.
- 스킵 없음 목표. 스킵 발생 시 Done 처리 금지.

### 진행 로그 (KST)

- 2026-05-16 10:30: 전수 감사 → 재검증 → 사용자 결정(P1만 진행) → 이전 변경 전부 원복 → P1 전용 plan 작성.
- 2026-05-16 11:00: Phase 0(테스트 선작성) → Phase 1(가드 구현, 대상 테스트 12 passed) → black(146 unchanged) → validate_project.py(passed=1026, failed=0, skipped=0) 통과. 상태 Done.
