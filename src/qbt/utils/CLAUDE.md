# 유틸리티 패키지 가이드

> 이 문서는 `src/qbt/utils/` 패키지에 대한 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 폴더 목적

유틸리티 패키지는 프로젝트 전반에서 공통으로 사용되는 횡단 관심사(cross-cutting concerns)를 제공합니다.

핵심 원칙: 도메인 로직과 독립적인 기술적 기능만 담당

---

## 모듈 구성

### 1. logger.py

프로젝트 전역 로거 생성 및 관리

- 레벨별 필터링, 포맷 표준화
- VSCode 통합을 위한 클릭 가능한 경로 (파일:줄번호 형식)

### 2. data_loader.py

중앙 집중식 CSV 로딩 및 DataFrame 전처리

- `load_stock_data`: 주식 데이터 로딩
- 자동 전처리: 파일 존재 확인, 필수 컬럼 검증, 날짜 파싱, 시간순 정렬, 중복 제거
- `extract_overlap_period`: 두 DataFrame의 겹치는 기간 추출 (교집합 날짜 필터링, 정렬, 빈 결과 시 ValueError)

### 3. cli_helpers.py

CLI 예외 처리 데코레이터

- `@cli_exception_handler`: 일관된 예외 처리 로직
- 스택 트레이스 자동 기록, 종료 코드 자동 반환 (성공 0, 실패 1)
- 로거 자동 감지

### 4. parallel_executor.py

병렬 처리 지원

- `execute_parallel`: 단일 인자 함수 병렬 실행
- `execute_parallel_with_kwargs`: 키워드 인자 함수 병렬 실행
- 입력 순서 보장된 결과 반환

### 5. formatting.py

터미널 출력 포맷팅

- 다국어 문자폭 계산 (한글 = 2칸, 영문 = 1칸)
- `TableLogger` 클래스: 컬럼 정의 기반 테이블 생성

### 6. stock_downloader.py

주식 데이터 다운로드 및 검증

- `validate_stock_data`: 주식 데이터 유효성 검증 (결측치, 0값, 음수, 급등락)
- `download_stock_data`: Yahoo Finance에서 주식 데이터 다운로드 + 전처리 + 검증 + CSV 저장
- 검증 실패 시 즉시 ValueError (보간 금지)

### 7. meta_manager.py

실행 메타데이터 관리

- `save_metadata`: CSV 결과 파일의 생성 정보를 JSON으로 관리
- 순환 저장: 최근 `MAX_HISTORY_COUNT` 개만 유지
- ISO 8601 타임스탬프 자동 추가

### 8. proxy_series.py

실물 ETF 상장 전 구간을 비슷하게 움직이는 다른 시세(대용)로 채우는 시세 가공. 이음매는 실물 첫 거래일이다

- `compute_seam_scale` · `rescale_to_actual`: 이음매 종가 비율로 대용 전 구간의 가격을 스케일 (수익률 · 거래량 불변)
- `splice_proxy`: 이음매 앞은 스케일한 대용(거래량 0), 이음매부터는 실물 행 그대로
- `build_daily_rebalanced_composite`: 매일 비율을 맞추는 바스켓 (첫 종가 1.0, 거래량 0, 고가 · 저가는 가중합 근사). 겹치는 기간 안에서 구성 종목의 날짜가 다르면 ValueError (보간 금지)
- `build_rate_accrual_series`: 전날 연 금리로 하루치 이자(÷ `TRADING_DAYS_PER_YEAR`)를 붙여 가는 시세 (첫 종가 1.0, 시가 · 고가 · 저가 = 종가, 거래량 0) — 초단기 국채 대체. 금리 결측은 메우지 않고 ValueError, 음수 금리는 그대로 쓴다
- 입력 날짜가 중복 없는 오름차순이 아니면 ValueError

### 9. proxy_comparison.py

대체 시세가 기준 시세(대개 실물 ETF)를 얼마나 잘 따르는지 잰다. 비교는 기준 첫 거래일부터 두 시세가 모두 있는 날만 쓴다(시장 달력이 다른 선물 · 펀드의 빈 날을 메우지 않는다)

- `align_closes`: 두 시세의 종가를 위 규칙으로 맞춘다 (겹치는 날 2개 미만이면 ValueError). `before` 를 주면 그 날짜 앞까지만 — 실물 상장 전 구간만 보는 교차 확인용
- 아래 비교 함수는 `align_closes` 가 만든 표만 받는다 (열 · 2행 이상 · 날짜 순서를 확인하고 아니면 ValueError)
- `summarize_pair` → `PairSummary`: 일간 · 월간(월 마지막 거래일) 상관, CAGR · MDD(%), 12개월 이동 상관 최저값과 날짜. 정의되지 않는 값(수익률 2쌍 미만 · 분산 0)은 None
- `summarize_periods` → `PeriodSummary`: 기간마다 겹치는 범위로 자른 상관 · 수익률 (기준은 기간 첫날의 전날 종가, 거래일 2개 미만 기간은 뺀다). `calendar_year_periods` 가 연도 기간을 만든다
- `rolling_correlation` · `normalized_overlay`: 대시보드의 이동 상관 · 겹쳐 그리기 (대체의 상장 전 구간 포함)
- 결과 표의 열 이름(`DISPLAY_*`)과 행 변환(`pair_summary_record` · `period_summary_records`), 자릿수를 고르는 열 종류(`RATIO_DISPLAY_COLUMNS` · `PERCENT_DISPLAY_COLUMNS`) — 계산 스크립트와 대시보드가 같은 열을 쓴다. 반올림 자릿수는 CLI 가 고른다

---

## 설계 원칙

- 도메인 독립성: 특정 도메인 로직에 의존하지 않음
- 최소 의존성: 표준 라이브러리 우선 사용
- 명확한 책임: 각 모듈은 하나의 관심사만 담당
- 오류 투명성: 예외를 숨기거나 변환하지 않음

---

## 제약사항

### 병렬 처리

- 제약(pickle 가능한 함수 · `__main__` 보호)은 `src/qbt/CLAUDE.md` 「병렬 처리」
