# Implementation Plan: [작업명/기능명]

**상태**: 🟡 Draft / 🔄 In Progress / ✅ Done  
**작성일**: YYYY-MM-DD  
**마지막 업데이트**: YYYY-MM-DD  
**관련 범위**: (예: backtest, tqqq, utils, scripts)  
**관련 문서**: (예: src/qbt/backtest/CLAUDE.md)

---

## 1) 목표(Goal)

- (예) TQQQ 비용 모델 파라미터 최적화 로직을 리팩토링하면서 결과 스키마는 유지한다.
- (예) 백테스트 그리드 결과 컬럼 정의를 명확히 하고 CSV 출력 규칙을 고정한다.

## 2) 비목표(Non-Goals)

- 이번 작업에서 하지 않을 것
  - (예) UI(스트림릿) 대규모 개편은 범위 밖
  - (예) 새로운 데이터 소스 추가는 범위 밖

## 3) 배경/맥락(Context)

- 왜 필요한가?
- 현재 문제/불편/버그
- 영향 받는 규칙(특히 `CLAUDE.md`의 불변 규칙)

## 4) 완료 조건(Definition of Done)

- [ ] 기능 요구사항 충족
- [ ] 회귀 테스트(또는 신규 테스트) 추가
- [ ] `./run_tests.sh` 통과
- [ ] `poetry run ruff check .` 통과
- [ ] `poetry run black --check .` 통과
- [ ] 필요한 문서(README/CLAUDE/plan) 업데이트

---

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- (예) `src/qbt/tqqq/simulation.py`
- (예) `src/qbt/tqqq/constants.py`
- (예) `scripts/tqqq/validate_tqqq_simulation.py`

### 데이터/결과 영향

- (예) `storage/results/tqqq_validation.csv` 컬럼 변화 여부
- (예) `meta.json` 기록 항목 변화 여부

---

## 6) 단계별 계획(Phases)

> Phase는 3~7개로 유지합니다.  
> 각 Phase는 “작게 완결”되고, 끝에 검증(Validation)이 있어야 합니다.

### Phase 1 — 분석/정리

- [ ] 관련 `CLAUDE.md` 읽고, 불변 규칙 목록화
- [ ] 현재 코드 흐름(입력/출력/중간 데이터) 요약
- [ ] 변경 후에도 유지해야 할 스키마/컬럼/정렬 기준 확정

**Validation**

- [ ] 변경 없음(문서만) → 스킵 가능

---

### Phase 2 — 최소 리팩토링(안전한 뼈대)

- [ ] 함수 분리/이름 정리(동작 동일)
- [ ] 상수 위치 정리(중복 제거, 계층 준수)
- [ ] 타입 힌트/Docstring 보강

**Validation**

- [ ] `./run_tests.sh`

---

### Phase 3 — 기능 변경(핵심 로직)

- [ ] 요구사항에 맞는 로직 변경
- [ ] 경계조건(결측/0/음수/급등락) 처리 확인
- [ ] CSV 출력/컬럼/정렬 규칙 준수

**Validation**

- [ ] `./run_tests.sh`
- [ ] `poetry run ruff check .`
- [ ] `poetry run black --check .`

---

### Phase 4 — 테스트 보강/회귀 방지

- [ ] 신규 케이스 추가(버그 재현/경계조건/대표 시나리오)
- [ ] 기존 테스트가 의도대로 보호하는지 확인
- [ ] 커버리지 필요 시 강화(핵심 로직 우선)

**Validation**

- [ ] `./run_tests.sh cov`

---

### Phase 5 — 정리/문서화

- [ ] Plan 체크리스트 정리(완료 표시)
- [ ] 필요한 문서 업데이트(README/도메인 CLAUDE/사용 예시)
- [ ] (필요 시) 결과 CSV 샘플/컬럼 설명 업데이트

**Validation**

- [ ] `./run_tests.sh`

---

## 7) 리스크(Risks)

- (예) 결과 CSV 스키마 변경으로 기존 분석 파이프라인 깨짐
- (예) 비용 모델 변경으로 지표 비교 불가

### 리스크 완화(Mitigation)

- (예) 출력 컬럼/정렬 고정 + 테스트로 스키마 보호
- (예) 변경 전/후 결과를 동일 조건에서 비교하는 테스트 추가

---

## 8) 메모(Notes)

- 참고 링크/실험 로그/결정 사항 기록
