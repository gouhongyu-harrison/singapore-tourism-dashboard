from pathlib import Path

import pandas as pd
import pytest

from src.analysis import (
    annual_hotel_summary,
    annual_market_comparison,
    annual_total_arrivals,
    composition_with_other,
    major_market_recovery,
)


BASE_DIR = Path(__file__).resolve().parents[1]
VISITOR_FILE = BASE_DIR / "data" / "processed" / "visitor_arrivals_2019_2025.csv"
HOTEL_FILE = BASE_DIR / "data" / "processed" / "hotel_statistics_2019_2025.csv"


@pytest.fixture(scope="module")
def visitors() -> pd.DataFrame:
    return pd.read_csv(VISITOR_FILE, parse_dates=["date"])


@pytest.fixture(scope="module")
def hotels() -> pd.DataFrame:
    return pd.read_csv(HOTEL_FILE, parse_dates=["date"])


def test_market_comparison_uses_annual_totals(visitors: pd.DataFrame) -> None:
    comparison = annual_market_comparison(visitors, 2019, 2025).set_index("market")

    assert comparison.loc["Australia", "recovery_pct"] == pytest.approx(110.85, 0.01)
    assert comparison.loc["Malaysia", "comparison_share_pct"] > comparison.loc[
        "Malaysia", "baseline_share_pct"
    ]


def test_major_market_ranking_avoids_small_baselines(visitors: pd.DataFrame) -> None:
    comparison = annual_market_comparison(visitors, 2019, 2025)
    ranking = major_market_recovery(comparison, number_of_markets=15)

    assert len(ranking) == 15
    assert ranking.iloc[0]["market"] == "Australia"
    assert ranking["recovery_pct"].is_monotonic_decreasing


def test_composition_sums_to_one_hundred(visitors: pd.DataFrame) -> None:
    comparison = annual_market_comparison(visitors, 2019, 2025)
    composition = composition_with_other(comparison, 2019, 2025)

    totals = composition.groupby("year")["share_pct"].sum()
    assert totals.loc["2019"] == pytest.approx(100)
    assert totals.loc["2025"] == pytest.approx(100)


def test_annual_headline_summaries(visitors: pd.DataFrame, hotels: pd.DataFrame) -> None:
    arrivals = annual_total_arrivals(visitors).set_index("year")
    hotel_summary = annual_hotel_summary(hotels).set_index("year")

    assert arrivals.loc[2025, "arrivals"] == 16_912_288
    assert hotel_summary.loc[2025, "occupancy_pct"] == pytest.approx(81.94, 0.01)
    assert hotel_summary.loc[2025, "room_revenue_sgd_thousand"] > hotel_summary.loc[
        2019, "room_revenue_sgd_thousand"
    ]


def test_market_comparison_rejects_missing_year(visitors: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="missing comparison years"):
        annual_market_comparison(visitors, 2019, 2026)
