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
            substages = stage_data.get("substages", [])
            for substage_data in substages:
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
    Send email notifications for stage assignments and substage assignees.
    Combines multiple assignments for the same person into one email.
    
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
                        "stage_name": assignment.get("stage_name", f"Stage {int(stage_index) + 1}"),
                        "substages": assignment.get("substages", [])
                    }
        else:
            # Send for all assignments
            assignments_to_notify = stage_assignments

        # Build combined assignment list per user
        user_assignments_map = {}

        for stage_index, assignment in assignments_to_notify.items():
            stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
            stage_deadline = assignment.get("deadline", "")

            # Stage-level members
            for member in assignment.get("members", []):
                user_assignments_map.setdefault(member, []).append({
                    "task": stage_name,
                    "deadline": stage_deadline
                })

            # Substage-level assignees
            for substage in assignment.get("substages", []):
                substage_name = substage.get("name", "Unnamed Substage")
                substage_deadline = substage.get("deadline", stage_deadline)
                for assignee in substage.get("assignees", []):
                    user_assignments_map.setdefault(assignee, []).append({
                        "task": f"{stage_name} → {substage_name}",
                        "deadline": substage_deadline
                    })

        # Send one combined email per user
        for user, tasks in user_assignments_map.items():
            email = [f"{user}@v-shesh.com"]
            send_combined_assignment_email(email, project_name, tasks,stage_name)

    except Exception as e:
        st.error(f"Error sending assignment notifications: {str(e)}")

def send_combined_assignment_email(recipient_email, project_name, tasks,stage_name):
    """
    Send a single combined email to a user with all their stage/substage assignments.

    Args:
        recipient_email (str): Recipient's email address.
        project_name (str): Name of the project.
        tasks (list of dict): List of tasks with "task" and "deadline".
                              Example: [{"task": "Stage 1 → Substage A", "deadline": "2025-05-12"}, ...]
    """
    try:
        # Sort tasks by deadline (if available)
        tasks_sorted = sorted(tasks, key=lambda x: x.get("deadline") or "")

        # Build HTML table of assignments
        task_rows = ""
        for t in tasks_sorted:
            task_name = t.get("task", "Unnamed Task")
            deadline = t.get("deadline", "No Deadline Set") or "No Deadline Set"
            task_rows += f"""
                <tr>
                    <td style="padding: 6px 10px; border: 1px solid #ddd;">{task_name}</td>
                    <td style="padding: 6px 10px; border: 1px solid #ddd;">{deadline}</td>
                </tr>
            """

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2>📋 New Assignments for Project: {project_name}</h2>
                <p>Hello,</p>
                <p>You have been assigned the following tasks:</p>
                <table style="border-collapse: collapse; width: 100%; border: 1px solid #ddd;">
                    <thead>
                        <tr style="background-color: #f4f4f4;">
                            <th style="padding: 6px 10px; border: 1px solid #ddd;">Task</th>
                            <th style="padding: 6px 10px; border: 1px solid #ddd;">Deadline</th>
                        </tr>
                    </thead>
                    <tbody>
                        {task_rows}
                    </tbody>
                </table>
                <p style="margin-top: 20px;">Please ensure to complete the tasks by the given deadlines.</p>
                <p>Regards,<br>Project Management System</p>
            </body>
        </html>
        """

        subject = f"Task Assignments for {project_name}"
        
        # Send using your existing email sender function
        send_stage_assignment_email(
            recipient_email,
            subject = subject,
            project_name = project_name,
            default_body=html_content,
            stage_name= stage_name,
            deadline = deadline,
        )

    except Exception as e:
        st.error(f"Error sending combined assignment email to {recipient_email}: {str(e)}")


# ==============================================================================
# HIGH-LEVEL PROJECT MANAGEMENT FUNCTIONS
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

def get_project_team(project):
    team = set()

    # 1. Stage-level members
    stage_assignments = project.get("stage_assignments", {})
    for stage in stage_assignments.values():
        members = stage.get("members", [])
        if isinstance(members, list):
            team.update(members)

        # 2. Substage assignees
        for ss in stage.get("substages", []):
            assignees = ss.get("assignees", [])
            if isinstance(assignees, list):
                team.update(assignees)

    # 3. Co-managers
    for cm in project.get("co_managers", []):
        user = cm.get("user")
        if user:
            team.add(user)

    # 4. Project creator
    if project.get("created_by"):
        team.add(project["created_by"])

    return sorted(team)
