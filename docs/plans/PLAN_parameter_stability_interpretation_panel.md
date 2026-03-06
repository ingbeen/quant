# Implementation Plan: 파라미터 안정성 대시보드 해석 패널 추가

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

**작성일**: 2026-03-06 12:00
**마지막 업데이트**: 2026-03-06 12:00
**관련 범위**: scripts/backtest
**관련 문서**: `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] 각 섹션(A, B, C, D) 차트/테이블 아래에 3가지 해석 패널 추가 (용어 설명, 해석 방법, 현재 결과 해석)
- [x] 지표를 모르는 사용자도 결과를 이해하고 판단할 수 있도록 안내

## 2) 비목표(Non-Goals)

- 판정 로직(Pass/Fail/Warn 계산) 변경하지 않음
- 차트/히트맵/바 차트 변경하지 않음
- 70% 임계선 변경하지 않음
- 종합 판정 색상 및 텍스트 변경하지 않음
- 비즈니스 로직(`src/qbt/backtest/parameter_stability.py`) 변경하지 않음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 1단계 검증 대시보드의 판정 로직은 현재 상태를 유지하되, 사용자가 지표의 의미와 결과 해석을 이해할 수 있도록 해석 패널이 필요
- 각 섹션에 용어 설명, 해석 방법, 현재 데이터 기반 구체적 해석을 제공

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`: CLI 스크립트 계층 규칙, Streamlit 앱 규칙
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙

## 4) 완료 조건(Definition of Done)

- [x] 섹션 A~D 각각에 해석 패널 3가지 추가 (용어 설명, 해석 방법, 현재 결과 해석)
- [x] 레이아웃 순서: 차트 → 현재 결과 해석(st.info) → 용어 설명(expander) → 해석 방법(expander)
- [x] 기존 판정 로직/차트 변경 없음 확인
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_parameter_stability.py`: 해석 패널 함수 추가 및 렌더 함수 내 호출 삽입

### 데이터/결과 영향

- 없음. 순수 UI 텍스트 패널 추가만 해당

## 6) 단계별 계획(Phases)

Phase 0 불필요: 인바리언트/정책 변경 없음, 비즈니스 로직 변경 없음

### Phase 1 — 해석 패널 구현 (그린 유지)

**작업 내용**:

- [x] 섹션 A 해석 패널 함수 작성 및 `_render_calmar_histogram` 내 호출 삽입
- [x] 섹션 B 해석 패널 함수 작성 및 `_render_heatmaps` 내 호출 삽입
- [x] 섹션 C 해석 패널 함수 작성 및 `_render_adjacent_comparison` 내 호출 삽입
- [x] 섹션 D 해석 패널 함수 작성 및 `_render_stability_summary` 내 호출 삽입

---

### Phase 2 (마지막) — 포맷팅 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=465, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 파라미터 안정성 대시보드에 해석 패널 추가 (A~D 섹션)
2. 백테스트 / 파라미터 안정성 분석 결과 해석 가이드 패널 구현
3. 백테스트 / 대시보드 UX 개선 - 지표 해석 패널 추가
4. 백테스트 / 파라미터 안정성 대시보드 해석 텍스트 및 expander 추가
5. 백테스트 / 파라미터 안정성 1단계 검증 해석 패널 구현

## 7) 리스크(Risks)

- 낮음: 순수 UI 텍스트 추가이므로 기존 기능에 영향 없음
- Streamlit expander/info 사용법 확인 필요 (width 파라미터 관련 규칙)

## 8) 메모(Notes)

- 해석 패널 텍스트는 프롬프트에서 제공된 내용을 그대로 사용
- 레이아웃 순서: 차트 바로 아래에 현재 결과 해석(항상 표시), 그 아래에 용어 설명/해석 방법(접힘)

### 진행 로그 (KST)

- 2026-03-06 12:00: 계획서 작성 완료, Phase 1 시작
- 2026-03-06 12:30: Phase 1 완료 (A~D 섹션 해석 패널 추가)
- 2026-03-06 12:30: Phase 2 완료 (Black + validate_project.py passed=465, failed=0, skipped=0)

---
