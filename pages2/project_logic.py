import streamlit as st
import time

from utils.utils_project_user_sync import(
    _sync_user_projects_on_stage_change
)
from utils.utils_project_core import (
    validate_project_dates,
    get_current_timestamp,
    notify_assigned_members,
)

from utils.utils_project_form import (
    _check_project_name_exists,
    _reset_create_form_state,
    )

from backend.projects_backend import (
    save_project_to_db,
    update_client_project_count,
    add_project_to_manager,
    update_project_in_db,
    update_project_name_in_user_profiles,
    update_project_level_in_db,
    move_project_to_completed,
    delete_project_from_db,
    remove_project_from_all_users,
)
from .project_helpers import (
    create_project_data, create_updated_project_data,
    send_stage_assignment_notifications,
    _update_client_counts_after_edit,
    _display_success_messages,
    _send_stage_assignment_change_notifications,
    _get_user_email_from_username,
    validate_user_assignments,
    sync_all_stage_assignments_to_user_profiles


)

from .project_completion import(
    _are_all_substages_complete,
   _check_project_completion,
   _handle_stage_completion_cleanup
 )

from .project_date_utils import (
    validate_stage_substage_dates,
)
# UPDATED FUNCTION: Enhanced create project handler with substage completion reset
def _handle_create_project(name, client, description, start, due):
    """Enhanced create project handler with comprehensive user-project sync"""
    if not validate_project_dates(start, due):
        st.error("Cannot submit: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    elif _check_project_name_exists(name):
        st.error("A project with this name already exists. Please choose a different name.")
    else:
        # Validate stage and substage dates
        stage_assignments = st.session_state.get("stage_assignments", {})
        date_errors = validate_stage_substage_dates(stage_assignments, due)
        
        if date_errors:
            st.error("Cannot create project due to date validation errors:")
            for error in date_errors:
                st.error(f"• {error}")
            return
        
        # Validate user assignments before creating project
        is_valid, invalid_users = validate_user_assignments(stage_assignments)
        if not is_valid:
            st.error("Cannot create project - the following users don't exist in the database:")
            for user in invalid_users:
                st.error(f"• {user}")
            return
        
        new_proj = create_project_data(name, client, description, start, due)
        
        # Ensure new project has clean substage completion data
        new_proj["substage_completion"] = {}
        new_proj["substage_timestamps"] = {}
        
        project_id = save_project_to_db(new_proj)
        if project_id:
            new_proj["id"] = project_id
            st.session_state.projects.append(new_proj)
            st.success("Project created and saved to database!")
            
            # Update client project count
            update_client_project_count(client)
            
            # Send stage assignment notifications
            send_stage_assignment_notifications(new_proj)
            
            # Add project to manager
            add_project_to_manager(st.session_state.get("username", ""), name)
            
            # ENHANCED: Sync all stage assignments to user profiles
            from .project_helpers import sync_all_stage_assignments_to_user_profiles
            success_count = sync_all_stage_assignments_to_user_profiles(name, stage_assignments)
            if success_count > 0:
                st.success(f"✅ Project added to {success_count} user profiles!")
            
            # Complete form state reset
            _reset_create_form_state()
            
            # Navigate back to dashboard
            st.session_state.view = "dashboard"
            st.rerun()

# UPDATED FUNCTION: Enhanced save project handler with date validation
def _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments):
    """Enhanced save project handler with comprehensive user-project sync"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    else:
        # Validate stage and substage dates
        date_errors = validate_stage_substage_dates(stage_assignments, due)
        
        if date_errors:
            st.error("Cannot save project due to date validation errors:")
            for error in date_errors:
                st.error(f"• {error}")
            return
        
        # Validate user assignments before saving
        is_valid, invalid_users = validate_user_assignments(stage_assignments)
        if not is_valid:
            st.error("Cannot save project - the following users don't exist in the database:")
            for user in invalid_users:
                st.error(f"• {user}")
            return
        
        # Get old stage assignments BEFORE update
        old_stage_assignments = project.get("stage_assignments", {})
        
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
            
            # Handle name change - update user profiles
            if original_name != name:
                updated_count = update_project_name_in_user_profiles(original_name, name)
                if updated_count > 0:
                    success_messages.append(f"Project name updated in {updated_count} user profiles!")
            
            # Handle stage assignment changes with comprehensive user sync
            if stage_assignments != old_stage_assignments:
                success_messages.append("Stage assignments updated!")
                _send_stage_assignment_change_notifications(stage_assignments, old_stage_assignments, name)
                
                # ENHANCED: Comprehensive user-project sync
                from .project_helpers import sync_user_assignment_changes
                sync_success = sync_user_assignment_changes(
                    name, old_stage_assignments, stage_assignments
                )
                if sync_success:
                    success_messages.append("✅ User project assignments synchronized!")
                
                # Also clean up unassigned users
                from .project_helpers import remove_project_from_unassigned_users
                removed_count = remove_project_from_unassigned_users(name, stage_assignments)
                if removed_count > 0:
                    success_messages.append(f"🧹 Project removed from {removed_count} unassigned user profiles!")
            
            project.update(updated_project)
            
            # Display success messages
            _display_success_messages(success_messages)
            
            st.session_state.view = "dashboard"
            st.rerun()


def _handle_project_deletion(pid, project):
    """Enhanced handle project deletion with user-project sync cleanup"""
    if delete_project_from_db(pid):
        project_name = project.get("name", "Unnamed")
        
        # Remove from projects list
        st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != pid]
        
        # Remove project from all user profiles
        remove_project_from_all_users(project_name)
        
        # Update client project count after deletion
        client_name = project.get("client", "")
        update_client_project_count(client_name)
        
        st.success(f"✅ Project '{project_name}' deleted and removed from all user profiles!")
    
    st.session_state.confirm_delete[f"confirm_delete_{pid}"] = False
    st.rerun()

def handle_substage_assignment_change(project_name, stage_name, substage_name, old_assignee, new_assignee):
    """
    Handle real-time user-project sync when substage assignment changes
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        substage_name: Name of the substage
        old_assignee: Previous assignee username
        new_assignee: New assignee username
    
    Returns:
        bool: True if sync was successful
    """
    try:
        from .project_helpers import sync_substage_assignment_change
        return sync_substage_assignment_change(
            project_name, stage_name, substage_name, old_assignee, new_assignee
        )
    except Exception as e:
        st.error(f"Error handling substage assignment change: {str(e)}")
        return False
    
def handle_stage_assignment_change_realtime(project_name, stage_name, old_assignment, new_assignment):
    """
    Handle real-time user-project sync when stage assignment changes
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        old_assignment: Previous assignment data
        new_assignment: New assignment data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        from .project_helpers import handle_stage_assignment_change
        return handle_stage_assignment_change(
            project_name, stage_name, old_assignment, new_assignment
        )
    except Exception as e:
        st.error(f"Error handling stage assignment change: {str(e)}")
        return False

def handle_level_change(project, project_id, new_index, stage_assignments, context="dashboard"):
    """
    Unified level change handler for both dashboard and edit contexts
    
    Args:
        project: Project dictionary
        project_id: Project ID
        new_index: New level index to set
        stage_assignments: Stage assignments dictionary
        context: "dashboard" or "edit" to handle context-specific logic
    
    Returns:
        bool: True if level change was successful, False otherwise
    """
       # Validate that project is a dictionary
    if not isinstance(project, dict):
        st.error(f"❌ Invalid project data type: expected dict, got {type(project)}")
        return False
    
    current_level = project.get("level", -1)
    
    # Sequential validation for main stages
    if new_index > current_level:
        # Can only advance one stage at a time
        if new_index != current_level + 1:
            st.error("❌ You can only advance to the next stage sequentially!")
            return False
        
        # Check if all substages are complete for the new stage
        if not _are_all_substages_complete(project, stage_assignments, new_index):
            st.error("❌ Cannot advance to this stage - complete all substages first!")
            return False
    elif new_index < current_level:
        # Can only go back one stage at a time
        if new_index != current_level - 1:
            st.error("❌ You can only go back one stage at a time!")
            return False
    
    # Store old stage assignments for user-project sync (edit context only)
    old_stage_assignments = None
    if context == "edit":
        old_stage_assignments = project.get("stage_assignments", {})
    
    timestamp = get_current_timestamp()
    
    # Handle unchecking - remove timestamps for unchecked stages
    if new_index < current_level:
        levels = project.get("levels", [])
        for level_idx in range(new_index + 1, len(levels)):
            if level_idx <= current_level:
                if "timestamps" in project and str(level_idx) in project["timestamps"]:
                    del project["timestamps"][str(level_idx)]
    
    # Handle stage completion cleanup when advancing (edit context only)
    if context == "edit" and new_index > current_level:
        _handle_stage_completion_cleanup(project, project_id, new_index)
    
    # Update project level and timestamp
    project["level"] = new_index
    if "timestamps" not in project:
        project["timestamps"] = {}
    project["timestamps"][str(new_index)] = timestamp
    
    # Update in database
    if update_project_level_in_db(project_id, new_index, timestamp):
        # Notify assigned members for the new stage - ensure stage_assignments is a dict
        if stage_assignments and isinstance(stage_assignments, dict):
            notify_assigned_members(stage_assignments, project.get("name", ""), new_index)
        
        # Context-specific user-project sync (edit context only)
        if context == "edit" and old_stage_assignments is not None:
            current_stage_assignments = project.get("stage_assignments", {})
            if current_stage_assignments != old_stage_assignments:
                project_name = project.get("name", "")
                _sync_user_projects_on_stage_change(
                    project_name, old_stage_assignments, current_stage_assignments
                )
        
        # Check if project reached completion
        _check_project_completion(project, project_id)
        
        # Set context-specific success state
        success_key = f"level_update_success_{project_id}" if context == "dashboard" else f"edit_level_update_success_{project_id}"
        st.session_state[success_key] = True
        
        st.success("Project level updated!")
        time.sleep(0.1)
        st.rerun()
        return True
    return False

def validate_and_sync_project_users(project_name, stage_assignments):
    """
    Validate and sync all users for a project
    
    Args:
        project_name: Name of the project
        stage_assignments: Dictionary of stage assignments
    
    Returns:
        tuple: (success, message)
    """
    try:
        
        # First validate all users exist
        is_valid, invalid_users = validate_user_assignments(stage_assignments)
        if not is_valid:
            return False, f"Invalid users found: {', '.join(invalid_users)}"
        
        # Then sync all assignments
        success_count = sync_all_stage_assignments_to_user_profiles(project_name, stage_assignments)
        
        return True, f"Project synced to {success_count} user profiles"
        
    except Exception as e:
        return False, f"Error validating and syncing users: {str(e)}"