# Implementation Plan: 대시보드 차트 초기 로드 시 전체 데이터 표시

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-20 18:00
**마지막 업데이트**: 2026-02-20 18:00
**관련 범위**: scripts/backtest (대시보드 앱)
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

- [ ] 대시보드 차트 초기 로드 시 전체 데이터가 보이도록 fitContent 활성화
- [ ] 기존 scroll_padding=60 (앞뒤 2~3개월 여유) 스크롤 제한 조건 유지

## 2) 비목표(Non-Goals)

- vendor fork TSX 코드 수정 (기존 TSX의 fitContent 폴백 로직을 활용)
- 새로운 컴포넌트 파라미터 추가
- 비즈니스 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- 현재 `DEFAULT_ZOOM_LEVEL = 200`으로 설정되어 초기 로드 시 마지막 200봉만 표시
- 사용자는 초기 로드 시 전체 시계열 흐름을 한눈에 보고 싶어함
- TSX 프론트엔드에 이미 구현된 폴백 로직 활용 가능:
  - `dataLength < zoom_level`이면 `timeScale().fitContent()` 자동 호출
  - `fitContent()`는 전체 데이터를 차트 너비에 맞춰 표시
- `scroll_padding=60`은 독립적으로 동작하며 fitContent와 무관

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 차트 초기 로드 시 전체 데이터가 fitContent로 표시됨
- [ ] scroll_padding=60 스크롤 제한 조건 유지됨
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `scripts/backtest/app_single_backtest.py`: `DEFAULT_ZOOM_LEVEL` 상수 값 변경 (1줄)

### 데이터/결과 영향

- 출력 데이터 변경 없음
- 대시보드 UI 초기 표시 범위만 변경

## 6) 단계별 계획(Phases)

### Phase 1 — 상수 변경 (그린 유지)

**작업 내용**:

- [ ] `DEFAULT_ZOOM_LEVEL = 200`을 충분히 큰 값으로 변경하여 fitContent 폴백 활성화
- [ ] 주석 업데이트: fitContent 동작 원리 설명

**동작 원리**:

TSX 프론트엔드의 기존 로직:
```typescript
if (mainSeriesData?.length >= zoom_level) {
  // zoom_level만큼 마지막 N봉 표시
  chartRef.current.timeScale().setVisibleRange({...})
} else {
  // 데이터가 zoom_level보다 적으면 전체 표시
  chartRef.current.timeScale().fitContent()
}
```

`zoom_level`을 데이터 길이보다 충분히 큰 값(99999)으로 설정하면 항상 `fitContent()` 폴백이 실행된다.

---

### Phase 2 (마지막) — 최종 검증

**작업 내용**

- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. 대시보드 / 차트 초기 로드 시 전체 데이터 표시 (fitContent 활성화)
2. 대시보드 / 초기 줌 레벨을 전체 표시로 변경 (zoom_level fitContent 폴백)
3. 대시보드 / 차트 기본 뷰를 전체 데이터 범위로 확장
4. 대시보드 / 메인 차트 초기 뷰 전체 데이터 fitContent 적용
5. 대시보드 / 차트 최초 로드 시 전체 흐름 표시되도록 줌 레벨 변경

## 7) 리스크(Risks)

- 리스크 거의 없음: UI 초기 표시만 변경, 비즈니스 로직 무관
- fitContent()는 lightweight-charts 공식 API로 안정적

## 8) 메모(Notes)

- TSX 코드 위치: `vendor/streamlit-lightweight-charts-v5/.../LightweightChartsComponent.tsx` 683~693행
- fitContent()는 lightweight-charts v5 TimeScale API 표준 메서드
- scroll_padding=60은 subscribeVisibleLogicalRangeChange 기반 독립 로직으로 fitContent와 충돌 없음

### 진행 로그 (KST)

- 2026-02-20 18:00: Plan 작성 완료

---
