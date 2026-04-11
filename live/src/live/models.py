"""live 도메인 데이터 모델.

Step 2에서 설계서 부록 B의 다음 dataclass / TypedDict 가 이 파일에서 정의된다.

- ``LiveState`` / ``AssetLiveState`` / ``BufferZoneState``
- ``PendingOrderDict`` (``execute_on`` 필드 없음)
- ``ActualFill``
- ``DailyResult``
- ``ChartSeries``
- ``DriftReport`` / ``AssetDrift``

원칙:

- model / actual 필드를 명시적으로 분리한다.
- 모든 dataclass 는 타입 힌트 필수, ``str | None`` 문법 사용.
"""
