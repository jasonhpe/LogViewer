import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

@st.cache_data
def load_logs():
    try:
        with open("parsed_logs.json") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to load logs: {e}")
        return pd.DataFrame()

@st.cache_data
def load_file_text(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"❌ Failed to load {filepath}: {e}"

def format_timestamp(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

st.set_page_config(layout="wide", page_title="LogViewer")
st.title("📋 Log Viewer Dashboard")

tabs = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])

# --- LOG TAB ---
with tabs[0]:
    df = load_logs()
    if df.empty:
        st.stop()

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        proc_filter = st.selectbox("Filter by Process", ["All"] + sorted(df['process'].dropna().unique().tolist()))
    with col2:
        keyword = st.text_input("Keyword Search")
    with col3:
        include_fastlogs = st.checkbox("Include Fastlogs", value=True)

    # Date Range
    if "timestamp" in df.columns:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors='coerce')
        min_date = df["timestamp_dt"].min().to_pydatetime()
        max_date = df["timestamp_dt"].max().to_pydatetime()
        start_date, end_date = st.slider("Time Range", min_value=min_date, max_value=max_date,
                                         value=(min_date, max_date), format="YYYY-MM-DD HH:mm")
    else:
        start_date, end_date = None, None

    # Filtering
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

    # Chart
    st.subheader("📈 Errors per Hour")
    error_logs = filtered_df[filtered_df['severity'] == 'LOG_ERR']
    if not error_logs.empty:
        error_logs['hour'] = error_logs['timestamp_dt'].dt.strftime("%Y-%m-%d %H")
        chart_data = error_logs.groupby('hour').size().rename("count").reset_index()
        st.line_chart(chart_data.set_index('hour'))
    else:
        st.info("No LOG_ERR entries in this view.")

    # Pagination
    logs_per_page = 100
    total_pages = (len(filtered_df) + logs_per_page - 1) // logs_per_page
    current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)

    start = (current_page - 1) * logs_per_page
    end = start + logs_per_page
    page_df = filtered_df.iloc[start:end].copy()

    # Display logs
    st.subheader(f"📝 Logs (Page {current_page}/{total_pages})")
    if not page_df.empty:
        page_df["timestamp"] = page_df["timestamp"].apply(format_timestamp)
        st.dataframe(page_df[["timestamp", "process", "message", "severity"]].reset_index(drop=True), height=400)
    else:
        st.warning("No logs to display.")

    # Download
    st.download_button("📤 Export Filtered Logs", filtered_df.to_csv(index=False), file_name="filtered_logs.csv")

# --- FASTLOG TAB ---
with tabs[1]:
    st.subheader("⚡ Fastlogs")
    fastlog_dir = "fastlogs"
    if os.path.isdir(fastlog_dir):
        fastlog_files = [f for f in os.listdir(fastlog_dir) if f.endswith(".supportlog")]
        selected_fastlog = st.selectbox("Select Fastlog", fastlog_files)
        if selected_fastlog:
            content = load_file_text(os.path.join(fastlog_dir, selected_fastlog))
            st.text_area("Fastlog Content", value=content, height=400)
    else:
        st.warning("No fastlogs directory found.")

# --- DIAG DUMP TAB ---
with tabs[2]:
    st.subheader("🛠️ Diag Dumps")
    diag_dir = "feature"
    diag_files = [f for f in os.listdir(diag_dir) if f.endswith("_diagdump.txt")] if os.path.isdir(diag_dir) else []
    selected_diag = st.selectbox("Select Diag Dump", diag_files)
    if selected_diag:
        content = load_file_text(os.path.join(diag_dir, selected_diag))
        st.text_area("Diag Dump Content", value=content, height=400)

# --- SHOWTECH TAB ---
with tabs[3]:
    st.subheader("📄 ShowTech Output")
    showtech_file = "showtech.txt"
    if os.path.isfile(showtech_file):
        content = load_file_text(showtech_file)
        st.text_area("ShowTech Content", value=content, height=500)
    else:
        st.warning("No showtech.txt file found.")
