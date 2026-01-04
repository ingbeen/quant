# Implementation Plan: Pandas CSV 로딩 최적화 및 Streamlit 캐싱 개선

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-01-03 18:20
**마지막 업데이트**: 2026-01-03 18:20
**관련 범위**: utils, tqqq, scripts
**관련 문서**: src/qbt/utils/CLAUDE.md, scripts/CLAUDE.md

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

- [ ] Pandas CSV 로딩 시 parse_dates 파라미터 사용으로 성능 및 가독성 향상
- [ ] Streamlit 앱에 mtime 기반 캐싱 적용으로 CSV 파일 변경 자동 감지
- [ ] 두 Streamlit 앱의 캐싱 전략 통일

## 2) 비목표(Non-Goals)

- dtype 최적화 (float32 등) - 현재 데이터 규모에서 효과 미미
- 기존 데이터 로딩 로직의 근본적인 재설계
- 테스트 코드의 대규모 리팩토링

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**Pandas CSV 로딩**:
- 현재: CSV 읽기 후 별도로 날짜 파싱 수행 (2단계)
- Context7 Best Practice: `parse_dates` 파라미터로 읽기 시점에 파싱 수행
- 개선 효과: 성능 향상, 코드 의도 명확화

**Streamlit 캐싱**:
- `streamlit_daily_comparison.py`: 기본 `@st.cache_data`만 사용
- `streamlit_rate_spread_lab.py`: `mtime` 기반으로 파일 변경 자동 감지
- 문제점: daily_comparison 앱은 CSV 재생성 시 앱 재시작 필요
- 개선 효과: 브라우저 새로고침만으로 최신 데이터 반영, 두 앱의 전략 통일

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/utils/CLAUDE.md` (유틸리티 패키지)
- `scripts/CLAUDE.md` (CLI 스크립트 계층)
- 테스트를 수정한다면 `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] Pandas: `load_stock_data()` 및 TQQQ 로더들에 parse_dates 적용
- [ ] Streamlit: daily_comparison 앱에 mtime 기반 캐싱 적용
- [ ] 기존 테스트 모두 통과 (동작 변경 없음)
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**Pandas 최적화**:
- `src/qbt/utils/data_loader.py` - load_stock_data()
- `src/qbt/tqqq/data_loader.py` - load_comparison_data(), load_qqq_data(), load_tqqq_data(), load_ffr_data()

**Streamlit 캐싱**:
- `scripts/tqqq/streamlit_daily_comparison.py` - load_data() 함수 및 호출부

### 데이터/결과 영향

- 데이터 로딩 결과는 동일 (기능적 변경 없음)
- Streamlit 앱의 사용자 경험 개선 (파일 변경 자동 반영)

## 6) 단계별 계획(Phases)

### Phase 1 — Pandas parse_dates 적용

**작업 내용**:

- [ ] `src/qbt/utils/data_loader.py:load_stock_data()` 수정
  - `pd.read_csv(path)` → `pd.read_csv(path, parse_dates=[COL_DATE])`
  - 이후 `.dt.date` 변환은 유지 (프로젝트 정책: date 객체 사용)
- [ ] `src/qbt/tqqq/data_loader.py` 수정
  - `load_comparison_data()`: DISPLAY_DATE 파싱
  - `load_qqq_data()`, `load_tqqq_data()`: COL_DATE 파싱
  - `load_ffr_data()`: DATE 컬럼은 문자열 유지 (yyyy-mm 형식)
- [ ] 기존 테스트 실행으로 동작 검증

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

---

### Phase 2 — Streamlit mtime 캐싱 적용

**작업 내용**:

- [ ] `scripts/tqqq/streamlit_daily_comparison.py` 수정
  - `get_file_mtime()` 함수 추가 (rate_spread_lab.py에서 참고)
  - `load_data()` 함수 시그니처 변경: `load_data(csv_path, _mtime)`
  - `@st.cache_data` → `@st.cache_data(ttl=600)` (10분 캐시)
  - 호출부에서 mtime 전달: `mtime = get_file_mtime(csv_path)`, `df = load_data(csv_path, mtime)`
- [ ] 두 Streamlit 앱의 캐싱 전략이 동일한 패턴인지 코드 리뷰

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)
- [ ] Streamlit 앱 수동 테스트 (CSV 재생성 후 새로고침으로 반영 확인)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [ ] 필요 시 data_loader 함수 docstring 업데이트 (parse_dates 언급)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=**, failed=**, skipped=__)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 리팩토링 / Pandas parse_dates 및 Streamlit mtime 캐싱 적용으로 성능 및 UX 개선
2. 데이터 로딩 / CSV 로딩 최적화 및 Streamlit 파일 변경 자동 감지
3. 개선 / Pandas 날짜 파싱 최적화 + Streamlit 캐싱 전략 통일
4. 리팩토링 / Context7 Best Practice 적용 (Pandas, Streamlit)
5. 유틸/스크립트 / 데이터 로딩 성능 개선 및 대시보드 캐싱 강화

## 7) 리스크(Risks)

- **리스크**: parse_dates 적용 후 날짜 타입이 기대와 다를 수 있음
  - **완화**: `.dt.date` 변환 유지로 기존 정책(date 객체) 준수, 테스트로 검증
- **리스크**: Streamlit 캐싱 변경으로 예상치 못한 동작 발생 가능
  - **완화**: rate_spread_lab.py의 검증된 패턴 재사용, 수동 테스트로 확인
- **리스크**: 기존 테스트 실패 가능성
  - **완화**: 각 Phase에서 즉시 검증 및 수정

## 8) 메모(Notes)

- Context7에서 권장하는 Pandas Best Practice: `pd.read_csv(path, parse_dates=[column_list])`
- Streamlit 앱 테스트는 `poetry run streamlit run scripts/tqqq/streamlit_daily_comparison.py`로 수행
- mtime 기반 캐싱: 파일 수정 시간이 변경되면 캐시 무효화되어 재로드

### 진행 로그 (KST)

- 2026-01-03 18:20: 계획서 초안 작성 완료

---
