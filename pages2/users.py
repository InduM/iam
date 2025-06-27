import streamlit as st
import pandas as pd
from datetime import date
from backend.users_backend import DatabaseManager, UserService, LogService, ProjectService, ProfileService
from utils.utils_users import SessionManager, DataUtils, ValidationUtils, UIHelpers


class UserInterface:
    """Main UI class for the users module"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.user_service = UserService(self.db_manager)
        self.log_service = LogService(self.db_manager)
        self.project_service = ProjectService(self.db_manager)
        self.profile_service = ProfileService(self.db_manager)
        
        # Initialize session state
        SessionManager.initialize_session()
    
    def display_profile_image(self, username, width=100):
        """Display user profile image with fallback to default"""
        profile_image_data = self.profile_service.get_profile_image(username)
        
        if profile_image_data:
            UIHelpers.display_profile_image(profile_image_data, width, width)
        else:
            # Use default image (admin's profile)
            default_image_data = self.profile_service.get_default_profile_image()
            if default_image_data:
                UIHelpers.display_profile_image(default_image_data, width, width)
            else:
                UIHelpers.display_profile_image(None, width, width)
    
    def show_profile(self, member_email):
        """Display individual member profile"""
        # Fetch fresh user data from MongoDB
        member = self.user_service.fetch_user_data(member_email)
        
        if not member:
            st.error("❌ User not found in database")
            SessionManager.go_back()
            st.rerun()
            return
        
        # Create back button and title
        col2 = UIHelpers.create_back_button()
        with col2:
            st.title(member["name"])
        
        # Display profile image
        self.display_profile_image(member["username"], width=100)
        
        if st.session_state.edit_mode:
            self._show_edit_form(member)
        else:
            self._show_profile_details(member)
    
    def _show_edit_form(self, member):
        """Show profile edit form"""
        with st.form("edit_form"):
            st.text_input("Name", value=member["name"], disabled=True)
            st.text_input("Email", value=member["email"], disabled=True)
            st.text_input("Role", value=member["role"], disabled=True)
            st.text_input("Branch", value=member["branch"], disabled=True)
            
            # Get all unique projects
            all_projects = self.user_service.get_all_projects()
            
            projects = st.multiselect(
                "Projects",
                options=all_projects,
                default=[p for p in member.get("project", []) if p in all_projects],
            )
            
            submitted = st.form_submit_button("💾 Save Projects")
            if submitted:
                self._handle_project_update(member, projects)
    
    def _handle_project_update(self, member, projects):
        """Handle project update logic"""
        # Get current projects before update to track changes
        current_projects = member.get("project", [])
        
        # Update member with new projects
        self.user_service.update_member(member["email"], {"project": projects})
        
        # Add user to newly assigned projects in projects table
        username = DataUtils.extract_username_from_email(member["email"])
        if username:
            # Find newly added projects
            new_projects = [proj for proj in projects if proj not in current_projects]
            
            # Add user to new projects
            if new_projects:
                self.project_service.add_user_to_projects(username, new_projects)
        
        st.success("✅ Projects updated successfully!")
        SessionManager.set_edit_mode(False)
        st.rerun()
    
    def _show_profile_details(self, member):
        """Show profile details in read-only mode"""
        st.markdown(f"**Email:** {member['email']}")
        st.markdown(f"**Role:** {member['position']}")
        st.markdown(f"**Branch:** {member['branch']}")
        
        # Display current projects
        projects = member.get("project", [])
        project_str = DataUtils.format_project_list(projects)
        st.write(f"**Current Projects:** {project_str}")
        
        # Display completed projects
        completed_raw = member.get("completed_projects", [])
        completed_projects = (
            [p for p in completed_raw if isinstance(p, str) and p.strip()]
            if isinstance(completed_raw, list)
            else []
        )
        completed_project_str = DataUtils.format_project_list(completed_projects)
        st.write(f"**Completed Projects:** {completed_project_str}")
        
        if st.button("✏️ Edit Profile"):
            SessionManager.set_edit_mode(True)
            st.rerun()
        
        # Show logs if user has permission
        if SessionManager.get_current_role() in ["manager", "admin"]:
            self._show_user_logs(member)
    
    def _show_user_logs(self, member):
        """Show user logs section"""
        st.subheader("📋 Daily Logs")
        
        # Date selector
        selected_log_date = st.date_input(
            "📅 Select a date to view logs", 
            value=date.today(), 
            key="log_view_date"
        )
        
        # Validate email and extract username
        email = member.get("email", "")
        if not ValidationUtils.is_valid_email(email):
            st.warning("⚠️ Cannot retrieve logs: Invalid email format.")
            return
        
        query_username = DataUtils.extract_username_from_email(email)
        if not query_username:
            st.warning("⚠️ Cannot retrieve logs: Unable to extract username.")
            return
        
        # Query logs for selected member on that date
        query_date_str = selected_log_date.strftime("%Y-%m-%d")
        logs = self.log_service.fetch_user_logs(query_username, query_date_str)
        
        if logs:
            df_logs = pd.DataFrame(logs)
            st.dataframe(df_logs, use_container_width=True, hide_index=True)
        else:
            st.info("📝 No logs found for this date.")
        
        # Add refresh button for logs
        UIHelpers.create_refresh_button("🔄 Refresh Logs", "refresh_logs")
    
    def show_team(self):
        """Display team overview page"""
        team_data = self.user_service.load_team_data()
        current_role = SessionManager.get_current_role()
        
        # Filter team data based on role
        team_data = DataUtils.filter_team_by_role(team_data, current_role)
        df = pd.DataFrame(team_data)
        
        if df.empty:
            st.info("👥 No team members found.")
            return
        
        # Add refresh button for team data
        col_refresh, col_spacer = st.columns([1, 4])
        with col_refresh:
            UIHelpers.create_refresh_button("🔄 Refresh Team Data")
        
        # Create filter controls
        branch_filter, project_filter, search_query = UIHelpers.create_filter_controls(df)
        
        # Apply filters
        filtered = DataUtils.apply_filters(df, branch_filter, project_filter, search_query)
        
        if filtered.empty:
            st.info("🔍 No team members match the current filters.")
            return
        
        # Display team members
        self._display_team_grid(filtered)
    
    def _display_team_grid(self, filtered_df):
        """Display team members in a grid layout"""
        num_columns = 2  # Adjust for more per row if needed
        rows = DataUtils.chunk_dataframe(filtered_df, num_columns)
        
        for row_chunk in rows:
            cols = st.columns(num_columns)
            for idx, (_, member) in enumerate(row_chunk.iterrows()):
                if idx < len(cols):  # Safety check
                    with cols[idx]:
                        self.display_profile_image(member["username"], width=100)
                        name = ValidationUtils.sanitize_string(member.get("name", "Unnamed"))
                        email = ValidationUtils.sanitize_string(member.get("email", f"key_{name}"))
                        
                        if st.button(name, key=email):
                            SessionManager.select_member(email)
                            st.rerun()
    
    def render(self):
        """Main render method - entry point for the module"""
        if st.session_state.selected_member_email:
            self.show_profile(st.session_state.selected_member_email)
        else:
            self.show_team()


def run():
    """Main function to run the users module"""
    ui = UserInterface()
    ui.render()