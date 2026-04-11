# QBT Live 구현 프롬프트

> 이 파일은 Claude Code에게 전달하는 구현 지시서이다.
> 반드시 아래 문서를 함께 참조하라:
> - `docs/DESIGN_QBT_LIVE_FINAL.md` (설계서)
> - `docs/TODO_QBT_LIVE.md` (구현 체크리스트)
>
> 문서 경로: `/home/yblee/workspace/quant/docs/`

---

## 프로젝트 개요

QBT 포트폴리오 전략의 실매매 알림 시스템을 구현한다.
매일 장 마감 후 GitHub Actions에서 Python 엔진이 실행되어
주가를 수집하고, 시그널을 감지하고, FCM + 텔레그램으로 알림을 보낸다.
사용자는 Android 앱에서 포트폴리오 확인, 차트 조회, 체결 입력을 한다.

## 인프라 (사전 준비 완료)

```
QBT 리포 (모노리포, 퍼블릭):  https://github.com/ingbeen/quant
상태 리포 (프라이빗):          https://github.com/ingbeen/qbt-live-state.git
Firebase 프로젝트:             qbt-live (Spark 요금제)
RTDB URL:                      https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app
Android 패키지:                com.ingbeen.qbtlive
Firebase Auth UID:             SxwvCeg6fRUeUrK9IpyazTzrLJJ2
텔레그램 봇:                   @qbt_live_alert_bot

GitHub Secrets (ingbeen/quant 리포에 등록 완료):
  FIREBASE_CONFIG       - Firebase Admin SDK 서비스 계정 JSON
  STATE_REPO_PAT        - qbt-live-state 리포 접근 PAT
  TELEGRAM_BOT_TOKEN    - 텔레그램 봇 토큰
  TELEGRAM_CHAT_ID      - 텔레그램 채팅 ID
```

## 코딩 규칙

```
1. QBT 본체 코드(src/qbt/)는 절대 수정하지 않는다. live/ 안에서만 작업.
2. CLAUDE.md 규칙 준수:
   - 타입 힌트 필수. str | None 문법 (Optional 사용 금지).
   - pathlib.Path 사용 (문자열 경로 금지).
   - 비율은 0~1 소수 (0.03 = 3%).
   - 로깅: INFO 금지. DEBUG/WARNING/ERROR만. 이모지 금지. 한글 메시지.
   - 네이밍: 함수/변수 snake_case, 클래스 PascalCase, 상수 UPPER_SNAKE_CASE.
   - 내부 불변조건 위반 시 RuntimeError("내부 불변조건 위반 ...").
   - 입력 검증 실패 시 ValueError.
3. 테스트: Given-When-Then. pytest.approx(). 외부 네트워크 호출 금지 (mock).
4. 장애 시 자동 복구/롤백 금지. 즉시 중단 + 에러 상세 포함 알림 발송.
   사용자가 상황을 직접 파악하여 디버깅해야 하므로 자동으로 상태를 되돌리지 않는다.
5. 한 Step만 구현. 완료 후 TODO_QBT_LIVE.md의 체크박스를 체크.
6. 다음 Step 전에 기존 테스트 전체 통과 확인.
```

## 실행 방법

`docs/TODO_QBT_LIVE.md`를 열고 현재 미완료([ ]) 상태인 가장 첫 번째 🤖 Step을 찾아서
해당 Step의 지시사항을 수행하라.

각 Step에는:
- 어떤 설계서 섹션을 참조해야 하는지
- 어떤 파일을 구현해야 하는지
- 어떤 테스트를 작성해야 하는지 (🤖 테스트 시나리오)
가 명시되어 있다.

👤 표시된 항목은 사용자가 직접 수행하므로 건너뛴다.

Step을 완료하면:
1. 해당 🤖 체크박스를 [x]로 변경
2. `poetry run pytest live/tests/` 전체 통과 확인
3. 완료 보고

## 주의사항

- 한 번에 1개 Step만 진행. 여러 Step을 한꺼번에 하지 않는다.
- 설계서에 명시된 함수 시그니처와 데이터 모델을 정확히 따른다.
- QBT 본체의 import 경로: `from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy`
- 프라이빗 리포: `https://github.com/ingbeen/qbt-live-state.git`
- RTDB URL: `https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app`
- 시그널 감지, 체결 계산, 리밸런싱은 새로 구현하지 않는다. QBT 코어를 import하여 호출만.
- 에러 발생 시 자동 복구/자동 롤백 하지 않는다. 중단 + 알림만.
