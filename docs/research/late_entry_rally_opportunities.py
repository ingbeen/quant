"""버퍼존 트레이드 내 지연진입 기회 탐지 (랠리 재확대 규칙).

운용자가 정의한 규칙으로 각 트레이드 안의 지연진입 기회를 찾는다.

규칙:
    1. 트레이드 시작 후 프리미엄(종가/EMA200 - 1)이 STRETCH(+10%) 이상 벌어지면 준비 상태.
    2. 준비 상태에서 프리미엄이 DIP(+5%) 이하로 내려온 날 = 기회. 다음 거래일 시가 매수.
    3. 기회가 인정되면 준비 상태가 해제되며, 다시 STRETCH 이상 벌어져야 다음 기회를 인정한다.
    4. 직전 인정된 기회로부터 COOLDOWN_DAYS(60일, 약 2달) 안에 걸린 신호는 휩소로 보고 버린다.
       이때 준비 상태도 함께 해제되므로(엄격 방식), 다시 STRETCH 이상 벌어져야 다음 기회가 인정된다.
    5. 기회일이 매도 시그널일(하단밴드 종가 이탈일)이면 다음날이 청산일이므로 매수 불가로 처리한다.

성과 계산은 전략 엔진과 동일한 체결 규약을 따른다:
    매수 = 기회일 다음 거래일 시가 × (1 + SLIPPAGE_RATE), 청산 = 트레이드의 실제 청산가(엔진 기록값).

완료된 트레이드의 기회별 성과표에 더해, 진행 중 포지션(summary.json의 open_position)이
있으면 현재 트레이드의 기회 이력과 다음 기회 발동 조건도 출력한다.

배경과 결론 해석은 같은 폴더의 `QQQ_지연진입_연구.md` 참고.

실행:
    poetry run python docs/research/late_entry_rally_opportunities.py
    poetry run python docs/research/late_entry_rally_opportunities.py --asset gld
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.common_constants import BACKTEST_RESULTS_DIR, COL_CLOSE, COL_DATE, COL_OPEN

MA_COL = "ma_200"

# 랠리 재확대 기준 (프리미엄이 이 이상 벌어져야 "새 랠리"로 인정)
STRETCH = 0.10

# 복귀 기준 (준비 상태에서 프리미엄이 이 이하로 내려오면 기회)
DIP = 0.05

# 휩소 제거: 직전 인정된 기회로부터 이 일수(달력일) 안의 신호는 버린다
COOLDOWN_DAYS = 60

# 분할 진입 트랜치 수. 균등 배분 고정이며 튜닝하지 않는다
# (전략_검증_보고서 부록 G.4 재최적화 금지 / §25.6 암묵적 자유도 경고)
SPLIT_TRANCHES = 3

# 부분비중 정책에서 검토할 총 투입 비중 (0.25 = 자본의 25%)
PARTIAL_WEIGHTS = (0.25, 0.50, 0.75)


@dataclass
class TradeSeg:
    """한 트레이드의 보유 구간(진입 체결 익일 ~ 매도 시그널일) 데이터."""

    trade_id: str
    dates: np.ndarray  # datetime64[ns]
    opens: np.ndarray
    prem: np.ndarray  # 종가/EMA200 - 1
    elapsed: np.ndarray  # 진입 체결일 대비 경과 달력일
    exit_price: float  # 엔진 기록 매도 체결가 (슬리피지 포함)


def load_signal(asset: str) -> pd.DataFrame:
    """자산의 시그널 CSV를 로드한다."""
    return pd.read_csv(BACKTEST_RESULTS_DIR / f"buffer_zone_{asset}" / "signal.csv", parse_dates=[COL_DATE])


def load_trade_segs(asset: str) -> list[TradeSeg]:
    """완료된 트레이드들의 보유 구간 데이터를 만든다."""
    sig = load_signal(asset)
    trades = pd.read_csv(
        BACKTEST_RESULTS_DIR / f"buffer_zone_{asset}" / "trades.csv", parse_dates=["entry_date", "exit_date"]
    )
    segs: list[TradeSeg] = []
    for _, t in trades.iterrows():
        seg = sig.loc[(sig[COL_DATE] > t["entry_date"]) & (sig[COL_DATE] < t["exit_date"])]
        if seg.empty:
            continue
        closes = seg[COL_CLOSE].to_numpy(dtype=float)
        ema = seg[MA_COL].to_numpy(dtype=float)
        dates = seg[COL_DATE].to_numpy()
        segs.append(
            TradeSeg(
                trade_id=str(t["entry_date"].date()),
                dates=dates,
                opens=seg[COL_OPEN].to_numpy(dtype=float),
                prem=closes / ema - 1,
                elapsed=((dates - np.datetime64(t["entry_date"])) / np.timedelta64(1, "D")).astype(float),
                exit_price=float(t["exit_price"]),
            )
        )
    return segs


def find_opportunities(dates: np.ndarray, prem: np.ndarray, cooldown_days: int) -> tuple[list[int], bool]:
    """규칙에 따라 기회일 인덱스 목록과 마지막 날의 준비 상태를 반환한다."""
    opps: list[int] = []
    armed = False
    last_opp: np.datetime64 | None = None
    for i in range(len(prem)):
        if prem[i] >= STRETCH:
            armed = True
        elif armed and prem[i] <= DIP:
            armed = False
            if last_opp is None or (dates[i] - last_opp) / np.timedelta64(1, "D") >= cooldown_days:
                opps.append(i)
                last_opp = dates[i]
            # 휩소(쿨다운 이내)면 카운트 없이 준비 상태만 소모된다 (엄격 방식)
    return opps, armed


def build_table(segs: list[TradeSeg]) -> tuple[pd.DataFrame, list[str]]:
    """전체 트레이드의 기회별 성과 표와 휩소로 제외된 날짜 목록을 만든다."""
    rows: list[dict[str, object]] = []
    removed: list[str] = []
    for seg in segs:
        n = len(seg.prem)
        opps, _ = find_opportunities(seg.dates, seg.prem, COOLDOWN_DAYS)
        no_cooldown, _ = find_opportunities(seg.dates, seg.prem, 0)
        kept_dates = {seg.dates[i] for i in opps}
        removed.extend(
            f"{seg.trade_id}: {pd.Timestamp(seg.dates[i]).date()}"
            for i in no_cooldown
            if seg.dates[i] not in kept_dates
        )
        for rank, i in enumerate(opps, start=1):
            opp_date = pd.Timestamp(seg.dates[i]).date()
            elapsed = int(seg.elapsed[i])
            if i >= n - 1:
                rows.append(
                    {
                        "트레이드": seg.trade_id,
                        "순번": rank,
                        "기회일": opp_date,
                        "며칠째": elapsed,
                        "매수일": "매도시그널일-진입불가",
                        "매수가": None,
                        "수익률%": None,
                    }
                )
                continue
            buy = seg.opens[i + 1] * (1 + SLIPPAGE_RATE)
            rows.append(
                {
                    "트레이드": seg.trade_id,
                    "순번": rank,
                    "기회일": opp_date,
                    "며칠째": elapsed,
                    "매수일": str(pd.Timestamp(seg.dates[i + 1]).date()),
                    "매수가": round(float(buy), 2),
                    "수익률%": round((seg.exit_price / buy - 1) * 100, 1),
                }
            )
    return pd.DataFrame(rows), removed


def print_stats(label: str, df: pd.DataFrame) -> None:
    """기회 부분집합 하나의 통계를 출력한다."""
    r = df["수익률%"].dropna().astype(float)
    print(f"\n[{label}]")
    if r.empty:
        print("  진입 가능한 기회가 없습니다.")
        return
    print(f"  진입 가능한 기회 {len(r)}회 (기회 자체는 {len(df)}회, 진입불가 {len(df) - len(r)}회)")
    print(f"  승 {(r > 0).sum()} / 패 {(r <= 0).sum()}  (승률 {(r > 0).mean() * 100:.0f}%)")
    print(f"  평균 {r.mean():+.1f}% / 중앙값 {r.median():+.1f}% / 최고 {r.max():+.1f}% / 최악 {r.min():+.1f}%")
    early = df.loc[df["며칠째"] <= 365, "수익률%"].dropna().astype(float)
    late = df.loc[df["며칠째"] > 365, "수익률%"].dropna().astype(float)
    if not early.empty:
        print(f"  트레이드 시작 1년 이내 기회: {len(early)}회, 평균 {early.mean():+.1f}%, 승률 {(early > 0).mean() * 100:.0f}%")
    if not late.empty:
        print(f"  트레이드 시작 1년 이후 기회: {len(late)}회, 평균 {late.mean():+.1f}%, 승률 {(late > 0).mean() * 100:.0f}%")


def print_summary(df: pd.DataFrame, segs: list[TradeSeg]) -> None:
    """전체 및 2번째 이후 기회의 요약 통계를 출력한다."""
    print_stats("전체 기회", df)
    print_stats("2번째 이후 기회 (각 트레이드의 첫 기회 제외)", df.loc[df["순번"] >= 2])
    zero = [s.trade_id for s in segs if s.trade_id not in set(df["트레이드"])]
    if zero:
        print(f"\n  기회가 없었던 트레이드: {', '.join(zero)}")


@dataclass
class PolicyOutcome:
    """트레이드 하나에 정책 하나를 적용한 결과."""

    trade_id: str
    deployed: float  # 실제 투입된 자본 비중 (0~1)
    total_return: float  # 전체 자본 기준 수익률 (미투입분은 0%로 계산)
    deployed_return: float | None  # 투입 자본 기준 수익률 (미투입이면 None)


def opportunity_buy_prices(seg: TradeSeg) -> list[float]:
    """트레이드의 기회별 매수 체결가 목록을 순번대로 반환한다.

    기회일이 마지막 행이면 익일 시가가 없어 매수할 수 없으므로 제외한다.
    """
    opps, _ = find_opportunities(seg.dates, seg.prem, COOLDOWN_DAYS)
    return [float(seg.opens[i + 1]) * (1 + SLIPPAGE_RATE) for i in opps if i + 1 < len(seg.prem)]


def apply_policy(seg: TradeSeg, tranches: int, weight: float) -> PolicyOutcome:
    """총 비중 weight를 tranches 조각으로 나눠 넣는 정책을 트레이드 하나에 적용한다.

    tranches=1이면 첫 기회 일괄 진입이다. 기회 수가 tranches보다 적으면 남은 비중은
    현금으로 남으며 수익률 0%로 계산된다. 청산은 전제 조건에 따라 매도 시그널에서 전량이다.

    Args:
        seg: 대상 트레이드의 보유 구간 데이터
        tranches: 분할 조각 수 (1이면 일괄)
        weight: 총 투입 비중 (1.0 = 자본 전액)

    Returns:
        전체 자본 기준과 투입 자본 기준 수익률을 담은 결과
    """
    prices = opportunity_buy_prices(seg)[:tranches]
    per_tranche = weight / tranches
    total = sum(per_tranche * (seg.exit_price / p - 1) for p in prices)
    deployed = per_tranche * len(prices)
    return PolicyOutcome(
        trade_id=seg.trade_id,
        deployed=deployed,
        total_return=total,
        deployed_return=(total / deployed) if deployed > 0 else None,
    )


def summarize_policy(label: str, outcomes: list[PolicyOutcome]) -> dict[str, object]:
    """정책 하나의 트레이드 단위 요약 통계를 만든다."""
    rets = np.array([o.total_return for o in outcomes], dtype=float)
    return {
        "정책": label,
        "관측": len(rets),
        "승": int((rets > 0).sum()),
        "무": int((rets == 0).sum()),
        "패": int((rets < 0).sum()),
        "승률%": round(float((rets > 0).mean() * 100), 1),
        "중앙값%": round(float(np.median(rets) * 100), 2),
        "평균%": round(float(rets.mean() * 100), 2),
        "최악%": round(float(rets.min() * 100), 2),
        "최고%": round(float(rets.max() * 100), 2),
        "평균투입비중%": round(float(np.mean([o.deployed for o in outcomes]) * 100), 1),
    }


def print_policy_comparison(segs: list[TradeSeg]) -> None:
    """실행 가능한 지연진입 정책들을 트레이드 단위로 비교 출력한다."""
    p1 = [apply_policy(s, tranches=1, weight=1.0) for s in segs]
    p3 = [apply_policy(s, tranches=SPLIT_TRANCHES, weight=1.0) for s in segs]

    rows: list[dict[str, object]] = [
        {
            "정책": "P0 미진입",
            "관측": len(segs),
            "승": 0,
            "무": len(segs),
            "패": 0,
            "승률%": 0.0,
            "중앙값%": 0.0,
            "평균%": 0.0,
            "최악%": 0.0,
            "최고%": 0.0,
            "평균투입비중%": 0.0,
        },
        summarize_policy("P1 첫기회 일괄100%", p1),
        summarize_policy(f"P3 분할 N={SPLIT_TRANCHES} 균등", p3),
    ]
    for w in PARTIAL_WEIGHTS:
        rows.append(summarize_policy(f"P4 부분비중 w={w:.2f}", [apply_policy(s, 1, w) for s in segs]))
    for w in PARTIAL_WEIGHTS:
        rows.append(
            summarize_policy(f"P5 조합 w={w:.2f}×N={SPLIT_TRANCHES}", [apply_policy(s, SPLIT_TRANCHES, w) for s in segs])
        )

    print("\n" + "=" * 90)
    print("[정책별 트레이드 단위 성과 — 전체 자본 기준] 기회 없던 트레이드는 0%로 포함")
    print(pd.DataFrame(rows).to_string(index=False))

    # 조건 3: 분할의 이득이 「덜 넣어서」가 아니라 「평단가」에서 나오는지 확인한다.
    # P3와 같은 비중을 첫 기회에 한 번에 넣는 정책을 트레이드마다 만들어 대조한다.
    print("\n[조건 3] 분할(P3) vs 같은 비중을 첫 기회에 일괄 — 투입 비중을 맞춘 대조")
    detail: list[dict[str, object]] = []
    for seg, a in zip(segs, p3, strict=True):
        matched = apply_policy(seg, tranches=1, weight=a.deployed) if a.deployed > 0 else None
        detail.append(
            {
                "트레이드": seg.trade_id,
                "기회수": len(opportunity_buy_prices(seg)),
                "P3투입%": round(a.deployed * 100, 1),
                "P3수익%": round(a.total_return * 100, 2),
                "동일비중일괄%": round(matched.total_return * 100, 2) if matched else 0.0,
                "분할이득%p": round((a.total_return - (matched.total_return if matched else 0.0)) * 100, 2),
            }
        )
    detail_df = pd.DataFrame(detail)
    print(detail_df.to_string(index=False))
    gain = detail_df["분할이득%p"].astype(float)
    print(f"\n  분할이득 합계 {gain.sum():+.2f}%p / 평균 {gain.mean():+.2f}%p / 중앙값 {gain.median():+.2f}%p")
    print(f"  분할이 유리했던 트레이드 {int((gain > 0).sum())}건 / 불리 {int((gain < 0).sum())}건 / 동일 {int((gain == 0).sum())}건")

    # 검증: P1은 기회별 성과표(build_table)의 순번 1 행과 일치해야 한다. 계산 경로가 다르므로 교차 검증이 된다.
    table, _ = build_table(segs)
    first = table.loc[table["순번"] == 1].set_index("트레이드")["수익률%"]
    mismatch = [
        f"{o.trade_id}: 정책 {o.total_return * 100:.1f}% vs 표 {float(first[o.trade_id]):.1f}%"
        for o in p1
        if o.trade_id in first.index and abs(o.total_return * 100 - float(first[o.trade_id])) > 0.05
    ]
    print("\n[검증] P1 vs 기회별 성과표 순번 1: " + ("일치" if not mismatch else f"불일치 {mismatch}"))


def print_current_status(asset: str) -> None:
    """진행 중 포지션이 있으면 현재 트레이드의 기회 이력과 발동 조건을 출력한다."""
    summary_path = BACKTEST_RESULTS_DIR / f"buffer_zone_{asset}" / "summary.json"
    with open(summary_path, encoding="utf-8") as f:
        open_pos = json.load(f)["summary"].get("open_position")
    if not open_pos:
        return
    entry_date = pd.Timestamp(open_pos["entry_date"])
    sig = load_signal(asset)
    seg = sig.loc[sig[COL_DATE] > entry_date]
    if seg.empty:
        return
    closes = seg[COL_CLOSE].to_numpy(dtype=float)
    ema = seg[MA_COL].to_numpy(dtype=float)
    dates = seg[COL_DATE].to_numpy()
    prem = closes / ema - 1
    opps, armed = find_opportunities(dates, prem, COOLDOWN_DAYS)
    cur = seg.iloc[-1]
    elapsed = int((dates[-1] - np.datetime64(entry_date)) / np.timedelta64(1, "D"))

    print("\n" + "=" * 90)
    print(f"[진행 중 트레이드] 진입 {entry_date.date()} / 경과 {elapsed}일 / 데이터 기준일 {cur[COL_DATE].date()}")
    if not opps:
        print("  지나간 기회 없음")
    for rank, i in enumerate(opps, start=1):
        if i + 1 < len(seg):
            note = f"매수했다면 {float(seg.iloc[i + 1][COL_OPEN]) * (1 + SLIPPAGE_RATE):.2f}"
        else:
            note = "익일 시가 데이터 없음"
        print(f"  지나간 기회 {rank}: {pd.Timestamp(dates[i]).date()} (프리미엄 {prem[i]:+.2%}, {note})")
    trigger_px = float(cur[MA_COL]) * (1 + DIP)
    gap = (trigger_px / float(cur[COL_CLOSE]) - 1) * 100
    print(f"  현재 프리미엄 {prem[-1]:+.2%} / 준비 상태({STRETCH:.0%} 재확대 후 대기): {'예' if armed else '아니오'}")
    print(f"  다음 기회 발동 조건: 종가 <= SMA200×{1 + DIP:.2f} = {trigger_px:.2f} (현재가 대비 {gap:+.1f}%)")
    if opps:
        days_since = (dates[-1] - dates[opps[-1]]) / np.timedelta64(1, "D")
        print(f"  직전 기회로부터 {days_since:.0f}일 경과 (휩소 기준 {COOLDOWN_DAYS}일)")


def main() -> None:
    parser = argparse.ArgumentParser(description="지연진입 기회 탐지 (랠리 재확대 규칙)")
    parser.add_argument("--asset", choices=["qqq", "gld", "tlt"], default="qqq")
    args = parser.parse_args()

    segs = load_trade_segs(args.asset)
    print(f"자산 {args.asset.upper()} / 완료 트레이드 {len(segs)}개")
    print(f"규칙: 벌어짐 {STRETCH:.0%} → 복귀 {DIP:.0%} 이하 = 기회, 직전 기회 후 {COOLDOWN_DAYS}일 이내 휩소 제외")
    print("=" * 90)

    df, removed = build_table(segs)
    for trade_id, sub in df.groupby("트레이드", sort=True):
        seg = next(s for s in segs if s.trade_id == trade_id)
        sig_day = pd.Timestamp(seg.dates[-1]).date()
        print(f"\n[트레이드 {trade_id}] 매도시그널일 {sig_day} / 청산가 {seg.exit_price:.2f}")
        print(sub.drop(columns=["트레이드"]).to_string(index=False))

    print("\n" + "=" * 90)
    print("[휩소로 제외된 신호]")
    for line in removed:
        print(f"  {line}")
    print("\n[전체 요약]")
    print_summary(df, segs)
    print_policy_comparison(segs)
    print_current_status(args.asset)


if __name__ == "__main__":
    main()
