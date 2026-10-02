"""
Smart City Traffic & Accident Analytics — ETL Pipeline
=======================================================
Run this in VS Code (python etl_pipeline.py).

What it does (Extract -> Transform -> Load):
  1. EXTRACT   : reads the two raw CSVs (sensor + accident data)
  2. TRANSFORM : cleans data, engineers metrics (Congestion_Index,
                 Accident_Severity_Score), builds a star-schema
                 (dimension + fact tables)
  3. LOAD      : writes the star schema into a SQLite data warehouse
                 (smart_city_dw.db) AND exports each table as a CSV
                 into /powerbi_exports so Power BI can import them
                 directly (Get Data -> Text/CSV, or Get Data -> SQLite).

Folder layout expected:
    data/road_traffic_sensor_data.csv
    data/traffic_accident_data.csv
    sql/                (DDL lives here, this script also creates tables)
    powerbi_exports/    (flat, Power-BI-ready CSVs land here)
"""

import os
import sqlite3
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORT_DIR = os.path.join(BASE_DIR, "powerbi_exports")
DB_PATH = os.path.join(BASE_DIR, "smart_city_dw.db")

TRAFFIC_CSV = os.path.join(DATA_DIR, "road_traffic_sensor_data.csv")
ACCIDENT_CSV = os.path.join(DATA_DIR, "traffic_accident_data.csv")

os.makedirs(EXPORT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. EXTRACT
# ---------------------------------------------------------------------------
def extract():
    traffic = pd.read_csv(TRAFFIC_CSV, parse_dates=["Date_Time"])
    accidents = pd.read_csv(ACCIDENT_CSV, parse_dates=["Date_Time"])
    print(f"[EXTRACT] traffic rows: {len(traffic)} | accident rows: {len(accidents)}")
    return traffic, accidents


# ---------------------------------------------------------------------------
# 2. TRANSFORM
# ---------------------------------------------------------------------------
def clean_common(df: pd.DataFrame) -> pd.DataFrame:
    """Generic cleaning: dedupe, trim strings, drop null keys."""
    df = df.drop_duplicates()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].str.strip()
    df = df.dropna(how="all")
    return df


def engineer_congestion_index(traffic: pd.DataFrame) -> pd.DataFrame:
    
    vc_norm = (traffic["Vehicle_Count"] - traffic["Vehicle_Count"].min()) / (
        traffic["Vehicle_Count"].max() - traffic["Vehicle_Count"].min()
    )
    speed_norm_inv = 1 - (traffic["Average_Speed"] - traffic["Average_Speed"].min()) / (
        traffic["Average_Speed"].max() - traffic["Average_Speed"].min()
    )
    traffic["Congestion_Index"] = ((0.5 * vc_norm + 0.5 * speed_norm_inv) * 100).round(2)
    return traffic


def engineer_severity_score(accidents: pd.DataFrame) -> pd.DataFrame:
    severity_map = {"Minor": 2, "Moderate": 5, "Severe": 7, "Fatal": 10}
    base = accidents["Accident_Severity"].map(severity_map)
    casualty_bonus = accidents["Casualties"].clip(upper=10) * 0.3
    vehicle_bonus = accidents["Number_of_Vehicles"].clip(upper=5) * 0.2
    score = base + casualty_bonus + vehicle_bonus
    accidents["Accident_Severity_Score"] = score.clip(upper=10).round(2)
    return accidents


def add_date_parts(df: pd.DataFrame, dt_col="Date_Time") -> pd.DataFrame:
    df["Date"] = df[dt_col].dt.date
    df["Year"] = df[dt_col].dt.year
    df["Month"] = df[dt_col].dt.month
    df["Day"] = df[dt_col].dt.day
    df["Hour"] = df[dt_col].dt.hour
    df["Day_Of_Week"] = df[dt_col].dt.day_name()
    df["Is_Weekend"] = df[dt_col].dt.dayofweek >= 5
    df["Is_Peak_Hour"] = df["Hour"].isin([7, 8, 9, 17, 18, 19, 20])
    return df


def transform(traffic_raw: pd.DataFrame, accidents_raw: pd.DataFrame):
    traffic = clean_common(traffic_raw.copy())
    accidents = clean_common(accidents_raw.copy())

    traffic = engineer_congestion_index(traffic)
    accidents = engineer_severity_score(accidents)

    traffic = add_date_parts(traffic)
    accidents = add_date_parts(accidents)

    # ---- Build dimension tables (shared across both facts) ----
    all_locations = pd.Index(traffic["Location"]).append(pd.Index(accidents["Location"])).unique()
    dim_location = pd.DataFrame({"Location_ID": range(1, len(all_locations) + 1), "Location_Name": all_locations})

    all_dates = pd.Index(traffic["Date"]).append(pd.Index(accidents["Date"])).unique().sort_values()
    dim_date = pd.DataFrame({"Date_ID": range(1, len(all_dates) + 1), "Date": all_dates})
    dim_date["Date"] = pd.to_datetime(dim_date["Date"])
    dim_date["Year"] = dim_date["Date"].dt.year
    dim_date["Month"] = dim_date["Date"].dt.month
    dim_date["Month_Name"] = dim_date["Date"].dt.month_name()
    dim_date["Day"] = dim_date["Date"].dt.day
    dim_date["Day_Of_Week"] = dim_date["Date"].dt.day_name()
    dim_date["Is_Weekend"] = dim_date["Date"].dt.dayofweek >= 5

    dim_weather = pd.DataFrame(
        {"Weather_ID": range(1, accidents["Weather_Condition"].nunique() + 1),
         "Weather_Condition": accidents["Weather_Condition"].unique()}
    )
    dim_road_condition = pd.DataFrame(
        {"Road_Condition_ID": range(1, accidents["Road_Condition"].nunique() + 1),
         "Road_Condition": accidents["Road_Condition"].unique()}
    )
    dim_vehicle_type = pd.DataFrame(
        {"Vehicle_Type_ID": range(1, accidents["Vehicle_Type"].nunique() + 1),
         "Vehicle_Type": accidents["Vehicle_Type"].unique()}
    )

    # ---- Map fact tables to dimension keys ----
    loc_map = dict(zip(dim_location["Location_Name"], dim_location["Location_ID"]))
    date_map = dict(zip(dim_date["Date"].dt.date, dim_date["Date_ID"]))
    weather_map = dict(zip(dim_weather["Weather_Condition"], dim_weather["Weather_ID"]))
    road_map = dict(zip(dim_road_condition["Road_Condition"], dim_road_condition["Road_Condition_ID"]))
    vtype_map = dict(zip(dim_vehicle_type["Vehicle_Type"], dim_vehicle_type["Vehicle_Type_ID"]))

    fact_traffic = pd.DataFrame({
        "Sensor_Reading_ID": range(1, len(traffic) + 1),
        "Sensor_ID": traffic["Sensor_ID"],
        "Location_ID": traffic["Location"].map(loc_map),
        "Date_ID": traffic["Date"].map(date_map),
        "Date_Time": traffic["Date_Time"],
        "Hour": traffic["Hour"],
        "Is_Peak_Hour": traffic["Is_Peak_Hour"],
        "Vehicle_Count": traffic["Vehicle_Count"],
        "Average_Speed": traffic["Average_Speed"],
        "Congestion_Level": traffic["Congestion_Level"],
        "Congestion_Index": traffic["Congestion_Index"],
    })

    fact_accidents = pd.DataFrame({
        "Accident_ID": accidents["Accident_ID"],
        "Location_ID": accidents["Location"].map(loc_map),
        "Date_ID": accidents["Date"].map(date_map),
        "Date_Time": accidents["Date_Time"],
        "Hour": accidents["Hour"],
        "Is_Peak_Hour": accidents["Is_Peak_Hour"],
        "Weather_ID": accidents["Weather_Condition"].map(weather_map),
        "Road_Condition_ID": accidents["Road_Condition"].map(road_map),
        "Vehicle_Type_ID": accidents["Vehicle_Type"].map(vtype_map),
        "Accident_Severity": accidents["Accident_Severity"],
        "Accident_Severity_Score": accidents["Accident_Severity_Score"],
        "Number_of_Vehicles": accidents["Number_of_Vehicles"],
        "Casualties": accidents["Casualties"],
        "Traffic_Density": accidents["Traffic_Density"],
    })

    print(f"[TRANSFORM] dim_location={len(dim_location)} dim_date={len(dim_date)} "
          f"dim_weather={len(dim_weather)} dim_road_condition={len(dim_road_condition)} "
          f"dim_vehicle_type={len(dim_vehicle_type)}")
    print(f"[TRANSFORM] fact_traffic={len(fact_traffic)} fact_accidents={len(fact_accidents)}")

    tables = {
        "dim_location": dim_location,
        "dim_date": dim_date,
        "dim_weather": dim_weather,
        "dim_road_condition": dim_road_condition,
        "dim_vehicle_type": dim_vehicle_type,
        "fact_traffic": fact_traffic,
        "fact_accidents": fact_accidents,
    }
    tables.update(build_linking_tables(fact_traffic, fact_accidents, dim_location, dim_date))
    return tables



# ---------------------------------------------------------------------------
# 2b. LINKING / DASHBOARD-SUPPORT TABLES
#     The sensor data (Jan 1-13) and accident data (Jan-Jul) do not overlap
#     in time, so they are linked through CONFORMED dimensions that both
#     facts share: dim_location and dim_hour. fact_location_hour pre-joins
#     both datasets at the Location x Hour grain.
# ---------------------------------------------------------------------------
def build_linking_tables(fact_traffic, fact_accidents, dim_location, dim_date):
    # --- dim_hour: shared by both facts (the hour-of-day bridge) ---
    def period(h):
        if h in (7, 8, 9): return "Morning Peak"
        if h in (17, 18, 19, 20): return "Evening Peak"
        if 10 <= h <= 16: return "Midday"
        if 21 <= h <= 23: return "Late Evening"
        return "Night"
    period_order = {"Night": 1, "Morning Peak": 2, "Midday": 3, "Evening Peak": 4, "Late Evening": 5}
    dim_hour = pd.DataFrame({"Hour": range(24)})
    dim_hour["Hour_Label"] = dim_hour["Hour"].apply(lambda h: f"{h:02d}:00")
    dim_hour["Time_Period"] = dim_hour["Hour"].apply(period)
    dim_hour["Time_Period_Sort"] = dim_hour["Time_Period"].map(period_order)
    dim_hour["Is_Peak_Hour"] = dim_hour["Time_Period"].isin(["Morning Peak", "Evening Peak"])

    # --- sort-order dimensions (so Low/Moderate/High etc. sort logically) ---
    dim_congestion_level = pd.DataFrame({"Congestion_Level": ["Low", "Moderate", "High"],
                                         "Congestion_Sort": [1, 2, 3]})
    dim_severity = pd.DataFrame({"Accident_Severity": ["Minor", "Moderate", "Severe", "Fatal"],
                                 "Severity_Sort": [1, 2, 3, 4],
                                 "Is_High_Risk": [False, False, True, True]})
    dim_traffic_density = pd.DataFrame({"Traffic_Density": ["Low", "Moderate", "High"],
                                        "Density_Sort": [1, 2, 3]})

    # --- extra date columns for correct sorting / trends ---
    dim_date["Day_Of_Week_Num"] = dim_date["Date"].dt.dayofweek + 1
    dim_date["Month_Year"] = dim_date["Date"].dt.strftime("%b %Y")
    dim_date["Week_Start"] = (dim_date["Date"] - pd.to_timedelta(dim_date["Date"].dt.dayofweek, unit="D")).dt.date

    # --- Location x Hour bridge: BOTH datasets at one grain ---
    tr = fact_traffic.groupby(["Location_ID", "Hour"]).agg(
        Sensor_Readings=("Sensor_Reading_ID", "count"),
        Avg_Vehicle_Count=("Vehicle_Count", "mean"),
        Avg_Speed=("Average_Speed", "mean"),
        Avg_Congestion_Index=("Congestion_Index", "mean")).reset_index()
    ac = fact_accidents.assign(High=fact_accidents["Accident_Severity"].isin(["Severe", "Fatal"]).astype(int)) \
        .groupby(["Location_ID", "Hour"]).agg(
        Accident_Count=("Accident_ID", "count"),
        Total_Casualties=("Casualties", "sum"),
        Avg_Severity_Score=("Accident_Severity_Score", "mean"),
        High_Risk_Accidents=("High", "sum")).reset_index()
    grid = pd.MultiIndex.from_product([dim_location["Location_ID"], range(24)],
                                      names=["Location_ID", "Hour"]).to_frame(index=False)
    lh = grid.merge(tr, how="left", on=["Location_ID", "Hour"]).merge(ac, how="left", on=["Location_ID", "Hour"])
    lh["High_Risk_Rate"] = (lh["High_Risk_Accidents"] / lh["Accident_Count"]).round(4)

    # --- Historical Risk Score (0-100): descriptive, NOT predictive. ---
    # 40% accident frequency + 30% avg severity + 30% congestion (min-max scaled)
    def mm(x): return (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else x * 0
    lh["Historical_Risk_Score"] = ((0.4 * mm(lh["Accident_Count"].fillna(0)) +
                                    0.3 * mm(lh["Avg_Severity_Score"].fillna(0)) +
                                    0.3 * mm(lh["Avg_Congestion_Index"].fillna(0))) * 100).round(1)
    lh["Risk_Band"] = pd.cut(lh["Historical_Risk_Score"], [-1, 33, 66, 100], labels=["Low", "Medium", "High"])
    for c in ["Avg_Vehicle_Count", "Avg_Speed", "Avg_Congestion_Index", "Avg_Severity_Score"]:
        lh[c] = lh[c].round(2)

    # --- Field-parameter table: lets viewers switch a chart's metric ---
    metric_switch = pd.DataFrame({
        "Metric": ["Avg Vehicle Count", "Avg Speed", "Avg Congestion Index"],
        "Metric_Order": [0, 1, 2]})

    return {"dim_hour": dim_hour, "dim_congestion_level": dim_congestion_level,
            "dim_severity": dim_severity, "dim_traffic_density": dim_traffic_density,
            "fact_location_hour": lh, "metric_switch": metric_switch, "dim_date": dim_date}

# ---------------------------------------------------------------------------
# 3. LOAD
# ---------------------------------------------------------------------------
def load(tables: dict):
    # --- SQLite warehouse ---
    conn = sqlite3.connect(DB_PATH)
    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    print(f"[LOAD] warehouse written -> {DB_PATH}")

    # --- Flat CSVs for Power BI ---
    for name, df in tables.items():
        out_path = os.path.join(EXPORT_DIR, f"{name}.csv")
        df.to_csv(out_path, index=False)
    print(f"[LOAD] Power BI-ready CSVs written -> {EXPORT_DIR}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    traffic_raw, accidents_raw = extract()
    tables = transform(traffic_raw, accidents_raw)
    load(tables)
    print("\n✅ ETL complete. Warehouse: smart_city_dw.db | Power BI CSVs: /powerbi_exports")
