import streamlit as st
from datetime import datetime

st.markdown("""
    <style>
    .project-row {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        padding: 0.5em;
        border-bottom: 1px solid #ddd;
        transition: background-color 0.2s ease;
    }
    .project-row:hover {
        background-color: #f5f5f5;
    }
    .project-title {
        font-weight: bold;
    }
    .project-actions {
        display: none;
    }
    .project-row:hover .project-actions {
        display: flex;
        gap: 0.5em;
    }
    
    .block-container {
            position: relative;
    }
    section[tabindex] {
            background-color: rgba(0, 0, 0, 0.05);
    }

        /* Overlay */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            z-index: 999;
        }

        /* Modal box */
        .modal-box {
            position: fixed;
            top: 50%;
            left: 50%;
            width: 90%;
            max-width: 400px;
            transform: translate(-50%, -50%);
            background-color: white;
            border-radius: 12px;
            padding: 2rem;
            z-index: 1000;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }

        /* Button styling inside modal */
        .modal-box button {
            margin-right: 10px;
        }
    </style>
""", unsafe_allow_html=True)



# --- Initialize Session State ---
if "projects" not in st.session_state:
    st.session_state.projects = {"Ongoing": [], "Completed": []}
if "page" not in st.session_state:
    st.session_state.page = "home"
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_type" not in st.session_state:
    st.session_state.edit_type = None
if "delete_index" not in st.session_state:
    st.session_state.delete_index = None
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False


# --- Navigation Helpers ---
def go_to(page):
    st.session_state.page = page

def reset_edit_state():
    st.session_state.edit_index = None
    st.session_state.edit_type = None
    st.session_state.delete_index = None
    st.session_state.confirm_delete = False


# --- HOME PAGE ---


if st.session_state.page == "home":
    st.title("📋 Project Dashboard")

    # Mobile-friendly layout
    with st.container():
        col1, col2, col3, col4 = st.columns([1, 1.5, 1.5, 3])
        with col1:
            if st.button("➕ Add", key="add_project_button"):
                st.session_state.page = "add"
                st.rerun()

        with col2:
            project_type = st.selectbox("View", ["Ongoing", "Completed", "All"], label_visibility="collapsed")
        with col3:
            sort_by = st.selectbox("Sort", ["Title (A-Z)", "Start Date (Newest)"], label_visibility="collapsed")
        with col4:
            search = st.text_input("Search", placeholder="Search by title or description", label_visibility="collapsed").lower()

    st.markdown("---")
    st.subheader(f"{project_type} Projects")

    # Get relevant project list
    if project_type == "All":
        projects = st.session_state.projects["Ongoing"] + st.session_state.projects["Completed"]
    else:
        projects = st.session_state.projects[project_type]

    # --- Filter and Sort ---
    filtered = [
        p for p in projects if search in p["Title"].lower() or search in p["Description"].lower()
    ]
    if sort_by == "Title (A-Z)":
        filtered = sorted(filtered, key=lambda x: x["Title"])
    elif sort_by == "Start Date (Newest)":
        filtered = sorted(filtered, key=lambda x: x["Start Date"], reverse=True)

    if not filtered:
        st.info("No projects match your criteria.")
    else:
        popup_triggered = False  # Flag to check if any checkbox is selected
        for idx, proj in enumerate(filtered):
            if proj in st.session_state.projects["Ongoing"]:
                proj_type = "Ongoing"
                actual_idx = st.session_state.projects["Ongoing"].index(proj)
            else:
                proj_type = "Completed"
                actual_idx = st.session_state.projects["Completed"].index(proj)

            with st.container():
                cols = st.columns([0.5, 2, 3, 2.5])
                with cols[0]:
                    checkbox_key = f"chk_{proj_type}_{idx}"
                    selected = st.checkbox("", key=checkbox_key)
                with cols[1]:
                    st.text(proj["Title"])
                with cols[2]:
                    st.text(proj["Description"])
                    st.caption(f"{', '.join(proj.get('Users', []))}")
                with cols[3]:
                    st.text(str(proj["Start Date"]))

                # When checkbox is clicked, show popup
                if selected:
                    # Only store popup if not already showing
                    if "popup" not in st.session_state or st.session_state.popup is None or st.session_state.popup.get("key") != checkbox_key:
                        st.session_state.popup = {
                            "index": actual_idx,
                            "type": proj_type,
                            "title": proj["Title"],
                            "key": checkbox_key
                        }
                    popup_triggered = True

        # If no checkbox is selected anymore, clear popup
        if not popup_triggered:
            st.session_state.popup = None

        # === POPUP SIMULATION ===
        if st.session_state.get("popup"):
            popup_data = st.session_state.popup
            st.markdown("---")
            with st.container():
                st.write(f"**Project**: {popup_data['title']}")
                col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
                with col1:
                    if st.button("✏️ ", key="popup_edit"):
                        st.session_state.edit_index = popup_data["index"]
                        st.session_state.edit_type = popup_data["type"]
                        st.session_state.page = "edit"
                        st.session_state.popup = None
                        st.rerun()
                with col2:
                    if st.button("🗑️", key="popup_delete"):
                        st.session_state.delete_index = popup_data["index"]
                        st.session_state.delete_type = popup_data["type"]
                        st.session_state.confirm_delete = True
                        st.session_state.popup = None
                if popup_data["type"] == "Ongoing":
                    with col3:
                        if st.button("✅", key="popup_complete"):
                            item = st.session_state.projects["Ongoing"].pop(popup_data["index"])
                            st.session_state.projects["Completed"].append(item)
                            st.success("✅ Project marked as completed.")
                            st.session_state.popup = None
                            st.rerun()

            # --- Confirm Delete Section ---
    if st.session_state.confirm_delete:
        st.warning("Are you sure you want to delete this project?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Delete"):
                idx = st.session_state.delete_index
                ptype = st.session_state.delete_type
                st.session_state.projects[ptype].pop(idx)
                reset_edit_state()
                st.success("Project deleted.")
                st.rerun()
        with col2:
            if st.button("Cancel"):
                reset_edit_state()

# --- ADD PROJECT PAGE ---
elif st.session_state.page == "add":
    st.title("➕ Add New Project")

    EMPLOYEES = ["Alice", "Bob", "Charlie", "David", "Eva"]
    LOCATIONS = ["San Francisco", "New York", "Remote", "London", "Bangalore"]

    with st.form("add_project_form"):
        title = st.text_input("Project Title")
        desc = st.text_area("Description")
        start_date = st.date_input("Start Date", value=datetime.today())
        users = st.multiselect("Assign Users", options=EMPLOYEES)

        submitted = st.form_submit_button("Add Project")
        if submitted:
            st.session_state.projects["Ongoing"].append({
                "Title": title,
                "Description": desc,
                "Start Date": start_date,
                "Users": users,
            })
            st.success("✅ Project added.")
            go_to("home")

    if st.button("🔙 Back", key="back_from_add"):
        st.session_state.page = "home"
        st.rerun()
        #go_to("home")

# --- EDIT PROJECT PAGE ---
elif st.session_state.page == "edit":
    idx = st.session_state.edit_index
    ptype = st.session_state.edit_type

    EMPLOYEES = ["Alice", "Bob", "Charlie", "David", "Eva"]
    LOCATIONS = ["San Francisco", "New York", "Remote", "London", "Bangalore"]

    if idx is None or ptype is None:
        st.error("No project selected.")
        go_to("home")
    else:
        st.title("✏️ Edit Project")
        project = st.session_state.projects[ptype][idx]

        with st.form("edit_form"):
            title = st.text_input("Project Title", value=project["Title"])
            desc = st.text_area("Description", value=project["Description"])
            start_date = st.date_input("Start Date", value=project["Start Date"])
            users = st.multiselect("Assign Users", options=EMPLOYEES, default=project.get("Users", []))

            submitted = st.form_submit_button("Update Project")
            if submitted:
                project["Title"] = title
                project["Description"] = desc
                project["Start Date"] = start_date
                project["Users"] = users
                st.success("✅ Project updated.")
                reset_edit_state()
                go_to("home")

        if st.button("🔙 Back",key="back_from_edit"):
            reset_edit_state()
            st.session_state.page = "home"
            st.rerun()
            #go_to("home")
