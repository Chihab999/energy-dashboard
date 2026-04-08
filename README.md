# Energy & Emissions Dashboard

Interactive Streamlit dashboard for multi-year analysis of energy, fuel, transport, waste, and refrigerant/emissions metrics from Excel uploads.

## Features

- Automatic header and year detection from uploaded Excel files
- Keyword-based category mapping:
  - Fuel Consumption
  - Refrigerants / Gases
  - Energy
  - Waste
  - Transport
- Five interactive tabs:
  - Overview
  - Year-over-Year Comparison
  - Deep Dive
  - Statistics Summary
  - Export
- Plotly visualizations with consistent styling
- KPI cards and auto-generated textual summary report
- CSV/Excel export and optional PNG chart export when Kaleido is installed

## Project Structure

```text
energy_dashboard/
├── app.py
├── requirements.txt
└── README.md
```

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Input Format Notes

- Upload `.xlsx` or `.xls`
- The app auto-detects the row containing `Data_Name`
- Year columns are detected dynamically (supports 2+ years)
- Invalid/missing year values are coerced safely to numeric

## Optional: Export Charts as PNG

To enable Plotly image export (`Download all charts as PNG`), install Kaleido:

```bash
pip install kaleido
```
