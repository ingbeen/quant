# Implementation Plan: WFO 대시보드 전략 통합 뷰

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

**작성일**: 2026-03-14 16:00
**마지막 업데이트**: 2026-03-14 16:30
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

- [x] 전략별 탭(QQQ/TQQQ)을 제거하고 단일 통합 뷰로 변경
- [x] 5개 섹션 모두 QQQ와 TQQQ를 나란히 비교할 수 있는 레이아웃 적용
- [x] VERBATIM 텍스트는 기존 내용 유지 (이미 QQQ/TQQQ 모두 언급)

## 2) 비목표(Non-Goals)

- 비즈니스 로직(`src/qbt/`) 변경 없음
- 테스트 추가 없음 (Streamlit 앱은 테스트 대상 아님)
- VERBATIM 해석 내용 변경 없음
- 새로운 지표/차트 추가 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 QQQ와 TQQQ가 별도 탭으로 분리되어 있어 두 전략을 비교하려면 탭을 오가야 함
- 같은 섹션(예: Stitched Equity)을 나란히 보면서 비교하는 것이 불가능
- 통합 뷰로 변경하면 한 화면에서 QQQ vs TQQQ 차이를 즉시 파악 가능

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md` (Streamlit 앱 규칙: `width="stretch"`, `use_container_width` 금지 등)
- `src/qbt/backtest/CLAUDE.md` (WFO 타입/상수 참조)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 탭 제거, 단일 통합 뷰로 변경
- [x] 섹션 1: 4열 테이블 (QQQ Dynamic / QQQ Fixed / TQQQ Dynamic / TQQQ Fixed)
- [x] 섹션 2: `make_subplots(1, 2)` 좌우 배치 (좌=QQQ, 우=TQQQ)
- [x] 섹션 3: `make_subplots(1, 2)` 좌우 배치 (CAGR 한 쌍, Calmar 한 쌍)
- [x] 섹션 4: 서브플롯에 QQQ/TQQQ 2라인 오버레이
- [x] 섹션 5: `make_subplots(1, 2)` 좌우 배치 (좌=QQQ, 우=TQQQ)
- [x] VERBATIM 텍스트 유지
- [x] 전략 1개만 존재 시 graceful fallback
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_walkforward.py` (기존 파일 수정)

### 데이터/결과 영향

- 읽기 전용: 기존 WFO 결과 파일을 로드하여 시각화만 수행
- 출력 스키마 변경 없음

## 6) 단계별 계획(Phases)

### Phase 1 — 통합 뷰 구현 (그린 유지)

**레이아웃 변경 요약**:

| 섹션 | 현재 | 변경 후 |
|------|------|---------|
| 1. 모드별 요약 | `st.metric` 2열 (D/F) | `st.dataframe` 4열 (QQQ D/F, TQQQ D/F) |
| 2. Stitched Equity | 단일 Figure 2라인 | `make_subplots(1,2)` 좌=QQQ, 우=TQQQ |
| 3. IS vs OOS | 단일 Grouped Bar | `make_subplots(1,2)` 좌=QQQ, 우=TQQQ (CAGR/Calmar 각각) |
| 4. 파라미터 추이 | 5 서브플롯 1라인 | 5 서브플롯 2라인 오버레이 (QQQ+TQQQ) |
| 5. WFE 분포 | 단일 Bar | `make_subplots(1,2)` 좌=QQQ, 우=TQQQ (Calmar/CAGR 각각) |

**작업 내용**:

- [x] 탭 구조 제거, `_discover_wfo_strategies()` 결과를 dict로 전환
- [x] 섹션 1: `_render_mode_summary()` → 4열 DataFrame 기반 비교 테이블
- [x] 섹션 2: `_render_stitched_equity()` → `make_subplots(1,2)` 좌우 배치
- [x] 섹션 3: `_render_is_vs_oos()` → `make_subplots(1,2)` 좌우 배치
- [x] 섹션 4: `_render_param_drift()` → 2라인 오버레이
- [x] 섹션 5: `_render_wfe_distribution()` → `make_subplots(1,2)` 좌우 배치
- [x] 전략 1개만 존재 시 단일 전략으로 표시 (빈 열/서브플롯은 "데이터 없음")

---

### Phase 2 (마지막) — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=334, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / WFO 앱 전략 통합 뷰 전환 (탭 → 나란히 비교)
2. 대시보드 / app_walkforward QQQ·TQQQ 통합 레이아웃 적용
3. 대시보드 / WFO 대시보드 탭 제거 + 전략 비교 뷰 구현
4. 백테스트 / WFO 시각화 전략별 탭을 단일 비교 뷰로 통합
5. 대시보드 / WFO 결과 QQQ vs TQQQ 나란히 비교 UI 전환

## 7) 리스크(Risks)

- equity 스케일 차이 (QQQ vs TQQQ): 좌우 분리 서브플롯으로 각각 독립 Y축 사용하여 해결
- 전략이 1개만 있을 때: 빈 서브플롯에 "데이터 없음" 안내로 graceful fallback

## 8) 메모(Notes)

- 기존 VERBATIM 텍스트는 이미 QQQ/TQQQ 구분하여 작성되어 있어 변경 불필요
- `_STRATEGY_DISPLAY_NAMES` 매핑 유지
- 차트 색상 규칙: Dynamic=파란(#1f77b4), Fully Fixed=주황(#ff7f0e)

### 진행 로그 (KST)

- 2026-03-14 16:00: 계획서 작성
- 2026-03-14 16:30: Phase 1 완료 (통합 뷰 구현)
- 2026-03-14 16:30: Phase 2 완료 (validate 통과: passed=334, failed=0, skipped=0)
