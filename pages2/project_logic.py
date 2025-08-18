import streamlit as st
import time

from utils.utils_project_user_sync import(
    _sync_user_projects_on_stage_change
)
from utils.utils_project_core import (
    validate_project_dates,
    get_current_timestamp,
    notify_assigned_members,
    display_success_messages,
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
    delete_project_from_db,
    remove_project_from_all_users,
)
from .project_helpers import (
    create_project_data, create_updated_project_data,
    _update_client_counts_after_edit,
    validate_users_exist,
    extract_project_users,
    sync_user_project_assignments,
    send_assignment_notifications
)

from .project_completion import(
    _are_all_substages_complete,
   _check_project_completion,
   _handle_stage_completion_cleanup
 )

from .project_date_utils import (
    validate_stage_substage_dates,
)

def _handle_create_project(name, client, description, start, due, selected_subtemplate="", co_manager=None):
    """Enhanced create project handler with subtemplate and co-manager support"""
    if not validate_project_dates(start, due):
        st.error("Cannot submit: Due date must be later than the start date.")
        return
    elif not name:
        st.error("Project name is required.")
        return
    elif st.session_state.selected_template != "Onwards" and not client:
        st.error("Client is required for non-Onwards projects.")
        return
    elif _check_project_name_exists(name):
        st.error("A project with this name already exists. Please choose a different name.")
        return
    else:
        # Validate stage and substage dates
        stage_assignments = st.session_state.get("stage_assignments", {})
        project_name = name
        date_errors = validate_stage_substage_dates(stage_assignments, due)
        
        if date_errors:
            st.error("Cannot create project due to date validation errors:")
            for error in date_errors:
                st.error(f"• {error}")
            return
        
        # Validate user assignments before creating project
        assigned_users = extract_project_users(stage_assignments)
        is_valid, invalid_users = validate_users_exist(assigned_users)
        if not is_valid:
            st.error("Cannot create project - the following users don't exist in the database:")
            for user in invalid_users:
                st.error(f"• {user}")
            return
            
        # Sync users to project
        sync_result = sync_user_project_assignments(project_name, users_to_add=assigned_users)

        new_proj = create_project_data(name, client, description, start, due)
        
        # Add subtemplate to project data if it's an Onwards project
        if st.session_state.get("selected_template") == "Onwards" and selected_subtemplate:
            new_proj["subtemplate"] = selected_subtemplate
        
        # --- NEW: Add co-manager if provided ---
        if co_manager:
            new_proj["co_manager"] = co_manager

        project_id = save_project_to_db(new_proj)
        if project_id:
            new_proj["id"] = project_id
            st.session_state.projects.append(new_proj)
            st.success("Project created and saved to database!")
            
            # Only update client project count for non-Onwards projects
            if st.session_state.selected_template != "Onwards" and client:
                update_client_project_count(client)
            
            # Add project to manager
            add_project_to_manager(st.session_state.get("username", ""), name)
            
            if sync_result["success"]:
                # Send notifications
                send_assignment_notifications(project_name, stage_assignments)
                
                if st.session_state.selected_template != "Onwards" and client:
                    update_client_project_count(client)
                
                if sync_result["added"] > 0:
                    st.success(f"✅ Project created and added to {sync_result['added']} user profiles")
            else:
                st.error("❌ Failed to sync user assignments")
                
            # Complete form state reset
            _reset_create_form_state()
            
            # Navigate back to dashboard
            st.session_state.view = "dashboard"
            st.rerun()
                                                
# UPDATED FUNCTION: Enhanced save project handler with date validation
# update logic in https://claude.ai/chat/22923190-8e0c-458d-a860-ed65ffb2a9a0
def handle_save_project(pid, project, name, client, description, start, due, original_name, stage_assignments):
    """Enhanced save project handler with comprehensive user-project sync and co-manager persistence"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
        return
    elif not name or (project.get("template") != "Onwards" and not client):
        st.error("Name and client are required.")
        return

    # Validate stage and substage dates
    date_errors = validate_stage_substage_dates(stage_assignments, due)
    if date_errors:
        st.error("Cannot save project due to date validation errors:")
        for error in date_errors:
            st.error(f"• {error}")
        return

    # Validate user assignments before saving
    assigned_users = extract_project_users(stage_assignments)
    is_valid, invalid_users = validate_users_exist(assigned_users)
    if not is_valid:
        st.error("Cannot save project - the following users don't exist in the database:")
        for user in invalid_users:
            st.error(f"• {user}")
        return

    # Get old stage assignments BEFORE update
    old_stage_assignments = project.get("stage_assignments", {})

    # Build updated project dict
    updated_project = create_updated_project_data(project, name, client, description, start, due, stage_assignments)

    # --- NEW: Include Co-Manager if set in project dict ---
    if "co_manager" in project:
        updated_project["co_manager"] = project["co_manager"]

    new_assignments = updated_project.get("stage_assignments", {})

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
            send_assignment_notifications(name, stage_assignments, old_assignments=old_stage_assignments)

            # ENHANCED: Comprehensive user-project sync
            old_users = extract_project_users(old_stage_assignments)
            new_users = extract_project_users(new_assignments)
            is_valid, invalid_users = validate_users_exist(new_users)
            if not is_valid:
                st.error(f"❌ Cannot update project: Invalid users {', '.join(invalid_users)}")
                return False

            users_to_add = new_users - old_users
            users_to_remove = old_users - new_users
            sync_result = sync_user_project_assignments(
                name,
                users_to_add=users_to_add,
                users_to_remove=users_to_remove
            )
            if sync_result["success"]:
                send_assignment_notifications(
                    name,
                    new_assignments,
                    changed_assignments_only=True,
                    old_assignments=old_stage_assignments
                )
                _update_client_counts_after_edit(project, updated_project.get("client", ""))

                if sync_result["added"] > 0:
                    st.success(f"✅ Project added to {sync_result['added']} new users")
                if sync_result["removed"] > 0:
                    st.info(f"ℹ️ Project removed from {sync_result['removed']} users")
            else:
                st.error("❌ Failed to sync user assignment changes")

        project.update(updated_project)

        # --- NEW: Confirm co-manager saved ---
        if "co_manager" in updated_project:
            cm = updated_project["co_manager"]
            cm_info = f"{cm['user']} ({cm['access']})"
            success_messages.append(f"Co-Manager saved: {cm_info}")

        # Display success messages
        display_success_messages(success_messages)

        from backend.log_backend import ProjectLogManager
        log_manager = ProjectLogManager()
        log_manager.extract_and_create_logs()

        st.session_state.view = "dashboard"
        st.rerun()


def _handle_project_deletion(pid, project):
    """Delete a project with permission checks, cleanup, and deletion logging"""
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")

    # --- Permission check ---
    if role == "user":
        created_by = project.get("created_by", "")
        co_managers = project.get("co_managers", [])
        is_creator = (created_by == username)
        is_co_manager = any(cm.get("user") == username for cm in co_managers)

        if not (is_creator or is_co_manager):
            st.error("🚫 You do not have permission to delete this project.")
            return
    # --- End permission check ---

    try:
        if delete_project_from_db(pid):
            # Remove from session state
            st.session_state.projects = [p for p in st.session_state.projects if p["id"] != pid]
            st.success("🗑 Project deleted successfully")

            # --- NEW: Log deletion event ---
            from backend.log_backend import ProjectLogManager
            log_manager = ProjectLogManager()
            log_manager.create_log_entry({
                "project": project.get("name", f"pid:{pid}"),
                "action": "delete",
                "performed_by": username,
                "role": role,
                "details": f"Project deleted by {username} (role: {role})"
            })
            # Refresh other logs if needed
            log_manager.extract_and_create_logs()
            # --- End new logging ---

            st.session_state.view = "dashboard"
            st.rerun()
        else:
            st.error("❌ Failed to delete project from database")
    except Exception as e:
        st.error(f"❌ Error while deleting project: {str(e)}")


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
    return False
