-- 04_business_questions.sql
-- Global Risk Advisory: the three business questions

-- ============================================================
-- Q1. Which regions are rising vs declining (2013 -> 2017)?
-- The trend label uses RAW attacks and deaths, because the risk score is relative
-- to other countries each year and can rise even when attacks fall.
-- ============================================================
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
ORDER BY killed_pct_change DESC NULLS LAST;

-- ============================================================
-- Q2. Which attack types kill more than their frequency suggests?
-- disproportion_ratio = share of deaths / share of attacks (above 1 = deadlier than frequent)
-- ============================================================
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
ORDER BY disproportion_ratio DESC;

-- ============================================================
-- Q3. Which countries are volatile and which are steady (2008-2017)?
-- Years with no attacks have no row, so they are filled with a score of 0.
-- volatility_ratio = standard deviation / average. Labels use the median of the top 20.
-- ============================================================
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
ORDER BY avg_risk DESC;
