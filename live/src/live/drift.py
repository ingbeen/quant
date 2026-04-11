"""fill 자동 매칭 및 drift 계산 모듈.

Step 8에서 다음 함수들이 구현된다 (설계서 6장, 14장, 부록 A 참고).

- ``classify_fill(fill: ActualFill, state: LiveState) -> str``
    반환: ``"system_fill"`` | ``"personal_trade"``
- ``apply_fills_idempotent(state, fills, applied_ids) -> tuple[LiveState, set[str]]``
    applied_fill_ids 로 중복 방지.
- ``compute_drift(state, closes) -> DriftReport``
    ``drift_pct = abs(model_equity - actual_equity) / model_equity * 100``
    0~3% 정상 / 3~5% 주의 / 5%+ 보정 필요.
"""
