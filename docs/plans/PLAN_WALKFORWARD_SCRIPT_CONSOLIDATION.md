# Implementation Plan: 워크포워드 검증 스크립트 통합 + 병렬처리 제거

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

**작성일**: 2026-02-21 17:40
**마지막 업데이트**: 2026-02-21 18:30
**관련 범위**: scripts/tqqq/spread_lab, src/qbt/tqqq, tests
**관련 문서**: PROJECT_ANALYSIS_REPORT.md D-3

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

- [x] 3개 워크포워드 검증 스크립트를 단일 `validate_walkforward.py`로 통합 (CLI 인자 없이 항상 3가지 모드 순차 실행)
- [x] 워크포워드/최적화의 병렬처리를 순차 실행으로 전환 (ProcessPool 오버헤드 제거)
- [x] 공통 패턴(데이터 로딩, 요약 출력, CSV 저장, 메타데이터) 함수 추출로 중복 제거

## 2) 비목표(Non-Goals)

- `src/qbt/tqqq/walkforward.py`의 워크포워드 로직(윈도우 구조, RMSE 계산 등) 변경
- `src/qbt/utils/parallel_executor.py` 모듈 자체 수정 (다른 도메인에서 여전히 사용)
- 출력 CSV 파일 형식/경로 변경
- `meta_manager.py`의 `VALID_CSV_TYPES` 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**D-3 (스크립트 중복)**: 3개 워크포워드 검증 스크립트가 "데이터 로딩 → 정보 출력 → 실행 → stitched RMSE → 요약 출력 → CSV 저장 → 메타데이터 저장" 패턴을 ~60% 중복

| 파일 | 줄 수 | 고유 로직 |
|------|-------|----------|
| `validate_walkforward.py` | 166 | `run_walkforward_validation()` (a,b 모두 최적화) |
| `validate_walkforward_fixed_b.py` | 174 | `run_walkforward_validation(fixed_b=b_global)` |
| `validate_walkforward_fixed_ab.py` | 244 | `run_fixed_ab_walkforward()` + 금리 구간별 RMSE |

**병렬처리 오버헤드**: 워크포워드에서 `execute_parallel()`이 ~121회 호출되며, 매번 ProcessPool 생성/소멸 + pickle 직렬화가 발생. 실측 결과 워커 1개(순차)가 워커 2개(병렬)보다 빠름

### 동작 변경 사항

- 기존: `validate_walkforward.py`는 튜닝 CSV 없이 독립 실행 가능
- 변경: 통합 스크립트는 항상 3가지 모드를 모두 실행하므로 `tune_softplus_params.py` 선행 필수
- 사유: 3가지 모드는 비교 분석 목적이므로 개별 실행보다 전체 실행이 의미 있음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`: 계층 분리, 상수 관리, 코딩 표준
- `scripts/CLAUDE.md`: CLI 계층 규칙, 예외 처리 패턴
- `src/qbt/tqqq/CLAUDE.md`: 워크포워드 검증 도메인 규칙
- `tests/CLAUDE.md`: 테스트 작성 원칙 (max_workers 파라미터 제거 반영)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 통합 `validate_walkforward.py`가 3가지 모드를 순차 실행
- [x] `validate_walkforward_fixed_b.py`, `validate_walkforward_fixed_ab.py` 삭제
- [x] `optimization.py`, `walkforward.py`에서 `execute_parallel` → 순차 루프 전환
- [x] `max_workers` 파라미터 제거 (함수 시그니처 + 테스트)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (README.md, scripts/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, PROJECT_ANALYSIS_REPORT.md)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**비즈니스 로직 (병렬 → 순차)**:

- `src/qbt/tqqq/optimization.py` — `execute_parallel` 2곳 → 순차 루프, `max_workers` 파라미터 제거
- `src/qbt/tqqq/walkforward.py` — `execute_parallel` 1곳 → 순차 루프, `max_workers` 파라미터 제거

**CLI 스크립트 (통합)**:

- `scripts/tqqq/spread_lab/validate_walkforward.py` — 3모드 통합 재작성
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py` — 삭제
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` — 삭제

**참조 업데이트**:

- `scripts/tqqq/spread_lab/app_rate_spread_lab.py` — 7개 참조 업데이트 (L28, L592, L903, L1008, L1021, L1138, L1271)
- `README.md` — L99, L102, L105, L199 참조 업데이트

**테스트 (max_workers 파라미터 제거 반영)**:

- `tests/test_tqqq_optimization.py` — `max_workers=1` 인자 5곳 제거
- `tests/test_tqqq_walkforward.py` — `max_workers=1` 인자 3곳 제거

**문서**:

- `scripts/CLAUDE.md` — 스크립트 목록 업데이트
- `src/qbt/tqqq/CLAUDE.md` — CLI 스크립트 섹션 + optimization.py 설명 업데이트
- `PROJECT_ANALYSIS_REPORT.md` — D-3 상태 업데이트

### 데이터/결과 영향

- 출력 CSV 파일 경로/형식 변경 없음 (기존 6개 결과 파일 동일 생성)
- `meta.json` 메타데이터 타입 3개 유지
- 시뮬레이션 결과값 동일 (순차/병렬 모두 동일한 `evaluate_softplus_candidate()` 사용)

## 6) 단계별 계획(Phases)

### Phase 1 — 병렬처리 → 순차 전환 (비즈니스 로직)

**작업 내용**:

`optimization.py` 변경:

```python
# 변경 전 (L441-448, L499-506)
candidates = execute_parallel(
    evaluate_softplus_candidate, param_combinations,
    max_workers=max_workers,
    initializer=init_worker_cache, initargs=(cache_data,),
)

# 변경 후
init_worker_cache(cache_data)
candidates = [evaluate_softplus_candidate(p) for p in param_combinations]
```

- `find_optimal_softplus_params()`: `max_workers` 파라미터 제거, Stage 1/Stage 2 모두 순차 루프
- import에서 `execute_parallel` 제거 (`WORKER_CACHE`, `init_worker_cache`는 유지)

`walkforward.py` 변경:

- `_local_refine_search()`: `max_workers` 파라미터 제거, 순차 루프
- `run_walkforward_validation()`: `max_workers` 파라미터 제거
- import에서 `execute_parallel` 제거

테스트 반영:

- `test_tqqq_optimization.py`: `max_workers=1` 인자 5곳 제거
- `test_tqqq_walkforward.py`: `max_workers=1` 인자 3곳 제거

- [x] `optimization.py` `execute_parallel` → 순차 루프 전환 (2곳)
- [x] `optimization.py` `max_workers` 파라미터 제거
- [x] `walkforward.py` `execute_parallel` → 순차 루프 전환 (1곳)
- [x] `walkforward.py` `max_workers` 파라미터 제거
- [x] `test_tqqq_optimization.py` `max_workers=1` 인자 제거 (5곳)
- [x] `test_tqqq_walkforward.py` `max_workers=1` 인자 제거 (3곳)

---

### Phase 2 — 통합 스크립트 작성 + 기존 스크립트 삭제

**작업 내용**:

통합 스크립트 내부 구조:

```
validate_walkforward.py
├── 공통 헬퍼 (private)
│   ├── _log_summary(): 결과 요약 출력 (8줄 공통 패턴)
│   ├── _save_results(): CSV 결과 + 요약 저장
│   └── _build_common_metadata(): 공통 메타데이터 딕셔너리 생성
├── 모드별 실행 함수 (private)
│   ├── _run_standard(): 동적 워크포워드
│   ├── _run_fixed_b(): b 고정 워크포워드
│   └── _run_fixed_ab(): (a,b) 고정 워크포워드
└── main(): 튜닝 파라미터 로드 → 데이터 로딩 (1회) → 3모드 순차 실행
```

main() 흐름:
1. 튜닝 CSV 존재 확인 + (a_global, b_global) 로드
2. QQQ, TQQQ, FFR, Expense 데이터 로드 (1회, 공유)
3. SPREAD_LAB_DIR 생성
4. `_run_standard(qqq_df, tqqq_df, ffr_df, expense_df)` 실행
5. `_run_fixed_b(qqq_df, tqqq_df, ffr_df, expense_df, b_global)` 실행
6. `_run_fixed_ab(qqq_df, tqqq_df, ffr_df, expense_df, a_global, b_global)` 실행

공통 헬퍼 설계:

- `_log_summary(title, summary, stitched_rmse, extra_lines=None)`: 공통 8줄 요약 출력
- `_save_results(result_df, summary, result_path, summary_path)`: CSV 저장 + 로깅
- `_build_common_metadata(summary, stitched_rmse, elapsed_time)`: 공통 메타데이터 dict 생성 (모드별 추가 필드는 호출측에서 dict.update)

- [x] 통합 `validate_walkforward.py` 작성
- [x] `validate_walkforward_fixed_b.py` 삭제
- [x] `validate_walkforward_fixed_ab.py` 삭제

---

### Phase 3 (마지막) — 참조 업데이트 + 문서 정비 + 최종 검증

**작업 내용**:

참조 업데이트:

- `app_rate_spread_lab.py`: 7개 참조를 `validate_walkforward.py` 단일 명령어로 통일
- `README.md`: L99, L102, L105, L199 참조 업데이트

문서 업데이트:

- `scripts/CLAUDE.md`: 3개 스크립트 → 1개 통합 스크립트
- `src/qbt/tqqq/CLAUDE.md`: CLI 스크립트 섹션 통합 + optimization.py 병렬처리 제거 반영
- `PROJECT_ANALYSIS_REPORT.md`: D-3 상태 `[해결됨]`

포맷 및 검증:

- [x] `app_rate_spread_lab.py` 7개 참조 업데이트
- [x] `README.md` 참조 업데이트
- [x] `scripts/CLAUDE.md` 업데이트
- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
- [x] `PROJECT_ANALYSIS_REPORT.md` D-3 상태 업데이트
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=317, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / 워크포워드 스크립트 3개 통합 + 병렬처리 순차 전환
2. TQQQ시뮬레이션 / 워크포워드 검증 통합 실행 + ProcessPool 오버헤드 제거
3. 리팩토링 / 워크포워드 스크립트 통합, 최적화 순차 실행 전환 (D-3 해결)
4. TQQQ시뮬레이션 / 워크포워드 3스크립트 단일 진입점 + 순차 시뮬레이션 전환
5. TQQQ시뮬레이션 / 워크포워드 통합 및 병렬처리 제거 (동작 동일, 성능 개선)

## 7) 리스크(Risks)

| 리스크 | 영향 | 완화책 |
|--------|------|--------|
| 동적 워크포워드 실패 시 후속 모드 미실행 | 중간 | `@cli_exception_handler`가 전체 실패 처리, 사전 조건(튜닝 CSV)을 main 진입 시 검증 |
| 순차 전환 시 수치 결과 차이 | 없음 | 동일한 `evaluate_softplus_candidate()` 사용, 입력 순서도 동일 |
| `tune_softplus_params.py`도 순차로 전환됨 | 낮음 | 이 스크립트는 `find_optimal_softplus_params()` 1회 호출 (풀 2회 생성만 제거), max_workers 미지정이므로 코드 변경 불필요 |

## 8) 메모(Notes)

### 기존 스크립트 실행 성능 기준선 (2026-02-21, 병렬 워커 2)

통합 후 순차 실행 성능과 비교하기 위한 기준 데이터:

| 스크립트 | 시작 시각 | 종료 시각 | 소요 시간 |
|---------|----------|----------|----------|
| `validate_walkforward.py` | 17:26:27 | 17:27:48 | **약 81초** |
| `validate_walkforward_fixed_b.py` | 17:28:32 | 17:29:40 | **약 68초** |
| `validate_walkforward_fixed_ab.py` | 17:29:44 | 17:29:54 | **약 10초** |
| **합계** | | | **약 159초** |

- fixed_ab는 파라미터 재최적화 없이 고정값 시뮬레이션만 수행하므로 가장 빠름
- standard와 fixed_b는 매월 최적화(execute_parallel ~121회 호출)가 주요 병목
- 통합 후 순차 전환 시 데이터 로딩 1회 공유 + ProcessPool 오버헤드 제거로 성능 개선 기대

### 주요 결정 사항

- 사용자 결정: CLI 인자 없이 항상 3가지 모드 전체 실행
- 사용자 결정: 워커 1개가 더 빠르므로 병렬처리 제거
- `VALID_CSV_TYPES` 3가지 타입 유지 — 메타데이터 이력 호환성
- 결과 CSV 경로 6개 유지 — 기존 결과 파일과 호환

### 참고: app_rate_spread_lab.py 내 참조 위치 (7개)

- L28: docstring (`validate_walkforward.py` — 유지)
- L592: st.warning (`validate_walkforward_fixed_b.py` → 변경)
- L903: st.warning (`validate_walkforward_fixed_ab.py` → 변경)
- L1008: st.info (`validate_walkforward_fixed_ab.py` → 변경)
- L1021: st.info (`validate_walkforward_fixed_ab.py` → 변경)
- L1138: st.warning (`validate_walkforward.py` — 유지)
- L1271: st.warning (`validate_walkforward.py` — 유지)

### 진행 로그 (KST)

- 2026-02-21 17:40: Plan 작성 완료
- 2026-02-21 18:30: 전체 Phase 완료, validate_project.py 통과 (passed=317, failed=0, skipped=0)

---
