# Implementation Plan: WFO 결과 시각화 대시보드

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

**작성일**: 2026-03-14 15:00
**마지막 업데이트**: 2026-03-14 15:30
**관련 범위**: scripts/backtest
**관련 문서**: src/qbt/backtest/CLAUDE.md, scripts/CLAUDE.md

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

- [x] `run_walkforward.py`의 결과물(WFO CSV/JSON)을 Streamlit 대시보드로 시각화
- [x] `app_rate_spread_lab.py`의 VERBATIM 패턴(용어 설명 / 해석 방법 / 현재 판단) 적용
- [x] 전략별 탭 구성 (buffer_zone_tqqq, buffer_zone_qqq)

## 2) 비목표(Non-Goals)

- 비즈니스 로직(`src/qbt/`) 변경 없음
- 테스트 추가 없음 (Streamlit 앱은 테스트 대상 아님)
- `app_parameter_stability.py`와 합치기 (별도 앱으로 분리)
- "현재 지표 해석 & 판단(결과)" 내용 작성 (추후 사용자가 캡처 후 별도 작성)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `run_walkforward.py` 실행 후 생성되는 WFO 결과(CSV/JSON)를 CLI 출력으로만 확인 가능
- 시각적으로 IS vs OOS 성과 비교, Stitched Equity 곡선, 파라미터 추이 등을 확인할 수 없음
- `app_rate_spread_lab.py`와 동일한 VERBATIM 패턴으로 용어/해석 가이드를 제공하여 일관된 사용자 경험 제공

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md` (Streamlit 앱 규칙: `width="stretch"`, `use_container_width` 금지 등)
- `src/qbt/backtest/CLAUDE.md` (WFO 타입/상수 참조)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `scripts/backtest/app_walkforward.py` 생성
- [x] 전략별 탭 (buffer_zone_tqqq, buffer_zone_qqq) 자동 탐색
- [x] 5개 시각화 섹션 구현 (모드 요약, Stitched Equity, IS/OOS 비교, 파라미터 추이, WFE 분포)
- [x] 각 섹션에 VERBATIM 3부분 구조 적용 (용어 설명, 해석 방법, 현재 판단은 빈칸)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `scripts/CLAUDE.md` 업데이트 (app_walkforward.py 설명 추가)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_walkforward.py` (신규 생성)
- `scripts/CLAUDE.md` (앱 설명 추가)

### 데이터/결과 영향

- 읽기 전용: 기존 WFO 결과 파일(walkforward_*.csv, walkforward_summary.json)을 로드하여 시각화만 수행
- 출력 스키마 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — app_walkforward.py 구현 (그린 유지)

**데이터 소스** (읽기 전용):

- `{strategy_dir}/walkforward_summary.json` → 모드별 요약 지표
- `{strategy_dir}/walkforward_dynamic.csv` → Dynamic 윈도우별 결과
- `{strategy_dir}/walkforward_fully_fixed.csv` → Fully Fixed 윈도우별 결과
- `{strategy_dir}/walkforward_equity_dynamic.csv` → Dynamic Stitched Equity
- `{strategy_dir}/walkforward_equity_fully_fixed.csv` → Fully Fixed Stitched Equity

**화면 구성** (전략별 탭 내부):

1. **모드별 요약 비교** — `st.columns` + `st.metric`으로 Dynamic vs Fully Fixed 핵심 지표 비교
   - Stitched CAGR, Stitched MDD, Stitched Calmar
   - OOS CAGR 평균, OOS MDD 최악, WFE Calmar Robust
   - Profit Concentration 최대

2. **Stitched Equity 곡선** — Plotly 라인차트
   - Dynamic equity vs Fully Fixed equity (2라인 오버레이)
   - X축: 날짜, Y축: equity

3. **윈도우별 IS vs OOS 성과 비교** — Plotly Grouped Bar 차트
   - (a) CAGR 비교: 윈도우별 IS CAGR vs OOS CAGR
   - (b) Calmar 비교: 윈도우별 IS Calmar vs OOS Calmar
   - Dynamic 모드 기준

4. **파라미터 추이** — Plotly 라인차트 (5개 서브플롯)
   - walkforward_summary.json의 `param_ma_windows`, `param_buy_buffers`, `param_sell_buffers`, `param_hold_days`, `param_recent_months`
   - X축: 윈도우 인덱스, Y축: 파라미터 값
   - Dynamic 모드 기준 (Fully Fixed는 일정하므로 시각화 불필요)

5. **WFE 분포** — Plotly Bar 차트
   - 윈도우별 WFE Calmar, WFE CAGR 바차트
   - 0 기준선 표시 (양수: 효율적, 음수: 비효율적)

**VERBATIM 패턴** (각 섹션마다):

```markdown
## 지표에 사용하는 용어에 대한 설명
- ...

## 지표를 해석하는 방법
- ...

## 현재 지표 해석 & 판단(결과)
- (추후 작성 예정)
```

**작업 내용**:

- [x] `scripts/backtest/app_walkforward.py` 파일 생성
- [x] 데이터 로딩 함수 (`@st.cache_data` 적용)
- [x] 전략 자동 탐색 (walkforward_summary.json 존재 여부로 판별)
- [x] 섹션 1: 모드별 요약 비교 + VERBATIM
- [x] 섹션 2: Stitched Equity 곡선 + VERBATIM
- [x] 섹션 3: IS vs OOS 성과 비교 바차트 + VERBATIM
- [x] 섹션 4: 파라미터 추이 차트 + VERBATIM
- [x] 섹션 5: WFE 분포 바차트 + VERBATIM

---

### Phase 2 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `scripts/CLAUDE.md` 업데이트 (app_walkforward.py 설명 추가)
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / WFO 결과 시각화 앱 신규 추가 (app_walkforward.py)
2. 대시보드 / 워크포워드 검증 결과 Streamlit 대시보드 구현
3. 백테스트 / WFO 시각화 대시보드 추가 (Stitched Equity, IS/OOS 비교, 파라미터 추이)
4. 대시보드 / WFO 결과 시각화 + VERBATIM 용어/해석 가이드 적용
5. 백테스트 / app_walkforward.py 신규 생성 + 스크립트 문서 업데이트

## 7) 리스크(Risks)

- WFO 결과 파일이 없는 경우: `st.warning()`으로 안내 (Fail-safe)
- 전략별 결과 디렉토리가 다를 수 있음: constants.py의 파일명 상수 재사용으로 대응

## 8) 메모(Notes)

- 참고 앱: `scripts/tqqq/spread_lab/app_rate_spread_lab.py` (VERBATIM 패턴, 화면 구성)
- "현재 지표 해석 & 판단(결과)"는 빈칸으로 생성. 사용자가 캡처 후 별도 작성 예정
- WFO 대상 전략: buffer_zone_tqqq, buffer_zone_qqq (run_walkforward.py의 STRATEGY_CONFIG 기준)

### 진행 로그 (KST)

- 2026-03-14 15:00: 계획서 작성
- 2026-03-14 15:30: Phase 1 완료 (app_walkforward.py 구현)
- 2026-03-14 15:30: Phase 2 완료 (문서 업데이트, validate 통과: passed=334, failed=0, skipped=0)
