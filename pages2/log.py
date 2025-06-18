import streamlit as st
from utils import is_logged_in
from datetime import datetime, date, time
from pymongo import MongoClient
import certifi

def run():
    # ✅ MongoDB connection
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["user_db"]
    logs_collection = db["logs"]

    def create_default_log():
        return {
            "Time": datetime.now().strftime("%H:%M"),
            "Project Name": "",
            "Client Name": "",
            "Priority": "",
            "Description": "",
            "Category": "",
            "Follow up": ""
        }

    # ✅ Check login
    if not is_logged_in():
        st.switch_page("option.py")

    username = st.session_state["username"]
    
    st.title("📘 Everyday Log")

    log_columns = [
        ("Time", 200),("Project Name", 200),("Client Name", 200),("Priority", 200),
        ("Description", 200),("Category", 300),("Follow up", 300)
    ]

    # ✅ Session state setup
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    if "last_selected_date" not in st.session_state:
        st.session_state.last_selected_date = None

    if "logs" not in st.session_state:
        st.session_state.logs = []

    if "refresh_triggered" not in st.session_state:
        st.session_state.refresh_triggered = False

    # Set default using a temporary variable, not directly in session state
    default_date = date.today()
    # ✅ Datepicker & Buttons
    col1, col2, col3 = st.columns([5, 1, 2])
    with col1:
        selected_date = st.date_input("", value=st.session_state.get("selected_date", default_date), key="selected_date", label_visibility="collapsed")
    with col2:
        st.button("➕ Log", on_click=lambda: st.session_state.logs.append(create_default_log()))
    with col3:
        def refresh_logs():
            with st.spinner("Refreshing logs..."):
                query = {"Date": selected_date.strftime("%Y-%m-%d"), "Username": username}
                st.session_state.logs = list(logs_collection.find(query, {"_id": 0, "Date": 0, "Username": 0}))
                if not st.session_state.logs:
                    st.session_state.logs.append(create_default_log())
                st.session_state.last_selected_date = selected_date
                st.session_state.refresh_triggered = False

        if st.button("🔄 Refresh") and not st.session_state.refresh_triggered:
            st.session_state.refresh_triggered = True
            refresh_logs()

    selected_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")

    # ✅ Fetch logs on first load or when date changes
    if st.session_state.last_selected_date != st.session_state.selected_date:
        st.session_state.logs = []
        query = {"Date": selected_date_str, "Username": username}
        for log in logs_collection.find(query, {"_id": 0, "Date": 0, "Username": 0}):
            st.session_state.logs.append(log)
        if not st.session_state.logs:
            st.session_state.logs.append(create_default_log())
        st.session_state.last_selected_date = st.session_state.selected_date

    def delete_log_row(index):
        log_to_delete = st.session_state.logs[index]
        logs_collection.delete_one({
            "Date": selected_date_str,
            "Time": log_to_delete["Time"],
            "Username": username
        })
        del st.session_state.logs[index]

    # ✅ Log table
    st.markdown("#### 📝 Logs for Selected Date")
    with st.container():
        st.markdown('<div class="scroll-container"><div class="block-container">', unsafe_allow_html=True)

        header_cols = st.columns([w for _, w in log_columns] + [80])
        for i, (col_name, _) in enumerate(log_columns):
            header_cols[i].markdown(f"<div class='column-header'>{col_name}</div>", unsafe_allow_html=True)
        header_cols[-1].markdown("<div class='column-header'>Action</div>", unsafe_allow_html=True)

        for i, log in enumerate(st.session_state.logs):
            row_cols = st.columns([w for _, w in log_columns] + [50])
            for j, (col, _) in enumerate(log_columns):
                key = f"{col}_{i}"
                with row_cols[j]:
                    st.markdown("<div class='column-input'>", unsafe_allow_html=True)

                    if col == "Time":
                        if isinstance(log[col], str):
                            log_time = datetime.strptime(log[col], "%H:%M").time()
                        elif isinstance(log[col], datetime):
                            log_time = log[col].time()
                        elif isinstance(log[col], time):
                            log_time = log[col]
                        else:
                            log_time = datetime.now().time().replace(second=0, microsecond=0)
                        new_time = st.time_input("", value=log_time, key=key, label_visibility="collapsed")
                        log[col] = new_time.strftime("%H:%M")

                    elif col == "Priority":
                        options = ["Low", "Medium", "High"]
                        log[col] = st.selectbox("", options=options, key=key, label_visibility="collapsed")

                    elif col == "Category":
                        options = ["Audit-Physical", "Audit-Digital", "Audit-Design", "Audit-Accessibility",
                                   "Audit-Policy", "Training-Onwards", "Training-Regular", "Sessions-Kiosk",
                                   "Sessions-Sensitization", "Sessions-Awareness", "Recruitment", "Other"]
                        log[col] = st.selectbox("", options=options, key=key, label_visibility="collapsed")
                        if log[col] == "Other":
                            custom = st.text_input("Specify Other", label_visibility="collapsed", key=key + "_custom")
                            log[col] = custom

                    elif col in ["Client Name", "Project Name"]:
                        log[col] = st.text_input("", value=log[col], key=key, label_visibility="collapsed")

                    else:
                        log[col] = st.text_area("", value=log[col], key=key, label_visibility="collapsed")

                    st.markdown("</div>", unsafe_allow_html=True)

            if row_cols[-1].button("🗑️", key=f"delete_{i}"):
                delete_log_row(i)
                st.rerun()

        st.markdown('</div></div>', unsafe_allow_html=True)

    # ✅ Save logs
    if st.button("💾 Save Logs"):
        logs_collection.delete_many({"Date": selected_date_str, "Username": username})
        for log in st.session_state.logs:
            log_with_meta = {"Date": selected_date_str, "Username": username, **log}
            logs_collection.insert_one(log_with_meta)
        st.success("Logs saved to MongoDB successfully!")
