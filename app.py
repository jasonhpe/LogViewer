import io
import streamlit as st 
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path

st.set_page_config(layout="wide", page_title="LogViewer")
st.title("📋 Log Viewer Dashboard")

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

def render_bundle_view(df, bundle_key):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        proc_filter = st.selectbox("Filter by Process", ["All"] + sorted(df['process'].dropna().unique().tolist()), key=f"proc_filter_{bundle_key}")
    with col2:
        keyword = st.text_input("Keyword Search", key=f"keyword_{bundle_key}")
    with col3:
        include_fastlogs = st.checkbox("Include Fastlogs", value=True, key=f"include_fastlogs_{bundle_key}")

    if "timestamp" in df.columns:
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors='coerce')
        min_date = df["timestamp_dt"].min().to_pydatetime()
        max_date = df["timestamp_dt"].max().to_pydatetime()
        start_date, end_date = st.slider("Time Range", min_value=min_date, max_value=max_date,
                                         value=(min_date, max_date), format="YYYY-MM-DD HH:mm",
                                         key=f"date_slider_{bundle_key}")
    else:
        start_date, end_date = None, None

    filtered_df = apply_filters(df, proc_filter, keyword, include_fastlogs, start_date, end_date)

    st.subheader("📈 Errors per Hour")
    if "severity" in filtered_df.columns:
        error_logs = filtered_df[filtered_df['severity'] == 'LOG_ERR']
        if not error_logs.empty:
            error_logs = error_logs.copy()
            error_logs['hour'] = error_logs['timestamp_dt'].dt.strftime("%Y-%m-%d %H")
            chart_data = error_logs.groupby('hour').size().rename("count").reset_index()
            st.line_chart(chart_data.set_index('hour'))
        else:
            st.info("No LOG_ERR entries in this view.")
    else:
        st.info("No severity field in logs.")

    logs_per_page = 100
    total_pages = (len(filtered_df) + logs_per_page - 1) // logs_per_page
    current_page = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=1,
                                   key=f"page_num_{bundle_key}")

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

    export_buffer = io.StringIO()
    export_buffer.write(filtered_df.to_string(index=False))
    export_buffer.seek(0)

    st.download_button(
        "📤 Export Filtered Logs",
        data=export_buffer,
        file_name="filtered_logs.txt",
        mime="text/plain",
        key=f"download_btn_{bundle_key}"
    )

def render_fastlogs(path, bundle_key="default"):
    fastlog_dir = os.path.join(path, "fastlogs")
    if not os.path.exists(fastlog_dir):
        st.info("No fastlog directory found.")
        return
    files = [f for f in os.listdir(fastlog_dir) if f.endswith(".txt")]
    if not files:
        st.info("No fastlog files found.")
        return
    selected = st.selectbox("Select fastlog file", files, key=f"fastlog_file_{bundle_key}")
    with open(os.path.join(fastlog_dir, selected)) as f:
        content = f.read()
    st.text_area("Fastlog Output", content, height=500, key=f"fastlog_output_{bundle_key}")

def render_diag(path, bundle_key="default"):
    diag_dir = os.path.join(path, "feature")
    if not os.path.exists(diag_dir):
        st.info("No diag directory found.")
        return
    files = [f for f in os.listdir(diag_dir) if f.endswith(".txt")]
    if not files:
        st.info("No diag files found.")
        return
    selected = st.selectbox("Select diagdump file", files, key=f"diag_file_{bundle_key}")
    with open(os.path.join(diag_dir, selected)) as f:
        content = f.read()
    st.text_area("Diag Dump Output", content, height=500, key=f"diag_output_{bundle_key}")

def render_showtech(path, bundle_key="default"):
    showtech_dir = os.path.join(path, "showtech")
    if not os.path.exists(showtech_dir):
        st.info("No showtech directory found.")
        return
    files = [f for f in os.listdir(showtech_dir) if f.endswith(".txt")]
    if not files:
        st.info("No showtech files found.")
        return
    selected = st.selectbox("Select showtech file", files, key=f"showtech_file_{bundle_key}")
    with open(os.path.join(showtech_dir, selected)) as f:
        content = f.read()
    st.text_area("ShowTech Output", content, height=500, key=f"showtech_output_{bundle_key}")

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
        tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])
        with tab1:
            render_bundle_view(df, bundle_key="single")
        with tab2:
            render_fastlogs(path, bundle_key="single")
        with tab3:
            render_diag(path, bundle_key="single")
        with tab4:
            render_showtech(path, bundle_key="single")

elif MODE == "carousel":
    bundles = config.get("bundle_list", [])
    if not bundles:
        st.error("No bundle_list found in config.json")
        st.stop()

    tabs = st.tabs([b["name"] for b in bundles])
    for i, bundle in enumerate(bundles):
        with tabs[i]:
            st.markdown(f"### 📦 Bundle: `{bundle['name']}`")
            df = load_parsed_logs(bundle["path"])
            if df.empty:
                st.warning("No logs found in parsed bundle.")
            else:
                tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])
                with tab1:
                    render_bundle_view(df, bundle_key=bundle["name"])
                with tab2:
                    render_fastlogs(bundle["path"], bundle_key=bundle["name"])
                with tab3:
                    render_diag(bundle["path"], bundle_key=bundle["name"])
                with tab4:
                    render_showtech(bundle["path"], bundle_key=bundle["name"])
else:
    st.error("Invalid mode in config.json")



