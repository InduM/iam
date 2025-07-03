import streamlit as st
import time
from datetime import date, timedelta
from typing import Dict, List, Optional, Union, Tuple

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


def auto_adjust_stage_dates(stage_assignments, old_due_date, new_due_date):
    """
    Automatically adjust stage and substage dates when project due date changes
    Proportionally scales dates to fit within new timeline
    """
    if not stage_assignments or old_due_date == new_due_date:
        return stage_assignments
    
    # Calculate the scaling factor
    old_duration = (old_due_date - date.today()).days
    new_duration = (new_due_date - date.today()).days
    
    if old_duration <= 0:
        return stage_assignments  # Can't scale if old duration is invalid
    
    scale_factor = new_duration / old_duration
    
    adjusted_assignments = {}
    
    for stage_key, stage_data in stage_assignments.items():
        adjusted_stage = stage_data.copy()
        
        # Adjust main stage deadline
        if "deadline" in stage_data and stage_data["deadline"]:
            try:
                stage_deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                days_from_today = (stage_deadline - date.today()).days
                new_days = int(days_from_today * scale_factor)
                new_deadline = date.today() + timedelta(days=max(1, new_days))
                
                # Ensure it doesn't exceed project due date
                if new_deadline > new_due_date:
                    new_deadline = new_due_date
                
                adjusted_stage["deadline"] = new_deadline.isoformat()
            except (ValueError, TypeError):
                pass  # Keep original if conversion fails
        
        # Adjust substage deadlines
        if "substages" in stage_data:
            adjusted_substages = []
            for substage in stage_data["substages"]:
                adjusted_substage = substage.copy()
                
                if "deadline" in substage and substage["deadline"]:
                    try:
                        substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                        days_from_today = (substage_deadline - date.today()).days
                        new_days = int(days_from_today * scale_factor)
                        new_deadline = date.today() + timedelta(days=max(1, new_days))
                        
                        # Ensure it doesn't exceed project due date
                        if new_deadline > new_due_date:
                            new_deadline = new_due_date
                        
                        adjusted_substage["deadline"] = new_deadline.isoformat()
                    except (ValueError, TypeError):
                        pass  # Keep original if conversion fails
                
                adjusted_substages.append(adjusted_substage)
            
            adjusted_stage["substages"] = adjusted_substages
        
        adjusted_assignments[stage_key] = adjusted_stage
    
    return adjusted_assignments

# NEW FUNCTION: Check for overdue stages and substages
def get_overdue_stages_and_substages(stage_assignments, project_levels, current_level):
    
    """
    Get all overdue stages and substages
    Returns list of overdue items with details
    """
    overdue_items = []
    today = date.today()
    
    if not stage_assignments:
        return overdue_items
    
    for stage_idx in range(min(current_level + 2, len(project_levels))):  # Check current and next stage
        stage_key = str(stage_idx)
        
        if stage_key not in stage_assignments:
            continue
        
        stage_data = stage_assignments[stage_key]
        stage_name = stage_data.get("stage_name", project_levels[stage_idx] if stage_idx < len(project_levels) else f"Stage {stage_idx}")
        
        # Check main stage deadline (only if not completed)
        if stage_idx > current_level and "deadline" in stage_data and stage_data["deadline"]:
            try:
                deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                if deadline < today:
                    days_overdue = (today - deadline).days
                    overdue_items.append({
                        "type": "stage",
                        "stage_index": stage_idx,
                        "stage_name": stage_name,
                        "deadline": deadline.isoformat(),
                        "days_overdue": days_overdue
                    })
            except (ValueError, TypeError):
                pass
        
        # Check substage deadlines
        substages = stage_data.get("substages", [])
        for substage_idx, substage in enumerate(substages):
            if "deadline" in substage and substage["deadline"]:
                try:
                    deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    if deadline < today:
                        days_overdue = (today - deadline).days
                        substage_name = substage.get("name", f"Substage {substage_idx + 1}")
                        overdue_items.append({
                            "type": "substage",
                            "stage_index": stage_idx,
                            "stage_name": stage_name,
                            "substage_index": substage_idx,
                            "substage_name": substage_name,
                            "deadline": deadline.isoformat(),
                            "days_overdue": days_overdue
                        })
                except (ValueError, TypeError):
                    pass
    
    return overdue_items


def auto_adjust_substage_dates_to_stage(stage_deadline, substages):
    """
    Automatically adjust substage dates when stage deadline changes
    Ensures all substage deadlines are <= stage deadline
    """
    if not stage_deadline or not substages:
        return substages
    
    try:
        # Convert stage deadline to date object if it's a string
        if isinstance(stage_deadline, str):
            stage_deadline = date.fromisoformat(stage_deadline)
        
        adjusted_substages = []
        
        for substage in substages:
            adjusted_substage = substage.copy()
            
            if "deadline" in substage and substage["deadline"]:
                try:
                    substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    
                    # If substage deadline is after stage deadline, adjust it
                    if substage_deadline > stage_deadline:
                        adjusted_substage["deadline"] = stage_deadline.isoformat()
                        # Optionally add a flag to indicate it was auto-adjusted
                        adjusted_substage["_auto_adjusted"] = True
                
                except (ValueError, TypeError):
                    # Keep original if conversion fails
                    pass
            
            adjusted_substages.append(adjusted_substage)
        
        return adjusted_substages
        
    except (ValueError, TypeError):
        return substages  # Return original if stage deadline conversion fails
    


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

class ProjectCompletionChecker:
    """Unified completion checker for projects, stages, and substages"""
    
    def __init__(self, project, stage_assignments=None):
        self.project = project or {}
        self.stage_assignments = stage_assignments or {}
        self.project_levels = self.project.get("levels", [])
        self.current_level = self.project.get("level", -1)
        self.substage_completion = self.project.get("substage_completion", {})
    
    def has_substages(self, stage_index):
        """Check if a stage has substages defined"""
        stage_key = str(stage_index)
        if stage_key not in self.stage_assignments:
            return False
        
        substages = self.stage_assignments[stage_key].get("substages", [])
        return len(substages) > 0
    
    def are_all_substages_complete(self, stage_index):
        """Check if all substages for a given stage are completed"""
        stage_key = str(stage_index)
        
        # No substages means stage can be completed
        if not self.has_substages(stage_index):
            return True
        
        substages = self.stage_assignments[stage_key].get("substages", [])
        stage_completion = self.substage_completion.get(stage_key, {})
        
        # Check if all substages are completed
        for substage_idx in range(len(substages)):
            if not stage_completion.get(str(substage_idx), False):
                return False
        
        return True
    
    def get_substage_completion_status(self, stage_index):
        """Get detailed completion status for a stage's substages"""
        stage_key = str(stage_index)
        
        if not self.has_substages(stage_index):
            return {
                "has_substages": False,
                "total_substages": 0,
                "completed_substages": 0,
                "completion_percentage": 100,
                "all_complete": True
            }
        
        substages = self.stage_assignments[stage_key].get("substages", [])
        stage_completion = self.substage_completion.get(stage_key, {})
        
        total = len(substages)
        completed = sum(1 for i in range(total) if stage_completion.get(str(i), False))
        
        return {
            "has_substages": True,
            "total_substages": total,
            "completed_substages": completed,
            "completion_percentage": (completed / total * 100) if total > 0 else 0,
            "all_complete": completed == total
        }
    
    def check_project_completion_status(self):
        """
        Check if project has reached completion and handle completion logic
        Returns completion status and performs necessary actions
        """
        completion_status = {
            "is_complete": False,
            "completion_stage": None,
            "completion_stage_index": -1,
            "moved_to_completed": False,
            "affected_members": 0
        }
        
        if self.current_level < 0 or self.current_level >= len(self.project_levels):
            return completion_status
        
        current_stage = self.project_levels[self.current_level]
        
        # Check if current stage is a completion stage (e.g., "Payment")
        if current_stage == "Payment":
            completion_status.update({
                "is_complete": True,
                "completion_stage": current_stage,
                "completion_stage_index": self.current_level
            })
            
            # Handle moving project to completed
            project_name = self.project.get("name", "")
            team_members = self.project.get("team", [])
            
            if project_name and team_members:
                from backend.projects_backend import move_project_to_completed
                moved_count = move_project_to_completed(project_name, team_members)
                completion_status.update({
                    "moved_to_completed": moved_count > 0,
                    "affected_members": moved_count
                })
        
        return completion_status
    
    def can_advance_to_stage(self, target_stage_index):
        """
        Check if project can advance to a specific stage
        Returns (can_advance, reason)
        """
        if target_stage_index <= self.current_level:
            return True, "Stage already completed or current"
        
        if target_stage_index != self.current_level + 1:
            return False, "Can only advance to next stage sequentially"
        
        if not self.are_all_substages_complete(target_stage_index):
            return False, "All substages must be completed before advancing"
        
        return True, "Can advance to stage"
    
    def get_completion_summary(self):
        """Get a comprehensive completion summary for the project"""
        summary = {
            "current_level": self.current_level,
            "total_stages": len(self.project_levels),
            "project_completion_percentage": 0,
            "stages": []
        }
        
        if len(self.project_levels) > 0:
            summary["project_completion_percentage"] = ((self.current_level + 1) / len(self.project_levels)) * 100
        
        # Get completion status for each stage
        for stage_idx, stage_name in enumerate(self.project_levels):
            stage_status = {
                "stage_index": stage_idx,
                "stage_name": stage_name,
                "is_completed": stage_idx <= self.current_level,
                "is_current": stage_idx == self.current_level + 1,
                "substage_status": self.get_substage_completion_status(stage_idx)
            }
            summary["stages"].append(stage_status)
        
        # Add overall project completion status
        completion_status = self.check_project_completion_status()
        summary["project_completion"] = completion_status
        
        return summary


def _check_project_completion(project, project_id):
    """
    Simplified wrapper function for backward compatibility
    Checks if project has reached completion stage and handles completion logic
    """
    stage_assignments = project.get("stage_assignments", {})
    checker = ProjectCompletionChecker(project, stage_assignments)
    completion_status = checker.check_project_completion_status()
    
    if completion_status["moved_to_completed"]:
        st.session_state[f"project_completed_message_{project_id}"] = \
            f"Project moved to completed for {completion_status['affected_members']} team member(s)!"
    
    return completion_status["is_complete"]


def _are_all_substages_complete(project, stage_assignments, stage_index):
    """
    Simplified wrapper function for backward compatibility
    Check if all substages for a given stage are completed
    """
    checker = ProjectCompletionChecker(project, stage_assignments)
    return checker.are_all_substages_complete(stage_index)


def _has_substages(stage_assignments, stage_index):
    """
    Simplified wrapper function for backward compatibility
    Check if a stage has substages defined
    """
    checker = ProjectCompletionChecker({}, stage_assignments)
    return checker.has_substages(stage_index)

class ProjectDateValidator:
    """Unified date validator for projects, stages, and substages"""
    
    def __init__(self, stage_assignments: Dict, project_due_date: Union[date, str]):
        self.stage_assignments = stage_assignments or {}
        self.project_due_date = self._parse_date(project_due_date)
        self.errors = []
        self.conflicts = {
            "stage_vs_project": [],
            "substage_vs_project": [],
            "substage_vs_stage": [],
            "invalid_formats": []
        }
    
    def _parse_date(self, date_input: Union[date, str, None]) -> Optional[date]:
        """Safely parse date from string or date object"""
        if not date_input:
            return None
        
        if isinstance(date_input, date):
            return date_input
        
        if isinstance(date_input, str):
            try:
                return date.fromisoformat(date_input)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def _validate_single_deadline(self, deadline: Union[date, str, None], 
                                 reference_date: Optional[date], 
                                 deadline_name: str, 
                                 reference_name: str) -> Tuple[Optional[date], bool]:
        """
        Validate a single deadline against a reference date
        Returns (parsed_date, is_valid)
        """
        if not deadline:
            return None, True
        
        parsed_deadline = self._parse_date(deadline)
        
        if parsed_deadline is None:
            self.conflicts["invalid_formats"].append({
                "name": deadline_name,
                "deadline": str(deadline),
                "type": "invalid_format"
            })
            return None, False
        
        if reference_date and parsed_deadline > reference_date:
            return parsed_deadline, False
        
        return parsed_deadline, True
    
    def validate_stage_deadline(self, stage_key: str, stage_data: Dict, stage_name: str) -> Optional[date]:
        """Validate stage deadline against project due date"""
        stage_deadline = stage_data.get("deadline")
        
        if not stage_deadline:
            return None
        
        parsed_deadline, is_valid = self._validate_single_deadline(
            stage_deadline, self.project_due_date, f"Stage '{stage_name}'", "project"
        )
        
        if not is_valid and parsed_deadline:
            self.conflicts["stage_vs_project"].append({
                "stage_name": stage_name,
                "stage_deadline": parsed_deadline.isoformat(),
                "project_due": self.project_due_date.isoformat() if self.project_due_date else "N/A"
            })
            self.errors.append(
                f"Stage '{stage_name}' deadline ({parsed_deadline}) cannot be after project due date ({self.project_due_date})"
            )
        
        return parsed_deadline
    
    def validate_substage_deadlines(self, stage_key: str, stage_data: Dict, 
                                   stage_name: str, stage_deadline: Optional[date]) -> None:
        """Validate all substage deadlines for a stage"""
        substages = stage_data.get("substages", [])
        
        for idx, substage in enumerate(substages):
            substage_deadline = substage.get("deadline")
            substage_name = substage.get("name", f"Substage {idx + 1}")
            
            if not substage_deadline:
                continue
            
            parsed_deadline, is_valid_vs_project = self._validate_single_deadline(
                substage_deadline, self.project_due_date, 
                f"Substage '{substage_name}' in stage '{stage_name}'", "project"
            )
            
            if parsed_deadline is None:
                continue
            
            # Check against project due date
            if not is_valid_vs_project:
                self.conflicts["substage_vs_project"].append({
                    "stage_name": stage_name,
                    "substage_name": substage_name,
                    "substage_deadline": parsed_deadline.isoformat(),
                    "project_due": self.project_due_date.isoformat() if self.project_due_date else "N/A"
                })
                self.errors.append(
                    f"Substage '{substage_name}' in stage '{stage_name}' deadline ({parsed_deadline}) cannot be after project due date ({self.project_due_date})"
                )
            
            # Check against stage deadline
            if stage_deadline and parsed_deadline > stage_deadline:
                self.conflicts["substage_vs_stage"].append({
                    "stage_name": stage_name,
                    "substage_name": substage_name,
                    "substage_deadline": parsed_deadline.isoformat(),
                    "stage_deadline": stage_deadline.isoformat()
                })
                self.errors.append(
                    f"Substage '{substage_name}' deadline ({parsed_deadline}) cannot be after its parent stage '{stage_name}' deadline ({stage_deadline})"
                )
    
    def validate_all_dates(self) -> Dict:
        """
        Perform comprehensive date validation
        Returns validation results with errors and conflicts
        """
        if not self.stage_assignments or not self.project_due_date:
            return self.get_validation_results()
        
        for stage_key, stage_data in self.stage_assignments.items():
            if not isinstance(stage_data, dict):
                continue
            
            stage_name = stage_data.get("stage_name", f"Stage {stage_key}")
            
            # Validate stage deadline
            stage_deadline = self.validate_stage_deadline(stage_key, stage_data, stage_name)
            
            # Validate substage deadlines
            self.validate_substage_deadlines(stage_key, stage_data, stage_name, stage_deadline)
        
        return self.get_validation_results()
    
    def get_validation_results(self) -> Dict:
        """Get comprehensive validation results"""
        return {
            "is_valid": len(self.errors) == 0,
            "errors": self.errors,
            "conflicts": self.conflicts,
            "error_count": len(self.errors),
            "conflict_summary": self._get_conflict_summary()
        }
    
    def _get_conflict_summary(self) -> Dict:
        """Get summary of conflicts by type"""
        return {
            "stage_vs_project": len(self.conflicts["stage_vs_project"]),
            "substage_vs_project": len(self.conflicts["substage_vs_project"]),
            "substage_vs_stage": len(self.conflicts["substage_vs_stage"]),
            "invalid_formats": len(self.conflicts["invalid_formats"]),
            "total_conflicts": sum(len(conflicts) for conflicts in self.conflicts.values())
        }
    
    def display_validation_errors(self) -> None:
        """Display validation errors in Streamlit UI"""
        if not self.errors:
            return
        
        st.error("⚠️ **Deadline Conflicts Detected:**")
        
        if self.conflicts["stage_vs_project"]:
            st.error("**Stages with deadlines after project due date:**")
            for conflict in self.conflicts["stage_vs_project"]:
                st.error(f"  • {conflict['stage_name']}: {conflict['stage_deadline']} (Project due: {conflict['project_due']})")
        
        if self.conflicts["substage_vs_project"]:
            st.error("**Substages with deadlines after project due date:**")
            for conflict in self.conflicts["substage_vs_project"]:
                st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Project due: {conflict['project_due']})")
        
        if self.conflicts["substage_vs_stage"]:
            st.error("**Substages with deadlines after their stage deadline:**")
            for conflict in self.conflicts["substage_vs_stage"]:
                st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Stage due: {conflict['stage_deadline']})")
        
        if self.conflicts["invalid_formats"]:
            st.error("**Invalid deadline formats:**")
            for conflict in self.conflicts["invalid_formats"]:
                st.error(f"  • {conflict['name']}: {conflict['deadline']}")
    
    def get_detailed_conflict_report(self) -> str:
        """Get a detailed text report of all conflicts"""
        if not self.errors:
            return "✅ No date conflicts found."
        
        report = ["📋 **Date Validation Report**", ""]
        
        if self.conflicts["stage_vs_project"]:
            report.append("🔴 **Stages exceeding project deadline:**")
            for conflict in self.conflicts["stage_vs_project"]:
                report.append(f"  • {conflict['stage_name']}: {conflict['stage_deadline']}")
            report.append("")
        
        if self.conflicts["substage_vs_project"]:
            report.append("🔴 **Substages exceeding project deadline:**")
            for conflict in self.conflicts["substage_vs_project"]:
                report.append(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']}")
            report.append("")
        
        if self.conflicts["substage_vs_stage"]:
            report.append("🔴 **Substages exceeding stage deadline:**")
            for conflict in self.conflicts["substage_vs_stage"]:
                report.append(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']}")
            report.append("")
        
        if self.conflicts["invalid_formats"]:
            report.append("🔴 **Invalid date formats:**")
            for conflict in self.conflicts["invalid_formats"]:
                report.append(f"  • {conflict['name']}: {conflict['deadline']}")
        
        return "\n".join(report)


# Backward compatibility wrapper functions
def validate_stage_substage_dates(stage_assignments: Dict, project_due_date: Union[date, str], 
                                 display_conflicts: bool = True) -> List[str]:
    """
    Wrapper function for backward compatibility
    Validate that all stage and substage due dates are <= project due date
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    
    if display_conflicts and not results["is_valid"]:
        validator.display_validation_errors()
    
    return results["errors"]


def validate_substage_deadline_against_stage(stage_deadline: Union[date, str], 
                                           substage_deadline: Union[date, str], 
                                           stage_name: str, 
                                           substage_name: str) -> Optional[str]:
    """
    Wrapper function for backward compatibility
    Validate a single substage deadline against its parent stage deadline
    """
    # Create a minimal stage assignment for validation
    stage_assignments = {
        "0": {
            "stage_name": stage_name,
            "deadline": stage_deadline,
            "substages": [{
                "name": substage_name,
                "deadline": substage_deadline
            }]
        }
    }
    
    validator = ProjectDateValidator(stage_assignments, "2099-12-31")  # Dummy project date
    results = validator.validate_all_dates()
    
    # Return the first substage vs stage error if any
    substage_vs_stage_errors = [
        error for error in results["errors"] 
        if substage_name in error and stage_name in error and "cannot be after its parent stage" in error
    ]
    
    return substage_vs_stage_errors[0] if substage_vs_stage_errors else None


def get_deadline_conflicts_summary(stage_assignments: Dict, project_due_date: Union[date, str]) -> Dict:
    """
    Wrapper function for backward compatibility
    Get a summary of all deadline conflicts
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    return results["conflicts"]


def display_deadline_conflicts(conflicts: Dict) -> None:
    """
    Wrapper function for backward compatibility
    Display deadline conflicts in Streamlit UI
    """
    # Create a validator just for display purposes
    validator = ProjectDateValidator({}, "2099-12-31")
    validator.conflicts = conflicts
    validator.errors = ["Conflicts detected"]  # Dummy error to trigger display
    validator.display_validation_errors()


# Enhanced validation function for comprehensive project validation
def validate_project_dates_comprehensive(stage_assignments: Dict, 
                                       project_due_date: Union[date, str],
                                       return_detailed_report: bool = False) -> Union[bool, Dict]:
    """
    Comprehensive project date validation with detailed reporting
    
    Args:
        stage_assignments: Dictionary of stage assignments
        project_due_date: Project due date
        return_detailed_report: If True, returns detailed validation results
        
    Returns:
        bool: True if valid (when return_detailed_report=False)
        Dict: Detailed validation results (when return_detailed_report=True)
    """
    validator = ProjectDateValidator(stage_assignments, project_due_date)
    results = validator.validate_all_dates()
    
    if return_detailed_report:
        results["detailed_report"] = validator.get_detailed_conflict_report()
        return results
    
    return results["is_valid"]