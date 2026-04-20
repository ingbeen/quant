# Implementation Plan: 포트폴리오 대시보드 월별/연간 수익률 히트맵 색상 스케일 분리

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

**작성일**: 2026-04-20 (KST)
**마지막 업데이트**: 2026-04-20 (KST)
**관련 범위**: scripts/backtest
**관련 문서**: [scripts/CLAUDE.md](../../scripts/CLAUDE.md)

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다.
- Phase 0은 "레드", Phase 1부터는 **그린 유지**.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**.
- 스킵은 가능하면 **Phase 분해로 제거**.

---

## 1) 목표(Goal)

- [x] 월별 수익률 히트맵의 "월(12열)"과 "연간(1열)" 색상 스케일을 독립적으로 분리한다
- [x] 단일 Plotly figure 내에서 `make_subplots(rows=1, cols=2, column_widths=[12, 1], shared_yaxes=True)`로 정렬 유지
- [x] 좌(월별) / 우(연간) 각자 자기 데이터의 `max_abs` 기준으로 대칭 색상 스케일 적용

## 2) 비목표(Non-Goals)

- summary.json 스키마 변경 (`monthly_returns`, `yearly_returns` 그대로 사용)
- 다른 대시보드의 월별 수익률 위젯 일괄 변경 (포트폴리오 대시보드 한정)
- 테스트 추가 (순수 시각화 레이아웃 변경 — 기존 회귀 테스트 커버리지로 충분)

## 3) 배경/맥락(Context)

### 현재 문제점

- [app_portfolio_backtest.py:458-475](../../scripts/backtest/app_portfolio_backtest.py#L458-L475): `max_abs`를 월간+연간 전체 값으로 계산 → 연간 수익률이 월간보다 훨씬 크므로 color 스케일을 연간이 주도
- 결과: 월별 셀이 흰색에 가깝게 나와 양/음 구분이 약하고, 연간 셀만 두드러짐

### 영향받는 규칙

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [scripts/CLAUDE.md](../../scripts/CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)

## 4) 완료 조건(Definition of Done)

- [x] 월별(1~12월) Heatmap과 연간(1열) Heatmap이 `make_subplots`로 같은 figure 안에서 나란히 표시
- [x] 각 Heatmap이 자기 데이터의 `max_abs` 기준 대칭 색상 스케일을 사용
- [x] 연도(y축)가 두 subplot에서 동일하게 정렬 (`shared_yaxes=True`)
- [x] 컬러바 두 개가 우측에 충돌 없이 표시 (x 위치 1.02 / 1.14, `margin.r=160`)
- [x] 각 셀의 텍스트(예: `3.21%`)와 hover가 기존과 동일하게 동작
- [x] `poetry run python validate_project.py` 통과 (passed=1023, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (파일 변경 없음)
- [x] 문서 업데이트: README.md 변경 없음 / docs/COMMANDS.md 변경 없음 / CLAUDE.md 변경 없음
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- [scripts/backtest/app_portfolio_backtest.py](../../scripts/backtest/app_portfolio_backtest.py): `_render_monthly_returns_section()` 함수 내부 구현 교체
- `README.md`: 변경 없음
- `docs/COMMANDS.md`: 변경 없음 (실행 명령어 동일)
- CLAUDE.md: 변경 없음 (대시보드 섹션 설명은 "월별 수익률 히트맵" 상위 설명 그대로 유효)

### 데이터/결과 영향

- 출력 스키마: 변경 없음
- 사용자 경험: 월별 셀의 색 대비가 개선됨, 연간 셀은 독립 스케일로 자연스러움

## 6) 단계별 계획(Phases)

### Phase 1 — `_render_monthly_returns_section()` 교체

**작업 내용**:

- [x] `z_data`를 `z_monthly (years × 12)` + `z_yearly (years × 1)` 두 행렬로 분리
- [x] 각 행렬의 `max_abs_*` 독립 계산 (빈 값 방어)
- [x] `from plotly.subplots import make_subplots` 이미 import되어 있음을 확인
- [x] `fig = make_subplots(rows=1, cols=2, column_widths=[12, 1], shared_yaxes=True, horizontal_spacing=0.02)`
- [x] 좌 trace: `go.Heatmap(z=z_monthly, x=month_labels, y=year_labels, coloraxis="coloraxis", ...)`
- [x] 우 trace: `go.Heatmap(z=z_yearly, x=["연간"], y=year_labels, coloraxis="coloraxis2", ...)`
- [x] `fig.update_layout(coloraxis=..., coloraxis2=..., margin={r: 160})` (colorbar x=1.02/1.14, len=0.9)
- [x] 두 subplot 모두 `xaxis.side="top"`, y축 `autorange="reversed"` 유지
- [x] 높이 계산식 기존과 동일하게 유지
- [x] texttemplate/hovertemplate 기존과 동일 유지

---

### 마지막 Phase — 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=1023, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 월별·연간 수익률 히트맵 색상 스케일 분리
2. 대시보드 / 포트폴리오 월별 수익률 대비 개선 — 연간 열 독립 coloraxis
3. 대시보드 / make_subplots 도입으로 월/연 히트맵 스케일 분리
4. 대시보드 / 월별 히트맵 가독성 개선 (연간 열 별도 색상축)
5. 대시보드 / _render_monthly_returns_section 월/연 분리 렌더링

## 7) 리스크(Risks)

- 두 컬러바가 차트 영역을 침범할 수 있음 → `colorbar.x` 값을 1.02 / 1.14로 분리하고 `margin.right`를 Streamlit 기본값에 맡기되, 필요시 `update_layout(margin=dict(r=140))` 보강
- 연도(y축) 연도 레이블이 좌측 subplot에만 보이고 우측에는 숨겨질 수 있으나, `shared_yaxes=True`로 같은 축 공유 → 자동 처리

## 8) 메모(Notes)

- Plotly에서 `coloraxis2`는 layout에 선언하면 생성됨 (`coloraxis`, `coloraxis2`, `coloraxis3`...)
- Heatmap trace에서 `colorscale/zmin/zmax`를 지정하면 coloraxis와 충돌 — coloraxis 사용 시 이들 속성 제거 필요
- texttemplate은 trace-level이므로 각 Heatmap에 개별 지정

### 진행 로그 (KST)

- 2026-04-20: 계획서 작성 및 In Progress 시작
- 2026-04-20: Phase 1 구현 완료 — `make_subplots(cols=2, column_widths=[12, 1])`로 월별/연간 Heatmap 분리, coloraxis/coloraxis2로 독립 색상 스케일 적용
- 2026-04-20: `validate_project.py` 통과 (passed=1023, failed=0, skipped=0). 상태 → Done
