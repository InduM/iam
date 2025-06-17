import streamlit as st
from utils import is_logged_in
from datetime import datetime, date, time
from pymongo import MongoClient
import certifi

def run():
    # MongoDB setup
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["user_db"]
    logs_collection = db["logs"]

    # Authentication check
    if not is_logged_in():
        st.switch_page("option.py")

    user_id = st.session_state.user["email"]
    st.title("📘 Everyday Log")

    log_columns = [
        ("Date", 200), ("Time", 200), ("Project Name", 200), ("Client Name", 200),
        ("Priority", 200), ("Description", 200), ("Category", 300), ("Follow up", 300)
    ]

    def create_default_log(selected_date=None):
        return {
            "user_id": user_id,
            "Date": selected_date or date.today(),
            "Time": datetime.now().time().replace(second=0, microsecond=0),
            "Project Name": "",
            "Client Name": "",
            "Priority": "",
            "Description": "",
            "Category": "",
            "Follow up": ""
        }

    def add_log_row():
        st.session_state.logs.append(create_default_log(selected_date))

    # UI: Date selector and Add button
    col1, col2 = st.columns([6, 1])
    with col1:
        selected_date = st.date_input("", date.today(), label_visibility="collapsed")
    with col2:
        st.button("➕ Log", on_click=add_log_row)

    # Load logs from MongoDB
    if "logs" not in st.session_state or st.session_state.get("last_loaded_date") != selected_date:
        st.session_state.logs = []
        start_dt = datetime.combine(selected_date, time.min)
        end_dt = datetime.combine(selected_date, time.max)

        query = {"user_id": user_id, "Date": {"$gte": start_dt, "$lt": end_dt}}
        for log in logs_collection.find(query, {"_id": 0}):
            log["Date"] = log["Date"].date()
            st.session_state.logs.append(log)

        if not st.session_state.logs:
            st.session_state.logs.append(create_default_log(selected_date))

        st.session_state.last_loaded_date = selected_date

    def delete_log_row(index):
        logs_on_date = [i for i, log in enumerate(st.session_state.logs) if log["Date"] == selected_date]
        if index < len(logs_on_date):
            log_to_delete = st.session_state.logs[logs_on_date[index]]
            logs_collection.delete_one({
                "user_id": user_id,
                "Date": {
                    "$gte": datetime.combine(log_to_delete["Date"], time.min),
                    "$lt": datetime.combine(log_to_delete["Date"], time.max)
                },
                "Time": log_to_delete["Time"]
            })
            del st.session_state.logs[logs_on_date[index]]

    # Editable table
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
            row_cols = st.columns([w for _, w in log_columns] + [50])
            for j, (col, _) in enumerate(log_columns):
                key = f"{col}_{i}"
                with row_cols[j]:
                    st.markdown("<div class='column-input'>", unsafe_allow_html=True)
                    if col == "Date":
                        log[col] = st.date_input("", value=log[col], key=key, label_visibility="collapsed")
                    elif col == "Time":
                        log[col] = st.time_input("", value=log[col], key=key, label_visibility="collapsed")
                    elif col == "Priority":
                        options = ["Low", "Medium", "High"]
                        index = options.index(log[col]) if log[col] in options else 0
                        log[col] = st.selectbox("", options, index=index, key=key, label_visibility="collapsed")
                    elif col == "Category":
                        options = ["Audit-Physical", "Audit-Digital", "Audit-Design", "Audit-Accessibility",
                                   "Audit-Policy", "Training-Onwards", "Training-Regular", "Sessions-Kiosk",
                                   "Sessions-Sensitization", "Sessions-Awareness", "Recruitment", "Other"]
                        index = options.index(log[col]) if log[col] in options else len(options) - 1
                        log[col] = st.selectbox("", options, index=index, key=key, label_visibility="collapsed")
                        if log[col] == "Other":
                            custom = st.text_input("Specify Other", label_visibility="collapsed", key=key + "_custom")
                            log[col] = custom
                    elif col in ["Client Name", "Project Name"]:
                        log[col] = st.text_input("", value=log[col], key=key, label_visibility="collapsed")
                    else:
                        log[col] = st.text_area("", value=log[col], key=key, label_visibility="collapsed")
                    st.markdown("</div>", unsafe_allow_html=True)
            if row_cols[-1].button("🗑️", key=f"delete_{i}"):
                delete_log_row(row_counter)
                st.rerun()
            row_counter += 1

        st.markdown('</div></div>', unsafe_allow_html=True)

    # Save button: overwrite logs in MongoDB
    if st.button("💾 Save Logs"):
        logs_collection.delete_many({
            "user_id": user_id,
            "Date": {
                "$gte": datetime.combine(selected_date, time.min),
                "$lt": datetime.combine(selected_date, time.max)
            }
        })
        for log in st.session_state.logs:
            if log["Date"] == selected_date:
                mongo_log = log.copy()
                mongo_log["Date"] = datetime.combine(log["Date"], time.min)
                logs_collection.insert_one(mongo_log)
        st.success("Logs saved to MongoDB successfully!")
