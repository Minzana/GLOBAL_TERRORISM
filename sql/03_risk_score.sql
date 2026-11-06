-- 03_risk_score.sql
-- Global Risk Advisory: weighted risk score per country per year
--
-- RiskScore = 0.4 * norm_incidents + 0.4 * norm_fatalities + 0.2 * norm_severity
--
--   * Each signal is min-max normalized to 0-1 WITHIN ITS OWN YEAR:
--         (value - min) / (max - min)
--     so the score is a country's position relative to every other country that year.
--     Trade-off: a year-over-year change can reflect the top country changing, so trends
--     are always checked against raw attack and death counts.
--   * Severity = deaths per attack. It is a ratio that gets noisy on small counts
--     (a country with 6 attacks), so it carries the lowest weight (0.2).
--   * Unknown deaths count as 0 via COALESCE (flagged in had_unknown_deaths).
--   * NULLIF(..., 0) guards against dividing by zero.

DROP TABLE IF EXISTS risk_score_country_year;

CREATE TABLE risk_score_country_year AS
WITH year_bounds AS (
    SELECT
        iyear,
        MIN(incident_count) AS min_inc, MAX(incident_count) AS max_inc,
        MIN(COALESCE(total_killed,0)) AS min_kill, MAX(COALESCE(total_killed,0)) AS max_kill,
        MIN(COALESCE(total_killed,0)::NUMERIC / NULLIF(incident_count,0)) AS min_sev,
        MAX(COALESCE(total_killed,0)::NUMERIC / NULLIF(incident_count,0)) AS max_sev
    FROM country_year_metrics
    GROUP BY iyear
),
scored AS (
    SELECT
        m.country_txt,
        m.region_txt,
        m.iyear,
        m.incident_count,
        m.total_killed,
        m.had_unknown_deaths,
        ROUND((m.incident_count - b.min_inc)::NUMERIC / NULLIF(b.max_inc - b.min_inc,0), 2) AS norm_incidents,
        ROUND((COALESCE(m.total_killed,0) - b.min_kill)::NUMERIC / NULLIF(b.max_kill - b.min_kill,0), 2) AS norm_fatalities,
        ROUND(
            ((COALESCE(m.total_killed,0)::NUMERIC / NULLIF(m.incident_count,0)) - b.min_sev)
            / NULLIF(b.max_sev - b.min_sev, 0)
        , 2) AS norm_severity
    FROM country_year_metrics m
    JOIN year_bounds b ON b.iyear = m.iyear
)
SELECT
    country_txt,
    region_txt,
    iyear,
    incident_count,
    total_killed,
    had_unknown_deaths,
    norm_incidents,
    norm_fatalities,
    norm_severity,
    ROUND(0.4*norm_incidents + 0.4*norm_fatalities + 0.2*norm_severity, 3) AS risk_score
FROM scored;

-- Check: expect 3762 rows
-- SELECT COUNT(*) FROM risk_score_country_year;
