import streamlit as st
import pandas as pd
from datetime import date
from backend.users_backend import DatabaseManager, UserService, LogService, ProjectService, ProfileService
from utils.utils_users import SessionManager, DataUtils, ValidationUtils, UIHelpers

# Inject global CSS for nicer visuals
st.markdown("""
<style>
/* Card hover effect */
.member-card:hover {
    background-color: #f1f3f6;
    transform: scale(1.02);
    transition: all 0.2s ease-in-out;
}

/* Rounded images */
img.profile-pic {
    border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
}

/* Buttons */
div.stButton > button:hover {
    background-color: #17a2b8;
    color: white;
    transform: scale(1.05);
}
</style>
""", unsafe_allow_html=True)

class UserInterface:
    """Main UI class for the users module"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.user_service = UserService(self.db_manager)
        self.log_service = LogService(self.db_manager)
        self.project_service = ProjectService(self.db_manager)
        self.profile_service = ProfileService(self.db_manager)
        SessionManager.initialize_session()

    def sync_user_project_assignment(self, username, project_name, action="add"):
        try:
            user_email = self._get_user_email_from_username(username)
            user_data = self.user_service.fetch_user_data(user_email)
            if not user_data:
                st.warning(f"User {username} not found in database")
                return False
            current_projects = user_data.get("project", [])
            if action == "add" and project_name not in current_projects:
                current_projects.append(project_name)
                self.user_service.update_member(user_email, {"project": current_projects})
                return True
            elif action == "remove" and project_name in current_projects:
                current_projects.remove(project_name)
                self.user_service.update_member(user_email, {"project": current_projects})
                return True
            return False
        except Exception as e:
            st.error(f"Error syncing user project assignment: {str(e)}")
            return False

    def bulk_sync_project_assignments(self, project_name, stage_assignments):
        try:
            assigned_users = set()
            for stage_name, assignment_data in stage_assignments.items():
                if isinstance(assignment_data, dict):
                    main_assignee = assignment_data.get("assigned_to", "")
                    if main_assignee:
                        assigned_users.add(main_assignee)
                    substages = assignment_data.get("substages", {})
                    for _, substage_data in substages.items():
                        if isinstance(substage_data, dict):
                            substage_assignee = substage_data.get("assigned_to", "")
                            if substage_assignee:
                                assigned_users.add(substage_assignee)
            success_count = 0
            for username in assigned_users:
                if self.sync_user_project_assignment(username, project_name, "add"):
                    success_count += 1
            return success_count
        except Exception as e:
            st.error(f"Error in bulk sync project assignments: {str(e)}")
            return 0

    def _get_user_email_from_username(self, username):
        if "@" in username:
            return username
        possible_patterns = [f"{username}@v-shesh.com", f"{username}@company.com"]
        for email_pattern in possible_patterns:
            user_data = self.user_service.fetch_user_data(email_pattern)
            if user_data:
                return email_pattern
        return f"{username}@v-shesh.com"

    def display_profile_image(self, username, width=100):
        profile_image_data = self.profile_service.get_profile_image(username)
        if profile_image_data:
            UIHelpers.display_profile_image(profile_image_data, width, width)
        else:
            default_image_data = self.profile_service.get_default_profile_image()
            UIHelpers.display_profile_image(default_image_data, width, width)

    def show_profile(self, member_email):
        member = self.user_service.fetch_user_data(member_email)
        if not member:
            st.error("❌ User not found in database")
            SessionManager.go_back()
            st.rerun()
            return
        col2 = UIHelpers.create_back_button()
        with col2:
            st.title(member["name"])
        self.display_profile_image(member["username"], width=120)
        if st.session_state.edit_mode:
            self._show_edit_form(member)
        else:
            self._show_profile_details(member)

    def _show_edit_form(self, member):
        with st.form("edit_form"):
            st.text_input("👤 Name", value=member["name"], disabled=True)
            st.text_input("📧 Email", value=member["email"], disabled=True)
            st.text_input("🛠 Role", value=member["role"], disabled=True)
            st.text_input("🏢 Branch", value=member["branch"], disabled=True)
            all_projects = self.user_service.get_all_projects()
            projects = st.multiselect(
                "📂 Projects",
                options=all_projects,
                default=[p for p in member.get("project", []) if p in all_projects],
            )
            submitted = st.form_submit_button("💾 Save Projects")
            if submitted:
                self._handle_project_update(member, projects)

    def _handle_project_update(self, member, projects):
        current_projects = member.get("project", [])
        self.user_service.update_member(member["email"], {"project": projects})
        username = DataUtils.extract_username_from_email(member["email"])
        if username:
            new_projects = [proj for proj in projects if proj not in current_projects]
            if new_projects:
                self.project_service.add_user_to_projects(username, new_projects)
        st.success("✅ Projects updated successfully!")
        SessionManager.set_edit_mode(False)
        st.rerun()

    def _show_profile_details(self, member):
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; background-color:#f8f9fa;">
            <h3 style="margin-bottom:5px;">{member['name']}</h3>
            <p><b>Email:</b> {member['email']}</p>
            <p><b>Role:</b> <span style="background:#17a2b8; color:white; padding:3px 6px; border-radius:5px;">{member['role']}</span></p>
            <p><b>Branch:</b> <span style="background:#28a745; color:white; padding:3px 6px; border-radius:5px;">{member['branch']}</span></p>
            <p><b>Projects:</b> {DataUtils.format_project_list(member.get('project', []))}</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✏️ Edit Profile"):
            SessionManager.set_edit_mode(True)
            st.rerun()

    def show_team(self):
        team_data = self.user_service.load_team_data()
        current_role = SessionManager.get_current_role()
        team_data = DataUtils.filter_team_by_role(team_data, current_role)
        df = pd.DataFrame(team_data)
        if df.empty:
            st.info("👥 No team members found.")
            return
        col_refresh, _ = st.columns([1, 4])
        with col_refresh:
            UIHelpers.create_refresh_button("🔄 Refresh")
        branch_filter, project_filter, search_query = UIHelpers.create_filter_controls(df)
        filtered = DataUtils.apply_filters(df, branch_filter, project_filter, search_query)
        if filtered.empty:
            st.info("🔍 No team members match the current filters.")
            return
        self._display_team_grid(filtered)

    def _display_team_grid(self, filtered_df):
        num_columns = 3
        rows = DataUtils.chunk_dataframe(filtered_df, num_columns)
        for row_chunk in rows:
            cols = st.columns(num_columns)
            for idx, (_, member) in enumerate(row_chunk.iterrows()):
                if idx < len(cols):
                    with cols[idx]:
                        st.markdown("<div class='member-card' style='padding:10px; border-radius:10px;'>", unsafe_allow_html=True)
                        self.display_profile_image(member["username"], width=80)
                        st.markdown(f"**{ValidationUtils.sanitize_string(member.get('name', 'Unnamed'))}**")
                        st.caption(f"{member.get('role', 'Unknown')} | {member.get('branch', 'Unknown')}")
                        if st.button("View Profile", key=member.get("email", f"key_{idx}")):
                            SessionManager.select_member(member["email"])
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

    def render(self):
        if st.session_state.selected_member_email:
            self.show_profile(st.session_state.selected_member_email)
        else:
            self.show_team()

def run():
    ui = UserInterface()
    ui.render()
