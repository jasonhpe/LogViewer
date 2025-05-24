# ---- Stable app.py
import streamlit as st 
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path

st.set_page_config(layout="wide", page_title="LogViewer")
st.title("📋 Log Viewer Dashboard")
st.sidebar.markdown("## 🧾 Available Bundles")

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

        # Display each row as a colored row with inline expandable message
        for _, row in page_df.iterrows():
            sev = row.get("severity", "")
            if sev == 'LOG_ERR':
                bg = "#f8d7da"
            elif sev == 'LOG_WARN':
                bg = "#fff3cd"
            elif sev == 'LOG_INFO':
                bg = "#d1ecf1"
            else:
                bg = "#f2f2f2"

            with st.container():
                cols = st.columns([2, 2, 8])
                cols[0].markdown(f"<div style='background-color:{bg};padding:5px'><b>{row['timestamp']}</b></div>", unsafe_allow_html=True)
                cols[1].markdown(f"<div style='background-color:{bg};padding:5px'>{row['process']}</div>", unsafe_allow_html=True)
                with cols[2].expander(label=row["message"][:100], expanded=False):
                    st.json(row.to_dict())
    else:
        st.warning("No logs to display.")

    
    # Prepare export data
    export_all = filtered_df[["timestamp", "process", "message"]]
    export_page = page_df[["timestamp", "process", "message"]]

    st.download_button(
        "📤 Export Filtered Logs (All)",
        export_all.to_csv(index=False),
        file_name="filtered_logs_all.csv",
        key=f"download_all_btn_{bundle_key}"
    )

    st.download_button(
        "📤 Export Current Page Only",
        export_page.to_csv(index=False),
        file_name="filtered_logs_page.csv",
        key=f"download_page_btn_{bundle_key}"
    )

def render_fastlogs(path, key_prefix="default"):
    fastlog_dir = os.path.join(path, "fastlogs")
    if not os.path.exists(fastlog_dir):
        st.info("No fastlog directory found.")
        return
    files = [f for f in os.listdir(fastlog_dir) if f.endswith(".txt")]
    if not files:
        st.info("No fastlog files found.")
        return
    selected = st.selectbox("Select fastlog file", files, key=f"fastlog_file_{key_prefix}")
    with open(os.path.join(fastlog_dir, selected)) as f:
        content = f.read()
    st.text_area("Fastlog Output", content, height=500, key=f"fastlog_output_{key_prefix}")

def render_diag(path, key_prefix="default"):
    diag_dir = os.path.join(path, "feature")
    if not os.path.exists(diag_dir):
        st.info("No diag directory found.")
        return
    files = [f for f in os.listdir(diag_dir) if f.endswith(".txt")]
    if not files:
        st.info("No diag files found.")
        return
    selected = st.selectbox("Select diagdump file", files, key=f"diag_file_{key_prefix}")
    with open(os.path.join(diag_dir, selected)) as f:
        content = f.read()
    st.text_area("Diag Dump Output", content, height=500, key=f"diag_output_{key_prefix}")

def render_showtech(path, key_prefix="default"):
    showtech_dir = os.path.join(path, "showtech")
    if not os.path.exists(showtech_dir):
        st.info("No showtech directory found.")
        return
    files = [f for f in os.listdir(showtech_dir) if f.endswith(".txt")]
    if not files:
        st.info("No showtech files found.")
        return
    selected = st.selectbox("Select showtech file", files, key=f"showtech_file_{key_prefix}")
    with open(os.path.join(showtech_dir, selected)) as f:
        content = f.read()
    st.text_area("ShowTech Output", content, height=500, key=f"showtech_output_{key_prefix}")

def get_vsf_members(bundle_output_dir):
    members_dir = os.path.join(bundle_output_dir, "members")
    if not os.path.exists(members_dir):
        return []
    return [name for name in os.listdir(members_dir)
            if os.path.isdir(os.path.join(members_dir, name)) and name.startswith("mem_")]

def render_isp_modal(path, key_prefix="default"):
    isp_file = os.path.join(path, "isp.txt")
    if not os.path.exists(isp_file):
        return
    with open(isp_file) as f:
        isp_data = f.read()

    with st.expander("🌐 ISP Summary (from isp.txt)", expanded=False):
        st.text_area("Parsed ISP Data", isp_data, height=300, key=f"isp_data_{key_prefix}")
        
# --- Main Rendering Logic ---
if MODE == "single":
    bundle_list = config.get("bundle_list")
    if not bundle_list:
        # Fallback to legacy support
        single_path = config.get("bundle_path")
        if not single_path or not os.path.exists(single_path):
            st.error("Missing both bundle_list and valid bundle_path in config.json")
            st.stop()
        selected_bundle = {"name": os.path.basename(single_path), "path": single_path}
    else:
        bundle_names = [b["name"] for b in bundle_list]
        selected_bundle_name = st.sidebar.selectbox("📦 Select Support Bundle", bundle_names)
        selected_bundle = next((b for b in bundle_list if b["name"] == selected_bundle_name), None)
        if not selected_bundle:
            st.error("Selected bundle not found.")
            st.stop()

    st.sidebar.markdown("### 🔄 Select Boot Context")
    boot_context = st.sidebar.selectbox("Boot:", ["Current Boot"])
    if boot_context != "Current Boot":
        st.warning("Only 'Current Boot' is implemented.")
        st.stop()

    bundle_path = selected_bundle["path"]
    members = get_vsf_members(bundle_path)
    st.sidebar.markdown("### 🧩 VSF Members")
    if members:
        vsf_member = st.sidebar.selectbox("Member:", ["Main Bundle"] + members)
        if vsf_member == "Main Bundle":
            path = bundle_path
            show_showtech = True
        else:
            path = os.path.join(bundle_path, "members", vsf_member)
            show_showtech = False
    else:
        st.sidebar.write("No VSF members detected.")
        path = bundle_path
        show_showtech = True

    st.markdown(f"### 📦 Bundle: `{selected_bundle['name']}`")
    df = load_parsed_logs(path)
    if df.empty:
        st.warning("No logs found in parsed bundle.")
    else:
        if show_showtech:
            tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])
            with tab1:
                render_bundle_view(df, bundle_key="single")
                render_isp_modal(path, key_prefix="single")
            with tab2:
                render_fastlogs(path, key_prefix="single")
            with tab3:
                render_diag(path, key_prefix="single")
            with tab4:
                render_showtech(path, key_prefix="single")
        else:
            tab1, tab2, tab3 = st.tabs(["Logs", "Fastlogs", "Diag Dumps"])
            with tab1:
                render_bundle_view(df, bundle_key=vsf_member)
            with tab2:
                render_fastlogs(path, key_prefix=vsf_member)
            with tab3:
                render_diag(path, key_prefix=vsf_member)
            

elif MODE == "carousel":
    bundles = config.get("bundle_list", [])
    if not bundles:
        st.error("No bundle_list found in config.json")
        st.stop()

    st.sidebar.markdown("### 📦 Select Support Bundle")
    bundle_names = [b["name"] for b in bundles]
    selected_bundle_name = st.sidebar.selectbox("Bundle:", bundle_names)

    selected_bundle = next((b for b in bundles if b["name"] == selected_bundle_name), None)
    if not selected_bundle:
        st.error("Selected bundle not found.")
        st.stop()

    st.sidebar.markdown("### 🔄 Select Boot Context")
    boot_context = st.sidebar.selectbox("Boot:", ["Current Boot"])
    if boot_context != "Current Boot":
        st.warning("Only 'Current Boot' is implemented.")
        st.stop()

    bundle_path = selected_bundle["path"]
    members = get_vsf_members(bundle_path)
    st.sidebar.markdown("### 🧩 VSF Members")
    if members:
        vsf_member = st.sidebar.selectbox("Member:", ["Main Bundle"] + members)
        if vsf_member == "Main Bundle":
            path = bundle_path
            show_showtech = True
        else:
            path = os.path.join(bundle_path, "members", vsf_member)
            show_showtech = False
    else:
        st.sidebar.write("No VSF members detected.")
        path = bundle_path
        show_showtech = True

    st.markdown(f"### 📦 Bundle: `{selected_bundle['name']}`")
    df = load_parsed_logs(path)
    if df.empty:
        st.warning("No logs found in parsed bundle.")
    else:
        if show_showtech:
            tab1, tab2, tab3, tab4 = st.tabs(["Logs", "Fastlogs", "Diag Dumps", "ShowTech"])
            with tab1:
                render_bundle_view(df, bundle_key=selected_bundle["name"])
                render_isp_modal(path, key_prefix=selected_bundle["name"])
            with tab2:
                render_fastlogs(path, key_prefix=selected_bundle["name"])
            with tab3:
                render_diag(path, key_prefix=selected_bundle["name"])
            with tab4:
                render_showtech(path, key_prefix=selected_bundle["name"])
        else:
            tab1, tab2, tab3 = st.tabs(["Logs", "Fastlogs", "Diag Dumps"])
            with tab1:
                render_bundle_view(df, bundle_key=vsf_member)
            with tab2:
                render_fastlogs(path, key_prefix=vsf_member)
            with tab3:
                render_diag(path, key_prefix=vsf_member)
else:
    st.error("Invalid mode in config.json")
