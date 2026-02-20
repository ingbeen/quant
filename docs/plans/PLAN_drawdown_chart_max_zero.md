# Implementation Plan: 드로우다운 차트 Y축 상한 0 고정

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

**작성일**: 2026-02-20 23:30
**마지막 업데이트**: 2026-02-20 23:40
**관련 범위**: scripts/backtest, vendor/streamlit-lightweight-charts-v5
**관련 문서**: scripts/CLAUDE.md

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

- [x] 드로우다운 차트의 Y축 상한을 0으로 고정하여, 0 이상의 값이 표시되지 않도록 한다

## 2) 비목표(Non-Goals)

- 드로우다운 데이터 계산 로직 변경
- 에쿼티/캔들 차트의 Y축 동작 변경
- Python 측 코드 변경 (이미 `fixedMaxValue: 0` 설정됨)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 드로우다운은 논리적으로 0을 초과할 수 없다 (0 = 최고점, 음수 = 하락폭)
- Python 측에서 `fixedMaxValue: 0`을 설정하고, TSX에서 `autoscaleInfoProvider`로 `maxValue`를 0으로 클램프하고 있으나, 차트 상단에 여전히 0 이상의 영역이 표시됨
- **원인**: lightweight-charts v5의 price scale `scaleMargins` (기본 `top: ~0.2`)가 `autoscaleInfoProvider`의 margins와 독립적으로 적용됨. `scaleMargins.top`은 차트 높이의 비율(0~1)로, autoscale 결과의 maxValue 위에 추가 여백을 생성함
- 참고: [lightweight-charts 공식 문서 - Price Scale](https://tradingview.github.io/lightweight-charts/tutorials/customization/price-scale), [autoscaleInfoProvider Issue #442](https://github.com/tradingview/lightweight-charts/issues/442)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 드로우다운 차트 Y축 상한이 0으로 고정됨 (0 이상 영역 미표시)
- [x] 기존 차트(캔들, 에쿼티) 동작에 영향 없음
- [x] 테스트 추가 불필요 (UI 전용 변경, 비즈니스 로직 변경 없음)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=295, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend/src/LightweightChartsComponent.tsx` — Phase 2.5에서 `fixedMaxValue` 적용 시 해당 시리즈의 price scale `scaleMargins.top`을 0으로 설정

### 데이터/결과 영향

- 출력 데이터/CSV 변경 없음 (UI 표시만 변경)
- 기존 결과 비교 불필요

## 6) 단계별 계획(Phases)

### Phase 1 — TSX fixedMaxValue 처리에 scaleMargins 추가

**작업 내용**:

- [x] `LightweightChartsComponent.tsx`의 Phase 2.5 블록에서, `autoscaleInfoProvider` 적용 직후 해당 시리즈의 price scale에 `scaleMargins: { top: 0, bottom: 0.1 }`을 설정
- [x] TSX 프론트엔드 빌드 수행 (`npm run build`)

구체적 변경 위치: `LightweightChartsComponent.tsx` 약 376행 근처, `autoscaleInfoProvider` applyOptions 호출 직후에 추가:

```typescript
// fixedMaxValue 적용 시 price scale 상단 여백 제거
seriesInstances[paneIndex][seriesIndex].priceScale().applyOptions({
  scaleMargins: {
    top: 0,
    bottom: 0.1,
  },
})
```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=295, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 대시보드 / 드로우다운 차트 Y축 상한 0 고정 (scaleMargins 적용)
2. 대시보드 / 드로우다운 Y축 0 초과 영역 표시 버그 수정
3. 대시보드 / fixedMaxValue 적용 시 price scale 상단 여백 제거
4. 대시보드 / 드로우다운 차트 불필요한 양수 영역 제거
5. 대시보드 / lightweight-charts scaleMargins 보정으로 드로우다운 표시 개선

## 7) 리스크(Risks)

- `scaleMargins.top: 0`으로 설정 시 Y축 최상단 가격 라벨이 잘릴 수 있음 → 드로우다운 값은 항상 0 이하이므로 0이 라벨 최상단에 위치하며, 잘림 위험 낮음
- 다른 시리즈에서 `fixedMaxValue`를 사용할 경우에도 동일하게 `scaleMargins.top: 0`이 적용됨 → 의도된 동작 (fixedMaxValue 사용 = 그 위에 공간이 불필요하다는 의미)

## 8) 메모(Notes)

- lightweight-charts v5.1.0 사용 중
- Python 측 `fixedMaxValue: 0` 설정은 이미 완료되어 있어 변경 불필요
- `autoscaleInfoProvider`의 `margins.above: 0`은 autoscale 범위 내 여백만 제어하며, price scale의 `scaleMargins`는 별도로 차트 영역 외곽 여백을 제어함 → 두 설정 모두 필요

### 진행 로그 (KST)

- 2026-02-20 23:30: 계획서 작성 완료
- 2026-02-20 23:40: Phase 1 완료 (TSX scaleMargins 추가 + 빌드)
- 2026-02-20 23:40: 마지막 Phase 완료 (black + validate_project.py 통과, passed=295, failed=0, skipped=0)

---
