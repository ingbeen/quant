"""
레버리지 ETF 시뮬레이션 도메인 상수

레버리지 ETF 시뮬레이션에서 사용하는 기본값과 경로를 정의한다.
- 경로 및 스펙 설정 (데이터 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값)
- 데이터 컬럼 정의 (월별 CSV 컬럼명)
"""

from typing import Final

from qbt.common_constants import (
    ETC_DIR,
    QLD_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    STOCK_DIR,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# ============================================================
# 경로 및 스펙 설정
# ============================================================

# --- 데이터 파일 경로 ---
# TQQQ (3배 레버리지 ETF) 데이터 파일 경로
TQQQ_DATA_PATH: Final = STOCK_DIR / "TQQQ_max.csv"

# 연방기금금리 월별 데이터 파일 경로
FFR_DATA_PATH: Final = ETC_DIR / "federal_funds_rate_monthly.csv"

# 운용비율(Expense Ratio) 월별 데이터 파일 경로
EXPENSE_RATIO_DATA_PATH: Final = ETC_DIR / "tqqq_net_expense_ratio_monthly.csv"

# --- 레버리지 상품 스펙 ---
DEFAULT_LEVERAGE_MULTIPLIER: Final = 3.0  # TQQQ 3배 레버리지
LEVERAGE_2X: Final = 2.0  # QLD 2배 레버리지

# 레버리지 합성 상품 — (상품 이름, 실물 시세, 배율, 합성 파일). 한 줄에 상품 하나의 연결을 모두 둠 → 저장 경로가 다른 상품과 섞이지 않음
LEVERAGED_SYNTHETIC_TARGETS: Final = (
    ("TQQQ", TQQQ_DATA_PATH, DEFAULT_LEVERAGE_MULTIPLIER, TQQQ_SYNTHETIC_DATA_PATH),
    ("QLD", QLD_DATA_PATH, LEVERAGE_2X, QLD_SYNTHETIC_DATA_PATH),
)

# ============================================================
# 비용 모델 파라미터
# ============================================================

# --- 기본값 ---
DEFAULT_PRE_LISTING_EXPENSE_RATIO: Final = 0.0095  # TQQQ 상장 이전 운용비율 가정값 (0.0095 = 0.95%)

# ============================================================
# Softplus 동적 스프레드 모델 파라미터
# ============================================================

# --- 전체기간 튜닝 최적값 (스프레드 랩 튜닝 결과의 RMSE 최소 행) ---
DEFAULT_SOFTPLUS_A: Final = -6.1  # softplus 절편 파라미터
DEFAULT_SOFTPLUS_B: Final = 0.37  # softplus 기울기 파라미터

# --- 가산금리 상한 (docs/research/합성_시세_연장.md 결정 4) ---
# 맞춘 범위(금리 5.33%) 밖 고금리에서 softplus 가 지수처럼 부풂 → 1999년 전 달에만 막음.
# 마지막 달을 1999 이후로 밀면 기존 합성의 1999년 이후 값이 바뀜 (사용자 결정 2026-11-05)
SPREAD_CAP: Final = 0.016  # 비율 (0.016 = 1.6%)
SPREAD_CAP_LAST_MONTH: Final = "1998-12"

# ============================================================
# 데이터 컬럼 정의
# ============================================================

# --- FFR 데이터 ---
COL_FFR_DATE: Final = "DATE"  # FFR CSV의 날짜 컬럼
COL_FFR_VALUE: Final = "VALUE"  # FFR CSV의 금리 값 컬럼

# --- Expense Ratio 데이터 ---
COL_EXPENSE_DATE: Final = "DATE"  # Expense Ratio CSV의 날짜 컬럼
COL_EXPENSE_VALUE: Final = "VALUE"  # Expense Ratio CSV의 값 컬럼

# --- 월 키 (yyyy-mm) ---
# 월별 딕셔너리를 문자열 비교로 가름 → 모양이 다르면 조용히 틀림
MONTH_KEY_PATTERN: Final = r"\d{4}-(0[1-9]|1[0-2])"
