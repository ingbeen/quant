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

**작성일**: 2026-02-19 (KST)
**마지막 업데이트**: 2026-02-19 (KST)
**관련 범위**: scripts/backtest
**관련 문서**: `scripts/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`

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

- [x] 목표 1: Buy/Sell 마커를 size+color로 더 강조하여 가시성 향상
- [x] 목표 2: 전일대비(%) Pane 제거로 차트 영역 간소화
- [x] 목표 3: 드로우다운을 에쿼티 아래 pane으로 통합 (크로스헤어 연동)
- [x] 목표 4: 섹션 순서 변경 (차트 → 히트맵 → 보유기간분포 → 거래내역 → 파라미터)
- [x] 목표 5: 버퍼 밴드 라인을 살짝 굵고 진하게 (이동평균선보다 덜 강조)

## 2) 비목표(Non-Goals)

- 커스텀 툴팁 구현 (Streamlit 컴포넌트 제약, 사용자 확인 완료)
- 마커 텍스트의 폰트크기/굵기/뒷배경 변경 (lightweight-charts API 제약, 사용자 확인 완료)
- `run_single_backtest.py` 변경 (데이터 생성 로직은 변경 없음)
- 비즈니스 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- Buy/Sell 마커가 size=1로 작아서 눈에 잘 띄지 않음
- 전일대비(%) Pane이 차트 공간을 차지하지만 활용도가 낮음
- 드로우다운이 별도 차트로 분리되어 에쿼티와 크로스헤어 연동이 안 됨
- 섹션 순서가 사용자 의도와 다름
- 버퍼 밴드 라인이 너무 얇아 잘 보이지 않음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `scripts/CLAUDE.md` (CLI 스크립트 / Streamlit 앱 규칙)
- `src/qbt/backtest/CLAUDE.md` (백테스트 도메인)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] 기능 요구사항 충족 (5개 항목 모두)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `scripts/backtest/app_single_backtest.py` (유일한 변경 대상)

### 데이터/결과 영향

- 출력 데이터(CSV/JSON) 변경 없음
- UI 레이아웃만 변경

## 6) 단계별 계획(Phases)

### Phase 1 — UI 변경 (단일 파일 수정)

**대상 파일**: `scripts/backtest/app_single_backtest.py`

**1-1. 로컬 상수 변경**

- [x] `DEFAULT_CHANGE_PANE_HEIGHT` 제거
- [x] `COLOR_CHANGE_POSITIVE`, `COLOR_CHANGE_NEGATIVE` 제거
- [x] `DEFAULT_DRAWDOWN_CHART_HEIGHT` → 메인 차트 내 드로우다운 pane 높이로 변경 (300 → 150)

**1-2. 마커 강조 (`_build_markers` 함수)**

현재:
```python
# Buy 마커
"size": 1

# Sell 마커
"size": 1
```

변경:
```python
# Buy 마커
"size": 2

# Sell 마커
"size": 2
```

- [x] Buy/Sell 마커 size를 1 → 2로 변경

**1-3. 버퍼 밴드 강조 (`_render_main_chart` 함수 내)**

현재:
```python
# Upper Band
"color": "rgba(33, 150, 243, 0.4)",
"lineWidth": 1,

# Lower Band
"color": "rgba(244, 67, 54, 0.4)",
"lineWidth": 1,
```

변경:
```python
# Upper Band
"color": "rgba(33, 150, 243, 0.6)",
"lineWidth": 2,

# Lower Band
"color": "rgba(244, 67, 54, 0.6)",
"lineWidth": 2,
```

- [x] Upper/Lower Band의 lineWidth를 1 → 2, opacity를 0.4 → 0.6으로 변경
- [x] 이동평균선(lineWidth: 2, opacity: 0.9)보다 덜 강조되는지 확인

**1-4. 전일대비 Pane 제거 + 드로우다운 통합 (`_render_main_chart` 함수)**

현재 pane 구성:
- Pane 1: 캔들+MA+밴드+마커 (height=500)
- Pane 2: 전일대비% Histogram (height=100)
- Pane 3: 에쿼티 (height=200)

변경 후 pane 구성:
- Pane 1: 캔들+MA+밴드+마커 (height=500)
- Pane 2: 에쿼티 (height=200)
- Pane 3: 드로우다운 (height=150)

작업 내용:
- [x] `_build_change_pct_data` 함수 호출 제거
- [x] pane2 (전일대비 Histogram) 제거
- [x] 드로우다운 데이터를 빌드하여 pane3으로 추가 (`_build_drawdown_data` 호출)
- [x] `_render_main_chart` 시그니처는 그대로 유지 (equity_df에서 drawdown_pct 접근 가능)
- [x] total_height 계산 업데이트 (500 + 200 + 150 = 850)

**1-5. 불필요한 함수/상수 정리**

- [x] `_build_change_pct_data` 함수 제거
- [x] `_render_drawdown_chart` 함수 제거
- [x] 미사용 상수 제거 (`DEFAULT_CHANGE_PANE_HEIGHT`, `COLOR_CHANGE_POSITIVE`, `COLOR_CHANGE_NEGATIVE`)

**1-6. 섹션 순서 변경 (`main()` 함수)**

현재 순서:
1. 요약 지표
2. 메인 차트 (QQQ 시그널 + 전략 오버레이)
3. 드로우다운
4. 월별 수익률 히트맵
5. 포지션 보유 기간 분포
6. 사용 파라미터
7. 전체 거래 상세 내역

변경 후 순서:
1. 요약 지표
2. 메인 차트 (QQQ 시그널 + 전략 오버레이 + 에쿼티 + 드로우다운)
3. 월별 수익률 히트맵
4. 포지션 보유 기간 분포
5. 전체 거래 상세 내역
6. 사용 파라미터

- [x] 드로우다운 섹션 제거 (차트에 통합됨)
- [x] "전체 거래 상세 내역"을 "사용 파라미터" 앞으로 이동
- [x] 섹션 번호 재정렬 (1~5)

---

### Phase 2 (마지막) — 포맷 및 최종 검증

**작업 내용**

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] Streamlit 앱 실행하여 시각적 검증 (수동)
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 대시보드 UI 개선 (마커 강조, 드로우다운 통합, 레이아웃 재정렬)
2. 백테스트 / 대시보드 마커 강조 및 전일대비 Pane 제거
3. 백테스트 / 대시보드 차트 레이아웃 리팩토링 (드로우다운 통합, 순서 변경)
4. 백테스트 / 단일 전략 대시보드 시각화 개선
5. 백테스트 / 대시보드 UI 리팩토링 (마커/밴드 강조, 레이아웃 정리)

## 7) 리스크(Risks)

- 드로우다운 pane을 메인 차트에 통합 시 높이 비율이 의도와 다를 수 있음 → height 값 조정으로 대응
- 마커 size=2가 과도할 수 있음 → 실행 후 시각적 확인 필요

## 8) 메모(Notes)

### 사용자 확인 사항 (계획서 작성 전 확인 완료)

- 마커 폰트크기/굵기/뒷배경: lightweight-charts API 미지원 → size+color로 대체 (사용자 동의)
- 커스텀 툴팁: Streamlit 컴포넌트 제약 → 생략 (사용자 동의)
- 전일대비 Pane: 제거만 진행 (사용자 동의)

### 기술 조사 결과

- lightweight-charts v5 마커 API: `size`, `shape`, `color`, `text`, `position`만 지원
- Streamlit 컴포넌트(v0.1.8): `subscribeCrosshairMove` 미연결, `customValues` 지원은 됨
- 다중 pane: 단일 차트 인스턴스 내 크로스헤어 자동 연동

### 진행 로그 (KST)

- 2026-02-19: Plan 작성 (구현 가능성 분석 및 사용자 확인 완료)
- 2026-02-19: 구현 완료 및 검증 통과 (passed=284, failed=0, skipped=0)

---
