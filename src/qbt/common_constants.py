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
TQQQ_RESULTS_DIR: Final = RESULTS_DIR / "tqqq"  # TQQQ 시뮬레이션 결과 저장 디렉토리
PORTFOLIO_RESULTS_DIR: Final = RESULTS_DIR / "portfolio"  # 포트폴리오 실험 결과
# 보완 전략 비중 그리드 요약 (포트폴리오 결과 폴더 밖 — 대시보드 실험 탐색에 섞이지 않는다)
PORTFOLIO_GRID_RESULTS_DIR: Final = RESULTS_DIR / "portfolio_grid"
PORTFOLIO_COMBO_GRID_RESULTS_DIR: Final = RESULTS_DIR / "portfolio_combo_grid"  # Q-2-2XS + HAA + 로테이션 조합 그리드 요약
PROXY_COMPARISON_RESULTS_DIR: Final = RESULTS_DIR / "proxy_comparison"  # 대체-실물 비교 요약

# --- 데이터 파일 경로 ---
# 나스닥 100 추종 ETF 데이터 파일 경로
QQQ_DATA_PATH: Final = STOCK_DIR / "QQQ_max.csv"

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
UGL_DATA_PATH: Final = STOCK_DIR / "UGL_max.csv"
UBT_DATA_PATH: Final = STOCK_DIR / "UBT_max.csv"

# 미국 외 주식 · 단기채 · 원자재 ETF 데이터 파일 경로 (대용 시계열의 대상과 대용)
EFA_DATA_PATH: Final = STOCK_DIR / "EFA_max.csv"
EEM_DATA_PATH: Final = STOCK_DIR / "EEM_max.csv"
VEA_DATA_PATH: Final = STOCK_DIR / "VEA_max.csv"
VXUS_DATA_PATH: Final = STOCK_DIR / "VXUS_max.csv"
SHY_DATA_PATH: Final = STOCK_DIR / "SHY_max.csv"
BIL_DATA_PATH: Final = STOCK_DIR / "BIL_max.csv"
DBC_DATA_PATH: Final = STOCK_DIR / "DBC_max.csv"
PDBC_DATA_PATH: Final = STOCK_DIR / "PDBC_max.csv"

# 보완 전략 배분 규칙(HAA · EWY 200일선)이 매매 · 신호에 쓰는 ETF 데이터 파일 경로
IWM_DATA_PATH: Final = STOCK_DIR / "IWM_max.csv"
VWO_DATA_PATH: Final = STOCK_DIR / "VWO_max.csv"
VNQ_DATA_PATH: Final = STOCK_DIR / "VNQ_max.csv"
IEF_DATA_PATH: Final = STOCK_DIR / "IEF_max.csv"
TIP_DATA_PATH: Final = STOCK_DIR / "TIP_max.csv"
EWY_DATA_PATH: Final = STOCK_DIR / "EWY_max.csv"

# 상장 전 구간을 대용으로 채운 이어 붙인 판 (scripts/data/generate_proxy_series.py 생성)
VEA_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "VEA_synthetic_max.csv"
BIL_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "BIL_synthetic_max.csv"
PDBC_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "PDBC_synthetic_max.csv"
VXUS_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "VXUS_synthetic_max.csv"

# 전 구간이 대용인 VXUS 합성 (실물 구간 없음, 같은 스크립트 생성)
VXUS_PROXY_DATA_PATH: Final = STOCK_DIR / "VXUS_proxy_max.csv"

# 장기 대체 시세 — 2000-08 이전에 실물 ETF 가 없던 종목을 전 기간 대신한다 (대체 판)
VGTSX_DATA_PATH: Final = STOCK_DIR / "VGTSX_max.csv"  # VXUS 와 같은 펀드의 뮤추얼 클래스
VTMGX_DATA_PATH: Final = STOCK_DIR / "VTMGX_max.csv"  # VEA 와 같은 펀드
VEIEX_DATA_PATH: Final = STOCK_DIR / "VEIEX_max.csv"  # VWO 와 같은 펀드
VGSIX_DATA_PATH: Final = STOCK_DIR / "VGSIX_max.csv"  # VNQ 와 같은 펀드
VUSTX_DATA_PATH: Final = STOCK_DIR / "VUSTX_max.csv"  # TLT 대체 (장기국채 펀드)
VFITX_DATA_PATH: Final = STOCK_DIR / "VFITX_max.csv"  # IEF 대체 (중기국채 펀드)
VFISX_DATA_PATH: Final = STOCK_DIR / "VFISX_max.csv"  # SHY 대체 (단기국채 펀드)
VIPSX_DATA_PATH: Final = STOCK_DIR / "VIPSX_max.csv"  # TIP 대체 (물가연동채 펀드)
# 다운로더가 티커를 그대로 파일 이름에 쓴다
SPGSCI_DATA_PATH: Final = STOCK_DIR / "^SPGSCI_max.csv"  # S&P GSCI 원자재 지수
GOLD_FUTURES_DATA_PATH: Final = STOCK_DIR / "GC=F_max.csv"  # 금 선물 연속물 (GLD 대체)

# 대체 판 생성 파일 (scripts/data/generate_long_proxy_series.py 생성)
SSO_PROXY_DATA_PATH: Final = STOCK_DIR / "SSO_proxy_max.csv"  # SPY 2배 합성, 전 구간
QLD_PROXY_DATA_PATH: Final = STOCK_DIR / "QLD_proxy_max.csv"  # QQQ 2배 합성, 전 구간
BIL_PROXY_DATA_PATH: Final = STOCK_DIR / "BIL_proxy_max.csv"  # 연방기금금리 누적, 전 구간
DBC_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "DBC_synthetic_max.csv"  # S&P GSCI → DBC 이어 붙인 판

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

# --- 출력용 컬럼명 (사용자 표시용) ---
DISPLAY_DATE: Final = "날짜"

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
