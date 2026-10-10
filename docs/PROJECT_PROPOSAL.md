# DS608 Group Project Proposal

## Project Title and Group Members

**Singapore Inbound Tourism and Hotel Recovery Dashboard**

- jiang minglan
- gou hongyu

## Motivation and Background

Tourism is an important part of Singapore's service economy. International travel fell sharply during the COVID-19 pandemic and later recovered at different speeds across source markets. This project will examine how visitor arrivals changed between 2019 and 2025 and whether the recovery was reflected in Singapore's hotel occupancy, room rates and room revenue.

## Research Question and Objectives

**Main research question:** How did visitor arrivals from major source markets recover relative to 2019, and how did this recovery compare with the performance of Singapore's hotel sector?

The project will:

1. Compare monthly visitor arrivals from major source markets.
2. Measure recovery against the same month in 2019.
3. Examine changes in hotel occupancy, average room rates and room revenue.
4. Present the findings through an interactive dashboard for non-technical users.

## Data Sources

The project will use two public monthly datasets from data.gov.sg:

1. **International Visitor Arrivals By Place Of Residence, Monthly**  
   Dataset ID: `d_7e7b2ee60c6ffc962f80fef129cf306e`

2. **Hotel Statistics, Monthly**  
   Dataset ID: `d_8e62605f0c1c948702b6ea0fe45242d3`

Both datasets are sourced from the Singapore Tourism Board. The analysis will use complete calendar years from January 2019 to December 2025.

## Proposed Approach

Python and pandas will be used to download, reshape and clean the data. The original datasets store months in separate columns, so the data will be converted into a tidy monthly format. The code will also convert dates and numeric values, check missing values and duplicate records, and save the processed data in `data/processed/`.

The analysis will calculate annual totals and a monthly recovery index:

`Recovery index = current monthly value / value in the same month of 2019 × 100`

The results will be presented using Plotly charts in a Streamlit dashboard.

## Dashboard Concept

The dashboard will include:

- A year-range slider from 2019 to 2025.
- A control for selecting source markets such as China, India, Indonesia, Malaysia and Australia.
- A line chart of monthly visitor arrivals.
- A chart showing recovery relative to the same month in 2019.
- Hotel occupancy and average-room-rate charts.
- A comparison of visitor-arrival recovery and hotel-room-revenue recovery.
- Key indicators and downloadable filtered data.

## Potential Challenges and Limitations

The visitor data classify markets by place of residence rather than nationality. Hotel statistics cover gazetted hotels and therefore do not represent every accommodation provider. Room rates and revenue are nominal and are not adjusted for inflation. The analysis is descriptive and cannot establish that changes in visitor arrivals caused changes in hotel performance. Tourism recovery may also be influenced by flight capacity, border policies, exchange rates and major events that are not included in the current analysis.
