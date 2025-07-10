import streamlit as st
from datetime import datetime, timedelta
from utils.utils_project_core import send_stage_assignment_email
from backend.projects_backend import update_client_project_count
from backend.users_backend import DatabaseManager, UserService

def create_project_data(name, client, description, start, due):
    """Create project data dictionary"""
    return {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "template": st.session_state.selected_template or "Custom",
        "levels": st.session_state.custom_levels.copy(),
        "level": st.session_state.level_index,
        "timestamps": st.session_state.level_timestamps.copy(),
        "stage_assignments": st.session_state.stage_assignments.copy(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "created_by": st.session_state.get("username", "unknown"),
    }

def create_updated_project_data(project, name, client, description, start, due, stage_assignments):
    """Create updated project data dictionary including substage data"""
    updated_data = {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "stage_assignments": stage_assignments,
        "updated_at": datetime.now().isoformat(),
        "created_at": project.get("created_at", datetime.now().isoformat()),
        "levels": project.get("levels", ["Initial", "Invoice", "Payment"]),
        "level": project.get("level", -1),
        "timestamps": project.get("timestamps", {})
    }
    
    # Include substage completion data if it exists
    if "substage_completion" in project:
        updated_data["substage_completion"] = project["substage_completion"]
    if "substage_timestamps" in project:
        updated_data["substage_timestamps"] = project["substage_timestamps"]
    
    return updated_data

def _update_client_counts_after_edit(project, new_client):
    """Update client project counts after editing"""
    # Update new client count
    update_client_project_count(new_client)
    
    # Update old client count if client was changed
    old_client = project.get("client", "")
    if new_client != old_client:
        update_client_project_count(old_client)

def _check_success_messages(pid, context="dashboard"):
    """Check and display success messages for dashboard or edit context"""
    key_prefix = "edit_" if context == "edit" else ""
    
    if st.session_state.get(f"{key_prefix}level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"{key_prefix}level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

# Helper function to convert username to email (adjust based on your email pattern)
def _get_user_email_from_username(username):
    """
    Convert username to email format.
    Adjust this function based on your actual email pattern.
    """
    if "@" in username:
        return username  # Already an email
    return f"{username}@v-shesh.com"  # Default fallback    

# ==============================================================================
# USER SYNCHRONIZATION FUNCTIONS
# ==============================================================================

def sync_user_project_assignments(project_name, users_to_add=None, users_to_remove=None):
    """
    Core function to sync user-project assignments
    
    Args:
        project_name: Name of the project
        users_to_add: Set/list of users to add project to
        users_to_remove: Set/list of users to remove project from
    
    Returns:
        dict: {"added": count, "removed": count, "success": bool}
    """
    try:
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        added_count = 0
        removed_count = 0
        
        # Add project to users
        if users_to_add:
            for username in users_to_add:
                user_email = _get_user_email_from_username(username)
                user_data = user_service.fetch_user_data(user_email)
                
                if user_data:
                    current_projects = user_data.get("project", [])
                    if not isinstance(current_projects, list):
                        current_projects = []
                    
                    if project_name not in current_projects:
                        current_projects.append(project_name)
                        user_service.update_member(user_email, {"project": current_projects})
                        added_count += 1
                else:
                    st.warning(f"⚠️ User {username} not found in database")
        
        # Remove project from users
        if users_to_remove:
            for username in users_to_remove:
                user_email = _get_user_email_from_username(username)
                user_data = user_service.fetch_user_data(user_email)
                
                if user_data:
                    current_projects = user_data.get("project", [])
                    if isinstance(current_projects, list) and project_name in current_projects:
                        current_projects.remove(project_name)
                        user_service.update_member(user_email, {"project": current_projects})
                        removed_count += 1
        
        return {
            "added": added_count,
            "removed": removed_count,
            "success": True
        }
        
    except Exception as e:
        st.error(f"❌ Error syncing user assignments: {str(e)}")
        return {"added": 0, "removed": 0, "success": False}
    
def extract_project_users(stage_assignments):
    """
    Extract all users assigned to any stage or substage in a project
    
    Args:
        stage_assignments: Dictionary of stage assignments
    
    Returns:
        set: Set of all assigned usernames
    """
    all_users = set()
    
    if not isinstance(stage_assignments, dict):
        return all_users
    
    for stage_data in stage_assignments.values():
        if isinstance(stage_data, dict):
            # Stage members
            members = stage_data.get("members", [])
            if isinstance(members, list):
                all_users.update(members)
            
            # Substage assignees
            substages = stage_data.get("substages", {})
            for substage_data in substages.values():
                if isinstance(substage_data, dict):
                    assignees = substage_data.get("assignees", [])
                    if isinstance(assignees, list):
                        all_users.update(assignees)
                    elif isinstance(assignees, str) and assignees.strip():
                        all_users.add(assignees.strip())
    
    return all_users

def validate_users_exist(usernames):
    """
    Validate that all users exist in the database
    
    Args:
        usernames: Set/list of usernames to validate
    
    Returns:
        tuple: (is_valid, list_of_invalid_users)
    """
    try:
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        invalid_users = []
        for username in usernames:
            user_email = _get_user_email_from_username(username)
            user_data = user_service.fetch_user_data(user_email)
            if not user_data:
                invalid_users.append(username)
        
        return len(invalid_users) == 0, invalid_users
        
    except Exception as e:
        st.error(f"Error validating users: {str(e)}")
        return False, []
    

def send_assignment_notifications(project_name, stage_assignments, changed_assignments_only=False, old_assignments=None):
    """
    Send email notifications for stage assignments
    
    Args:
        project_name: Name of the project
        stage_assignments: Current stage assignments
        changed_assignments_only: If True, only send for changed assignments
        old_assignments: Previous assignments (needed if changed_assignments_only=True)
    """
    try:
        assignments_to_notify = {}
        
        if changed_assignments_only and old_assignments:
            # Find only changed assignments
            for stage_index, assignment in stage_assignments.items():
                old_assignment = old_assignments.get(stage_index, {})
                new_members = set(assignment.get("members", []))
                old_members = set(old_assignment.get("members", []))
                
                newly_assigned = new_members - old_members
                if newly_assigned:
                    assignments_to_notify[stage_index] = {
                        "members": list(newly_assigned),
                        "deadline": assignment.get("deadline", ""),
                        "stage_name": assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
                    }
        else:
            # Send for all assignments
            assignments_to_notify = stage_assignments
        
        # Send emails
        for stage_index, assignment in assignments_to_notify.items():
            members = assignment.get("members", [])
            if members:
                deadline = assignment.get("deadline", "")
                stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
                member_emails = [f"{member}@v-shesh.com" for member in members]
                send_stage_assignment_email(member_emails, project_name, stage_name, deadline)
        
    except Exception as e:
        st.error(f"Error sending assignment notifications: {str(e)}")

# ==============================================================================
# HIGH-LEVEL PROJECT MANAGEMENT FUNCTIONS
# ==============================================================================

def handle_project_creation(project_data):
    """
    Complete project creation handler with validation and sync
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        bool: True if creation was successful
    """
    try:
        project_name = project_data.get("name", "")
        stage_assignments = project_data.get("stage_assignments", {})
        
        # Extract and validate users
        assigned_users = extract_project_users(stage_assignments)
        is_valid, invalid_users = validate_users_exist(assigned_users)
        
        if not is_valid:
            st.error(f"❌ Cannot create project: Invalid users {', '.join(invalid_users)}")
            return False
        
        # Sync users to project
        sync_result = sync_user_project_assignments(project_name, users_to_add=assigned_users)
        
        if sync_result["success"]:
            # Send notifications
            send_assignment_notifications(project_name, stage_assignments)
            
            # Update client count
            update_client_project_count(project_data.get("client", ""))
            
            if sync_result["added"] > 0:
                st.success(f"✅ Project created and added to {sync_result['added']} user profiles")
            
            return True
        else:
            st.error("❌ Failed to sync user assignments")
            return False
            
    except Exception as e:
        st.error(f"❌ Error creating project: {str(e)}")
        return False

def handle_project_update(project_name, old_project_data, new_project_data):
    """
    Complete project update handler with validation and sync
    
    Args:
        project_name: Name of the project
        old_project_data: Previous project data
        new_project_data: Updated project data
    
    Returns:
        bool: True if update was successful
    """
    try:
        old_assignments = old_project_data.get("stage_assignments", {})
        new_assignments = new_project_data.get("stage_assignments", {})
        
        # Extract users
        old_users = extract_project_users(old_assignments)
        new_users = extract_project_users(new_assignments)
        
        # Validate new users
        is_valid, invalid_users = validate_users_exist(new_users)
        if not is_valid:
            st.error(f"❌ Cannot update project: Invalid users {', '.join(invalid_users)}")
            return False
        
        # Calculate changes
        users_to_add = new_users - old_users
        users_to_remove = old_users - new_users
        
        # Sync changes
        sync_result = sync_user_project_assignments(
            project_name, 
            users_to_add=users_to_add, 
            users_to_remove=users_to_remove
        )
        
        if sync_result["success"]:
            # Send notifications for changes
            send_assignment_notifications(
                project_name, 
                new_assignments, 
                changed_assignments_only=True, 
                old_assignments=old_assignments
            )
            
            # Update client counts
            _update_client_counts_after_edit(old_project_data, new_project_data.get("client", ""))
            
            # Display results
            if sync_result["added"] > 0:
                st.success(f"✅ Project added to {sync_result['added']} new users")
            if sync_result["removed"] > 0:
                st.info(f"ℹ️ Project removed from {sync_result['removed']} users")
            
            return True
        else:
            st.error("❌ Failed to sync user assignment changes")
            return False
            
    except Exception as e:
        st.error(f"❌ Error updating project: {str(e)}")
        return False

def handle_realtime_assignment_change(project_name, stage_name, new_assignment_data):
    """
    Handle real-time assignment changes (for UI updates)
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        new_assignment_data: New assignment data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Extract users from new assignment
        assigned_users = set()
        
        if isinstance(new_assignment_data, dict):
            # Stage members
            members = new_assignment_data.get("members", [])
            if isinstance(members, list):
                assigned_users.update(members)
            
            # Substage assignees
            substages = new_assignment_data.get("substages", {})
            for substage_data in substages.values():
                if isinstance(substage_data, dict):
                    assignees = substage_data.get("assignees", [])
                    if isinstance(assignees, list):
                        assigned_users.update(assignees)
                    elif isinstance(assignees, str) and assignees.strip():
                        assigned_users.add(assignees.strip())
        
        # Sync users (add only - removal handled by full project updates)
        sync_result = sync_user_project_assignments(project_name, users_to_add=assigned_users)
        
        return sync_result["success"]
        
    except Exception as e:
        st.error(f"❌ Error handling real-time assignment change: {str(e)}")
        return False
