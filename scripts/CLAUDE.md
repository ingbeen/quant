# CLI 스크립트 계층 가이드

> CRITICAL: CLI 계층 작업 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

CLI 스크립트 계층(`scripts/`)은 사용자 인터페이스를 제공하며,
비즈니스 로직(`src/qbt/`)을 호출하고 실행 결과를 사용자에게 전달합니다.

계층 원칙: 도메인 로직 구현 금지, 오직 인터페이스 제공만 담당

---

## 핵심 책임

### 1. 사용자 인터페이스

- 명령행 인자 파싱
- 사용자 입력 검증
- 실행 옵션 해석

### 2. 실행 환경 설정

- 로거 초기화
- 로그 레벨 설정
- 환경 변수 처리

### 3. 비즈니스 로직 호출

- 적절한 도메인 모듈 선택
- 파라미터 전달
- 결과 수령

### 4. 결과 표시

- 성공/실패 메시지
- 요약 통계 출력
- 테이블 형식 결과 표시

### 5. 메타데이터 관리

책임: CSV 결과 생성 시 실행 이력 자동 저장

- `meta_manager.save_metadata(csv_type, metadata)` 호출
- 자동 기록 항목:
  - ISO 8601 타임스탬프 (KST)
  - 실행 파라미터 (전략 설정, 그리드 범위 등)
  - 핵심 통계 (검증 기간, 거래일 수, 오차 지표 등)
- 순환 저장: 최근 N개만 유지 (`MAX_HISTORY_COUNT = 5`)
- 저장 위치: `storage/results/meta.json`

지원 타입:

- `"single_backtest"`: 단일 백테스트 결과 (signal, equity, trades, summary)
- `"backtest_walkforward"`: 백테스트 워크포워드 검증
- `"tqqq_daily_comparison"`: TQQQ 일별 비교
- `"tqqq_synthetic"`: TQQQ 합성 데이터 생성

근거 위치: [src/qbt/utils/meta_manager.py](../src/qbt/utils/meta_manager.py), [src/qbt/common_constants.py](../src/qbt/common_constants.py)

### 6. 예외 처리

책임: 모든 예외를 사용자 친화적 메시지로 변환

- `@cli_exception_handler` 데코레이터 사용 (자동 예외 처리)
- 자동 수행:
  - 예외 캐치 및 ERROR 로그 기록
  - 스택 트레이스 포함
  - 종료 코드 1 반환 (실패)
- 데코레이터가 로거 자동 감지 (모듈 레벨 `logger` 변수)
- CLI 계층에서만 ERROR 로그 사용 가능 (비즈니스 로직에서는 금지)

근거 위치: [src/qbt/utils/cli_helpers.py](../src/qbt/utils/cli_helpers.py)

---

## 표준 구조

### 필수 구성 요소

임포트 섹션:

- 표준 라이브러리
- 도메인 모듈
- 유틸리티 모듈
- 상수 모듈

로거 초기화:

- 모듈 레벨에서 로거 생성
- 예외 처리 데코레이터가 자동 감지

main 함수:

- 데코레이터 적용
- 종료 코드 반환 (0=성공, 1=실패)
- 명확한 단계별 로직

진입점 보호:

- `if __name__ == "__main__"` 사용
- 병렬 처리 환경 고려

### 실행 흐름

1. 로거 초기화
2. 명령행 인자 파싱 (필요 시)
3. 데이터 로딩
4. 비즈니스 로직 호출
5. 결과 표시
6. 메타데이터 저장 (CSV 생성 시)
7. 성공 코드 반환

---

## 도메인별 스크립트

### 데이터 수집 (data/)

- 외부 소스에서 데이터 다운로드
- 엄격한 검증 수행
- 검증 통과 후 저장
- 다운로드 통계 출력

### 백테스트 (backtest/)

- 전략 파라미터 설정
- 단일 백테스트 또는 그리드 탐색 실행
- 성과 지표 계산
- 결과 요약 및 저장
- 데이터 로딩: `load_stock_data` + `extract_overlap_period` (공통 유틸 사용)
- 워크포워드 검증:
  - `run_walkforward.py`: WFO 2-Mode 비교 실행 (Dynamic/Fully Fixed)
    - `--strategy` 인자로 실행 전략 선택 (all / buffer_zone_tqqq / buffer_zone_qqq, 기본값: all)
    - 각 모드별 CSV + Stitched Equity CSV + walkforward_summary.json 저장
- 분할 매수매도:
  - `run_split_backtest.py`: 분할 매수매도 백테스트 실행 (ma250/ma200/ma150 3분할)
    - `--strategy` 인자로 실행 전략 선택 (all / split_buffer_zone_tqqq / split_buffer_zone_qqq, 기본값: all)
    - 결과: `split_buffer_zone_tqqq/`, `split_buffer_zone_qqq/` 디렉토리에 signal.csv, equity.csv, trades.csv, summary.json 저장
    - signal.csv: OHLCV + MA 3개(ma_250/200/150) + 밴드 6개(upper/lower × 3) + 전일대비%
    - 메타데이터 타입: `"split_backtest"`
- 파라미터 고원 분석:
  - `run_param_plateau_all.py`: 4개 파라미터(hold_days, sell_buffer, buy_buffer, ma_window) 통합 고원 분석
    - `--experiment` 인자: all(기본) / hold_days / sell_buffer / buy_buffer / ma_window
    - 결과: `param_plateau/` 디렉토리에 피벗 CSV 저장 (calmar/cagr/mdd/trades × 4 파라미터)
- 대시보드 앱:
  - `app_single_backtest.py`: 전략별 동적 탭 대시보드 (Streamlit + lightweight-charts + Plotly)
    - 선행: `run_single_backtest.py` 실행 필요 (결과 CSV/JSON 로드)
    - 전략 자동 탐색: `BACKTEST_RESULTS_DIR` 하위 폴더를 스캔하여 전략별 탭 자동 생성
    - Feature Detection: 데이터 존재 여부로 차트 오버레이 결정 (전략명 분기 없음)
    - 미청산 포지션 마커: `summary.open_position` 존재 시 `"Buy $XX.X (보유중)"` 마커 자동 표시
    - customValues 기반 tooltip: 전일대비%, 이평선, 상단/하단 밴드 표시
    - 날짜 표기: `localization.dateFormat` 설정으로 한국식 "yyyy-MM-dd" 형식 적용
    - vendor fork: `vendor/streamlit-lightweight-charts-v5/` (tooltip 지원 추가)
  - `app_parameter_stability.py`: 4개 파라미터(MA Window, Buy Buffer, Sell Buffer, Hold Days) 고원 시각화 대시보드
    - 선행: `run_param_plateau_all.py` 실행 필요 (고원 분석 CSV 로드)
    - 각 탭: 7자산 Calmar 라인차트, 확정값 마커, 고원 구간 하이라이트, 보조 지표(CAGR/MDD/거래수) expander
  - `app_split_backtest.py`: 분할 매수매도 시각화 대시보드 (Streamlit + lightweight-charts + Plotly)
    - 선행: `run_split_backtest.py` 실행 필요 (결과 CSV/JSON 로드)
    - 전략 자동 탐색: `BACKTEST_RESULTS_DIR`에서 `split_` 접두사 + `split_summary` 키로 판별
    - 주요 섹션: 요약 지표, 캔들스틱(포커스 트랜치 선택: MA+밴드+마커), 에쿼티(합산+트랜치별 오버레이), 포지션 추적(평균단가/보유수량/active_tranches), 드로우다운, 거래 테이블, 파라미터
    - 트랜치별 색상 체계: ma250=파랑, ma200=주황, ma150=초록
  - `app_walkforward.py`: WFO 2-Mode 결과 시각화 대시보드 (Streamlit + Plotly)
    - 선행: `run_walkforward.py` 실행 필요 (WFO 결과 CSV/JSON 로드)
    - 전략 자동 탐색: walkforward_summary.json 존재 여부로 유효 전략 판별, 전략별 좌우 비교 통합 뷰
    - 주요 섹션: 모드 요약 비교, Stitched Equity 곡선, IS/OOS 성과 바차트, 파라미터 추이, WFE 분포
    - VERBATIM 패턴: 각 섹션에 용어 설명 / 해석 방법 / 현재 판단 3부분 구조 적용

### 레버리지 시뮬레이션 (tqqq/)

- 합성 데이터 생성 (`generate_synthetic.py`)
- 일별 비교 데이터 생성 (`generate_daily_comparison.py`, softplus 동적 스프레드 사용)
- 대시보드 앱:
  - `app_daily_comparison.py`: 일별 비교 대시보드

### 스프레드 모델 검증 결과 열람 (tqqq/spread_lab/)

스프레드 모델 확정 후 검증 결과를 열람하기 위한 시각화 앱만 유지:

- 대시보드 앱:
  - `app_rate_spread_lab.py`: 금리-오차 관계 분석 연구용 앱 (시각화 전용, 단일 흐름: 오차분석→튜닝→과최적화진단→상세분석)
- CSV 생성 스크립트(tune, validate, generate)는 삭제됨 (`docs/archive/tqqq_removed_modules.md` 참고, git history에서 복원 가능)

---

## 코딩 규칙

### 예외 처리

데코레이터 사용:

- main 함수에 데코레이터 적용
- try-except 블록 불필요
- 자동 로깅 및 종료 코드 처리

예외 전파:

- 비즈니스 로직에서 발생한 예외를 그대로 전파
- 변환하거나 숨기지 않음

### Streamlit 앱 규칙

width 파라미터 사용:

- `use_container_width` 파라미터는 deprecated됨 (사용 금지)
- 전체 너비 사용 시: `width="stretch"`
- 콘텐츠 크기 맞춤 시: `width="content"`

적용 대상 위젯:

- `st.button()`
- `st.dataframe()`
- `st.plotly_chart()`
- `st.download_button()`
- 기타 width 관련 파라미터를 지원하는 위젯

### 명령행 인자

기본 원칙: 명령행 인자 최소화

- CLI 스크립트는 기본적으로 명령행 인자를 받지 않음
- 모든 파라미터는 상수 파일에서 정의
  - 공통 상수: `src/qbt/common_constants.py`
  - 도메인 상수: 각 도메인의 `constants.py` (예: `src/qbt/backtest/constants.py`)
  - 상수 명명 규칙: 루트 CLAUDE.md 참고
- 예외 사례 1: 데이터 다운로드 스크립트(`scripts/data/download_data.py`)
  - ticker(선택), 시작일, 종료일을 명령행 인자로 받음
  - ticker 미지정 시 `DEFAULT_TICKERS` 전체 종목 일괄 다운로드
  - 이유: 다양한 종목/기간에 대한 유연한 데이터 수집 필요
- 예외 사례 2: 단일 백테스트 스크립트(`scripts/backtest/run_single_backtest.py`)
  - `--strategy` 인자로 실행 전략 선택 (all / buffer_zone_tqqq / buffer_zone_spy / ... / buy_and_hold_qqq 등, 기본값: all)
  - cross-asset 전략은 CONFIGS 기반 자동 등록, regime_summaries는 QQQ 시그널 전략에만 적용
  - 이유: 전략별 독립 실행 및 비교 실행 지원
    근거 위치: [scripts/data/download_data.py](data/download_data.py), [scripts/backtest/run_single_backtest.py](backtest/run_single_backtest.py)

---

## 제약사항

### 비즈니스 로직 분리

- CLI 계층에 도메인 로직 포함 금지
- 단순히 비즈니스 로직 호출만 담당

### 에러 로깅

- CLI 계층만 ERROR 레벨 로그 출력
- 비즈니스 로직은 예외만 발생

### 종료 코드

- 성공 시 0 반환 필수
- 실패 시 1 반환 필수
- 데코레이터가 자동 처리

### 사용자 메시지

- 한글 사용
- 명확하고 구체적
- 액션 가능한 정보 포함
