import streamlit as st
import pandas as pd
from datetime import date
from pymongo import MongoClient
import certifi

def run():
        # 🔌 Connect to MongoDB Atlas
    uri = st.secrets["MONGO_URI"]
    client = MongoClient(uri, tlsCAFile=certifi.where())
    db = client["user_db"]

    @st.cache_resource
    def get_mongo_collection():
        return db["users"]

    @st.cache_resource
    def get_logs_collection():
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


    def display_profile(username, w):
        collection2 = db["documents"]
        user_doc = collection2.find_one({"username": username})
        profile_image_data = user_doc.get("profile_image", {}).get("data", None)
        if  profile_image_data:# Decode base64 and display image
            st.markdown(
                f"""
                <img src="data:image/png;base64,{profile_image_data}" 
                    style="width:100px; height:100px; object-fit:cover; border-radius:10%;">
                """,
                unsafe_allow_html=True,
            )
        else:           # Default image if none uploaded
            user_doc = collection2.find_one({"username": "admin"}) # change it to default user later
            profile_image_data = user_doc.get("profile_image", {}).get("data", None)
            st.markdown(
            f"""
            <img src="data:image/png;base64,{profile_image_data}" 
                style="width:100px; height:100px; object-fit:cover; border-radius:10%;">
            """,
            unsafe_allow_html=True,
             )



    # 📋 Profile Page
    def show_profile(member):
        col1, col2 = st.columns([1, 8])  # Narrow left column for back arrow
        with col1:
            if st.button("←", key="back_arrow"):
                go_back()
                st.rerun()
        with col2:
            st.title(member["name"])

        display_profile(member["username"], w=100)

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
                    "Projects",
                    options=all_projects,
                    default=[p for p in member.get("project", []) if p in all_projects],
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
            st.markdown(f"**Role:** {member['position']}")
            st.markdown(f"**Branch:** {member['branch']}")
            st.markdown("**Projects:** " + ", ".join(member.get("project", [])))

            if st.button("✏️ Edit Profile"):
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
        current_role = st.session_state.get("role")
        if current_role == "manager":
            team_data = [member for member in team_data if member.get("role") == "user"]
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

        # ✅ Sort by name alphabetically
        filtered = filtered.sort_values(by="name", ascending=True, na_position='last')

        # --- Display Team Members (left-to-right layout) ---
        num_columns = 2  # Adjust for more per row if needed
        rows = [filtered.iloc[i:i+num_columns] for i in range(0, len(filtered), num_columns)]

        for row_chunk in rows:
            cols = st.columns(num_columns)
            for idx, (_, member) in enumerate(row_chunk.iterrows()):
                with cols[idx]:
                    display_profile(member["username"], w=100)
                    name = str(member.get("name", "Unnamed"))
                    email = str(member.get("email", f"key_{name}"))
                    if st.button(name, key=email):
                        st.session_state.selected_member = member.to_dict()
                        st.rerun()

    # 🚦 Routing
    if st.session_state.selected_member:
        show_profile(st.session_state.selected_member)
    else:
        show_team()