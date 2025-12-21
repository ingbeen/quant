"""
합성 데이터 생성 도메인 상수

레버리지 ETF 시뮬레이션에서 사용하는 기본값과 검증 임계값을 정의한다.
"""

# 레버리지 ETF 기본값
DEFAULT_LEVERAGE_MULTIPLIER = 3.0  # TQQQ 3배 레버리지
DEFAULT_FUNDING_SPREAD = 0.004  # FFR 스프레드 (%)
DEFAULT_EXPENSE_RATIO = 0.085  # 연간 비용 비율 (%)

# 합성 데이터 초기 가격
DEFAULT_SYNTHETIC_INITIAL_PRICE = 200.0

# 검증 임계값
MAX_FFR_MONTHS_DIFF = 2  # FFR 데이터 최대 월 차이

# 그리드 서치 기본 범위
DEFAULT_SPREAD_RANGE = (0.004, 0.008)  # 스프레드 범위 (%)
DEFAULT_SPREAD_STEP = 0.0005  # 스프레드 증분 (%)
DEFAULT_EXPENSE_RANGE = (0.0075, 0.0105)  # expense ratio 범위 (%)
DEFAULT_EXPENSE_STEP = 0.0005  # expense ratio 증분 (%)

# 결과 제한
MAX_TOP_STRATEGIES = 50  # find_optimal_cost_model 반환 상위 전략 수
