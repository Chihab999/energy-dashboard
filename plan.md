# 🧠 COPILOT PROMPT — Full Streamlit Energy & Emissions Dashboard

## CONTEXT

Build a **complete, production-ready Streamlit application** for statistical analysis and multi-year comparison of energy, fuel, and emissions data. The app must be fully autonomous: the user uploads an Excel file and the app auto-detects and displays everything — no hardcoding of values.

---

## INPUT FILE STRUCTURE

The Excel file (`Book12222.xlsx`) has **one sheet (Sheet1)**. The real data starts at **row 3 (index 2)** and has this structure:

| Column C (Data_Name) | Column D (2024) | Column E (2025) | Column F (2026) |
|---|---|---|---|
| Diesel | 78832 | 70000 | 75000 |
| gasoline | 11976 | 12000 | 11500 |
| diesel | 17292 | 174000 | 17000 |
| CO2-ext | 35 | 35 | 35 |
| R-410A | 47 | 45 | 48 |
| HFE-134 | 44 | 45 | 44 |
| HCFC-22 | 11 | 10 | 10 |
| Electricity | 14760180 | 14760200 | 14770000 |
| solaire | 23484 | 23490 | 23590 |
| Indsutrial waste | 1.7 | 2.0 | 1.5 |
| composting | 900.5 | 910 | 901 |
| Mixed recycling | 7.4 | 8.0 | 8.0 |
| Waste water | 230.761 | 230.761 | 231 |
| Road travel | 91848 | 91050 | 91850 |
| Air travel | 2 | 2 | 2 |
| car | 4093.5 | 4094 | 4093.9 |
| shuttle bus, van | 2549.1 | 2649.1 | 2549 |
| car/ taxi | 7071838 | 7071838 | 7081838 |
| shuttle bus, van | 3359460 | 3360460 | 3459460 |
| Aircraft movements | 63235 | 63236 | 63255 |

---

## CATEGORIES TO AUTO-DETECT & GROUP

Group the rows into these **logical categories** (detect by keyword matching on `Data_Name`):

| Category | Keywords to match |
|---|---|
| ⛽ Fuel Consumption | diesel, gasoline, Diesel |
| 💨 Refrigerants / Gases | CO2, R-410A, HFE, HCFC |
| ⚡ Energy | Electricity, solaire, solar |
| ♻️ Waste | waste, composting, recycling |
| 🚗 Transport | travel, car, shuttle, bus, van, taxi, Aircraft |

---

## FILE PARSING LOGIC

```python
import pandas as pd

def parse_excel(file) -> pd.DataFrame:
    df_raw = pd.read_excel(file, sheet_name=0, header=None)
    # Find the header row (contains 'Data_Name')
    header_row = None
    for i, row in df_raw.iterrows():
        if row.astype(str).str.contains('Data_Name', case=False).any():
            header_row = i
            break
    # Extract data from header_row onwards
    df = df_raw.iloc[header_row:].copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].dropna(subset=['Data_Name'])
    df = df[['Data_Name'] + [c for c in df.columns if str(c).startswith('2')]]
    df = df.reset_index(drop=True)
    year_cols = [c for c in df.columns if str(c).startswith('2')]
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors='coerce')
    return df
```

---

## FULL APP SPECIFICATION

### 1. PAGE CONFIGURATION
```python
st.set_page_config(
    page_title="Energy & Emissions Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

---

### 2. SIDEBAR

- App logo/title: `⚡ Energy Analytics`
- **File uploader**: accepts `.xlsx`, `.xls`
- **Year selector**: multi-select of detected year columns (default: all)
- **Category filter**: multi-select checkboxes (Fuel, Refrigerants, Energy, Waste, Transport)
- **Metric selector**: dropdown to choose which metric to highlight in KPI cards
- Color theme toggle (Light / Dark) — optional bonus

---

### 3. MAIN LAYOUT — TABS

Use `st.tabs()` with these 5 tabs:

#### 📊 Tab 1 — Overview
- **KPI Cards row** (use `st.columns()`):
  - Total records loaded
  - Number of years detected
  - Largest increase (% YoY) — auto-detected
  - Largest decrease (% YoY) — auto-detected
  - Category with highest total value
- **Full data table** with `st.dataframe()` — styled, searchable
- **Heatmap**: rows = Data_Name, columns = years, values = normalized % of max per row (use Plotly `imshow`)

---

#### 📈 Tab 2 — Year-over-Year Comparison
For each **category group**:
- Grouped **Bar Chart** (Plotly): x = Data_Name, bars grouped by year, colors per year
- **Line Chart** (Plotly): evolution of each metric over years
- **Delta table**: show absolute change and % change between each consecutive year pair (e.g., 2024→2025, 2025→2026)
  - Color cells: green if decrease (better for emissions), red if increase

Formula for % change:
```
pct_change = ((year_N - year_N-1) / year_N-1) * 100
```

---

#### 🔍 Tab 3 — Deep Dive (Single Metric)
- Dropdown to select ONE metric from `Data_Name`
- Show:
  - **Line chart** with data points labeled
  - **Statistics table**: min, max, mean, std dev, total, % change first→last year
  - **Gauge chart** (Plotly `go.Indicator`): showing latest year value vs. previous year
  - **Trend annotation**: "📈 Increasing", "📉 Decreasing", or "➡️ Stable" with color badge

---

#### 📐 Tab 4 — Statistics Summary
- Full **descriptive statistics** table (per year column): count, mean, std, min, 25%, 50%, 75%, max
- **Box plots** (Plotly) per category showing distribution across years
- **Radar/Spider chart** (Plotly `go.Scatterpolar`): normalized values per category, one trace per year
- **Correlation matrix** between years (Plotly heatmap)

---

#### 📥 Tab 5 — Export
- Button: **Download processed data as CSV**
- Button: **Download statistics summary as Excel**
- Button: **Download all charts as PNG** (use `plotly.io.write_image` if kaleido is available, else skip silently)
- Show a **summary report text block** (auto-generated) describing:
  - Which metric grew the most
  - Which metric decreased the most
  - Category with highest consumption
  - Year with highest total across all metrics

---

## CHART STYLING REQUIREMENTS

All charts must use **Plotly** (not matplotlib). Apply this consistent theme:

```python
COLORS = {
    "2024": "#1f77b4",   # blue
    "2025": "#ff7f0e",   # orange
    "2026": "#2ca02c",   # green
    "bg": "#0e1117",
    "card": "#1c2333"
}

chart_layout = dict(
    template="plotly_dark",
    font=dict(family="Inter, sans-serif", size=13),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=40, r=40, t=60, b=40)
)
```

Apply `fig.update_layout(**chart_layout)` to every chart.

---

## KPI CARD COMPONENT

Create a reusable `kpi_card(title, value, delta, delta_color)` function using `st.metric()`:

```python
def kpi_card(col, title, value, delta=None, unit=""):
    col.metric(
        label=title,
        value=f"{value:,.2f} {unit}",
        delta=f"{delta:+.2f}%" if delta is not None else None,
        delta_color="inverse"  # red=increase for emissions context
    )
```

---

## ERROR HANDLING

- If no file uploaded: show a **friendly landing page** with instructions and a sample data preview
- If file has wrong format: show `st.error()` with clear message
- If a year column is missing: skip it gracefully without crashing
- Wrap all chart rendering in `try/except` — on failure show `st.warning("Chart unavailable for this metric")`

---

## DEPENDENCIES (requirements.txt)

```
streamlit>=1.32.0
pandas>=2.0.0
openpyxl>=3.1.0
plotly>=5.18.0
xlsxwriter>=3.1.0
numpy>=1.26.0
```

---

## FILE STRUCTURE

```
energy_dashboard/
├── app.py              # Main Streamlit app (all code here, single file)
├── requirements.txt
└── README.md
```

Keep **everything in `app.py`** — no separate modules. The app must run with:
```bash
streamlit run app.py
```

---

## IMPORTANT UX RULES

1. Always show a **spinner** (`st.spinner("Analyzing data...")`) during file parsing and chart generation
2. Use `st.success("✅ File loaded: X rows, Y years detected")` after upload
3. All charts must have **titles, axis labels, and tooltips**
4. Numbers must be **formatted with thousands separators** everywhere
5. The app must work with **any number of years** (2, 3, 4+) — no hardcoding of year values
6. Use `st.cache_data` on the parse function to avoid re-parsing on every interaction

---

## DELIVERABLE

A single `app.py` file that is complete, runs without errors, and handles the described Excel format. Comment each major section clearly. The dashboard must be visually polished, data-driven, and fully interactive.