"""LiveState 직렬화/역직렬화 및 초기화 모듈.

Step 3에서 다음 함수들이 구현된다 (설계서 부록 A, 5장 참고).

- ``load_state(path: Path) -> LiveState``
- ``save_state(state: LiveState, path: Path) -> None``
- ``create_initial_state(total_capital: float) -> LiveState``
- ``load_applied_fill_ids(path: Path) -> set[str]``
- ``save_applied_fill_ids(ids: set[str], path: Path) -> None``
- ``cleanup_old_fill_ids(ids: set[str], max_age_days: int = 90) -> set[str]``

원칙: 파일 I/O 는 반드시 ``pathlib.Path`` 사용, 파일 손상 시 ``ValueError`` 로 즉시 중단.
"""
