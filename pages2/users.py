import streamlit as st
import pandas as pd
from datetime import date
from pymongo import MongoClient
import certifi


def run():
        # 🔌 Connect to MongoDB Atlas
    @st.cache_resource
    def get_mongo_collection():
        uri = st.secrets["MONGO_URI"]
        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client["user_db"]
        return db["users"]

    @st.cache_resource
    def get_logs_collection():
        uri = st.secrets["MONGO_URI"]
        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client["user_db"]
        return db["logs"]
    collection = get_mongo_collection()

    # 🔄 Load and normalize team data
    def load_team_data():
        data = list(collection.find({}, {"_id": 0}))
        for d in data:
            proj = d.get("project")
            if isinstance(proj, list):
                continue
            elif isinstance(proj, str):
                d["project"] = [proj]
            else:
                d["project"] = []
        return data

    # 📝 Update team member details
    def update_member(original_email, updated_data):
        collection.update_one(
            {"email": original_email},
            {"$set": updated_data}
        )

    # Session state
    if "selected_member" not in st.session_state:
        st.session_state.selected_member = None
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    default_img_path ="images/img_avatar.png"

    # 🔙 Navigation helpers
    def go_back():
        st.session_state.selected_member = None
        st.session_state.edit_mode = False

    def save_edits(name, email, role, branch, projects):
        update_member(
            st.session_state.selected_member["email"],
            {
                "name": name,
                "email": email,
                "role": role,
                "branch": branch,
                "project": projects
            }
        )
        st.session_state.selected_member = {
            "name": name,
            "email": email,
            "role": role,
            "branch": branch,
            "project": projects
        }
        st.success("✅ Profile updated successfully!")
        st.session_state.edit_mode = False

    # 📋 Profile Page
    def show_profile(member):
        col1, col2 = st.columns([1, 8])  # Narrow left column for back arrow
        with col1:
            if st.button("←", key="back_arrow"):
                go_back()
                st.rerun()
        with col2:
            st.title(member["name"])

        st.image(default_img_path, width=150)

        if st.session_state.edit_mode:
            with st.form("edit_form"):
                st.text_input("Name", value=member["name"], disabled=True)
                st.text_input("Email", value=member["email"], disabled=True)
                st.text_input("Role", value=member["role"], disabled=True)
                st.text_input("Branch", value=member["branch"], disabled=True)

                # Get all unique projects
                all_projects = sorted({
                    p for m in load_team_data()
                    if isinstance(m.get("project"), list)
                    for p in m.get("project", [])
                })

                projects = st.multiselect(
                    "Projects (Editable)",
                    options=all_projects,
                    default=member.get("project", []),
                )

                submitted = st.form_submit_button("💾 Save Projects")
                if submitted:
                    update_member(member["email"], {"project": projects})
                    st.success("✅ Projects updated successfully!")
                    st.session_state.selected_member["project"] = projects
                    st.session_state.edit_mode = False
                    st.rerun()
        else:
            st.markdown(f"**Email:** {member['email']}")
            st.markdown(f"**Role:** {member['role']}")
            st.markdown(f"**Branch:** {member['branch']}")
            st.markdown("**Projects:** " + ", ".join(member.get("project", [])))

            if st.button("✏️ Edit Projects"):
                st.session_state.edit_mode = True
                st.rerun()

            # 🔍 Show Everyday Log if current user is a manager
                # 🔍 Show Everyday Log if current user is a manager
            if st.session_state.get("role") == "manager":
                logs_collection = get_logs_collection()

                # ✅ Date selector
                selected_log_date = st.date_input("📅 Select a date to view logs", value=date.today(), key="log_view_date")

                # ✅ Query logs for selected member on that date
                query_date_str = selected_log_date.strftime("%Y-%m-%d")
                query_username = member["email"].split("@")[0]
                logs = list(logs_collection.find(
                    {"Date": query_date_str, "Username": query_username},
                    {"_id": 0, "Date": 0, "Username": 0}
                ))

                if logs:
                    import pandas as pd
                    df_logs = pd.DataFrame(logs)
                    st.dataframe(df_logs, use_container_width=True, hide_index=True)
                else:
                    st.info("No logs found for this date.")


    # 👥 Team View Page
    def show_team():

        team_data = load_team_data()
        df = pd.DataFrame(team_data)

        # --- Filters ---
        col1, col2 = st.columns(2)
        with col1:
            branch_filter = st.selectbox("📍 Filter by Branch", ["All"] + sorted(df["branch"].dropna().unique()))

        with col2:
            # ✅ Flatten all project lists into a single unique list
            all_projects = sorted({
                p for projs in df["project"]
                if isinstance(projs, list)
                for p in projs
            })
            project_filter = st.selectbox("📁 Filter by Project", ["All"] + all_projects)

        # --- Search by Name ---
        search_query = st.text_input("🔍 Search by name")

        # --- Apply Filters ---
        filtered = df.copy()
        if branch_filter != "All":
            filtered = filtered[filtered["branch"] == branch_filter]
        if project_filter != "All":
            filtered = filtered[
                filtered["project"].apply(
                    lambda projs: isinstance(projs, list) and project_filter in projs
                )
            ]
        if search_query:
            filtered = filtered[filtered["name"].str.contains(search_query, case=False)]

        # --- Display Team Members ---
            # --- Display Team Members (left-to-right layout) ---
        st.subheader("👥 Team Members")
        num_columns = 2  # Adjust for more per row if needed
        rows = [filtered.iloc[i:i+num_columns] for i in range(0, len(filtered), num_columns)]

        for row_chunk in rows:
            cols = st.columns(num_columns)
            for idx, (_, member) in enumerate(row_chunk.iterrows()):
                with cols[idx]:
                    st.image(default_img_path, width=100)
                    if st.button(member["name"], key=member["email"]):
                        st.session_state.selected_member = member.to_dict()
                        st.rerun()

    # 🚦 Routing
    if st.session_state.selected_member:
        show_profile(st.session_state.selected_member)
    else:
        show_team()