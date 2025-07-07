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
)

from .project_completion import(
    _are_all_substages_complete,
   _check_project_completion,
 )

from .project_date_utils import (
    validate_stage_substage_dates,
)
# UPDATED FUNCTION: Enhanced create project handler with substage completion reset
def _handle_create_project(name, client, description, start, due):
    """Enhanced version of your existing create function with improved user-project sync"""
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
        
        new_proj = create_project_data(name, client, description, start, due)
        
        # ENHANCED: Ensure new project has clean substage completion data
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
            
            # ENHANCED: Update user project assignments based on stage assignments
            _update_user_project_assignments(name, stage_assignments)
            
            # ENHANCED: Complete form state reset including substages and completion data
            _reset_create_form_state()
            
            # Navigate back to dashboard
            st.session_state.view = "dashboard"
            st.rerun()

# UPDATED FUNCTION: Enhanced save project handler with date validation
def _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments):
    """Enhanced version of your existing save function with improved user-project sync"""
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
            
            # Handle name change
            if original_name != name:
                updated_count = update_project_name_in_user_profiles(original_name, name)
                if updated_count > 0:
                    success_messages.append(f"Project name updated in {updated_count} user profiles!")
            
            # Handle stage assignment changes and update user project assignments
            if stage_assignments != old_stage_assignments:
                success_messages.append("Stage assignments updated!")
                _send_stage_assignment_change_notifications(stage_assignments, old_stage_assignments, name)
                
                # ENHANCED: Update user project assignments based on new stage assignments
                _update_user_project_assignments(name, stage_assignments)
            
            project.update(updated_project)
            
            # Display success messages
            _display_success_messages(success_messages)
            
            st.session_state.view = "dashboard"
            st.rerun()


def _handle_project_deletion(pid, project):
    """Handle project deletion"""
    if delete_project_from_db(pid):
        st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != pid]
        remove_project_from_all_users(project.get("name", "Unnamed"))
        st.success("Project deleted from database.")
        
        # Update client project count after deletion
        client_name = project.get("client", "")
        update_client_project_count(client_name)
    
    st.session_state.confirm_delete[f"confirm_delete_{pid}"] = False
    st.rerun()

def _update_user_project_assignments(project_name, stage_assignments):
    """
    Update user project assignments when stage assignments change.
    Adds project to users assigned to any stage/substage.
    """
    try:
        from backend.users_backend import UserService, DatabaseManager
        
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        # Collect all assigned users from all stages and substages
        assigned_users = set()
        
        for stage_name, assignment_data in stage_assignments.items():
            if isinstance(assignment_data, dict):
                # Main stage assignment
                main_assignee = assignment_data.get("assigned_to", "")
                if main_assignee and main_assignee != "":
                    assigned_users.add(main_assignee)
                
                # Substage assignments
                substages = assignment_data.get("substages", {})
                for substage_name, substage_data in substages.items():
                    if isinstance(substage_data, dict):
                        substage_assignee = substage_data.get("assigned_to", "")
                        if substage_assignee and substage_assignee != "":
                            assigned_users.add(substage_assignee)
        
        # Add project to each assigned user's current projects
        for username in assigned_users:
            # Convert username to email format 
            user_email = _get_user_email_from_username(username)
            
            # Fetch current user data
            user_data = user_service.fetch_user_data(user_email)
            if user_data:
                current_projects = user_data.get("project", [])
                
                # Add project if not already in list
                if project_name not in current_projects:
                    current_projects.append(project_name)
                    user_service.update_member(user_email, {"project": current_projects})
                    
        return True
        
    except Exception as e:
        st.error(f"Error updating user project assignments: {str(e)}")
        return False


def _handle_stage_completion_cleanup(project, project_id, completed_level):
    """
    Handle cleanup when a stage is completed - remove users from project if no future assignments.
    """
    try:
        project_name = project.get("name", "")
        project_levels = project.get("levels", [])
        stage_assignments = project.get("stage_assignments", {})
        
        if not project_name or completed_level >= len(project_levels):
            return
        
        # Get the completed stage name
        completed_stage_name = project_levels[completed_level]
        completed_assignment = stage_assignments.get(completed_stage_name, {})
        
        # Collect users who completed this stage
        completed_users = set()
        
        if isinstance(completed_assignment, dict):
            # Main stage assignee
            main_assignee = completed_assignment.get("assigned_to", "")
            if main_assignee:
                completed_users.add(main_assignee)
            
            # Substage assignees
            substages = completed_assignment.get("substages", {})
            for substage_name, substage_data in substages.items():
                if isinstance(substage_data, dict):
                    substage_assignee = substage_data.get("assigned_to", "")
                    if substage_assignee:
                        completed_users.add(substage_assignee)
        
        # Remove project from each user if they have no future assignments
        for username in completed_users:
            _remove_user_from_completed_project(
                project_name, username, completed_level, project_levels, stage_assignments
            )
            
    except Exception as e:
        st.error(f"Error in stage completion cleanup: {str(e)}")

def _handle_substage_completion_cleanup(project_name, stage_name, substage_name, assigned_username, project_levels, stage_assignments):
    """
    Handle cleanup when a substage is completed - remove user from project if no future assignments.
    Call this function when a substage is marked as complete.
    """
    try:
        if not assigned_username or not project_name:
            return
        
        # Check if user has any future assignments in this project
        user_has_future_assignments = False
        
        # Get current stage index
        current_stage_index = -1
        if stage_name in project_levels:
            current_stage_index = project_levels.index(stage_name)
        
        # Check remaining stages (current stage and future stages)
        remaining_stages = project_levels[current_stage_index:] if current_stage_index >= 0 else project_levels
        
        for remaining_stage_name in remaining_stages:
            assignment_data = stage_assignments.get(remaining_stage_name, {})
            if isinstance(assignment_data, dict):
                # Check main stage assignment
                main_assignee = assignment_data.get("assigned_to", "")
                if main_assignee == assigned_username:
                    user_has_future_assignments = True
                    break
                
                # Check substage assignments
                substages = assignment_data.get("substages", {})
                for sub_name, substage_data in substages.items():
                    if isinstance(substage_data, dict):
                        substage_assignee = substage_data.get("assigned_to", "")
                        if substage_assignee == assigned_username:
                            # If it's the same substage that was just completed, skip it
                            if remaining_stage_name == stage_name and sub_name == substage_name:
                                continue
                            user_has_future_assignments = True
                            break
                
                if user_has_future_assignments:
                    break
        
        # If user has no future assignments, remove project from their current projects
        if not user_has_future_assignments:
            from backend.users_backend import UserService, DatabaseManager
            
            db_manager = DatabaseManager()
            user_service = UserService(db_manager)
            
            user_email = _get_user_email_from_username(assigned_username)
            user_data = user_service.fetch_user_data(user_email)
            
            if user_data:
                current_projects = user_data.get("project", [])
                if project_name in current_projects:
                    current_projects.remove(project_name)
                    user_service.update_member(user_email, {"project": current_projects})
                    
    except Exception as e:
        st.error(f"Error in substage completion cleanup: {str(e)}")

# Helper function to convert username to email (adjust based on your email pattern)
def _get_user_email_from_username(username):
    """
    Convert username to email format.
    Adjust this function based on your actual email pattern.
    """
    if "@" in username:
        return username  # Already an email
    
    # Common patterns - adjust as needed
    possible_patterns = [
        f"{username}@v-shesh.com"
    ]
    
    # Try to find existing user with one of these patterns
    from backend.users_backend import UserService, DatabaseManager
    
    try:
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        for email_pattern in possible_patterns:
            user_data = user_service.fetch_user_data(email_pattern)
            if user_data:
                return email_pattern
                
        # If no pattern works, return the first one as default
        return possible_patterns[0]
        
    except Exception:
        return f"{username}@v-shesh.com"  # Default fallback
    


def _remove_user_from_completed_project(project_name, username, current_level, project_levels, stage_assignments):
    """
    Remove project from user's current projects if they're not assigned to any future stages/substages.
    Only called when a stage/substage is completed.
    """
    try:
        from backend.users_backend import UserService, DatabaseManager
        
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        # Check if user is assigned to any future stages/substages
        user_has_future_assignments = False
        
        # Get remaining stages (stages after current completed level)
        remaining_stages = project_levels[current_level + 1:] if current_level + 1 < len(project_levels) else []
        
        for stage_name in remaining_stages:
            assignment_data = stage_assignments.get(stage_name, {})
            if isinstance(assignment_data, dict):
                # Check main stage assignment
                main_assignee = assignment_data.get("assigned_to", "")
                if main_assignee == username:
                    user_has_future_assignments = True
                    break
                
                # Check substage assignments
                substages = assignment_data.get("substages", {})
                for substage_name, substage_data in substages.items():
                    if isinstance(substage_data, dict):
                        substage_assignee = substage_data.get("assigned_to", "")
                        if substage_assignee == username:
                            user_has_future_assignments = True
                            break
                
                if user_has_future_assignments:
                    break
        
        # If user has no future assignments, remove project from their current projects
        if not user_has_future_assignments:
            user_email = f"{username}@v-shesh.com"  # Adjust email pattern as needed
            user_data = user_service.fetch_user_data(user_email)
            
            if user_data:
                current_projects = user_data.get("project", [])
                if project_name in current_projects:
                    current_projects.remove(project_name)
                    user_service.update_member(user_email, {"project": current_projects})
                    
        return True
        
    except Exception as e:
        st.error(f"Error removing user from completed project: {str(e)}")
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