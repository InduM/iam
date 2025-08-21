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
    insert_project_to_db
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

def _handle_create_project(
    name, client, description, start, due,
    template, subtemplate, stage_assignments,
    created_by, co_managers=None
):
    """Handles new project creation, with optional co-manager logging"""

    # --- Validation ---
    if not validate_project_dates(start, due):
        st.error("Cannot create project: Due date must be later than the start date.")
        return None
    elif not name or (template != "Onwards" and not client):
        st.error("Name and client are required.")
        return None

    date_errors = validate_stage_substage_dates(stage_assignments, due)
    if date_errors:
        st.error("Cannot create project due to date validation errors:")
        for error in date_errors:
            st.error(f"• {error}")
        return None

    assigned_users = extract_project_users(stage_assignments)
    is_valid, invalid_users = validate_users_exist(assigned_users)
    if not is_valid:
        st.error("Cannot create project - the following users don't exist in the database:")
        for user in invalid_users:
            st.error(f"• {user}")
        return None

    # --- Construct project document ---
    from datetime import datetime
    now = datetime.now()
    levels  = [s.get("stage_name", f"Stage {i+1}") for i, s in enumerate(stage_assignments.values())] \
         if isinstance(stage_assignments, dict) else []


    project_data = {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "template": template,
        "subtemplate": subtemplate,
        "levels": levels,
        "level": 0,
        "timestamps": {"0": now.strftime("%Y-%m-%d %H:%M:%S")},
        "stage_assignments": stage_assignments,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": created_by,
        "co_managers": co_managers or []
    }

    pid = insert_project_to_db(project_data)

    if pid:
        st.success("✅ Project created successfully")

        # --- Co-Manager logging ---
        if co_managers:
            from backend.log_backend import ProjectLogManager
            from bson import ObjectId
            log_manager = ProjectLogManager()
            username = st.session_state.get("username", "?")

            for cm in co_managers:
                log_manager.create_log_entry({
                    "project_id": ObjectId(pid),
                    "project": name,
                    "event": "co_manager_added",
                    "message": f"Initial Co-Manager {cm['user']} ({cm.get('access','full')})",
                    "performed_by": username,
                    "created_at": now,
                    "updated_at": now
                })
        # --- End logging ---

        return pid
    else:
        st.error("❌ Failed to create project")
        return None
                                                
# UPDATED FUNCTION: Enhanced save project handler with date validation
# update logic in https://claude.ai/chat/22923190-8e0c-458d-a860-ed65ffb2a9a0
def handle_save_project(pid, project, name, client, description, start, due, original_name, stage_assignments):
    """Enhanced save project handler with co-manager logging"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
        return
    elif not name or (project.get("template") != "Onwards" and not client):
        st.error("Name and client are required.")
        return

    # Validate stage/substage dates
    date_errors = validate_stage_substage_dates(stage_assignments, due)
    if date_errors:
        st.error("Cannot save project due to date validation errors:")
        for error in date_errors:
            st.error(f"• {error}")
        return

    # Validate user assignments
    assigned_users = extract_project_users(stage_assignments)
    is_valid, invalid_users = validate_users_exist(assigned_users)
    if not is_valid:
        st.error("Cannot save project - the following users don't exist in the database:")
        for user in invalid_users:
            st.error(f"• {user}")
        return

    old_stage_assignments = project.get("stage_assignments", {})
    old_co_managers = project.get("co_managers", [])

    # Build updated project dict
    updated_project = create_updated_project_data(project, name, client, description, start, due, stage_assignments)

    # Preserve co-managers if present
    if "co_managers" in project:
        updated_project["co_managers"] = project["co_managers"]

    new_assignments = updated_project.get("stage_assignments", {})

    if update_project_in_db(pid, updated_project):
        success_messages = []

        _update_client_counts_after_edit(project, client)

        # Name changes
        if original_name != name:
            updated_count = update_project_name_in_user_profiles(original_name, name)
            if updated_count > 0:
                success_messages.append(f"Project name updated in {updated_count} user profiles!")

        # Stage assignment changes
        if stage_assignments != old_stage_assignments:
            success_messages.append("Stage assignments updated!")
            send_assignment_notifications(name, stage_assignments, old_assignments=old_stage_assignments)

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

        # --- NEW: Co-Manager change logging ---
        new_co_managers = updated_project.get("co_managers", [])
        if new_co_managers != old_co_managers:
            from backend.log_backend import ProjectLogManager
            log_manager = ProjectLogManager()
            username = st.session_state.get("username", "")
            role = st.session_state.get("role", "")

            old_users = {cm["user"]: cm for cm in old_co_managers}
            new_users = {cm["user"]: cm for cm in new_co_managers}

            # Added
            for user, cm in new_users.items():
                if user not in old_users:
                    log_manager.create_log_entry({
                        "project": name,
                        "action": "co_manager_added",
                        "performed_by": username,
                        "role": role,
                        "details": f"Co-Manager {user} added ({cm.get('access','full')})"
                    })

            # Removed
            for user in old_users:
                if user not in new_users:
                    log_manager.create_log_entry({
                        "project": name,
                        "action": "co_manager_removed",
                        "performed_by": username,
                        "role": role,
                        "details": f"Co-Manager {user} removed"
                    })

            # Updated
            for user, cm in new_users.items():
                if user in old_users and cm != old_users[user]:
                    log_manager.create_log_entry({
                        "project": name,
                        "action": "co_manager_updated",
                        "performed_by": username,
                        "role": role,
                        "details": f"Co-Manager {user} updated from {old_users[user]} to {cm}"
                    })
        # --- End new logging ---

        # Success messages
        if new_co_managers:
            cm_info = ", ".join([f"{cm['user']} ({cm['access']})" for cm in new_co_managers])
            success_messages.append(f"Co-Managers saved: {cm_info}")

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
