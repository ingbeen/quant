---
상태: Done
작성일: 2026-04-12 20:30
마지막 업데이트: 2026-04-12 20:30
---

# Plan: direction 검증 강화 + fills RTDB 마킹 수정

## Goal

1. ActualFill.direction 타입을 `str` → `Literal["buy", "sell"]`로 강화하고,
   입구(rtdb_gateway)와 내부(drift)에 런타임 검증을 추가하여 unknown direction이
   조용히 무시되는 버그를 제거한다.
2. rtdb_gateway._dict_to_balance_adjust의 null값 검증 갭을 보강한다.
3. fills RTDB 마킹에서 ALL keys → NEW keys로 변경하여 불필요한 RTDB write를 제거한다.

## Non-Goals

- cli.py 구조 분리 (예외 규칙으로 대체 완료)

## Context

live/ 전수 분석에서 발견된 버그(8-1), 불가능 값 중단 누락(9-1, 9-2), 비일관 마킹(4-1).

영향받는 규칙:

- [CLAUDE.md](../../CLAUDE.md) — 불가능 조건 처리 (RuntimeError), 입력 검증 (ValueError)
- [live/CLAUDE.md](../../live/CLAUDE.md) — fail-fast 정책

## Definition of Done

- [x] ActualFill.direction → Literal["buy", "sell"]
- [x] rtdb_gateway._dict_to_actual_fill에 direction 값 검증 추가
- [x] drift._apply_single_fill에 else RuntimeError 추가
- [x] rtdb_gateway._dict_to_balance_adjust null값 검증 강화
- [x] cli._publish_to_rtdb fills 마킹 → NEW keys only
- [x] 테스트 추가/수정
- [x] `poetry run python validate_project.py` passed failed=0 skipped=0
- [ ] README.md 변경 없음

## Scope

| 파일 | 변경 내용 |
|------|----------|
| `live/src/live/models.py` | direction 타입 강화 |
| `live/src/live/rtdb_gateway.py` | direction 검증 + balance_adjust null 검증 |
| `live/src/live/drift.py` | else RuntimeError |
| `live/src/live/cli.py` | fills 마킹 NEW keys only |
| `live/tests/test_drift.py` | unknown direction 테스트 |
| `live/tests/test_rtdb_gateway.py` | direction 검증 / null값 테스트 |

## Phase 1 — 타입 강화 + 검증 + fills 마킹 (단일 Phase)

1. models.py: `ActualFill.direction: str` → `Literal["buy", "sell"]`
2. rtdb_gateway._dict_to_actual_fill: direction 값 검증 추가
3. drift._apply_single_fill: else 분기에 RuntimeError 추가
4. rtdb_gateway._dict_to_balance_adjust: new_shares/new_cash 둘 다 None인 경우 검증
5. cli._publish_to_rtdb: processed_keys를 NEW keys로 변경
6. 테스트 추가

Validation: `poetry run python validate_project.py`

## Risks

- direction 타입 변경은 models.py의 dataclass 필드만 영향. 기존 테스트가 "buy"/"sell"만
  사용하므로 호환성 문제 없음.

## Commit Messages (Final candidates)

1. `live / direction 타입 강화 + fills 마킹 최적화 + null 검증 보강`
2. `live / ActualFill direction Literal 타입 + fail-fast 검증 + NEW keys 마킹`
3. `live / 입력 검증 강화 (direction·balance_adjust) + fills 마킹 비일관 수정`
4. `live / direction 검증 체인 + balance_adjust null 방어 + fills RTDB 최적화`
5. `live / 버그 수정: unknown direction 무시 + fills 전체 마킹 → 신규만`
