"""
Goal: predict whether a given combination of location, time, weather,
road condition, and traffic density is a HIGH-RISK situation
(Accident_Severity in {Severe, Fatal}) vs LOWER-RISK (Minor, Moderate).

Model: Random Forest Classifier (handles categorical/non-linear
interactions well, gives feature importances the city can act on).

"""

import os
import sqlite3
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smart_city_dw.db")
MODEL_DIR = os.path.join(BASE_DIR, "models")
EXPORT_DIR = os.path.join(BASE_DIR, "powerbi_exports")
os.makedirs(MODEL_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Load data from the warehouse
# ---------------------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("""
    SELECT
        a.Accident_Severity, a.Number_of_Vehicles, a.Casualties, a.Traffic_Density,
        a.Hour, a.Is_Peak_Hour,
        l.Location_Name, w.Weather_Condition, r.Road_Condition, v.Vehicle_Type,
        d.Is_Weekend
    FROM fact_accidents a
    JOIN dim_location l ON a.Location_ID = l.Location_ID
    JOIN dim_weather w ON a.Weather_ID = w.Weather_ID
    JOIN dim_road_condition r ON a.Road_Condition_ID = r.Road_Condition_ID
    JOIN dim_vehicle_type v ON a.Vehicle_Type_ID = v.Vehicle_Type_ID
    JOIN dim_date d ON a.Date_ID = d.Date_ID
""", conn)
conn.close()

# ---------------------------------------------------------------------------
# 2. Define target: High-Risk (Severe/Fatal) = 1, else 0
# ---------------------------------------------------------------------------
df["High_Risk"] = df["Accident_Severity"].isin(["Severe", "Fatal"]).astype(int)

feature_cols = ["Location_Name", "Weather_Condition", "Road_Condition", "Vehicle_Type",
                 "Traffic_Density", "Hour", "Is_Peak_Hour", "Is_Weekend"]
X = df[feature_cols]
y = df["High_Risk"]

categorical = ["Location_Name", "Weather_Condition", "Road_Condition", "Vehicle_Type", "Traffic_Density"]
numeric = ["Hour", "Is_Peak_Hour", "Is_Weekend"]

preprocess = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
], remainder="passthrough")

model = Pipeline([
    ("prep", preprocess),
    ("clf", RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42, class_weight="balanced")),
])


# 3 Train / evaluate

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

print("=== Model Evaluation (High-Risk Accident Classifier) ===")
print(classification_report(y_test, y_pred, target_names=["Lower-Risk", "High-Risk"]))
print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.3f}")
print(f"Baseline high-risk rate in data: {y.mean():.2%}")

joblib.dump(model, os.path.join(MODEL_DIR, "high_risk_model.pkl"))

# ---------------------------------------------------------------------------
# 4. Feature importance (which raw categorical values matter most)
# ---------------------------------------------------------------------------
ohe = model.named_steps["prep"].named_transformers_["cat"]
feature_names = list(ohe.get_feature_names_out(categorical)) + numeric
importances = model.named_steps["clf"].feature_importances_
fi = pd.DataFrame({"Feature": feature_names, "Importance": importances}).sort_values(
    "Importance", ascending=False
)
fi.to_csv(os.path.join(MODEL_DIR, "feature_importances.csv"), index=False)
print("\nTop 10 risk drivers:")
print(fi.head(10).to_string(index=False))

# ---------------------------------------------------------------------------
# 5. Score every Location x Hour x Weather x Road_Condition combo
#    -> gives the city a lookup table of predicted risk, ready for
#       a Power BI "Predictive Insights" page (map/heatmap by hour).
# ---------------------------------------------------------------------------
locations = df["Location_Name"].unique()
weathers = df["Weather_Condition"].unique()
roads = df["Road_Condition"].unique()
hours = range(24)
vehicle_mode = df["Vehicle_Type"].mode()[0]
density_mode = df["Traffic_Density"].mode()[0]

grid = pd.MultiIndex.from_product(
    [locations, weathers, roads, hours], names=["Location_Name", "Weather_Condition", "Road_Condition", "Hour"]
).to_frame(index=False)
grid["Vehicle_Type"] = vehicle_mode
grid["Traffic_Density"] = density_mode
grid["Is_Peak_Hour"] = grid["Hour"].isin([7, 8, 9, 17, 18, 19, 20]).astype(int)
grid["Is_Weekend"] = 0

grid["Predicted_High_Risk_Probability"] = model.predict_proba(grid[feature_cols])[:, 1].round(4)
grid_out = grid.drop(columns=["Vehicle_Type", "Traffic_Density"]).sort_values(
    "Predicted_High_Risk_Probability", ascending=False
)
# Add Location_ID so this table joins to dim_location / dim_hour in Power BI
_conn = sqlite3.connect(DB_PATH)
_loc = pd.read_sql("SELECT Location_ID, Location_Name FROM dim_location", _conn)
_conn.close()
grid_out = grid_out.merge(_loc, on="Location_Name", how="left")
# Feature importance for the Power BI bar chart
fi.rename(columns={"Feature": "Feature", "Importance": "Importance"}).head(15).to_csv(
    os.path.join(EXPORT_DIR, "model_feature_importance.csv"), index=False)
grid_out.to_csv(os.path.join(EXPORT_DIR, "high_risk_predictions.csv"), index=False)
print(f"\n✅ Predictions exported -> {os.path.join(EXPORT_DIR, 'high_risk_predictions.csv')} "
      f"({len(grid_out)} rows)")
print("\nTop 5 highest-predicted-risk combinations:")
print(grid_out.head(5).to_string(index=False))
