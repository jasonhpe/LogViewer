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

def format_timestamp(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

st.set_page_config(layout="wide", page_title="LogViewer")
st.title("📋 Log Viewer Dashboard")

tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])

with tab1:
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
                color = 'background-color: #f8d7da'  # light red
            elif val == 'LOG_WARN':
                color = 'background-color: #fff3cd'  # light yellow
            elif val == 'LOG_INFO':
                color = 'background-color: #d1ecf1'  # light blue
            return color

    styled_df = page_df[["timestamp", "process", "message", "severity"]].reset_index(drop=True).style.applymap(
        color_severity, subset=["severity"]
    )
    st.dataframe(styled_df, height=400, use_container_width=True)

        
        else:
            st.warning("No logs to display.")

    st.download_button("📤 Export Filtered Logs", filtered_df.to_csv(index=False), file_name="filtered_logs.csv")

with tab2:
    st.subheader("⚡ Fastlogs")
    fastlog_files = [f for f in os.listdir("fastlogs") if f.endswith(".supportlog.txt")]
    if fastlog_files:
        selected = st.selectbox("Select fastlog file", fastlog_files)
        with open(os.path.join("fastlogs", selected)) as f:
            content = f.read()
        st.text_area("Fastlog Output", content, height=500)
    else:
        st.info("No fastlog files found in ./fastlogs")

with tab3:
    st.subheader("🛠️ Diag Dumps")
    diag_files = [f for f in os.listdir("feature") if f.endswith(".txt")]
    if diag_files:
        selected = st.selectbox("Select diagdump file", diag_files)
        with open(os.path.join("feature", selected)) as f:
            content = f.read()
        st.text_area("Diag Dump Output", content, height=500)
    else:
        st.info("No diagdump files found in ./feature")

with tab4:
    st.subheader("📄 ShowTech Output")
    showtech_files = [f for f in os.listdir("showtech") if f.endswith(".txt")]
    if showtech_files:
        selected = st.selectbox("Select ShowTech file", showtech_files)
        with open(os.path.join("showtech", selected)) as f:
            content = f.read()
        st.text_area("ShowTech Output", content, height=500)
    else:
        st.info("No showtech files found in ./showtech")

