import streamlit as st
from datetime import time
from utils.utils_project_core import (
    validate_project_dates,
    get_current_timestamp
)
from backend.projects_backend import (
    save_project_to_db,
    update_client_project_count,
    add_project_to_manager,
    update_project_in_db,
    update_project_name_in_user_profiles,
    update_project_level_in_db,
    move_project_to_completed,
    notify_assigned_members,
)
from project_helpers import (
    create_project_data, create_updated_project_data,
    send_stage_assignment_notifications,
    _reset_create_form_state,
    _update_client_counts_after_edit,
    _display_success_messages,
    _send_stage_assignment_change_notifications,
)

def _handle_create_project(name, client, description, start, due):
    """Handle project creation"""
    if not validate_project_dates(start, due):
        st.error("Cannot submit: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    elif _check_project_name_exists(name):
        st.error("A project with this name already exists. Please choose a different name.")
    else:
        new_proj = create_project_data(name, client, description, start, due)
        
        project_id = save_project_to_db(new_proj)
        if project_id:
            new_proj["id"] = project_id
            st.session_state.projects.append(new_proj)
            st.success("Project created and saved to database!")
            
            # Update client project count
            update_client_project_count(client)
            
            # Send stage assignment notifications
            send_stage_assignment_notifications(new_proj)
            
            # Reset form state and navigate back
            _reset_create_form_state()
            
            add_project_to_manager(st.session_state.get("username", ""), name)
            
            st.rerun()

def _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments):
    """Handle project save with substage data"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    else:
        updated_project = create_updated_project_data(project, name, client, description, start, due, stage_assignments)
        
        # Include substage completion data
        if "substage_completion" in project:
            updated_project["substage_completion"] = project["substage_completion"]
        if "substage_timestamps" in project:
            updated_project["substage_timestamps"] = project["substage_timestamps"]
        
        if update_project_in_db(pid, updated_project):
            success_messages = []
            
            # Update client project counts
            _update_client_counts_after_edit(project, client)
            
            # Handle name change
            if original_name != name:
                updated_count = update_project_name_in_user_profiles(original_name, name)
                if updated_count > 0:
                    success_messages.append(f"Project name updated in {updated_count} user profiles!")
            
            # Handle stage assignment changes
            old_assignments = project.get("stage_assignments", {})
            if stage_assignments != old_assignments:
                success_messages.append("Stage assignments updated!")
                _send_stage_assignment_change_notifications(stage_assignments, old_assignments, name)
            
            project.update(updated_project)
            
            # Display success messages
            _display_success_messages(success_messages)
            
            st.session_state.view = "dashboard"
            st.rerun()

def _handle_level_change_dashboard(proj_id, proj, new_index, stage_assignments):
    """Handle level change in dashboard view with sequential validation"""
    current_level = proj.get("level", -1)
    
    # Sequential validation for main stages
    if new_index > current_level:
        # Can only advance one stage at a time
        if new_index != current_level + 1:
            st.error("❌ You can only advance to the next stage sequentially!")
            return
        
        # Check if all substages are complete for the new stage
        if not _are_all_substages_complete(proj, stage_assignments, new_index):
            st.error("❌ Cannot advance to this stage - complete all substages first!")
            return
    elif new_index < current_level:
        # Can only go back one stage at a time
        if new_index != current_level - 1:
            st.error("❌ You can only go back one stage at a time!")
            return
    
    timestamp = get_current_timestamp()
    
    # Handle unchecking - remove timestamps for unchecked stages
    if new_index < current_level:
        levels = proj.get("levels", [])
        for level_idx in range(new_index + 1, len(levels)):
            if level_idx <= current_level:
                if "timestamps" in proj and str(level_idx) in proj["timestamps"]:
                    del proj["timestamps"][str(level_idx)]
    
    if update_project_level_in_db(proj_id, new_index, timestamp):
        proj["level"] = new_index
        if "timestamps" not in proj:
            proj["timestamps"] = {}
        proj["timestamps"][str(new_index)] = timestamp
        
        # Notify assigned members for the new stage
        if stage_assignments:
            notify_assigned_members(stage_assignments, proj.get("name", ""), new_index)
        
        # Check if project reached Payment stage
        _check_project_completion(proj, proj_id)
        
        st.session_state[f"level_update_success_{proj_id}"] = True
        st.success("Project level updated!")
        time.sleep(0.1)
        st.rerun()

def _handle_level_change_edit(project, pid, new_index, stage_assignments):
    """Handle level change in edit view with sequential validation"""
    current_level = project.get("level", -1)
    
    # Sequential validation for main stages
    if new_index > current_level:
        # Can only advance one stage at a time
        if new_index != current_level + 1:
            st.error("❌ You can only advance to the next stage sequentially!")
            return
        
        # Check if all substages are complete for the new stage
        if not _are_all_substages_complete(project, stage_assignments, new_index):
            st.error("❌ Cannot advance to this stage - complete all substages first!")
            return
    elif new_index < current_level:
        # Can only go back one stage at a time
        if new_index != current_level - 1:
            st.error("❌ You can only go back one stage at a time!")
            return
    
    timestamp = get_current_timestamp()
    
    # Handle unchecking - remove timestamps for unchecked stages
    if new_index < current_level:
        levels = project.get("levels", [])
        for level_idx in range(new_index + 1, len(levels)):
            if level_idx <= current_level:
                if "timestamps" in project and str(level_idx) in project["timestamps"]:
                    del project["timestamps"][str(level_idx)]
    
    project["level"] = new_index
    project.setdefault("timestamps", {})[str(new_index)] = timestamp
    
    # Update in database immediately
    if update_project_level_in_db(pid, new_index, timestamp):
        # Notify assigned members for the new stage
        if stage_assignments:
            notify_assigned_members(stage_assignments, project.get("name", ""), new_index)
        
        _check_project_completion(project, pid)
        st.session_state[f"edit_level_update_success_{pid}"] = True
        st.success("Project level updated!")
        time.sleep(0.1)
        st.rerun()

def _are_all_substages_complete(project, stage_assignments, stage_index):
    """
    Check if all substages for a given stage are completed
    """
    if not project or not stage_assignments:
        return True  # No substages means stage can be completed
    
    stage_key = str(stage_index)
    if stage_key not in stage_assignments:
        return True  # No substages defined for this stage
    
    substages = stage_assignments[stage_key].get("substages", [])
    if not substages:
        return True  # No substages means stage can be completed
    
    substage_completion = project.get("substage_completion", {})
    stage_completion = substage_completion.get(stage_key, {})
    
    # Check if all substages are completed
    for substage_idx in range(len(substages)):
        if not stage_completion.get(str(substage_idx), False):
            return False
    
    return True

def _has_substages(stage_assignments, stage_index):
    """
    Check if a stage has substages defined
    """
    if not stage_assignments:
        return False
    
    stage_key = str(stage_index)
    if stage_key not in stage_assignments:
        return False
    
    substages = stage_assignments[stage_key].get("substages", [])
    return len(substages) > 0

def _auto_advance_main_stage(project, project_id, stage_index):
    """
    Automatically advance the main stage when all substages are completed
    """
    current_level = project.get("level", -1)
    
    # Only auto-advance if this is the next stage
    if stage_index == current_level + 1:
        timestamp = get_current_timestamp()
        project["level"] = stage_index
        if "timestamps" not in project:
            project["timestamps"] = {}
        project["timestamps"][str(stage_index)] = timestamp
        
        # Update in database
        if update_project_level_in_db(project_id, stage_index, timestamp):
            # Get stage assignments for notifications
            stage_assignments = project.get("stage_assignments", {})
            
            # Notify assigned members for the new stage
            if stage_assignments:
                notify_assigned_members(stage_assignments, project.get("name", ""), stage_index)
            
            # Check if project reached completion
            _check_project_completion(project, project_id)
            
            # Set success message
            st.session_state[f"auto_advance_success_{project_id}_{stage_index}"] = True
            st.success(f"🎉 Stage {stage_index + 1} automatically completed - all substages done!")


def _auto_uncheck_main_stage(project, project_id, stage_index):
    """
    Automatically uncheck the main stage when a substage is unchecked
    Enhanced to handle sequential unchecking
    """
    current_level = project.get("level", -1)
    
    # Only auto-uncheck if this stage is currently completed
    if stage_index <= current_level:
        # Set the level to one stage before this stage
        new_level = stage_index - 1
        
        # Sequential unchecking: uncheck all stages after the new level
        levels = project.get("levels", [])
        for level_idx in range(new_level + 1, len(levels)):
            if level_idx <= current_level:
                # Remove timestamps for unchecked stages
                if "timestamps" in project and str(level_idx) in project["timestamps"]:
                    del project["timestamps"][str(level_idx)]
        
        project["level"] = new_level
        if "timestamps" not in project:
            project["timestamps"] = {}
        
        # Update the timestamp for the new current level
        if new_level >= 0:
            project["timestamps"][str(new_level)] = get_current_timestamp()
        
        # Update in database
        if update_project_level_in_db(project_id, new_level, get_current_timestamp()):
            # Set success message
            st.session_state[f"auto_uncheck_success_{project_id}_{stage_index}"] = True
            st.warning(f"⚠️ Stage {stage_index + 1} and subsequent stages automatically unchecked!")


def _check_project_completion(project, project_id):
    """Check if project has reached completion stage"""
    project_levels = project.get("levels", [])
    new_level = project.get("level", -1)
    
    if (new_level >= 0 and new_level < len(project_levels) and 
        project_levels[new_level] == "Payment"):
        project_name = project.get("name", "")
        team_members = project.get("team", [])
        moved_count = move_project_to_completed(project_name, team_members)
        if moved_count > 0:
            st.session_state[f"project_completed_message_{project_id}"] = \
                f"Project moved to completed for {moved_count} team member(s)!"

def _check_project_name_exists(name):
    """Check if project name already exists"""
    from backend.projects_backend import get_db_collections
    collections = get_db_collections()
    return collections["projects"].find_one({"name": name}) is not None
