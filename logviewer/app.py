import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path

st.set_page_config(layout="wide", page_title="LogViewer")
st.title("📋 Log Viewer Dashboard")

# Load config to determine mode
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    st.error("Missing config.json! Cannot continue.")
    st.stop()

with open(CONFIG_FILE) as f:
    config = json.load(f)

MODE = config.get("mode")

@st.cache_data
def load_parsed_logs(path):
    log_path = os.path.join(path, "parsed_logs.json")
    if not os.path.exists(log_path):
        return pd.DataFrame()
    with open(log_path) as f:
        data = json.load(f)
    return pd.DataFrame(data)

def format_timestamp(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

def apply_filters(df, proc_filter, keyword, include_fastlogs, start_date, end_date):
    filtered_df = df.copy()
    if proc_filter != "All":
        filtered_df = filtered_df[filtered_df['process'] == proc_filter]
    if keyword:
        filtered_df = filtered_df[filtered_df['message'].str.contains(keyword, case=False, na=False)]
    if not include_fastlogs:
        filtered_df = filtered_df[~filtered_df['source'].eq("fastlog")]
    if start_date and end_date:
        filtered_df = filtered_df[
            (filtered_df["timestamp_dt"] >= start_date) & (filtered_df["timestamp_dt"] <= end_date)
        ]
    return filtered_df

def render_bundle_view(df):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        proc_filter = st.selectbox("Filter by Process", ["All"] + sorted(df['process'].dropna().unique().tolist()))
    with col2:
        keyword = st.text_input("Keyword Search")
    with col3:
        include_fastlogs = st.checkbox("Include Fastlogs", value=True)

    if "timestamp" in df.columns:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors='coerce')
        min_date = df["timestamp_dt"].min().to_pydatetime()
        max_date = df["timestamp_dt"].max().to_pydatetime()
        start_date, end_date = st.slider("Time Range", min_value=min_date, max_value=max_date,
                                         value=(min_date, max_date), format="YYYY-MM-DD HH:mm")
    else:
        start_date, end_date = None, None

    filtered_df = apply_filters(df, proc_filter, keyword, include_fastlogs, start_date, end_date)

    st.subheader("📈 Errors per Hour")
    error_logs = filtered_df[filtered_df['severity'] == 'LOG_ERR']
    if not error_logs.empty:
        error_logs['hour'] = error_logs['timestamp_dt'].dt.strftime("%Y-%m-%d %H")
        chart_data = error_logs.groupby('hour').size().rename("count").reset_index()
        st.line_chart(chart_data.set_index('hour'))
    else:
        st.info("No LOG_ERR entries in this view.")

    logs_per_page = 100
    total_pages = (len(filtered_df) + logs_per_page - 1) // logs_per_page
    current_page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1)

    start = (current_page - 1) * logs_per_page
    end = start + logs_per_page
    page_df = filtered_df.iloc[start:end].copy()

    st.subheader(f"📝 Logs (Page {current_page}/{total_pages})")
    if not page_df.empty:
        page_df["timestamp"] = page_df["timestamp"].apply(format_timestamp)

        def color_severity(val):
            color = ''
            if val == 'LOG_ERR':
                color = 'background-color: #f8d7da'
            elif val == 'LOG_WARN':
                color = 'background-color: #fff3cd'
            elif val == 'LOG_INFO':
                color = 'background-color: #d1ecf1'
            return color

        styled_df = page_df[["timestamp", "process", "message", "severity"]].reset_index(drop=True).style.applymap(
            color_severity, subset=["severity"]
        )
        st.dataframe(styled_df, height=400, use_container_width=True)
    else:
        st.warning("No logs to display.")

    st.download_button("📤 Export Filtered Logs", filtered_df.to_csv(index=False), file_name="filtered_logs.csv")

# --- Main Rendering Logic ---
if MODE == "single":
    path = config.get("bundle_path")
    if not path or not os.path.exists(path):
        st.error("Invalid or missing bundle_path in config.json")
        st.stop()
    df = load_parsed_logs(path)
    if df.empty:
        st.warning("No logs found in parsed bundle.")
    else:
        render_bundle_view(df)

elif MODE == "carousel":
    bundles = config.get("bundle_list", [])
    if not bundles:
        st.error("No bundle_list found in config.json")
        st.stop()

    tabs = st.tabs([b["name"] for b in bundles])
    for i, bundle in enumerate(bundles):
        with tabs[i]:
            df = load_parsed_logs(bundle["path"])
            if df.empty:
                st.warning("No logs found in parsed bundle.")
            else:
                render_bundle_view(df)
else:
    st.error("Invalid mode in config.json")


