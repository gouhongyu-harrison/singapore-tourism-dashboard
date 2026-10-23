"""Streamlit dashboard for Singapore tourism and hotel recovery."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analysis import (
    annual_hotel_summary,
    annual_market_comparison,
    annual_total_arrivals,
    composition_with_other,
    major_market_recovery,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"
VISITOR_FILE = DATA_DIR / "visitor_arrivals_2019_2025.csv"
HOTEL_FILE = DATA_DIR / "hotel_statistics_2019_2025.csv"
BASELINE_YEAR = 2019
MAJOR_MARKET_COUNT = 15

ARRIVALS_SOURCE = (
    "https://data.gov.sg/datasets/"
    "d_7e7b2ee60c6ffc962f80fef129cf306e/view"
)
HOTEL_SOURCE = (
    "https://data.gov.sg/datasets/"
    "d_8e62605f0c1c948702b6ea0fe45242d3/view"
)

PHASES = (
    ("2019 baseline", "2019-01-01", "2019-12-31", "#F59E0B", 0.06),
    ("Pandemic shock", "2020-03-01", "2021-12-31", "#64748B", 0.13),
    ("Reopening", "2022-01-01", "2022-12-31", "#3B82F6", 0.07),
    ("Recovery", "2023-01-01", "2025-12-31", "#10B981", 0.05),
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
        data[data["year"] == BASELINE_YEAR][["market", "month", "arrivals"]]
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
        (data["year"] == BASELINE_YEAR)
        & (data["month"] == latest_date.month),
        "arrivals",
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


def add_phase_shading(figure, *, labels: bool = False) -> None:
    """Mark the four analytical phases without breaking the time series."""
    for phase, start, end, colour, opacity in PHASES:
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor=colour,
            opacity=opacity,
            line_width=0,
            annotation_text=phase if labels else None,
            annotation_position="top left",
        )


def polish_figure(figure, *, legend_title: str = "") -> None:
    figure.update_layout(
        hovermode="x unified",
        legend_title_text=legend_title,
        margin=dict(l=10, r=10, t=45, b=10),
    )


st.title("Singapore Inbound Tourism and Hotel Recovery")
st.caption(
    "A descriptive account of the shock, reopening and changing visitor mix, "
    "using monthly official data from 2019 to 2025."
)

if not VISITOR_FILE.exists() or not HOTEL_FILE.exists():
    st.error("Processed data files are missing. Run the data-wrangling script first.")
    st.code("python src/wrangle.py", language="bash")
    st.stop()

visitors, hotels = load_data()
latest_complete_year = int(visitors["year"].max())
countries = sorted(
    visitors.loc[visitors["market_type"] == "country", "market"].unique()
)

default_markets = [
    market
    for market in ["China", "Indonesia", "India", "Australia", "Malaysia"]
    if market in countries
]

st.sidebar.header("Explore the data")
year_range = st.sidebar.slider(
    "Year range",
    min_value=int(visitors["year"].min()),
    max_value=latest_complete_year,
    value=(BASELINE_YEAR, latest_complete_year),
)
selected_markets = st.sidebar.multiselect(
    "Source markets",
    options=countries,
    default=default_markets,
    help="Source market means place of residence, not citizenship.",
)
show_2019_reference = st.sidebar.checkbox(
    "Show 2019 recovery reference", value=True
)
st.sidebar.caption(
    "Headline findings compare the complete years 2019 and 2025. "
    "The filters control the exploratory charts."
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

market_comparison = annual_market_comparison(
    visitors, BASELINE_YEAR, latest_complete_year
)
major_recovery = major_market_recovery(
    market_comparison, number_of_markets=MAJOR_MARKET_COUNT
)
fastest_market = major_recovery.iloc[0]

total_annual = annual_total_arrivals(visitors).set_index("year")
hotel_annual = annual_hotel_summary(hotels).set_index("year")
baseline_total = float(total_annual.loc[BASELINE_YEAR, "arrivals"])
latest_total = float(total_annual.loc[latest_complete_year, "arrivals"])
total_recovery_pct = latest_total / baseline_total * 100

baseline_hotel = hotel_annual.loc[BASELINE_YEAR]
latest_hotel = hotel_annual.loc[latest_complete_year]
occupancy_change_pp = (
    latest_hotel["occupancy_pct"] - baseline_hotel["occupancy_pct"]
)
room_rate_change_pct = (
    latest_hotel["room_rate_sgd"] / baseline_hotel["room_rate_sgd"] - 1
) * 100
revenue_change_pct = (
    latest_hotel["room_revenue_sgd_thousand"]
    / baseline_hotel["room_revenue_sgd_thousand"]
    - 1
) * 100

headline_1, headline_2, headline_3, headline_4 = st.columns(4)
headline_1.metric(
    f"Visitors in {latest_complete_year}",
    f"{latest_total / 1_000_000:.2f}M",
    f"{total_recovery_pct - 100:.1f}% vs 2019",
)
headline_2.metric(
    "Fastest major recovery",
    str(fastest_market["market"]),
    f"{fastest_market['recovery_pct']:.1f}% of 2019",
)
headline_3.metric(
    "Hotel room revenue",
    f"S${latest_hotel['room_revenue_sgd_thousand'] / 1_000_000:.2f}B",
    f"{revenue_change_pct:+.1f}% vs 2019",
)
headline_4.metric(
    "Hotel occupancy",
    f"{latest_hotel['occupancy_pct']:.1f}%",
    f"{occupancy_change_pp:+.1f} pp vs 2019",
)

story_tab, markets_tab, mix_tab, hotels_tab, methods_tab = st.tabs(
    [
        "Recovery story",
        "Market explorer",
        "Visitor mix",
        "Hotels",
        "Data and methodology",
    ]
)

with story_tab:
    st.subheader("The recovery is clearer when divided into phases")
    st.write(
        "The chart remains one continuous time series, while the shaded periods separate "
        "the 2019 baseline, pandemic shock, reopening and later recovery. This prevents "
        "the sharp structural break from being treated as an ordinary fluctuation."
    )

    total_monthly = visitors[visitors["market_type"] == "total"].copy()
    story_figure = px.area(
        total_monthly,
        x="date",
        y="arrivals",
        labels={"date": "Month", "arrivals": "Total visitor arrivals"},
        color_discrete_sequence=["#0F766E"],
    )
    add_phase_shading(story_figure, labels=True)
    polish_figure(story_figure)
    st.plotly_chart(story_figure, width="stretch")

    st.info(
        f"By {latest_complete_year}, total arrivals had recovered to "
        f"{total_recovery_pct:.1f}% of the 2019 level. Recovery was substantial, "
        "but not yet complete."
    )

    left_story, right_story = st.columns(2)
    with left_story:
        st.markdown("#### Which major market recovered fastest?")
        ranking = major_recovery.head(10).sort_values("recovery_pct")
        ranking_figure = px.bar(
            ranking,
            x="recovery_pct",
            y="market",
            orientation="h",
            text="recovery_pct",
            color="recovery_pct",
            color_continuous_scale=["#CBD5E1", "#0F766E"],
            labels={
                "recovery_pct": f"{latest_complete_year} arrivals (2019 = 100)",
                "market": "",
            },
        )
        ranking_figure.add_vline(
            x=100,
            line_dash="dash",
            line_color="#334155",
            annotation_text="2019 level",
        )
        ranking_figure.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        ranking_figure.update_layout(
            coloraxis_showscale=False, margin=dict(l=10, r=35, t=20, b=10)
        )
        st.plotly_chart(ranking_figure, width="stretch")
        st.caption(
            f"Major markets are defined as the {MAJOR_MARKET_COUNT} largest source "
            "markets in 2019. This avoids calling a very small market the fastest "
            "because of a low starting point."
        )

    with right_story:
        st.markdown("#### Did hotels recover for the same reason?")
        st.metric(
            "Average room rate",
            f"S${latest_hotel['room_rate_sgd']:,.0f}",
            f"{room_rate_change_pct:+.1f}% vs 2019",
        )
        st.metric(
            "Total visitor arrivals",
            f"{total_recovery_pct:.1f}% of 2019",
        )
        st.write(
            "Hotel room revenue exceeded its 2019 level even though visitor arrivals and "
            "occupancy had not fully returned. Higher nominal room rates therefore matter "
            "to the revenue story; visitor volume alone is not a sufficient explanation."
        )
        st.warning(
            "This is descriptive evidence. It does not prove that visitor arrivals caused "
            "hotel outcomes. Inflation, room supply, business travel, major events and "
            "staycations may also contribute."
        )

with markets_tab:
    latest_visitor_date = filtered_visitors["date"].max()
    latest_selected_arrivals = int(
        filtered_visitors.loc[
            filtered_visitors["date"] == latest_visitor_date, "arrivals"
        ].sum()
    )
    selected_recovery_pct = same_month_recovery(country_data, latest_visitor_date)

    selected_1, selected_2 = st.columns(2)
    selected_1.metric(
        f"Selected arrivals, {latest_visitor_date:%b %Y}",
        f"{latest_selected_arrivals:,.0f}",
    )
    selected_2.metric(
        "Selected recovery vs matching 2019 month",
        "n.a."
        if selected_recovery_pct is None
        else f"{selected_recovery_pct:.1f}%",
    )

    st.subheader("Visitor arrivals by selected source market")
    arrivals_figure = px.line(
        filtered_visitors,
        x="date",
        y="arrivals",
        color="market",
        labels={"date": "Month", "arrivals": "Visitor arrivals", "market": "Market"},
    )
    add_phase_shading(arrivals_figure)
    polish_figure(arrivals_figure)
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
    add_phase_shading(recovery_figure)
    polish_figure(recovery_figure)
    st.plotly_chart(recovery_figure, width="stretch")
    st.caption(
        "Each month is compared with the matching calendar month in 2019, reducing "
        "distortion from regular seasonal peaks and troughs."
    )

    st.subheader("Annual comparison for the selected markets")
    selected_annual = (
        filtered_visitors.groupby(["market", "year"], as_index=False)["arrivals"]
        .sum()
        .pivot(index="market", columns="year", values="arrivals")
        .reset_index()
    )
    selected_annual.columns = [str(column) for column in selected_annual.columns]
    recovery_column = f"{year_range[1]} vs {year_range[0]} recovery (%)"
    if (
        year_range[0] != year_range[1]
        and str(year_range[0]) in selected_annual.columns
        and str(year_range[1]) in selected_annual.columns
    ):
        selected_baseline = selected_annual[str(year_range[0])].where(
            selected_annual[str(year_range[0])] > 0
        )
        selected_annual[recovery_column] = (
            selected_annual[str(year_range[1])].div(selected_baseline) * 100
        )
    selected_config = {
        str(year): st.column_config.NumberColumn(f"{year} arrivals", format="%,d")
        for year in range(year_range[0], year_range[1] + 1)
        if str(year) in selected_annual.columns
    }
    if recovery_column in selected_annual.columns:
        selected_config[recovery_column] = st.column_config.NumberColumn(
            recovery_column, format="%.1f%%"
        )
    st.dataframe(
        selected_annual,
        width="stretch",
        hide_index=True,
        column_config=selected_config,
    )

with mix_tab:
    st.subheader("The source-market mix changed after the disruption")
    st.write(
        "Absolute arrivals answer how many visitors came. Market share answers whether "
        "Singapore became more or less dependent on particular source markets."
    )

    composition = composition_with_other(
        market_comparison,
        BASELINE_YEAR,
        latest_complete_year,
        number_of_markets=8,
    )
    composition_figure = px.bar(
        composition,
        x="year",
        y="share_pct",
        color="market",
        barmode="stack",
        text_auto=".1f",
        labels={"year": "", "share_pct": "Share of visitor arrivals (%)", "market": ""},
    )
    composition_figure.update_layout(
        yaxis_range=[0, 100], margin=dict(l=10, r=10, t=20, b=10)
    )
    st.plotly_chart(composition_figure, width="stretch")

    major_share_change = major_recovery.sort_values("share_change_pp")
    share_figure = px.bar(
        major_share_change,
        x="share_change_pp",
        y="market",
        orientation="h",
        color="share_change_pp",
        color_continuous_scale=["#B91C1C", "#F8FAFC", "#0F766E"],
        color_continuous_midpoint=0,
        labels={
            "share_change_pp": f"Change in visitor share, {BASELINE_YEAR}-{latest_complete_year} (pp)",
            "market": "",
        },
    )
    share_figure.add_vline(x=0, line_color="#334155")
    share_figure.update_layout(
        coloraxis_showscale=False, margin=dict(l=10, r=10, t=20, b=10)
    )
    st.plotly_chart(share_figure, width="stretch")

    largest_gain = major_share_change.iloc[-1]
    largest_loss = major_share_change.iloc[0]
    st.info(
        f"Among the major 2019 markets, {largest_gain['market']} recorded the largest "
        f"share gain ({largest_gain['share_change_pp']:+.2f} percentage points), while "
        f"{largest_loss['market']} recorded the largest decline "
        f"({largest_loss['share_change_pp']:+.2f} percentage points)."
    )

    with st.expander("View the full 2019-2025 comparison table"):
        mix_table = market_comparison.sort_values(
            "comparison_arrivals", ascending=False
        ).rename(
            columns={
                "market": "Source market",
                "baseline_arrivals": "2019 arrivals",
                "comparison_arrivals": f"{latest_complete_year} arrivals",
                "recovery_pct": "Recovery (%)",
                "baseline_share_pct": "2019 share (%)",
                "comparison_share_pct": f"{latest_complete_year} share (%)",
                "share_change_pp": "Share change (pp)",
            }
        )
        st.dataframe(
            mix_table,
            width="stretch",
            hide_index=True,
            column_config={
                "2019 arrivals": st.column_config.NumberColumn(format="%,d"),
                f"{latest_complete_year} arrivals": st.column_config.NumberColumn(
                    format="%,d"
                ),
                "Recovery (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "2019 share (%)": st.column_config.NumberColumn(format="%.2f%%"),
                f"{latest_complete_year} share (%)": st.column_config.NumberColumn(
                    format="%.2f%%"
                ),
                "Share change (pp)": st.column_config.NumberColumn(format="%+.2f"),
            },
        )

with hotels_tab:
    latest_hotel_date = filtered_hotels["date"].max()
    occupancy = hotel_value(
        filtered_hotels, "Average Hotel Occupancy Rate", latest_hotel_date
    )
    room_rate = hotel_value(
        filtered_hotels, "Average Room Rate", latest_hotel_date
    )

    hotel_1, hotel_2 = st.columns(2)
    hotel_1.metric(
        f"Hotel occupancy, {latest_hotel_date:%b %Y}",
        "n.a." if occupancy is None else f"{occupancy:.1f}%",
    )
    hotel_2.metric(
        f"Average room rate, {latest_hotel_date:%b %Y}",
        "n.a." if room_rate is None else f"S${room_rate:,.0f}",
    )

    overall_hotels = filtered_hotels[
        filtered_hotels["segment"] == "All gazetted hotels"
    ].copy()
    occupancy_data = overall_hotels[
        overall_hotels["metric"] == "Average Hotel Occupancy Rate"
    ]
    room_rate_data = overall_hotels[
        overall_hotels["metric"] == "Average Room Rate"
    ]

    left_chart, right_chart = st.columns(2)
    with left_chart:
        occupancy_figure = px.line(
            occupancy_data,
            x="date",
            y="value",
            labels={"date": "Month", "value": "Occupancy rate (%)"},
            title="Average hotel occupancy rate",
            color_discrete_sequence=["#2563EB"],
        )
        add_phase_shading(occupancy_figure)
        polish_figure(occupancy_figure)
        st.plotly_chart(occupancy_figure, width="stretch")
    with right_chart:
        rate_figure = px.line(
            room_rate_data,
            x="date",
            y="value",
            labels={"date": "Month", "value": "Average room rate (S$)"},
            title="Average room rate",
            color_discrete_sequence=["#0F766E"],
        )
        add_phase_shading(rate_figure)
        polish_figure(rate_figure)
        st.plotly_chart(rate_figure, width="stretch")

    st.subheader("Visitor arrivals and room revenue moved together, but not identically")
    total_arrivals = visitors[
        (visitors["market_type"] == "total")
        & (visitors["year"].between(year_range[0], year_range[1]))
    ][["date", "year", "month", "arrivals"]].copy()
    total_baseline = visitors[
        (visitors["market_type"] == "total")
        & (visitors["year"] == BASELINE_YEAR)
    ][["month", "arrivals"]].rename(columns={"arrivals": "baseline"})
    total_arrivals = total_arrivals.merge(total_baseline, on="month", how="left")
    total_arrivals["value"] = (
        total_arrivals["arrivals"]
        .div(total_arrivals["baseline"].where(total_arrivals["baseline"] > 0))
        * 100
    )
    total_arrivals["series"] = "Total visitor arrivals"

    room_revenue = overall_hotels[overall_hotels["metric"] == "Room Revenue"][
        ["date", "year", "month", "value"]
    ].copy()
    revenue_baseline = hotels[
        (hotels["metric"] == "Room Revenue")
        & (hotels["segment"] == "All gazetted hotels")
        & (hotels["year"] == BASELINE_YEAR)
    ][["month", "value"]].rename(columns={"value": "baseline"})
    room_revenue = room_revenue.merge(revenue_baseline, on="month", how="left")
    room_revenue["value"] = (
        room_revenue["value"]
        .div(room_revenue["baseline"].where(room_revenue["baseline"] > 0))
        * 100
    )
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
        color_discrete_sequence=["#2563EB", "#0F766E"],
    )
    comparison_figure.add_hline(y=100, line_dash="dash", line_color="#374151")
    add_phase_shading(comparison_figure)
    polish_figure(comparison_figure)
    st.plotly_chart(comparison_figure, width="stretch")

    merged_monthly = total_arrivals[["date", "arrivals"]].merge(
        room_revenue[["date", "value"]].rename(columns={"value": "revenue_index"}),
        on="date",
        how="inner",
    )
    monthly_correlation = merged_monthly["arrivals"].corr(
        merged_monthly["revenue_index"]
    )
    st.metric(
        "Descriptive monthly correlation",
        f"{monthly_correlation:.2f}",
        help="Pearson correlation for the selected year range.",
    )
    st.warning(
        "A high correlation means the two series often moved together; it does not show "
        "that one caused the other. Prices, inflation, room supply, business travel, "
        "staycations and major events are plausible additional explanations."
    )

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

    st.subheader("How the story is measured")
    st.markdown(
        "- **Monthly recovery index:** current month divided by the matching month in 2019.\n"
        "- **Annual market recovery:** 2025 annual arrivals divided by 2019 annual arrivals.\n"
        f"- **Major market ranking:** limited to the {MAJOR_MARKET_COUNT} largest markets in 2019.\n"
        "- **Visitor share:** a market's arrivals divided by arrivals from all country markets.\n"
        "- **Descriptive correlation:** shows co-movement, not causation."
    )

    st.subheader("Analytical phases")
    st.markdown(
        "- **2019 baseline:** pre-disruption comparison year.\n"
        "- **2020-2021 pandemic shock:** exceptional collapse in international arrivals.\n"
        "- **2022 reopening:** initial return of cross-border travel.\n"
        "- **2023-2025 recovery:** continued recovery and changing source-market mix."
    )

    st.subheader("Limitations")
    st.markdown(
        "- Source market means place of residence, not citizenship.\n"
        "- Aggregated monthly data cannot identify individual behaviour or establish causality.\n"
        "- Hotel statistics cover gazetted hotels rather than every accommodation provider.\n"
        "- Room rates and revenue are nominal and are not adjusted for inflation.\n"
        "- Results can also reflect border policy, flight capacity, exchange rates and events."
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
