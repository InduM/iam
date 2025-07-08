import streamlit as st
from backend.projects_backend import update_project_level_in_db
from utils.utils_project_core import (
    get_current_timestamp,
    notify_assigned_members,
)
from .project_helpers import(
    _get_user_email_from_username,
)
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
