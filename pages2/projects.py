import streamlit as st
import time
from datetime import datetime, date, timedelta
from typing import List

# Import functions from backend and utils
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *

from projects_display import (
    render_project_card, render_level_checkboxes_with_substages,
    render_custom_levels_editor, render_progress_section
)
from projects_logic import (
    handle_create_project, handle_save_project,
    handle_level_change_dashboard, handle_level_change_edit
)
from projects_helpers import (
    create_project_data, reset_create_form_state,
    check_dashboard_success_messages
)


def run():
    """Main function to run the project management interface"""
    
    # Initialize session state
    initialize_session_state()
    
    # Load projects from database on first run or when explicitly refreshed
    if "projects" not in st.session_state or st.session_state.get("refresh_projects", False):
        st.session_state.projects = load_projects_from_db()
        st.session_state.refresh_projects = False
    
    # Navigation
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()

def show_dashboard():
    """Display the main dashboard with project list and controls"""
    st.query_params["_"] = str(int(time.time() // 60))  # Trigger rerun every 60 seconds

    # Action buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ New Project"):
            st.session_state.view = "create"
            st.rerun()
    with col2:
        if st.button("🔄Refresh"):
            st.session_state.refresh_projects = True
            st.rerun()

    # Filters and search
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search_query = st.text_input("Search", placeholder="Name, client, or team")
    with col2:
        filter_template = st.selectbox("Template", ["All"] + list(TEMPLATES.keys()))
    with col3:
        all_levels = sorted(set(
            lvl for proj in st.session_state.projects for lvl in proj.get("levels", [])
        ))
        filter_level = st.selectbox("Progress Level", ["All"] + all_levels)

    filter_due = st.date_input("Due Before or On", value=None)

    # Apply filters
    filtered_projects = _apply_filters(
        st.session_state.projects, search_query, filter_template, filter_level, filter_due
    )

    # Display projects
    for i, project in enumerate(filtered_projects):
        render_project_card(project, i)

def show_create_form():
    """Display the create project form with substage support"""
    st.title("🛠 Create Project")
    
    # Back button
    _render_back_button()
    
    # Template selection
    template_options = ["Custom Template"] + list(TEMPLATES.keys())
    selected = st.selectbox("Select Template (optional)", template_options)
    
    if selected != "Custom Template":
        st.session_state.selected_template = selected
    else:
        st.session_state.selected_template = ""
    
    # Form fields
    name = st.text_input("Project Name")
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    client = st.selectbox("Client", options=clients)
    description = st.text_area("Project Description")
    start = st.date_input("Start Date")
    due = st.date_input("Due Date")
    
    # Handle template levels
    if st.session_state.selected_template:
        st.markdown(f"Using template: **{st.session_state.selected_template}**")
        levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
        for required in ["Invoice", "Payment"]:
            if required in levels_from_template:
                levels_from_template.remove(required)
        st.session_state.custom_levels = levels_from_template + ["Invoice", "Payment"]
    else:
        render_custom_levels_editor()
    
    team_members = get_team_members(st.session_state.get("role", ""))
    
    # Enhanced Stage Assignments Section with Substages
    st.markdown("---")
    stage_assignments = render_stage_assignments_editor_with_substages(
        st.session_state.custom_levels, 
        team_members, 
        st.session_state.get("stage_assignments", {})
    )
    st.session_state.stage_assignments = stage_assignments
    
    # Validate stage assignments
    if stage_assignments:
        assignment_issues = validate_stage_assignments(stage_assignments, st.session_state.custom_levels)
        if assignment_issues:
            for issue in assignment_issues:
                st.warning(f"⚠️ {issue}")
    
    # Progress section
    render_progress_section("create")
    
    # Create button
    if st.button("✅ Create Project"):
        _handle_create_project(name, client, description, start, due)
        
def show_edit_form():
    """Display the edit project form with substage support"""
    st.title("✏ Edit Project")
    
    # Back button
    _render_back_button()
    
    pid = st.session_state.edit_project_id
    project = next((p for p in st.session_state.projects if p["id"] == pid), None)
    
    if not project:
        st.error("Project not found.")
        return
    
    # Ensure project has required fields
    project = ensure_project_defaults(project)
    
    original_team = project.get("team", [])
    original_name = project.get("name", "")
    
    # Form fields
    name = st.text_input("Project Name", value=project.get("name", ""))
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    
    current_client = project.get("client", "")
    client_index = clients.index(current_client) if current_client in clients else 0
    client = st.selectbox("Client", options=clients, index=client_index)
    
    description = st.text_area("Project Description", value=project.get("description", ""))
    start = st.date_input("Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))
    
    team_members = get_team_members(st.session_state.get("role", ""))    
    
    # Enhanced Stage Assignments Section with Substages
    st.markdown("---")
    current_stage_assignments = project.get("stage_assignments", {})
    stage_assignments = render_stage_assignments_editor_with_substages(
        project.get("levels", ["Initial", "Invoice", "Payment"]), 
        team_members, 
        current_stage_assignments
    )
    
    # Validate stage assignments
    if stage_assignments:
        assignment_issues = validate_stage_assignments(stage_assignments, project.get("levels", []))
        if assignment_issues:
            for issue in assignment_issues:
                st.warning(f"⚠️ {issue}")
    
    # Show substage completion summary
    render_substage_summary_widget(project)
    
    # Show overdue stages
    overdue_stages = get_overdue_stages(
        current_stage_assignments, 
        project.get("levels", []), 
        project.get("level", -1)
    )
    if overdue_stages:
        st.error("🔴 Overdue Stages:")
        for overdue in overdue_stages:
            st.error(f"  • {overdue['stage_name']}: {overdue['days_overdue']} days overdue (Due: {overdue['deadline']})")
    
    # Progress section with substages
    st.subheader("Progress")
    
    def on_change_edit(new_index):
        _handle_level_change_edit(project, pid, new_index, current_stage_assignments)
    
    # Check for success messages
    _check_edit_success_messages(pid)
    
    # Render level checkboxes with substage support
    render_level_checkboxes_with_substages(
        "edit", pid, int(project.get("level", -1)), 
        project.get("timestamps", {}), project.get("levels", ["Initial", "Invoice", "Payment"]), 
        on_change_edit, editable=True, stage_assignments=current_stage_assignments, project=project
    )
    
    # Save button
    if st.button("💾 Save"):
        _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments)
def _render_back_button():
    """Render back button with styling"""
    st.markdown(
        """
        <style>
        .back-button {
            font-size: 24px;
            margin-bottom: 1rem;
            display: inline-block;
            cursor: pointer;
            color: #007BFF;
        }
        .back-button:hover {
            text-decoration: underline;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    if st.button("← Back", key="back_button"):
        st.session_state.view = "dashboard"
        st.rerun()

def _apply_filters(projects, search_query, filter_template, filter_level, filter_due):
    """Apply filters to project list"""
    filtered_projects = projects
    
    if search_query:
        q = search_query.lower()
        filtered_projects = [p for p in filtered_projects if
                            q in p.get("name", "").lower() or
                            q in p.get("client", "").lower() or
                            any(q in member.lower() for member in p.get("team", []))]
    
    if filter_template != "All":
        filtered_projects = [p for p in filtered_projects if p.get("template") == filter_template]
    
    if filter_due:
        filtered_projects = [p for p in filtered_projects if 
                           p.get("dueDate") and date.fromisoformat(p["dueDate"]) <= filter_due]
    
    if filter_level != "All":
        filtered_projects = [
            p for p in filtered_projects
            if p.get("level", -1) >= 0 and
            p.get("levels") and
            len(p["levels"]) > p.get("level", -1) and
            p["levels"][p["level"]] == filter_level
        ]
    
    return filtered_projects
