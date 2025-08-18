import streamlit as st
import time
from datetime import date
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *
from utils.utils_project_user_sync import _initialize_services
from utils.utils_project_form import _reset_create_form_state, initialize_create_form_state
from .projects_display import (
    render_project_card, render_level_checkboxes_with_substages,
    render_custom_levels_editor, render_progress_section
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
        st.session_state.projects = load_projects_from_db()
        st.session_state.refresh_projects = False
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()


def show_dashboard():
    st.query_params["_"] = str(int(time.time() // 60))
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ New Project", use_container_width=True):
            st.session_state.view = "create"
            st.rerun()
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.refresh_projects = True
            st.rerun()

    with st.container():
        st.markdown("<div class='filter-bar'>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            search_query = st.text_input("🔍 Search", placeholder="Name, client, or team")
        with col2:
            filter_template = st.selectbox("📂 Template", ["All"] + list(TEMPLATES.keys()))
        with col3:
            # Subtemplate filter - only show when "Onwards" template is selected
            filter_subtemplate = "All"
            if filter_template == "Onwards":
                filter_subtemplate = st.selectbox("🔄 Subtemplate", ["All", "Foundation", "Work Readiness"])
            else:
                st.empty()  # Empty space when subtemplate not shown
        with col4:
            # Dynamic progress levels based on template/subtemplate selection
            progress_levels = _get_template_progress_levels(filter_template, filter_subtemplate)
            filter_level = st.selectbox("📊 Progress Level", ["All"] + progress_levels)
        with col5:
            filter_due = st.date_input("📅 Due Before or On", value=None)
        st.markdown("</div>", unsafe_allow_html=True)

    filtered_projects = _apply_filters(st.session_state.projects, search_query, filter_template, filter_subtemplate, filter_level, filter_due)

    # Display projects in 2 columns instead of 3
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

    if st.button("✅ Create Project", use_container_width=True):
        _handle_create_project(name, client, description, start, due, selected_subtemplate)


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
            st.warning("⚠ No clients found in the database.")
        current_client = project.get("client", "")
        if current_client in clients:
            client = st.selectbox("👤 Client", options=clients, index=clients.index(current_client))
        else:
            st.warning(f"⚠ Current client '{current_client}' not found in client list. Please select a new client.")
            client = st.selectbox("👤 Client", options=clients)
    else:
        # For Onwards projects, don't show client field but preserve existing client value
        client = project.get("client", "")
        if client:
            st.info(f"👤 Client field hidden for Onwards template. Current client: {client}")
    
    description = st.text_area("🗒 Project Description", value=project.get("description", ""))
    start = st.date_input("📅 Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("📅 Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))
    team_members = get_team_members_username(st.session_state.get("role", ""))
    st.markdown("<div class='section-header'>Stage Assignments</div>", unsafe_allow_html=True)
    current_stage_assignments = project.get("stage_assignments", {})
    stage_assignments = render_substage_assignments_editor(project.get("levels", ["Initial", "Invoice", "Payment"]), team_members, current_stage_assignments)
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
    st.subheader("Progress")
    def on_change_edit(new_index):
        fresh_proj = get_project_by_name(project_name)
        fresh_assignments = fresh_proj.get("stage_assignments", {}) if fresh_proj else {}
        handle_level_change(fresh_proj or project, pid, new_index, fresh_assignments, "edit")
    render_level_checkboxes_with_substages("edit", pid, int(project.get("level", -1)), project.get("timestamps", {}), project.get("levels", ["Initial", "Invoice", "Payment"]), on_change_edit, editable=True, stage_assignments=current_stage_assignments, project=project)
    if st.button("💾 Save", use_container_width=True):
        handle_save_project(pid, project, name, client, description, start, due, original_name, stage_assignments)

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
        st.session_state.create_initialized = False
        st.rerun()

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