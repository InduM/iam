import streamlit as st

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
