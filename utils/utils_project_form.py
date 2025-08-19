import streamlit as st
from datetime import datetime
import time
from backend.projects_backend import (
    update_substage_completion_in_db,
)
from utils.utils_project_core import (
    get_current_timestamp
)
# UPDATED FUNCTION: Enhanced form state reset with substage completion clearing
def _reset_create_form_state():
    """Reset all create form state including stage assignments, substages, and completion data"""
    # Reset basic form fields
    if "selected_template" in st.session_state:
        st.session_state.selected_template = ""
    if "custom_levels" in st.session_state:
        st.session_state.custom_levels = []
    st.session_state.view = "dashboard"

    
    # Reset stage assignments and substages completely
    st.session_state.stage_assignments = {}
    
    # ENHANCED: Clear substage completion data
    if "substage_completion" in st.session_state:
        st.session_state.substage_completion = {}
    if "substage_timestamps" in st.session_state:
        st.session_state.substage_timestamps = {}
    st.session_state.level_timestamps = {}

    # Reset any substage-related states
    substage_keys = [key for key in st.session_state.keys() if key.startswith("substage_")]
    for key in substage_keys:
        del st.session_state[key]
    
    # Reset any assignment-related states
    assignment_keys = [key for key in st.session_state.keys() if "assignment" in key.lower()]
    for key in assignment_keys:
        del st.session_state[key]
    
    # Reset any deadline-related states
    deadline_keys = [key for key in st.session_state.keys() if "deadline" in key.lower()]
    for key in deadline_keys:
        del st.session_state[key]
    
    # ENHANCED: Clear completion tracking states
    completion_keys = [key for key in st.session_state.keys() if "completion" in key.lower()]
    for key in completion_keys:
        del st.session_state[key]
    
    # Reset view tracking
    st.session_state.last_view = None

def initialize_create_form_state():
    """Initialize create form state with all necessary defaults including substage completion and subtemplate"""
    # Initialize basic form state
    if "selected_template" not in st.session_state:
        st.session_state.selected_template = ""
    if "selected_subtemplate" not in st.session_state:
        st.session_state.selected_subtemplate = ""
    if "custom_levels" not in st.session_state:
        st.session_state.custom_levels = []
    if "stage_assignments" not in st.session_state:
        st.session_state.stage_assignments = {}
        
    if "substage_completion" not in st.session_state:
        st.session_state.substage_completion = {}
    if "substage_timestamps" not in st.session_state:
        st.session_state.substage_timestamps = {}
        
    # Ensure clean state when switching to create view
    if st.session_state.get("last_view") != "create":
        _reset_create_form_state()
        st.session_state.last_view = "create"

# NEW FUNCTION: Initialize project with empty substage completion
def initialize_empty_project_substages(project_levels, stage_assignments):
    """Initialize a new project with empty substage completion data"""
    substage_completion = {}
    substage_timestamps = {}
    
    if stage_assignments:
        for stage_idx in range(len(project_levels)):
            stage_key = str(stage_idx)
            if stage_key in stage_assignments:
                substages = stage_assignments[stage_key].get("substages", [])
                if substages:
                    # Initialize all substages as incomplete
                    substage_completion[stage_key] = {}
                    substage_timestamps[stage_key] = {}
                    for substage_idx in range(len(substages)):
                        substage_completion[stage_key][str(substage_idx)] = False
                        substage_timestamps[stage_key][str(substage_idx)] = None
    
    return substage_completion, substage_timestamps

def _check_project_name_exists(name):
    """Check if project name already exists"""
    from backend.projects_backend import get_db_collections
    collections = get_db_collections()
    return collections["projects"].find_one({"name": name}) is not None

def render_custom_levels_editor():
    """Render custom levels editor"""
    st.subheader("Customize Progress Levels")
    if not st.session_state.custom_levels:
        st.session_state.custom_levels = ["Initial"]
    
    # Remove required levels from custom levels for editing
    for required in ["Invoice", "Payment"]:
        if required in st.session_state.custom_levels:
            st.session_state.custom_levels.remove(required)
    
    editable_levels = st.session_state.custom_levels.copy()
    for i in range(len(editable_levels)):
        cols = st.columns([5, 1])
        editable_levels[i] = cols[0].text_input(
            f"Level {i+1}", value=editable_levels[i], key=f"level_{i}"
        )
        if len(editable_levels) > 1 and cols[1].button("➖", key=f"remove_{i}"):
            editable_levels.pop(i)
            st.session_state.custom_levels = editable_levels
            st.rerun()
    
    st.session_state.custom_levels = editable_levels
    
    if st.button("➕ Add Level"):
        st.session_state.custom_levels.append(f"New Level {len(st.session_state.custom_levels) + 1}")
        st.rerun()
    
    # Add required levels back
    st.session_state.custom_levels += ["Invoice", "Payment"]

def _detect_form_context(project_id):
    """Centralized form context detection"""
    return (project_id == "new" or 
            not project_id or 
            project_id.startswith("auto_") or
            project_id.startswith("form_"))
def _validate_sequential_access(current_index, target_index, max_completed, is_advance=True):
    """Centralized sequential validation logic"""
    if is_advance:
        return target_index == max_completed + 1
    else:
        return target_index == max_completed

def _get_completion_status(project, stage_key, substage_idx, is_form_context):
    """Centralized completion status retrieval"""
    if is_form_context:
        substage_completion = st.session_state.get("substage_completion", {})
    else:
        substage_completion = project.get("substage_completion", {}) if project else {}
    
    current_completion = substage_completion.get(stage_key, {})
    return current_completion.get(str(substage_idx), False)

def _handle_timestamp_update(project, project_id, stage_key, substage_idx, completed, is_form_context):
    """Centralized timestamp handling for both form and database contexts"""
    timestamp = get_current_timestamp() if completed else None
    
    if is_form_context:
        # Handle session state timestamps
        if "substage_timestamps" not in st.session_state:
            st.session_state.substage_timestamps = {}
        if stage_key not in st.session_state.substage_timestamps:
            st.session_state.substage_timestamps[stage_key] = {}
        
        if completed:
            st.session_state.substage_timestamps[stage_key][str(substage_idx)] = timestamp
        else:
            # Remove timestamp when unchecked
            if str(substage_idx) in st.session_state.substage_timestamps[stage_key]:
                del st.session_state.substage_timestamps[stage_key][str(substage_idx)]
    else:
        # Handle project timestamps
        if project:
            timestamp_key = "substage_timestamps"
            if timestamp_key not in project:
                project[timestamp_key] = {}
            if stage_key not in project[timestamp_key]:
                project[timestamp_key][stage_key] = {}
            
            if completed:
                project[timestamp_key][stage_key][str(substage_idx)] = timestamp
            else:
                # Remove timestamp when unchecked
                if str(substage_idx) in project[timestamp_key][stage_key]:
                    del project[timestamp_key][stage_key][str(substage_idx)]

def _update_substage_completion(project, project_id, stage_key, substage_idx, completed, is_form_context):
    """Centralized substage completion update"""
    if is_form_context:
        # Update session state
        if "substage_completion" not in st.session_state:
            st.session_state.substage_completion = {}
        if stage_key not in st.session_state.substage_completion:
            st.session_state.substage_completion[stage_key] = {}
        
        st.session_state.substage_completion[stage_key][str(substage_idx)] = completed
    else:
        # Update project data
        if project:
            if "substage_completion" not in project:
                project["substage_completion"] = {}
            if stage_key not in project["substage_completion"]:
                project["substage_completion"][stage_key] = {}
            
            project["substage_completion"][stage_key][str(substage_idx)] = completed
            
            # Update database for existing projects
            update_substage_completion_in_db(project_id, project["substage_completion"])

def _render_two_column_layout(left_content, right_content, left_ratio=1, right_ratio=3):
    """Reusable two-column layout"""
    col1, col2 = st.columns([left_ratio, right_ratio])
    with col1:
        left_content()
    with col2:
        right_content()

def _show_sequential_error(is_advance=True, is_substage=False):
    """Centralized sequential error messages"""
    if is_substage:
        if is_advance:
            st.error("❌ Complete substages sequentially!")
        else:
            st.error("❌ You can only uncheck the last completed substage!")
    else:
        if is_advance:
            st.error("❌ You can only advance to the next stage sequentially!")
        else:
            st.error("❌ You can only go back one stage at a time!")
    
    time.sleep(0.1)
    st.rerun()

def _render_completion_timestamp(timestamp, is_compact=False):
    """Centralized timestamp rendering"""
    if not timestamp:
        return
    
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if is_compact:
            st.caption(f"{dt.strftime('%m/%d %H:%M')}")
        else:
            st.caption(f"Completed: {dt.strftime('%Y-%m-%d %H:%M')}")
    except:
        st.caption(f"Completed: {timestamp}")
