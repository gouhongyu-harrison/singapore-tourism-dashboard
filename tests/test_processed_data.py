from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
VISITOR_FILE = BASE_DIR / "data" / "processed" / "visitor_arrivals_2019_2025.csv"
HOTEL_FILE = BASE_DIR / "data" / "processed" / "hotel_statistics_2019_2025.csv"


def test_processed_files_exist() -> None:
    assert VISITOR_FILE.exists()
    assert HOTEL_FILE.exists()


def test_visitor_data_quality() -> None:
    visitors = pd.read_csv(VISITOR_FILE, parse_dates=["date"])
    assert visitors["year"].min() == 2019
    assert visitors["year"].max() == 2025
    assert not visitors.duplicated(["date", "market", "market_type"]).any()
    assert {"China", "India", "Indonesia", "Malaysia", "Australia"}.issubset(
        set(visitors.loc[visitors["market_type"] == "country", "market"])
    )
    assert visitors.loc[visitors["market_type"] == "total", "arrivals"].notna().all()


def test_hotel_data_quality() -> None:
    hotels = pd.read_csv(HOTEL_FILE, parse_dates=["date"])
    assert hotels["year"].min() == 2019
    assert hotels["year"].max() == 2025
    assert not hotels.duplicated(["date", "metric", "segment"]).any()
    assert {
        "Room Revenue",
        "Average Room Rate",
        "Average Hotel Occupancy Rate",
    }.issubset(set(hotels["metric"]))
    assert hotels.loc[
        hotels["segment"] == "All gazetted hotels", "value"
    ].notna().all()
