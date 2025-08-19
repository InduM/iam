import streamlit as st
import time
from backend.projects_backend import *
from utils.utils_project_core import *
from utils.utils_project_substage import *
from utils.utils_project_form import _reset_create_form_state

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