import pandas as pd

# ============================================================
# 1. TRAFFIC ACCIDENT DATA
# ============================================================

accident_df = pd.read_csv("data/traffic_accident_data.csv")

print("\n" + "=" * 80)
print("TRAFFIC ACCIDENT DATA PROFILING")
print("=" * 80)

print("\n1. DESCRIPTIVE STATISTICS")
print(accident_df.describe())

print("\n2. UNIQUE LOCATIONS")
print(accident_df["Location"].unique())

print("\n3. MISSING VALUES")
print(accident_df.isna().sum())


# ============================================================
# 2. ROAD TRAFFIC SENSOR DATA
# ============================================================

sensor_df = pd.read_csv("data/road_traffic_sensor_data.csv")

print("\n" + "=" * 80)
print("ROAD TRAFFIC SENSOR DATA PROFILING")
print("=" * 80)

print("\n1. DESCRIPTIVE STATISTICS")
print(sensor_df.describe())

print("\n2. UNIQUE LOCATIONS")
print(sensor_df["Location"].unique())

print("\n3. MISSING VALUES")
print(sensor_df.isna().sum())


print("\n" + "=" * 80)
print("ALL PROFILING COMPLETED")
print("=" * 80)