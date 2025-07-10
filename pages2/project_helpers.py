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


def _get_member_emails(members):
    """Helper function to construct member email addresses"""
    return [f"{member}@v-shesh.com" for member in members]

def _send_stage_assignment_emails(assignments, project_name):
    """Helper function to send stage assignment emails"""
    for stage_index, assignment in assignments.items():
        members = assignment.get("members", [])
        if members:
            deadline = assignment.get("deadline", "")
            stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
            member_emails = _get_member_emails(members)
            send_stage_assignment_email(member_emails, project_name, stage_name, deadline)

def send_stage_assignment_notifications(project):
    """Send notifications for stage assignments in new project"""
    stage_assignments = project.get("stage_assignments", {})
    project_name = project.get("name", "Unnamed")
    
    if stage_assignments:
        _send_stage_assignment_emails(stage_assignments, project_name)

def _send_stage_assignment_change_notifications(new_assignments, old_assignments, project_name):
    """Send notifications when stage assignments change"""
    # Compare old and new assignments to find changes
    changed_assignments = {}
    
    for stage_index, assignment in new_assignments.items():
        old_assignment = old_assignments.get(stage_index, {})
        new_members = set(assignment.get("members", []))
        old_members = set(old_assignment.get("members", []))
        
        # Find newly assigned members
        newly_assigned = new_members - old_members
        if newly_assigned:
            # Create assignment dict for newly assigned members only
            changed_assignments[stage_index] = {
                "members": list(newly_assigned),
                "deadline": assignment.get("deadline", ""),
                "stage_name": assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
            }
    
    if changed_assignments:
        _send_stage_assignment_emails(changed_assignments, project_name)

def _handle_email_reminders(project, pid, levels, current_level):
    """Handle email reminder logic"""
    project_name = project.get("name", "Unnamed")
    lead_email = st.secrets.get("project_leads", {}).get("Project Alpha")
    
    # Safe check for Invoice and Payment levels
    try:
        invoice_index = levels.index("Invoice") if "Invoice" in levels else -1
        payment_index = levels.index("Payment") if "Payment" in levels else -1
    except (ValueError, AttributeError):
        invoice_index = -1
        payment_index = -1
    
    email_key = f"last_email_sent_{pid}"
    if email_key not in st.session_state:
        st.session_state[email_key] = None
    
    if (0 <= invoice_index <= current_level) and (payment_index > current_level) and lead_email:
        now = datetime.now()
        last_sent = st.session_state[email_key]
        if not last_sent or now - last_sent >= timedelta(minutes=1):
            if send_invoice_email(lead_email, project_name):
                st.session_state[email_key] = now

def _check_success_messages(pid, context="dashboard"):
    """Check and display success messages for dashboard or edit context"""
    key_prefix = "edit_" if context == "edit" else ""
    
    if st.session_state.get(f"{key_prefix}level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"{key_prefix}level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

# Legacy function names for backward compatibility
def _check_dashboard_success_messages(pid):
    """Check and display dashboard success messages - Legacy wrapper"""
    _check_success_messages(pid, "dashboard")

def _check_edit_success_messages(pid):
    """Check and display edit form success messages - Legacy wrapper"""
    _check_success_messages(pid, "edit")

# Enhanced version of existing function with better error handling
def sync_user_project_assignment(username, project_name, action="add"):
    """
    Enhanced sync user project assignment with better error handling
    
    Args:
        username: Username to sync
        project_name: Project name to add/remove
        action: "add" or "remove"
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        
        if not username or not project_name:
            return False
        
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        # Convert username to email format
        user_email = _get_user_email_from_username(username)
        
        # Fetch user data
        user_data = user_service.fetch_user_data(user_email)
        if not user_data:
            # Create a warning but don't fail completely
            st.warning(f"⚠️ User {username} not found in database")
            return False
        
        # Get current projects
        current_projects = user_data.get("project", [])
        if not isinstance(current_projects, list):
            current_projects = []
        
        # Handle add action
        if action == "add":
            if project_name not in current_projects:
                current_projects.append(project_name)
                user_service.update_member(user_email, {"project": current_projects})
                return True
            return True  # Already exists, consider it success
        
        # Handle remove action
        elif action == "remove":
            if project_name in current_projects:
                current_projects.remove(project_name)
                user_service.update_member(user_email, {"project": current_projects})
                return True
            return True  # Already doesn't exist, consider it success
        return False
        
    except Exception as e:
        st.error(f"❌ Error syncing user project assignment for {username}: {str(e)}")
        print(f"❌ Error syncing user project assignment for {username}: {str(e)}")
        return False
    
def sync_stage_assignment_to_user_profiles(project_name, stage_name, assignment_data):
    """
    Sync a single stage assignment to user profiles
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        assignment_data: Stage assignment data dictionary
    
    Returns:
        int: Number of users successfully updated
    """
    if not isinstance(assignment_data, dict):
        return 0
    
    success_count = 0
    users_to_sync = set()
    

    # Get substage assignees
    substages = assignment_data.get("substages", {})
    for substage_name, substage_data in substages:
        if isinstance(substage_data, dict):
            substage_assignee = substage_data.get("assignees", [])
            users_to_sync.add(substage_assignee)
    
    # Sync each user
    for username in users_to_sync:
        if sync_user_project_assignment(username, project_name, "add"):
            success_count += 1
    
    return success_count

def sync_all_stage_assignments_to_user_profiles(project_name, stage_assignments):
    """
    Sync all stage assignments to user profiles
    
    Args:
        project_name: Name of the project
        stage_assignments: Dictionary of all stage assignments
    
    Returns:
        int: Total number of users successfully updated
    """
    if not isinstance(stage_assignments, dict):
        return 0
    
    total_success = 0
    
    for stage_name, assignment_data in stage_assignments.items():
        success_count = sync_stage_assignment_to_user_profiles(
            project_name, stage_name, assignment_data
        )
        total_success += success_count
    
    return total_success

def handle_stage_assignment_change(project_name, stage_name, old_assignment, new_assignment):
    """
    Handle user-project sync when a single stage assignment changes in real-time
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage being changed
        old_assignment: Previous assignment data
        new_assignment: New assignment data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Extract users from old assignment
        old_users = set()
        if isinstance(old_assignment, dict):
            substages = old_assignment.get("substages", {})
            for substage_data in substages:
                if isinstance(substage_data, dict):
                    substage_assignee = substage_data.get("assignees", [])
                    old_users.updaet(substage_assignee)
        
        # Extract users from new assignment
        new_users = set()
        if isinstance(new_assignment, dict):
            substages = new_assignment.get("substages", {})
            for substage_data in substages:
                if isinstance(substage_data, dict):
                    substage_assignee = substage_data.get("assignees", [])
                    new_users.update(substage_assignee)
        
        # Add project to newly assigned users
        users_to_add = new_users - old_users
        for username in users_to_add:
            sync_user_project_assignment(username, project_name, "add")
        
        # Note: We don't remove users here because they might have assignments 
        # in other stages. Removal should be handled by the comprehensive sync
        # functions when the entire project is saved.
        
        return True
        
    except Exception as e:
        st.error(f"Error handling stage assignment change: {str(e)}")
        return False
    

# Helper function to convert username to email (adjust based on your email pattern)
def _get_user_email_from_username(username):
    """
    Convert username to email format.
    Adjust this function based on your actual email pattern.
    """
    if "@" in username:
        return username  # Already an email
    return f"{username}@v-shesh.com"  # Default fallback

def sync_user_assignment_changes(project_name, old_stage_assignments, new_stage_assignments):
    """
    Comprehensive sync when stage assignments change - handles both additions and removals
    Returns:
        bool: True if sync was successful
    """
    try:
        # Extract all users from old assignments
        old_users = set()
        if isinstance(old_stage_assignments, dict):
            for stage_data in old_stage_assignments.values():
                if isinstance(stage_data, dict):
                    members = stage_data.get("members", [])
                    old_users.update(members)
                    
        # Extract all users from new assignments
        new_users = set()
        if isinstance(new_stage_assignments, dict):
            for stage_data in new_stage_assignments.values():
                if isinstance(stage_data, dict):
                    members = stage_data.get("members", [])
                    if isinstance(members, list):
                        new_users.update(members)
            
        # Add project to newly assigned users
        users_to_add = new_users - old_users
        for username in users_to_add:
            sync_user_project_assignment(username, project_name, "add")
        
        # Remove project from users no longer assigned
        users_to_remove = old_users - new_users
        for username in users_to_remove:
            sync_user_project_assignment(username, project_name, "remove")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing user assignment changes: {str(e)}")
        print(f"Error syncing user assignment changes: {str(e)}")
        return False
    
def sync_single_user_assignment(username, project_name, action="add"):
    """
    Real-time sync for individual user assignment changes
    
    Args:
        username: Username to sync
        project_name: Project name
        action: "add" or "remove"
    
    Returns:
        bool: True if successful
    """
    try:
        return sync_user_project_assignment(username, project_name, action)
    except Exception as e:
        st.error(f"Error syncing single user assignment: {str(e)}")
        print(f"Error syncing single user assignment: {str(e)}")
        return False

def sync_substage_assignment(project_name, stage_name, substage_name, assignee_data):
    """
    Sync users when a substage assignment is updated
    Returns:
        bool: True if sync was successful
    """
    try:
        users_to_sync = set()
        
        # Handle different assignee data formats
        if isinstance(assignee_data, str) and assignee_data.strip():
            users_to_sync.add(assignee_data.strip())
        elif isinstance(assignee_data, list):
            users_to_sync.update(assignee_data)
        elif isinstance(assignee_data, dict):
            # Handle dictionary format
            assigned_to = assignee_data.get("assignees", [])
            users_to_sync.update(assigned_to)
        
        # Sync each user
        for username in users_to_sync:
            sync_user_project_assignment(username, project_name, "add")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing substage assignment: {str(e)}")
        print(f"Error syncing substage assignment: {str(e)}")

        return False
    
def validate_and_sync_project_assignments(project_data):
    """
    Validate all user assignments exist and sync them to the project
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        tuple: (is_valid, list_of_invalid_users, sync_successful)
    """
    try:
        project_name = project_data.get("name", "")
        stage_assignments = project_data.get("stage_assignments", {})
        
        # First validate all users exist
        is_valid, invalid_users = validate_user_assignments(stage_assignments)
        
        if not is_valid:
            st.error(f"❌ Invalid users found: {', '.join(invalid_users)}")
            print(f"❌ Invalid users found: {', '.join(invalid_users)}")
            return False, invalid_users, False
        
        # If validation passes, sync the assignments
        sync_successful = sync_project_users_on_creation(project_data)
        
        return True, [], sync_successful
        
    except Exception as e:
        st.error(f"Error validating and syncing project assignments: {str(e)}")
        return False, [], False


def sync_substage_assignment_change(project_name, stage_name, substage_name, old_assignee, new_assignee):
    """
    Handle user-project sync when a substage assignment changes
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Remove project from old assignee if they exist
        if old_assignee and old_assignee.strip():
            # Note: We don't remove here because they might have other assignments
            # Removal should be handled by comprehensive sync functions
            pass
        
        # Add project to new assignee
        if new_assignee and new_assignee.strip():
            return sync_user_project_assignment(new_assignee.strip(), project_name, "add")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing substage assignment change: {str(e)}")
        print(f"Error syncing substage assignment change: {str(e)}")

        return False

def get_all_project_users(stage_assignments):
    """
    Get all users assigned to any stage or substage in a project
    
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
            # Members list (if exists)
            members = stage_data.get("members", [])
            if isinstance(members, list):
                for member in members:
                        all_users.update(members)      
            # Substage assignees
            substages = stage_data.get("substages", {})
            for substage_data in substages:
                if isinstance(substage_data, dict):
                    assignees = substage_data.get("assignees", [])
                    if isinstance(assignees, list):
                        all_users.update(assignees)
    
    return all_users

def sync_project_users_on_creation(project_data):
    """
    Sync all users to project when a new project is created
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        bool: True if sync was successful
    """
    try:
        project_name = project_data.get("name", "")
        stage_assignments = project_data.get("stage_assignments", {})
        
        if not project_name:
            return False
        
        # Get all users assigned to this project
        all_users = get_all_project_users(stage_assignments)
        
        # Add project to each user's profile
        success_count = 0
        for username in all_users:
            if sync_user_project_assignment(username, project_name, "add"):
                success_count += 1
        
        # Log success
        if success_count > 0:
            st.success(f"✅ Project added to {success_count} user profiles")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing project users on creation: {str(e)}")
        return False
    
def sync_project_users_on_update(project_name, old_stage_assignments, new_stage_assignments):
    """
    Comprehensive sync when project is updated - handles both additions and removals
    
    Args:
        project_name: Name of the project
        old_stage_assignments: Previous stage assignments
        new_stage_assignments: New stage assignments
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Get users from old and new assignments
        old_users = get_all_project_users(old_stage_assignments or {})
        new_users = get_all_project_users(new_stage_assignments or {})
        
        # Users to add (newly assigned)
        users_to_add = new_users - old_users
        # Users to remove (no longer assigned)
        users_to_remove = old_users - new_users
        
        success_count = 0
        
        # Add project to newly assigned users
        for username in users_to_add:
            if sync_user_project_assignment(username, project_name, "add"):
                success_count += 1
        
        # Remove project from users no longer assigned
        for username in users_to_remove:
            if sync_user_project_assignment(username, project_name, "remove"):
                success_count += 1
        
        # Log changes
        if users_to_add:
            st.success(f"✅ Project added to {len(users_to_add)} new users")
        if users_to_remove:
            st.info(f"ℹ️ Project removed from {len(users_to_remove)} users")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing project users on update: {str(e)}")
        print(f"Error syncing project users on update: {str(e)}")
        return False

def sync_single_stage_assignment(project_name, stage_name, assignment_data):
    """
    Sync users when a single stage assignment is updated in real-time
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        assignment_data: Stage assignment data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        if not isinstance(assignment_data, dict):
            return False
        
        users_to_sync = set()
        
        # Get members
        members = assignment_data.get("members", [])
        if isinstance(members, list):
            users_to_sync.update(members)
        
        # Get substage assignees
        substages = assignment_data.get("substages", {})
        for substage_data in substages:
            if isinstance(substage_data, dict):
                # Handle multiple assignees
                assignees = substage_data.get("assignees", [])
                if isinstance(assignees, list):
                    users_to_sync.update(assignees)
        
        # Sync each user
        for username in users_to_sync:
            sync_user_project_assignment(username, project_name, "add")
        
        return True
        
    except Exception as e:
        st.error(f"Error syncing single stage assignment: {str(e)}")
        print(f"Error syncing single stage assignment: {str(e)}")
        return False


def remove_project_from_unassigned_users(project_name, stage_assignments):
    """
    Remove project from users who are no longer assigned to any stage/substage
    
    Args:
        project_name: Name of the project
        stage_assignments: Current stage assignments
    
    Returns:
        int: Number of users updated
    """
    try:
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        # Get all currently assigned users
        current_users = get_all_project_users(stage_assignments)
        
        # Get all users who have this project in their profile
        all_users = user_service.get_all_users() 
        users_with_project = []
        
        for user in all_users:
            user_projects = user.get("project", [])
            if project_name in user_projects:
                username = user.get("username", "")
                if username:
                    users_with_project.append(username)
        
        # Remove project from users who no longer have assignments
        removed_count = 0
        for username in users_with_project:
            if username not in current_users:
                if sync_user_project_assignment(username, project_name, "remove"):
                    removed_count += 1
        
        return removed_count
        
    except Exception as e:
        st.error(f"Error removing project from unassigned users: {str(e)}")
        print(f"Error removing project from unassigned users: {str(e)}")

        return 0

def validate_user_assignments(stage_assignments):
    """
    Validate that all assigned users exist in the database
    
    Args:
        stage_assignments: Dictionary of stage assignments
    
    Returns:
        tuple: (is_valid, list_of_invalid_users)
    """
    try:
        if not isinstance(stage_assignments, dict):
            st.error("Stage assignments must be a dictionary.")
            return False, []
        
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        all_users = get_all_project_users(stage_assignments)
        invalid_users = []
        for username in all_users:
            user_email = _get_user_email_from_username(username)
            user_data = user_service.fetch_user_data(user_email)
            if not user_data:
                invalid_users.append(username)
        return len(invalid_users) == 0, invalid_users
        
    except Exception as e:
        st.error(f"Error validating user assignments: {str(e)}")
        return False, []
    

# Integration functions to call from your main project creation/update code

def handle_project_creation_with_sync(project_data):
    """
    Handle project creation with automatic user synchronization
    Call this when creating a new project
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        bool: True if creation and sync were successful
    """
    try:
        # Validate and sync users
        is_valid, invalid_users, sync_successful = validate_and_sync_project_assignments(project_data)
        
        if not is_valid:
            st.error(f"Cannot create project: Invalid users {', '.join(invalid_users)}")
            return False
        
        # Send stage assignment notifications
        send_stage_assignment_notifications(project_data)
        
        return sync_successful
        
    except Exception as e:
        st.error(f"Error handling project creation: {str(e)}")
        return False

def handle_project_update_with_sync(project_name, old_project_data, new_project_data):
    """
    Handle project update with automatic user synchronization
    Call this when updating an existing project
    
    Args:
        project_name: Name of the project
        old_project_data: Previous project data
        new_project_data: Updated project data
    
    Returns:
        bool: True if update and sync were successful
    """
    try:
        old_stage_assignments = old_project_data.get("stage_assignments", {})
        new_stage_assignments = new_project_data.get("stage_assignments", {})
        
        # Validate new assignments
        is_valid, invalid_users = validate_user_assignments(new_stage_assignments)
        
        if not is_valid:
            st.error(f"Cannot update project: Invalid users {', '.join(invalid_users)}")
            return False
        
        # Sync user assignments
        sync_successful = sync_project_users_on_update(
            project_name, old_stage_assignments, new_stage_assignments
        )
        
        # Send notifications for changed assignments
        _send_stage_assignment_change_notifications(
            new_stage_assignments, old_stage_assignments, project_name
        )
        
        return sync_successful
        
    except Exception as e:
        st.error(f"Error handling project update: {str(e)}")
        print(f"Error handling project update: {str(e)}")

        return False

def handle_stage_assignment_change_with_sync(project_name, stage_name, old_assignment, new_assignment):
    """
    Handle real-time stage assignment changes with user synchronization
    Call this when a stage assignment is modified in the UI
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        old_assignment: Previous assignment data
        new_assignment: New assignment data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Sync the new assignment
        sync_successful = sync_single_stage_assignment(project_name, stage_name, new_assignment)
        
        # Handle the change notification
        handle_stage_assignment_change(project_name, stage_name, old_assignment, new_assignment)
        
        return sync_successful
        
    except Exception as e:
        st.error(f"Error handling stage assignment change: {str(e)}")
        print(f"Error handling stage assignment change: {str(e)}")

        return False

def handle_substage_assignment_change_with_sync(project_name, stage_name, substage_name, old_assignee, new_assignee):
    """
    Handle real-time substage assignment changes with user synchronization
    Call this when a substage assignment is modified in the UI
    
    Args:
        project_name: Name of the project
        stage_name: Name of the stage
        substage_name: Name of the substage
        old_assignee: Previous assignee data
        new_assignee: New assignee data
    
    Returns:
        bool: True if sync was successful
    """
    try:
        # Sync the new substage assignment
        sync_successful = sync_substage_assignment(project_name, stage_name, substage_name, new_assignee)
        
        # Handle the change (this already exists in your code)
        sync_substage_assignment_change(project_name, stage_name, substage_name, old_assignee, new_assignee)
        
        return sync_successful
        
    except Exception as e:
        st.error(f"Error handling substage assignment change: {str(e)}")
        print(f"Error handling substage assignment change: {str(e)}")
        return False