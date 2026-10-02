-- ============================================================
-- Smart City Traffic & Accident Analytics — Analysis Queries
-- Run against smart_city_dw.db (or point Power BI's SQL connector here)
-- ============================================================

-- 1) Average vehicle flow & speed by location
SELECT
    l.Location_Name,
    ROUND(AVG(f.Vehicle_Count), 1)  AS Avg_Vehicle_Count,
    ROUND(AVG(f.Average_Speed), 1)  AS Avg_Speed,
    ROUND(AVG(f.Congestion_Index), 1) AS Avg_Congestion_Index
FROM fact_traffic f
JOIN dim_location l ON f.Location_ID = l.Location_ID
GROUP BY l.Location_Name
ORDER BY Avg_Congestion_Index DESC;

-- 2) Congestion level distribution by location
SELECT
    l.Location_Name,
    f.Congestion_Level,
    COUNT(*) AS Readings
FROM fact_traffic f
JOIN dim_location l ON f.Location_ID = l.Location_ID
GROUP BY l.Location_Name, f.Congestion_Level
ORDER BY l.Location_Name, Readings DESC;

-- 3) Peak-hour vs off-peak congestion comparison
SELECT
    CASE WHEN f.Is_Peak_Hour = 1 THEN 'Peak Hour' ELSE 'Off-Peak' END AS Period,
    ROUND(AVG(f.Vehicle_Count), 1)    AS Avg_Vehicle_Count,
    ROUND(AVG(f.Average_Speed), 1)    AS Avg_Speed,
    ROUND(AVG(f.Congestion_Index), 1) AS Avg_Congestion_Index
FROM fact_traffic f
GROUP BY Period;

-- 4) Hourly traffic pattern (congestion by hour of day, all locations)
SELECT
    f.Hour,
    ROUND(AVG(f.Vehicle_Count), 1)    AS Avg_Vehicle_Count,
    ROUND(AVG(f.Congestion_Index), 1) AS Avg_Congestion_Index
FROM fact_traffic f
GROUP BY f.Hour
ORDER BY f.Hour;

-- 5) Top 10 most congested individual sensor readings ("hotspots")
SELECT
    l.Location_Name,
    f.Sensor_ID,
    f.Date_Time,
    f.Vehicle_Count,
    f.Average_Speed,
    f.Congestion_Index
FROM fact_traffic f
JOIN dim_location l ON f.Location_ID = l.Location_ID
ORDER BY f.Congestion_Index DESC
LIMIT 10;

-- 6) Accident-prone areas: accident count & avg severity by location
SELECT
    l.Location_Name,
    COUNT(*) AS Total_Accidents,
    ROUND(AVG(a.Accident_Severity_Score), 2) AS Avg_Severity_Score,
    SUM(a.Casualties) AS Total_Casualties
FROM fact_accidents a
JOIN dim_location l ON a.Location_ID = l.Location_ID
GROUP BY l.Location_Name
ORDER BY Total_Accidents DESC;

-- 7) Accident severity breakdown by weather condition
SELECT
    w.Weather_Condition,
    COUNT(*) AS Accidents,
    ROUND(AVG(a.Accident_Severity_Score), 2) AS Avg_Severity_Score
FROM fact_accidents a
JOIN dim_weather w ON a.Weather_ID = w.Weather_ID
GROUP BY w.Weather_Condition
ORDER BY Avg_Severity_Score DESC;

-- 8) Accident severity breakdown by road condition
SELECT
    r.Road_Condition,
    COUNT(*) AS Accidents,
    ROUND(AVG(a.Accident_Severity_Score), 2) AS Avg_Severity_Score
FROM fact_accidents a
JOIN dim_road_condition r ON a.Road_Condition_ID = r.Road_Condition_ID
GROUP BY r.Road_Condition
ORDER BY Avg_Severity_Score DESC;

-- 9) Accidents by hour of day (peak-hour risk pattern)
SELECT
    Hour,
    COUNT(*) AS Accidents,
    ROUND(AVG(Accident_Severity_Score), 2) AS Avg_Severity_Score
FROM fact_accidents
GROUP BY Hour
ORDER BY Hour;

-- 10) Combined risk view: locations with BOTH high congestion AND high accident severity
SELECT
    l.Location_Name,
    ROUND(t.Avg_Congestion_Index, 1) AS Avg_Congestion_Index,
    ROUND(a.Avg_Severity_Score, 2)   AS Avg_Severity_Score,
    a.Total_Accidents
FROM dim_location l
JOIN (
    SELECT Location_ID, AVG(Congestion_Index) AS Avg_Congestion_Index
    FROM fact_traffic GROUP BY Location_ID
) t ON t.Location_ID = l.Location_ID
JOIN (
    SELECT Location_ID, AVG(Accident_Severity_Score) AS Avg_Severity_Score, COUNT(*) AS Total_Accidents
    FROM fact_accidents GROUP BY Location_ID
) a ON a.Location_ID = l.Location_ID
ORDER BY Avg_Congestion_Index DESC, Avg_Severity_Score DESC;

-- 11) Vehicle type involvement in accidents
SELECT
    v.Vehicle_Type,
    COUNT(*) AS Accidents,
    ROUND(AVG(a.Casualties), 2) AS Avg_Casualties
FROM fact_accidents a
JOIN dim_vehicle_type v ON a.Vehicle_Type_ID = v.Vehicle_Type_ID
GROUP BY v.Vehicle_Type
ORDER BY Accidents DESC;

-- 12) Weekend vs weekday accident comparison
SELECT
    CASE WHEN d.Is_Weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS Period,
    COUNT(*) AS Accidents,
    ROUND(AVG(a.Accident_Severity_Score), 2) AS Avg_Severity_Score
FROM fact_accidents a
JOIN dim_date d ON a.Date_ID = d.Date_ID
GROUP BY Period;
