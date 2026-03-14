# Implementation Plan: 고원 임계값 90% → 80% 변경

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

**작성일**: 2026-03-14 15:40
**마지막 업데이트**: 2026-03-14 15:45
**관련 범위**: backtest, scripts
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

- [x] 고원 탐지 기본 임계값을 90% → 80%로 변경 (전체 파라미터 공통)
- [x] 앱 annotation 레이블을 "80%"로 갱신

## 2) 비목표(Non-Goals)

- 고원 탐지 알고리즘 변경
- 파라미터별 개별 임계값 적용

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- overfitting_analysis_report.md(§18)에서 sell_buffer 고원은 0.03~0.07로 식별됨
- 코드의 90% 임계값은 sell_buffer에서 0.05 단일 포인트만 잡아 보고서와 불일치
- 80%로 낮추면 보고서의 고원 범위에 근접하며, 다른 파라미터도 더 넓은 고원 표시

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `find_plateau_range()` 기본 threshold_ratio 0.8으로 변경
- [x] `find_plateau_range_with_trade_filter()` 기본 threshold_ratio 0.8으로 변경
- [x] 앱의 annotation 레이블 "80%"로 갱신
- [x] 기존 테스트 통과 (명시적 threshold_ratio 사용 테스트는 변경 불필요)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/parameter_stability.py`: 기본값 0.9 → 0.8
- `scripts/backtest/app_parameter_stability.py`: 명시적 0.9 제거 + annotation "80%"

### 데이터/결과 영향

- 기존 CSV/JSON 변경 없음
- 시각화에서 모든 파라미터의 고원 범위가 넓어짐

## 6) 단계별 계획(Phases)

### Phase 1 — 기본값 변경 + 앱 갱신 + 최종 검증

**작업 내용**:

- [x] `parameter_stability.py`: 두 함수의 `threshold_ratio` 기본값 0.9 → 0.8
- [x] `app_parameter_stability.py`: 명시적 `threshold_ratio=0.9` 제거 (기본값 사용) + annotation "90%" → "80%"
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=328, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 고원 탐지 임계값 90% → 80% 변경 (보고서 §18 일치)
2. 백테스트 / 파라미터 고원 threshold 0.8로 조정
3. 백테스트 / 고원 구간 기준 완화 (threshold_ratio 0.9 → 0.8)
4. 백테스트 / 고원 분석 임계값을 보고서 기준에 맞춰 80%로 변경
5. 백테스트 / 고원 시각화 threshold 0.8 적용 및 annotation 갱신

## 7) 리스크(Risks)

- 리스크 낮음: 기본값 변경이며, 명시적 threshold를 전달하는 테스트는 영향 없음

## 8) 메모(Notes)

- 근거: overfitting_analysis_report.md §18의 수동 고원 분석 범위와 코드 일치시키기 위함

### 진행 로그 (KST)

- 2026-03-14 15:40: 계획서 작성 및 구현 시작
- 2026-03-14 15:45: 전체 구현 완료 (passed=328, failed=0, skipped=0)
