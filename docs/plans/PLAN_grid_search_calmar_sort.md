# Implementation Plan: 그리드 서치 정렬 기준 Calmar 통일 + README 수정

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

**작성일**: 2026-03-02 22:30
**마지막 업데이트**: 2026-03-02 23:00
**관련 범위**: backtest, scripts, docs
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

- [x] 그리드 서치 결과 정렬 기준을 CAGR에서 Calmar(CAGR / |MDD|)로 변경
- [x] `load_best_grid_params` 함수의 docstring을 Calmar 기준으로 갱신
- [x] README.md의 `run_grid_search.py` 설명에서 `buffer_zone_atr_tqqq` 제거

## 2) 비목표(Non-Goals)

- GridSearchResult TypedDict에 calmar 필드 추가 (Calmar는 CAGR와 MDD에서 계산 가능하므로 저장 불필요)
- grid_results.csv에 Calmar 컬럼 추가 (정렬 기준만 변경, CSV 스키마 변경 없음)
- WFO의 `select_best_calmar_params` 변경 (이미 Calmar 기준)
- `backtest_research_log.md` 수정 (사용자 관리 영역)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **기준 불일치**: 그리드 서치는 CAGR 기준, WFO IS 최적화는 Calmar 기준으로 서로 다른 최적화 기준 사용
   - `run_grid_search` (buffer_zone_helpers.py:886): `sort_values(by=COL_CAGR)`
   - `select_best_calmar_params` (walkforward.py:199): Calmar 내림차순
2. **리스크 미반영**: CAGR만으로 정렬 시 MDD -85%인 조합이 1위가 될 수 있음 (연구 로그 §2.1 과최적화 경고 사례)
3. **README 오류**: `run_grid_search.py --strategy buffer_zone_atr_tqqq`가 README에 명시되어 있으나, 실제 코드의 `STRATEGY_CONFIG`에는 해당 전략이 없음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 계층 규칙
- `tests/CLAUDE.md`: 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `run_grid_search` 함수가 Calmar 내림차순으로 정렬
- [x] `run_grid_search.py` 스크립트의 정렬도 Calmar 기준으로 변경
- [x] `load_best_grid_params` docstring이 Calmar 기준으로 갱신
- [x] 기존 테스트 및 신규 테스트 통과
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] README.md에서 `buffer_zone_atr_tqqq` 제거
- [x] 관련 CLAUDE.md 문서 갱신
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

비즈니스 로직:
- `src/qbt/backtest/strategies/buffer_zone_helpers.py`: `run_grid_search()` 정렬 기준 변경 (CAGR → Calmar)
- `src/qbt/backtest/analysis.py`: `load_best_grid_params()` docstring 갱신 (CAGR 1위 → Calmar 1위)

CLI 스크립트:
- `scripts/backtest/run_grid_search.py`: 정렬 로직 변경 + 테이블 타이틀 변경 ("CAGR 기준" → "Calmar 기준")

문서:
- `README.md`: `run_grid_search.py --strategy` 옵션에서 `buffer_zone_atr_tqqq` 제거
- `src/qbt/backtest/CLAUDE.md`: grid_results.csv 정렬 기준 갱신
- `scripts/CLAUDE.md`: 그리드 서치 `--strategy` 선택지 문서 확인 (이미 정확하면 변경 없음)

테스트:
- `tests/test_analysis.py`: `TestLoadBestGridParams` docstring/주석 갱신 (CAGR → Calmar), CSV 데이터 변경 (Calmar 내림차순 정렬 반영)
- `tests/test_buffer_zone_helpers.py`: 그리드 서치 정렬 관련 테스트 확인 및 필요 시 수정

### 데이터/결과 영향

- `storage/results/backtest/{strategy_name}/grid_results.csv`: 재실행 시 정렬 순서가 변경됨 (기존 파일은 사용자가 재실행 시 갱신)
- CSV 스키마(컬럼) 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — Calmar 정렬 로직 구현 + 테스트 수정 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py`:
  - `run_grid_search()` (line 886): 정렬을 Calmar 기반으로 변경
    - Calmar 계산: `CAGR / abs(MDD)`, MDD=0 안전 처리는 `walkforward.py`의 `_calmar()` 패턴 재사용
    - 방식: `_calmar` 컬럼을 임시 생성 → 정렬 → 임시 컬럼 삭제
- [x] `scripts/backtest/run_grid_search.py`:
  - line 191: `sort_values(by=COL_CAGR)` 제거 (비즈니스 로직에서 이미 정렬)
  - line 228: 테이블 타이틀 "CAGR 기준" → "Calmar 기준"
- [x] `src/qbt/backtest/analysis.py`:
  - `load_best_grid_params()` docstring: "CAGR 1위" → "Calmar 1위"
- [x] `tests/test_analysis.py`:
  - `TestLoadBestGridParams` 클래스: docstring/주석의 "CAGR 1위" → "Calmar 1위", "CAGR 내림차순" → "Calmar 내림차순"
  - `_CSV_ROW_1` MDD를 -50.00으로 조정하여 Calmar 내림차순 유지 (ROW_1 Calmar≈0.418 > ROW_2 Calmar≈0.264)
- [x] `tests/test_buffer_zone_helpers.py`: Calmar 내림차순 정렬 검증으로 변경

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `README.md` line 46: `buffer_zone_atr_tqqq /` 제거
- [x] `src/qbt/backtest/CLAUDE.md`: "정렬: CAGR 내림차순" → "정렬: Calmar 내림차순" + `load_best_grid_params` 설명 갱신
- [x] `scripts/CLAUDE.md`: 확인 완료 (이미 `all / buffer_zone_tqqq / buffer_zone_qqq`, 변경 불필요)
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=423, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 그리드 서치 정렬 기준 CAGR → Calmar 통일 + README buffer_zone_atr_tqqq 제거
2. 백테스트 / 그리드 서치와 WFO 최적화 기준 Calmar로 일관성 확보
3. 백테스트 / 그리드 서치 Calmar 정렬 적용 및 README 문서 오류 수정
4. 백테스트 / 리스크 조정 수익률(Calmar) 기준 그리드 서치 정렬 통일
5. 백테스트 / 그리드 서치 정렬 Calmar 전환 + README --strategy 옵션 수정

## 7) 리스크(Risks)

- **기존 grid_results.csv와 순서 불일치**: Calmar 기준 재정렬 시 기존 CAGR 기준 CSV와 순서가 달라짐. 사용자가 스크립트를 재실행하면 자동 갱신되므로 실질적 영향 없음
- **Calmar 계산 중복**: `walkforward.py`의 `_calmar()` 함수와 동일한 MDD=0 안전 처리 로직이 필요. 로컬 헬퍼로 구현하여 중복은 최소화

## 8) 메모(Notes)

- Calmar 계산식: `CAGR / abs(MDD)` (CAGR, MDD 모두 % 단위)
- MDD=0 안전 처리: `abs(MDD) < EPSILON`일 때 CAGR>0이면 `1e10 + CAGR` 반환 (walkforward.py 패턴 동일)
- `run_grid_search()` 내부에서 임시 컬럼(`_calmar`)을 생성하여 정렬 후 삭제하는 방식 채택
- 스크립트의 중복 정렬(`run_grid_search.py` line 191) 제거 — 비즈니스 로직에서 이미 정렬하므로 불필요

### 진행 로그 (KST)

- 2026-03-02 22:30: 계획서 초안 작성
- 2026-03-02 23:00: 전체 구현 완료 (passed=423, failed=0, skipped=0)

---
