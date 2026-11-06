
import os

import matplotlib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

matplotlib.use("Agg")
import matplotlib.pyplot as plt
DB_USER = "postgres"
DB_PASSWORD = "pass"
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "Global_Terrorism"
# -------------------------------------------------------------

TRAIN_START = 2008   # last 10 years of data
LAST_YEAR = 2017     # the dataset ends in 2017
FORECAST_YEAR = LAST_YEAR + 1
TOP_N = 10
TREND_THRESHOLD = 0.01  # change in score per year needed to call a trend "Rising"/"Falling"
OUT_DIR = "output"

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- 1. Read the table from PostgreSQL ----------
url = URL.create(
    "postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)
engine = create_engine(url)
df = pd.read_sql(
    "SELECT country_txt, region_txt, iyear, incident_count, total_killed, "
    "had_unknown_deaths, norm_incidents, norm_fatalities, norm_severity, risk_score "
    "FROM risk_score_country_year",
    engine,
)
print(f"Loaded {len(df)} country-year rows")

# Full table for the Power BI report
df.to_csv(os.path.join(OUT_DIR, "risk_score_country_year.csv"), index=False)

# ---------- 2. Build a country x year grid for the last 10 years ----------
years = np.arange(TRAIN_START, LAST_YEAR + 1)
recent = df[(df.iyear >= TRAIN_START) & (df.iyear <= LAST_YEAR)]

wide = (
    recent.pivot_table(index="country_txt", columns="iyear", values="risk_score", aggfunc="sum")
    .reindex(columns=years)
    .fillna(0.0)  # a year with no attacks has no row in the table, so its score is 0
)
region_of = recent.drop_duplicates("country_txt").set_index("country_txt")["region_txt"]

top_countries = wide.mean(axis=1).sort_values(ascending=False).head(TOP_N).index


# ---------- 3. Linear regression forecast ----------
def fit_and_predict(y, x_train, x_next):
    """Fit y = slope * year + intercept, return (prediction clipped to 0-1, slope)."""
    slope, intercept = np.polyfit(x_train, y, 1)
    return float(np.clip(slope * x_next + intercept, 0.0, 1.0)), float(slope)


rows = []
for country in top_countries:
    y = wide.loc[country].values

    forecast, slope = fit_and_predict(y, years, FORECAST_YEAR)

    # Backtest: train without the final year, then predict it
    backtest_pred, _ = fit_and_predict(y[:-1], years[:-1], LAST_YEAR)
    naive_pred = y[-2]  # "same as the year before"

    if slope > TREND_THRESHOLD:
        outlook = "Rising"
    elif slope < -TREND_THRESHOLD:
        outlook = "Falling"
    else:
        outlook = "Stable"

    rows.append(
        {
            "country": country,
            "region": region_of.get(country),
            "avg_risk_2008_2017": round(y.mean(), 3),
            f"actual_{LAST_YEAR}": round(y[-1], 3),
            f"forecast_{FORECAST_YEAR}": round(forecast, 3),
            "slope_per_year": round(slope, 4),
            "outlook": outlook,
            "backtest_abs_error_linear": round(abs(backtest_pred - y[-1]), 3),
            "backtest_abs_error_naive": round(abs(naive_pred - y[-1]), 3),
        }
    )

result = pd.DataFrame(rows)
result.to_csv(os.path.join(OUT_DIR, "forecast_top10.csv"), index=False)

# Long format (actual + forecast) - easy to use as a line chart in Power BI
history = wide.loc[top_countries].reset_index().melt(
    id_vars="country_txt", var_name="year", value_name="risk_score"
)
history["type"] = "Actual"
future = pd.DataFrame(
    {
        "country_txt": result["country"],
        "year": FORECAST_YEAR,
        "risk_score": result[f"forecast_{FORECAST_YEAR}"],
        "type": "Forecast",
    }
)
pd.concat([history, future]).to_csv(os.path.join(OUT_DIR, "forecast_history_top10.csv"), index=False)

# ---------- 4. Chart ----------
fig, axes = plt.subplots(2, 5, figsize=(18, 7), sharex=True)
for ax, country in zip(axes.flat, top_countries):
    y = wide.loc[country].values
    ax.plot(years, y, marker="o", color="#2F5496", label="Actual")
    f = result.loc[result.country == country, f"forecast_{FORECAST_YEAR}"].iloc[0]
    ax.plot([LAST_YEAR, FORECAST_YEAR], [y[-1], f], linestyle="--", marker="o", color="#C00000", label="Forecast")
    ax.set_title(country, fontsize=10)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
axes.flat[0].legend(fontsize=8)
fig.suptitle(f"Risk score 2008-{LAST_YEAR} and linear forecast for {FORECAST_YEAR} (top {TOP_N} countries)")
fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "forecast_chart.png"), dpi=150)

# ---------- 5. Print results and the honest backtest summary ----------
print()
print(result.to_string(index=False))
print()
mae_lin = result["backtest_abs_error_linear"].mean()
mae_naive = result["backtest_abs_error_naive"].mean()
print(f"Backtest (predicting {LAST_YEAR}): linear regression avg error = {mae_lin:.3f}, "
      f"'same as last year' avg error = {mae_naive:.3f}")
print("Files saved in the 'output' folder.")
