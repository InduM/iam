import streamlit as st
from utils import is_logged_in
from datetime import datetime, date, timedelta
from pymongo import MongoClient
import certifi


def run():
    # ✅ MongoDB connection
    MONGO_URI = st.secrets["MONGO_URI"]
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["user_db"]
    logs_collection = db["logs"]
    users_collection = db["users"]
    clients_collection = db["clients"]  # Add clients collection

    def create_default_log():
        return {
            "Time": datetime.now().strftime("%H:%M"),
            "Project Name": "",
            "Client Name": "",
            "Priority": "",
            "Description": "",
            "Category": "",
            "Status": "",
            "Follow up": ""
        }

    # ✅ Login check
    if not is_logged_in():
        st.switch_page("option.py")

    username = st.session_state["username"]
    log_columns = [
        ("Time", 200), ("Project Name", 200), ("Client Name", 200), ("Priority", 200),
        ("Description", 200), ("Category", 300), ("Status", 150), ("Follow up", 300)
    ]
    user_doc = users_collection.find_one({"username": username})
    assigned_projects = user_doc.get("project", []) if user_doc else []
    if isinstance(assigned_projects, str):
        assigned_projects = [assigned_projects]

    # ✅ Fetch client names and details from MongoDB
    @st.cache_data(ttl=300)  # Cache for 5 minutes to improve performance
    def get_client_data():
        try:
            # Fetch clients with all necessary fields
            clients = list(clients_collection.find({}, {
                "client_name": 1, 
                "spoc_name": 1, 
                "email": 1, 
                "phone_number": 1, 
                "_id": 0
            }))
            
            # Create a dictionary for easy lookup
            client_dict = {}
            client_names = []
            
            for client in clients:
                if client.get("client_name"):
                    client_name = client.get("client_name", "")
                    client_names.append(client_name)
                    client_dict[client_name] = {
                        "spoc_name": client.get("spoc_name", ""),
                        "email": client.get("email", ""),
                        "phone_number": client.get("phone_number", "")
                    }
            
            return sorted(client_names), client_dict
        except Exception as e:
            st.error(f"Error fetching clients: {e}")
            return [], {}

    # ✅ Get user's assigned projects
    def get_user_projects():
        try:
            # Return sorted list of assigned projects
            if assigned_projects:
                return sorted(assigned_projects)
            else:
                return []
        except Exception as e:
            st.error(f"Error getting user projects: {e}")
            return []

    client_names, client_dict = get_client_data()
    user_projects = get_user_projects()

    # ✅ Session state setup
    if "last_selected_date" not in st.session_state:
        st.session_state.last_selected_date = None
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "refresh_triggered" not in st.session_state:
        st.session_state.refresh_triggered = False

    # ✅ Datepicker & control buttons
    today = date.today()
    default_date = today
    start_of_week = today - timedelta(days=today.weekday())
    start_of_prev_week = start_of_week - timedelta(days=7)
    end_of_week = start_of_week + timedelta(days=6)

    col1, col2, col3 = st.columns([5, 1, 2])
    with col1:
        selected_date = st.date_input("Select Date", value=default_date, key="selected_date", label_visibility="collapsed")
        can_add_log = start_of_prev_week <= selected_date <= end_of_week

    with col2:
        st.button("➕ Log", on_click=lambda: st.session_state.logs.append(create_default_log()), disabled=not can_add_log)

    with col3:
        def refresh_logs():
            with st.spinner("Refreshing logs..."):
                query = {"Date": selected_date.strftime("%Y-%m-%d"), "Username": username}
                fetched_logs = list(logs_collection.find(query, {"_id": 0, "Date": 0, "Username": 0}))
                st.session_state.logs = []
                for log in fetched_logs:
                    # Ensure all required fields exist with default values
                    default_log = create_default_log()
                    for key in default_log:
                        if key not in log:
                            log[key] = default_log[key]
                    st.session_state.logs.append(log)
                if not st.session_state.logs:
                    st.session_state.logs.append(create_default_log())
                st.session_state.last_selected_date = selected_date
                st.session_state.refresh_triggered = False

        if st.button("🔄 Refresh") and not st.session_state.refresh_triggered:
            st.session_state.refresh_triggered = True
            refresh_logs()

    selected_date_str = st.session_state.selected_date.strftime("%Y-%m-%d")

    # ✅ Fetch logs on date change
    if st.session_state.last_selected_date != st.session_state.selected_date:
        st.session_state.logs = []
        query = {"Date": selected_date_str, "Username": username}
        for log in logs_collection.find(query, {"_id": 0, "Date": 0, "Username": 0}):
            # Ensure all required fields exist with default values
            default_log = create_default_log()
            for key in default_log:
                if key not in log:
                    log[key] = default_log[key]
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

    # ✅ Initialize session state for tracking client selections
    if "client_selections" not in st.session_state:
        st.session_state.client_selections = {}

    # ✅ Log table
    with st.container():
        st.markdown('<div class="scroll-container"><div class="block-container">', unsafe_allow_html=True)
        for i, log in enumerate(st.session_state.logs):
                log["Time"] = datetime.now().strftime("%H:%M")
                summary = f"{log.get('Time', '--')} | {log.get('Project Name', 'No Project')} | {log.get('Status', '') or 'No Status'}"
                with st.expander(f"Log Entry {i+1} — {summary}", expanded=True):
                    col_left, col_right = st.columns(2)

                    def render_input(col_widget, field, widget_key):
                        if field == "Time":
                            log_time = datetime.strptime(log[field], "%H:%M").time() if isinstance(log[field], str) else log.get(field, datetime.now().time())
                            new_time = col_widget.time_input("Time", value=log_time, key=widget_key)
                            log[field] = new_time.strftime("%H:%M")

                        elif field == "Priority":
                            options = ["Low", "Medium", "High"]
                            idx = options.index(log[field]) if log[field] in options else 0
                            log[field] = col_widget.selectbox("Priority", options=options, index=idx, key=widget_key)

                        elif field == "Category":
                            options = [
                                "Audit-Physical", "Audit-Digital", "Audit-Design", "Audit-Accessibility",
                                "Audit-Policy", "Training-Onwards", "Training-Regular", "Sessions-Kiosk",
                                "Sessions-Sensitization", "Sessions-Awareness", "Recruitment", "Other"
                            ]
                            idx = options.index(log[field]) if log[field] in options else 0
                            selected = col_widget.selectbox("Category", options=options, index=idx, key=widget_key)
                            if selected == "Other":
                                custom = col_widget.text_input("Specify Other Category", key=widget_key + "_custom")
                                log[field] = custom
                            else:
                                log[field] = selected

                        elif field == "Status":
                            options = ["", "Completed", "InProgress", "Incomplete"]
                            idx = options.index(log[field]) if log[field] in options else 0
                            log[field] = col_widget.selectbox("Status", options=options, index=idx, key=widget_key)

                        elif field == "Client Name":
                            options = [""] + client_names
                            idx = options.index(log[field]) if log[field] in options else 0
                            selected_client = col_widget.selectbox("Client Name", options=options, index=idx, key=widget_key, on_change=None)
                            log[field] = selected_client
                            
                            # Display SPOC information immediately when client is selected
                            if selected_client and selected_client in client_dict:
                                client_info = client_dict[selected_client]
                                print("CLIENT INFO: ",client_info)
                                spoc_name = client_info.get("spoc_name", "")
                                spoc_email = client_info.get("email", "")
                                spoc_phone = client_info.get("phone_number", "")
                                
                                if spoc_name or spoc_email or spoc_phone:
                                    print(spoc_name, spoc_email, spoc_phone)
                                    display_string=[]
                                    col_widget.markdown("**📞 SPOC Details:**")
                                    if spoc_name:
                                        #col_widget.info(f"**👤 Name:** {spoc_name}")
                                        display_string.append(f"**👤 Name:** {spoc_name}\n")
                                    if spoc_email:
                                        display_string.append(f"**📧 Email:** {spoc_email}\n")
                                    if spoc_phone:
                                        display_string.append(f"**📱 Phone:** {spoc_phone}")
                                    col_widget.info('\n'.join(display_string))
                                else:
                                    col_widget.warning("⚠️ No SPOC information available for this client")

                        elif field == "Project Name":
                            options = [""] + user_projects
                            idx = options.index(log[field]) if log[field] in options else 0
                            log[field] = col_widget.selectbox("Project Name", options=options, index=idx, key=widget_key)

                        else:
                            log[field] = col_widget.text_area(field, value=log[field], key=widget_key)

                    # Split fields between columns
                    for j, (field, _) in enumerate(log_columns):
                        if field == "Time":
                            continue  # Hide from UI but keep in DB
                        target_col = col_left if j % 2 == 0 else col_right
                        render_input(target_col, field, f"{field}_{i}")

                    st.button("🗑️ Delete this log", key=f"delete_{i}", on_click=lambda idx=i: delete_log_row(idx))

    # ✅ Save logs
    if st.button("💾 Save"):
        logs_collection.delete_many({"Date": selected_date_str, "Username": username})
        for log in st.session_state.logs:
            logs_collection.insert_one({"Date": selected_date_str, "Username": username, **log})
        st.success("Logs saved to MongoDB successfully!")