"""보완 전략 실험 모듈 테스트

Q-2-2XS (100−w)% + 후보 w% 비중 그리드의 구성 만들기 · 실행 목록 · 지표 · 신호 일치율 ·
기준선 대비 우위 · 통과 판정(D24 · D47) · 대용 검증(D23 · D41 · D48)의 계약과,
조합 실험(D55 – D69)이 쓰는 대체 판 · 조합 구성 · 2001 – 2007 국면 구간의 계약을 검증한다.

왜 중요한가요?
통과 · 탈락은 사용자가 이 숫자를 보고 정한다. 비교 상대(같은 시작일 · 같은 w 의 기준선),
「높다」의 경계, 두 기간 조건, 월말 판단만 세는 신호 일치율이 한 군데만 어긋나도
판정이 에러 없이 바뀐다.
"""

import dataclasses
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest import supplement_experiment as se
from qbt.backtest.allocators.ewy_buffer_zone import EWY_ASSET_IDS
from qbt.backtest.allocators.haa import HAA_ASSET_IDS, HAA_SERIES_IDS
from qbt.backtest.allocators.us_weakness_rotation import ROTATION_ASSET_IDS, ROTATION_SERIES_IDS
from qbt.backtest.engines.portfolio_data import validate_portfolio_config
from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.portfolio_types import (
    AllocatorMethodConfig,
    PortfolioConfig,
    PortfolioResult,
    SlotMethodConfig,
)
from qbt.common_constants import (
    BIL_DATA_PATH,
    BIL_PROXY_DATA_PATH,
    BIL_SYNTHETIC_DATA_PATH,
    COL_DATE,
    DBC_DATA_PATH,
    DBC_SYNTHETIC_DATA_PATH,
    EFA_DATA_PATH,
    GLD_DATA_PATH,
    GOLD_FUTURES_DATA_PATH,
    IEF_DATA_PATH,
    IWM_DATA_PATH,
    PDBC_DATA_PATH,
    PDBC_SYNTHETIC_DATA_PATH,
    QLD_DATA_PATH,
    QLD_PROXY_DATA_PATH,
    QQQ_DATA_PATH,
    SHY_DATA_PATH,
    SPY_DATA_PATH,
    SSO_DATA_PATH,
    SSO_PROXY_DATA_PATH,
    TIP_DATA_PATH,
    TLT_DATA_PATH,
    VEA_DATA_PATH,
    VEA_SYNTHETIC_DATA_PATH,
    VEIEX_DATA_PATH,
    VFISX_DATA_PATH,
    VFITX_DATA_PATH,
    VGSIX_DATA_PATH,
    VGTSX_DATA_PATH,
    VIPSX_DATA_PATH,
    VNQ_DATA_PATH,
    VTMGX_DATA_PATH,
    VUSTX_DATA_PATH,
    VWO_DATA_PATH,
    VXUS_DATA_PATH,
    VXUS_PROXY_DATA_PATH,
    VXUS_SYNTHETIC_DATA_PATH,
)

_Q2_SLOTS = get_portfolio_config("portfolio_q2_2xs").asset_slots
_START = date(2007, 6, 22)

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _summary(calmar: float, start: date = _START, trading_days: int = 4800) -> se.RunSummary:
    return se.RunSummary(
        start_date=start,
        end_date=date(2026, 9, 24),
        trading_days=trading_days,
        cagr=10.0,
        mdd=-20.0,
        calmar=calmar,
        sell_trades=0,
        annual_turnover=0.0,
        phase_returns={},
        phase_mdds={},
    )


def _advantages(values: list[float]) -> dict[int, float]:
    return dict(zip(se.W_PCTS, values, strict=True))


def _targets(dates: list[date], rows: list[dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.Index(dates, name=COL_DATE))


def _config_paths(config: PortfolioConfig) -> set[Path]:
    """설정이 가리키는 모든 시세 경로 — 데이터클래스 필드를 재귀로 훑어 Path 값을 모은다(결과 폴더는 뺀다).

    필드를 손으로 나열하지 않는다 — 설정 타입에 경로 칸이 새로 생겨도 대체 판 검사에서 빠지지 않게.
    """
    paths: set[Path] = set()

    def visit(value: object) -> None:
        if isinstance(value, Path):
            paths.add(value)
        elif isinstance(value, tuple):
            for item in value:
                visit(item)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            for f in dataclasses.fields(value):
                if f.name != "result_dir":
                    visit(getattr(value, f.name))

    visit(config)
    return paths


def _fake_results(
    calmar_of: dict[tuple[str, str, str], float],
    targets_of: dict[tuple[str, str, str], pd.DataFrame] | None = None,
) -> list[se.GridCaseResult]:
    """149개 실행 전부에 가짜 요약을 붙인다. calmar_of 키 (묶음, 후보, 판) 가 없으면 Calmar 0.5"""
    month_dates = [date(2016, m, 1) for m in range(1, 5)]
    default_targets = {
        se.CANDIDATE_HAA: _targets(month_dates, [{"spy": 0.25, "bil": 0.75}] * 4),
        se.CANDIDATE_ROTATION: _targets(month_dates, [{"vxus": 1.0, "shy": 0.0}] * 4),
    }
    results: list[se.GridCaseResult] = []
    for case in se.build_grid_cases():
        key = (case.group, case.candidate, case.variant)
        calmar = calmar_of.get(key, 0.5)
        targets = None
        if case.candidate in se.PROXY_CANDIDATES:
            targets = (targets_of or {}).get(key, default_targets[case.candidate])
        results.append(se.GridCaseResult(case, _summary(calmar, case.start_date), [], targets))
    return results


# ============================================================================
# 구성 만들기
# ============================================================================


class TestBuildExperimentConfig:
    """build_experiment_config 의 매매법 · 몫 · 자산 id · 데이터 판 계약."""

    @pytest.mark.parametrize("candidate", se.SUPPLEMENT_CANDIDATES + (se.CANDIDATE_BASELINE,))
    def test_shares_sum_to_one_and_q2_2xs_first(self, candidate: str) -> None:
        """
        목적: 모든 w 에서 Q-2-2XS 매매법이 앞이고 몫이 (100 − w)% · w% 로 합이 1 이다 (D5 · D40).

        Given: 후보 하나
        When:  w 7단계 각각으로 구성을 만든다
        Then:  매매법 둘, 첫째는 q2_2xs(몫 1 − w, 넘긴 슬롯 그대로), 둘째는 후보(몫 w)
        """
        for w in se.W_PCTS:
            # When
            config = se.build_experiment_config(_Q2_SLOTS, candidate, w, se.VARIANT_SPLICED, _START)

            # Then
            q2, cand = config.methods
            assert isinstance(q2, SlotMethodConfig)
            assert q2.method_id == se.CANDIDATE_Q2_2XS
            assert q2.asset_slots == _Q2_SLOTS
            assert q2.target_weight == pytest.approx((100 - w) / 100, abs=1e-12)
            assert cand.method_id == candidate
            assert cand.target_weight == pytest.approx(w / 100, abs=1e-12)
            assert q2.target_weight + cand.target_weight == pytest.approx(1.0, abs=1e-12)

    def test_allocator_candidates_use_rule_ids(self) -> None:
        """
        목적: 배분 규칙 후보의 자산 · 시세 id 가 규칙이 요구하는 id 와 같다 (D44 ③).

        Given: HAA · 로테이션 · EWY
        When:  구성을 만든다
        Then:  자산 id 집합과 시세 id 집합이 각 규칙의 상수와 같다
        """
        expected = {
            se.CANDIDATE_HAA: (set(HAA_ASSET_IDS), set(HAA_SERIES_IDS)),
            se.CANDIDATE_ROTATION: (set(ROTATION_ASSET_IDS), set(ROTATION_SERIES_IDS)),
            se.CANDIDATE_EWY: (set(EWY_ASSET_IDS), set()),
        }
        for candidate, (asset_ids, series_ids) in expected.items():
            # When
            method = se.build_experiment_config(_Q2_SLOTS, candidate, 30, se.VARIANT_SPLICED, _START).methods[1]

            # Then
            assert isinstance(method, AllocatorMethodConfig)
            assert {a.asset_id for a in method.assets} == asset_ids
            assert {s.series_id for s in method.signal_series} == series_ids

    @pytest.mark.parametrize(
        ("variant", "vea", "bil", "pdbc"),
        [
            (se.VARIANT_SPLICED, VEA_SYNTHETIC_DATA_PATH, BIL_SYNTHETIC_DATA_PATH, PDBC_SYNTHETIC_DATA_PATH),
            (se.VARIANT_REAL, VEA_DATA_PATH, BIL_DATA_PATH, PDBC_SYNTHETIC_DATA_PATH),
            (se.VARIANT_GATE_REAL, VEA_DATA_PATH, BIL_DATA_PATH, PDBC_DATA_PATH),
            (se.VARIANT_PURE, EFA_DATA_PATH, SHY_DATA_PATH, DBC_DATA_PATH),
            (se.VARIANT_PAIR_VEA, VEA_DATA_PATH, SHY_DATA_PATH, DBC_DATA_PATH),
            (se.VARIANT_PAIR_BIL, EFA_DATA_PATH, BIL_DATA_PATH, DBC_DATA_PATH),
            (se.VARIANT_PAIR_PDBC, EFA_DATA_PATH, SHY_DATA_PATH, PDBC_DATA_PATH),
        ],
    )
    def test_haa_variant_data_paths(self, variant: str, vea: Path, bil: Path, pdbc: Path) -> None:
        """
        목적: HAA 의 대용 3쌍(VEA · BIL · PDBC)이 판마다 정한 파일을 가리킨다 (D46 · D48 ② ③).

        Given: HAA 와 판 하나
        When:  구성을 만든다
        Then:  vea · bil · pdbc 의 신호 · 매매 경로가 표와 같다
        """
        # When
        method = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 30, variant, _START).methods[1]

        # Then
        assert isinstance(method, AllocatorMethodConfig)
        paths = {a.asset_id: (a.signal_data_path, a.trade_data_path) for a in method.assets}
        assert paths["vea"] == (vea, vea)
        assert paths["bil"] == (bil, bil)
        assert paths["pdbc"] == (pdbc, pdbc)

    @pytest.mark.parametrize(
        ("variant", "vxus"),
        [
            (se.VARIANT_SPLICED, VXUS_SYNTHETIC_DATA_PATH),
            (se.VARIANT_REAL, VXUS_DATA_PATH),
            (se.VARIANT_PURE, VXUS_PROXY_DATA_PATH),
        ],
    )
    def test_rotation_variant_data_paths(self, variant: str, vxus: Path) -> None:
        """
        목적: 로테이션의 VXUS 가 판마다 정한 파일을 가리킨다 (D39 · D48 ②).

        Given: 로테이션과 판 하나
        When:  구성을 만든다
        Then:  vxus 경로가 표와 같다
        """
        # When
        method = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_ROTATION, 30, variant, _START).methods[1]

        # Then
        assert isinstance(method, AllocatorMethodConfig)
        paths = {a.asset_id: a.trade_data_path for a in method.assets}
        assert paths["vxus"] == vxus

    @pytest.mark.parametrize(("candidate", "asset_id"), [(se.CANDIDATE_BASELINE, "shy"), (se.CANDIDATE_GOLD, "gld")])
    def test_hold_candidates_are_single_buy_and_hold_slot(self, candidate: str, asset_id: str) -> None:
        """
        목적: 기준선(SHY) · 금 확대는 그 자산 하나를 매매법 자본의 100% 로 보유만 한다 (D4 · 7.1 · 7.2).

        Given: 기준선 · 금 확대
        When:  구성을 만든다
        Then:  후보 매매법 슬롯이 (자산, 1.0, buy_and_hold) 하나 — 전략이 빠지면 기본값(버퍼존)으로 기준선이 추세추종이 된다
        """
        # When
        method = se.build_experiment_config(_Q2_SLOTS, candidate, 25, se.VARIANT_SPLICED, _START).methods[1]

        # Then
        assert isinstance(method, SlotMethodConfig)
        assert [(s.asset_id, s.target_weight, s.strategy_id) for s in method.asset_slots] == [
            (asset_id, 1.0, "buy_and_hold")
        ]

    def test_shared_assets_use_q2_2xs_paths(self) -> None:
        """
        목적: Q-2-2XS 와 같은 종목(GLD · TLT)은 같은 자산 id · 같은 파일이라 상계된다 (D17).

        Given: 금 확대와 HAA
        When:  구성을 만든다
        Then:  gld · tlt 의 매매 경로가 Q-2-2XS 슬롯의 것과 같다
        """
        # Given
        q2_paths = {slot.asset_id: slot.trade_data_path for slot in _Q2_SLOTS}

        # When
        gold = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_GOLD, 30, se.VARIANT_SPLICED, _START).methods[1]
        haa = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 30, se.VARIANT_SPLICED, _START).methods[1]

        # Then
        assert isinstance(gold, SlotMethodConfig)
        assert isinstance(haa, AllocatorMethodConfig)
        assert gold.asset_slots[0].asset_id == "gld"
        assert gold.asset_slots[0].trade_data_path == q2_paths["gld"] == GLD_DATA_PATH
        assert {a.asset_id: a.trade_data_path for a in haa.assets}["tlt"] == q2_paths["tlt"] == TLT_DATA_PATH

    def test_every_valid_case_passes_config_validation(self) -> None:
        """
        목적: 실행 목록의 모든 구성이 엔진의 설정 검증을 통과한다.

        Given: 실행 목록 149개
        When:  구성을 만들어 validate_portfolio_config 를 부른다
        Then:  예외 없음 (파일은 읽지 않는다)
        """
        for case in se.build_grid_cases():
            # When / Then
            validate_portfolio_config(
                se.build_experiment_config(_Q2_SLOTS, case.candidate, case.w_pct, case.variant, case.start_date)
            )

    def test_names_and_min_start_date(self) -> None:
        """
        목적: 실험 이름과 시작일 하한 칸 — 등록 이름은 portfolio_q2_2xs_{후보}{w} 이고 대용 판은 접미사가 붙는다 (D48 ⑨).

        Given: HAA w=30 의 이어 붙인 판 · 순수 대용판, Q-2-2XS 단독
        When:  구성을 만든다
        Then:  이름 · 결과 폴더 · min_start_date
        """
        # When
        spliced = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 30, se.VARIANT_SPLICED, _START)
        pure = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 30, se.VARIANT_PURE, _START)
        alone = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_Q2_2XS, 0, se.VARIANT_SPLICED, _START)

        # Then
        assert spliced.experiment_name == "portfolio_q2_2xs_haa30"
        assert spliced.result_dir.name == "portfolio_q2_2xs_haa30"
        assert pure.experiment_name == "portfolio_q2_2xs_haa30_pure"
        assert spliced.min_start_date == _START
        assert alone.asset_slots == _Q2_SLOTS
        assert alone.methods == ()

    @pytest.mark.parametrize(
        ("candidate", "w_pct", "variant"),
        [
            (se.CANDIDATE_GOLD, 30, se.VARIANT_PURE),
            (se.CANDIDATE_ROTATION, 30, se.VARIANT_GATE_REAL),
            (se.CANDIDATE_ROTATION, 30, se.VARIANT_PAIR_VEA),
            (se.CANDIDATE_HAA, 12, se.VARIANT_SPLICED),
            (se.CANDIDATE_Q2_2XS, 30, se.VARIANT_SPLICED),
            ("unknown", 30, se.VARIANT_SPLICED),
            (se.CANDIDATE_HAA, 30, "unknown"),
        ],
    )
    def test_invalid_combination_raises(self, candidate: str, w_pct: int, variant: str) -> None:
        """
        목적: 정하지 않은 후보 · 비중 · 판 조합은 즉시 ValueError (대용이 없는 후보에 대용 판 등).

        Given: 잘못된 조합
        When:  구성을 만든다
        Then:  ValueError
        """
        with pytest.raises(ValueError):
            se.build_experiment_config(_Q2_SLOTS, candidate, w_pct, variant, _START)


# 대체 판 후보 — 조합 실험(D55)에 쓰는 것만 대체 판을 받는다 (D69 ③)
_ALT_CANDIDATES: list[tuple[str, int]] = [
    (se.CANDIDATE_Q2_2XS, 0),
    (se.CANDIDATE_BASELINE, 30),
    (se.CANDIDATE_HAA, 30),
    (se.CANDIDATE_ROTATION, 30),
]
# 2000-08-30 전부터 실물이 있어 대체 판에서도 그대로 쓰는 시세
_KEPT_REAL_PATHS = {SPY_DATA_PATH, QQQ_DATA_PATH, IWM_DATA_PATH}


class TestAltVariant:
    """대체 판 — 실물판 설정의 경로를 「실물 파일 → 대체 파일」 표 하나로 바꾼다 (D57 · D59 · D69 ②)."""

    def test_path_map_is_the_planned_table(self) -> None:
        """
        목적: 대체 판 경로 표가 설계서 8.4 의 13종이다 — 원자재는 실물판의 DBC → PDBC 이어 붙인 판을 GSCI → DBC 로 바꾼다.

        Given: 경로 표
        When:  그대로 읽는다
        Then:  13줄이 계획한 짝과 같다
        """
        # Then
        assert se.ALT_PATH_MAP == {
            SSO_DATA_PATH: SSO_PROXY_DATA_PATH,
            QLD_DATA_PATH: QLD_PROXY_DATA_PATH,
            GLD_DATA_PATH: GOLD_FUTURES_DATA_PATH,
            TLT_DATA_PATH: VUSTX_DATA_PATH,
            VEA_DATA_PATH: VTMGX_DATA_PATH,
            VWO_DATA_PATH: VEIEX_DATA_PATH,
            VNQ_DATA_PATH: VGSIX_DATA_PATH,
            PDBC_SYNTHETIC_DATA_PATH: DBC_SYNTHETIC_DATA_PATH,
            IEF_DATA_PATH: VFITX_DATA_PATH,
            BIL_DATA_PATH: BIL_PROXY_DATA_PATH,
            TIP_DATA_PATH: VIPSX_DATA_PATH,
            VXUS_DATA_PATH: VGTSX_DATA_PATH,
            SHY_DATA_PATH: VFISX_DATA_PATH,
        }

    def test_alt_configs_use_only_alt_files_and_kept_real(self) -> None:
        """
        목적: 대체 판 설정에는 대체 파일과 SPY · QQQ · IWM 만 남는다 — 하나라도 실물이 남으면 「대체 판」이 실물 일부로 돈다.

        Given: Q-2-2XS 단독 · 기준선 · HAA · 로테이션
        When:  대체 판 설정을 만든다
        Then:  모든 경로가 (표의 대체 파일 ∪ SPY · QQQ · IWM) 안에 있다
        """
        # Given
        allowed = set(se.ALT_PATH_MAP.values()) | _KEPT_REAL_PATHS

        for candidate, w in _ALT_CANDIDATES:
            # When
            config = se.build_experiment_config(_Q2_SLOTS, candidate, w, se.VARIANT_ALT, _START)

            # Then
            assert _config_paths(config) <= allowed, candidate

    def test_every_table_row_is_used(self) -> None:
        """
        목적: 표의 13줄이 모두 쓰인다 — 실물판 네 설정이 쓰는 파일이 표의 왼쪽과 SPY · QQQ · IWM 로 정확히 덮인다.

        Given: Q-2-2XS 단독 · 기준선 · HAA · 로테이션의 실물판 · 대체 판 설정
        When:  경로를 모은다
        Then:  실물판 합집합 = 표 왼쪽 ∪ 남기는 실물, 대체 판 합집합 = 표 오른쪽 ∪ 남기는 실물
        """
        # When
        real_paths: set[Path] = set()
        alt_paths: set[Path] = set()
        for candidate, w in _ALT_CANDIDATES:
            real_paths |= _config_paths(se.build_experiment_config(_Q2_SLOTS, candidate, w, se.VARIANT_REAL, _START))
            alt_paths |= _config_paths(se.build_experiment_config(_Q2_SLOTS, candidate, w, se.VARIANT_ALT, _START))

        # Then
        assert real_paths == set(se.ALT_PATH_MAP) | _KEPT_REAL_PATHS
        assert alt_paths == set(se.ALT_PATH_MAP.values()) | _KEPT_REAL_PATHS

    def test_q2_2xs_slots_keep_index_signals(self) -> None:
        """
        목적: Q-2-2XS 의 SSO · QLD 는 매매만 2배 합성으로 바뀌고 신호는 SPY · QQQ 실물 그대로다 (D57 ①).

        Given: Q-2-2XS 단독 대체 판
        When:  구성을 만든다
        Then:  (신호, 매매) — sso (SPY, SSO 합성) · qld (QQQ, QLD 합성) · gld (금 선물 둘) · tlt (VUSTX 둘)
        """
        # When
        config = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_Q2_2XS, 0, se.VARIANT_ALT, _START)

        # Then
        assert {s.asset_id: (s.signal_data_path, s.trade_data_path) for s in config.asset_slots} == {
            "sso": (SPY_DATA_PATH, SSO_PROXY_DATA_PATH),
            "qld": (QQQ_DATA_PATH, QLD_PROXY_DATA_PATH),
            "gld": (GOLD_FUTURES_DATA_PATH, GOLD_FUTURES_DATA_PATH),
            "tlt": (VUSTX_DATA_PATH, VUSTX_DATA_PATH),
        }

    def test_shared_tlt_is_same_alt_file(self) -> None:
        """
        목적: Q-2-2XS 와 HAA 의 tlt 가 대체 판에서도 같은 파일(VUSTX)이다 — 같은 자산 id 는 같은 매매 데이터여야 상계된다 (D17).

        Given: HAA 대체 판
        When:  구성을 만든다
        Then:  Q-2-2XS 슬롯 tlt 와 HAA 자산 tlt 의 매매 경로가 둘 다 VUSTX, 설정 검증 통과
        """
        # When
        config = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 30, se.VARIANT_ALT, _START)

        # Then
        q2, haa = config.methods
        assert isinstance(q2, SlotMethodConfig)
        assert isinstance(haa, AllocatorMethodConfig)
        assert {s.asset_id: s.trade_data_path for s in q2.asset_slots}["tlt"] == VUSTX_DATA_PATH
        assert {a.asset_id: a.trade_data_path for a in haa.assets}["tlt"] == VUSTX_DATA_PATH
        validate_portfolio_config(config)

    def test_alt_names_and_validation(self) -> None:
        """
        목적: 대체 판 이름은 접미사 _alt 이고 네 후보 모두 엔진 설정 검증을 통과한다.

        Given: 네 후보의 대체 판
        When:  구성을 만든다
        Then:  이름이 _alt 로 끝나고 검증 예외 없음
        """
        for candidate, w in _ALT_CANDIDATES:
            # When
            config = se.build_experiment_config(_Q2_SLOTS, candidate, w, se.VARIANT_ALT, _START)

            # Then
            assert config.experiment_name.endswith("_alt")
            validate_portfolio_config(config)

    def test_unmapped_path_raises(self) -> None:
        """
        목적: 경로 표에 없고 그대로 써도 되는 실물(SPY · QQQ · IWM)도 아닌 파일이 남으면 ValueError — 조용히 실물로 돌지 않는다.

        Given: TLT 슬롯을 표에 없는 EFA 파일로 바꾼 Q-2-2XS 슬롯
        When:  Q-2-2XS 단독 대체 판 구성을 만든다
        Then:  ValueError
        """
        # Given
        slots = tuple(
            dataclasses.replace(s, signal_data_path=EFA_DATA_PATH, trade_data_path=EFA_DATA_PATH)
            if s.asset_id == "tlt"
            else s
            for s in _Q2_SLOTS
        )

        # When / Then
        with pytest.raises(ValueError, match="대체 판 경로 표"):
            se.build_experiment_config(slots, se.CANDIDATE_Q2_2XS, 0, se.VARIANT_ALT, _START)

    @pytest.mark.parametrize("candidate", [se.CANDIDATE_GOLD, se.CANDIDATE_EWY])
    def test_alt_is_not_for_other_candidates(self, candidate: str) -> None:
        """
        목적: 금 확대 · EWY 는 대체 판을 받지 않는다 (D69 ③).

        Given: 금 확대 · EWY
        When:  대체 판 구성을 만든다
        Then:  ValueError
        """
        with pytest.raises(ValueError):
            se.build_experiment_config(_Q2_SLOTS, candidate, 30, se.VARIANT_ALT, _START)


_COMBO_VARIANTS = (se.VARIANT_SPLICED, se.VARIANT_REAL, se.VARIANT_ALT)


class TestBuildComboConfig:
    """build_combo_config — Q-2-2XS + HAA + 로테이션 세 매매법 구성 (D55 · D56 · D69 ④)."""

    @pytest.mark.parametrize("variant", _COMBO_VARIANTS)
    def test_shares_and_method_order(self, variant: str) -> None:
        """
        목적: 16칸 모두 매매법이 Q-2-2XS → HAA → 로테이션 순서이고 몫이 (100 − h − r)% · h% · r% 로 합 1 이다.

        Given: 판 하나
        When:  h · r 4단계씩 구성을 만든다
        Then:  매매법 id 순서와 몫
        """
        for h in se.COMBO_PCTS:
            for r in se.COMBO_PCTS:
                # When
                config = se.build_combo_config(_Q2_SLOTS, h, r, variant, _START)

                # Then
                assert [m.method_id for m in config.methods] == [
                    se.CANDIDATE_Q2_2XS,
                    se.CANDIDATE_HAA,
                    se.CANDIDATE_ROTATION,
                ]
                shares = [m.target_weight for m in config.methods]
                assert shares == pytest.approx([(100 - h - r) / 100, h / 100, r / 100], abs=1e-12)
                assert sum(shares) == pytest.approx(1.0, abs=1e-12)

    @pytest.mark.parametrize("variant", _COMBO_VARIANTS)
    def test_methods_match_single_candidate_configs(self, variant: str) -> None:
        """
        목적: 조합의 각 매매법은 같은 판의 단독 설정의 매매법과 몫 말고 같다 — 조합과 단독이 같은 정의를 쓴다.

        Given: HAA 10 + 로테이션 15 조합과, 같은 판의 HAA 단독 · 로테이션 단독 · Q-2-2XS 단독
        When:  매매법을 비교한다
        Then:  몫을 맞추면 같다, Q-2-2XS 슬롯은 같은 판의 Q-2-2XS 단독 슬롯과 같다
        """
        # Given
        combo = se.build_combo_config(_Q2_SLOTS, 10, 15, variant, _START)
        haa = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_HAA, 25, variant, _START).methods[1]
        rotation = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_ROTATION, 25, variant, _START).methods[1]
        alone = se.build_experiment_config(_Q2_SLOTS, se.CANDIDATE_Q2_2XS, 0, variant, _START)

        # When
        q2, combo_haa, combo_rotation = combo.methods

        # Then
        assert isinstance(q2, SlotMethodConfig)
        assert q2.asset_slots == alone.asset_slots
        assert dataclasses.replace(combo_haa, target_weight=haa.target_weight) == haa
        assert dataclasses.replace(combo_rotation, target_weight=rotation.target_weight) == rotation

    def test_alt_combo_uses_only_alt_files(self) -> None:
        """
        목적: 대체 판 조합에도 대체 파일과 SPY · QQQ · IWM 만 남는다.

        Given: 대체 판 조합
        When:  경로를 모은다
        Then:  허용 집합 안
        """
        # When
        config = se.build_combo_config(_Q2_SLOTS, 15, 15, se.VARIANT_ALT, _START)

        # Then
        assert _config_paths(config) <= set(se.ALT_PATH_MAP.values()) | _KEPT_REAL_PATHS

    def test_every_cell_passes_config_validation(self) -> None:
        """
        목적: 세 판 · 16칸 모든 조합이 엔진 설정 검증(몫 합 · 같은 자산 id 같은 경로)을 통과한다.

        Given: 판 셋 × 16칸
        When:  validate_portfolio_config 를 부른다
        Then:  예외 없음 (파일은 읽지 않는다)
        """
        for variant in _COMBO_VARIANTS:
            for h in se.COMBO_PCTS:
                for r in se.COMBO_PCTS:
                    # When / Then
                    validate_portfolio_config(se.build_combo_config(_Q2_SLOTS, h, r, variant, _START))

    def test_names_and_min_start_date(self) -> None:
        """
        목적: 조합 이름은 portfolio_q2_2xs_haa{h}_rotation{r} 이고 이어 붙인 판이 아니면 판 접미사가 붙는다.

        Given: HAA 15 + 로테이션 20 의 이어 붙인 판 · 완전 실물판 · 대체 판
        When:  구성을 만든다
        Then:  이름 · 결과 폴더 · 표시 이름 · min_start_date
        """
        # When
        spliced = se.build_combo_config(_Q2_SLOTS, 15, 20, se.VARIANT_SPLICED, _START)
        real = se.build_combo_config(_Q2_SLOTS, 15, 20, se.VARIANT_REAL, _START)
        alt = se.build_combo_config(_Q2_SLOTS, 15, 20, se.VARIANT_ALT, _START)

        # Then
        assert spliced.experiment_name == "portfolio_q2_2xs_haa15_rotation20"
        assert spliced.result_dir.name == "portfolio_q2_2xs_haa15_rotation20"
        assert real.experiment_name == "portfolio_q2_2xs_haa15_rotation20_real"
        assert alt.experiment_name == "portfolio_q2_2xs_haa15_rotation20_alt"
        assert spliced.display_name == "Q-2-2XS 65% + HAA 15% + 미국 약세 로테이션 20%"
        assert spliced.min_start_date == _START

    @pytest.mark.parametrize(
        ("haa_pct", "rotation_pct", "variant"),
        [
            (25, 10, se.VARIANT_SPLICED),
            (10, 0, se.VARIANT_SPLICED),
            (12, 10, se.VARIANT_SPLICED),
            (10, 10, se.VARIANT_PURE),
            (10, 10, se.VARIANT_GATE_REAL),
            (10, 10, "unknown"),
        ],
    )
    def test_invalid_combination_raises(self, haa_pct: int, rotation_pct: int, variant: str) -> None:
        """
        목적: 격자 밖 비중 · 정하지 않은 판은 즉시 ValueError (D56 ① · D69 ④).

        Given: 잘못된 비중 또는 판
        When:  조합 구성을 만든다
        Then:  ValueError
        """
        with pytest.raises(ValueError):
            se.build_combo_config(_Q2_SLOTS, haa_pct, rotation_pct, variant, _START)


# ============================================================================
# 실행 목록
# ============================================================================


class TestGridCases:
    """build_grid_cases 의 실행 수 · 시작일 · 비교 상대 계약."""

    def test_case_counts(self) -> None:
        """
        목적: 실행 목록이 계획한 149회이고 묶음별 수가 맞다.

        Given: 실행 목록
        When:  묶음별로 센다
        Then:  주 비교 36 · 보조 36 · 로테이션 관문 7 · HAA 관문 21 · VEA 쌍 21 · BIL 쌍 21 · PDBC 쌍 7
        """
        # When
        cases = se.build_grid_cases()
        counts: dict[str, int] = {}
        for case in cases:
            counts[case.group] = counts.get(case.group, 0) + 1

        # Then
        assert len(cases) == 149
        assert counts == {
            se.GROUP_MAIN: 36,
            se.GROUP_SUB: 36,
            se.GROUP_GATE_ROTATION: 7,
            se.GROUP_GATE_HAA: 21,
            se.GROUP_PAIR_VEA: 21,
            se.GROUP_PAIR_BIL: 21,
            se.GROUP_PAIR_PDBC: 7,
        }

    def test_cases_are_unique(self) -> None:
        """
        목적: 같은 구성(후보 · 판 · 시작일 · w)을 두 번 돌리지 않고, 결과를 찾는 키(묶음 · 후보 · 판 · w)도 겹치지 않는다.

        Given: 실행 목록
        When:  두 키로 각각 센다
        Then:  둘 다 중복 없음 — 찾는 키가 겹치면 판정이 다른 실행의 결과를 조용히 읽는다
        """
        # When
        cases = se.build_grid_cases()
        run_keys = [(c.candidate, c.variant, c.start_date, c.w_pct) for c in cases]
        lookup_keys = [(c.group, c.candidate, c.variant, c.w_pct) for c in cases]

        # Then
        assert len(run_keys) == len(set(run_keys))
        assert len(lookup_keys) == len(set(lookup_keys))

    def test_group_start_dates(self) -> None:
        """
        목적: 묶음마다 모든 구성이 같은 시작일이다 (D45 · D48 ② ③).

        Given: 실행 목록
        When:  묶음별 시작일 집합을 모은다
        Then:  묶음마다 하나이고 정한 날짜다
        """
        # When
        starts: dict[str, set[date]] = {}
        for case in se.build_grid_cases():
            starts.setdefault(case.group, set()).add(case.start_date)

        # Then
        assert starts == {
            se.GROUP_MAIN: {date(2007, 6, 22)},
            se.GROUP_SUB: {date(2011, 11, 10)},
            se.GROUP_GATE_ROTATION: {date(2011, 11, 10)},
            se.GROUP_GATE_HAA: {date(2015, 11, 9)},
            se.GROUP_PAIR_VEA: {date(2008, 7, 25)},
            se.GROUP_PAIR_BIL: {date(2008, 5, 29)},
            se.GROUP_PAIR_PDBC: {date(2015, 11, 9)},
        }

    def test_every_candidate_run_has_same_start_baseline(self) -> None:
        """
        목적: 후보 실행마다 같은 시작일 · 같은 w 의 기준선 실행이 있다 (D4 · D24 의 비교 상대).

        Given: 실행 목록
        When:  기준선 (시작일, w) 집합을 만든다
        Then:  모든 후보 실행의 (시작일, w) 가 그 안에 있다
        """
        # Given
        cases = se.build_grid_cases()
        baselines = {(c.start_date, c.w_pct) for c in cases if c.candidate == se.CANDIDATE_BASELINE}

        # When / Then
        for case in cases:
            if case.candidate in se.SUPPLEMENT_CANDIDATES:
                assert (case.start_date, case.w_pct) in baselines, case


# ============================================================================
# 지표
# ============================================================================


class TestPhaseMetrics:
    """phase_metrics 의 국면 수익률 · 구간 MDD · 기간 밖 처리 계약 (D48 ⑦)."""

    _DATES = [date(2020, 1, d) for d in (2, 3, 6, 7, 8, 9)]
    _EQUITY = [100.0, 110.0, 99.0, 121.0, 108.9, 130.0]

    def test_return_uses_previous_day_as_base(self) -> None:
        """
        목적: 수익률 = 구간 마지막 거래일 자본 ÷ 구간 첫 거래일 전날 자본 − 1.

        Given: 자본 [100, 110, 99, 121, 108.9, 130], 구간 01-06 – 01-08
        When:  국면 지표를 잰다
        Then:  수익률 108.9 ÷ 110 − 1 = −1%
        """
        # Given
        window = se.PhaseWindow("t", "시험", date(2020, 1, 6), date(2020, 1, 8))

        # When
        ret, _ = se.phase_metrics(self._DATES, self._EQUITY, window)

        # Then
        assert ret == pytest.approx(-1.0, abs=1e-9)

    def test_mdd_starts_from_previous_day_peak(self) -> None:
        """
        목적: 구간 MDD 는 전날 자본을 첫 고점으로 둔다 — 구간 첫날의 하락도 낙폭에 든다.

        Given: 구간 01-06 – 01-08 (전날 110 → 99 → 121 → 108.9)
        When:  국면 지표를 잰다
        Then:  MDD = min(99/110 − 1, 108.9/121 − 1) = −10%
        """
        # Given
        window = se.PhaseWindow("t", "시험", date(2020, 1, 6), date(2020, 1, 8))

        # When
        _, mdd = se.phase_metrics(self._DATES, self._EQUITY, window)

        # Then
        assert mdd == pytest.approx(-10.0, abs=1e-9)

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (date(2020, 1, 2), date(2020, 1, 6)),  # 첫 거래일이 실행 첫날 — 전날이 없다
            (date(2019, 12, 1), date(2020, 1, 6)),  # 실행 시작보다 앞에서 시작
            (date(2020, 1, 7), date(2020, 1, 31)),  # 실행 끝보다 뒤에서 끝남
            (date(2021, 1, 1), date(2021, 12, 31)),  # 실행 기간 밖
        ],
    )
    def test_window_not_fully_inside_is_empty(self, start: date, end: date) -> None:
        """
        목적: 구간이 실행 기간 안에 다 들지 않으면 빈 값 — 부분 구간은 길이가 달라 비교할 수 없다.

        Given: 실행 기간을 벗어나는 구간
        When:  국면 지표를 잰다
        Then:  (None, None)
        """
        # Given
        window = se.PhaseWindow("t", "시험", start, end)

        # When / Then
        assert se.phase_metrics(self._DATES, self._EQUITY, window) == (None, None)

    def test_phase_windows_do_not_overlap_within_same_phase(self) -> None:
        """
        목적: 금융위기와 미국 약세 ① 은 하루도 겹치지 않는다 (D48 ⑦).

        Given: 국면 구간 상수
        When:  두 구간을 찾는다
        Then:  미국 약세 ① 시작이 금융위기 끝 다음 날
        """
        # Given
        windows = {w.phase_id: w for w in se.PHASE_WINDOWS}

        # Then
        assert windows["us_weak_1"].start == windows["financial_crisis"].end + timedelta(days=1)


class TestEarlyPhaseWindows:
    """대체 판에만 있는 2001 – 2007 국면 두 구간 (D68)."""

    def test_dates(self) -> None:
        """
        목적: 닷컴 하락 후반 2001-09-04 – 2002-10-09, 미국 약세 2002 – 07 2002-10-10 – 2007-10-08 (D68).

        Given: 국면 구간 상수
        When:  날짜를 읽는다
        Then:  정한 날짜와 같고, 금융위기 · 미국 약세 ① 과 이어지며 겹치지 않는다
        """
        # Given
        early = {w.phase_id: w for w in se.EARLY_PHASE_WINDOWS}
        later = {w.phase_id: w for w in se.PHASE_WINDOWS}

        # Then
        assert [(w.start, w.end) for w in se.EARLY_PHASE_WINDOWS] == [
            (date(2001, 9, 4), date(2002, 10, 9)),
            (date(2002, 10, 10), date(2007, 10, 8)),
        ]
        dotcom, us_weak = se.EARLY_PHASE_WINDOWS
        assert us_weak.start == dotcom.end + timedelta(days=1)
        assert later["financial_crisis"].start == us_weak.end + timedelta(days=1)
        assert set(early).isdisjoint(later)
        assert se.ALL_PHASE_WINDOWS == (*se.EARLY_PHASE_WINDOWS, *se.PHASE_WINDOWS)

    def test_dotcom_late_has_value_when_run_starts_on_previous_trading_day(self) -> None:
        """
        목적: 대체 판 조합이 2001-08-31 에 시작하면 닷컴 하락 후반 구간의 기준(전날 자본)이 실행 첫날이라 값이 나온다.

        Given: 2001-08-31 · 2001-09-04 부터 이어지는 거래일(09-03 노동절 없음)과 자본
        When:  닷컴 하락 후반 국면 지표를 잰다
        Then:  수익률 = 2002-10-09 자본 ÷ 2001-08-31 자본 − 1
        """
        # Given
        dates = [date(2001, 8, 31), *_weekdays(date(2001, 9, 4), date(2002, 10, 31))]
        equity = [100.0] + [100.0 + i for i in range(1, len(dates))]
        dotcom = se.EARLY_PHASE_WINDOWS[0]
        last = max(i for i, d in enumerate(dates) if d <= dotcom.end)

        # When
        ret, mdd = se.phase_metrics(dates, equity, dotcom)

        # Then
        assert ret == pytest.approx((equity[last] / 100.0 - 1.0) * 100.0, abs=1e-9)
        assert mdd == pytest.approx(0.0, abs=1e-12)

    def test_dotcom_late_is_empty_when_run_starts_inside(self) -> None:
        """
        목적: 실행이 구간 첫날(2001-09-04)에 시작하면 전날 자본이 없어 빈 값 — D68 이 시작을 실행 첫날 다음 날로 둔 이유.

        Given: 2001-09-04 부터의 거래일
        When:  닷컴 하락 후반 국면 지표를 잰다
        Then:  (None, None)
        """
        # Given
        dates = _weekdays(date(2001, 9, 4), date(2002, 10, 31))
        equity = [100.0] * len(dates)

        # When / Then
        assert se.phase_metrics(dates, equity, se.EARLY_PHASE_WINDOWS[0]) == (None, None)


class TestAnnualTurnover:
    """annual_turnover 계약 — 매수 · 매도 금액을 모두 센다 (D48 ⑪)."""

    def test_counts_buys_and_sells(self) -> None:
        """
        목적: 체결 주수 × 체결가를 매수 · 매도 모두 더해 평균 자본과 연수로 나눈다.

        Given: 1년(365.25일) 실행, 평균 자본 1,000, 매수 10주 × 20 + 매도 5주 × 40
        When:  연 회전율을 잰다
        Then:  (200 + 200) ÷ 1,000 ÷ 1 = 0.4
        """
        # Given
        start = date(2020, 1, 1)
        end = start + timedelta(days=365)
        state_log = pd.DataFrame(
            {
                COL_DATE: [start, start + timedelta(days=100), end],
                "a.x_exec_shares": [10, 0, 0],
                "a.x_exec_price": [20.0, 0.0, 0.0],
                "b.y_exec_shares": [0, 5, 0],
                "b.y_exec_price": [0.0, 40.0, 0.0],
            }
        )
        equity = pd.DataFrame({COL_DATE: [start, start + timedelta(days=100), end], "equity": [900.0, 1000.0, 1100.0]})

        # When
        turnover = se.annual_turnover(state_log, equity)

        # Then
        assert turnover == pytest.approx(400.0 / 1000.0 / (365 / 365.25), abs=1e-9)


class TestSummarizeRun:
    """summarize_run 이 엔진 요약의 반올림 전 값과 시작 · 끝날 · 매도 거래 수를 옮긴다."""

    def test_copies_unrounded_metrics(self) -> None:
        """
        목적: CAGR · MDD · Calmar 는 반올림 전 값 그대로, 매도 거래 수는 trades 행 수.

        Given: 가짜 결과 (Calmar 0.123456789, 매도 2건)
        When:  요약한다
        Then:  값 그대로
        """
        # Given
        days = _weekdays(date(2020, 1, 1), date(2020, 3, 31))
        equity = pd.DataFrame({COL_DATE: days, "equity": [100.0 + i for i in range(len(days))]})
        state_log = pd.DataFrame({COL_DATE: days, "is_month_end": [False] * len(days)})
        result = PortfolioResult(
            experiment_name="t",
            display_name="t",
            equity_df=equity,
            trades_df=pd.DataFrame({"pnl": [1.0, 2.0]}),
            summary={"cagr": 12.3456789, "mdd": -7.654321, "calmar": 0.123456789},
            config=PortfolioConfig("t", "t", 100.0, Path("unused")),
            state_log_df=state_log,
        )

        # When
        summary = se.summarize_run(result)

        # Then
        assert summary.calmar == 0.123456789
        assert summary.cagr == 12.3456789
        assert summary.mdd == -7.654321
        assert summary.sell_trades == 2
        assert summary.start_date == days[0]
        assert summary.end_date == days[-1]
        assert set(summary.phase_returns) == {w.phase_id for w in se.ALL_PHASE_WINDOWS}
        assert summary.trading_days == len(days)

    def test_datetime_dates_become_dates(self) -> None:
        """
        목적: 날짜 열이 datetime 이어도 date 로 바꿔 읽는다 — datetime 은 date 의 하위 클래스라 그대로 두면 date 와 비교가 틀어진다.

        Given: Date 열이 파이썬 datetime 객체(object 열)인 가짜 결과
        When:  요약한다
        Then:  시작 · 끝날이 date 이고 국면 계산이 예외 없이 끝난다
        """
        # Given
        days = pd.Series(
            [datetime(d.year, d.month, d.day) for d in _weekdays(date(2020, 1, 1), date(2020, 3, 31))], dtype=object
        )
        result = PortfolioResult(
            experiment_name="t",
            display_name="t",
            equity_df=pd.DataFrame({COL_DATE: days, "equity": [100.0] * len(days)}),
            trades_df=pd.DataFrame(),
            summary={"cagr": 0.0, "mdd": 0.0, "calmar": 0.0},
            config=PortfolioConfig("t", "t", 100.0, Path("unused")),
            state_log_df=pd.DataFrame({COL_DATE: days}),
        )

        # When
        summary = se.summarize_run(result)

        # Then
        assert type(summary.start_date) is date
        assert summary.start_date == date(2020, 1, 1)
        assert type(summary.end_date) is date


# ============================================================================
# 신호 일치율
# ============================================================================


class TestDecisionAgreement:
    """신호 일치율 — 월말 판단 직후 목표 비중만 비교한다 (D48 ①)."""

    @staticmethod
    def _state_log(weights: list[float]) -> pd.DataFrame:
        # 1월 말(01-31) · 2월 말(02-28) 이 판단일, 다음 거래일(02-03 · 03-02)이 판단 직후 행
        days = [date(2020, 1, 30), date(2020, 1, 31), date(2020, 2, 3), date(2020, 2, 4), date(2020, 2, 28)]
        days += [date(2020, 3, 2), date(2020, 3, 3)]
        return pd.DataFrame(
            {
                COL_DATE: days,
                "is_month_end": [False, True, False, False, True, False, False],
                "haa.spy_target_weight": weights,
                "haa.bil_target_weight": [1.0 - w for w in weights],
                "q2_2xs.sso_shares": [0] * len(days),
            }
        )

    def test_extract_keeps_only_rows_after_month_end(self) -> None:
        """
        목적: 판단 비중표는 월 마지막 거래일 다음 거래일 행만 담는다.

        Given: 판단일 둘이 있는 상태 로그
        When:  판단 비중표를 뽑는다
        Then:  02-03 · 03-02 두 행, 열은 자산 id (spy · bil)
        """
        # Given
        state_log = self._state_log([0.0, 0.0, 0.25, 0.25, 0.25, 0.5, 0.5])

        # When
        targets = se.extract_decision_targets(state_log, "haa")

        # Then
        assert list(targets.index) == [date(2020, 2, 3), date(2020, 3, 2)]
        assert set(targets.columns) == {"spy", "bil"}
        assert targets["spy"].tolist() == [0.25, 0.5]

    def test_mid_month_differences_are_not_counted(self) -> None:
        """
        목적: 월중 행이 달라도 판단 직후 행이 같으면 일치율 100% — 날마다 세면 부풀거나 줄어든다.

        Given: 판단 직후 행은 같고 월중 행(02-04 · 03-03)만 다른 두 상태 로그
        When:  신호 일치율을 잰다
        Then:  1.0, 비교 달 2
        """
        # Given
        a = se.extract_decision_targets(self._state_log([0.0, 0.0, 0.25, 0.25, 0.25, 0.5, 0.5]), "haa")
        b = se.extract_decision_targets(self._state_log([0.0, 0.0, 0.25, 0.75, 0.25, 0.5, 1.0]), "haa")

        # When
        rate, months = se.decision_agreement(a, b)

        # Then
        assert rate == pytest.approx(1.0, abs=1e-12)
        assert months == 2

    def test_rate_counts_months_with_every_weight_equal(self) -> None:
        """
        목적: 한 달의 모든 자산 비중이 같아야 일치로 센다.

        Given: 4달 중 1달만 비중이 다른 두 판단 비중표
        When:  신호 일치율을 잰다
        Then:  0.75, 비교 달 4
        """
        # Given
        dates = [date(2020, m, 1) for m in range(1, 5)]
        a = _targets(dates, [{"vxus": 1.0, "shy": 0.0}] * 4)
        b = _targets(dates, [{"vxus": 1.0, "shy": 0.0}] * 3 + [{"vxus": 0.0, "shy": 1.0}])

        # When
        rate, months = se.decision_agreement(a, b)

        # Then
        assert rate == pytest.approx(0.75, abs=1e-12)
        assert months == 4

    def test_different_months_raise(self) -> None:
        """
        목적: 비교하는 두 표의 달이 다르면 ValueError — 같은 시작일 실행끼리만 비교한다.

        Given: 달이 다른 두 표
        When:  신호 일치율을 잰다
        Then:  ValueError
        """
        # Given
        a = _targets([date(2020, 1, 1)], [{"vxus": 1.0}])
        b = _targets([date(2020, 2, 1)], [{"vxus": 1.0}])

        # When / Then
        with pytest.raises(ValueError):
            se.decision_agreement(a, b)


# ============================================================================
# 기준선 대비 우위 · 판정
# ============================================================================


class TestAdvantages:
    """compute_advantages — 같은 시작일 · 같은 w 의 기준선과 비교한다."""

    def test_advantage_is_against_same_start_and_w_baseline(self) -> None:
        """
        목적: 우위 = 후보 Calmar − (같은 시작일 · 같은 w) 기준선 Calmar.

        Given: 주 비교 기준선 0.5, 보조 기준선 0.4, 주 비교 금 0.6, 보조 금 0.35
        When:  우위를 계산한다
        Then:  주 비교 금 +0.1, 보조 금 −0.05
        """
        # Given
        results = _fake_results(
            {
                (se.GROUP_SUB, se.CANDIDATE_BASELINE, se.VARIANT_REAL): 0.4,
                (se.GROUP_MAIN, se.CANDIDATE_GOLD, se.VARIANT_SPLICED): 0.6,
                (se.GROUP_SUB, se.CANDIDATE_GOLD, se.VARIANT_REAL): 0.35,
            }
        )

        # When
        advantages = se.compute_advantages(results)

        # Then
        main_gold = se.GridCase(se.GROUP_MAIN, se.CANDIDATE_GOLD, 30, se.VARIANT_SPLICED, date(2007, 6, 22))
        sub_gold = se.GridCase(se.GROUP_SUB, se.CANDIDATE_GOLD, 30, se.VARIANT_REAL, date(2011, 11, 10))
        assert advantages[main_gold] == pytest.approx(0.1, abs=1e-12)
        assert advantages[sub_gold] == pytest.approx(-0.05, abs=1e-12)

    def test_missing_baseline_raises(self) -> None:
        """
        목적: 같은 시작일 · 같은 w 의 기준선이 없으면 ValueError.

        Given: 기준선 실행을 뺀 결과
        When:  우위를 계산한다
        Then:  ValueError
        """
        # Given
        results = [r for r in _fake_results({}) if r.case.candidate != se.CANDIDATE_BASELINE]

        # When / Then
        with pytest.raises(ValueError):
            se.compute_advantages(results)

    def test_different_actual_period_raises(self) -> None:
        """
        목적: 같은 시작일이어도 후보와 기준선의 실제 기간(거래일 수)이 다르면 ValueError — 다른 기간의 Calmar 를 빼지 않는다.

        Given: 주 비교 금 w=30 실행만 거래일이 하루 적다 (후보 시세 하나의 날짜가 빠진 경우)
        When:  우위를 계산한다
        Then:  ValueError
        """
        # Given
        results = _fake_results({})
        for i, r in enumerate(results):
            if (r.case.group, r.case.candidate, r.case.w_pct) == (se.GROUP_MAIN, se.CANDIDATE_GOLD, 30):
                results[i] = se.GridCaseResult(r.case, _summary(0.5, r.case.start_date, 4799), [], None)

        # When / Then
        with pytest.raises(ValueError, match="실제 기간"):
            se.compute_advantages(results)


class TestJudge:
    """D24 판정 (D47 해석) — 두 기간 모두 기준선보다 높은 w 가 3단계 이상 연달아."""

    def test_three_consecutive_pass(self) -> None:
        """
        목적: 두 기간 모두 높은 w 가 연속 3단계면 통과, 고원 = 그 구간.

        Given: 20 · 25 · 30% 만 두 기간 모두 양의 우위
        When:  판정한다
        Then:  통과, 고원 [(20, 30)]
        """
        # Given
        adv = _advantages([-0.01, -0.01, 0.02, 0.03, 0.01, -0.02, -0.03])

        # When
        judgment = se.judge(adv, adv)

        # Then
        assert judgment.passed
        assert judgment.plateaus == ((20, 30),)

    def test_two_consecutive_fail(self) -> None:
        """
        목적: 연속 2단계는 탈락.

        Given: 20 · 25% 만 양의 우위
        When:  판정한다
        Then:  탈락, 고원 없음
        """
        # Given
        adv = _advantages([-0.01, -0.01, 0.02, 0.03, -0.01, -0.02, -0.03])

        # When
        judgment = se.judge(adv, adv)

        # Then
        assert not judgment.passed
        assert judgment.plateaus == ()

    def test_sub_period_must_support_each_w(self) -> None:
        """
        목적: 주 비교 7단계가 모두 높아도 보조 기간이 받쳐 주는 연속 구간만 고원이다 (D47 예).

        Given: 주 비교 10 – 40% 전부 양, 보조 20 · 25 · 30% 만 양
        When:  판정한다
        Then:  통과, 고원 [(20, 30)] (주 비교만 보면 10 – 40%)
        """
        # Given
        main = _advantages([0.05] * 7)
        sub = _advantages([-0.01, -0.01, 0.02, 0.03, 0.01, -0.02, -0.03])

        # When
        judgment = se.judge(main, sub)

        # Then
        assert judgment.passed
        assert judgment.plateaus == ((20, 30),)

    def test_periods_must_overlap_on_same_w(self) -> None:
        """
        목적: 두 기간의 양의 구간이 서로 다른 w 면 탈락 — 같은 w 에서 둘 다 높아야 한다.

        Given: 주 비교 10 · 15 · 20% 양, 보조 25 · 30 · 35% 양
        When:  판정한다
        Then:  탈락
        """
        # Given
        main = _advantages([0.02, 0.02, 0.02, -0.01, -0.01, -0.01, -0.01])
        sub = _advantages([-0.01, -0.01, -0.01, 0.02, 0.02, 0.02, -0.01])

        # When / Then
        assert not se.judge(main, sub).passed

    def test_multiple_plateaus_reported(self) -> None:
        """
        목적: 연속 구간이 여럿이면 모두 보고한다.

        Given: 10 – 20% 와 30 – 40% 가 양, 25% 만 음
        When:  판정한다
        Then:  고원 [(10, 20), (30, 40)]
        """
        # Given
        adv = _advantages([0.01, 0.01, 0.01, -0.01, 0.01, 0.01, 0.01])

        # When / Then
        assert se.judge(adv, adv).plateaus == ((10, 20), (30, 40))

    def test_equal_to_baseline_is_not_higher(self) -> None:
        """
        목적: 「높다」는 엄격한 `>` — 기준선과 같으면(우위 0) 높지 않다.

        Given: 20 · 25 · 30% 중 25% 의 우위가 정확히 0
        When:  판정한다
        Then:  탈락
        """
        # Given
        adv = _advantages([-0.01, -0.01, 0.02, 0.0, 0.01, -0.02, -0.03])

        # When / Then
        assert not se.judge(adv, adv).passed

    def test_sub_only_basis_ignores_main_period(self) -> None:
        """
        목적: 대용이 탈락한 후보는 보조 기간만으로 판정한다 (D23 · D48 ⑤).

        Given: 주 비교는 전부 음, 보조 20 · 25 · 30% 양
        When:  주 비교 없이(None) 판정한다
        Then:  통과, 고원 [(20, 30)]
        """
        # Given
        sub = _advantages([-0.01, -0.01, 0.02, 0.03, 0.01, -0.02, -0.03])

        # When
        judgment = se.judge(None, sub)

        # Then
        assert judgment.passed
        assert judgment.plateaus == ((20, 30),)


class TestGateAgreement:
    """판정 일치 (D41) — w 별 「기준선보다 높은가」가 대용판 · 실물판에서 같은가."""

    def test_sign_match_and_plateau_verdict(self) -> None:
        """
        목적: w 별 부호 일치 수와 고원 판정(연속 3단계) 일치를 낸다.

        Given: 대용판 10 – 30% 양, 실물판 10 – 25% 양 (30% 만 뒤집힘)
        When:  판정 일치를 잰다
        Then:  일치 6/7, 30% 불일치, 두 판 모두 고원 있음(판정 일치), 고원 범위는 다르다
        """
        # Given
        proxy = _advantages([0.02, 0.02, 0.02, 0.02, 0.001, -0.01, -0.01])
        real = _advantages([0.02, 0.02, 0.02, 0.02, -0.001, -0.01, -0.01])

        # When
        gate = se.gate_agreement(proxy, real)

        # Then
        assert gate.match_count == 6
        assert gate.sign_match[30] is False
        assert gate.proxy_plateaus == ((10, 30),)
        assert gate.real_plateaus == ((10, 25),)
        assert gate.plateau_verdict_match


# ============================================================================
# 모으기 — 판정 기준 두 가지 · 관문 다섯
# ============================================================================


class TestCollect:
    """collect_judgments · collect_gates — 어느 실행을 어느 실행과 비교하는가."""

    def test_judgment_rows_have_both_bases_for_proxy_candidates(self) -> None:
        """
        목적: 대용을 쓰는 후보(HAA · 로테이션)는 두 판정 기준을 모두 낸다 — 러너는 확인 지점 1 전에 돈다.

        Given: 149개 가짜 결과
        When:  판정 행을 모은다
        Then:  HAA · 로테이션은 기준 둘 × 7, 금 · EWY 는 기준 하나 × 7 (합 42행)
        """
        # When
        rows = se.collect_judgments(_fake_results({}))

        # Then
        bases: dict[str, set[str]] = {}
        for row in rows:
            bases.setdefault(row.candidate, set()).add(row.basis)
        assert len(rows) == 42
        assert bases[se.CANDIDATE_HAA] == {se.BASIS_BOTH, se.BASIS_SUB_ONLY}
        assert bases[se.CANDIDATE_ROTATION] == {se.BASIS_BOTH, se.BASIS_SUB_ONLY}
        assert bases[se.CANDIDATE_GOLD] == {se.BASIS_BOTH}
        assert bases[se.CANDIDATE_EWY] == {se.BASIS_BOTH}

    def test_judgment_marks_boundary_advantage(self) -> None:
        """
        목적: 우위 절댓값이 0.00005 미만(4자리로 0)인 w 는 「경계」로 표시한다 (D48 ⑥).

        Given: 보조 기간 금의 우위가 0.00004 (기준선 0.5, 금 0.50004)
        When:  판정 행을 모은다
        Then:  금의 모든 w 행이 경계
        """
        # Given
        results = _fake_results({(se.GROUP_SUB, se.CANDIDATE_GOLD, se.VARIANT_REAL): 0.50004})

        # When
        rows = [r for r in se.collect_judgments(results) if r.candidate == se.CANDIDATE_GOLD]

        # Then
        assert rows
        assert all(r.boundary for r in rows)

    def test_gates_pair_proxy_with_real_at_same_start(self) -> None:
        """
        목적: 관문 다섯이 같은 시작일의 대용판 · 실물판을 짝짓고, 신호 일치율을 함께 낸다.

        Given: 로테이션 순수 대용판의 Calmar 0.7(실물판 0.5), 4달 중 1달 비중이 다른 판단 비중표
        When:  관문 행을 모은다
        Then:  5관문 × 7 = 35행, 로테이션 관문 시작일 2011-11-10 · Calmar 차이 −0.2 · 신호 일치율 0.75
        """
        # Given
        month_dates = [date(2016, m, 1) for m in range(1, 5)]
        proxy_targets = _targets(month_dates, [{"vxus": 1.0, "shy": 0.0}] * 3 + [{"vxus": 0.0, "shy": 1.0}])
        results = _fake_results(
            {(se.GROUP_GATE_ROTATION, se.CANDIDATE_ROTATION, se.VARIANT_PURE): 0.7},
            {(se.GROUP_GATE_ROTATION, se.CANDIDATE_ROTATION, se.VARIANT_PURE): proxy_targets},
        )

        # When
        rows = se.collect_gates(results)

        # Then
        assert len(rows) == 35
        assert {r.gate for r in rows} == set(se.GATE_IDS)
        rotation = [r for r in rows if r.gate == se.GATE_ROTATION]
        assert len(rotation) == 7
        assert all(r.start_date == date(2011, 11, 10) for r in rotation)
        assert rotation[0].real_calmar - rotation[0].proxy_calmar == pytest.approx(-0.2, abs=1e-12)
        assert rotation[0].signal_agreement == pytest.approx(0.75, abs=1e-12)
        assert rotation[0].signal_months == 4

    def test_judgment_reads_main_and_sub_from_their_groups(self) -> None:
        """
        목적: 판정의 주 비교 우위는 주 비교 묶음(이어 붙인 판), 보조 우위는 보조 묶음(실물판)에서 온다.

        Given: 기준선 0.5, 주 비교 HAA 0.6, 보조 HAA 0.45
        When:  판정 행을 모은다
        Then:  「주 비교 + 보조」 행은 주 비교 +0.1 · 보조 −0.05, 「보조만」 행은 주 비교 없음 · 보조 −0.05
        """
        # Given
        results = _fake_results(
            {
                (se.GROUP_MAIN, se.CANDIDATE_HAA, se.VARIANT_SPLICED): 0.6,
                (se.GROUP_SUB, se.CANDIDATE_HAA, se.VARIANT_REAL): 0.45,
            }
        )

        # When
        rows = [r for r in se.collect_judgments(results) if r.candidate == se.CANDIDATE_HAA]

        # Then
        both = [r for r in rows if r.basis == se.BASIS_BOTH]
        sub_only = [r for r in rows if r.basis == se.BASIS_SUB_ONLY]
        assert len(both) == len(sub_only) == len(se.W_PCTS)
        for row in both:
            assert row.main_advantage == pytest.approx(0.1, abs=1e-12)
            assert row.sub_advantage == pytest.approx(-0.05, abs=1e-12)
        for row in sub_only:
            assert row.main_advantage is None
            assert row.sub_advantage == pytest.approx(-0.05, abs=1e-12)

    def test_haa_gates_pair_the_planned_variants(self) -> None:
        """
        목적: HAA 관문 넷이 정한 대용판 · 실물판을 짝짓는다 (D48 ② ③) — 맞바뀌면 우위 열과 Calmar 차이 부호가 뒤집힌다.

        Given: HAA 실행마다 다른 Calmar (묶음 · 판별)
        When:  관문 행을 모은다
        Then:  관문별 대용판 · 실물판 Calmar 가 계획한 묶음 · 판의 값이다
        """
        # Given
        calmars = {
            (se.GROUP_GATE_HAA, se.CANDIDATE_HAA, se.VARIANT_PURE): 0.61,
            (se.GROUP_GATE_HAA, se.CANDIDATE_HAA, se.VARIANT_GATE_REAL): 0.62,
            (se.GROUP_PAIR_VEA, se.CANDIDATE_HAA, se.VARIANT_PURE): 0.63,
            (se.GROUP_PAIR_VEA, se.CANDIDATE_HAA, se.VARIANT_PAIR_VEA): 0.64,
            (se.GROUP_PAIR_BIL, se.CANDIDATE_HAA, se.VARIANT_PURE): 0.65,
            (se.GROUP_PAIR_BIL, se.CANDIDATE_HAA, se.VARIANT_PAIR_BIL): 0.66,
            (se.GROUP_PAIR_PDBC, se.CANDIDATE_HAA, se.VARIANT_PAIR_PDBC): 0.67,
        }
        expected = {
            se.GATE_HAA_BUNDLE: (0.61, 0.62),
            se.GATE_HAA_PAIR_VEA: (0.63, 0.64),
            se.GATE_HAA_PAIR_BIL: (0.65, 0.66),
            se.GATE_HAA_PAIR_PDBC: (0.61, 0.67),
        }

        # When
        rows = se.collect_gates(_fake_results(calmars))

        # Then
        for gate, (proxy_calmar, real_calmar) in expected.items():
            gate_rows = [r for r in rows if r.gate == gate]
            assert len(gate_rows) == len(se.W_PCTS)
            for row in gate_rows:
                assert row.proxy_calmar == pytest.approx(proxy_calmar, abs=1e-12)
                assert row.real_calmar == pytest.approx(real_calmar, abs=1e-12)


# ============================================================================
# 워커
# ============================================================================


class TestRunGridCase:
    """run_grid_case 의 시작일 확인 — 엔진의 start_date 는 하한이라 늦게 시작하면 조용히 늦게 시작한다."""

    def test_later_actual_start_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        목적: 결과의 첫 날짜가 묶음 시작일과 다르면 ValueError — 같은 기간 비교가 깨진다.

        Given: 엔진이 요청보다 하루 늦게 시작한 결과를 돌려준다
        When:  워커를 실행한다
        Then:  ValueError
        """
        # Given
        case = se.GridCase(se.GROUP_MAIN, se.CANDIDATE_GOLD, 30, se.VARIANT_SPLICED, date(2007, 6, 22))
        late = pd.DataFrame({COL_DATE: [date(2007, 6, 25), date(2007, 6, 26)], "equity": [1.0, 1.0]})

        def _fake_run(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
            return PortfolioResult("t", "t", late, pd.DataFrame(), {}, config)

        monkeypatch.setattr(se, "run_portfolio_backtest", _fake_run)

        # When / Then
        with pytest.raises(ValueError, match="시작일"):
            se.run_grid_case(case, _Q2_SLOTS)
