# Implementation Plan: Cross-Asset Buy & Hold 벤치마크

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

**작성일**: 2026-03-10
**마지막 업데이트**: 2026-03-10
**관련 범위**: backtest, scripts, common_constants
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

- [x] 7개 자산(QQQ, SPY, IWM, EFA, EEM, GLD, TLT)의 Buy & Hold 백테스트 실행 지원
- [x] 버퍼존 전략 대비 B&H 비교 테이블(cross_asset_bh_comparison.csv) 생성
- [x] B&H 상세 테이블(cross_asset_bh_detail.csv) 생성

## 2) 비목표(Non-Goals)

- 기존 버퍼존 전략 결과 재실행/변경
- B&H 전략 자체의 로직 변경
- 대시보드 앱 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 7개 자산의 교차 자산 검증(버퍼존 전략)이 완료되었으나, B&H 벤치마크와의 정량 비교가 없다.
- QQQ, TQQQ의 B&H는 이미 실행된 적 있으나, SPY/IWM/EFA/EEM/GLD/TLT는 B&H 실행 이력이 없다.
- "전략이 B&H보다 나은가?"라는 핵심 질문에 답하기 위해 동일 기간 비교가 필요하다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: B&H 팩토리 패턴, CONFIGS 패턴
- `scripts/CLAUDE.md`: CLI 스크립트 규칙, 예외 처리, 메타데이터 관리
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] buy_and_hold.py CONFIGS에 6개 자산(SPY, IWM, EFA, EEM, GLD, TLT) 추가
- [x] common_constants.py에 6개 B&H 결과 디렉토리 상수 추가
- [x] 비교 스크립트(run_cross_asset_bh_comparison.py) 작성
- [x] 기존 test_buy_and_hold.py의 CONFIGS 관련 테스트 통과 (자동 호환)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/common_constants.py`: B&H 결과 디렉토리 상수 6개 추가
- `src/qbt/backtest/strategies/buy_and_hold.py`: CONFIGS에 6개 설정 추가
- `scripts/backtest/run_cross_asset_bh_comparison.py`: 신규 비교 스크립트
- `tests/test_buy_and_hold.py`: CONFIGS 테스트 업데이트 (기존 테스트가 자동 호환되는지 확인)

### 데이터/결과 영향

- 신규 결과 디렉토리 6개 생성: `storage/results/backtest/buy_and_hold_{spy,iwm,efa,eem,gld,tlt}/`
- 신규 CSV 2개: `cross_asset_bh_comparison.csv`, `cross_asset_bh_detail.csv`
- 기존 결과 파일 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 핵심 구현 (상수 + CONFIGS + 비교 스크립트)

**작업 내용**:

- [x] `common_constants.py`에 B&H 결과 디렉토리 상수 6개 추가
- [x] `buy_and_hold.py` CONFIGS에 6개 BuyAndHoldConfig 추가
- [x] `scripts/backtest/run_cross_asset_bh_comparison.py` 작성
  - 7개 자산 B&H 실행 (기존 B&H runner 활용)
  - 전략 결과(summary.json)에서 CAGR/MDD/Calmar 로딩
  - 비교 테이블 생성 및 CSV 저장
  - 터미널 출력

---

### Phase 2 — 테스트 업데이트

**작업 내용**:

- [x] `test_buy_and_hold.py`의 기존 CONFIGS 테스트가 자동 호환되는지 확인
- [x] CONFIGS 개수 및 cross-asset 포함 테스트 추가

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] 루트 CLAUDE.md 디렉토리 구조에 신규 결과 폴더 반영
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=481, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / cross-asset Buy & Hold 벤치마크 비교 스크립트 추가
2. 백테스트 / 7개 자산 B&H 실행 및 전략 대비 비교 테이블 생성
3. 백테스트 / Buy & Hold CONFIGS 확장(6개 자산) + 비교 스크립트
4. 백테스트 / B&H 벤치마크 cross-asset 비교 기능 추가
5. 백테스트 / 전략 vs B&H 비교 테이블 생성 스크립트 추가

## 7) 리스크(Risks)

- B&H 기간이 버퍼존 전략 기간과 불일치할 수 있음 → 동일 데이터 파일 사용으로 자연 일치
- 기존 test_buy_and_hold.py의 CONFIGS 개수 assertion 실패 가능 → Phase 2에서 수정

## 8) 메모(Notes)

- 기존 패턴: buy_and_hold.py의 BuyAndHoldConfig + CONFIGS + create_runner 팩토리
- B&H 기간은 각 자산의 데이터 파일(SPY_max.csv 등) 전체 기간과 동일
- 버퍼존 전략도 동일 데이터 파일을 사용하므로 기간이 자연스럽게 일치
- 비교 테이블의 전략 결과는 각 전략의 summary.json에서 읽어옴

### 진행 로그 (KST)

- 2026-03-10: Plan 작성 완료, Phase 1~3 구현 및 검증 완료

---
