# Implementation Plan: 파라미터 고원 분석 (sell_buffer / buy_buffer / ma_window)

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

**작성일**: 2026-03-09 23:00
**마지막 업데이트**: 2026-03-09 23:00
**관련 범위**: scripts/backtest, backtest
**관련 문서**: [docs/PLAN_param_plateau_analysis.md](../PLAN_param_plateau_analysis.md) (실험 설계 원본), [docs/overfitting_analysis_report.md](../overfitting_analysis_report.md)

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

- [x] 3개 파라미터(sell_buffer, buy_buffer, ma_window)의 고원(plateau) 형태를 확인하는 래퍼 스크립트 구현
- [x] 7개 자산 × 6개 값 × 3개 실험 = 126회 백테스트 실행 및 결과 CSV 16종 생성
- [x] hold_days 고원 분석 스크립트와 동일한 구조 및 출력 형식 유지

## 2) 비목표(Non-Goals)

- 기존 전략의 결과 파일(storage/results/backtest/buffer_zone_*)을 변경하지 않는다
- hold_days 고원 분석 결과(hold_days_plateau/)를 변경하지 않는다
- 결과에서 "최적값"을 선택하는 로직을 넣지 않는다 (형태 확인 목적)
- 비즈니스 로직(src/qbt/) 변경 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- hold_days에 대해서는 56회 고원 분석을 통해 "봉우리가 아닌 고원의 일부"임을 확인 완료
- 나머지 3개 파라미터(sell_buffer, buy_buffer, ma_window)에 대해서는 동일한 검증이 미수행
- sell_buffer는 "넓을수록 Calmar가 높아지는 체계적 방향성"이 관찰되었으나, 탐색 범위 [0.01, 0.03, 0.05]로 제한되어 고원 vs 봉우리 판단 불가
- 상세 실험 설계: [docs/PLAN_param_plateau_analysis.md](../PLAN_param_plateau_analysis.md) §1~10 참조

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `scripts/backtest/run_param_plateau.py` 구현 완료 (3개 실험 × 7자산 × 6값 = 126회)
- [x] CSV 16종 생성 구조 구현 (피벗 5종 × 3실험 + 상세 1종)
- [x] 터미널 출력 (TableLogger) 구현
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트 (scripts/CLAUDE.md, 루트 CLAUDE.md 디렉토리 구조)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/run_param_plateau.py` (신규)
- `scripts/CLAUDE.md` (스크립트 목록 업데이트)
- `CLAUDE.md` (루트 - 디렉토리 구조에 결과 폴더 추가)

### 데이터/결과 영향

- 결과 저장 경로: `storage/results/backtest/param_plateau/`
- 기존 결과 파일에 영향 없음
- CSV 16종 출력 (피벗 15종 + 상세 1종)

## 6) 단계별 계획(Phases)

### Phase 1 — 스크립트 구현 (그린 유지)

기존 `run_hold_days_plateau.py`와 동일한 구조로, 3개 실험을 순차 실행하는 래퍼 스크립트를 구현한다.

**핵심 구조:**

1. 실험 정의 (로컬 상수)
   - 실험 A: sell_buffer = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15], 나머지 고정
   - 실험 B: buy_buffer = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10], 나머지 고정
   - 실험 C: ma_window = [50, 100, 150, 200, 250, 300], 나머지 고정

2. 고정 파라미터 (모든 실험 공통):
   - hold_days=3, recent_months=0, ma_type=ema
   - 실험별 고정값: §3~5 of PLAN_param_plateau_analysis.md 참조

3. 실험 C (ma_window) 특수 처리:
   - 실험 A/B: 자산별 MA 계산 1회 (ma=200 고정) → hold_days 스크립트와 동일
   - 실험 C: ma_window 값마다 MA 재계산 필요 (`add_single_moving_average` 호출)

**작업 내용**:

- [x] `scripts/backtest/run_param_plateau.py` 신규 생성
  - [x] 로컬 상수 정의 (결과 경로, 실험별 탐색 값, 자산 목록, 고정 파라미터)
  - [x] 실험 실행 함수 구현 (126회 백테스트)
  - [x] CSV 저장 함수 구현 (피벗 15종 + 상세 1종)
  - [x] 터미널 출력 함수 구현 (TableLogger)
  - [x] main() 함수 구현 (@cli_exception_handler)

---

### Phase 2 (Final) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `scripts/CLAUDE.md` 업데이트 (백테스트 스크립트 목록에 추가)
- [x] 루트 `CLAUDE.md` 업데이트 (디렉토리 구조에 param_plateau/ 추가)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=479, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / sell_buffer·buy_buffer·ma_window 고원 분석 래퍼 스크립트 추가
2. 백테스트 / 파라미터 고원 분석 스크립트 구현 (126회 백테스트, CSV 16종)
3. 백테스트 / 3개 파라미터 고원 형태 확인 실험 스크립트 추가
4. 백테스트 / param_plateau 분석 래퍼 구현 (hold_days 고원 분석 확장)
5. 백테스트 / 파라미터 안정성 검증용 고원 분석 스크립트 추가

## 7) 리스크(Risks)

- 리스크 낮음: 기존 비즈니스 로직 변경 없이 래퍼 스크립트만 추가
- 스크립트 실행은 사용자가 직접 수행 (AI 모델이 실행하지 않음)

## 8) 메모(Notes)

- 기존 `run_hold_days_plateau.py` (247줄) 구조를 기반으로 확장
- `_CROSS_ASSET_HOLD_DAYS = 2` (현재 코드) vs 실험 고정값 hold_days=3: `dataclasses.replace()`로 명시적 오버라이드하여 실험 설계 문서의 값을 사용
- 실험 설계 원본: [docs/PLAN_param_plateau_analysis.md](../PLAN_param_plateau_analysis.md)
- 참고 보고서: [docs/overfitting_analysis_report.md](../overfitting_analysis_report.md) §18

### 진행 로그 (KST)

- 2026-03-09 23:00: 계획서 작성 완료, Phase 1 진행 시작

---
