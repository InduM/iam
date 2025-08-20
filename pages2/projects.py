import streamlit as st
import io
import time
import pandas as pd
from datetime import date
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *
from utils.utils_project_user_sync import _initialize_services
from utils.utils_project_form import ( initialize_create_form_state,render_custom_levels_editor)
from .projects_state_management import (_render_back_button,_render_edit_header_with_refresh,_initialize_edit_mode_state)
from .project_substage_manager import render_progress_section
from .projects_display import (
    render_project_card, render_level_checkboxes_with_substages)
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

                # Check if user is creator
                is_creator = (created_by == username)

                # Check if user is co-manager
                is_co_manager = any(cm.get("user") == username for cm in co_managers)

                if is_creator or is_co_manager:
                    filtered_projects.append(proj)

            st.session_state.projects = filtered_projects
        else:
            # Managers/Admins → see everything
            st.session_state.projects = all_projects

        st.session_state.refresh_projects = False

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
        st.caption(f"Showing projects you created or co-manage (logged in as **{username}**)")
    else:
        st.caption(f"Showing all projects (logged in as **{username}**, role: {role})")

    # --- Top buttons ---
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("➕ New Project", use_container_width=True):
            st.session_state.view = "create"
            st.rerun()
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.refresh_projects = True
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
    if not st.session_state.get("create_initialized", False):
        initialize_create_form_state()
        st.session_state.create_initialized = True
    _render_back_button()
    
    # Template selection with current value
    template_options = ["Custom Template"] + list(TEMPLATES.keys())
    current_template = st.session_state.get("selected_template", "")
    
    # Find current index for template
    if current_template and current_template in TEMPLATES:
        current_template_index = template_options.index(current_template)
    else:
        current_template_index = 0
    
    selected = st.selectbox(
        "📂 Select Template (optional)", 
        template_options, 
        index=current_template_index,
        key="template_selector"
    )
    
    # Handle template selection change
    if selected != st.session_state.get("selected_template", ""):
        if selected != "Custom Template":
            st.session_state.selected_template = selected
            st.session_state.stage_assignments = {}
        else:
            st.session_state.selected_template = ""
            st.session_state.stage_assignments = {}
        # Reset subtemplate when template changes
        st.session_state.selected_subtemplate = ""

    # Subtemplate selection for "Onwards" template
    selected_subtemplate = ""
    if st.session_state.get("selected_template") == "Onwards":
        subtemplate_options = ["Foundation", "Work Readiness"]
        current_subtemplate = st.session_state.get("selected_subtemplate", "")
        
        # Find current index for subtemplate
        if current_subtemplate and current_subtemplate in subtemplate_options:
            current_subtemplate_index = subtemplate_options.index(current_subtemplate)
        else:
            current_subtemplate_index = 0
        
        selected_subtemplate = st.selectbox(
            "🔄 Select Subtemplate", 
            subtemplate_options, 
            index=current_subtemplate_index,
            key="subtemplate_selector"
        )
        
        # Update session state only if changed
        if selected_subtemplate != st.session_state.get("selected_subtemplate", ""):
            st.session_state.selected_subtemplate = selected_subtemplate

    st.markdown("<div class='section-header'>Project Details</div>", unsafe_allow_html=True)
    name = st.text_input("📝 Project Name", value="")
    
    # Only show client field if template is NOT "Onwards"
    client = ""
    if st.session_state.get("selected_template") != "Onwards":
        clients = get_all_clients()
        if not clients:
            st.warning("⚠ No clients found in the database.")
            client_options = [""]
        else:
            client_options = [""] + clients
        
        client = st.selectbox(
            "👤 Client", 
            options=client_options, 
            index=0,
            key="client_selector"
        )
    
    description = st.text_area("🗒 Project Description", value="")
    start = st.date_input("📅 Start Date", value=date.today())
    due = st.date_input("📅 Due Date", value=date.today())

    # Handle template levels
    if st.session_state.selected_template:
        if st.session_state.selected_template == "Onwards":
            st.markdown(f"Using template: **{st.session_state.selected_template}** - **{selected_subtemplate}**")
            # Get base template levels and remove Invoice/Payment
            levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
            # Remove Invoice and Payment stages for Onwards template
            for stage_to_remove in ["Invoice", "Payment"]:
                if stage_to_remove in levels_from_template:
                    levels_from_template.remove(stage_to_remove)
            st.session_state.custom_levels = levels_from_template
        else:
            st.markdown(f"Using template: **{st.session_state.selected_template}**")
            levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
            # For other templates, remove Invoice/Payment and add them back at the end
            for required in ["Invoice", "Payment"]:
                if required in levels_from_template:
                    levels_from_template.remove(required)
            st.session_state.custom_levels = levels_from_template + ["Invoice", "Payment"]
    else:
        render_custom_levels_editor()

    team_members = get_team_members_username(st.session_state.get("role", ""))
    st.markdown("<div class='section-header'>Stage Assignments</div>", unsafe_allow_html=True)
    stage_assignments = render_substage_assignments_editor(st.session_state.custom_levels, team_members, st.session_state.get("stage_assignments", {}))
    st.session_state.stage_assignments = stage_assignments

    if stage_assignments:
        assignment_issues = validate_stage_assignments(stage_assignments, st.session_state.custom_levels)
        if assignment_issues:
            for issue in assignment_issues:
                st.warning(f"⚠️ {issue}")

    render_progress_section("create")

    # --- NEW: Co-Manager in create form ---
    st.subheader("Co-Manager")
    co_manager = None
    if st.checkbox("➕ Add Co-Manager", key="add_co_manager_create"):
        team_members = get_team_members_username(st.session_state.get("role", ""))
        cm_user = st.selectbox("Select Co-Manager", options=team_members, key="cm_user_create")
        cm_access = st.radio("Access Type", ["Full Project Access", "Stage-Limited Access"], key="cm_access_create")
        if cm_access == "Stage-Limited Access":
            cm_stages = st.multiselect("Select allowed stages", st.session_state.custom_levels, key="cm_stages_create")
            co_manager = {"user": cm_user, "access": "limited", "stages": cm_stages}
        else:
            co_manager = {"user": cm_user, "access": "full"}


    if st.button("✅ Create Project", use_container_width=True):
        _handle_create_project(name, client, description, start, due, selected_subtemplate,co_manager   )


def show_edit_form():
    from backend.projects_backend import update_project_field
    from backend.log_backend import ProjectLogManager
    from bson import ObjectId
    from datetime import datetime

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

    # --- Permission check ---
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")
    if role == "user":
        created_by = current_project.get("created_by", "")
        co_managers = current_project.get("co_managers", [])
        is_creator = (created_by == username)
        is_co_manager = any(cm.get("user") == username for cm in co_managers)
        if not (is_creator or is_co_manager):
            st.error("🚫 You do not have permission to edit this project.")
            st.session_state.view = "dashboard"
            st.rerun()
            return
    # --- End permission check ---

    fresh_project = get_project_by_name(project_name)
    if not fresh_project:
        st.error("Project not found in database.")
        return
    project = ensure_project_defaults(fresh_project)
    original_name = project.get("name", "")

    st.markdown("<div class='section-header'>Project Details</div>", unsafe_allow_html=True)
    name = st.text_input("📝 Project Name", value=project.get("name", ""))

    # Template and subtemplate info
    project_template = project.get("template", "")
    project_subtemplate = project.get("subtemplate", "")
    if project_template:
        if project_template == "Onwards" and project_subtemplate:
            st.info(f"📂 Template: **{project_template}** - **{project_subtemplate}**")
        else:
            st.info(f"📂 Template: **{project_template}**")

    # Client field
    client = ""
    if project_template != "Onwards":
        clients = get_all_clients()
        if not clients:
            st.warning("⚠ No clients found in the database.")
        current_client = project.get("client", "")
        if current_client in clients:
            client = st.selectbox("👤 Client", options=clients, index=clients.index(current_client))
        else:
            st.warning(f"⚠ Current client '{current_client}' not found in client list. Please select a new client.")
            client = st.selectbox("👤 Client", options=clients)
    else:
        client = project.get("client", "")
        if client:
            st.info(f"👤 Client field hidden for Onwards template. Current client: {client}")

    description = st.text_area("🗒 Project Description", value=project.get("description", ""))
    start = st.date_input("📅 Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("📅 Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))

    # --- Multi Co-Managers section ---
    st.subheader("Co-Managers")
    existing_cms = project.get("co_managers", [])
    if not existing_cms:
        st.caption("No co-managers assigned yet.")

    updated_cms = []
    team_members = get_team_members_username(st.session_state.get("role", ""))

    log_manager = ProjectLogManager()
    actor = st.session_state.get("username", "?")

    for idx, cm in enumerate(existing_cms):
        st.markdown(f"**Co-Manager {idx+1}:**")

        cm_user = st.selectbox(
            "User", options=team_members,
            index=team_members.index(cm.get("user")) if cm.get("user") in team_members else 0,
            key=f"cm_user_{pid}_{idx}"
        )

        cm_access = st.radio(
            "Access Type", ["Full Project Access", "Stage-Limited Access"],
            index=0 if cm.get("access") == "full" else 1,
            key=f"cm_access_{pid}_{idx}"
        )

        if cm_access == "Stage-Limited Access":
            cm_stages = st.multiselect(
                "Allowed Stages", project.get("levels", []),
                default=cm.get("stages", []),
                key=f"cm_stages_{pid}_{idx}"
            )
            updated_cms.append({"user": cm_user, "access": "limited", "stages": cm_stages})
        else:
            updated_cms.append({"user": cm_user, "access": "full"})

        # Remove button
        if st.button(f"❌ Remove {cm_user}", key=f"remove_cm_{pid}_{idx}"):
            project["co_managers"].pop(idx)
            update_project_field(pid, {"co_managers": project["co_managers"]})

            log_manager.create_log_entry({
                "project_id": ObjectId(pid),
                "project": project.get("name", ""),
                "event": "co_manager_removed",
                "message": f"Removed {cm_user}",
                "performed_by": actor,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })

            st.success(f"Removed {cm_user}.")
            st.rerun()

    # Add new co-manager
    if st.button("➕ Add Co-Manager", key=f"add_co_manager_{pid}"):
        st.session_state[f"show_add_cm_{pid}"] = True

    if st.session_state.get(f"show_add_cm_{pid}", False):
        cm_user = st.selectbox("Select Co-Manager", options=team_members, key=f"cm_user_add_{pid}")
        cm_access = st.radio("Access Type", ["Full Project Access", "Stage-Limited Access"], key=f"cm_access_add_{pid}")
        if cm_access == "Stage-Limited Access":
            cm_stages = st.multiselect("Select allowed stages", project.get("levels", []), key=f"cm_stages_add_{pid}")
            new_cm = {"user": cm_user, "access": "limited", "stages": cm_stages}
        else:
            new_cm = {"user": cm_user, "access": "full"}

        if st.button("✅ Confirm Add", key=f"confirm_add_cm_{pid}"):
            project.setdefault("co_managers", []).append(new_cm)
            update_project_field(pid, {"co_managers": project["co_managers"]})

            log_manager.create_log_entry({
                "project_id": ObjectId(pid),
                "project": project.get("name", ""),
                "event": "co_manager_added",
                "message": f"Added {cm_user} ({new_cm['access']})",
                "performed_by": actor,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })

            st.success(f"Added {cm_user} as co-manager.")
            st.session_state[f"show_add_cm_{pid}"] = False
            st.rerun()

    # Replace with updated list (and persist if changed)
    if updated_cms != existing_cms:
        project["co_managers"] = updated_cms
        update_project_field(pid, {"co_managers": project["co_managers"]})

        # Track updates
        old_users = {cm["user"]: cm for cm in existing_cms}
        new_users = {cm["user"]: cm for cm in updated_cms}
        for user, cm in new_users.items():
            if user in old_users and cm != old_users[user]:
                log_manager.create_log_entry({
                    "project_id": ObjectId(pid),
                    "project": project.get("name", ""),
                    "event": "co_manager_updated",
                    "message": f"Updated {user} ({cm['access']})",
                    "performed_by": actor,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })

    # --- Stage Assignments ---
    st.markdown("<div class='section-header'>Stage Assignments</div>", unsafe_allow_html=True)
    current_stage_assignments = project.get("stage_assignments", {})
    stage_assignments = render_substage_assignments_editor(
        project.get("levels", ["Initial", "Invoice", "Payment"]),
        team_members, current_stage_assignments
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

    # --- Progress ---
    st.subheader("Progress")
    def on_change_edit(new_index):
        fresh_proj = get_project_by_name(project_name)
        fresh_assignments = fresh_proj.get("stage_assignments", {}) if fresh_proj else {}
        handle_level_change(fresh_proj or project, pid, new_index, fresh_assignments, "edit")

    render_level_checkboxes_with_substages(
        "edit", pid, int(project.get("level", -1)),
        project.get("timestamps", {}), project.get("levels", ["Initial", "Invoice", "Payment"]),
        on_change_edit, editable=True, stage_assignments=current_stage_assignments, project=project
    )

    # --- Save project general fields ---
    if st.button("💾 Save", use_container_width=True):
        handle_save_project(pid, project, name, client, description, start, due, original_name, stage_assignments)



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


