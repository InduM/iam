import streamlit as st
import time
from datetime import date, timedelta
from utils.utils_project_core import (
    validate_project_dates,
    get_current_timestamp,
    notify_assigned_members,
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
    _reset_create_form_state,
    _update_client_counts_after_edit,
    _display_success_messages,
    _send_stage_assignment_change_notifications,
)

# UPDATED FUNCTION: Enhanced create project handler with substage completion reset
def _handle_create_project(name, client, description, start, due):
    """Handle project creation with enhanced date validation, complete reset, and substage completion clearing"""
    if not validate_project_dates(start, due):
        st.error("Cannot submit: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    elif _check_project_name_exists(name):
        st.error("A project with this name already exists. Please choose a different name.")
    else:
        # Validate stage and substage dates
        stage_assignments = st.session_state.get("stage_assignments", {})
        date_errors = enhanced_validate_stage_substage_dates(stage_assignments, due)
        
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
            
            # ENHANCED: Complete form state reset including substages and completion data
            _reset_create_form_state()
            clear_substage_completion_data()
            
            # Navigate back to dashboard
            st.session_state.view = "dashboard"
            st.rerun()

# UPDATED FUNCTION: Enhanced save project handler with date validation
def _handle_save_project(pid, project, name, client, description, start, due, original_team, original_name, stage_assignments):
    """Handle project save with enhanced date validation and substage data"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    else:
        # Validate stage and substage dates
        date_errors = enhanced_validate_stage_substage_dates(stage_assignments, due)
        
        if date_errors:
            st.error("Cannot save project due to date validation errors:")
            for error in date_errors:
                st.error(f"• {error}")
            return
        
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
            
            # Handle stage assignment changes
            old_assignments = project.get("stage_assignments", {})
            if stage_assignments != old_assignments:
                success_messages.append("Stage assignments updated!")
                _send_stage_assignment_change_notifications(stage_assignments, old_assignments, name)
            
            project.update(updated_project)
            
            # Display success messages
            _display_success_messages(success_messages)
            
            st.session_state.view = "dashboard"
            st.rerun()

def _handle_level_change_dashboard(proj_id, proj, new_index, stage_assignments):
    """Handle level change in dashboard view with sequential validation"""
    current_level = proj.get("level", -1)
    
    # Sequential validation for main stages
    if new_index > current_level:
        # Can only advance one stage at a time
        if new_index != current_level + 1:
            st.error("❌ You can only advance to the next stage sequentially!")
            return
        
        # Check if all substages are complete for the new stage
        if not _are_all_substages_complete(proj, stage_assignments, new_index):
            st.error("❌ Cannot advance to this stage - complete all substages first!")
            return
    elif new_index < current_level:
        # Can only go back one stage at a time
        if new_index != current_level - 1:
            st.error("❌ You can only go back one stage at a time!")
            return
    
    timestamp = get_current_timestamp()
    
    # Handle unchecking - remove timestamps for unchecked stages
    if new_index < current_level:
        levels = proj.get("levels", [])
        for level_idx in range(new_index + 1, len(levels)):
            if level_idx <= current_level:
                if "timestamps" in proj and str(level_idx) in proj["timestamps"]:
                    del proj["timestamps"][str(level_idx)]
    
    if update_project_level_in_db(proj_id, new_index, timestamp):
        proj["level"] = new_index
        if "timestamps" not in proj:
            proj["timestamps"] = {}
        proj["timestamps"][str(new_index)] = timestamp
        
        # Notify assigned members for the new stage
        if stage_assignments:
            notify_assigned_members(stage_assignments, proj.get("name", ""), new_index)
        
        # Check if project reached Payment stage
        _check_project_completion(proj, proj_id)
        
        st.session_state[f"level_update_success_{proj_id}"] = True
        st.success("Project level updated!")
        time.sleep(0.1)
        st.rerun()

def _handle_level_change_edit(project, pid, new_index, stage_assignments):
    """Handle level change in edit view with sequential validation"""
    current_level = project.get("level", -1)
    
    # Sequential validation for main stages
    if new_index > current_level:
        # Can only advance one stage at a time
        if new_index != current_level + 1:
            st.error("❌ You can only advance to the next stage sequentially!")
            return
        
        # Check if all substages are complete for the new stage
        if not _are_all_substages_complete(project, stage_assignments, new_index):
            st.error("❌ Cannot advance to this stage - complete all substages first!")
            return
    elif new_index < current_level:
        # Can only go back one stage at a time
        if new_index != current_level - 1:
            st.error("❌ You can only go back one stage at a time!")
            return
    
    timestamp = get_current_timestamp()
    
    # Handle unchecking - remove timestamps for unchecked stages
    if new_index < current_level:
        levels = project.get("levels", [])
        for level_idx in range(new_index + 1, len(levels)):
            if level_idx <= current_level:
                if "timestamps" in project and str(level_idx) in project["timestamps"]:
                    del project["timestamps"][str(level_idx)]
    
    project["level"] = new_index
    project.setdefault("timestamps", {})[str(new_index)] = timestamp
    
    # Update in database immediately
    if update_project_level_in_db(pid, new_index, timestamp):
        # Notify assigned members for the new stage
        if stage_assignments:
            notify_assigned_members(stage_assignments, project.get("name", ""), new_index)
        
        _check_project_completion(project, pid)
        st.session_state[f"edit_level_update_success_{pid}"] = True
        st.success("Project level updated!")
        time.sleep(0.1)
        st.rerun()

def _are_all_substages_complete(project, stage_assignments, stage_index):
    """
    Check if all substages for a given stage are completed
    """
    if not project or not stage_assignments:
        return True  # No substages means stage can be completed
    
    stage_key = str(stage_index)
    if stage_key not in stage_assignments:
        return True  # No substages defined for this stage
    
    substages = stage_assignments[stage_key].get("substages", [])
    if not substages:
        return True  # No substages means stage can be completed
    
    substage_completion = project.get("substage_completion", {})
    stage_completion = substage_completion.get(stage_key, {})
    
    # Check if all substages are completed
    for substage_idx in range(len(substages)):
        if not stage_completion.get(str(substage_idx), False):
            return False
    
    return True

def _has_substages(stage_assignments, stage_index):
    """
    Check if a stage has substages defined
    """
    if not stage_assignments:
        return False
    
    stage_key = str(stage_index)
    if stage_key not in stage_assignments:
        return False
    
    substages = stage_assignments[stage_key].get("substages", [])
    return len(substages) > 0

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


def _check_project_completion(project, project_id):
    """Check if project has reached completion stage"""
    project_levels = project.get("levels", [])
    new_level = project.get("level", -1)
    
    if (new_level >= 0 and new_level < len(project_levels) and 
        project_levels[new_level] == "Payment"):
        project_name = project.get("name", "")
        team_members = project.get("team", [])
        moved_count = move_project_to_completed(project_name, team_members)
        if moved_count > 0:
            st.session_state[f"project_completed_message_{project_id}"] = \
                f"Project moved to completed for {moved_count} team member(s)!"

def _check_project_name_exists(name):
    """Check if project name already exists"""
    from backend.projects_backend import get_db_collections
    collections = get_db_collections()
    return collections["projects"].find_one({"name": name}) is not None
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

def validate_stage_substage_dates(stage_assignments, project_due_date):
    """
    Validate that all stage and substage due dates are <= project due date
    AND substage deadlines are <= their parent stage deadline
    Returns list of validation errors
    """
    errors = []
    
    if not stage_assignments or not project_due_date:
        return errors
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {stage_key}")
        stage_deadline = None
        
        # Check main stage deadline
        if "deadline" in stage_data and stage_data["deadline"]:
            try:
                stage_deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                if stage_deadline > project_due_date:
                    errors.append(f"Stage '{stage_name}' deadline ({stage_deadline}) cannot be after project due date ({project_due_date})")
            except (ValueError, TypeError):
                errors.append(f"Invalid deadline format for stage '{stage_name}'")
                stage_deadline = None  # Reset to None if invalid
        
        # Check substage deadlines
        substages = stage_data.get("substages", [])
        for idx, substage in enumerate(substages):
            if "deadline" in substage and substage["deadline"]:
                try:
                    substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    substage_name = substage.get("name", f"Substage {idx + 1}")
                    
                    # Check against project due date
                    if substage_deadline > project_due_date:
                        errors.append(f"Substage '{substage_name}' in stage '{stage_name}' deadline ({substage_deadline}) cannot be after project due date ({project_due_date})")
                    
                    # Check against parent stage deadline (if stage has a deadline)
                    if stage_deadline and substage_deadline > stage_deadline:
                        errors.append(f"Substage '{substage_name}' deadline ({substage_deadline}) cannot be after its parent stage '{stage_name}' deadline ({stage_deadline})")
                        
                except (ValueError, TypeError):
                    substage_name = substage.get("name", f"Substage {idx + 1}")
                    errors.append(f"Invalid deadline format for substage '{substage_name}' in stage '{stage_name}'")
    
    return errors

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

def validate_substage_deadline_against_stage(stage_deadline, substage_deadline, stage_name, substage_name):
    """
    Validate a single substage deadline against its parent stage deadline
    Returns error message if invalid, None if valid
    """
    if not substage_deadline:
        return None  # No deadline to validate
    
    if not stage_deadline:
        return None  # No stage deadline to compare against
    
    try:
        # Convert to date objects if they're strings
        if isinstance(stage_deadline, str):
            stage_deadline = date.fromisoformat(stage_deadline)
        if isinstance(substage_deadline, str):
            substage_deadline = date.fromisoformat(substage_deadline)
        
        if substage_deadline > stage_deadline:
            return f"Substage '{substage_name}' deadline ({substage_deadline}) cannot be after stage '{stage_name}' deadline ({stage_deadline})"
        
        return None  # Valid
        
    except (ValueError, TypeError):
        return f"Invalid date format for substage '{substage_name}' or stage '{stage_name}'"

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
    
def validate_and_adjust_stage_assignments(stage_assignments, project_due_date, auto_adjust=False):
    """
    Validate stage assignments and optionally auto-adjust substage dates
    
    Args:
        stage_assignments: Dictionary of stage assignments
        project_due_date: Project due date
        auto_adjust: If True, automatically adjust invalid substage dates
    
    Returns:
        tuple: (adjusted_stage_assignments, list_of_errors)
    """
    errors = []
    adjusted_assignments = {}
    
    if not stage_assignments or not project_due_date:
        return stage_assignments, errors
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {stage_key}")
        adjusted_stage = stage_data.copy()
        stage_deadline = None
        
        # Validate and get stage deadline
        if "deadline" in stage_data and stage_data["deadline"]:
            try:
                stage_deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                
                # Check against project due date
                if stage_deadline > project_due_date:
                    if auto_adjust:
                        adjusted_stage["deadline"] = project_due_date.isoformat()
                        adjusted_stage["_auto_adjusted"] = True
                        stage_deadline = project_due_date
                    else:
                        errors.append(f"Stage '{stage_name}' deadline ({stage_deadline}) cannot be after project due date ({project_due_date})")
                        
            except (ValueError, TypeError):
                errors.append(f"Invalid deadline format for stage '{stage_name}'")
                stage_deadline = None
        
        # Process substages
        if "substages" in stage_data:
            substages = stage_data["substages"]
            adjusted_substages = []
            
            for idx, substage in enumerate(substages):
                adjusted_substage = substage.copy()
                substage_name = substage.get("name", f"Substage {idx + 1}")
                
                if "deadline" in substage and substage["deadline"]:
                    try:
                        substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                        
                        # Check against project due date
                        if substage_deadline > project_due_date:
                            if auto_adjust:
                                adjusted_substage["deadline"] = project_due_date.isoformat()
                                adjusted_substage["_auto_adjusted"] = True
                                substage_deadline = project_due_date
                            else:
                                errors.append(f"Substage '{substage_name}' in stage '{stage_name}' deadline ({substage_deadline}) cannot be after project due date ({project_due_date})")
                        
                        # Check against stage deadline
                        if stage_deadline and substage_deadline > stage_deadline:
                            if auto_adjust:
                                adjusted_substage["deadline"] = stage_deadline.isoformat()
                                adjusted_substage["_auto_adjusted"] = True
                            else:
                                errors.append(f"Substage '{substage_name}' deadline ({substage_deadline}) cannot be after stage '{stage_name}' deadline ({stage_deadline})")
                                
                    except (ValueError, TypeError):
                        errors.append(f"Invalid deadline format for substage '{substage_name}' in stage '{stage_name}'")
                
                adjusted_substages.append(adjusted_substage)
            
            adjusted_stage["substages"] = adjusted_substages
        
        adjusted_assignments[stage_key] = adjusted_stage
    
    return adjusted_assignments, errors

def get_deadline_conflicts_summary(stage_assignments, project_due_date):
    """
    Get a summary of all deadline conflicts for display purposes
    
    Returns:
        dict: Summary of conflicts organized by type
    """
    conflicts = {
        "stage_vs_project": [],
        "substage_vs_project": [],
        "substage_vs_stage": [],
        "invalid_formats": []
    }
    
    if not stage_assignments or not project_due_date:
        return conflicts
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {stage_key}")
        stage_deadline = None
        
        # Check stage deadline
        if "deadline" in stage_data and stage_data["deadline"]:
            try:
                stage_deadline = date.fromisoformat(stage_data["deadline"]) if isinstance(stage_data["deadline"], str) else stage_data["deadline"]
                
                if stage_deadline > project_due_date:
                    conflicts["stage_vs_project"].append({
                        "stage_name": stage_name,
                        "stage_deadline": stage_deadline.isoformat(),
                        "project_due": project_due_date.isoformat()
                    })
                    
            except (ValueError, TypeError):
                conflicts["invalid_formats"].append({
                    "type": "stage",
                    "name": stage_name,
                    "deadline": stage_data["deadline"]
                })
                stage_deadline = None
        
        # Check substages
        substages = stage_data.get("substages", [])
        for idx, substage in enumerate(substages):
            substage_name = substage.get("name", f"Substage {idx + 1}")
            
            if "deadline" in substage and substage["deadline"]:
                try:
                    substage_deadline = date.fromisoformat(substage["deadline"]) if isinstance(substage["deadline"], str) else substage["deadline"]
                    
                    # Check against project due date
                    if substage_deadline > project_due_date:
                        conflicts["substage_vs_project"].append({
                            "stage_name": stage_name,
                            "substage_name": substage_name,
                            "substage_deadline": substage_deadline.isoformat(),
                            "project_due": project_due_date.isoformat()
                        })
                    
                    # Check against stage deadline
                    if stage_deadline and substage_deadline > stage_deadline:
                        conflicts["substage_vs_stage"].append({
                            "stage_name": stage_name,
                            "substage_name": substage_name,
                            "substage_deadline": substage_deadline.isoformat(),
                            "stage_deadline": stage_deadline.isoformat()
                        })
                        
                except (ValueError, TypeError):
                    conflicts["invalid_formats"].append({
                        "type": "substage",
                        "stage_name": stage_name,
                        "name": substage_name,
                        "deadline": substage["deadline"]
                    })
    
    return conflicts

def display_deadline_conflicts(conflicts):
    """
    Display deadline conflicts in Streamlit UI
    """
    import streamlit as st
    
    if not any(conflicts.values()):
        return  # No conflicts to display
    
    st.error("⚠️ **Deadline Conflicts Detected:**")
    
    if conflicts["stage_vs_project"]:
        st.error("**Stages with deadlines after project due date:**")
        for conflict in conflicts["stage_vs_project"]:
            st.error(f"  • {conflict['stage_name']}: {conflict['stage_deadline']} (Project due: {conflict['project_due']})")
    
    if conflicts["substage_vs_project"]:
        st.error("**Substages with deadlines after project due date:**")
        for conflict in conflicts["substage_vs_project"]:
            st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Project due: {conflict['project_due']})")
    
    if conflicts["substage_vs_stage"]:
        st.error("**Substages with deadlines after their stage deadline:**")
        for conflict in conflicts["substage_vs_stage"]:
            st.error(f"  • {conflict['stage_name']} → {conflict['substage_name']}: {conflict['substage_deadline']} (Stage due: {conflict['stage_deadline']})")
    
    if conflicts["invalid_formats"]:
        st.error("**Invalid deadline formats:**")
        for conflict in conflicts["invalid_formats"]:
            if conflict["type"] == "stage":
                st.error(f"  • Stage {conflict['name']}: {conflict['deadline']}")
            else:
                st.error(f"  • {conflict['stage_name']} → {conflict['name']}: {conflict['deadline']}")


# Integration function for use in your existing validation
# FIXED FUNCTION: Enhanced validation that returns proper error list
def enhanced_validate_stage_substage_dates(stage_assignments, project_due_date, display_conflicts=True):
    """
    Enhanced validation that includes substage vs stage deadline checking
    Can optionally display conflicts in Streamlit UI
    
    Returns:
        list: list_of_error_messages (for backward compatibility)
    """
    # Use the existing validation function to get proper error messages
    errors = validate_stage_substage_dates(stage_assignments, project_due_date)
    
    # Get conflicts summary for display purposes
    conflicts = get_deadline_conflicts_summary(stage_assignments, project_due_date)
    
    # Display conflicts in UI if requested and there are errors
    if display_conflicts and errors:
        display_deadline_conflicts(conflicts)
    
    # Return just the errors list for backward compatibility
    return errors

# ALTERNATIVE: Enhanced version that returns tuple (if you want to update calling code)
def enhanced_validate_stage_substage_dates_detailed(stage_assignments, project_due_date, display_conflicts=True):
    """
    Enhanced validation that includes substage vs stage deadline checking
    Can optionally display conflicts in Streamlit UI
    
    Returns:
        tuple: (is_valid, list_of_errors, conflicts_summary)
    """
    errors = validate_stage_substage_dates(stage_assignments, project_due_date)
    conflicts = get_deadline_conflicts_summary(stage_assignments, project_due_date)
    
    if display_conflicts and errors:
        display_deadline_conflicts(conflicts)
    
    return len(errors) == 0, errors, conflicts

# UPDATED FUNCTION: Enhanced form state reset with substage completion clearing
def _reset_create_form_state():
    """Reset all create form state including stage assignments, substages, and completion data"""
    # Reset basic form fields
    if "selected_template" in st.session_state:
        st.session_state.selected_template = ""
    if "custom_levels" in st.session_state:
        st.session_state.custom_levels = []
    
    # Reset stage assignments and substages completely
    st.session_state.stage_assignments = {}
    
    # ENHANCED: Clear substage completion data
    if "substage_completion" in st.session_state:
        st.session_state.substage_completion = {}
    if "substage_timestamps" in st.session_state:
        st.session_state.substage_timestamps = {}
    
    # Reset any substage-related states
    substage_keys = [key for key in st.session_state.keys() if key.startswith("substage_")]
    for key in substage_keys:
        del st.session_state[key]
    
    # Reset any assignment-related states
    assignment_keys = [key for key in st.session_state.keys() if "assignment" in key.lower()]
    for key in assignment_keys:
        del st.session_state[key]
    
    # Reset any deadline-related states
    deadline_keys = [key for key in st.session_state.keys() if "deadline" in key.lower()]
    for key in deadline_keys:
        del st.session_state[key]
    
    # ENHANCED: Clear completion tracking states
    completion_keys = [key for key in st.session_state.keys() if "completion" in key.lower()]
    for key in completion_keys:
        del st.session_state[key]
    
    # Reset view tracking
    st.session_state.last_view = None

# UPDATED FUNCTION: Enhanced form initialization with substage completion defaults
def initialize_create_form_state():
    """Initialize create form state with all necessary defaults including substage completion"""
    # Initialize basic form state
    if "selected_template" not in st.session_state:
        st.session_state.selected_template = ""
    if "custom_levels" not in st.session_state:
        st.session_state.custom_levels = []
    if "stage_assignments" not in st.session_state:
        st.session_state.stage_assignments = {}
    
    # ENHANCED: Initialize substage completion tracking
    if "substage_completion" not in st.session_state:
        st.session_state.substage_completion = {}
    if "substage_timestamps" not in st.session_state:
        st.session_state.substage_timestamps = {}
    
    # Ensure clean state when switching to create view
    if st.session_state.get("last_view") != "create":
        _reset_create_form_state()
        st.session_state.last_view = "create"

# NEW FUNCTION: Clear substage completion data specifically
def clear_substage_completion_data():
    """Clear all substage completion data from session state"""
    # Clear completion tracking
    st.session_state.substage_completion = {}
    st.session_state.substage_timestamps = {}
    
    # Clear any completion-related session state keys
    completion_keys = [
        key for key in st.session_state.keys() 
        if any(term in key.lower() for term in ["substage_complete", "completion", "substage_check"])
    ]
    
    for key in completion_keys:
        if isinstance(st.session_state[key], dict):
            st.session_state[key].clear()
        else:
            del st.session_state[key]

# NEW FUNCTION: Initialize project with empty substage completion
def initialize_empty_project_substages(project_levels, stage_assignments):
    """Initialize a new project with empty substage completion data"""
    substage_completion = {}
    substage_timestamps = {}
    
    if stage_assignments:
        for stage_idx in range(len(project_levels)):
            stage_key = str(stage_idx)
            if stage_key in stage_assignments:
                substages = stage_assignments[stage_key].get("substages", [])
                if substages:
                    # Initialize all substages as incomplete
                    substage_completion[stage_key] = {}
                    substage_timestamps[stage_key] = {}
                    for substage_idx in range(len(substages)):
                        substage_completion[stage_key][str(substage_idx)] = False
                        substage_timestamps[stage_key][str(substage_idx)] = None
    
    return substage_completion, substage_timestamps

