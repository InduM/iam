import streamlit as st
from utils import is_logged_in
from datetime import datetime,date
import pandas as pd


def run():
     # ➕ Add/Delete Log Row for selected date
    def add_log_row():
        st.session_state.logs.append(create_default_log(selected_date))

    if not is_logged_in():
        st.switch_page("option.py")

    st.title("📘 Everyday Log")

    log_columns = [
        ("Date",200),
        ("Time", 200),
        ("Project Name",200),
        ("Client Name",200),
        ("Priority", 200),
        ("Description", 200),
        ("Category", 300),
        ("Follow up", 300)
    ]

    def create_default_log(selected_date=None):
        return {
            "Date": selected_date or datetime.today().date(),
            "Time": datetime.now().time().replace(second=0, microsecond=0),
            "Project Name":"",
            "Client Name": "",
            "Priority": "",
            "Description":"",
            "Category":"",
            "Follow up": ""
        }

    if "logs" not in st.session_state:
        st.session_state.logs = []

    # 📅 Date Filter
    # Row: Date selector + Add Row button side by side
    col1, col2 = st.columns([6, 1])
    with col1:
        selected_date = st.date_input("",date.today(),label_visibility="collapsed")
    with col2:
        st.button("➕ Log", on_click=add_log_row)

    filtered_logs = [log for log in st.session_state.logs if log["Date"] == selected_date]

    # Add default row if none exist for selected date
    if not filtered_logs:
        new_log = create_default_log(selected_date)
        st.session_state.logs.append(new_log)
        filtered_logs = [new_log]
    
   
    def delete_log_row(index):
        logs_on_selected_date = [i for i, log in enumerate(st.session_state.logs) if log["Date"] == selected_date]
        if index < len(logs_on_selected_date):
            del st.session_state.logs[logs_on_selected_date[index]]


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
            row_cols = st.columns([w for _, w in log_columns]+[50])
            for j, (col, _) in enumerate(log_columns):
                key = f"{col}_{i}"
                with row_cols[j]:
                    st.markdown("<div class='column-input'>", unsafe_allow_html=True)
                    if col == "Date":
                        log[col] = st.date_input("", value=log[col], key=key)
                    elif col == "Time":
                        log[col] = st.time_input("", value=log[col], key=key)
                    elif col == "Priority":
                        priority_options = ["Low", "Medium", "High"]
                        log[col] = st.selectbox("", options=priority_options, key=key)
                    elif col == "Category":
                        category_options = ["Audit-Physical","Audit-Digital","Audit-Design","Audit-Accessibility", "Audit-Policy", "Training-Onwards","Training-Regular","Sessions-Kiosk","Sessions-Sensitization","Sessions-Awareness","Recruitment","Other"]
                        log[col] = st.selectbox("", options=category_options, key=key)
                        if log[col] == "Other":
                            custom_mood = st.text_input("Specify Other")
                            log[col] = custom_mood

                    elif col == "Client Name " or col == "Project Name":
                        log[col] = st.text_input("",value = log[col],key = key)
                    else:
                        log[col] = st.text_area("", value=log[col], key=key)
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

