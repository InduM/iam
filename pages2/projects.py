import streamlit as st
import time
from datetime import date
from typing import List

# Import functions from backend and utils
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *
from utils.utils_project_user_sync import _initialize_services

from utils.utils_project_form import _reset_create_form_state,initialize_create_form_state
from .projects_display import (
    render_project_card, render_level_checkboxes_with_substages,
    render_custom_levels_editor, render_progress_section
)

from .project_logic import (
    _handle_create_project,
    _handle_save_project,
    handle_level_change,
)
from .project_helpers import (
    _check_edit_success_messages
)

def run():
    """Main function to run the project management interface"""
    
    # Initialize session state
    initialize_session_state()
    _initialize_services()
    
    if "last_view" not in st.session_state:
        st.session_state.last_view = None


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
    """Display the create project form with substage support and proper field reset"""
    st.title("🛠 Create Project")
    
    # ENHANCED: Proper form state initialization and reset
    initialize_create_form_state()

    # Back button
    _render_back_button()
    
    # Template selection
    template_options = ["Custom Template"] + list(TEMPLATES.keys())
    selected = st.selectbox("Select Template (optional)", template_options, 
                           index=0 if not st.session_state.selected_template else None)
    
    if selected != "Custom Template":
        # If template changed, reset stage assignments
        if st.session_state.selected_template != selected:
            st.session_state.stage_assignments = {}
        st.session_state.selected_template = selected
    else:
        # If switching to custom, reset everything
        if st.session_state.selected_template:
            st.session_state.stage_assignments = {}
        st.session_state.selected_template = ""
    
    # Form fields (these will be empty on new project)
    name = st.text_input("Project Name", value="")  # Explicit empty value
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    client = st.selectbox("Client", options=[""] + clients, index=0)  # Start with empty selection
    description = st.text_area("Project Description", value="")  # Explicit empty value
    start = st.date_input("Start Date", value=date.today())  # Default to today
    due = st.date_input("Due Date", value=date.today())  # Default to today
    
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
    stage_assignments = render_substage_assignments_editor(
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
    """Simplified edit form that always fetches fresh data on refresh"""
    pid = st.session_state.edit_project_id
    
    # Get current project for the header
    current_project = next((p for p in st.session_state.projects if p["id"] == pid), None)
    project_name = current_project.get("name", "") if current_project else ""
    
    # Render header with refresh button
    _render_edit_header_with_refresh(project_name, pid)
    
    # Check for refresh success message first
    if st.session_state.get(f"edit_refresh_success_{pid}", False):
        st.success("✅ Project data refreshed from database!")
        del st.session_state[f"edit_refresh_success_{pid}"]
    
    # Initialize edit mode if not done yet
    if not st.session_state.get(f"edit_initialized_{pid}", False):
        _initialize_edit_mode_state(pid)
        st.session_state[f"edit_initialized_{pid}"] = True
        st.rerun()
    
    # Get current project data - always fresh after refresh
    if not current_project:
        st.error("Project not found.")
        return
    
    # For direct database access, bypass session cache completely
    fresh_project = get_project_by_name(project_name)
    if not fresh_project:
        st.error("Project not found in database.")
        return
    
    # Use fresh project data instead of cached data
    project = ensure_project_defaults(fresh_project)
    
    original_team = project.get("team", [])
    original_name = project.get("name", "")
    
    # Form fields using fresh project data
    name = st.text_input("Project Name", value=project.get("name", ""))
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    
    # Client dropdown with safe default
    current_client = project.get("client", "")
    if current_client in clients:
        client = st.selectbox("Client", options=clients, index=clients.index(current_client))
    else:
        st.warning(f"⚠ Current client '{current_client}' not found in client list. Please select a new client.")
        client = st.selectbox("Client", options=clients)

    description = st.text_area("Project Description", value=project.get("description", ""))
    start = st.date_input("Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))
    
    team_members = get_team_members(st.session_state.get("role", ""))    
    
    # Stage Assignments Section - always use fresh data
    st.markdown("---")
    
    # Get fresh stage assignments directly from the database project
    current_stage_assignments = project.get("stage_assignments", {})
    
    # Use direct rendering without caching
    stage_assignments = render_substage_assignments_editor(
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
    
    # Progress section
    st.subheader("Progress")
    
    def on_change_edit(new_index):
        # Use fresh stage assignments for level changes
        fresh_proj = get_project_by_name(project_name)
        fresh_assignments = fresh_proj.get("stage_assignments", {}) if fresh_proj else {}
        handle_level_change(fresh_proj or project, pid, new_index, fresh_assignments,"edit")
    
    # Check for success messages
    _check_edit_success_messages(pid)
    
    # Render level checkboxes with fresh data
    render_level_checkboxes_with_substages(
        "edit", pid, int(project.get("level", -1)), 
        project.get("timestamps", {}), project.get("levels", ["Initial", "Invoice", "Payment"]), 
        on_change_edit, editable=True, stage_assignments=current_stage_assignments, project=project
    )
    
    if st.button("💾 Save"):
        _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments)


def _render_back_button():
    """Enhanced back button with cleanup"""
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
        # NEW: Clean up edit mode before navigating
        _handle_edit_navigation_cleanup()
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

# NEW FUNCTION: Clean navigation state
def _clean_navigation_state():
    """Clean up navigation-related session state"""
    navigation_keys = [
        "edit_project_id", "confirm_delete", "level_update_success",
        "edit_level_update_success", "auto_advance_success", 
        "auto_uncheck_success", "project_completed_message"
    ]
    
    for key in navigation_keys:
        if key in st.session_state:
            if isinstance(st.session_state[key], dict):
                st.session_state[key].clear()
            else:
                del st.session_state[key]

# NEW FUNCTION: Reset all project-related state
def reset_all_project_state():
    """Reset all project-related session state for clean slate"""
    # Reset form states
    _reset_create_form_state()
    
    # Clean navigation state
    _clean_navigation_state()
    
    # Reset view
    st.session_state.view = "dashboard"
    st.session_state.last_view = None
    
    # Force projects refresh
    st.session_state.refresh_projects = True


def _clear_edit_mode_cache(project_id):
    """Comprehensive cache clearing for edit mode"""
    # Remove all project-specific cached data
    cache_patterns = [
        f"project_{project_id}_",
        f"edit_stage_cache_{project_id}",
        f"edit_substage_cache_{project_id}",
        f"edit_assignments_cache_{project_id}",
        f"substages_{project_id}",
        f"substage_cache_{project_id}",
        f"substage_data_{project_id}",
        f"fresh_substages_{project_id}",
        f"latest_substage_key_{project_id}"
    ]
    
    # Remove keys that match patterns
    keys_to_remove = []
    for key in st.session_state.keys():
        for pattern in cache_patterns:
            if pattern in key:
                keys_to_remove.append(key)
                break
    
    for key in keys_to_remove:
        del st.session_state[key]


def _initialize_edit_mode_state(project_id):
    """Enhanced initialize edit mode with aggressive cache clearing and fresh substage loading"""
    # Clear all cached data first
    _clear_edit_mode_cache(project_id)
    _clear_all_substage_cache(project_id)
    
    # Clear any edit-specific session state
    edit_state_keys = [
        f"edit_level_update_success_{project_id}",
        f"edit_stage_modified_{project_id}",
        f"edit_substage_modified_{project_id}",
        "edit_form_dirty",
        "edit_validation_errors",
        f"substage_editor_state_{project_id}",
        f"substage_form_data_{project_id}",
        f"substage_render_cache_{project_id}",
        # Clear any old substage cache keys
        f"latest_substage_key_{project_id}"
    ]
    
    for key in edit_state_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear any cached substage keys for this project
    keys_to_remove = []
    for key in st.session_state.keys():
        if f"fresh_substages_{project_id}" in key:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]
    
    # Force refresh of project data from MongoDB
    st.session_state.refresh_projects = True
    
    # Pre-load fresh substage data
    try:
        current_project = next((p for p in st.session_state.projects if p["id"] == project_id), None)
        if current_project:
            project_name = current_project.get("name", "")
            if project_name:
                # Fetch and cache fresh substages immediately
                _get_fresh_substage_data(project_id)
    except Exception as e:
        st.warning(f"Could not pre-load substage data: {str(e)}")



def _handle_edit_navigation_cleanup():
    """Enhanced cleanup with substage cache clearing and refresh success cleanup"""
    if st.session_state.get("edit_project_id"):
        pid = st.session_state.edit_project_id
        # Clear edit-specific cache
        _clear_edit_mode_cache(pid)
        # Clear all substage cache
        _clear_all_substage_cache(pid)
        # Reset edit initialization flag
        if f"edit_initialized_{pid}" in st.session_state:
            del st.session_state[f"edit_initialized_{pid}"]
        # Clear force refresh flag
        if f"force_substage_refresh_{pid}" in st.session_state:
            del st.session_state[f"force_substage_refresh_{pid}"]
        # Clear refresh success message
        if f"edit_refresh_success_{pid}" in st.session_state:
            del st.session_state[f"edit_refresh_success_{pid}"]

def _clear_all_substage_cache(project_id=None):
    """Comprehensive substage cache clearing"""
    # Clear all substage-related keys
    keys_to_remove = []
    
    for key in list(st.session_state.keys()):
        # Remove any key containing substage-related terms
        if any(term in key.lower() for term in ['substage', 'sub_stage', 'stage_assignment']):
            keys_to_remove.append(key)
        
        # Remove project-specific substage keys
        if project_id and str(project_id) in key and any(term in key.lower() for term in ['substage', 'stage', 'assignment']):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

    
def _get_fresh_substage_data(project_id, stage_name=None):
    """Enhanced function to get fresh substage data with database fallback"""
    try:
        # First try to get from latest refresh cache
        latest_key = st.session_state.get(f"latest_substage_key_{project_id}")
        if latest_key and latest_key in st.session_state:
            fresh_substages = st.session_state[latest_key]
            if stage_name:
                return fresh_substages.get(stage_name, {})
            return fresh_substages
        
        # Fallback: fetch directly from database
        current_project = next((p for p in st.session_state.projects if p["id"] == project_id), None)
        if not current_project:
            return {}
            
        project_name = current_project.get("name", "")
        if not project_name:
            return {}
        
        # Fetch fresh project data from database
        fresh_project = get_project_by_name(project_name)
        if not fresh_project:
            return {}
        
        # Extract substage data
        fresh_substages = {}
        stage_assignments = fresh_project.get("stage_assignments", {})
        
        for stage_name_key, assignment_data in stage_assignments.items():
            if isinstance(assignment_data, dict) and "substages" in assignment_data:
                fresh_substages[stage_name_key] = assignment_data["substages"]
        
        # Cache the fresh data
        timestamp_key = f"fresh_substages_{project_id}_{int(time.time())}"
        st.session_state[timestamp_key] = fresh_substages
        st.session_state[f"latest_substage_key_{project_id}"] = timestamp_key
        
        if stage_name:
            return fresh_substages.get(stage_name, {})
        
        return fresh_substages
        
    except Exception as e:
        st.error(f"Error getting fresh substage data: {str(e)}")
        return {}


def _handle_edit_refresh(project_id):
    """Direct database refresh that bypasses all session state caching"""
    try:
        # Get current project name
        current_project = next((p for p in st.session_state.projects if p["id"] == project_id), None)
        if not current_project:
            st.error("Project not found in session state")
            return
        
        project_name = current_project.get("name", "")
        if not project_name:
            st.error("Project name not found")
            return
        
        # STEP 1: Complete cache clearing - be very aggressive
        _clear_edit_mode_cache(project_id)
        _clear_all_substage_cache(project_id)
        
        # STEP 2: Clear the entire projects list to force fresh fetch
        if "projects" in st.session_state:
            del st.session_state["projects"]
        
        # STEP 3: Force immediate reload of all projects from database
        st.session_state.projects = load_projects_from_db()
        
        # STEP 4: Reset edit initialization flag
        if f"edit_initialized_{project_id}" in st.session_state:
            del st.session_state[f"edit_initialized_{project_id}"]
        
        # STEP 5: Set refresh success flag
        st.session_state[f"edit_refresh_success_{project_id}"] = True
        
        # STEP 6: Force immediate rerun
        st.rerun()
        
    except Exception as e:
        st.error(f"Error refreshing project data: {str(e)}")


def _render_edit_header_with_refresh(project_name, project_id):
    """Enhanced header with better refresh button"""
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.title("✏ Edit Project")
        if project_name:
            st.caption(f"Editing: {project_name}")
    
    with col2:
        if st.button("🔄 Refresh", key=f"refresh_edit_{project_id}", help="Reload from database", type="secondary"):
            _handle_edit_refresh(project_id)
    
    with col3:
        if st.button("← Back", key="back_button", type="primary"):
            _handle_edit_navigation_cleanup()
            st.session_state.view = "dashboard"
            st.rerun()