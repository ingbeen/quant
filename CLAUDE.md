# QBT 프로젝트 가이드라인

> CRITICAL: 특정 패키지 또는 폴더의 파일을 분석하거나 작업할 때는
> 반드시 해당 폴더에 위치한 `CLAUDE.md`를 먼저 읽고 참고해야 합니다.
> 이는 필수 요구사항입니다. 루트 문서는 프로젝트 전반의 공통 규칙을 제공하며,
> 각 패키지 문서는 해당 도메인의 구체적인 맥락과 핵심 개념을 제공합니다.

## 문서 목적

이 문서는 AI 모델이 QBT 프로젝트를 정확히 이해하고, 일관성 있는 응답을 생성하도록 돕습니다.
사람을 위한 상세 문서가 아닌, AI 모델의 판단 기준과 프로젝트 맥락을 제공합니다.

---

## 규칙 문서 참고 순서

각 작업 전에 해당 경로의 규칙 문서를 반드시 읽습니다

- **전역 규칙**: `~/.claude/CLAUDE.md` — 사고 절차·수술적 변경·개발 원칙·목표 주도 실행·계획서 선행·검증 지침·문서 참조 방향의 SoT입니다. 이 문서는 QBT 고유 맥락만 담습니다
- 공통 규칙: `CLAUDE.md`(루트), `scripts/CLAUDE.md`(스크립트), `tests/CLAUDE.md`(테스트)
- 파이썬 구현: `.claude/rules/python.md` — 구현 원칙·코딩 표준·로깅 정책. `.py` 파일을 다룰 때 자동으로 로드됩니다
- 패키지 규칙: `src/qbt/CLAUDE.md`(qbt 패키지), `src/live/CLAUDE.md`(live 패키지)
- 도메인 규칙: 작업 대상 경로의 `CLAUDE.md`
  - 예: `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/utils/CLAUDE.md`

---

## 패키지 간 의존 관계

프로젝트는 두 개의 독립 패키지로 구성됩니다:

- **qbt**: 주식 백테스팅 CLI 도구 코어 (backtest, tqqq, utils)
- **live**: QBT 포트폴리오 전략의 실매매 알림 시스템

### 의존 방향 (단방향)

- **live → qbt**: import 허용. live는 qbt에 이미 정의된 함수/상수를 적극 활용하며, 동일한 기능을 독립 재구현하지 않는다.
- **qbt → live**: import 금지. qbt는 live에 대한 어떤 의존도 갖지 않는다.

### 리팩토링 시 영향도 고려

qbt의 핵심 비즈니스 로직이나 대규모 리팩토링을 진행할 때는 live 패키지의 영향도를 함께 고려해야 한다.
live가 qbt의 어떤 심볼을 import하는지 확인하고, 시그니처/타입 변경 시 live 코드도 함께 수정한다.

### QBT 본체 수정 제한 (live 작업 중)

- 원칙: **QBT 본체(`src/qbt/`) 는 live 작업 중 수정 금지**. 모든 live 구현은 `src/live/` 내부에서만 수행한다.
- 예외: **사용자 승인이 명시적으로 있을 경우에만** QBT 본체 수정 가능.
  - 수정 전 반드시 사용자에게 수정 범위 / 사유를 설명하고 승인 요청한다.
- 상세 가이드: [src/live/CLAUDE.md](src/live/CLAUDE.md)

---

## 계획서(Plan) 작성이 필요한 경우

원칙: 모든 코드 변경은 계획서를 작성한 후 진행합니다.

예외 (계획서 없이 바로 진행 가능):

- 오타 수정
- 주석 수정
- 로그 메시지 수정

위 예외를 제외한 모든 변경은 먼저 [`docs/CLAUDE.md`](docs/CLAUDE.md)를 읽고 `docs/plans/`에 계획서를 작성해야 합니다.

계획서 작성 절차 및 품질 게이트: [`docs/CLAUDE.md`](docs/CLAUDE.md)에서 상세 내용 확인

> 보완 관계: 인라인 plan은 즉석 실행용이며, 코드 변경이 필요한 작업은 위 절차에 따라 `docs/plans/`에 공식 계획서를 작성합니다.

---

## 문서 보관 원칙

- **아카이브 폴더를 만들지 않는다**. 역할을 다한 문서를 별도 보관소로 옮겨 쌓아두지 않는다.
- 남길 가치가 있는 과거 이력(결론, 수치, 기각 사유, 폐기 근거)은 `docs/research/`의 보고서 본문에 기록한 뒤 원본 문서는 삭제한다.
- 삭제된 코드의 스냅샷은 문서로 복제하지 않는다. git history가 원본을 보관한다.
- `docs/research/` 문서의 파일명은 한글 + 언더스코어로 작성한다.

상세 규칙: [`docs/CLAUDE.md`](docs/CLAUDE.md)

---

## 프로젝트 개요

QBT(Quant BackTest) 프로젝트는 두 개의 패키지로 구성됩니다:

- **qbt** (`src/qbt/`): 주식 백테스팅 CLI 도구. 시계열 데이터 수집, 이동평균 기반 전략 백테스트, 레버리지 ETF 시뮬레이션, 대화형 시각화 대시보드를 제공합니다.
- **live** (`src/live/`): QBT 포트폴리오 전략의 실매매 알림 시스템. GitHub Actions에서 매일 장 마감 후 실행되어 주가 수집, 시그널 감지, FCM/텔레그램 알림을 수행합니다.

기술 환경:

- Python 3.12 (`str | None` 문법 사용)
- 의존성 관리: Poetry
- 코드 품질: Black, Ruff
- 타입 체커: PyRight (strict mode for src/)
- 주요 라이브러리: pandas, yfinance, Plotly, Streamlit

---

## 디렉토리 구조

```
quant/
├── src/                # 패키지 소스 코드
│   ├── qbt/            # 백테스트 코어 패키지 (상세: src/qbt/CLAUDE.md)
│   │   ├── common_constants.py
│   │   ├── backtest/   # 백테스트 도메인
│   │   ├── tqqq/       # 레버리지 ETF 시뮬레이션
│   │   └── utils/      # 공통 유틸리티
│   └── live/           # 실매매 알림 패키지 (상세: src/live/CLAUDE.md)
├── tests/              # 테스트 코드 (상세: tests/CLAUDE.md)
│   ├── qbt/            # qbt 패키지 테스트
│   └── live/           # live 패키지 테스트
├── scripts/            # CLI 스크립트 (qbt 전용, 도메인별 분리)
│   ├── data/           # 데이터 다운로드
│   ├── backtest/       # 백테스트 실행 + 대시보드 앱
│   └── tqqq/           # 레버리지 ETF 관련
├── docs/               # 프로젝트 문서 및 계획서
│   ├── plans/          # 작업 계획서 저장소
│   └── research/       # 연구/검증 보고서 저장소
├── storage/            # 데이터 저장소 (stock, etc, results)
└── vendor/             # 서드파티 포크 (streamlit-lightweight-charts-v5)
```

---

## 실행 명령어 관리 원칙

> CRITICAL: 모든 실행 명령어(`poetry run`, `streamlit run` 등)는 **[docs/COMMANDS.md](docs/COMMANDS.md)에서 단일 관리**합니다.
> README.md 와 CLAUDE.md 파일에는 실행 명령어를 기재하지 않으며, 필요 시 `docs/COMMANDS.md` 를 참조합니다.

## 스크립트 실행 규칙

> CRITICAL: `scripts/` 폴더에 위치한 모든 스크립트는 **사용자만이 직접 실행**합니다.
> AI 모델은 scripts 폴더의 스크립트를 직접 실행하지 않습니다.

- AI 모델의 역할: 스크립트 코드 작성/수정, 실행 방법 안내
- 사용자의 역할: 스크립트 직접 실행, 결과 확인 및 피드백
- 예외: `validate_project.py`는 루트에 위치하며 AI 모델이 실행 가능

---

## 이 프로젝트의 개발 원칙

전역 「개발 원칙」(YAGNI·간결성·재사용성·영향도 관리·자문 체크·사용자 중심)에 더해, QBT 고유로 하나를 더 본다.

- **확장성**: 패키지/도메인별 모듈 독립성 유지 (`qbt` ↔ `live` 경계, `backtest`·`tqqq`·`utils` 경계)
