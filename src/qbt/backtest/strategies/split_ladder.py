"""스플릿 매매 설정 모듈

고점에서 내려갈수록 칸을 나눠 사고, 앞 칸의 매수가로 되파는 사다리 매매의 값과 자산별 설정을 둔다.
칸마다 진입가가 달라 단일 포지션 엔진에 얹을 수 없으므로 계산은 `engines/split_engine.py` 가 한다.
규칙과 결정 근거는 `docs/research/전략_검증_보고서.md` 부록 N.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from qbt.common_constants import BACKTEST_RESULTS_DIR, TQQQ_SYNTHETIC_DATA_PATH

SPLIT_DROP_PCT: Final = 0.05  # 칸 사이 하락 비율 (0.05 = 5%)
SPLIT_MAX_LOTS: Final = 30  # 칸 수


@dataclass(frozen=True)
class SplitLadderConfig:
    """스플릿 매매의 설정. CONFIGS 에 추가하면 러너 · 대시보드에 자동으로 등록된다."""

    strategy_name: str  # 전략 내부 식별자 (예: "split_tqqq")
    display_name: str  # 전략 표시명 (예: "스플릿 매매 (TQQQ)")
    data_path: Path  # 시세 경로
    result_dir: Path  # 결과 저장 디렉토리
    start_date: date | None = None  # 이 날짜 전 시세는 쓰지 않는다 — 고점도 그 뒤 첫 종가부터 센다. None 이면 전 구간


CONFIGS: list[SplitLadderConfig] = [
    SplitLadderConfig(
        strategy_name="split_tqqq",
        display_name="스플릿 매매 (TQQQ)",
        data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "split_tqqq",
    ),
    SplitLadderConfig(
        strategy_name="split_tqqq_2004",
        display_name="스플릿 매매 (TQQQ 2004년부터)",
        data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "split_tqqq_2004",
        start_date=date(2004, 1, 1),
    ),
]
