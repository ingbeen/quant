"""live 도메인 공통 pytest 픽스처.

Step 3 이후 각 테스트에서 재사용할 픽스처(임시 state 디렉토리, mock Firebase,
mock yfinance 응답 등)를 이 파일에서 정의한다.

현재(Step 1)는 스켈레톤만 존재하며, 실제 픽스처는 각 Step에서 해당 모듈과 함께 추가된다.

테스트 작성 원칙은 ``tests/CLAUDE.md`` 와 ``live/CLAUDE.md`` 를 참고한다.
외부 네트워크 호출(Firebase, yfinance, 텔레그램) 은 **항상 mock** 처리한다.
"""
