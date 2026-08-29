---
paths:
  - "**/*.py"
---

# 파이썬 구현 규칙

> 이 문서는 파이썬 파일을 다룰 때만 로드됩니다.
> 프로젝트 전반의 공통 규칙은 루트 `CLAUDE.md`를 참고하세요.

## 구현 원칙

프로젝트 전반(qbt + live)의 비즈니스 로직 구현 시 준수해야 하는 원칙입니다.

#### 데이터 불변성

- 원본 DataFrame을 변경하지 않음
- 계산 시 복사본 사용 (예: `df.copy()`)
- 함수 호출 후 원본 데이터 보장

#### 명시적 검증

- 파라미터 유효성 즉시 검증
- 유효하지 않은 입력 시 즉시 예외 발생 (ValueError)
- 암묵적 가정 금지

#### 불가능 조건 처리

내부 불변조건이 보장하는 "로직상 절대 발생할 수 없는 조건"에 대한 방어 코드 규칙:

- 조용히 기본값을 반환하거나 건너뛰지 않는다 (return, continue, 0 대체 금지)
- RuntimeError를 발생시켜 사용자가 즉시 인지할 수 있도록 한다
- 메시지에 "내부 불변조건 위반" 접두사와 위반된 변수/값을 포함한다

구분 기준:

- 입력 파라미터 검증 (외부에서 잘못된 값 전달 가능) → ValueError
- 내부 로직 불변조건 (코드 흐름상 절대 도달 불가) → RuntimeError

---

## 코딩 표준

### 필수 규칙

타입 안정성:

- 모든 함수에 타입 힌트 필수
- Optional 타입은 `|` 문법 사용 (예: `str | None`, `int | None`)
- 여러 타입 허용 시에도 `|` 사용 (예: `int | float`, `Path | str`)

파일 처리:

- Path 객체만 사용 (문자열 경로 금지)

비율 표기 규칙:

- 모든 비율 값은 0~1 사이 소수로 정의 (0.03 = 3%)
- 주석에서 % 표기 시 혼란 방지를 위해 "비율 (0.03 = 3%)" 형식 사용
- 변수명 접미사: `_rate`, `_ratio`, `_pct` (모두 0~1 범위)
- 예시:
  - `SLIPPAGE_RATE = 0.003  # 슬리피지 비율 (0.003 = 0.3%)`
  - `buy_buffer_zone_pct: float  # 매수 버퍼존 비율 (0.03 = 3%)`

출력 데이터 반올림 규칙:

CSV/JSON 결과 파일 저장 시 적절한 소수점 자릿수로 반올림합니다.
비즈니스 로직 내부 계산 정밀도는 변경하지 않으며, 저장 직전에만 적용합니다.

| 데이터 유형                              | 소수점 자릿수 | 예시         |
| ---------------------------------------- | ------------- | ------------ |
| 가격 (종가, 시가, 밴드, 체결가 등)       | 6자리         | `103.450000` |
| 자본금 (equity, pnl)                     | 정수 (0자리)  | `10000000`   |
| 백분율 (수익률, MDD, 승률, 드로우다운)   | 2자리         | `22.47`      |
| 비율 (0~1, buy_buffer_zone_pct, pnl_pct) | 4자리         | `0.0300`     |

적용 패턴:

- DataFrame: `df.round({컬럼명: 자릿수, ...})` (to_csv 직전)
- JSON: `round(float(str(value)), 자릿수)` (dict 구성 시). `str()` 우회는 값 타입이 불명확한 경우(TypedDict의 Any, numpy/pandas scalar 등) 안전 변환을 위함이며, 값 타입이 명확한 dataclass 필드 / typed float 변수는 `round(float(value), 자릿수)` 로 충분하다.

문서화:

- Google 스타일 Docstring
- 한글 작성
- 복잡한 로직은 넘버링 주석
- 주석 작성 원칙:
  - 현재 코드의 상태와 동작만 설명
  - 과거 상태, 변경 이력, 계획 단계는 기록하지 않음
  - 금지 패턴: "Phase 0", "Phase 3", "레드", "그린" 등 개발 단계 표현 사용 금지
- 문서 내구성 원칙 (README.md, CLAUDE.md, 주석/docstring 공통):
  - 역할/책임 중심 설명을 사용한다 ("이 파일은 무엇을 담당하는가")
  - 구체적 수치(개수, 파라미터 값)와 가변 정보(실험 ID 목록, 시리즈 나열)를 직접 기재하지 않는다
  - 코드에서 파생 가능한 정보(실험 목록, 전략 목록 등)는 문서에 복제하지 않고 해당 코드 파일을 참조한다
  - 리팩토링 후에도 쉽게 깨지지 않는 설명을 목표로 한다

네이밍:

- 함수/변수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

품질 검증:

- 모든 품질 검증은 `validate_project.py`를 통해서만 수행 (Ruff + PyRight + Pytest 통합)
- 직접 명령어 실행 금지 (원칙): `poetry run ruff check .`, `poetry run pyright`, `poetry run pytest tests/` 등
- 예외: 특정 모듈/파일만 테스트할 때 직접 pytest 명령 허용
- 실행 명령어는 [docs/COMMANDS.md](docs/COMMANDS.md)를 참고
- 타입 체커: PyRight 단일 사용
  - 설정 파일: `pyrightconfig.json` (`executionEnvironments` 방식)
  - 전역: strict 모드, reportUnknown\* 5개 규칙 + reportMissingTypeStubs는 none (pandas/Plotly 타입 스텁 한계 대응)
  - tests, scripts 폴더: `executionEnvironments`로 추가 규칙 완화 (테스트/스크립트 특성에 맞게)

### 로깅 정책

레벨 사용:

- DEBUG: 실행 흐름, 데이터 처리 상태
- WARNING: 잠재적 문제 상황
- ERROR: CLI 계층에서만 사용

금지 사항:

- INFO 레벨 사용 금지 (일반 정보는 DEBUG 사용)
- 이모지 사용 금지
- 함수명 중복 기재 금지 (로그 포맷에 자동 포함)

### 테스트

- 테스트 코드도 동일한 품질 기준 적용
