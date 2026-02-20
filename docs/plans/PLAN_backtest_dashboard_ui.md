# Implementation Plan: 백테스트 대시보드 UI 개선

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

**작성일**: 2026-02-20 15:30
**마지막 업데이트**: 2026-02-20 16:00
**관련 범위**: scripts/backtest, vendor
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`

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

- [x] 드로우다운 차트 Y축 최대값을 0으로 고정 (논리적 제약 반영)
- [x] 섹션 순서 변경: 거래내역 → 2번, 파라미터 → 3번, 나머지 하단
- [x] "시그널 차트 + 전략 오버레이" → "메인 차트" 네이밍 변경
- [x] `desc_parts` 코드 제거
- [x] 거래 내역 테이블에 손익률 기반 행별 배경색 추가
- [x] 최대 축소 시 전체 시계열 데이터 표출 (25년치)

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 없음
- 테스트 추가/변경 없음 (Streamlit UI 전용 변경)
- 다른 대시보드 앱(app_daily_comparison, app_rate_spread_lab) 변경 없음
- CSV/JSON 결과 스키마 변경 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **드로우다운 차트 스케일**: auto-scale로 인해 0 위에 여백 발생 → 논리적으로 drawdown_pct ≤ 0 (항상)
2. **섹션 배치**: 거래 내역/파라미터가 히트맵/보유기간 뒤에 배치되어 접근성 저하
3. **헤더 네이밍**: "시그널 차트 + 전략 오버레이"가 특정 전략에 종속적
4. **desc_parts**: 불필요한 설명 텍스트
5. **거래 내역 가독성**: 수익/손실 거래 시각적 구분 불가
6. **줌아웃 제한**: lightweight-charts `minBarSpacing` 기본값(0.5)으로 인해 25년치(~6,300개 바) 전체 표출 불가 (1400px 기준 최대 2,800개)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `scripts/CLAUDE.md` (Streamlit width 규칙 등)
- `src/qbt/backtest/CLAUDE.md` (대시보드 아키텍처, Feature Detection 원칙)
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] 드로우다운 차트 Y축 최대값 0 고정 동작 확인
- [x] 섹션 순서: 1.메인차트 → 2.거래내역 → 3.파라미터 → 4.히트맵 → 5.보유기간
- [x] 헤더 "메인 차트"로 변경 확인
- [x] `desc_parts` 코드 완전 제거 확인
- [x] 거래 내역 행별 손익 배경색 적용 확인
- [x] 최대 축소 시 25년치 전체 데이터 표출 확인
- [x] `poetry run python validate_project.py` 통과 (passed=295, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `vendor/.../LightweightChartsComponent.tsx` | `fixedMaxValue` → `autoscaleInfoProvider` 변환, `minBarSpacing` 타입 추가 |
| `scripts/backtest/app_single_backtest.py` | 섹션 순서, 네이밍, desc_parts 제거, 거래 배경색, drawdown fixedMaxValue, minBarSpacing |
| 프론트엔드 빌드 결과물 | `npm run build` 재빌드 |

### 데이터/결과 영향

- 출력 스키마 변경 없음
- CSV/JSON 결과 변경 없음
- UI 표시만 변경

## 6) 단계별 계획(Phases)

### Phase 1 — TSX 변경 + 프론트엔드 빌드

**작업 내용**:

- [x] **1-1. `fixedMaxValue` 지원 추가**

  파일: `vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend/src/LightweightChartsComponent.tsx`

  위치: "First Phase" 섹션, `seriesOptions` 구성 직후 (시리즈 생성 전)

  시리즈 옵션에 `fixedMaxValue`(숫자)가 있으면 `autoscaleInfoProvider`를 주입하여 Y축 최대값을 고정한다:

  ```typescript
  // fixedMaxValue 지원: Y축 최대값 고정 (예: 드로우다운 차트 0 고정)
  if (seriesOptions.fixedMaxValue !== undefined) {
      const fixedMax = seriesOptions.fixedMaxValue
      delete seriesOptions.fixedMaxValue
      seriesOptions.autoscaleInfoProvider = (original: () => any) => {
          const res = original()
          if (res !== null) {
              res.priceRange.maxValue = fixedMax
          }
          return res
      }
  }
  ```

  API 근거: lightweight-charts v5.1.0 `autoscaleInfoProvider` (typings.d.ts 라인 3983~4028)

- [x] **1-2. `minBarSpacing` 타입 추가**

  `ChartConfig.chart.timeScale` 인터페이스에 `minBarSpacing` 속성 추가:

  ```typescript
  timeScale?: {
      visible?: boolean
      minBarSpacing?: number
  }
  ```

  실제 값은 Python → chart config → `...charts[0].chart` spread → `createChart()` 경로로 전달되므로 별도 처리 로직 불필요. 타입만 추가하면 TypeScript 경고 없이 동작.

- [x] **1-3. 프론트엔드 빌드**

  ```bash
  cd vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend && npm run build
  ```

---

### Phase 2 — Python 변경 (app_single_backtest.py)

**작업 내용**:

- [x] **2-1. `chart_theme`에 `minBarSpacing` 추가**

  `_render_main_chart()` 내부 `chart_theme` dict에 `timeScale` 키 추가:

  ```python
  chart_theme = {
      "layout": {...},
      "grid": {...},
      "crosshair": {...},
      "timeScale": {"minBarSpacing": 0.1},
  }
  ```

  `minBarSpacing=0.1` → 1400px 기준 최대 14,000개 바 표출 가능 (25년×252일 ≈ 6,300개 충분)

- [x] **2-2. 드로우다운 시리즈에 `fixedMaxValue` 추가**

  pane3 (드로우다운) Area 시리즈 `options`에 `"fixedMaxValue": 0` 추가:

  ```python
  "options": {
      "lineColor": COLOR_DRAWDOWN_LINE,
      "topColor": COLOR_DRAWDOWN_TOP,
      "bottomColor": COLOR_DRAWDOWN_BOTTOM,
      "lineWidth": 2,
      "priceLineVisible": False,
      "priceFormat": {"type": "price", "precision": 2, "minMove": 0.01},
      "invertFilledArea": True,
      "fixedMaxValue": 0,
  }
  ```

- [x] **2-3. 섹션 순서 변경**

  `_render_strategy_tab()` 내부 섹션 순서 재배치:

  | 현재 | 변경 후 |
  |------|---------|
  | 요약 지표 (상단, 번호 없음) | 요약 지표 (상단, 번호 없음) |
  | 1. 시그널 차트 + 전략 오버레이 | 1. 메인 차트 |
  | 2. 월별/연도별 수익률 히트맵 | **2. 전체 거래 상세 내역** |
  | 3. 포지션 보유 기간 분포 | **3. 사용 파라미터** |
  | 4. 전체 거래 상세 내역 | **4. 월별/연도별 수익률 히트맵** |
  | 5. 사용 파라미터 | **5. 포지션 보유 기간 분포** |

- [x] **2-4. 헤더 네이밍 변경**

  `st.header("1. 시그널 차트 + 전략 오버레이")` → `st.header("1. 메인 차트")`

- [x] **2-5. `desc_parts` 코드 제거**

  삭제 대상 (679~691행 부근):
  - `ma_col = _detect_ma_col(...)` (탭 렌더링 내부 중복 — `_render_main_chart`에서 이미 감지)
  - `has_bands = "upper_band" in ...` (동일 이유)
  - `desc_parts` 리스트 구성 전체
  - `st.markdown(" | ".join(desc_parts))` 호출

- [x] **2-6. 거래 내역 테이블 행별 배경색**

  모듈 레벨에 스타일 함수 추가:

  ```python
  def _style_pnl_rows(row: pd.Series) -> list[str]:
      """손익률 기반 행별 배경색을 반환한다."""
      pnl_col = TRADE_COLUMN_RENAME.get("pnl_pct", "손익률")
      pnl = row.get(pnl_col, 0)
      if pnl > 0:
          return [f"background-color: rgba(38, 166, 154, 0.15)"] * len(row)
      elif pnl < 0:
          return [f"background-color: rgba(239, 83, 80, 0.15)"] * len(row)
      return [""] * len(row)
  ```

  거래 내역 렌더링 부분에서 Styler 적용:

  ```python
  styled_df = display_df.style.apply(_style_pnl_rows, axis=1)
  st.dataframe(styled_df, width="stretch")
  ```

  색상: `COLOR_UP`/`COLOR_DOWN`과 동일 계열 (rgba, 투명도 0.15)

---

### 마지막 Phase — 포맷팅 및 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=295, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 드로우다운 0고정 + 섹션순서 변경 + 거래내역 배경색 + 전체데이터 표출
2. 대시보드 / UI 개선 6건 (드로우다운·섹션순서·네이밍·거래배경색·줌아웃)
3. 대시보드 / 백테스트 대시보드 사용성 개선 (차트·테이블·레이아웃)
4. 대시보드 / 드로우다운 Y축 고정 + minBarSpacing 전체표출 + 섹션 리팩토링
5. 대시보드 / 차트 스케일 수정 + 레이아웃 개선 + 거래내역 시각화 강화

## 7) 리스크(Risks)

- **TSX 빌드 실패**: npm run build 실패 시 앱 미동작 → 빌드 로그 확인 후 즉시 수정
- **pandas Styler 호환성**: `st.dataframe(styler, width="stretch")` → Streamlit 최신 버전에서 지원됨

## 8) 메모(Notes)

- lightweight-charts v5.1.0의 `autoscaleInfoProvider` API 활용 (typings.d.ts 확인 완료)
- `minBarSpacing` 기본값 0.5 → 0.1로 설정하여 최대 14,000개 바 표출 가능
- `fixedMaxValue`는 JSON 직렬화 가능한 숫자값으로 Python에서 전달, TSX에서 `autoscaleInfoProvider` 함수로 변환
- Phase 0 불필요: 핵심 인바리언트/정책 변경 없음 (순수 UI 변경)

### 진행 로그 (KST)

- 2026-02-20 15:30: Draft 작성
- 2026-02-20 16:00: 전체 구현 완료 (Phase 1~마지막 Phase), validate_project.py 통과 (295 passed, 0 failed, 0 skipped)
