"""Download, clean, validate, and export the project datasets.

The script uses two official data.gov.sg datasets:

1. International Visitor Arrivals By Place Of Residence, Monthly
2. Hotel Statistics, Monthly

Run from the repository root with:

    python src/wrangle.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
TABLES_DIR = BASE_DIR / "outputs" / "tables"

ARRIVALS_DATASET_ID = "d_7e7b2ee60c6ffc962f80fef129cf306e"
HOTEL_DATASET_ID = "d_8e62605f0c1c948702b6ea0fe45242d3"
DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"

START_YEAR = 2019
END_YEAR = 2025

MONTH_PATTERN = re.compile(
    r"^\d{4}(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$"
)


def fetch_dataset(dataset_id: str, limit: int = 500) -> dict[str, Any]:
    """Return a complete data.gov.sg datastore response for a small dataset."""
    url = f"{DATASTORE_URL}?resource_id={dataset_id}&limit={limit}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DS608-Singapore-Tourism-Dashboard/1.0",
        },
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)

    if not payload.get("success"):
        raise RuntimeError(f"data.gov.sg request failed for {dataset_id}")

    result = payload["result"]
    if result["total"] > len(result["records"]):
        raise RuntimeError(
            f"Dataset {dataset_id} contains {result['total']} records, "
            f"but only {len(result['records'])} were downloaded. Increase limit."
        )
    return payload


def _date_columns(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        raise ValueError("Dataset returned no records")
    columns = records[0].keys()
    date_columns = [column for column in columns if MONTH_PATTERN.fullmatch(column)]
    if not date_columns:
        raise ValueError("No YYYYMon columns were found in the dataset")
    return date_columns


def prepare_visitor_arrivals(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert the hierarchical wide arrivals table into tidy monthly rows."""
    records = sorted(payload["result"]["records"], key=lambda row: row["_id"])
    date_columns = _date_columns(records)
    output_rows: list[dict[str, Any]] = []
    current_region = "All markets"

    for record in records:
        raw_label = str(record["DataSeries"])
        market = raw_label.strip()
        indentation = len(raw_label) - len(raw_label.lstrip())

        if market.startswith("Total International Visitor Arrivals"):
            market_type = "total"
            region = "All markets"
        elif indentation <= 4:
            market_type = "region"
            current_region = market
            region = market
        else:
            market_type = "country"
            region = current_region

        for period in date_columns:
            date = pd.to_datetime(period, format="%Y%b")
            if START_YEAR <= date.year <= END_YEAR:
                output_rows.append(
                    {
                        "date": date,
                        "year": date.year,
                        "month": date.month,
                        "market": market,
                        "region": region,
                        "market_type": market_type,
                        "arrivals": pd.to_numeric(record.get(period), errors="coerce"),
                    }
                )

    result = pd.DataFrame(output_rows).sort_values(
        ["date", "market_type", "market"]
    )
    result.reset_index(drop=True, inplace=True)
    return result


def _hotel_metric_details(raw_label: str) -> tuple[str, str, str]:
    label = raw_label.strip()
    indentation = len(raw_label) - len(raw_label.lstrip())

    if label.startswith("Average Room Rate - "):
        metric = "Average Room Rate"
        segment = label.split(" - ", maxsplit=1)[1]
    elif label.startswith("Average Occupancy Rate - "):
        metric = "Average Hotel Occupancy Rate"
        segment = label.split(" - ", maxsplit=1)[1]
    else:
        metric = label
        segment = "All gazetted hotels" if indentation == 0 else "Other"

    unit_by_metric = {
        "Room Revenue": "SGD thousand",
        "Average Room Rate": "SGD per room night",
        "Average Hotel Occupancy Rate": "percent",
        "Gross Lettings": "room nights",
        "Available Room Nights": "room nights",
    }
    return metric, segment, unit_by_metric.get(metric, "not specified")


def prepare_hotel_statistics(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert the wide hotel table into tidy monthly observations."""
    records = sorted(payload["result"]["records"], key=lambda row: row["_id"])
    date_columns = _date_columns(records)
    output_rows: list[dict[str, Any]] = []

    for record in records:
        metric, segment, unit = _hotel_metric_details(str(record["DataSeries"]))
        for period in date_columns:
            date = pd.to_datetime(period, format="%Y%b")
            if START_YEAR <= date.year <= END_YEAR:
                output_rows.append(
                    {
                        "date": date,
                        "year": date.year,
                        "month": date.month,
                        "metric": metric,
                        "segment": segment,
                        "value": pd.to_numeric(record.get(period), errors="coerce"),
                        "unit": unit,
                    }
                )

    result = pd.DataFrame(output_rows).sort_values(["date", "metric", "segment"])
    result.reset_index(drop=True, inplace=True)
    return result


def validate_data(visitors: pd.DataFrame, hotels: pd.DataFrame) -> None:
    """Fail clearly if required coverage, categories, or uniqueness are missing."""
    expected_years = set(range(START_YEAR, END_YEAR + 1))
    expected_months = pd.date_range(
        f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS"
    ).tolist()
    required_visitor_columns = {
        "date", "year", "month", "market", "region", "market_type", "arrivals"
    }
    required_hotel_columns = {
        "date", "year", "month", "metric", "segment", "value", "unit"
    }
    required_markets = {"China", "India", "Indonesia", "Malaysia", "Australia"}
    required_metrics = {
        "Room Revenue",
        "Average Room Rate",
        "Average Hotel Occupancy Rate",
    }

    for name, data, required_columns in (
        ("Visitor", visitors, required_visitor_columns),
        ("Hotel", hotels, required_hotel_columns),
    ):
        missing_columns = required_columns - set(data.columns)
        if missing_columns:
            raise ValueError(f"{name} data are missing columns: {sorted(missing_columns)}")

        dates = pd.to_datetime(data["date"], errors="coerce")
        if dates.isna().any():
            raise ValueError(f"{name} data contain invalid dates")
        if dates.dt.is_month_start.eq(False).any():
            raise ValueError(f"{name} dates must be the first day of each month")
        if not dates.dt.year.eq(data["year"]).all() or not dates.dt.month.eq(
            data["month"]
        ).all():
            raise ValueError(f"{name} year/month values do not match their dates")
        if dates.sort_values().drop_duplicates().tolist() != expected_months:
            raise ValueError(
                f"{name} data do not contain complete monthly coverage from "
                f"{START_YEAR} to {END_YEAR}"
            )

    if set(visitors["year"].unique()) != expected_years:
        raise ValueError("Visitor data do not contain every year from 2019 to 2025")
    if set(hotels["year"].unique()) != expected_years:
        raise ValueError("Hotel data do not contain every year from 2019 to 2025")

    for name, data, value_column in (
        ("Visitor arrivals", visitors, "arrivals"),
        ("Hotel values", hotels, "value"),
    ):
        values = pd.to_numeric(data[value_column], errors="coerce")
        if (
            values.isna().any()
            or values.isin([float("inf"), float("-inf")]).any()
            or values.lt(0).any()
        ):
            raise ValueError(
                f"{name} contain missing, non-finite, or negative values"
            )

    countries = set(visitors.loc[visitors["market_type"] == "country", "market"])
    if missing := required_markets - countries:
        raise ValueError(f"Required source markets are missing: {sorted(missing)}")

    metrics = set(hotels["metric"])
    if missing := required_metrics - metrics:
        raise ValueError(f"Required hotel metrics are missing: {sorted(missing)}")

    visitor_duplicates = visitors.duplicated(
        ["date", "market", "market_type"], keep=False
    )
    hotel_duplicates = hotels.duplicated(["date", "metric", "segment"], keep=False)
    if visitor_duplicates.any():
        raise ValueError("Duplicate visitor keys were found")
    if hotel_duplicates.any():
        raise ValueError("Duplicate hotel keys were found")


def build_summary_tables(
    visitors: pd.DataFrame, hotels: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Create small, presentation-ready tables from the processed data."""
    total_visitors = visitors[visitors["market_type"] == "total"].copy()
    annual_arrivals = (
        total_visitors.groupby("year", as_index=False)["arrivals"].sum()
        .rename(columns={"arrivals": "total_visitor_arrivals"})
        .sort_values("year")
    )
    baseline_arrivals = annual_arrivals.loc[
        annual_arrivals["year"] == START_YEAR, "total_visitor_arrivals"
    ].iloc[0]
    annual_arrivals["visitor_recovery_vs_2019_pct"] = (
        annual_arrivals["total_visitor_arrivals"] / baseline_arrivals * 100
    )

    overall_hotels = hotels[hotels["segment"] == "All gazetted hotels"].copy()
    annual_hotel = overall_hotels.pivot_table(
        index="year", columns="metric", values="value", aggfunc="mean"
    ).reset_index()
    annual_revenue = (
        overall_hotels[overall_hotels["metric"] == "Room Revenue"]
        .groupby("year", as_index=False)["value"]
        .sum()
        .rename(columns={"value": "hotel_room_revenue_sgd_thousand"})
    )
    annual_hotel = annual_hotel.drop(columns=["Room Revenue"], errors="ignore")
    annual_summary = annual_arrivals.merge(annual_hotel, on="year", how="left")
    annual_summary = annual_summary.merge(annual_revenue, on="year", how="left")
    annual_summary["hotel_room_revenue_sgd_million"] = (
        annual_summary["hotel_room_revenue_sgd_thousand"] / 1_000
    )

    country_rows = visitors[visitors["market_type"] == "country"]
    top_markets = (
        country_rows[country_rows["year"] == END_YEAR]
        .groupby(["market", "region"], as_index=False)["arrivals"]
        .sum()
        .sort_values("arrivals", ascending=False)
        .head(15)
    )
    official_total_2025 = annual_arrivals.loc[
        annual_arrivals["year"] == END_YEAR, "total_visitor_arrivals"
    ].iloc[0]
    top_markets["share_of_total_pct"] = (
        top_markets["arrivals"] / official_total_2025 * 100
    )

    quality_summary = pd.DataFrame(
        [
            {
                "dataset": "visitor_arrivals",
                "rows": len(visitors),
                "start_date": visitors["date"].min().date(),
                "end_date": visitors["date"].max().date(),
                "missing_values": int(visitors["arrivals"].isna().sum()),
                "duplicate_keys": int(
                    visitors.duplicated(["date", "market", "market_type"]).sum()
                ),
            },
            {
                "dataset": "hotel_statistics",
                "rows": len(hotels),
                "start_date": hotels["date"].min().date(),
                "end_date": hotels["date"].max().date(),
                "missing_values": int(hotels["value"].isna().sum()),
                "duplicate_keys": int(
                    hotels.duplicated(["date", "metric", "segment"]).sum()
                ),
            },
        ]
    )

    return {
        "annual_tourism_summary.csv": annual_summary,
        "top_source_markets_2025.csv": top_markets,
        "data_quality_summary.csv": quality_summary,
    }


def run() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    arrivals_payload = fetch_dataset(ARRIVALS_DATASET_ID)
    hotel_payload = fetch_dataset(HOTEL_DATASET_ID)

    (RAW_DIR / "visitor_arrivals_api.json").write_text(
        json.dumps(arrivals_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RAW_DIR / "hotel_statistics_api.json").write_text(
        json.dumps(hotel_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    visitors = prepare_visitor_arrivals(arrivals_payload)
    hotels = prepare_hotel_statistics(hotel_payload)
    validate_data(visitors, hotels)

    visitors.to_csv(PROCESSED_DIR / "visitor_arrivals_2019_2025.csv", index=False)
    hotels.to_csv(PROCESSED_DIR / "hotel_statistics_2019_2025.csv", index=False)

    for filename, table in build_summary_tables(visitors, hotels).items():
        table.to_csv(TABLES_DIR / filename, index=False)

    print(
        "Created processed datasets: "
        f"{len(visitors):,} visitor rows and {len(hotels):,} hotel rows."
    )
    print(f"Coverage: {START_YEAR}-01 to {END_YEAR}-12")


if __name__ == "__main__":
    run()
