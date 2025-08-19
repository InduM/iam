import streamlit as st
import io
import time
import pandas as pd
from datetime import date
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *
from utils.utils_project_user_sync import _initialize_services
from utils.utils_project_form import _reset_create_form_state, initialize_create_form_state
from .projects_state_management import (
    _render_edit_header_with_refresh,_initialize_edit_mode_state)
from .projects_display import (
    render_project_card, render_level_checkboxes_with_substages,
    render_limited_substage_assignments_editor
)
from .project_logic import (
    _handle_create_project,
    handle_save_project,
    handle_level_change,
)


def run():
    initialize_session_state()
    _initialize_services()
    if "last_view" not in st.session_state:
        st.session_state.last_view = None

    if "projects" not in st.session_state or st.session_state.get("refresh_projects", False):
        all_projects = load_projects_from_db()
        username = st.session_state.get("username", "")
        role = st.session_state.get("role", "")

        if role == "user":
            filtered_projects = []
            for proj in all_projects:
                created_by = proj.get("created_by", "")
                co_managers = proj.get("co_managers", [])

                # Check if this user is the creator or a co-manager
                is_creator = (created_by == username)
                is_co_manager = any(cm.get("user") == username for cm in co_managers)

                if is_creator or is_co_manager:
                    filtered_projects.append(proj)

            st.session_state.projects = filtered_projects
        else:
            # Managers/Admins → see everything
            st.session_state.projects = all_projects

        st.session_state.refresh_projects = False

    # route to correct view
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()



def show_dashboard():
    st.query_params["_"] = str(int(time.time() // 60))
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")

    # --- Header ---
    if role == "user":
        st.caption(f"Showing projects you created or co-manage (logged in as **{username}**) 🧑‍💻")
    else:
        st.caption(f"Showing all projects (logged in as **{username}**, role: {role})")

    # --- Top buttons ---
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("➕ New Project", use_container_width=True):
            st.session_state.view = "create"
            if st.session_state.get("role") != "user": # 🚫 Prevent rerun for user
                st.rerun()
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.refresh_projects = True
            if st.session_state.get("role") != "user": # 🚫 Prevent rerun for user
                st.rerun()
    with col3:
        # Export button will appear after filters are applied
        export_trigger = st.button("📤 Export to Excel", use_container_width=True)

    # --- Filter bar ---
    with st.container():
        st.markdown("<div class='filter-bar'>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            search_query = st.text_input("🔍 Search", placeholder="Name, client, or team")
        with col2:
            filter_template = st.selectbox("📂 Template", ["All"] + list(TEMPLATES.keys()))
        with col3:
            filter_subtemplate = "All"
            if filter_template == "Onwards":
                filter_subtemplate = st.selectbox("🔄 Subtemplate", ["All", "Foundation", "Work Readiness"])
            else:
                st.empty()
        with col4:
            progress_levels = _get_template_progress_levels(filter_template, filter_subtemplate)
            filter_level = st.selectbox("📊 Progress Level", ["All"] + progress_levels)
        with col5:
            filter_due = st.date_input("📅 Due Before or On", value=None)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Apply standard filters ---
    filtered_projects = _apply_filters(
        st.session_state.projects,
        search_query,
        filter_template,
        filter_subtemplate,
        filter_level,
        filter_due,
    )

    # --- Extra role-based filter (user only) ---
    if role == "user":
        filter_option = st.selectbox(
            "👤 Filter by ownership",
            ["All", "Created by me", "I co-manage"],
            key="project_user_filter"
        )
        if filter_option == "Created by me":
            filtered_projects = [p for p in filtered_projects if p.get("created_by") == username]
        elif filter_option == "I co-manage":
            filtered_projects = [
                p for p in filtered_projects
                if any(cm.get("user") == username for cm in p.get("co_managers", []))
            ]

    # --- Export projects to Excel ---
    if export_trigger and filtered_projects:
        df = pd.DataFrame(filtered_projects)

        # Flatten co-managers for readability
        if "co_managers" in df.columns:
            df["co_managers"] = df["co_managers"].apply(
                lambda cms: ", ".join([f"{cm.get('user')} ({cm.get('access','full')})" for cm in cms]) if cms else ""
            )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Projects")
        st.download_button(
            label="⬇ Download Excel file",
            data=output.getvalue(),
            file_name="projects_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- Display projects in 2-column layout ---
    cols = st.columns(2)
    for i, project in enumerate(filtered_projects):
        with cols[i % 2]:
            st.markdown("<div class='project-card'>", unsafe_allow_html=True)
            render_project_card(project, i)
            st.markdown("</div>", unsafe_allow_html=True)

def _get_template_progress_levels(filter_template, filter_subtemplate="All"):
    """Get progress levels based on selected template and subtemplate"""
    if filter_template == "All":
        # Show all unique levels from all projects
        all_levels = sorted(set(lvl for proj in st.session_state.projects for lvl in proj.get("levels", [])))
        return all_levels
    elif filter_template == "Onwards":
        # For Onwards template, levels don't include Invoice/Payment
        if filter_template in TEMPLATES:
            base_levels = TEMPLATES[filter_template].copy()
            # Remove Invoice and Payment if they exist
            for stage_to_remove in ["Invoice", "Payment"]:
                if stage_to_remove in base_levels:
                    base_levels.remove(stage_to_remove)
            return base_levels
        else:
            return []
    elif filter_template in TEMPLATES:
        # For other templates, include all standard levels
        template_levels = TEMPLATES[filter_template].copy()
        # Remove Invoice and Payment first, then add them back at the end
        for required in ["Invoice", "Payment"]:
            if required in template_levels:
                template_levels.remove(required)
        return template_levels + ["Invoice", "Payment"]
    else:
        # Fallback: get levels from projects matching this template
        matching_projects = [p for p in st.session_state.projects if p.get("template") == filter_template]
        if matching_projects:
            all_levels = sorted(set(lvl for proj in matching_projects for lvl in proj.get("levels", [])))
            return all_levels
        return []

def show_create_form():
    st.markdown("## ➕ Create New Project")

    name = st.text_input("Project Name")
    template = st.selectbox("Template", list(TEMPLATES.keys()))
    client = ""
    subtemplate = None

    if template == "Onwards":
        subtemplate = st.selectbox("Subtemplate", ["Foundation", "Work Readiness"])
    else:
        client = st.text_input("Client")

    description = st.text_area("Description")
    start = st.date_input("Start Date")
    due = st.date_input("Due Date")

    created_by = st.session_state.get("username", "")

    # --- NEW: Co-Manager section ---
    st.markdown("### 👥 Co-Managers")

    # Fetch all usernames from DB, excluding creator
    from backend.users_backend import get_all_users
    all_users = get_all_users()
    usernames = [
        u.get("username") for u in all_users
        if u.get("username") and u.get("username") != created_by
    ]

    co_managers = []
    num_cms = st.number_input("Number of Co-Managers", min_value=0, max_value=5, value=0, step=1)

    for i in range(num_cms):
        st.markdown(f"#### Co-Manager #{i+1}")
        col1, col2 = st.columns(2)
        with col1:
            cm_user = st.selectbox(
                f"Select User (Co-Manager #{i+1})",
                [""] + usernames,
                key=f"cm_user_{i}"
            )
        with col2:
            cm_access = st.selectbox(
                f"Access Type (Co-Manager #{i+1})",
                ["full", "limited"],
                key=f"cm_access_{i}"
            )

        cm_stages = []
        if cm_access == "limited":
            # --- Reactive stage list based on template ---
            if template in TEMPLATES:
                all_stages = TEMPLATES[template].get("stages", [])
            else:
                all_stages = []

            cm_stages = st.multiselect(
                f"Allowed Stages (Co-Manager #{i+1})",
                all_stages,
                key=f"cm_stages_{i}"
            )

        if cm_user:
            co_managers.append({
                "user": cm_user,
                "access": cm_access,
                "stages": cm_stages
            })
    # --- End Co-Manager section ---

    # Stage assignments (existing logic in your app)
    stage_assignments = {}

    if st.button("✅ Create Project"):
        pid = _handle_create_project(
            name,
            client,
            description,
            start,
            due,
            template,
            subtemplate,
            stage_assignments,
            created_by,
            co_managers=co_managers
        )
        if pid:
            st.session_state.view = "dashboard"
            st.rerun()


# Updated show_edit_form function with proper permission handling
def show_edit_form():
    pid = st.session_state.edit_project_id
    current_project = next((p for p in st.session_state.projects if p["id"] == pid), None)
    project_name = current_project.get("name", "") if current_project else ""
    _render_edit_header_with_refresh(project_name, pid)
    
    if st.session_state.get(f"edit_refresh_success_{pid}", False):
        st.success("✅ Project data refreshed from database!")
        del st.session_state[f"edit_refresh_success_{pid}"]
    if not st.session_state.get(f"edit_initialized_{pid}", False):
        _initialize_edit_mode_state(pid)
        st.session_state[f"edit_initialized_{pid}"] = True
        st.rerun()
    
    if not current_project:
        st.error("Project not found.")
        return
    
    # --- Enhanced Permission check ---
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")
    allowed_stages = []  # Initialize as empty list
    is_creator = False
    is_co_manager = False
    has_full_access = False

    if role == "user":
        created_by = current_project.get("created_by", "")
        co_managers = current_project.get("co_managers", [])
        project_levels = current_project.get("levels", [])
        
        is_creator = (created_by == username)

        # Check co-manager permissions
        for cm in co_managers:
            if cm.get("user") == username:
                if cm.get("access") == "full":
                    is_co_manager = True
                    has_full_access = True
                    allowed_stages = project_levels  # all stages
                elif cm.get("access") == "limited":
                    is_co_manager = True
                    has_full_access = False
                    allowed_stages = cm.get("stages", [])
                break

        # Creator has full access to all stages
        if is_creator:
            has_full_access = True
            allowed_stages = project_levels

        if not (is_creator or is_co_manager):
            st.error("🚫 You do not have permission to edit this project.")
            st.session_state.view = "dashboard"
            st.rerun()
            return
            
        # Show permission info for limited access users
        if not has_full_access and allowed_stages:
            st.info(f"🔒 Limited Access: You can only edit stages: {', '.join(allowed_stages)}")
    else:
        # Managers/Admins have full access
        has_full_access = True
        allowed_stages = current_project.get("levels", [])
    # --- End enhanced permission check ---

    fresh_project = get_project_by_name(project_name)
    if not fresh_project:
        st.error("Project not found in database.")
        return
    project = ensure_project_defaults(fresh_project)
    original_name = project.get("name", "")
    
    st.markdown("<div class='section-header'>Project Details</div>", unsafe_allow_html=True)
    name = st.text_input("📝 Project Name", value=project.get("name", ""))
    
    # Show template and subtemplate info (read-only for existing projects)
    project_template = project.get("template", "")
    project_subtemplate = project.get("subtemplate", "")
    
    if project_template:
        if project_template == "Onwards" and project_subtemplate:
            st.info(f"📂 Template: **{project_template}** - **{project_subtemplate}**")
        else:
            st.info(f"📂 Template: **{project_template}**")
    
    # Only show client field if project template is NOT "Onwards"
    client = ""
    if project_template != "Onwards":
        clients = get_all_clients()
        if not clients:
            st.warning("⚠️ No clients found in the database.")
        current_client = project.get("client", "")
        if current_client in clients:
            client = st.selectbox("👤 Client", options=clients, index=clients.index(current_client))
        else:
            st.warning(f"⚠️ Current client '{current_client}' not found in client list. Please select a new client.")
            client = st.selectbox("👤 Client", options=clients)
    else:
        client = project.get("client", "")
        if client:
            st.info(f"👤 Client field hidden for Onwards template. Current client: {client}")
    
    description = st.text_area("🗒️ Project Description", value=project.get("description", ""))
    start = st.date_input("📅 Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("📅 Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))

    # --- Multi Co-Managers Section (only show if user has full access) ---
    if has_full_access:
        st.subheader("👥 Co-Managers")
        existing_cms = project.get("co_managers", [])

        if existing_cms:
            st.markdown("**Current Co-Managers:**")
            for cm in existing_cms:
                cm_user = cm.get("user", "-")
                cm_access = cm.get("access", "full")
                if cm_access == "limited":
                    stages = ", ".join(cm.get("stages", [])) or "No stages selected"
                    st.info(f"• {cm_user} (Limited Access: {stages})")
                else:
                    st.info(f"• {cm_user} (Full Access)")

        num_cms = st.number_input(
            "Number of Co-Managers",
            min_value=0,
            max_value=5,
            value=len(existing_cms),
            step=1,
            key=f"num_co_managers_{pid}"
        )

        co_managers = []
        team_members = get_team_members_username(st.session_state.get("role", ""))
        for i in range(num_cms):
            st.markdown(f"#### Co-Manager #{i+1}")
            col1, col2 = st.columns(2)
            with col1:
                cm_user = st.selectbox(
                    f"Select User (Co-Manager #{i+1})",
                    [""] + team_members,
                    index=(team_members.index(existing_cms[i]["user"]) + 1) if i < len(existing_cms) and existing_cms[i]["user"] in team_members else 0,
                    key=f"cm_user_edit_{pid}_{i}"
                )
            with col2:
                cm_access = st.selectbox(
                    f"Access Type (Co-Manager #{i+1})",
                    ["full", "limited"],
                    index=(["full", "limited"].index(existing_cms[i]["access"])) if i < len(existing_cms) else 0,
                    key=f"cm_access_edit_{pid}_{i}"
                )

            cm_stages = []
            if cm_access == "limited":
                all_stages = project.get("levels", [])
                cm_stages = st.multiselect(
                    f"Allowed Stages (Co-Manager #{i+1})",
                    all_stages,
                    default=existing_cms[i].get("stages", []) if i < len(existing_cms) else [],
                    key=f"cm_stages_edit_{pid}_{i}"
                )

            if cm_user:
                co_managers.append({
                    "user": cm_user,
                    "access": cm_access,
                    "stages": cm_stages
                })

        # Save co-managers back to project
        project["co_managers"] = co_managers

    # --- Stage Assignments ---
    team_members = get_team_members_username(st.session_state.get("role", ""))
    st.markdown("<div class='section-header'>Stage Assignments</div>", unsafe_allow_html=True)
    current_stage_assignments = project.get("stage_assignments", {})
    
    if has_full_access:
        # Full access - can edit all stages
        stage_assignments = render_substage_assignments_editor(
            project.get("levels", ["Initial", "Invoice", "Payment"]),
            team_members,
            current_stage_assignments,
        )
    else:
        # Limited access - can only edit allowed stages
        stage_assignments = render_limited_substage_assignments_editor(
            project.get("levels", ["Initial", "Invoice", "Payment"]),
            team_members,
            current_stage_assignments,
            allowed_stages,
            pid
        )
    
    if stage_assignments:
        assignment_issues = validate_stage_assignments(stage_assignments, project.get("levels", []))
        if assignment_issues:
            for issue in assignment_issues:
                st.warning(f"⚠️ {issue}")
    overdue_stages = get_overdue_stages(current_stage_assignments, project.get("levels", []), project.get("level", -1))
    if overdue_stages:
        st.error("🔴 Overdue Stages:")
        for overdue in overdue_stages:
            st.error(f"  • {overdue['stage_name']}: {overdue['days_overdue']} days overdue (Due: {overdue['deadline']})")

    # --- Progress Section ---
    st.subheader("Progress")
    def on_change_edit(new_index):
        fresh_proj = get_project_by_name(project_name)
        fresh_assignments = fresh_proj.get("stage_assignments", {}) if fresh_proj else {}
        handle_level_change(fresh_proj or project, pid, new_index, fresh_assignments, "edit")
        if role != "user":
            st.rerun()
        else:
             # ✅ Update just this project's level in session_state
            for idx, p in enumerate(st.session_state.projects):
                if p["id"] == pid:
                    st.session_state.projects[idx]["level"] = new_index
                    break
            st.success("✅ Progress updated (no refresh needed)")

    render_level_checkboxes_with_substages(
        "edit", pid, int(project.get("level", -1)),
        project.get("timestamps", {}),
        project.get("levels", ["Initial", "Invoice", "Payment"]),
        on_change_edit,
        editable=True,
        stage_assignments=project.get("stage_assignments", {}),
        project=project,
        editable_stages=allowed_stages if role == "user" else None
    )

    # --- Save Button ---
    if st.button("💾 Save", use_container_width=True):
        handle_save_project(pid, project, name, client, description, start, due, original_name, stage_assignments)
        if role != "user":   # 🚫 Prevent rerun for user
            st.rerun()
        else:
           # ✅ Update the in-memory project list
            for idx, p in enumerate(st.session_state.projects):
                if p["id"] == pid:
                    st.session_state.projects[idx] = project
                    break
            st.success("✅ Changes saved (no refresh needed)")
            st.session_state.view = "dashboard"


def _apply_filters(projects, search_query, filter_template, filter_subtemplate, filter_level, filter_due):
    """Apply filters to project list including subtemplate filter with template-aware level filtering"""
    filtered_projects = projects
    
    if search_query:
        q = search_query.lower()
        filtered_projects = [p for p in filtered_projects if
                            q in p.get("name", "").lower() or
                            q in p.get("client", "").lower() or
                            any(q in member.lower() for member in p.get("team", []))]
    
    if filter_template != "All":
        filtered_projects = [p for p in filtered_projects if p.get("template") == filter_template]
    
    # Apply subtemplate filter for Onwards projects
    if filter_template == "Onwards" and filter_subtemplate != "All":
        filtered_projects = [p for p in filtered_projects if p.get("subtemplate") == filter_subtemplate]
    
    if filter_due:
        filtered_projects = [p for p in filtered_projects if 
                           p.get("dueDate") and date.fromisoformat(p["dueDate"]) <= filter_due]
    
    # Enhanced level filtering that works with template-specific levels
    if filter_level != "All":
        if filter_template != "All":
            # Template-specific level filtering
            template_levels = _get_template_progress_levels(filter_template, filter_subtemplate)
            filtered_projects = [
                p for p in filtered_projects
                if p.get("level", -1) >= 0 and
                p.get("levels") and
                len(p["levels"]) > p.get("level", -1) and
                p["levels"][p["level"]] == filter_level and
                filter_level in template_levels
            ]
        else:
            # General level filtering (original logic)
            filtered_projects = [
                p for p in filtered_projects
                if p.get("level", -1) >= 0 and
                p.get("levels") and
                len(p["levels"]) > p.get("level", -1) and
                p["levels"][p["level"]] == filter_level
            ]
    
    return filtered_projects




