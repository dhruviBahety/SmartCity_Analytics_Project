-- ============================================================
-- Smart City Traffic & Accident Analytics — Data Warehouse DDL
-- Star Schema: 5 dimensions + 2 fact tables
-- Written for SQLite (etl_pipeline.py creates these automatically);
-- syntax is near-identical for SQL Server / Postgres / MySQL —
-- swap AUTOINCREMENT / TEXT / INTEGER for your engine's equivalents.
-- ============================================================

-- ---------- DIMENSION TABLES ----------

CREATE TABLE IF NOT EXISTS dim_location (
    Location_ID    INTEGER PRIMARY KEY,
    Location_Name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_date (
    Date_ID        INTEGER PRIMARY KEY,
    Date           DATE NOT NULL UNIQUE,
    Year           INTEGER,
    Month          INTEGER,
    Month_Name     TEXT,
    Day            INTEGER,
    Day_Of_Week    TEXT,
    Is_Weekend     BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_weather (
    Weather_ID        INTEGER PRIMARY KEY,
    Weather_Condition TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_road_condition (
    Road_Condition_ID INTEGER PRIMARY KEY,
    Road_Condition    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_vehicle_type (
    Vehicle_Type_ID INTEGER PRIMARY KEY,
    Vehicle_Type    TEXT NOT NULL UNIQUE
);

-- ---------- FACT TABLES ----------

-- Grain: one row per sensor reading (one sensor, one hour)
CREATE TABLE IF NOT EXISTS fact_traffic (
    Sensor_Reading_ID INTEGER PRIMARY KEY,
    Sensor_ID         TEXT,
    Location_ID       INTEGER REFERENCES dim_location(Location_ID),
    Date_ID           INTEGER REFERENCES dim_date(Date_ID),
    Date_Time         DATETIME,
    Hour              INTEGER,
    Is_Peak_Hour      BOOLEAN,
    Vehicle_Count     INTEGER,
    Average_Speed     INTEGER,
    Congestion_Level  TEXT,       -- Low / Moderate / High (source label)
    Congestion_Index  REAL        -- engineered 0-100 continuous KPI
);

-- Grain: one row per reported accident
CREATE TABLE IF NOT EXISTS fact_accidents (
    Accident_ID              TEXT PRIMARY KEY,
    Location_ID               INTEGER REFERENCES dim_location(Location_ID),
    Date_ID                    INTEGER REFERENCES dim_date(Date_ID),
    Date_Time                  DATETIME,
    Hour                       INTEGER,
    Is_Peak_Hour               BOOLEAN,
    Weather_ID                 INTEGER REFERENCES dim_weather(Weather_ID),
    Road_Condition_ID          INTEGER REFERENCES dim_road_condition(Road_Condition_ID),
    Vehicle_Type_ID            INTEGER REFERENCES dim_vehicle_type(Vehicle_Type_ID),
    Accident_Severity          TEXT,   -- Minor / Moderate / Severe / Fatal (source label)
    Accident_Severity_Score    REAL,   -- engineered 1-10 continuous KPI
    Number_of_Vehicles         INTEGER,
    Casualties                 INTEGER,
    Traffic_Density            TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_traffic_loc  ON fact_traffic(Location_ID);
CREATE INDEX IF NOT EXISTS idx_fact_traffic_date ON fact_traffic(Date_ID);
CREATE INDEX IF NOT EXISTS idx_fact_accidents_loc  ON fact_accidents(Location_ID);
CREATE INDEX IF NOT EXISTS idx_fact_accidents_date ON fact_accidents(Date_ID);
