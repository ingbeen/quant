# Implementation Plan: Rate Spread Lab 서버 런 1회 로드+저장 구조로 고정

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

**작성일**: 2026-01-14 20:30
**마지막 업데이트**: 2026-01-14 21:45
**관련 범위**: tqqq, scripts, utils
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: Streamlit 서버가 처음 기동될 때만 입력 파일 로드 및 월별 결과 계산, 결과 CSV 1회 저장
- [x] 목표 2: 브라우저 새로고침/새 세션에서는 캐시된 데이터만 사용, CSV 재저장 금지
- [x] 목표 3: 입력 파일 변경 시 서버 재실행 전까지 무시 (캐시 유지)
- [x] 목표 4: B/C/D/E 요구사항 반영 (Top 5 diff 기준 명확화, 저장 정책 변경, 성능 최적화, 로직 분리)

## 2) 비목표(Non-Goals)

- CSV 출력 내용/형식 변경 (기존 컬럼명, 라운딩 정책 유지)
- 차트 생성 로직 변경 (visualization.py는 수정하지 않음)
- 분석 계산 로직 변경 (aggregate_monthly, save_monthly_features 등 기존 로직 유지)
- UI 레이아웃 변경 (탭 구조, 섹션 순서 등 유지)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**현재 구현**:

- `load_daily_comparison()`, `load_ffr()`: `@st.cache_data(ttl=600)` + mtime 기반 캐시
- `prepare_monthly_data()`: 캐시 없음 (매번 재계산)
- CSV 저장: `st.session_state.csv_saved`로 세션당 1회 제어

**문제점**:

1. **새로고침 시 CSV 재저장**: 브라우저 새로고침 시 세션이 초기화되어 `st.session_state.csv_saved`가 리셋되고, CSV가 다시 저장됨
2. **파일 변경 시 캐시 무효화**: mtime 기반 캐시 키 사용으로 파일 변경 시 자동 반영됨 (요구사항과 반대)
3. **월별 집계 재계산**: `prepare_monthly_data()`가 캐시되지 않아 Lag 변경 등 위젯 상호작용 시 재계산 가능성

**요구사항**:

1. **서버 런 1회만 저장**: Streamlit 서버 프로세스가 기동될 때만 로드+저장, 이후 새로고침/새 세션은 캐시 사용
2. **입력 파일 변경 무시**: 서버 기동 후 파일 변경 시 캐시 유지 (서버 재실행 전까지)
3. **성능 최적화**: 불필요한 재계산 방지
4. **B/C/D/E 요구사항**:
   - B) Top 5 diff 선정 기준 명확화 (abs(diff) 기준)
   - C) 저장 정책: 세션당 1회 → 서버 런 1회
   - D) 성능: 불필요한 재계산 방지
   - E) 로직 이동: UI와 비즈니스 로직 분리 (현재는 이미 잘 분리되어 있음)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `scripts/CLAUDE.md` (CLI 계층 규칙)
- `src/qbt/tqqq/CLAUDE.md` (TQQQ 도메인 규칙)
- `src/qbt/utils/CLAUDE.md` (유틸리티 규칙)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족:
  - [x] 서버 최초 기동 시 CSV 1회 생성/갱신
  - [x] 브라우저 새로고침 여러 번 → CSV 파일 mtime 변경 없음
  - [x] 서버 실행 중 입력 파일 변경 → UI는 이전 데이터로 계속 정상 표시
  - [x] 서버 재실행 → 새 입력 로드 및 CSV 다시 1회 저장
  - [x] Top 5 diff가 abs(diff) 기준으로 정렬되어 표시됨
- [x] 회귀/신규 테스트 추가 (필요 시) - 기존 테스트 모두 통과, 신규 테스트 불필요
- [x] `poetry run python validate_project.py` 통과 (passed=200, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (42 files left unchanged)
- [x] 필요한 문서 업데이트 (src/qbt/tqqq/CLAUDE.md 업데이트 완료)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**주요**:

- `scripts/tqqq/streamlit_rate_spread_lab.py`: 캐시 구조 변경, 저장 로직 수정, Top 5 diff 정렬 기준 명확화

**문서**:

- `src/qbt/tqqq/CLAUDE.md`: 캐시 정책 및 저장 정책 업데이트 (필요 시)
- `docs/plans/PLAN_streamlit_rate_spread_lab_server_run_once.md`: 이 계획서

**검토 대상** (변경 가능성 낮음):

- `src/qbt/tqqq/analysis_helpers.py`: 로직 이동 여부 검토 (현재는 이미 잘 분리되어 있음)

### 데이터/결과 영향

- **CSV 출력 스키마**: 변경 없음 (컬럼명, 라운딩 정책 유지)
- **CSV 생성 시점**: 변경됨 (세션당 1회 → 서버 런 1회)
- **UI 동작**: 변경됨 (파일 변경 즉시 반영 → 서버 재시작 후 반영)

## 6) 단계별 계획(Phases)

### Phase 1 — 캐시 구조 변경 및 저장 로직 수정 (그린 유지)

**작업 내용**:

- [x] `@st.cache_resource`로 저장 가드 함수 구현 (`_save_guard()`)
  - 반환 구조: `{"saved": False, "lock": threading.Lock()}`
  - 서버 런 동안 유지되는 단일 객체 (세션/새로고침 무관)
- [x] `@st.cache_data`로 데이터 빌드 함수 구현 (`build_artifacts()`)
  - 입력: `(daily_path_str, ffr_path_str)` (문자열만, mtime 제거)
  - 내부: `load_comparison_data()`, `load_ffr_data()`, `prepare_monthly_data()` 호출
  - 출력: `monthly_df` (월별 집계 결과)
- [x] `get_file_mtime()` 제거 (더 이상 사용하지 않음)
- [x] `load_daily_comparison()`, `load_ffr()` 함수 제거 또는 단순화
  - `build_artifacts()` 내부에서 직접 호출하도록 변경
- [x] `st.session_state.csv_saved` 로직 제거
- [x] 저장 로직을 guard 기반으로 변경
  - `with guard["lock"]:` 블록에서 `saved` 체크
  - `saved=False`일 때만 저장 실행 후 `saved=True` 설정
- [x] `prepare_monthly_data()` 로직이 `build_artifacts()` 내부로 통합되었는지 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=200, failed=0, skipped=0)

---

### Phase 2 — B/D/E 요구사항 반영 (그린 유지)

**작업 내용**:

- [x] B) Top 5 diff 선정 기준 명확화
  - `display_cross_validation()`에서 `.nlargest(5, "diff", keep="all")` 수정
  - `abs(diff)` 기준으로 정렬: `nlargest(5, "abs_diff")`로 변경
  - 변수명/레이블에 "절댓값 기준" 명시: `top_diff_abs`, "|diff| 상위 5개월" 표시
- [x] D) 성능 검증
  - Lag 선택 시 `build_artifacts()`가 재실행되지 않는지 확인 (캐시 유지)
  - 월별 DF 복사본에서 shift/파생 계산 수행 확인
- [x] E) 로직 분리 확인
  - `display_cross_validation()`: 이미 UI 로직으로 적절히 분리되어 있음
  - `prepare_monthly_data()`: 이미 비즈니스 로직으로 분리되어 있음
  - 추가 이동 불필요 (현재 구조 유지)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=200, failed=0, skipped=0)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md`의 `streamlit_rate_spread_lab.py` 섹션 업데이트
  - 캐시 정책: `@st.cache_resource` guard + `@st.cache_data` 데이터 빌드
  - 저장 정책: 서버 런 1회 (새로고침 무시)
  - 파일 변경 정책: 서버 재실행 전까지 무시
- [x] `poetry run black .` 실행 (42 files left unchanged)
- [x] 변경 기능 및 전체 플로우 최종 검증
  - 서버 기동 → CSV 생성 → 새로고침 → CSV mtime 변경 없음
  - 입력 파일 수정 → UI는 이전 데이터 표시
  - 서버 재실행 → 새 데이터 로드 + CSV 재생성
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=200, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / Rate Spread Lab 서버 런 1회 저장 구조로 고정
2. TQQQ시뮬레이션 / Rate Spread Lab 캐시 정책 개선 (세션 → 서버 스코프)
3. TQQQ시뮬레이션 / Rate Spread Lab UI 동작 개선 (새로고침 시 재저장 방지)
4. TQQQ시뮬레이션 / Rate Spread Lab 저장 로직 수정 + Top 5 diff 기준 명확화
5. TQQQ시뮬레이션 / Rate Spread Lab 성능 최적화 (불필요한 재계산 방지)

## 7) 리스크(Risks)

- **사용자 경험 변경**: 서버 실행 중 입력 파일 변경 시 즉시 반영되지 않음 (서버 재실행 필요)
  - 완화책: 문서에 명확히 기록, 필요 시 사용자에게 안내 메시지 추가 가능
- **멀티 유저 환경**: `@st.cache_resource`는 모든 유저가 공유하므로 동시 접근 시 lock 필요
  - 완화책: `threading.Lock()` 사용으로 동시 접근 방지 (이미 설계에 포함)
- **캐시 무효화 방법 부재**: 서버 재실행 외에는 캐시를 무효화할 방법이 없음
  - 완화책: 요구사항대로 의도된 동작임 (문제 없음)

## 8) 메모(Notes)

### 참고 자료

- Streamlit 캐시 문서: `st.cache_data` vs `st.cache_resource`
  - `st.cache_data`: 데이터 캐싱, 모든 유저/세션 공유
  - `st.cache_resource`: 리소스 캐싱, 싱글톤처럼 작동, 상태 변경 가능
  - `st.session_state`: 세션별 상태, 새로고침 시 초기화
- Context7 학습 완료: `/websites/streamlit_io` (2026-01-14)

### 핵심 결정 사항

- **Top 5 diff 기준**: abs(diff) 기준 (옵션1) 선택 (사용자 확인 완료)
- **캐시 키**: 파일 경로 문자열만 사용 (mtime 제거)
- **저장 가드**: `@st.cache_resource` + `threading.Lock()` 사용

### 진행 로그 (KST)

- 2026-01-14 20:30: 계획서 작성 시작
- 2026-01-14 20:30: 필수 문서 학습 완료 (루트, scripts, tqqq, utils, tests, docs CLAUDE.md)
- 2026-01-14 20:30: Streamlit 캐시 시스템 학습 완료 (Context7)
- 2026-01-14 20:30: 사용자 확인 완료 (Top 5 diff 기준: abs(diff))
- 2026-01-14 20:30: 계획서 초안 작성 완료
- 2026-01-14 21:00: Phase 1 시작 - 캐시 구조 변경 및 저장 로직 수정
- 2026-01-14 21:10: Phase 1 완료 - 검증 통과 (passed=200, failed=0, skipped=0)
- 2026-01-14 21:15: Phase 2 시작 - B/D/E 요구사항 반영
- 2026-01-14 21:20: Phase 2 완료 - 검증 통과 (passed=200, failed=0, skipped=0)
- 2026-01-14 21:25: 마지막 Phase 시작 - 문서 업데이트 및 최종 검증
- 2026-01-14 21:30: src/qbt/tqqq/CLAUDE.md 업데이트 완료
- 2026-01-14 21:35: Black 포맷팅 실행 완료
- 2026-01-14 21:40: 최종 검증 완료 - 모든 테스트 통과
- 2026-01-14 21:45: 계획서 완료 처리 및 상태 Done으로 변경

---
