"""Streamlit dashboard for Singapore tourism and hotel recovery."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
VISITOR_FILE = DATA_DIR / "visitor_arrivals_2019_2025.csv"
HOTEL_FILE = DATA_DIR / "hotel_statistics_2019_2025.csv"

ARRIVALS_SOURCE = (
    "https://data.gov.sg/datasets/"
    "d_7e7b2ee60c6ffc962f80fef129cf306e/view"
)
HOTEL_SOURCE = (
    "https://data.gov.sg/datasets/"
    "d_8e62605f0c1c948702b6ea0fe45242d3/view"
)


st.set_page_config(
    page_title="Singapore Tourism Recovery",
    page_icon="🌏",
    layout="wide",
)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    visitors = pd.read_csv(VISITOR_FILE, parse_dates=["date"])
    hotels = pd.read_csv(HOTEL_FILE, parse_dates=["date"])
    return visitors, hotels


def recovery_index_by_market(data: pd.DataFrame) -> pd.DataFrame:
    baseline = (
        data[data["year"] == 2019][["market", "month", "arrivals"]]
        .rename(columns={"arrivals": "arrivals_2019"})
        .drop_duplicates(["market", "month"])
    )
    result = data.merge(baseline, on=["market", "month"], how="left")
    baseline_arrivals = result["arrivals_2019"].where(
        result["arrivals_2019"] > 0
    )
    result["recovery_index"] = result["arrivals"].div(baseline_arrivals) * 100
    return result


def same_month_recovery(data: pd.DataFrame, latest_date: pd.Timestamp) -> float | None:
    latest_value = data.loc[data["date"] == latest_date, "arrivals"].sum()
    baseline_value = data.loc[
        (data["year"] == 2019) & (data["month"] == latest_date.month), "arrivals"
    ].sum()
    if baseline_value <= 0:
        return None
    return latest_value / baseline_value * 100


def hotel_value(
    hotels: pd.DataFrame, metric: str, date: pd.Timestamp
) -> float | None:
    values = hotels.loc[
        (hotels["metric"] == metric)
        & (hotels["segment"] == "All gazetted hotels")
        & (hotels["date"] == date),
        "value",
    ]
    return None if values.empty else float(values.iloc[0])


def add_pandemic_shading(figure) -> None:
    figure.add_vrect(
        x0="2020-03-01",
        x1="2021-12-31",
        fillcolor="#9CA3AF",
        opacity=0.14,
        line_width=0,
        annotation_text="COVID-19 disruption",
        annotation_position="top left",
    )


st.title("Singapore Inbound Tourism and Hotel Recovery")
st.caption(
    "Monthly visitor arrivals by place of residence and gazetted-hotel performance, "
    "2019-2025"
)

if not VISITOR_FILE.exists() or not HOTEL_FILE.exists():
    st.error("Processed data files are missing. Run the data-wrangling script first.")
    st.code("python src/wrangle.py", language="bash")
    st.stop()

visitors, hotels = load_data()
countries = sorted(
    visitors.loc[visitors["market_type"] == "country", "market"].unique()
)

default_markets = [
    market
    for market in ["China", "Indonesia", "India", "Australia", "Malaysia"]
    if market in countries
]

st.sidebar.header("Filters")
year_range = st.sidebar.slider(
    "Year range",
    min_value=int(visitors["year"].min()),
    max_value=int(visitors["year"].max()),
    value=(2019, 2025),
)
selected_markets = st.sidebar.multiselect(
    "Source markets",
    options=countries,
    default=default_markets,
    help="Select one or more places of residence for comparison.",
)
show_2019_reference = st.sidebar.checkbox(
    "Show 2019 recovery reference", value=True
)

if not selected_markets:
    st.warning("Select at least one source market from the sidebar.")
    st.stop()

country_data = visitors[
    (visitors["market_type"] == "country")
    & (visitors["market"].isin(selected_markets))
].copy()
filtered_visitors = country_data[
    country_data["year"].between(year_range[0], year_range[1])
].copy()
filtered_hotels = hotels[hotels["year"].between(year_range[0], year_range[1])].copy()

if filtered_visitors.empty:
    st.warning("No visitor-arrival data are available for the selected filters.")
    st.stop()

latest_visitor_date = filtered_visitors["date"].max()
latest_selected_arrivals = int(
    filtered_visitors.loc[
        filtered_visitors["date"] == latest_visitor_date, "arrivals"
    ].sum()
)
recovery_pct = same_month_recovery(country_data, latest_visitor_date)

latest_hotel_date = filtered_hotels["date"].max()
occupancy = hotel_value(
    filtered_hotels, "Average Hotel Occupancy Rate", latest_hotel_date
)
room_rate = hotel_value(filtered_hotels, "Average Room Rate", latest_hotel_date)

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric(
    f"Selected arrivals, {latest_visitor_date:%b %Y}",
    f"{latest_selected_arrivals:,.0f}",
)
metric_2.metric(
    "Recovery vs same month in 2019",
    "n.a." if recovery_pct is None else f"{recovery_pct:.1f}%",
)
metric_3.metric(
    f"Hotel occupancy, {latest_hotel_date:%b %Y}",
    "n.a." if occupancy is None else f"{occupancy:.1f}%",
)
metric_4.metric(
    f"Average room rate, {latest_hotel_date:%b %Y}",
    "n.a." if room_rate is None else f"S${room_rate:,.0f}",
)

overview_tab, markets_tab, hotels_tab, methods_tab = st.tabs(
    ["Overview", "Source markets", "Hotel recovery", "Data and methodology"]
)

with overview_tab:
    st.subheader("Visitor arrivals by source market")
    arrivals_figure = px.line(
        filtered_visitors,
        x="date",
        y="arrivals",
        color="market",
        labels={"date": "Month", "arrivals": "Visitor arrivals", "market": "Market"},
    )
    add_pandemic_shading(arrivals_figure)
    arrivals_figure.update_layout(hovermode="x unified", legend_title_text="")
    st.plotly_chart(arrivals_figure, width="stretch")

    st.subheader("Recovery relative to the same month in 2019")
    recovery_data = recovery_index_by_market(country_data)
    recovery_data = recovery_data[
        recovery_data["year"].between(year_range[0], year_range[1])
    ]
    recovery_figure = px.line(
        recovery_data,
        x="date",
        y="recovery_index",
        color="market",
        labels={
            "date": "Month",
            "recovery_index": "Recovery index (same month in 2019 = 100)",
            "market": "Market",
        },
    )
    if show_2019_reference:
        recovery_figure.add_hline(
            y=100,
            line_dash="dash",
            line_color="#374151",
            annotation_text="2019 level",
        )
    add_pandemic_shading(recovery_figure)
    recovery_figure.update_layout(hovermode="x unified", legend_title_text="")
    st.plotly_chart(recovery_figure, width="stretch")

    st.info(
        "The recovery index compares each month with the matching month in 2019. "
        "This controls for regular seasonal differences across months."
    )

with markets_tab:
    st.subheader("Source-market comparison")
    market_summary = (
        filtered_visitors.groupby("market", as_index=False)["arrivals"]
        .sum()
        .sort_values("arrivals", ascending=True)
    )
    market_bar = px.bar(
        market_summary,
        x="arrivals",
        y="market",
        orientation="h",
        labels={"arrivals": "Arrivals in selected period", "market": "Source market"},
    )
    market_bar.update_layout(showlegend=False)
    st.plotly_chart(market_bar, width="stretch")

    annual_market = (
        filtered_visitors.groupby(["market", "year"], as_index=False)["arrivals"].sum()
        .pivot(index="market", columns="year", values="arrivals")
        .reset_index()
    )
    annual_market.columns = [str(column) for column in annual_market.columns]
    recovery_column = f"{year_range[1]} vs {year_range[0]} recovery (%)"
    if (
        year_range[0] != year_range[1]
        and str(year_range[0]) in annual_market.columns
        and str(year_range[1]) in annual_market.columns
    ):
        baseline_arrivals = annual_market[str(year_range[0])].where(
            annual_market[str(year_range[0])] > 0
        )
        annual_market[recovery_column] = (
            annual_market[str(year_range[1])].div(baseline_arrivals) * 100
        )
    annual_column_config = {
        str(year): st.column_config.NumberColumn(f"{year} arrivals", format="%,d")
        for year in range(year_range[0], year_range[1] + 1)
        if str(year) in annual_market.columns
    }
    if recovery_column in annual_market.columns:
        annual_column_config[recovery_column] = st.column_config.NumberColumn(
            recovery_column, format="%.1f%%"
        )
    st.dataframe(
        annual_market,
        width="stretch",
        hide_index=True,
        column_config=annual_column_config,
    )

with hotels_tab:
    st.subheader("Hotel occupancy and room rates")
    overall_hotels = filtered_hotels[
        filtered_hotels["segment"] == "All gazetted hotels"
    ].copy()
    occupancy_data = overall_hotels[
        overall_hotels["metric"] == "Average Hotel Occupancy Rate"
    ]
    room_rate_data = overall_hotels[overall_hotels["metric"] == "Average Room Rate"]

    left_chart, right_chart = st.columns(2)
    with left_chart:
        occupancy_figure = px.line(
            occupancy_data,
            x="date",
            y="value",
            labels={"date": "Month", "value": "Occupancy rate (%)"},
            title="Average hotel occupancy rate",
        )
        add_pandemic_shading(occupancy_figure)
        st.plotly_chart(occupancy_figure, width="stretch")
    with right_chart:
        rate_figure = px.line(
            room_rate_data,
            x="date",
            y="value",
            labels={"date": "Month", "value": "Average room rate (S$)"},
            title="Average room rate",
        )
        add_pandemic_shading(rate_figure)
        st.plotly_chart(rate_figure, width="stretch")

    st.subheader("Visitor and hotel-revenue recovery")
    total_arrivals = visitors[
        (visitors["market_type"] == "total")
        & (visitors["year"].between(year_range[0], year_range[1]))
    ][["date", "year", "month", "arrivals"]].copy()
    total_baseline = visitors[
        (visitors["market_type"] == "total") & (visitors["year"] == 2019)
    ][["month", "arrivals"]].rename(columns={"arrivals": "baseline"})
    total_arrivals = total_arrivals.merge(total_baseline, on="month", how="left")
    total_baseline_values = total_arrivals["baseline"].where(
        total_arrivals["baseline"] > 0
    )
    total_arrivals["value"] = total_arrivals["arrivals"].div(
        total_baseline_values
    ) * 100
    total_arrivals["series"] = "Total visitor arrivals"

    room_revenue = overall_hotels[overall_hotels["metric"] == "Room Revenue"][
        ["date", "year", "month", "value"]
    ].copy()
    revenue_baseline = hotels[
        (hotels["metric"] == "Room Revenue")
        & (hotels["segment"] == "All gazetted hotels")
        & (hotels["year"] == 2019)
    ][["month", "value"]].rename(columns={"value": "baseline"})
    room_revenue = room_revenue.merge(revenue_baseline, on="month", how="left")
    revenue_baseline_values = room_revenue["baseline"].where(
        room_revenue["baseline"] > 0
    )
    room_revenue["value"] = room_revenue["value"].div(
        revenue_baseline_values
    ) * 100
    room_revenue["series"] = "Hotel room revenue"

    comparison = pd.concat(
        [
            total_arrivals[["date", "value", "series"]],
            room_revenue[["date", "value", "series"]],
        ],
        ignore_index=True,
    )
    comparison_figure = px.line(
        comparison,
        x="date",
        y="value",
        color="series",
        labels={
            "date": "Month",
            "value": "Recovery index (same month in 2019 = 100)",
            "series": "",
        },
    )
    comparison_figure.add_hline(y=100, line_dash="dash", line_color="#374151")
    add_pandemic_shading(comparison_figure)
    comparison_figure.update_layout(hovermode="x unified", legend_title_text="")
    st.plotly_chart(comparison_figure, width="stretch")

with methods_tab:
    st.subheader("Data sources")
    st.markdown(
        f"- [International Visitor Arrivals By Place Of Residence, Monthly]({ARRIVALS_SOURCE})\n"
        f"- [Hotel Statistics, Monthly]({HOTEL_SOURCE})"
    )
    st.write(
        "Both datasets are published on data.gov.sg and sourced from the Singapore "
        "Tourism Board. The project uses complete calendar years from 2019 through 2025."
    )

    st.subheader("Definitions")
    st.markdown(
        "- **Source market** means the visitor's place of residence, not citizenship.\n"
        "- **Gazetted hotels** are licensed hotels covered by the relevant tourism legislation.\n"
        "- **Recovery index** compares a month with the same calendar month in 2019."
    )

    st.subheader("Limitations")
    st.markdown(
        "- Aggregated monthly data cannot identify why arrivals changed or establish causality.\n"
        "- Hotel statistics cover gazetted hotels rather than every accommodation provider.\n"
        "- Room rates and revenue are nominal and are not adjusted for inflation.\n"
        "- Results can be affected by seasonality, public policy, flight capacity and major events."
    )

    st.subheader("Download filtered data")
    st.download_button(
        "Download selected visitor-arrival data",
        data=filtered_visitors.to_csv(index=False).encode("utf-8"),
        file_name="selected_visitor_arrivals.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download selected hotel data",
        data=filtered_hotels.to_csv(index=False).encode("utf-8"),
        file_name="selected_hotel_statistics.csv",
        mime="text/csv",
    )
