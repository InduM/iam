import streamlit as st
from datetime import datetime

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
            if st.button("➕ Add"):
                go_to("add")
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
        for idx, proj in enumerate(filtered):
            # figure out actual project source
            if proj in st.session_state.projects["Ongoing"]:
                proj_type = "Ongoing"
                actual_idx = st.session_state.projects["Ongoing"].index(proj)
            else:
                proj_type = "Completed"
                actual_idx = st.session_state.projects["Completed"].index(proj)

            with st.container():
                cols = st.columns([0.5, 2, 3, 2.5, 1, 1] if proj_type == "Completed" else [0.5, 2, 3, 2.5, 1, 1, 1])
                with cols[0]:
                    selected = st.checkbox("", key=f"chk_{proj_type}_{idx}")
                with cols[1]:
                    st.text(proj["Title"])
                with cols[2]:
                    st.text(proj["Description"])
                with cols[3]:
                    st.text(str(proj["Start Date"]))
                with cols[4]:
                    if selected and st.button("✏️", key=f"edit_{proj_type}_{idx}"):
                        st.session_state.edit_index = actual_idx
                        st.session_state.edit_type = proj_type
                        go_to("edit")
                with cols[5]:
                    if st.button("🗑️", key=f"delete_{proj_type}_{idx}"):
                        st.session_state.delete_index = actual_idx
                        st.session_state.delete_type = proj_type
                        st.session_state.confirm_delete = True
                if proj_type == "Ongoing":
                    with cols[6]:
                        if st.button("✅", key=f"complete_{idx}"):
                            item = st.session_state.projects["Ongoing"].pop(actual_idx)
                            st.session_state.projects["Completed"].append(item)
                            st.success("✅ Project marked as completed.")
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
    with st.form("add_project_form"):
        title = st.text_input("Project Title")
        desc = st.text_area("Description")
        start_date = st.date_input("Start Date", value=datetime.today())
        submitted = st.form_submit_button("Add Project")
        if submitted:
            st.session_state.projects["Ongoing"].append({
                "Title": title,
                "Description": desc,
                "Start Date": start_date
            })
            st.success("✅ Project added.")
            go_to("home")

    if st.button("🔙 Back"):
        go_to("home")

# --- EDIT PROJECT PAGE ---
elif st.session_state.page == "edit":
    idx = st.session_state.edit_index
    ptype = st.session_state.edit_type

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

            submitted = st.form_submit_button("Update Project")
            if submitted:
                project["Title"] = title
                project["Description"] = desc
                project["Start Date"] = start_date
                st.success("✅ Project updated.")
                reset_edit_state()
                go_to("home")

        if st.button("🔙 Back"):
            reset_edit_state()
            go_to("home")
