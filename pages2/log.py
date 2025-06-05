import streamlit as st
from utils import is_logged_in
from utils import show_sidebar
from datetime import datetime,date
import pandas as pd


def run():
    if not is_logged_in():
        st.switch_page("option.py")


    st.title("📘 Everyday Log (Tabular + Summary by Date)")

    log_columns = [
        ("Date", 150),
        ("Time", 120),
        ("Activity", 200),
        ("Duration (mins)", 150),
        ("Mood", 150),
        ("Notes", 300)
    ]

    def create_default_log(selected_date=None):
        return {
            "Date": selected_date or datetime.today().date(),
            "Time": datetime.now().time().replace(second=0, microsecond=0),
            "Activity": "",
            "Duration (mins)": "",
            "Mood": "",
            "Notes": ""
        }

    if "logs" not in st.session_state:
        st.session_state.logs = []

    # 📅 Date Filter
    selected_date = st.date_input("📅 Select a date to view/edit logs:", date.today())
    filtered_logs = [log for log in st.session_state.logs if log["Date"] == selected_date]

    # Add default row if none exist for selected date
    if not filtered_logs:
        new_log = create_default_log(selected_date)
        st.session_state.logs.append(new_log)
        filtered_logs = [new_log]

    # 🔧 CSS for scroll and layout
    st.markdown("""
        <style>
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
        .column-header {
            font-weight: bold;
            padding: 6px 4px;
        }
        .column-input input, .column-input textarea {
            width: 100% !important;
            min-height: 38px;
        }
        </style>
        """, unsafe_allow_html=True)

    # ➕ Add/Delete Log Row for selected date
    def add_log_row():
        st.session_state.logs.append(create_default_log(selected_date))

    def delete_log_row(index):
        logs_on_selected_date = [i for i, log in enumerate(st.session_state.logs) if log["Date"] == selected_date]
        if index < len(logs_on_selected_date):
            del st.session_state.logs[logs_on_selected_date[index]]

    st.button("➕ Add Log", on_click=add_log_row)

    # 🎯 Editable Log Table for Selected Date
    st.markdown("#### 📝 Logs for Selected Date")
    with st.container():
        st.markdown('<div class="scroll-container"><div class="block-container">', unsafe_allow_html=True)

        header_cols = st.columns([w for _, w in log_columns] + [80])
        for i, (col_name, _) in enumerate(log_columns):
            header_cols[i].markdown(f"<div class='column-header'>{col_name}</div>", unsafe_allow_html=True)
        header_cols[-1].markdown("<div class='column-header'>Action</div>", unsafe_allow_html=True)

        row_counter = 0
        for i, log in enumerate(st.session_state.logs):
            if log["Date"] != selected_date:
                continue
            row_cols = st.columns([w for _, w in log_columns] + [80])
            for j, (col, _) in enumerate(log_columns):
                key = f"{col}_{i}"
                with row_cols[j]:
                    st.markdown("<div class='column-input'>", unsafe_allow_html=True)
                    if col == "Date":
                        log[col] = st.date_input("", value=log[col], key=key)
                    elif col == "Time":
                        log[col] = st.time_input("", value=log[col], key=key)
                    elif col == "Notes":
                        lines = log[col].count('\n') + 1
                        log[col] = st.text_area("", value=log[col], key=key)
                    else:
                        log[col] = st.text_input("", value=log[col], key=key)
                    st.markdown("</div>", unsafe_allow_html=True)
            if row_cols[-1].button("🗑️", key=f"delete_{i}"):
                delete_log_row(row_counter)
                st.rerun()
            row_counter += 1

        st.markdown('</div></div>', unsafe_allow_html=True)

    # 💾 Save Button
    if st.button("💾 Save Logs"):
        st.success("Logs saved for this session!")


    # 📊 Collapsible Summary by Date
    st.markdown("## 📅 All Logs Summary (Grouped by Date)")
    if st.session_state.logs:
        df_all = pd.DataFrame(st.session_state.logs)
        df_all["Date"] = pd.to_datetime(df_all["Date"]).dt.date
        grouped = df_all.groupby("Date")

        for date_group, group_df in sorted(grouped, reverse=True):
            with st.expander(f"📂 {date_group} ({len(group_df)} logs)"):
                st.dataframe(group_df.drop(columns=["Date"]), use_container_width=True, hide_index=True)
    else:
        st.info("No logs available yet.")

