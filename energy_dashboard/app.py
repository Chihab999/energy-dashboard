from __future__ import annotations

import re
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Energy & Emissions Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_COLORS = {
    "2024": "#1f77b4",
    "2025": "#ff7f0e",
    "2026": "#2ca02c",
    "bg": "#0e1117",
    "card": "#1c2333",
}

CATEGORY_KEYWORDS = {
    "⛽ Fuel Consumption": ["diesel", "gasoline"],
    "💨 Refrigerants / Gases": ["co2", "r-410a", "hfe", "hcfc"],
    "⚡ Energy": ["electricity", "solaire", "solar"],
    "♻️ Waste": ["waste", "composting", "recycling"],
    "🚗 Transport": ["travel", "car", "shuttle", "bus", "van", "taxi", "aircraft"],
}


def chart_layout(theme_mode: str) -> dict:
    template = "plotly_dark" if theme_mode == "Dark" else "plotly_white"
    return {
        "template": template,
        "font": {"family": "Inter, sans-serif", "size": 13},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02},
        "margin": {"l": 40, "r": 40, "t": 60, "b": 40},
    }


def get_year_colors(years: list[str]) -> dict:
    palette = px.colors.qualitative.Set2 + px.colors.qualitative.Plotly
    color_map: dict[str, str] = {}
    for idx, year in enumerate(years):
        color_map[year] = BASE_COLORS.get(year, palette[idx % len(palette)])
    return color_map


@st.cache_data(show_spinner=False)
def parse_excel(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(BytesIO(file_bytes), sheet_name=0, header=None)

    header_row = None
    for i, row in raw.iterrows():
        row_values = row.astype(str)
        if row_values.str.contains("Data_Name", case=False, na=False).any():
            header_row = i
            break

    if header_row is None:
        raise ValueError("Could not find a header row containing 'Data_Name'.")

    df = raw.iloc[header_row:].copy()
    df.columns = df.iloc[0]
    df = df.iloc[1:].copy()

    if "Data_Name" not in df.columns:
        raise ValueError("The parsed table does not contain a 'Data_Name' column.")

    year_col_map: dict[object, str] = {}
    for col in df.columns:
        col_text = str(col).strip()
        year_label = None

        # Handle numeric headers like 2024.0 and convert them to canonical labels.
        numeric_match = re.match(r"^(\d{4})(?:\.0+)?$", col_text)
        if numeric_match and numeric_match.group(1).startswith("2"):
            year_label = numeric_match.group(1)
        elif re.match(r"^20\d{2}$", col_text):
            year_label = col_text

        if year_label is not None:
            year_col_map[col] = year_label

    year_cols = list(year_col_map.values())

    if not year_cols:
        raise ValueError("No year columns were detected in the uploaded file.")

    selected_cols = ["Data_Name"] + list(year_col_map.keys())
    df = df[selected_cols].copy()
    df = df.rename(columns=year_col_map)
    df["Data_Name"] = df["Data_Name"].astype(str).str.strip()
    df = df[df["Data_Name"].notna() & (df["Data_Name"] != "")]

    for col in year_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=year_cols, how="all").reset_index(drop=True)
    return df


def detect_category(metric_name: str) -> str:
    metric = str(metric_name).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in metric for keyword in keywords):
            return category
    return "Other"


def with_categories(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Category"] = out["Data_Name"].apply(detect_category)
    return out


def build_delta_table(df: pd.DataFrame, years: list[str]) -> pd.DataFrame:
    delta_df = pd.DataFrame({"Data_Name": df["Data_Name"]})
    for i in range(1, len(years)):
        prev_y = years[i - 1]
        curr_y = years[i]
        delta_col = f"Δ {prev_y}->{curr_y}"
        pct_col = f"% {prev_y}->{curr_y}"

        delta_vals = df[curr_y] - df[prev_y]
        pct_vals = np.where(df[prev_y] == 0, np.nan, (delta_vals / df[prev_y]) * 100)

        delta_df[delta_col] = delta_vals
        delta_df[pct_col] = pct_vals
    return delta_df


def style_delta_table(delta_df: pd.DataFrame) -> pd.io.formats.style.Styler:
    pct_cols = [c for c in delta_df.columns if c.startswith("% ")]
    num_cols = [c for c in delta_df.columns if c != "Data_Name"]

    def color_pct(val: float) -> str:
        if pd.isna(val):
            return ""
        if val < 0:
            return "background-color: #d9f2d9; color: #0f5132;"
        if val > 0:
            return "background-color: #f8d7da; color: #842029;"
        return "background-color: #e2e3e5; color: #41464b;"

    styler = delta_df.style.format({col: "{:,.2f}" for col in num_cols})
    for col in pct_cols:
        if hasattr(styler, "map"):
            styler = styler.map(color_pct, subset=[col])
        else:
            styler = styler.applymap(color_pct, subset=[col])
    return styler


def compute_biggest_yoy(df: pd.DataFrame, years: list[str]) -> tuple[dict | None, dict | None]:
    if len(years) < 2:
        return None, None

    records: list[dict] = []
    for _, row in df.iterrows():
        for i in range(1, len(years)):
            prev_y = years[i - 1]
            curr_y = years[i]
            prev_val = row.get(prev_y)
            curr_val = row.get(curr_y)
            if pd.isna(prev_val) or pd.isna(curr_val) or prev_val == 0:
                continue
            pct = ((curr_val - prev_val) / prev_val) * 100
            records.append(
                {
                    "Data_Name": row["Data_Name"],
                    "from": prev_y,
                    "to": curr_y,
                    "pct": float(pct),
                }
            )

    if not records:
        return None, None

    inc = max(records, key=lambda x: x["pct"])
    dec = min(records, key=lambda x: x["pct"])
    return inc, dec


def metric_first_last_change(row: pd.Series, years: list[str]) -> float | None:
    if len(years) < 2:
        return None
    first = row[years[0]]
    last = row[years[-1]]
    if pd.isna(first) or pd.isna(last) or first == 0:
        return None
    return float(((last - first) / first) * 100)


def safe_register_figure(name: str, fig: go.Figure, registry: dict[str, go.Figure], layout_cfg: dict) -> None:
    fig.update_layout(**layout_cfg)
    registry[name] = fig
    st.plotly_chart(fig, use_container_width=True)


def create_kpi_card(col, title: str, value, delta: float | None = None, unit: str = "") -> None:
    if isinstance(value, (int, float, np.floating)):
        value_text = f"{value:,.2f} {unit}".strip()
    else:
        value_text = str(value)
    col.metric(
        label=title,
        value=value_text,
        delta=f"{delta:+.2f}%" if delta is not None else None,
        delta_color="inverse",
    )


def export_figures_to_zip(figures: dict[str, go.Figure]) -> bytes | None:
    memory = BytesIO()
    exported = 0
    with ZipFile(memory, mode="w", compression=ZIP_DEFLATED) as zf:
        for name, fig in figures.items():
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "chart"
            try:
                image_bytes = fig.to_image(format="png", scale=2)
                zf.writestr(f"{safe_name}.png", image_bytes)
                exported += 1
            except Exception:
                continue

    if exported == 0:
        return None

    memory.seek(0)
    return memory.getvalue()


def friendly_landing() -> None:
    st.title("⚡ Energy & Emissions Dashboard")
    st.markdown(
        "Upload an Excel file (.xlsx/.xls) from the sidebar. "
        "The app auto-detects years, categories, and all metrics."
    )

    sample = pd.DataFrame(
        {
            "Data_Name": ["Diesel", "Electricity", "Road travel", "Mixed recycling"],
            "2024": [78832, 14760180, 91848, 7.4],
            "2025": [70000, 14760200, 91050, 8.0],
            "2026": [75000, 14770000, 91850, 8.0],
        }
    )
    st.caption("Sample data preview")
    st.dataframe(sample, use_container_width=True)


def main() -> None:
    st.sidebar.title("⚡ Energy Analytics")
    uploaded_file = st.sidebar.file_uploader("Upload Excel file", type=["xlsx", "xls"])

    theme_mode = st.sidebar.selectbox("Theme", ["Dark", "Light"], index=0)

    if uploaded_file is None:
        friendly_landing()
        return

    try:
        with st.spinner("Analyzing data..."):
            parsed_df = parse_excel(uploaded_file.getvalue())
            parsed_df = with_categories(parsed_df)
    except Exception as exc:
        st.error(f"Could not parse the file. Please verify format and headers. Details: {exc}")
        return

    year_cols = [c for c in parsed_df.columns if re.match(r"^20\d{2}$", str(c)) or str(c).startswith("2")]
    if not year_cols:
        st.error("No valid year columns were detected. The app needs at least one year column.")
        return

    year_cols = [str(y) for y in year_cols]
    for y in year_cols:
        parsed_df[y] = pd.to_numeric(parsed_df[y], errors="coerce")

    st.success(f"✅ File loaded: {len(parsed_df):,} rows, {len(year_cols):,} years detected")

    selected_years = st.sidebar.multiselect("Select years", options=year_cols, default=year_cols)
    category_options = [c for c in CATEGORY_KEYWORDS.keys() if c in parsed_df["Category"].unique()] + [
        c for c in parsed_df["Category"].unique() if c not in CATEGORY_KEYWORDS
    ]
    selected_categories = st.sidebar.multiselect(
        "Filter categories",
        options=category_options,
        default=category_options,
    )

    available_metrics = parsed_df["Data_Name"].dropna().unique().tolist()
    metric_highlight = st.sidebar.selectbox("Metric to highlight", available_metrics)

    if not selected_years:
        st.warning("Please select at least one year.")
        return

    if not selected_categories:
        st.warning("Please select at least one category.")
        return

    df = parsed_df[parsed_df["Category"].isin(selected_categories)].copy()
    if df.empty:
        st.warning("No data available after applying filters.")
        return

    year_colors = get_year_colors(selected_years)
    layout_cfg = chart_layout(theme_mode)
    figure_registry: dict[str, go.Figure] = {}

    tabs = st.tabs(["📊 Overview", "📈 Year-over-Year", "🔍 Deep Dive", "📐 Statistics", "📥 Export"])

    with tabs[0]:
        st.subheader("Dataset Overview")
        increase, decrease = compute_biggest_yoy(df, selected_years)

        category_totals = df.groupby("Category")[selected_years].sum(min_count=1).sum(axis=1)
        top_category = category_totals.idxmax() if not category_totals.empty else "N/A"

        cols = st.columns(5)
        create_kpi_card(cols[0], "Total records loaded", int(len(df)))
        create_kpi_card(cols[1], "Years detected", int(len(selected_years)))

        inc_label = "N/A"
        dec_label = "N/A"
        if increase:
            inc_label = f"{increase['Data_Name']} ({increase['pct']:+.2f}%)"
        if decrease:
            dec_label = f"{decrease['Data_Name']} ({decrease['pct']:+.2f}%)"

        create_kpi_card(cols[2], "Largest increase (% YoY)", inc_label)
        create_kpi_card(cols[3], "Largest decrease (% YoY)", dec_label)
        create_kpi_card(cols[4], "Category highest total", top_category)

        metric_row = df[df["Data_Name"] == metric_highlight]
        if not metric_row.empty:
            m = metric_row.iloc[0]
            latest_val = m[selected_years[-1]]
            delta_pct = metric_first_last_change(m, selected_years)
            st.metric(
                label=f"Highlighted metric: {metric_highlight} ({selected_years[-1]})",
                value=f"{latest_val:,.2f}" if pd.notna(latest_val) else "N/A",
                delta=f"{delta_pct:+.2f}%" if delta_pct is not None else None,
                delta_color="inverse",
            )

        st.markdown("### Full Data Table")
        st.dataframe(
            df[["Data_Name", "Category"] + selected_years].style.format(
                {y: "{:,.2f}" for y in selected_years}
            ),
            use_container_width=True,
        )

        st.markdown("### Normalized Heatmap")
        try:
            with st.spinner("Analyzing data..."):
                heat = df.set_index("Data_Name")[selected_years].copy()
                row_max = heat.max(axis=1).replace(0, np.nan)
                heat_norm = heat.div(row_max, axis=0).fillna(0)
                fig_heat = px.imshow(
                    heat_norm,
                    aspect="auto",
                    color_continuous_scale="Turbo",
                    labels={"x": "Year", "y": "Metric", "color": "Normalized"},
                    title="Metric Intensity by Year (Normalized per Metric)",
                )
                safe_register_figure("overview_heatmap", fig_heat, figure_registry, layout_cfg)
        except Exception:
            st.warning("Chart unavailable for this metric")

    with tabs[1]:
        st.subheader("Year-over-Year Comparison by Category")
        for category in selected_categories:
            cat_df = df[df["Category"] == category].copy()
            if cat_df.empty:
                continue

            st.markdown(f"### {category}")
            melted = cat_df.melt(
                id_vars=["Data_Name", "Category"],
                value_vars=selected_years,
                var_name="Year",
                value_name="Value",
            )

            chart_cols = st.columns(2)
            with chart_cols[0]:
                try:
                    with st.spinner("Analyzing data..."):
                        fig_bar = px.bar(
                            melted,
                            x="Data_Name",
                            y="Value",
                            color="Year",
                            barmode="group",
                            color_discrete_map=year_colors,
                            title=f"Grouped Bar Chart - {category}",
                            labels={"Data_Name": "Metric", "Value": "Value"},
                            hover_data={"Value": ":,.2f"},
                        )
                        fig_bar.update_xaxes(tickangle=-25)
                        safe_register_figure(f"bar_{category}", fig_bar, figure_registry, layout_cfg)
                except Exception:
                    st.warning("Chart unavailable for this metric")

            with chart_cols[1]:
                try:
                    with st.spinner("Analyzing data..."):
                        fig_line = px.line(
                            melted,
                            x="Year",
                            y="Value",
                            color="Data_Name",
                            markers=True,
                            title=f"Trend Line Chart - {category}",
                            labels={"Value": "Value", "Year": "Year"},
                            hover_data={"Value": ":,.2f"},
                        )
                        safe_register_figure(f"line_{category}", fig_line, figure_registry, layout_cfg)
                except Exception:
                    st.warning("Chart unavailable for this metric")

            st.markdown("**Delta Table (absolute and % change)**")
            delta_df = build_delta_table(cat_df, selected_years)
            st.dataframe(style_delta_table(delta_df), use_container_width=True)

    with tabs[2]:
        st.subheader("Deep Dive: Single Metric")
        deep_metric = st.selectbox("Select one metric", df["Data_Name"].tolist(), key="deep_dive_metric")
        deep_row = df[df["Data_Name"] == deep_metric].iloc[0]

        y_values = [deep_row[y] for y in selected_years]

        try:
            with st.spinner("Analyzing data..."):
                fig_metric = go.Figure(
                    data=[
                        go.Scatter(
                            x=selected_years,
                            y=y_values,
                            mode="lines+markers+text",
                            text=[f"{v:,.2f}" if pd.notna(v) else "N/A" for v in y_values],
                            textposition="top center",
                            name=deep_metric,
                            line={"width": 3, "color": year_colors.get(selected_years[0], "#1f77b4")},
                        )
                    ]
                )
                fig_metric.update_layout(
                    title=f"Metric Evolution: {deep_metric}",
                    xaxis_title="Year",
                    yaxis_title="Value",
                )
                safe_register_figure(f"deep_dive_{deep_metric}", fig_metric, figure_registry, layout_cfg)
        except Exception:
            st.warning("Chart unavailable for this metric")

        stats_values = pd.Series(y_values, dtype="float64")
        first_val = stats_values.iloc[0] if len(stats_values) else np.nan
        last_val = stats_values.iloc[-1] if len(stats_values) else np.nan
        first_last_pct = np.nan
        if pd.notna(first_val) and first_val != 0 and pd.notna(last_val):
            first_last_pct = ((last_val - first_val) / first_val) * 100

        stats_table = pd.DataFrame(
            {
                "Statistic": ["Min", "Max", "Mean", "Std Dev", "Total", "% Change first->last"],
                "Value": [
                    stats_values.min(),
                    stats_values.max(),
                    stats_values.mean(),
                    stats_values.std(),
                    stats_values.sum(),
                    first_last_pct,
                ],
            }
        )
        st.dataframe(stats_table.style.format({"Value": "{:,.2f}"}), use_container_width=True)

        if len(selected_years) >= 2 and pd.notna(stats_values.iloc[-1]) and pd.notna(stats_values.iloc[-2]):
            try:
                with st.spinner("Analyzing data..."):
                    fig_gauge = go.Figure(
                        go.Indicator(
                            mode="gauge+number+delta",
                            value=float(stats_values.iloc[-1]),
                            delta={"reference": float(stats_values.iloc[-2]), "relative": True},
                            title={"text": f"Latest value vs previous year ({selected_years[-1]})"},
                            gauge={
                                "axis": {"range": [0, max(float(stats_values.max()) * 1.1, 1)]},
                                "bar": {"color": year_colors.get(selected_years[-1], "#2ca02c")},
                            },
                        )
                    )
                    safe_register_figure(f"gauge_{deep_metric}", fig_gauge, figure_registry, layout_cfg)
            except Exception:
                st.warning("Chart unavailable for this metric")

        trend_label = "➡️ Stable"
        trend_color = "#6c757d"
        if pd.notna(first_val) and pd.notna(last_val):
            if last_val > first_val:
                trend_label = "📈 Increasing"
                trend_color = "#d9534f"
            elif last_val < first_val:
                trend_label = "📉 Decreasing"
                trend_color = "#198754"

        st.markdown(
            f"<div style='display:inline-block;padding:0.4rem 0.7rem;border-radius:0.5rem;"
            f"background:{trend_color};color:white;font-weight:700'>{trend_label}</div>",
            unsafe_allow_html=True,
        )

    with tabs[3]:
        st.subheader("Statistics Summary")
        desc = df[selected_years].describe().T
        st.markdown("### Descriptive Statistics by Year")
        st.dataframe(desc.style.format("{:,.2f}"), use_container_width=True)

        st.markdown("### Box Plot Distribution by Category")
        try:
            with st.spinner("Analyzing data..."):
                box_df = df.melt(
                    id_vars=["Data_Name", "Category"],
                    value_vars=selected_years,
                    var_name="Year",
                    value_name="Value",
                )
                fig_box = px.box(
                    box_df,
                    x="Category",
                    y="Value",
                    color="Category",
                    points="outliers",
                    title="Distribution Across Categories",
                    labels={"Value": "Value", "Category": "Category"},
                )
                safe_register_figure("boxplot_categories", fig_box, figure_registry, layout_cfg)
        except Exception:
            st.warning("Chart unavailable for this metric")

        st.markdown("### Radar / Spider Chart (Normalized by Category)")
        try:
            with st.spinner("Analyzing data..."):
                cat_totals = df.groupby("Category")[selected_years].sum(min_count=1)
                norm = cat_totals.copy()
                for year in selected_years:
                    max_v = norm[year].max()
                    if pd.notna(max_v) and max_v != 0:
                        norm[year] = norm[year] / max_v
                    else:
                        norm[year] = 0

                radar_categories = norm.index.tolist()
                fig_radar = go.Figure()
                for year in selected_years:
                    r_vals = norm[year].tolist()
                    if radar_categories:
                        r_vals = r_vals + [r_vals[0]]
                        theta_vals = radar_categories + [radar_categories[0]]
                    else:
                        theta_vals = []
                    fig_radar.add_trace(
                        go.Scatterpolar(
                            r=r_vals,
                            theta=theta_vals,
                            fill="toself",
                            name=year,
                            line={"color": year_colors.get(year)},
                        )
                    )

                fig_radar.update_layout(
                    title="Normalized Category Profile by Year",
                    polar={"radialaxis": {"visible": True, "range": [0, 1]}},
                )
                safe_register_figure("radar_categories", fig_radar, figure_registry, layout_cfg)
        except Exception:
            st.warning("Chart unavailable for this metric")

        st.markdown("### Correlation Matrix Between Years")
        try:
            with st.spinner("Analyzing data..."):
                corr = df[selected_years].corr(numeric_only=True)
                fig_corr = px.imshow(
                    corr,
                    text_auto=True,
                    color_continuous_scale="RdBu",
                    zmin=-1,
                    zmax=1,
                    title="Year-to-Year Correlation Matrix",
                    labels={"color": "Correlation"},
                )
                safe_register_figure("correlation_matrix", fig_corr, figure_registry, layout_cfg)
        except Exception:
            st.warning("Chart unavailable for this metric")

    with tabs[4]:
        st.subheader("Export & Report")

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download processed data as CSV",
            data=csv_bytes,
            file_name="processed_energy_data.csv",
            mime="text/csv",
        )

        stats_buffer = BytesIO()
        with pd.ExcelWriter(stats_buffer, engine="xlsxwriter") as writer:
            df[selected_years].describe().to_excel(writer, sheet_name="statistics")
            df.groupby("Category")[selected_years].sum(min_count=1).to_excel(writer, sheet_name="category_totals")
        stats_buffer.seek(0)

        st.download_button(
            label="Download statistics summary as Excel",
            data=stats_buffer.getvalue(),
            file_name="statistics_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        chart_zip = export_figures_to_zip(figure_registry)
        if chart_zip is not None:
            st.download_button(
                label="Download all charts as PNG",
                data=chart_zip,
                file_name="dashboard_charts_png.zip",
                mime="application/zip",
            )

        totals_per_year = df[selected_years].sum(numeric_only=True)
        year_with_highest = totals_per_year.idxmax() if not totals_per_year.empty else "N/A"

        metric_first_last = []
        if len(selected_years) >= 2:
            for _, row in df.iterrows():
                if row[selected_years[0]] and not pd.isna(row[selected_years[0]]):
                    pct = metric_first_last_change(row, selected_years)
                    if pct is not None:
                        metric_first_last.append((row["Data_Name"], pct))

        metric_grew_most = max(metric_first_last, key=lambda x: x[1]) if metric_first_last else ("N/A", np.nan)
        metric_decreased_most = min(metric_first_last, key=lambda x: x[1]) if metric_first_last else ("N/A", np.nan)

        cat_totals = df.groupby("Category")[selected_years].sum(min_count=1).sum(axis=1)
        top_category = cat_totals.idxmax() if not cat_totals.empty else "N/A"

        report = (
            f"Summary Report\n"
            f"- Metric with highest growth: {metric_grew_most[0]} ({metric_grew_most[1]:+.2f}% first to last year)\n"
            f"- Metric with largest decrease: {metric_decreased_most[0]} ({metric_decreased_most[1]:+.2f}% first to last year)\n"
            f"- Category with highest consumption: {top_category}\n"
            f"- Year with highest total across metrics: {year_with_highest}\n"
        )
        st.text_area("Auto-generated report", report, height=180)


if __name__ == "__main__":
    main()
