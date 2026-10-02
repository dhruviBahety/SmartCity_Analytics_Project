# Power BI Guide — Smart City Traffic & Accident Analytics (v2)

I can't produce a `.pbix` (Power BI Desktop isn't available in my environment), so this
guide plus the prepared data, DAX and theme lets you assemble it in about 1–2 hours.
The DAX and relationships are **not tested inside Power BI Desktop**; check each measure for errors as you paste it.

Files you need: `powerbi_exports/*.csv` (15 tables), `powerbi/measures.dax`, `powerbi/smartcity_theme.json`.

---

## 1. Fixing the data limits (what changed and why)

| Limit | Fix |
|---|---|
| Sensor data = 1–13 Jan; accidents = Jan–Jul, so a date slicer blanks traffic | The two datasets are linked by **Location** and **Hour**, not date. Every traffic measure uses `REMOVEFILTERS(dim_date)`, so the date slicer only affects accident visuals. A dynamic "Data Coverage" text box shows each dataset's real date range so nobody misreads it. |
| No lat/long, so no map | Zone-level visuals only: bar, treemap, matrix, scatter. Map removed from the plan. |
| ML model ≈ coin flip (AUC 0.52) | Added a **Historical Risk Score** (0–100, descriptive: 40% accident frequency, 30% severity, 30% congestion) in `fact_location_hour`. The ML page stays but is labelled "Illustrative". |
| Unsorted categories (High/Low/Moderate alphabetical) | Added sort-key columns and small dims (`dim_congestion_level`, `dim_severity`, `dim_traffic_density`, `dim_hour`). |
| Only 300 sensor rows | 8 of 120 Location×Hour cells have **no sensor reading**. They show blank, not zero. Mention this as a data limitation. |

## 2. Load and model

Get Data → Text/CSV → load all 15 tables. In Power Query set types: `Date_Time` = Date/Time, `Date`/`Week_Start` = Date, `Is_Peak_Hour`/`Is_Weekend`/`Is_High_Risk` = True/False.
Then View → Themes → Browse for themes → `smartcity_theme.json`.

**Relationships** (all Many-to-One, single direction, dim → fact):

| Dimension | Key | Related fact tables |
|---|---|---|
| dim_location | Location_ID | fact_traffic, fact_accidents, fact_location_hour, high_risk_predictions |
| dim_hour | Hour | fact_traffic, fact_accidents, fact_location_hour, high_risk_predictions |
| dim_date | Date_ID | fact_traffic, fact_accidents |
| dim_weather | Weather_ID | fact_accidents |
| dim_road_condition | Road_Condition_ID | fact_accidents |
| dim_vehicle_type | Vehicle_Type_ID | fact_accidents |
| dim_severity | Accident_Severity | fact_accidents |
| dim_traffic_density | Traffic_Density | fact_accidents |
| dim_congestion_level | Congestion_Level | fact_traffic |

`metric_switch` and `model_feature_importance` stay **unrelated** (disconnected tables).
Mark `dim_date` as the date table (column `Date`).

```
dim_location ─┬─ fact_traffic ──── dim_congestion_level
dim_hour ─────┤   (shared dims link the two datasets)
              ├─ fact_accidents ─┬─ dim_weather / dim_road_condition / dim_vehicle_type
dim_date ─────┘                  └─ dim_severity / dim_traffic_density
dim_location + dim_hour ── fact_location_hour, high_risk_predictions
```

**Sort by column** (Column tools → Sort by column):
`Congestion_Level`→Congestion_Sort · `Accident_Severity`→Severity_Sort · `Traffic_Density`→Density_Sort ·
`Day_Of_Week`→Day_Of_Week_Num · `Month_Name`→Month · `Time_Period`→Time_Period_Sort · `Hour_Label`→Hour

**Measures:** create an empty table `_Measures`, paste everything from `measures.dax`.

---

## 3. Complete visual list

### Page 1 — Traffic & Congestion
| # | Visual | Fields |
|---|---|---|
| 1 | 4 KPI cards | Avg Congestion Index, Total Vehicles, Avg Speed, High Congestion % |
| 2 | Line chart | Axis `dim_hour[Hour_Label]`, values = `[Selected Metric Value]`, title = `[Selected Metric Title]` |
| 3 | Bar chart (sorted desc) | `dim_location[Location_Name]`, `[Avg Congestion Index]` |
| 4 | 100% stacked bar | Location × `dim_congestion_level[Congestion_Level]`, count of readings |
| 5 | Clustered column | `dim_hour[Time_Period]`, `[Avg Speed]` + `[Avg Congestion Index]` |
| 6 | Card | `[Peak Uplift %]` ("peak hours are X% more congested") |
| 7 | Text box | `[Data Coverage Note]` |

### Page 2 — Accident-Prone Areas
| # | Visual | Fields |
|---|---|---|
| 8 | 4 KPI cards | Total Accidents, Total Casualties, High-Risk Rate, Avg Severity Score |
| 9 | Combo (bar + line) | Location, columns `[Total Accidents]`, line `[Avg Severity Score]` |
| 10 | Column charts (×2) | Accidents & Avg Severity by `dim_weather` and by `dim_road_condition` |
| 11 | Donut | `dim_severity[Accident_Severity]`, `[Total Accidents]` |
| 12 | Table | Location, `[Total Accidents]`, `[High-Risk Accidents]`, `[High-Risk Rate]`, `[Location Risk Rank]`, with data bars |
| 13 | Bar chart | `dim_vehicle_type`, `[Avg Casualties per Accident]` |
| 14 | Treemap | Location → `[Total Casualties]` |

### Page 3 — Peak Hour & Trends
| # | Visual | Fields |
|---|---|---|
| 15 | Dual-axis line | `dim_hour[Hour_Label]`, `[Total Accidents]` (left) + `[Avg Congestion Index]` (right) |
| 16 | Matrix heatmap | Rows `Day_Of_Week`, columns `Hour_Label`, `[Total Accidents]`, color scale |
| 17 | Line chart | `dim_date[Month_Year]` (drill: Month → Day), `[Total Accidents]` |
| 18 | Clustered column | `dim_date[Is_Weekend]`, `[Total Accidents]` + `[Avg Severity Score]` |
| 19 | **Scatter** | Details = Location, X = `[Avg Congestion Index]`, Y = `[Avg Severity Score]`, size = `[Total Accidents]` |
| 20 | Matrix | Location × Hour, `[Congestion-Accident Priority]` (conditional format) |

### Page 4 — Risk Insights
| # | Visual | Fields |
|---|---|---|
| 21 | Matrix heatmap | Location × `Hour_Label`, `[Historical Risk Score]`, background = `[Risk Color]` |
| 22 | Table (Top N filter = 10) | Location, Hour, `[Historical Risk Score]`, `[Total Accidents]`, `[Avg Congestion Index]` |
| 23 | **Decomposition tree** | Analyze `[High-Risk Accidents]` explain-by Weather, Road Condition, Location, Vehicle Type |
| 24 | Matrix heatmap (labelled *Illustrative*) | Location × Hour, `[Avg Predicted Risk]` |
| 25 | Bar chart | `model_feature_importance` (Feature, Importance) |
| 26 | Text box | "Model ROC-AUC ≈ 0.52: no predictive signal in this sample data. Use Historical Risk Score for decisions." |

### Page 5 — Location Detail (drill-through target)
| # | Visual | Fields |
|---|---|---|
| 27 | Title | `[Location Page Title]` |
| 28 | KPI cards | Avg Congestion, Total Accidents, High-Risk Rate, Historical Risk Score |
| 29 | Line chart | Hourly `[Avg Congestion Index]` and `[Total Accidents]` for that location |
| 30 | Column | Accidents by weather for that location |

### Page 6 — Tooltip (hidden, Page size = Tooltip)
| # | Visual | Fields |
|---|---|---|
| 31 | Mini line chart | `Hour_Label`, `[Avg Congestion Index]`, plus card `[Total Accidents]` |

---

## 4. Interactive objects (how to build each)

1. **Slicers, synced across pages.** View → Sync slicers. Add: Location (dropdown), Weather, Road Condition, Vehicle Type, Severity, Time Period, Date range (between).
2. **Date slicer scope.** Select the Date slicer → Format → Edit interactions → set to **None** on Page 1 traffic visuals. Traffic measures already ignore date; this stops the visuals greying out too.
3. **Cross-filtering / highlight.** Default behaviour: click a location bar to filter everything on the page. Ctrl+click for multi-select.
4. **Metric switch.** Add a slicer on `metric_switch[Metric]` (single select, tile style) to drive visual #2's value and title.
5. **Drill-down / drill-up.** Enable on #17 (Month_Year → Date) and #16 (Day → Hour). Use the drill arrows in the visual header.
6. **Drill-through.** On Page 5, drop `dim_location[Location_Name]` into the "Drill through" well. Right-click any location on pages 1-4 → Drill through → Location Detail.
7. **Report-page tooltip.** On Page 6: Format page → Page information → Allow use as tooltip = On; Canvas settings → Type = Tooltip. On visuals #3 and #9: Format → Tooltips → Type = Report page → Page 6.
8. **Bookmarks + buttons.** (a) A nav bar using Insert → Buttons → Navigator → Page navigator. (b) "Reset filters" button: clear all slicers, then View → Bookmarks → Add, and set the button's Action to that bookmark. (c) "Show table / Show chart" toggle using two bookmarks that hide/show visuals via the Selection pane.
9. **Conditional formatting.** Color scale on heatmaps (#16, #21); data bars on table #12; background from `[Congestion-Accident Priority]` on #20; background = field value `[Risk Color]` on #21.
10. **Top N filter.** On #22: Filters pane → Top N = 10 by `[Historical Risk Score]`.
11. **Dynamic titles/text.** Use the fx button on visual titles with `[Selected Metric Title]`, `[Data Coverage Note]`, `[Location Page Title]`.
12. **Decomposition tree (#23).** Click-through root-cause exploration. Optional extra: Key Influencers visual.
13. **Q&A visual (optional).** Insert → Q&A so viewers can type "accidents by weather".
14. **Data alerts (Service only).** After publishing, set an alert on the High-Risk Rate card.

## 5. Suggested layout
Left slim rail: page navigator and slicers. Top row: KPI cards. Body: 2 large visuals plus 1-2 supporting. Footer text box with `[Data Coverage Note]`. Stay within the theme's colors; use red only for risk.

## 6. What to say about limitations in your report
- Sensor and accident data don't overlap in time, so they are linked by Location + Hour; no causal claim between congestion and accidents.
- Sensor coverage is thin (300 rows, 8 empty Location×Hour cells).
- The ML model has no predictive power on this data (AUC 0.52); the Historical Risk Score is a descriptive ranking, not a forecast.
- The data looks randomly generated (near-uniform severity, no missing values), so most patterns in the dashboard will reflect noise.
