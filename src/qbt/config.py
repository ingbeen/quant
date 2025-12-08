"""
QBT 프로젝트 전역 설정

모든 도메인에서 공통으로 사용하는 경로 상수와 설정을 정의한다.
"""

from pathlib import Path

# 디렉토리 경로
DATA_DIR = Path("data/raw")
RESULTS_DIR = Path("results")

# 데이터 파일 경로
QQQ_DATA_PATH = DATA_DIR / "QQQ_max.csv"
TQQQ_DATA_PATH = DATA_DIR / "TQQQ_max.csv"
TQQQ_SYNTHETIC_PATH = DATA_DIR / "TQQQ_synthetic_max.csv"
FFR_DATA_PATH = DATA_DIR / "federal_funds_rate_monthly.csv"

# 결과 파일 경로
GRID_RESULTS_PATH = RESULTS_DIR / "grid_results.csv"
TQQQ_VALIDATION_PATH = RESULTS_DIR / "tqqq_validation.csv"
TQQQ_DAILY_COMPARISON_PATH = RESULTS_DIR / "tqqq_daily_comparison.csv"
