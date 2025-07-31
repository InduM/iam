"""
Profile management module for Streamlit application.
Handles user profile display, editing, and project details viewing.
"""

import streamlit as st
from pymongo import MongoClient
import time
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Dict, List, Tuple, Any

# Local imports
from utils.utils_login import is_logged_in
from backend.profile_backend import *
from backend.projects_backend import get_project_by_name
from utils.utils_profile import (
    decode_base64_image, calculate_project_progress,
    get_project_status, format_date, get_current_stage_info,
    get_substage_completion_status, get_substage_timestamp
)

# Constants
CSS_STYLES = """
<style>
.sidebar .sidebar-content {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid #ddd;
    padding: 10px 20px;
    margin: 5px;
    transition: all 0.3s ease;
}

.stButton > button:hover {
    background-color: #f0f2f6;
    border-color: #1f77b4;
}
</style>
"""

PRIORITY_COLORS = {
    'High': "🔴",
    'Medium': "🟡",
    'Low': "🟢"
}


# Context Managers and Utilities
@contextmanager
def loading_state(message: str = "Loading...", success_message: Optional[str] = None):
    """Context manager for showing loading spinners with optional success message."""
    try:
        with st.spinner(message):
            yield
        if success_message:
            st.success(success_message)
    except Exception as e:
        st.error(f"Error: {str(e)}")
        raise


class DatabaseManager:
    """Handles database operations for profile and project management."""
    
    @staticmethod
    def get_mongo_client() -> MongoClient:
        """Get MongoDB client connection."""
        return MongoClient(st.secrets["MONGO_URI"])
    
    @staticmethod
    def update_project_stage(project_name: str, new_stage: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update project stage in MongoDB Atlas.
        
        Args:
            project_name: Name of the project to update
            new_stage: New stage information containing stage_key, stage_name, etc.
        
        Returns:
            Result dictionary with success status and details
        """
        try:
            client = DatabaseManager.get_mongo_client()
            db = client['user_db']
            collection = db['logs']
            
            # Process new_stage parameter
            if isinstance(new_stage, int):
                if new_stage not in stage_mappings:
                    return DatabaseManager._create_error_response(
                        f"Invalid stage index: {new_stage}. Valid stages: {list(stage_mappings.keys())}",
                        project_name
                    )
                stage_info = stage_mappings[new_stage]
            elif isinstance(new_stage, dict):
                stage_info = new_stage
                if "stage_key" not in stage_info or "stage_name" not in stage_info:
                    return DatabaseManager._create_error_response(
                        "Stage dict must contain 'stage_key' and 'stage_name'",
                        project_name
                    )
            else:
                return DatabaseManager._create_error_response(
                    "new_stage must be an integer or dictionary",
                    project_name
                )
            
            # Prepare update fields
            update_fields = DatabaseManager._prepare_stage_update_fields(stage_info)
            
            # Perform the update
            result = collection.update_many(
                {"project_name": project_name},
                {"$set": update_fields}
            )
            
            client.close()
            
            return {
                "success": result.modified_count > 0,
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "project_name": project_name,
                "new_stage_key": stage_info["stage_key"],
                "new_stage_name": stage_info["stage_name"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return DatabaseManager._create_error_response(str(e), project_name)
    
    @staticmethod
    def update_substage_completion(project_name: str, stage_idx: int, 
                                 substage_idx: int, completed: bool = True) -> Dict[str, Any]:
        """
        Update substage completion status in MongoDB Atlas.
        
        Args:
            project_name: Name of the project
            stage_idx: Stage index (0-based)
            substage_idx: Substage index (0-based)
            completed: Completion status
        
        Returns:
            Result dictionary with success status and details
        """
        try:
            client = DatabaseManager.get_mongo_client()
            db = client['user_db']
            collection = db['logs']
            
            update_fields = {
                "is_completed": completed,
                "status": "Completed" if completed else "In Progress",
                "updated_at": datetime.now(),
                "completed_at": datetime.now() if completed else None
            }
            
            query = {
                "project_name": project_name,
                "stage_key": str(stage_idx),
                "$or": [
                    {"substage_id": {"$regex": f"^substage_{stage_idx}_{substage_idx}_"}},
                    {"substage_name": {"$exists": True}}
                ]
            }
            
            result = collection.update_one(query, {"$set": update_fields})
            client.close()
            
            return {
                "success": result.modified_count > 0,
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "project_name": project_name,
                "stage_idx": stage_idx,
                "substage_idx": substage_idx,
                "completed": completed,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "project_name": project_name,
                "stage_idx": stage_idx,
                "substage_idx": substage_idx
            }
    
    @staticmethod
    def _prepare_stage_update_fields(stage_info: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare update fields for stage update."""
        update_fields = {
            "stage_key": stage_info["stage_key"],
            "stage_name": stage_info["stage_name"],
            "updated_at": datetime.now(),
            "substage_id": None,
            "substage_name": None,
            "substage_deadline": None,
            "is_completed": False,
            "status": "In Progress",
            "completed_at": None
        }
        
        if "stage_deadline" in stage_info:
            deadline = stage_info["stage_deadline"]
            if isinstance(deadline, str):
                try:
                    update_fields["stage_deadline"] = datetime.fromisoformat(deadline)
                except ValueError:
                    update_fields["stage_deadline"] = deadline
            else:
                update_fields["stage_deadline"] = deadline
        
        return update_fields
    
    @staticmethod
    def _create_error_response(error_message: str, project_name: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "success": False,
            "error": error_message,
            "project_name": project_name
        }


class ProjectDetailsManager:
    """Manages project details display and interactions."""
    
    def __init__(self):
        self.project_data = None
        self.selected_project = None
    
    def display_project_details(self):
        """Main method to display project details with custom data structure support."""
        if not self._handle_navigation_and_validation():
            return
        
        self.project_data = self._get_project_data()
        if not self.project_data:
            return
        
        self._display_all_sections()
    
    def _handle_navigation_and_validation(self) -> bool:
        """Handle back button navigation and project selection validation."""
        if st.button("⬅️ Back to Profile", key="back_to_profile"):
            st.session_state.selected_project = None
            st.session_state.show_project_details = False
            st.rerun()
        
        self.selected_project = st.session_state.get("selected_project", None)
        if not self.selected_project:
            st.error("No project selected.")
            st.stop()
            return False
        
        return True
    
    def _get_project_data(self) -> Optional[Dict[str, Any]]:
        """Fetch and validate project data."""
        with loading_state("Loading project details..."):
            project_data = get_project_by_name(self.selected_project)
        
        if not project_data:
            st.error("Project details not found.")
            st.stop()
            return None
        
        return project_data
    
    def _display_all_sections(self):
        """Display all project sections."""
        self._display_project_header()
        self._display_project_info()
        self._display_project_stages()
        self._display_team_summary()
        self._display_project_statistics()
    
    def _display_project_header(self):
        """Display project header with status and progress."""
        st.markdown("---")
        
        col_header, col_status, col_progress = st.columns([2, 1, 1])
        
        with col_header:
            st.subheader(f"📌 {self.project_data.get('name', 'Unnamed Project')}")
            if self.project_data.get('client'):
                st.markdown(f"**Client:** {self.project_data.get('client')}")
        
        with col_status:
            status_text, status_emoji = get_project_status(self.project_data)
            st.markdown(f"**Status:** {status_emoji} {status_text}")
            
            stage_info, stage_emoji = get_current_stage_info(self.project_data)
            st.markdown(f"**{stage_emoji} {stage_info}**")
        
        with col_progress:
            progress = calculate_project_progress(self.project_data)
            st.markdown(f"**📊 Progress:** {progress}%")
            st.progress(progress / 100)
    
    def _display_project_info(self):
        """Display basic project information in two columns."""
        col1, col2 = st.columns(2)
        
        with col1:
            self._display_project_description()
            self._display_project_metadata()
        
        with col2:
            self._display_project_timeline()
    
    def _display_project_description(self):
        """Display project description and template info."""
        st.markdown("**📝 Description:**")
        description = self.project_data.get('description', 'No description available.')
        st.write(description if description.strip() else "No description available.")
        
        if self.project_data.get('template'):
            st.markdown(f"**📋 Template:** {self.project_data.get('template')}")
    
    def _display_project_metadata(self):
        """Display project metadata like creator and timestamps."""
        if self.project_data.get('created_by'):
            st.markdown(f"**👤 Created by:** {self.project_data.get('created_by')}")
        
        if self.project_data.get('created_at'):
            created_at = self._parse_datetime(self.project_data.get('created_at'))
            if created_at:
                st.markdown(f"**📅 Created:** {created_at.strftime('%B %d, %Y at %I:%M %p')}")
    
    def _display_project_timeline(self):
        """Display project timeline and duration calculations."""
        st.markdown("**📅 Timeline:**")
        start_date = format_date(self.project_data.get('startDate'))
        due_date = format_date(self.project_data.get('dueDate'))
        
        st.write(f"**Start Date:** {start_date}")
        st.write(f"**Due Date:** {due_date}")
        
        self._display_duration_info()
        
        if self.project_data.get('updated_at'):
            updated_at = self._parse_datetime(self.project_data.get('updated_at'))
            if updated_at:
                st.markdown(f"**🔄 Last Updated:** {updated_at.strftime('%B %d, %Y at %I:%M %p')}")
    
    def _display_duration_info(self):
        """Calculate and display project duration and remaining days."""
        start_date_str = self.project_data.get('startDate')
        due_date_str = self.project_data.get('dueDate')
        
        if not (start_date_str and due_date_str):
            return
        
        try:
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(due_date_str, '%Y-%m-%d')
            duration = (end - start).days
            st.write(f"**Duration:** {duration} days")
            
            days_remaining = (end - datetime.now()).days
            if days_remaining > 0:
                st.write(f"**Days Remaining:** {days_remaining}")
            elif days_remaining == 0:
                st.write("**Due Today!** 🔥")
            else:
                st.write(f"**Overdue by:** {abs(days_remaining)} days ⚠️")
        except ValueError:
            pass
    
    def _display_project_stages(self):
        """Display project stages with filtering and search capabilities."""
        if not self.project_data.get('levels'):
            return
        
        st.markdown("---")
        st.markdown("**📋 Project Stages:**")
        
        stage_filter, search_term = self._display_stage_filters()
        stages_to_display = self._filter_stages(stage_filter, search_term)
        self._display_filtered_stages(stages_to_display)
    
    def _display_stage_filters(self) -> Tuple[str, str]:
        """Display stage filtering controls."""
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            stage_filter = st.selectbox(
                "Filter by Stage Status:",
                ["All Stages", "Completed", "Current", "Upcoming"],
                key="stage_filter"
            )
        
        with col_filter2:
            search_term = st.text_input(
                "Search in stages/substages:",
                placeholder="Search by name or description...",
                key="stage_search"
            )
        
        return stage_filter, search_term
    
    def _filter_stages(self, stage_filter: str, search_term: str) -> List[int]:
        """Filter stages based on status and search criteria."""
        levels = self.project_data.get('levels', [])
        current_level = self.project_data.get('level', -1)
        stage_assignments = self.project_data.get('stage_assignments', {})
        
        stages_to_display = []
        
        for i, level_name in enumerate(levels):
            if not self._stage_matches_filter(i, current_level, stage_filter):
                continue
            
            if search_term and not self._stage_matches_search(i, level_name, stage_assignments, search_term):
                continue
            
            stages_to_display.append(i)
        
        return stages_to_display
    
    def _stage_matches_filter(self, stage_index: int, current_level: int, stage_filter: str) -> bool:
        """Check if stage matches the selected filter."""
        filter_mappings = {
            "All Stages": lambda: True,
            "Completed": lambda: stage_index < current_level,
            "Current": lambda: stage_index == current_level,
            "Upcoming": lambda: stage_index > current_level
        }
        return filter_mappings.get(stage_filter, lambda: False)()
    
    def _stage_matches_search(self, stage_index: int, level_name: str, 
                            stage_assignments: Dict, search_term: str) -> bool:
        """Check if stage matches the search term."""
        stage_info = stage_assignments.get(str(stage_index), {})
        stage_name = stage_info.get('stage_name', level_name)
        substages = stage_info.get('substages', [])
        
        search_lower = search_term.lower()
        stage_matches = search_lower in stage_name.lower()
        substage_matches = any(
            search_lower in substage.get('name', '').lower() or 
            search_lower in substage.get('description', '').lower()
            for substage in substages
        )
        
        return stage_matches or substage_matches
    
    def _display_filtered_stages(self, stages_to_display: List[int]):
        """Display the filtered list of stages."""
        if not stages_to_display:
            st.info("No stages match the current filter criteria.")
            return
        
        levels = self.project_data.get('levels', [])
        current_level = self.project_data.get('level', -1)
        
        for i in stages_to_display:
            self._display_single_stage(i, levels[i], current_level)
    
    def _display_single_stage(self, stage_index: int, level_name: str, current_level: int):
        """Display a single stage with all its details."""
        status_icon = self._get_stage_status_icon(stage_index, current_level)
        
        stage_assignments = self.project_data.get('stage_assignments', {})
        stage_info = stage_assignments.get(str(stage_index), {})
        stage_name = stage_info.get('stage_name', level_name)
        
        with st.expander(f"{status_icon} Stage {stage_index+1}: {stage_name}", 
                        expanded=(stage_index == current_level)):
            self._display_stage_details(stage_index, stage_info, current_level)
    
    def _get_stage_status_icon(self, stage_index: int, current_level: int) -> str:
        """Get the appropriate status icon for a stage."""
        if stage_index < current_level:
            return "✅"
        elif stage_index == current_level:
            return "🔄"
        else:
            return "⏳"
    
    def _display_stage_details(self, stage_index: int, stage_info: Dict, current_level: int):
        """Display detailed information for a single stage."""
        self._display_stage_basic_info(stage_info)
        self._display_stage_timestamp(stage_index)
        
        substages = stage_info.get('substages', [])
        if substages:
            self._display_substage_progress(stage_index, substages)
            self._display_substages(stage_index, substages, current_level)
    
    def _display_stage_basic_info(self, stage_info: Dict):
        """Display basic stage information like members and deadline."""
        col_stage1, col_stage2 = st.columns(2)
        
        with col_stage1:
            members = stage_info.get('members', [])
            members_text = ', '.join(members) if members else "Not assigned"
            st.write(f"**👥 Assigned to:** {members_text}")
        
        with col_stage2:
            deadline = stage_info.get('deadline', '')
            deadline_text = format_date(deadline) if deadline else "Not set"
            st.write(f"**📅 Deadline:** {deadline_text}")
    
    def _display_stage_timestamp(self, stage_index: int):
        """Display stage completion timestamp if available."""
        stage_timestamp = self.project_data.get('timestamps', {}).get(str(stage_index), None)
        if stage_timestamp:
            st.write(f"**⏰ Stage Completed:** {stage_timestamp}")
    
    def _display_substage_progress(self, stage_index: int, substages: List[Dict]):
        """Display overall substage progress for a stage."""
        completed_count = sum(1 for k in range(len(substages)) 
                            if get_substage_completion_status(self.project_data, stage_index, k))
        total_count = len(substages)
        substage_progress = (completed_count / total_count) * 100 if total_count > 0 else 0
        
        st.write(f"**📊 Substage Progress:** {completed_count}/{total_count} ({substage_progress:.0f}%)")
        st.progress(substage_progress / 100)
    
    def _display_substages(self, stage_index: int, substages: List[Dict], current_level: int):
        """Display all substages for a stage."""
        st.write("**📝 Substages:**")
        
        for j, substage in enumerate(substages):
            self._display_single_substage(stage_index, j, substage, current_level)
    
    def _display_single_substage(self, stage_index: int, substage_index: int, 
                               substage: Dict, current_level: int):
        """Display a single substage with all its details."""
        is_completed = get_substage_completion_status(self.project_data, stage_index, substage_index)
        completion_timestamp = get_substage_timestamp(self.project_data, stage_index, substage_index)
        
        substage_icon = "✅" if is_completed else "⏳"
        priority_color = PRIORITY_COLORS.get(substage.get('priority', 'Medium'), "🟡")
        
        st.markdown(f"{substage_icon} **{substage.get('name', 'Unnamed Substage')}**")
        st.markdown(f" 📝 {substage.get('description', 'No description')}")
        
        self._display_substage_details(substage, priority_color)
        
        if completion_timestamp:
            st.markdown(f"✅ **Completed:** {completion_timestamp}")
        
        if stage_index == current_level:
            self._display_substage_toggle(stage_index, substage_index, is_completed)
        
        st.markdown("---")
    
    def _display_substage_details(self, substage: Dict, priority_color: str):
        """Display substage assignees, deadlines, and priority."""
        col_sub1, col_sub2 = st.columns(2)
        
        with col_sub1:
            assignees = substage.get('assignees', [])
            if assignees:
                st.markdown(f"👤 **Assignees:** {', '.join(assignees)}")
            
            substage_deadline = substage.get('deadline', '')
            if substage_deadline:
                formatted_sub_deadline = format_date(substage_deadline)
                st.markdown(f"📅 **Deadline:** {formatted_sub_deadline}")
        
        with col_sub2:
            priority = substage.get('priority', 'Medium')
            st.markdown(f"{priority_color} **Priority:** {priority}")
            
            start_date = substage.get('start_date', '')
            if start_date:
                formatted_start = format_date(start_date)
                st.markdown(f"📅 **Start:** {formatted_start}")
    
    def _display_substage_toggle(self, stage_index: int, substage_index: int, is_completed: bool):
        """Display substage completion toggle button."""
        col_toggle, col_space = st.columns([1, 3])
        with col_toggle:
            button_text = "↩️ Undo" if is_completed else "✅ Complete"
            if st.button(button_text, key=f"toggle_substage_{stage_index}_{substage_index}", 
                        type="secondary"):
                with loading_state("Updating substage status..."):
                    success = DatabaseManager.update_substage_completion(
                        self.selected_project, stage_index, substage_index, not is_completed
                    )
                    if success:
                        st.success("Substage updated successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to update substage!")
    
    def _display_team_summary(self):
        """Display team members summary."""
        if not self.project_data.get('stage_assignments'):
            return
        
        st.markdown("---")
        st.markdown("**👥 Team Members:**")
        
        member_stages = self._collect_team_members()
        
        for member in sorted(member_stages.keys()):
            stages = member_stages[member]
            st.write(f"👤 **{member}** - Assigned to: {', '.join(stages)}")
    
    def _collect_team_members(self) -> Dict[str, List[str]]:
        """Collect all team members and their stage assignments."""
        member_stages = {}
        
        for stage_idx, stage_info in self.project_data.get('stage_assignments', {}).items():
            stage_name = stage_info.get('stage_name', f"Stage {stage_idx}")
            
            # Add stage members
            for member in stage_info.get('members', []):
                if member not in member_stages:
                    member_stages[member] = []
                member_stages[member].append(stage_name)
            
            # Add substage assignees
            for substage in stage_info.get('substages', []):
                for assignee in substage.get('assignees', []):
                    if assignee not in member_stages:
                        member_stages[assignee] = []
                    if stage_name not in member_stages[assignee]:
                        member_stages[assignee].append(stage_name)
        
        return member_stages
    
    def _display_project_statistics(self):
        """Display project statistics in metric cards."""
        st.markdown("---")
        st.markdown("**📊 Project Statistics:**")
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            total_stages = len(self.project_data.get('levels', []))
            st.metric("Total Stages", total_stages)
        
        with col_stat2:
            current_stage = self.project_data.get('level', -1) + 1
            total_stages = len(self.project_data.get('levels', []))
            st.metric("Current Stage", f"{current_stage}/{total_stages}")
        
        with col_stat3:
            completed, total = self._calculate_substage_stats()
            st.metric("Substages Completed", f"{completed}/{total}")
        
        with col_stat4:
            days_elapsed = self._calculate_days_elapsed()
            st.metric("Days Elapsed", days_elapsed)
    
    def _calculate_substage_stats(self) -> Tuple[int, int]:
        """Calculate total and completed substages."""
        total_substages = 0
        completed_substages = 0
        
        for stage_idx, stage_info in self.project_data.get('stage_assignments', {}).items():
            substages = stage_info.get('substages', [])
            total_substages += len(substages)
            
            completion_data = self.project_data.get('substage_completion', {}).get(stage_idx, {})
            completed_substages += sum(1 for completed in completion_data.values() if completed)
        
        return completed_substages, total_substages
    
    def _calculate_days_elapsed(self) -> str:
        """Calculate days elapsed since project start."""
        if not self.project_data.get('startDate'):
            return "N/A"
        
        try:
            start_date = datetime.strptime(self.project_data.get('startDate'), '%Y-%m-%d')
            days_elapsed = (datetime.now() - start_date).days
            return str(days_elapsed)
        except ValueError:
            return "N/A"
    
    @staticmethod
    def _parse_datetime(date_string: str) -> Optional[datetime]:
        """Parse datetime string safely."""
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None


class ProfileManager:
    """Manages user profile display and editing functionality."""
    
    @staticmethod
    def edit_profile(profile: Dict[str, Any]):
        """Display profile editing interface."""
        st.subheader("✏️ Edit Profile")
        name = st.text_input("Name", value=profile["name"])
        email = st.text_input("Email", value=profile["email"])
        branch = st.text_input("Branch", value=profile["branch"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Changes"):
                updated = {
                    "username": profile["username"],
                    "name": name,
                    "email": email,
                    "branch": branch,
                }
                update_user_profile(profile["username"], updated)
                st.success("✅ Profile updated!")
                st.session_state.edit_mode = False
                st.rerun()
        
        with col2:
            if st.button("❌ Cancel"):
                st.session_state.edit_mode = False
                st.rerun()
    
    @staticmethod
    def display_profile(user_profile: Dict[str, Any]):
        """Display user profile with projects."""
        ProfileManager._display_profile_image()
        ProfileManager._display_profile_info(user_profile)
        ProfileManager._display_projects(user_profile)
    
    @staticmethod
    def _display_profile_image():
        """Display user profile image."""
        col1, col2, col3 = st.columns(3)
        with col2:
            image_data = decode_base64_image(get_profile_image(st.session_state["username"]))
            if not image_data:
                image_data = decode_base64_image(get_profile_image("admin"))
            if image_data:
                st.image(image_data, use_container_width=False, width=200)
    
    @staticmethod
    def _display_profile_info(user_profile: Dict[str, Any]):
        """Display user profile information."""
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Name:** {user_profile.get('name', 'N/A')}")
            st.write(f"**Email:** {user_profile.get('email', 'N/A')}")
            st.write(f"**Branch:** {user_profile.get('branch', 'N/A')}")
        
        with col2:
            st.write(f"**Role:** {user_profile.get('position', 'N/A')}")
            st.write(f"**Date of Joining:** {user_profile.get('DOJ', 'N/A')}")
    
    @staticmethod
    def _display_projects(user_profile: Dict[str, Any]):
        """Display user's assigned projects."""
        st.markdown("---")
        st.markdown("### Current Projects")
        
        projects = user_profile.get("project", [])
        if isinstance(projects, list) and projects:
            # Display projects in a grid layout
            cols = st.columns(min(len(projects), 3))  # Max 3 columns
            for i, project in enumerate(projects):
                with cols[i % 3]:
                    if st.button(f"📂 {project}", key=f"project_btn_{project}", use_container_width=True):
                        st.session_state.selected_project = project
                        st.session_state.show_project_details = True
                        st.rerun()
        else:
            st.info("No projects assigned currently.")


class SessionManager:
    """Manages Streamlit session state."""
    
    @staticmethod
    def initialize_session_state():
        """Initialize required session state variables."""
        session_vars = {
            "show_project_details": False,
            "selected_project": None,
            "edit_mode": False
        }
        
        for var, default_value in session_vars.items():
            if var not in st.session_state:
                st.session_state[var] = default_value
    
    @staticmethod
    def check_authentication():
        """Check if user is logged in and redirect if not."""
        if not is_logged_in():
            st.switch_page("option.py")


class UIManager:
    """Manages UI styling and layout."""
    
    @staticmethod
    def apply_custom_styles():
        """Apply custom CSS styles to the application."""
        st.markdown(CSS_STYLES, unsafe_allow_html=True)


def run():
    """Main function to run the profile application."""
    # Apply custom styles
    UIManager.apply_custom_styles()
    
    # Check authentication
    SessionManager.check_authentication()
    
    # Initialize session state
    SessionManager.initialize_session_state()
    
    # Get user profile
    user_profile = get_user_profile(st.session_state["username"])
    
    if not user_profile:
        st.error("User profile not found.")
        return
    
    # Navigation logic
    if st.session_state.show_project_details:
        # Show project details page
        project_manager = ProjectDetailsManager()
        project_manager.display_project_details()
    else:
        # Show profile page        
        if st.session_state.get("edit_mode", False):
            ProfileManager.edit_profile(user_profile)
        else:
            ProfileManager.display_profile(user_profile)
            
            # Update profile button
            st.markdown("---")
            if st.button("Update Profile", type="primary"):
                st.session_state.edit_mode = True
                st.rerun()