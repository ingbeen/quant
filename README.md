# QBT (Quant BackTest)

주식 백테스팅과 레버리지 ETF 시뮬레이션, 그리고 그 결과를 기반으로 한 실매매 알림까지 한 번에 다루는 퀀트 프로젝트입니다.

## 엔지니어링 하이라이트

- **매일 돌아가는 라이브 시스템**: GitHub Actions 가 장 마감 후 자동 실행되어 주가 수집 → 시그널 판정 → 알림까지 수행하고, Firebase RTDB 를 거쳐 본인 Android 앱으로 시그널이 배달됩니다. "돌려보고 끝" 이 아니라 실제로 신호를 받아보며 운영 중인 시스템입니다.
- **과최적화 방어 장치**: Walk-Forward Optimization (Dynamic / Fully Fixed 2-Mode 비교) · WFE · Profit Concentration · 멀티자산 파라미터 고원 분석을 결합해, IS 에서 좋아 보이는 값을 그대로 믿지 않도록 설계했습니다.
- **정합성 자동 검증**: 포트폴리오 백테스트 실행 직후 시그널-체결 lag, 리밸런싱 비중, EXIT_ALL 주수, 현금 비음수, 에쿼티 등식 같은 핵심 불변조건을 자동으로 검증하고, 하나라도 위반하면 스크립트를 즉시 중지합니다.
- **엔지니어링 품질**: PyRight strict (`src/`) · Ruff · Black 을 `validate_project.py` 원커맨드로 통합해, 린트 / 타입 / 테스트를 한 번에 돌리는 구조를 유지합니다.

## 주요 기능

### qbt — 백테스트 코어 (`src/qbt/`)

- Yahoo Finance 기반 시계열 데이터 수집 및 검증
- 이동평균 기반 **버퍼존 거래 전략** 백테스트 — 엔진/전략 분리 아키텍처
- **멀티자산 포트폴리오** 백테스트 (목표 비중 + 이중 트리거 리밸런싱, 자산 슬롯별 파라미터 독립 설정)
- **워크포워드 검증** (Dynamic / Fully Fixed 2-Mode 비교, WFE · Profit Concentration)
- **파라미터 고원 분석** (멀티자산 x 4개 파라미터 통합)
- **TQQQ 레버리지 ETF 시뮬레이션** — softplus 동적 스프레드 비용 모델
- **Streamlit + Plotly 대시보드** — 단일 전략, 포트폴리오, 디버그, 워크포워드, 파라미터 고원

### live — 실매매 알림 시스템 (`src/live/`)

- QBT 포트폴리오 전략의 실매매 알림을 GitHub Actions 에서 매일 장 마감 후 자동 실행
- 주가 수집 → 시그널 감지 → FCM / 텔레그램 알림
- 원격 state 리포 기반 상태 관리, Firebase RTDB 를 통해 Android 앱과 연동

## 기술 스택

- **언어**: Python 3.12 (`str | None` 문법)
- **의존성 관리**: Poetry
- **데이터/분석**: pandas, yfinance
- **시각화**: Plotly, Streamlit, matplotlib
- **코드 품질**: Black, Ruff, PyRight (strict for `src/`)
- **테스트**: pytest, pytest-cov, freezegun
- **자동화**: GitHub Actions, Firebase RTDB, FCM, Telegram Bot API

## 관련 문서

- 실행 명령어 레퍼런스 → [docs/COMMANDS.md](docs/COMMANDS.md)
- 프로젝트 전체 규칙 → [CLAUDE.md](CLAUDE.md)
- 백테스트 패키지 규칙 → [src/qbt/CLAUDE.md](src/qbt/CLAUDE.md)
- 실매매 알림 규칙 → [src/live/CLAUDE.md](src/live/CLAUDE.md)
- 계획서 운영 규칙 → [docs/CLAUDE.md](docs/CLAUDE.md)
