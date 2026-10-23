"""Reusable analysis helpers for the tourism recovery dashboard."""

from __future__ import annotations

import pandas as pd


def annual_market_comparison(
    visitors: pd.DataFrame,
    baseline_year: int,
    comparison_year: int,
) -> pd.DataFrame:
    """Compare country arrivals and visitor shares between two complete years."""
    countries = visitors[visitors["market_type"] == "country"].copy()
    annual = (
        countries[countries["year"].isin([baseline_year, comparison_year])]
        .groupby(["market", "year"], as_index=False)["arrivals"]
        .sum()
        .pivot(index="market", columns="year", values="arrivals")
    )

    missing_years = {baseline_year, comparison_year} - set(annual.columns)
    if missing_years:
        raise ValueError(f"Visitor data are missing comparison years: {sorted(missing_years)}")

    result = annual.rename(
        columns={
            baseline_year: "baseline_arrivals",
            comparison_year: "comparison_arrivals",
        }
    ).reset_index()
    baseline = result["baseline_arrivals"].where(result["baseline_arrivals"] > 0)
    baseline_total = result["baseline_arrivals"].sum()
    comparison_total = result["comparison_arrivals"].sum()

    result["recovery_pct"] = result["comparison_arrivals"].div(baseline) * 100
    result["baseline_share_pct"] = (
        result["baseline_arrivals"].div(baseline_total) * 100
    )
    result["comparison_share_pct"] = (
        result["comparison_arrivals"].div(comparison_total) * 100
    )
    result["share_change_pp"] = (
        result["comparison_share_pct"] - result["baseline_share_pct"]
    )
    return result


def major_market_recovery(
    comparison: pd.DataFrame,
    number_of_markets: int = 15,
) -> pd.DataFrame:
    """Rank recovery among the largest baseline-year source markets."""
    major_markets = comparison.nlargest(number_of_markets, "baseline_arrivals")
    return major_markets.sort_values("recovery_pct", ascending=False).reset_index(
        drop=True
    )


def composition_with_other(
    comparison: pd.DataFrame,
    baseline_year: int,
    comparison_year: int,
    number_of_markets: int = 8,
) -> pd.DataFrame:
    """Return top source-market shares for a compact 100% composition chart."""
    top_markets = comparison.nlargest(number_of_markets, "baseline_arrivals")[
        "market"
    ].tolist()
    rows: list[dict[str, object]] = []

    for year, share_column in (
        (baseline_year, "baseline_share_pct"),
        (comparison_year, "comparison_share_pct"),
    ):
        selected = comparison[comparison["market"].isin(top_markets)]
        for row in selected.itertuples(index=False):
            rows.append(
                {
                    "year": str(year),
                    "market": row.market,
                    "share_pct": getattr(row, share_column),
                }
            )
        rows.append(
            {
                "year": str(year),
                "market": "Other markets",
                "share_pct": 100 - selected[share_column].sum(),
            }
        )

    return pd.DataFrame(rows)


def annual_total_arrivals(visitors: pd.DataFrame) -> pd.DataFrame:
    """Return one total-arrival observation per calendar year."""
    return (
        visitors[visitors["market_type"] == "total"]
        .groupby("year", as_index=False)["arrivals"]
        .sum()
        .sort_values("year")
    )


def annual_hotel_summary(hotels: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hotel indicators using metric-appropriate annual statistics."""
    overall = hotels[hotels["segment"] == "All gazetted hotels"]
    mean_metrics = {
        "Average Hotel Occupancy Rate": "occupancy_pct",
        "Average Room Rate": "room_rate_sgd",
    }
    pieces = []
    for metric, column in mean_metrics.items():
        piece = (
            overall[overall["metric"] == metric]
            .groupby("year", as_index=False)["value"]
            .mean()
            .rename(columns={"value": column})
        )
        pieces.append(piece)

    revenue = (
        overall[overall["metric"] == "Room Revenue"]
        .groupby("year", as_index=False)["value"]
        .sum()
        .rename(columns={"value": "room_revenue_sgd_thousand"})
    )
    pieces.append(revenue)

    result = pieces[0]
    for piece in pieces[1:]:
        result = result.merge(piece, on="year", how="outer")
    return result.sort_values("year")
