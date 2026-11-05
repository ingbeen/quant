"""
QBT 프로젝트 공통 상수

모든 도메인에서 공통으로 사용하는 상수를 정의한다.
- 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
- 데이터 상수 (컬럼명, 연간 영업일, 수치 안정성 등)
"""

from pathlib import Path
from typing import Final

# ============================================================
# 경로 상수
# ============================================================

# --- 디렉토리 경로 ---
# 실행 위치(저장소 루트) 기준 상대 경로다. 파일 위치 기준 절대 경로로 바꾸지 않는다 — 결과 파일(summary.json 등)에
# 경로 문자열이 실려, 절대 경로면 공개 저장소에 로컬 경로가 올라간다. CLI 스크립트는 cli_exception_handler 가
# 저장소 루트에서 실행됐는지 확인한다
STORAGE_DIR: Final = Path("storage")

STOCK_DIR: Final = STORAGE_DIR / "stock"  # 주식 데이터 저장 디렉토리
ETC_DIR: Final = STORAGE_DIR / "etc"  # 금리 등 기타 데이터 저장 디렉토리
RESULTS_DIR: Final = STORAGE_DIR / "results"  # 분석 결과 저장 디렉토리
BACKTEST_RESULTS_DIR: Final = RESULTS_DIR / "backtest"  # 백테스트 결과 저장 디렉토리
PORTFOLIO_RESULTS_DIR: Final = RESULTS_DIR / "portfolio"  # 포트폴리오 실험 결과
PROXY_VALIDATION_RESULTS_DIR: Final = RESULTS_DIR / "proxy_validation"  # 상장 전 구간을 채운 합성 시세의 검증 표

# --- 데이터 파일 경로 ---
# 나스닥 100 추종 ETF 데이터 파일 경로
QQQ_DATA_PATH: Final = STOCK_DIR / "QQQ_max.csv"

# 나스닥 100 지수 — QQQ 상장 전 구간의 대용
NDX_DATA_PATH: Final = STOCK_DIR / "^NDX_max.csv"

# 합성 QQQ 데이터 파일 경로 (상장 전은 나스닥 100 지수, 상장 후는 실물)
QQQ_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "QQQ_synthetic_max.csv"

# 합성 TQQQ · QLD 데이터 파일 경로 (시뮬레이션 생성)
TQQQ_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "TQQQ_synthetic_max.csv"
QLD_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "QLD_synthetic_max.csv"

# 교차 자산 검증용 데이터 파일 경로
SPY_DATA_PATH: Final = STOCK_DIR / "SPY_max.csv"
GLD_DATA_PATH: Final = STOCK_DIR / "GLD_max.csv"
TLT_DATA_PATH: Final = STOCK_DIR / "TLT_max.csv"

# 2배 레버리지 ETF 데이터 파일 경로
SSO_DATA_PATH: Final = STOCK_DIR / "SSO_max.csv"
QLD_DATA_PATH: Final = STOCK_DIR / "QLD_max.csv"

# 레버리지 ETF 상장 전의 펀드 — 합성의 상장 전 구간 대조
UOPIX_DATA_PATH: Final = STOCK_DIR / "UOPIX_max.csv"  # ProFunds 나스닥 100 2배
RYNVX_DATA_PATH: Final = STOCK_DIR / "RYNVX_max.csv"  # Rydex S&P 500 1.5배

# S&P 500 인덱스 펀드 (배당 포함) — RYNVX 대조의 기초
VFINX_DATA_PATH: Final = STOCK_DIR / "VFINX_max.csv"

# ============================================================
# 데이터 상수
# ============================================================

# --- CSV 컬럼명 (DataFrame 내부용) ---
COL_DATE: Final = "Date"  # 날짜 컬럼
COL_OPEN: Final = "Open"  # 시가 (Open Price)
COL_HIGH: Final = "High"  # 고가 (High Price)
COL_LOW: Final = "Low"  # 저가 (Low Price)
COL_CLOSE: Final = "Close"  # 종가 (Close Price)
COL_VOLUME: Final = "Volume"  # 거래량

# 컬럼 그룹
REQUIRED_COLUMNS: Final = [COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME]

# 가격 관련 컬럼만 따로 묶음 (검증 시 양수 체크 등에 사용)
PRICE_COLUMNS: Final = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]

# --- 기타 데이터 상수 ---

# 1년의 평균 달력 일수 (윤년 포함) — CAGR 의 연수 환산에 쓴다
ANNUAL_DAYS: Final = 365.25

# 주식 시장의 연간 거래일 수 (주말, 공휴일 제외) — 일일 비용과 연간 비용을 서로 환산할 때 쓴다
TRADING_DAYS_PER_YEAR: Final = 252

# 수치 안정성 상수 — 분모 0 방지 및 로그 계산 안정성 확보
EPSILON: Final = 1e-12

# ============================================================
# 반올림 규칙 상수 — 이 저장소의 자릿수 SoT
# CSV/JSON 저장 직전에만 적용하며, 계산 정밀도는 바꾸지 않는다
# ============================================================

ROUND_PRICE: Final = 4  # 가격 (종가, 시가, 밴드, 체결가 등)
ROUND_CAPITAL: Final = 0  # 자본금 (equity, pnl) -> 정수
ROUND_PERCENT: Final = 2  # 백분율 (수익률, MDD, 승률, 드로우다운)
ROUND_RATIO: Final = 4  # 비율 (0~1, buy_buffer_zone_pct, pnl_pct)
