# QBT (Quant BackTest)

백테스트로 검증한 매매 전략을 GitHub Actions로 매일 자동 실행하여 시그널 알림을 발송하고, Android 앱으로 포트폴리오 / 차트 / 알림을 제공하는 퀀트 시스템입니다.

## 프로젝트 목표

- **서버 운영 비용 부담 없는 시그널 알림 체계** 구축을 핵심 목표로, 처음부터 **서버리스 환경**으로 설계
- **Claude Code를 안정적으로 활용하기 위한 하네스 엔지니어링**을 함께 도입하여, AI 협업의 일관성과 코드 품질을 확보

## 시스템 아키텍처

별도 서버 없이 GitHub Actions의 정기 실행과 Firebase 서비스만으로 엔진을 운영하면서, **데이터 보관(GCS 정본)** 과 **앱 전달(Firebase RTDB)** 역할을 분리하여 앱과 서버 간 양방향 통신 구조를 확보했습니다.

### 데이터 흐름

```
[GitHub Actions]  평일 장 마감 후 엔진 자동 실행
       │
       ├─→ [GCS 정본 버킷]  매일 GCS 업로드로 누적 보존
       │
       ├─→ [Firebase RTDB]  매일 덮어쓰기 → 앱이 최신 상태 조회
       │         ↑
       │         └── [Android 앱]  체결 데이터를 별도 입력 경로로 저장
       │                          (다음 실행 시 엔진이 처리)
       │
       ├─→ [FCM]            주 채널 (앱 푸시)
       └─→ [Telegram Bot]   백업 채널 (한쪽 장애 시에도 도달 보장)
```

### 설계 결정

- **GitHub Actions**: 평일 장 마감 후 엔진을 자동 실행하여 GCS 정본 + Firebase RTDB를 동시 갱신. 알림은 FCM(주 채널)과 텔레그램 Bot API(백업 채널)로 **이중 발송**하여 한쪽 장애 시에도 사용자 도달을 보장
- **Firebase RTDB**: 앱이 매일 최신 데이터를 읽도록 매 실행마다 **덮어쓰기**로 갱신. 앱에서 입력한 체결 데이터는 별도 입력 경로에 저장되어 다음 실행 시 엔진이 처리하는 **양방향 구조**
- **GCS 정본 버킷**: Firebase RTDB는 갱신 시 과거 데이터를 볼 수 없는 단점이 있어, 모든 데이터를 매일 commit으로 **누적 보존**하여 보완

## Claude Code 하네스 엔지니어링

Claude Code에 매번 컨텍스트를 설명하면 같은 실수를 반복하고 코드 스타일이 흔들리는 문제를 관찰하여, **AI가 따라야 할 규칙과 작업 프로세스를 프로젝트 내부에 문서화**했습니다.

- **AI 전용 가이드 계층화**: 루트 및 도메인별로 AI 가이드 문서(`CLAUDE.md`)를 12개 이상 분리 운영하여, 작업 시작 전 해당 도메인 문서를 반드시 읽도록 강제
- **계획서 템플릿 표준화**: 모든 코드 변경 작업이 직접 정의한 계획서 템플릿을 따르도록 하여, **목표 / 범위 / 검증 기준 / 리스크**가 항상 동일한 형식으로 작성되고 **Phase 단위로 실행**되도록 표준화
- **TDD + 통합 검증**: 핵심 비즈니스 로직에 TDD를 적용하여 회귀를 자동 검증. 계획서에 따른 구현이 완료되면 항상 통합 검증 스크립트(`validate_project.py`)를 실행하여 **린트 / 타입 / 테스트를 하나의 커맨드로 일괄 검증**

## 관련 저장소

- 백테스트 / 매매 시그널 엔진 (이 저장소) — https://github.com/ingbeen/quant
- Android 앱 — https://github.com/ingbeen/qbt-live-app

## 기술 스택

- **언어 / 런타임**: Python 3.12 (`str | None` 문법), React Native (앱)
- **인프라 / 자동화**: GitHub Actions, Firebase RTDB, FCM, Telegram Bot API
- **데이터 / 분석**: pandas, yfinance
- **시각화**: Plotly, Streamlit, matplotlib
- **코드 품질**: PyRight (strict for `src/`), Ruff, Black
- **테스트**: pytest, pytest-cov, freezegun
- **의존성 관리**: Poetry

## 퀀트 비즈니스 로직

### qbt — 백테스트 코어 (`src/qbt/`)

- Yahoo Finance 기반 시계열 데이터 수집 및 검증
- 이동평균 기반 **버퍼존 거래 전략** 백테스트 — 엔진/전략 분리 아키텍처
- **멀티자산 포트폴리오** 백테스트 (목표 비중 + 이중 트리거 리밸런싱, 자산 슬롯별 파라미터 독립 설정)
- **워크포워드 검증** (Dynamic / Fully Fixed 2-Mode 비교, WFE · Profit Concentration)
- **파라미터 고원 분석** (멀티자산 x 4개 파라미터 통합)
- **TQQQ 레버리지 ETF 시뮬레이션** — softplus 동적 스프레드 비용 모델
- **Streamlit + Plotly 대시보드** — 단일 전략, 포트폴리오, 디버그, 워크포워드, 파라미터 고원

### live — 실매매 알림 시스템 (`src/live/`)

- QBT 포트폴리오 전략의 실매매 알림을 GitHub Actions에서 매일 장 마감 후 자동 실행
- 주가 수집 → 시그널 감지 → FCM / 텔레그램 알림
- 원격 state 리포 기반 상태 관리, Firebase RTDB를 통해 Android 앱과 연동

### 과최적화 방어 / 정합성 검증

- **과최적화 방어 장치**: Walk-Forward Optimization (Dynamic / Fully Fixed 2-Mode 비교) · WFE · Profit Concentration · 멀티자산 파라미터 고원 분석을 결합해, IS에서 좋아 보이는 값을 그대로 믿지 않도록 설계
- **정합성 자동 검증**: 포트폴리오 백테스트 실행 직후 시그널-체결 lag, 리밸런싱 비중, EXIT_ALL 주수, 현금 비음수, 에쿼티 등식 같은 핵심 불변조건을 자동으로 검증하고, 하나라도 위반하면 스크립트를 즉시 중지

## 관련 문서

- 실행 명령어 레퍼런스 → [docs/COMMANDS.md](docs/COMMANDS.md)
- 프로젝트 전체 규칙 → [CLAUDE.md](CLAUDE.md)
- 백테스트 패키지 규칙 → [src/qbt/CLAUDE.md](src/qbt/CLAUDE.md)
- 실매매 알림 규칙 → [src/live/CLAUDE.md](src/live/CLAUDE.md)
- 계획서 운영 규칙 → [docs/CLAUDE.md](docs/CLAUDE.md)
