import streamlit as st
import pandas as pd
from datetime import datetime, time, date

# Set page config
st.set_page_config(page_title="Everyday Log", layout="wide")

# Mobile-friendly CSS
st.markdown("""
    <style>
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem 0.5rem;
        }
        input, textarea, select {
            font-size: 16px !important;
        }
        label {
            font-size: 15px !important;
        }
    }
    .scroll-container {
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 10px;
        border: 1px solid #ddd;
    }
    .block-container {
        min-width: 1100px;
        display: inline-block;
    }
    .stCheckbox > div {
        padding-top: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "logs" not in st.session_state:
    st.session_state.logs = []

if "delete_flags" not in st.session_state:
    st.session_state.delete_flags = {}

# Define column layout and options
log_columns = [
    ("Time", 2),
    ("Activity", 3),
    ("Mood", 2),
    ("Energy Level", 2),
    ("Focus Level", 2),
    ("Notes", 5)
]
mood_options = ["🙂 Happy", "😐 Neutral", "🙁 Sad", "😤 Stressed", "😴 Tired"]

# Header
st.title("📘 Everyday Log")

# Date selector
selected_date = st.date_input("Select a date to view or add logs", date.today())

# Show editable log entries for selected date
st.subheader(f"Logs for {selected_date}")
st.markdown("Use the checkboxes to select rows for deletion.")

# Filter logs for selected date
today_logs = [log for log in st.session_state.logs if log["Date"] == selected_date]

# Editable form per log
for i, log in enumerate(today_logs):
    row_key = f"{selected_date}_{i}"
    row_cols = st.columns([1, 2, 3, 2, 2, 2, 5])  # 7 columns: checkbox + 6 fields

    checked = row_cols[0].checkbox("", key=f"delete_{row_key}", value=st.session_state.delete_flags.get(f"delete_{row_key}", False))
    st.session_state.delete_flags[f"delete_{row_key}"] = checked

    log["Time"] = row_cols[1].time_input("", value=log["Time"], key=f"time_{row_key}")
    log["Activity"] = row_cols[2].text_input("", value=log["Activity"], key=f"activity_{row_key}")
    log["Mood"] = row_cols[3].selectbox("", mood_options, index=mood_options.index(log["Mood"]), key=f"mood_{row_key}")
    log["Energy Level"] = row_cols[4].select_slider("", options=list(range(1, 11)), value=log.get("Energy Level", 5), key=f"energy_{row_key}")
    log["Focus Level"] = row_cols[5].select_slider("", options=list(range(1, 11)), value=log.get("Focus Level", 5), key=f"focus_{row_key}")
    log["Notes"] = row_cols[6].text_area("", value=log["Notes"], key=f"notes_{row_key}", height=75)

# ➕ Add a new log row
if st.button("➕ Add Row"):
    st.session_state.logs.append({
        "Date": selected_date,
        "Time": time(9, 0),
        "Activity": "",
        "Mood": mood_options[0],
        "Energy Level": 5,
        "Focus Level": 5,
        "Notes": ""
    })

# 🗑 Delete selected rows
if st.button("🗑 Delete Selected Rows"):
    keys_to_delete = [k for k, v in st.session_state.delete_flags.items() if v and str(selected_date) in k]
    if keys_to_delete:
        st.session_state.logs = [
            log for idx, log in enumerate(st.session_state.logs)
            if f"{selected_date}_{idx}" not in keys_to_delete
        ]
        for key in keys_to_delete:
            del st.session_state.delete_flags[key]
        st.success(f"Deleted {len(keys_to_delete)} row(s).")
        st.rerun()
    else:
        st.info("No rows selected for deletion.")

# 📊 Preview as DataFrame
st.markdown("### 📊 Preview (Pandas-style)")
filtered_df = pd.DataFrame([log for log in st.session_state.logs if log["Date"] == selected_date])
if not filtered_df.empty:
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
else:
    st.info("No logs for selected date.")

# 📅 Summary of all logs grouped by date
st.markdown("## 📅 All Logs Summary")
if st.session_state.logs:
    df_all = pd.DataFrame(st.session_state.logs)
    df_all["Date"] = pd.to_datetime(df_all["Date"]).dt.date
    grouped = df_all.groupby("Date")

    for log_date, group in sorted(grouped, reverse=True):
        with st.expander(f"📂 {log_date} ({len(group)} logs)"):
            st.dataframe(group.drop(columns=["Date"]), use_container_width=True, hide_index=True)
else:
    st.info("No logs added yet.")
