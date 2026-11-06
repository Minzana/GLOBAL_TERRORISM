-- 02_clean_and_metrics.sql
-- Global Risk Advisory: cleaning and country-year summary
--
-- Decisions (documented for the README / interviews):
--   * Duplicates: DISTINCT ON (eventid) is a defensive safety net. This export has
--     0 duplicate event IDs, but a future GTD update might.
--   * Unknown casualties: empty nkill / nwound stay NULL (NULLIF). They are NOT turned into 0
--     in the clean table, because "unknown" is not the same as "nobody was hurt".
--   * Month / day = 0 means "unknown" in GTD, so they become NULL.
--   * Historical country names (Yugoslavia, USSR, ...) are kept as they were at the time.
--   * 1993 is missing from the GTD itself (a data loss at the source).

-- ---------- incidents_clean: typed columns, only what the analysis needs ----------
DROP TABLE IF EXISTS incidents_clean;

CREATE TABLE incidents_clean (
    eventid          BIGINT,
    iyear            INT,
    imonth           INT,
    iday             INT,
    country_txt      TEXT,
    region_txt       TEXT,
    attacktype1_txt  TEXT,
    targtype1_txt    TEXT,
    weaptype1_txt    TEXT,
    nkill            NUMERIC,
    nwound           NUMERIC
);

INSERT INTO incidents_clean
    (eventid, iyear, imonth, iday, country_txt, region_txt,
     attacktype1_txt, targtype1_txt, weaptype1_txt, nkill, nwound)
SELECT DISTINCT ON (eventid)
    eventid::BIGINT,
    iyear::INT,
    NULLIF(imonth, '0')::INT,
    NULLIF(iday, '0')::INT,
    country_txt,
    region_txt,
    attacktype1_txt,
    targtype1_txt,
    weaptype1_txt,
    NULLIF(nkill, '')::NUMERIC,
    NULLIF(nwound, '')::NUMERIC
FROM staging_raw
ORDER BY eventid;

-- Check: expect 181691
-- SELECT COUNT(*), COUNT(DISTINCT eventid) FROM incidents_clean;

-- ---------- country_year_metrics: one row per country per year ----------
DROP TABLE IF EXISTS country_year_metrics;

CREATE TABLE country_year_metrics AS
SELECT
    country_txt,
    region_txt,
    iyear,
    COUNT(*)      AS incident_count,
    SUM(nkill)    AS total_killed,
    SUM(nwound)   AS total_wounded
FROM incidents_clean
GROUP BY country_txt, region_txt, iyear;

-- Flag country-years where no attack had a recorded death count.
-- For scoring these are treated as 0, but the flag keeps that assumption visible.
ALTER TABLE country_year_metrics ADD COLUMN had_unknown_deaths BOOLEAN;

UPDATE country_year_metrics
SET had_unknown_deaths = (total_killed IS NULL);

-- Check: expect 3762 rows, 46 flagged TRUE
-- SELECT had_unknown_deaths, COUNT(*) FROM country_year_metrics GROUP BY 1;
