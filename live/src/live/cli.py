"""live 도메인 CLI 엔트리포인트.

Step 10에서 다음 명령어들이 구현된다 (설계서 부록 A 참고).

- ``run-daily``: 일일 실행 메인 루프
- ``init``: ``live_state.json`` 초기화 (자본금 지정)
- ``init-data``: yfinance 로 6종 주가 CSV 초기 다운로드
- ``rebuild-data``: 스플릿 대응 재다운로드
- ``fetch-state`` / ``push-state``: 프라이빗 리포 상태 동기화
- ``fetch-fills``: RTDB 체결 입력 조회
- ``history``: 히스토리 출력
- ``drift``: 현재 drift 지표 출력
- ``notify-failure``: 실패 알림 강제 발송 (GitHub Actions retry job 에서 호출)

원칙:

- ``scripts/CLAUDE.md`` 의 CLI 계층 원칙 준수 (``@cli_exception_handler`` 등).
- CLI 계층만 ERROR 로그 허용. 비즈니스 로직은 예외 전파만.
- 장애 시 자동 복구/롤백 금지. 중단 + 알림만.
- 실행 명령: ``poetry run python -m live.cli <command>``
"""
