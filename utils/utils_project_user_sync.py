import streamlit as st
from backend.users_backend import DatabaseManager,UserService,ProjectService
from backend.projects_backend import get_project_by_name,update_project_by_name 

def _initialize_services():
    """Initialize services for user-project synchronization"""
    if 'user_service' not in st.session_state:
        db_manager = DatabaseManager()
        st.session_state.user_service = UserService(db_manager)
        st.session_state.project_service = ProjectService(db_manager)

def _sync_user_projects_on_assignment_change(project_name, old_assignments, new_assignments):
    """
    Synchronize user projects when stage/substage assignments change
    
    Args:
        project_name: Name of the project being modified
        old_assignments: Previous stage assignments
        new_assignments: New stage assignments
    """
    try:
        # Get all users from old and new assignments
        old_users = _get_users_from_assignments(old_assignments)
        new_users = _get_users_from_assignments(new_assignments)
        
        # Users who were added to the project
        added_users = new_users - old_users
        
        # Users who were removed from the project
        removed_users = old_users - new_users
        
        # Add project to newly assigned users
        for username in added_users:
            if username:
                _add_project_to_user(username, project_name)
        
        # Remove project from users who are no longer assigned
        for username in removed_users:
            if username:
                _remove_project_from_user(username, project_name)
                
    except Exception as e:
        st.error(f"Error synchronizing user projects: {str(e)}")

def _get_users_from_assignments(assignments):
    """Extract all unique users from stage assignments"""
    users = set()
    
    if not assignments:
        return users
    
    for stage_name, assignment_data in assignments.items():
        if isinstance(assignment_data, dict):
            # Get user assigned to main stage
            assigned_to = assignment_data.get("assigned_to", "")
            if assigned_to and assigned_to.strip():
                users.add(assigned_to.strip())
            
            # Get users assigned to substages
            substages = assignment_data.get("substages", {})
            for substage_name, substage_data in substages.items():
                if isinstance(substage_data, dict):
                    substage_assigned_to = substage_data.get("assigned_to", "")
                    if substage_assigned_to and substage_assigned_to.strip():
                        users.add(substage_assigned_to.strip())
    
    return users

def _add_project_to_user(username, project_name):
    """Add project to user's current projects list"""
    try:
        # Convert username to email format for user service
        email = f"{username}@v-shesh.com"  # Adjust based on your email format
        
        # Get current user data
        user_data = st.session_state.get('user_service', UserService(DatabaseManager())).fetch_user_data(email)
        
        if user_data:
            current_projects = user_data.get("project", [])
            if project_name not in current_projects:
                current_projects.append(project_name)
                
                # Update user in database
                st.session_state.get('user_service', UserService(DatabaseManager())).update_member(
                    email, {"project": current_projects}
                )
                
                # Also update projects table
                project_service = st.session_state.get('project_service', ProjectService(DatabaseManager()))
                project_service.add_user_to_projects(username, [project_name])
                
    except Exception as e:
        st.warning(f"Could not add project {project_name} to user {username}: {str(e)}")

def _remove_project_from_user(username, project_name):
    """Remove project from user's current projects list"""
    try:
        # Convert username to email format for user service
        email = f"{username}@v-shesh.com"  # Adjust based on your email format
        
        # Get current user data
        user_data = st.session_state.get('user_service', UserService(DatabaseManager())).fetch_user_data(email)
        
        if user_data:
            current_projects = user_data.get("project", [])
            if project_name in current_projects:
                current_projects.remove(project_name)
                
                # Update user in database
                st.session_state.get('user_service', UserService(DatabaseManager())).update_member(
                    email, {"project": current_projects}
                )
                
                # Also update projects table
                project_service = st.session_state.get('project_service', ProjectService(DatabaseManager()))
                project_service.remove_user_from_projects(username, [project_name])
                
    except Exception as e:
        st.warning(f"Could not remove project {project_name} from user {username}: {str(e)}")


def _get_all_users_in_project_assignments(stage_assignments):
    """Extract all users assigned to any stage or substage in the project assignments"""
    all_users = set()
    
    if not stage_assignments:
        return all_users
    
    for stage_name, assignment_data in stage_assignments.items():
        if isinstance(assignment_data, dict):
            # Get user assigned to main stage
            assigned_to = assignment_data.get("assigned_to", "")
            if assigned_to and assigned_to.strip():
                all_users.add(assigned_to.strip())
            
            # Get users assigned to substages
            substages = assignment_data.get("substages", {})
            for substage_name, substage_data in substages.items():
                if isinstance(substage_data, dict):
                    substage_assigned_to = substage_data.get("assigned_to", "")
                    if substage_assigned_to and substage_assigned_to.strip():
                        all_users.add(substage_assigned_to.strip())
    
    return all_users

def _update_user_project_assignments(project_name, stage_assignments):
    """
    Enhanced version of your existing function to handle both stage and substage assignments
    This replaces your existing _update_user_project_assignments function
    """
    try:
        # Get all users currently assigned to this project (stages + substages)
        assigned_users = _get_all_users_in_project_assignments(stage_assignments)
        
        # Get all users who currently have this project in their profile
        current_users_with_project = _get_users_with_project(project_name)
        
        # Users to add (newly assigned)
        users_to_add = assigned_users - current_users_with_project
        
        # Users to remove (no longer assigned anywhere)
        users_to_remove = current_users_with_project - assigned_users
        
        # Add project to newly assigned users
        for username in users_to_add:
            if username:
                _add_project_to_user_profile(username, project_name)
        
        # Remove project from users who are no longer assigned
        for username in users_to_remove:
            if username:
                _remove_project_from_user_profile(username, project_name)
                
        # Update project team list with all assigned users
        _update_project_team_list(project_name, list(assigned_users))
        
    except Exception as e:
        st.error(f"Error updating user project assignments: {str(e)}")

def _get_users_with_project(project_name):
    """Get all users who currently have this project in their profile"""
    try:
        # Initialize database manager and user service
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        
        # Get all users
        all_users = user_service.load_team_data()
        
        users_with_project = set()
        for user in all_users:
            user_projects = user.get("project", [])
            if project_name in user_projects:
                username = user.get("username", "")
                if username:
                    users_with_project.add(username)
        
        return users_with_project
        
    except Exception as e:
        st.warning(f"Error getting users with project {project_name}: {str(e)}")
        return set()

def _add_project_to_user_profile(username, project_name):
    """Add project to user's profile"""
    try:
        # Initialize services
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        project_service = ProjectService(db_manager)
        
        # Convert username to email format (adjust based on your system)
        email = f"{username}@v-shesh.com"  # Modify this format as needed
        
        # Get current user data
        user_data = user_service.fetch_user_data(email)
        
        if user_data:
            current_projects = user_data.get("project", [])
            if project_name not in current_projects:
                current_projects.append(project_name)
                
                # Update user in database
                user_service.update_member(email, {"project": current_projects})
                
                # Also update projects table
                project_service.add_user_to_projects(username, [project_name])
                
                st.success(f"✅ Added {project_name} to {username}'s projects")
        else:
            st.warning(f"⚠️ User {username} not found in database")
            
    except Exception as e:
        st.warning(f"Could not add project {project_name} to user {username}: {str(e)}")

def _remove_project_from_user_profile(username, project_name):
    """Remove project from user's profile"""
    try:
        # Initialize services
        db_manager = DatabaseManager()
        user_service = UserService(db_manager)
        project_service = ProjectService(db_manager)
        
        # Convert username to email format (adjust based on your system)
        email = f"{username}@v-shesh.com"  # Modify this format as needed
        
        # Get current user data
        user_data = user_service.fetch_user_data(email)
        
        if user_data:
            current_projects = user_data.get("project", [])
            if project_name in current_projects:
                current_projects.remove(project_name)
                
                # Update user in database
                user_service.update_member(email, {"project": current_projects})
                
                # Also update projects table
                project_service.remove_user_from_projects(username, [project_name])
                
                st.success(f"✅ Removed {project_name} from {username}'s projects")
                
    except Exception as e:
        st.warning(f"Could not remove project {project_name} from user {username}: {str(e)}")

def _update_project_team_list(project_name, assigned_users):
    """Update the project's team list with all assigned users"""
    try:
        # Get project data
        project_data = get_project_by_name(project_name)
        if project_data:
            # Update team list
            update_data = {"team": assigned_users}
            update_project_by_name(project_name, update_data)
            
    except Exception as e:
        st.warning(f"Could not update team list for project {project_name}: {str(e)}")


def _sync_user_projects_on_stage_change(project_name, old_stage_assignments, new_stage_assignments):
    """
    Synchronize user projects when stage assignments change during level progression
    This is called when stages are completed/uncompleted
    """
    try:
        # Get users from both old and new assignments
        old_users = _get_all_users_in_project_assignments(old_stage_assignments)
        new_users = _get_all_users_in_project_assignments(new_stage_assignments)
        
        # If assignments are the same, no sync needed
        if old_users == new_users:
            return
        
        # Users who were added
        added_users = new_users - old_users
        
        # Users who were removed
        removed_users = old_users - new_users
        
        # Add project to newly assigned users
        for username in added_users:
            if username:
                _add_project_to_user_profile(username, project_name)
        
        # Remove project from users who are no longer assigned
        for username in removed_users:
            if username:
                _remove_project_from_user_profile(username, project_name)
                
    except Exception as e:
        st.error(f"Error synchronizing user projects on stage change: {str(e)}")

