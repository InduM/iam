import streamlit as st
from datetime import datetime, timedelta
from utils.utils_project_core import send_stage_assignment_email
from backend.projects_backend import update_client_project_count
from backend.users_backend import DatabaseManager, UserService

# =============================================================================
# CORE DATA FUNCTIONS
# =============================================================================

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

# =============================================================================
# USER EXTRACTION AND MANAGEMENT
# =============================================================================

class UserExtractor:
    """Centralized user extraction from project assignments"""
    
    @staticmethod
    def extract_users_from_stage_assignments(stage_assignments):
        """Extract all users from stage assignments"""
        if not isinstance(stage_assignments, dict):
            return set()
        
        users = set()
        for stage_data in stage_assignments.values():
            if isinstance(stage_data, dict):
                # Extract from members list
                members = stage_data.get("members", [])
                if isinstance(members, list):
                    users.update(member.strip() for member in members if member and member.strip())
                
                # Extract from substages
                substages = stage_data.get("substages", {})
                for substage_data in substages.values():
                    if isinstance(substage_data, dict):
                        assignees = substage_data.get("assignees", [])
                        if isinstance(assignees, str) and assignees.strip():
                            users.add(assignees.strip())
                        elif isinstance(assignees, list):
                            users.update(assignee.strip() for assignee in assignees if assignee and assignee.strip())
        
        return users
    
    @staticmethod
    def get_user_email_from_username(username):
        """Convert username to email format"""
        if "@" in username:
            return username
        return f"{username}@v-shesh.com"

class UserProjectSync:
    """Centralized user-project synchronization"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.user_service = UserService(self.db_manager)
        self.user_extractor = UserExtractor()
    
    def sync_single_user(self, username, project_name, action="add"):
        """
        Sync a single user's project assignment
        
        Args:
            username: Username to sync
            project_name: Project name
            action: "add" or "remove"
        
        Returns:
            bool: Success status
        """
        try:
            if not username or not project_name:
                return False
            
            user_email = self.user_extractor.get_user_email_from_username(username)
            user_data = self.user_service.fetch_user_data(user_email)
            
            if not user_data:
                st.warning(f"⚠️ User {username} not found in database")
                return False
            
            current_projects = user_data.get("project", [])
            if not isinstance(current_projects, list):
                current_projects = []
            
            if action == "add":
                if project_name not in current_projects:
                    current_projects.append(project_name)
                    self.user_service.update_member(user_email, {"project": current_projects})
                return True
            
            elif action == "remove":
                if project_name in current_projects:
                    current_projects.remove(project_name)
                    self.user_service.update_member(user_email, {"project": current_projects})
                return True
            
            return False
            
        except Exception as e:
            st.error(f"❌ Error syncing user {username}: {str(e)}")
            return False
    
    def sync_multiple_users(self, usernames, project_name, action="add"):
        """
        Sync multiple users' project assignments
        
        Args:
            usernames: Set or list of usernames
            project_name: Project name
            action: "add" or "remove"
        
        Returns:
            int: Number of users successfully synced
        """
        success_count = 0
        for username in usernames:
            if self.sync_single_user(username, project_name, action):
                success_count += 1
        return success_count
    
    def validate_users_exist(self, usernames):
        """
        Validate that all users exist in the database
        
        Args:
            usernames: Set or list of usernames
        
        Returns:
            tuple: (is_valid, list_of_invalid_users)
        """
        try:
            invalid_users = []
            for username in usernames:
                user_email = self.user_extractor.get_user_email_from_username(username)
                user_data = self.user_service.fetch_user_data(user_email)
                if not user_data:
                    invalid_users.append(username)
            
            return len(invalid_users) == 0, invalid_users
            
        except Exception as e:
            st.error(f"Error validating users: {str(e)}")
            return False, list(usernames)

# =============================================================================
# PROJECT MANAGEMENT FUNCTIONS
# =============================================================================

class ProjectManager:
    """Centralized project management with user synchronization"""
    
    def __init__(self):
        self.user_sync = UserProjectSync()
        self.user_extractor = UserExtractor()
    
    def create_project(self, project_data):
        """
        Create a new project with user synchronization
        
        Args:
            project_data: Complete project data dictionary
        
        Returns:
            bool: Success status
        """
        try:
            project_name = project_data.get("name", "")
            stage_assignments = project_data.get("stage_assignments", {})
            
            # Extract and validate users
            all_users = self.user_extractor.extract_users_from_stage_assignments(stage_assignments)
            is_valid, invalid_users = self.user_sync.validate_users_exist(all_users)
            
            if not is_valid:
                st.error(f"❌ Invalid users found: {', '.join(invalid_users)}")
                return False
            
            # Sync users to project
            success_count = self.user_sync.sync_multiple_users(all_users, project_name, "add")
            
            # Send notifications
            self._send_stage_assignment_notifications(project_data)
            
            # Update client count
            update_client_project_count(project_data.get("client", ""))
            
            if success_count > 0:
                st.success(f"✅ Project created and added to {success_count} user profiles")
            
            return True
            
        except Exception as e:
            st.error(f"Error creating project: {str(e)}")
            return False
    
    def update_project(self, project_name, old_project_data, new_project_data):
        """
        Update an existing project with user synchronization
        
        Args:
            project_name: Name of the project
            old_project_data: Previous project data
            new_project_data: Updated project data
        
        Returns:
            bool: Success status
        """
        try:
            old_stage_assignments = old_project_data.get("stage_assignments", {})
            new_stage_assignments = new_project_data.get("stage_assignments", {})
            
            # Extract users from old and new assignments
            old_users = self.user_extractor.extract_users_from_stage_assignments(old_stage_assignments)
            new_users = self.user_extractor.extract_users_from_stage_assignments(new_stage_assignments)
            
            # Validate new users
            is_valid, invalid_users = self.user_sync.validate_users_exist(new_users)
            if not is_valid:
                st.error(f"❌ Invalid users found: {', '.join(invalid_users)}")
                return False
            
            # Calculate changes
            users_to_add = new_users - old_users
            users_to_remove = old_users - new_users
            
            # Sync changes
            added_count = self.user_sync.sync_multiple_users(users_to_add, project_name, "add")
            removed_count = self.user_sync.sync_multiple_users(users_to_remove, project_name, "remove")
            
            # Send change notifications
            self._send_stage_assignment_change_notifications(
                new_stage_assignments, old_stage_assignments, project_name
            )
            
            # Update client counts
            self._update_client_counts_after_edit(old_project_data, new_project_data.get("client", ""))
            
            # Log results
            if added_count > 0:
                st.success(f"✅ Project added to {added_count} new users")
            if removed_count > 0:
                st.info(f"ℹ️ Project removed from {removed_count} users")
            
            return True
            
        except Exception as e:
            st.error(f"Error updating project: {str(e)}")
            return False
    
    def handle_real_time_assignment_change(self, project_name, stage_assignments):
        """
        Handle real-time assignment changes (for UI updates)
        
        Args:
            project_name: Name of the project
            stage_assignments: Current stage assignments
        
        Returns:
            bool: Success status
        """
        try:
            # Extract current users
            current_users = self.user_extractor.extract_users_from_stage_assignments(stage_assignments)
            
            # Add project to all current users (idempotent operation)
            success_count = self.user_sync.sync_multiple_users(current_users, project_name, "add")
            
            return success_count >= 0  # Even 0 is success (no new users to add)
            
        except Exception as e:
            st.error(f"Error handling real-time assignment change: {str(e)}")
            return False
    
    def _send_stage_assignment_notifications(self, project_data):
        """Send notifications for stage assignments in new project"""
        stage_assignments = project_data.get("stage_assignments", {})
        project_name = project_data.get("name", "Unnamed")
        
        if stage_assignments:
            self._send_stage_assignment_emails(stage_assignments, project_name)
    
    def _send_stage_assignment_emails(self, assignments, project_name):
        """Helper function to send stage assignment emails"""
        for stage_index, assignment in assignments.items():
            members = assignment.get("members", [])
            if members:
                deadline = assignment.get("deadline", "")
                stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
                member_emails = [f"{member}@v-shesh.com" for member in members]
                send_stage_assignment_email(member_emails, project_name, stage_name, deadline)
    
    def _send_stage_assignment_change_notifications(self, new_assignments, old_assignments, project_name):
        """Send notifications when stage assignments change"""
        changed_assignments = {}
        
        for stage_index, assignment in new_assignments.items():
            old_assignment = old_assignments.get(stage_index, {})
            new_members = set(assignment.get("members", []))
            old_members = set(old_assignment.get("members", []))
            
            newly_assigned = new_members - old_members
            if newly_assigned:
                changed_assignments[stage_index] = {
                    "members": list(newly_assigned),
                    "deadline": assignment.get("deadline", ""),
                    "stage_name": assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
                }
        
        if changed_assignments:
            self._send_stage_assignment_emails(changed_assignments, project_name)
    
    def _update_client_counts_after_edit(self, old_project_data, new_client):
        """Update client project counts after editing"""
        update_client_project_count(new_client)
        
        old_client = old_project_data.get("client", "")
        if new_client != old_client:
            update_client_project_count(old_client)

# =============================================================================
# UI HELPER FUNCTIONS
# =============================================================================

def display_success_messages(messages=None):
    """Display success messages"""
    if messages:
        for message in messages:
            st.success(message)
    else:
        st.success("Changes saved to database!")

def check_success_messages(pid, context="dashboard"):
    """Check and display success messages for dashboard or edit context"""
    key_prefix = "edit_" if context == "edit" else ""
    
    if st.session_state.get(f"{key_prefix}level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"{key_prefix}level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

def handle_email_reminders(project, pid, levels, current_level):
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

# =============================================================================
# MAIN API FUNCTIONS (Use these in your application)
# =============================================================================

# Initialize global project manager
_project_manager = ProjectManager()

def create_project_with_sync(project_data):
    """
    Main function to create a project with full synchronization
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        bool: Success status
    """
    return _project_manager.create_project(project_data)

def update_project_with_sync(project_name, old_project_data, new_project_data):
    """
    Main function to update a project with full synchronization
    
    Args:
        project_name: Name of the project
        old_project_data: Previous project data
        new_project_data: Updated project data
    
    Returns:
        bool: Success status
    """
    return _project_manager.update_project(project_name, old_project_data, new_project_data)

def handle_assignment_change(project_name, stage_assignments):
    """
    Main function to handle real-time assignment changes
    
    Args:
        project_name: Name of the project
        stage_assignments: Current stage assignments
    
    Returns:
        bool: Success status
    """
    return _project_manager.handle_real_time_assignment_change(project_name, stage_assignments)

# =============================================================================
# LEGACY COMPATIBILITY (Keep for backward compatibility)
# =============================================================================

# Legacy function names that delegate to new implementations
def _check_dashboard_success_messages(pid):
    """Legacy wrapper"""
    check_success_messages(pid, "dashboard")

def _check_edit_success_messages(pid):
    """Legacy wrapper"""
    check_success_messages(pid, "edit")

def _display_success_messages(messages):
    """Legacy wrapper"""
    display_success_messages(messages)

def _update_client_counts_after_edit(project, new_client):
    """Legacy wrapper"""
    _project_manager._update_client_counts_after_edit(project, new_client)

def _handle_email_reminders(project, pid, levels, current_level):
    """Legacy wrapper"""
    handle_email_reminders(project, pid, levels, current_level)