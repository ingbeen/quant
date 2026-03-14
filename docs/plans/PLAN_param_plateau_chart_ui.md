# Plan: 파라미터 고원 대시보드 차트 UI 개선

- 상태: Done
- 작성일: 2026-03-14 15:00

## Goal

`app_parameter_stability.py` 대시보드의 차트 범례-축제목 겹침 해결 및 expander 기본 열림 처리

## Non-Goals

- 차트 로직이나 데이터 변경 없음
- 다른 대시보드 수정 없음

## Context

- 영향받는 규칙: `scripts/CLAUDE.md` (Streamlit 앱 규칙)
- 현재 legend `y=-0.2`가 x축 제목과 겹침 → 범례를 차트 내부 상단 우측으로 이동
- expander 기본 닫힘 → `expanded=True`로 변경

## Definition of Done

- [x] 범례가 x축 제목과 겹치지 않음
- [x] 보조 지표, 거래 수 expander가 기본 열림
- [x] `validate_project.py` 통과

## Scope

- `scripts/backtest/app_parameter_stability.py`: legend 위치 변경 (1곳), expander expanded=True (2곳)

## Phases

### Phase 1: UI 수정 + 검증

1. legend를 차트 내부 우측 상단으로 이동
2. expander 2곳에 `expanded=True` 추가
3. `poetry run python validate_project.py` 실행

## Risks

- 없음 (UI 파라미터만 변경)

## Commit Messages (Final candidates)

1. 대시보드 / 파라미터 고원 차트 범례 겹침 해결 + expander 기본 열림
2. 대시보드 / param plateau 차트 UI 개선 (범례 위치, expander 기본 열림)
3. 대시보드 / 파라미터 고원 시각화 차트 범례-축 겹침 수정 및 expander 열림 기본값 적용
4. 대시보드 / app_parameter_stability 범례 위치 조정 + expander expanded=True
5. 대시보드 / 고원 분석 차트 범례 x축 제목 겹침 해결 및 보조지표-거래수 탭 기본 펼침
