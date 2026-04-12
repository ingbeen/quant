---
상태: Done
작성일: 2026-04-12 21:00
마지막 업데이트: 2026-04-12 21:00
---

# Plan: drift 통합 (drift_pct 0~1 + model_value=0 + round 제거) + 테스트 내구성

## Goal

1. drift_pct 를 QBT 원칙(0~1 범위)으로 통일. RTDB 는 × 100 변환하여 앱 호환 유지.
2. per_asset drift 에서 model_value=0 + actual_value>0 일 때 drift_pct=1.0 (100%) 반환.
3. balance_adjust cash 정수 반올림 제거.
4. 테스트 티커 하드코딩 → 동적 추출.

## Non-Goals

- RTDB 스키마 변경 (앱 호환성 유지)
- drift recommendation 문자열 상수화 (이번 범위 외)

## Context

Q1(drift_pct 0~100→0~1), Q2(round 제거), Q3(model_value=0) 확정 사항 반영.

영향받는 규칙:

- [CLAUDE.md](../../CLAUDE.md) — 비율 표기 규칙 (`_pct` = 0~1)
- [live/CLAUDE.md](../../live/CLAUDE.md)

## Definition of Done

- [x] drift.compute_drift: drift_pct 0~1 반환 (× 100 제거)
- [x] drift.compute_drift: model_value=0 + actual_value>0 → asset_drift_pct=1.0
- [x] balance_adjust: cash round() 제거
- [x] 소비자 코드 갱신 (notifier, cli 로그)
- [x] rtdb_gateway: RTDB 쓸 때 × 100 변환
- [x] 테스트 전체 갱신
- [x] 테스트 티커 하드코딩 → 동적 추출
- [x] `poetry run python validate_project.py` passed failed=0 skipped=0
- [ ] README.md 변경 없음

## Scope

| 파일 | 변경 내용 |
|------|----------|
| `live/src/live/drift.py` | drift_pct 0~1 + model_value=0 처리 |
| `live/src/live/models.py` | drift_pct 주석 갱신 |
| `live/src/live/notifier.py` | 표시 시 × 100 |
| `live/src/live/cli.py` | 로그 표시 시 × 100 |
| `live/src/live/rtdb_gateway.py` | RTDB 쓸 때 × 100 |
| `live/src/live/balance_adjust.py` | round() 제거 |
| `live/tests/test_drift.py` | 기대값 갱신 |
| `live/tests/test_daily_runner.py` | 기대값 갱신 |
| `live/tests/test_notifier.py` | 기대값 갱신 |
| `live/tests/test_rtdb_gateway.py` | 기대값 갱신 |
| `live/tests/test_alert_coverage.py` | 티커 동적 추출 |

## Phase 1 — drift_pct 0~1 + model_value=0 + round 제거 + 테스트

단일 Phase. 변경 순서:

1. drift.py: `× 100.0` 제거, 반올림 4자리, model_value=0 분기 추가
2. models.py: drift_pct 주석 갱신
3. notifier.py: `{drift_pct * 100:.2f}%` 형식
4. cli.py: 로그 `{drift_pct * 100:.2f}%` 형식
5. rtdb_gateway.py: `"drift_pct": result.drift_pct * 100`
6. balance_adjust.py: `round()` 제거
7. 테스트 전체 기대값 갱신 + 티커 동적 추출

Validation: `poetry run python validate_project.py`

## Risks

- 영향 범위 22곳. 단일 계산원(drift.compute_drift)에서 시작하므로 변경 누락 위험 낮음.
- RTDB × 100 변환으로 앱 호환성 유지.

## Commit Messages (Final candidates)

1. `live / drift_pct QBT 원칙(0~1) 통일 + model_value=0 처리 + round 제거`
2. `live / drift 비율 0~1 정규화 + per-asset 100% 이탈 감지 + cash round 제거`
3. `live / drift_pct 범위 통일(0~1) + RTDB 호환 유지 + balance_adjust round 제거`
4. `live / QBT 비율 원칙 적용: drift_pct 0~1 + model_value=0 방어 + 테스트 갱신`
5. `live / drift 비율 범위 정규화 + 자산별 100% 이탈 감지 + 테스트 내구성`
