# QBT (Quant BackTest)

이동평균 기반 매매 전략을 백테스트하고, **과최적화가 아님을 확인하는 데 무게를 둔** 퀀트 백테스팅 도구입니다.

## 프로젝트 목표

- **검증 가능한 백테스트 파이프라인** 구축 — 전략을 만드는 것보다, 그 전략이 과거에만 좋았던 것이 아님을 확인하는 절차(워크포워드 · 파라미터 고원 · 정합성 자동 검증)를 갖추는 데 무게를 둡니다
- **Claude Code를 안정적으로 활용하기 위한 하네스 엔지니어링**을 함께 도입하여, AI 협업의 일관성과 코드 품질을 확보

## Claude Code 하네스 엔지니어링

Claude Code에 매번 컨텍스트를 설명하면 같은 실수를 반복하고 코드 스타일이 흔들리는 문제를 관찰하여, **AI가 따라야 할 규칙과 작업 프로세스를 프로젝트 내부에 문서화**했습니다.

- **AI 전용 가이드 계층화**: 루트 및 도메인별로 AI 가이드 문서(`CLAUDE.md`)를 계층화하여 운영하며, 작업 시작 전 해당 도메인 문서를 반드시 읽도록 강제
- **계획서 템플릿 표준화**: 모든 코드 변경 작업이 직접 정의한 계획서 템플릿을 따르도록 하여, **목표 / 범위 / 검증 기준 / 리스크**가 항상 동일한 형식으로 작성되고 **Phase 단위로 실행**되도록 표준화
- **TDD + 통합 검증**: 핵심 비즈니스 로직에 TDD를 적용하여 회귀를 자동 검증. 계획서에 따른 구현이 완료되면 항상 통합 검증 스크립트(`validate_project.py`)를 실행하여 **린트 / 타입 / 테스트를 하나의 커맨드로 일괄 검증**

## 관련 저장소

- 백테스트 엔진 (이 저장소) — https://github.com/ingbeen/quant
- 실매매 알림 — https://github.com/ingbeen/quant-notify

## 기술 스택

- **언어 / 런타임**: Python 3.12 (`str | None` 문법)
- **데이터 / 분석**: pandas, yfinance
- **시각화**: Plotly, Streamlit
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

### 과최적화 방어 / 정합성 검증

- **과최적화 방어 장치**: Walk-Forward Optimization (Dynamic / Fully Fixed 2-Mode 비교) · WFE · Profit Concentration · 멀티자산 파라미터 고원 분석을 결합해, IS에서 좋아 보이는 값을 그대로 믿지 않도록 설계
- **정합성 자동 검증**: 포트폴리오 백테스트 실행 직후 시그널-체결 lag, 리밸런싱 비중, EXIT_ALL 주수, 현금 비음수, 에쿼티 등식 같은 핵심 불변조건을 자동으로 검증하고, 하나라도 위반하면 스크립트를 즉시 중지

## 관련 문서

- 실행 명령어 레퍼런스 → [docs/COMMANDS.md](docs/COMMANDS.md)
- 프로젝트 전체 규칙 → [CLAUDE.md](CLAUDE.md)
- 백테스트 패키지 규칙 → [src/qbt/CLAUDE.md](src/qbt/CLAUDE.md)
- 계획서 운영 규칙 → 전역 `/impl-plan` 스킬 (프로젝트 고유 값은 [CLAUDE.md](CLAUDE.md) 「계획서 규약」 절)
