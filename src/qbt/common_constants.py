"""
QBT 프로젝트 공통 상수

모든 도메인에서 공통으로 사용하는 상수를 정의한다.
- 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
- 데이터 상수 (컬럼명)
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

# 데이터 저장소(quant-data)가 받고 · 가공해 내보낸 시세 사본 — 받을 파일 목록은 이 폴더의 quant_data_files.txt
STOCK_DIR: Final = STORAGE_DIR / "stock"
RESULTS_DIR: Final = STORAGE_DIR / "results"  # 분석 결과 저장 디렉토리
BACKTEST_RESULTS_DIR: Final = RESULTS_DIR / "backtest"  # 백테스트 결과 저장 디렉토리
PORTFOLIO_RESULTS_DIR: Final = RESULTS_DIR / "portfolio"  # 포트폴리오 실험 결과

# --- 데이터 파일 경로 ---
# 이름은 `{티커}_{가격 기준}.csv` — 합성(synthetic)은 상장 전 구간을 대용 · 시뮬레이션으로 채우고 상장 후는 실물 수정주가다

# 합성 QQQ (상장 전은 나스닥 100 지수)
QQQ_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "QQQ_synthetic.csv"

# 합성 SPY (상장 전은 VFINX)
SPY_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "SPY_synthetic.csv"

# 합성 TLT (상장 전은 VUSTX)
TLT_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "TLT_synthetic.csv"

# 합성 GLD (상장 전은 Perth Mint 금값 · 금 선물을 이은 사슬)
GLD_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "GLD_synthetic.csv"

# 합성 TQQQ · QLD · SSO · UPRO (상장 전은 1배 합성을 배율만큼 굴린 시뮬레이션)
TQQQ_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "TQQQ_synthetic.csv"
QLD_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "QLD_synthetic.csv"
SSO_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "SSO_synthetic.csv"
UPRO_SYNTHETIC_DATA_PATH: Final = STOCK_DIR / "UPRO_synthetic.csv"

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

# ============================================================
# 반올림 규칙 상수 — 이 저장소의 자릿수 SoT
# CSV/JSON 저장 직전에만 적용하며, 계산 정밀도는 바꾸지 않는다
# ============================================================

ROUND_PRICE: Final = 4  # 가격 (종가, 시가, 밴드, 체결가 등)
ROUND_CAPITAL: Final = 0  # 자본금 (equity, pnl) -> 정수
ROUND_PERCENT: Final = 2  # 백분율 (수익률, MDD, 승률, 드로우다운)
ROUND_RATIO: Final = 4  # 비율 (0~1, buy_buffer_zone_pct, pnl_pct)
