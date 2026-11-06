"""
Global Risk Advisory - Export the SQL results as CSV files for Power BI

Runs the three business-question queries against PostgreSQL and saves each result
as a CSV in the 'output' folder (the same folder forecast_risk.py uses).

"""
import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ---------------- CONFIG: copy the same 5 lines from forecast_risk.py ----------------
DB_USER = "postgres"
DB_PASSWORD = "pass"
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "Global_Terrorism"
# -------------------------------------------------------------------------------------

OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

engine = create_engine(
    URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
)

QUERIES = {
    # Question 1: rising vs declining regions (risk score next to the raw numbers)
    "q1_region_trend.csv": """
        WITH score AS (
            SELECT region_txt,
                   ROUND(AVG(risk_score) FILTER (WHERE iyear = 2013), 3) AS risk_2013,
                   ROUND(AVG(risk_score) FILTER (WHERE iyear = 2017), 3) AS risk_2017
            FROM risk_score_country_year
            WHERE iyear IN (2013, 2017)
            GROUP BY region_txt
        ),
        raw_counts AS (
            SELECT region_txt,
                   SUM(incident_count) FILTER (WHERE iyear = 2013) AS attacks_2013,
                   SUM(incident_count) FILTER (WHERE iyear = 2017) AS attacks_2017,
                   SUM(total_killed)   FILTER (WHERE iyear = 2013) AS killed_2013,
                   SUM(total_killed)   FILTER (WHERE iyear = 2017) AS killed_2017
            FROM country_year_metrics
            WHERE iyear IN (2013, 2017)
            GROUP BY region_txt
        )
        SELECT s.region_txt, s.risk_2013, s.risk_2017,
               r.attacks_2013, r.attacks_2017,
               ROUND(100.0 * (r.attacks_2017 - r.attacks_2013) / NULLIF(r.attacks_2013, 0), 1) AS attacks_pct_change,
               r.killed_2013, r.killed_2017,
               ROUND(100.0 * (r.killed_2017 - r.killed_2013) / NULLIF(r.killed_2013, 0), 1) AS killed_pct_change,
               CASE
                   WHEN r.attacks_2017 > r.attacks_2013 AND r.killed_2017 > r.killed_2013 THEN 'Rising'
                   WHEN r.attacks_2017 < r.attacks_2013 AND r.killed_2017 < r.killed_2013 THEN 'Declining'
                   ELSE 'Mixed'
               END AS trend
        FROM score s
        JOIN raw_counts r ON r.region_txt = s.region_txt
        ORDER BY killed_pct_change DESC NULLS LAST
    """,
    # Question 2: attack types that kill more than their frequency suggests
    "q2_attack_types.csv": """
        WITH by_type AS (
            SELECT attacktype1_txt AS attack_type,
                   COUNT(*) AS attacks,
                   COALESCE(SUM(nkill), 0) AS total_killed
            FROM incidents_clean
            GROUP BY attacktype1_txt
        ),
        totals AS (
            SELECT SUM(attacks) AS all_attacks, SUM(total_killed) AS all_killed FROM by_type
        )
        SELECT b.attack_type, b.attacks,
               ROUND(100.0 * b.attacks / t.all_attacks, 1) AS pct_of_attacks,
               b.total_killed,
               ROUND(100.0 * b.total_killed / t.all_killed, 1) AS pct_of_deaths,
               ROUND(b.total_killed / b.attacks, 2) AS killed_per_attack,
               ROUND((b.total_killed / t.all_killed) / (b.attacks::NUMERIC / t.all_attacks), 2) AS disproportion_ratio
        FROM by_type b
        CROSS JOIN totals t
        ORDER BY disproportion_ratio DESC
    """,
    # Question 3: volatile vs steady countries, last 10 years (missing years count as 0)
    "q3_volatility.csv": """
        WITH years AS (SELECT generate_series(2008, 2017) AS iyear),
        countries AS (
            SELECT DISTINCT country_txt FROM risk_score_country_year
            WHERE iyear BETWEEN 2008 AND 2017
        ),
        grid AS (SELECT c.country_txt, y.iyear FROM countries c CROSS JOIN years y),
        filled AS (
            SELECT g.country_txt, g.iyear, COALESCE(r.risk_score, 0) AS risk_score
            FROM grid g
            LEFT JOIN risk_score_country_year r
                   ON r.country_txt = g.country_txt AND r.iyear = g.iyear
        ),
        stats AS (
            SELECT country_txt,
                   ROUND(AVG(risk_score), 3) AS avg_risk,
                   ROUND(STDDEV(risk_score), 3) AS volatility,
                   ROUND(STDDEV(risk_score) / NULLIF(AVG(risk_score), 0), 2) AS volatility_ratio
            FROM filled
            GROUP BY country_txt
        ),
        top_countries AS (SELECT * FROM stats ORDER BY avg_risk DESC LIMIT 20)
        SELECT country_txt, avg_risk, volatility, volatility_ratio,
               CASE
                   WHEN volatility_ratio >= (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY volatility_ratio) FROM top_countries)
                   THEN 'Volatile' ELSE 'Steady'
               END AS risk_pattern
        FROM top_countries
        ORDER BY avg_risk DESC
    """,
    # Yearly world totals for the Overview page trend line
    "yearly_totals.csv": """
        SELECT iyear,
               COUNT(*) AS attacks,
               COALESCE(SUM(nkill), 0) AS killed,
               COALESCE(SUM(nwound), 0) AS wounded
        FROM incidents_clean
        GROUP BY iyear
        ORDER BY iyear
    """,
}

for filename, sql in QUERIES.items():
    result = pd.read_sql(text(sql), engine)
    result.to_csv(os.path.join(OUT_DIR, filename), index=False)
    print(f"Saved {filename}: {len(result)} rows")

print("Done. All files are in the 'output' folder.")
