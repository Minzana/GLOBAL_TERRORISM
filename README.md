# Global Risk Advisory: Terrorism Risk Scoring (1970–2017)

**Tools:** PostgreSQL · SQL (CTEs, window functions) · Python (pandas, NumPy, SQLAlchemy, matplotlib) · Power BI
**Data:** Global Terrorism Database (GTD), 181,691 incidents, 205 countries, 1970–2017

## Executive summary

**Question:** Where is terrorism risk rising or falling, which attack types cause the most harm for their frequency, and which countries are steady versus unpredictable?

**Key findings**

1. **Sub-Saharan Africa is the clearest rising region (2013 → 2017).** Attacks rose 97% (999 → 1,970) and deaths rose 74% (3,857 → 6,712).
2. **Several regions saw fewer but deadlier attacks.** In the Middle East & North Africa and in South Asia, attacks fell 17% and 26%, yet deaths rose 6% and 8%. A count of attacks alone would have missed this.
3. **Some attack types are far deadlier than their frequency suggests.** Hijackings account for 0.4% of attacks but 0.9% of deaths (about 2.5× their share). Armed assaults are 1.7×. Bombings are the most common type (48.6% of attacks) but cause a smaller share of deaths (38.2%).
4. **Iraq is both the highest-risk and the steadiest country** (average risk 0.81 over 2008–2017, low year-to-year variation). South Sudan, Chad and Egypt have much lower average risk but swing sharply from year to year, which makes them harder to plan for.

**Recommendations**

1. Prioritise monitoring in Sub-Saharan Africa, and track deaths per attack alongside attack counts in the Middle East and South Asia.
2. Treat persistently high-risk countries (Iraq) and volatile countries (South Sudan, Chad) differently: fixed mitigation for the first, scenario planning for the second.

## Method

**Risk score** = 0.4 × normalized incident count + 0.4 × normalized fatalities + 0.2 × normalized attack severity (deaths per attack), calculated per country per year.

- Each signal is min-max normalized to 0–1 **within its own year**, so the score is a country's position relative to every other country that year.
- Incident count and fatalities carry the most weight (0.4 each) because they are the most stable, large-sample signals. Severity is a ratio that can swing on small denominators (a country with 6 attacks), so it carries 0.2.
- The weights are a starting assumption, not a fixed law, and can be changed in one place in the SQL.

**Pipeline**

1. `staging_raw`: raw CSV loaded with all 135 columns as TEXT, as a lossless safety copy.
2. `incidents_clean`: typed columns, defensive de-duplication on `eventid`, unknown casualty counts kept as NULL.
3. `country_year_metrics`: one row per country per year, with a flag (`had_unknown_deaths`) for country-years where deaths were never recorded.
4. `risk_score_country_year`: the normalized and weighted score.
5. Three business-question queries (region trend, attack-type disproportion, volatility).
6. Python: linear-regression outlook for the top 10 countries, with a backtest.
7. Power BI report built on the exported tables.

## Forecast: lightweight and honestly evaluated

A linear regression on 2008–2017 scores projects 2018 for the 10 highest-risk countries (Afghanistan, Nigeria, Syria and Yemen trend up; Pakistan, India and DR Congo trend down; Iraq stays very high and stable).

**Backtest:** trained on 2008–2016 and predicted 2017. Average error was 0.082 for the regression versus 0.074 for simply repeating the previous year's score. The model does **not** clearly beat the naive baseline, so the forecast is a directional outlook, not a precise prediction.

## Limitations

- **1993 is missing** from the GTD because of a data loss at the source. A dip in 1993 is not a real drop in attacks.
- **Unknown casualty counts** (5.7% of incidents for deaths, 9% for wounded) are kept as NULL in the clean table. In the risk score they count as 0, which can understate risk where reporting is poor. The `had_unknown_deaths` flag keeps this visible.
- **Scores are relative within each year.** A year-over-year change in a region's score can come from the leading country changing, not only from the region itself, so trends are always checked against raw attack and death counts.
- **A region's score is the average of its countries' scores,** counting only countries with at least one attack that year.
- **Wounded people are not in the score;** severity uses deaths only.
- **Historical states** (Yugoslavia, USSR, East/West Germany and others) are kept under their historical names and do not appear on a modern map.
- The data ends in 2017.

## What I would do with more time

- Add economic and political indicators (GDP, conflict data, governance scores) as predictors.
- Replace the linear model with a time-series model (for example ARIMA) and compare it against the baseline.
- Test how sensitive the rankings are to different weights.
- Score regions directly, instead of averaging country scores.

## Data

The raw GTD file is not included in this repository (it is over 100 MB and is distributed by its owners). Download it from the START Global Terrorism Database website (https://www.start.umd.edu/gtd/) and save it as `globalterrorism.csv`.

## How to reproduce

1. Run `sql/01_staging.sql`, then import `globalterrorism.csv` into `staging_raw` (expect 181,691 rows).
2. Run `sql/02_clean_and_metrics.sql`, then `sql/03_risk_score.sql`, then `sql/04_business_questions.sql`.
3. `pip install -r requirements.txt`, set the database settings at the top of `forecast_risk.py` and `export_for_powerbi.py`, then run both scripts.

## Files

| File | Purpose |
|---|---|
| `sql/01_staging.sql` | Raw staging table (135 TEXT columns) |
| `sql/02_clean_and_metrics.sql` | Cleaning, typed table, country-year summary |
| `sql/03_risk_score.sql` | Weighted risk score |
| `sql/04_business_questions.sql` | Region trend, attack-type disproportion, volatility |
| `forecast_risk.py` | Reads the risk table from PostgreSQL, forecasts 2018, runs the backtest |
| `export_for_powerbi.py` | Exports the SQL results to CSV for Power BI |
| `output/` | CSV files and forecast chart |
| `powerbi/` | Power BI report (`.pbix`), PDF export and page screenshots |
