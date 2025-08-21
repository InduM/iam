import streamlit as st

class SessionManager:
    """Manage session state variables"""
    
    @staticmethod
    def initialize_session():
        """Initialize session state variables"""
        if "selected_member_email" not in st.session_state:
            st.session_state.selected_member_email = None
        if "edit_mode" not in st.session_state:
            st.session_state.edit_mode = False
    
    @staticmethod
    def go_back():
        """Reset session state for navigation"""
        st.session_state.selected_member_email = None
        st.session_state.edit_mode = False
    
    @staticmethod
    def set_edit_mode(mode=True):
        """Set edit mode state"""
        st.session_state.edit_mode = mode
    
    @staticmethod
    def select_member(email):
        """Select a member by email"""
        st.session_state.selected_member_email = email
    
    @staticmethod
    def get_current_role():
        """Get current user role from session"""
        return st.session_state.get("role")


class DataUtils:
    """Utility functions for data processing"""
    
    @staticmethod
    def normalize_projects(projects):
        """Normalize project data to ensure it's always a list"""
        if isinstance(projects, list):
            return projects
        elif isinstance(projects, str):
            return [projects]
        else:
            return []
    
    @staticmethod
    def extract_username_from_email(email):
        """Extract username from email address"""
        if not isinstance(email, str) or "@" not in email:
            return None
        return email.split("@")[0]
    
    @staticmethod
    def format_project_list(projects):
        """Format project list for display"""
        if isinstance(projects, list):
            return ", ".join(projects) if projects else "None"
        else:
            return projects if projects else "None"
    
    @staticmethod
    def filter_team_by_role(team_data, current_role):
        """Filter team data based on current user role"""
        if current_role == "manager":
            return [member for member in team_data if member.get("role") != "admin"]
        return team_data
    
    @staticmethod
    def apply_filters(df, branch_filter, project_filter, search_query):
        """Apply filters to team dataframe"""
        filtered = df.copy()
        
        if branch_filter != "All":
            filtered = filtered[filtered["branch"] == branch_filter]
        
        if project_filter != "All":
            filtered = filtered[
                filtered["project"].apply(
                    lambda projs: isinstance(projs, list) and project_filter in projs
                )
            ]
        
        if search_query:
            filtered = filtered[filtered["name"].str.contains(search_query, case=False)]
        
        # Sort by name alphabetically
        filtered = filtered.sort_values(by="name", ascending=True, na_position='last')
        
        return filtered
    
    @staticmethod
    def chunk_dataframe(df, chunk_size):
        """Split dataframe into chunks for display"""
        return [df.iloc[i:i+chunk_size] for i in range(0, len(df), chunk_size)]


class ValidationUtils:
    """Utility functions for data validation"""
    
    @staticmethod
    def is_valid_email(email):
        """Check if email format is valid"""
        return isinstance(email, str) and "@" in email
    
    @staticmethod
    def validate_member_data(member):
        """Validate member data structure"""
        required_fields = ["name", "email", "role", "branch"]
        return all(field in member and member[field] for field in required_fields)
    
    @staticmethod
    def sanitize_string(value):
        """Sanitize string values"""
        return str(value) if value is not None else ""


class UIHelpers:
    """Helper functions for UI components"""
    
    @staticmethod
    def create_back_button():
        """Create a back button in a narrow column"""
        col1, col2 = st.columns([1, 8])
        with col1:
            if st.button("←", key="back_arrow"):
                SessionManager.go_back()
                st.rerun()
        return col2
    
    @staticmethod
    def create_refresh_button(label="🔄 Refresh", key=None):
        """Create a refresh button"""
        if st.button(label, key=key):
            st.rerun()
    
    @staticmethod
    def display_profile_image(profile_image_data, width=100, height=100):
        """Display profile image with fallback"""
        if profile_image_data:
            st.markdown(
                f"""
                <img src="data:image/png;base64,{profile_image_data}" 
                    style="width:{width}px; height:{height}px; object-fit:cover; border-radius:10%;">
                """,
                unsafe_allow_html=True,
            )
        else:
            # Display placeholder or default image
            st.markdown(
                f"""
                <div style="width:{width}px; height:{height}px; background-color:#f0f0f0; 
                     border-radius:10%; display:flex; align-items:center; justify-content:center;">
                    <span style="color:#888;">No Image</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    @staticmethod
    def create_filter_controls(df):
        """Create filter controls for team view"""
        col1, col2 = st.columns(2)
        
        with col1:
            branch_filter = st.selectbox(
                "📍 Filter by Branch", 
                ["All"] + sorted(df["branch"].dropna().unique())
            )
        
        with col2:
            # Flatten all project lists into a single unique list
            all_projects = sorted({
                p for projs in df["project"]
                if isinstance(projs, list)
                for p in projs
            })
            project_filter = st.selectbox("📁 Filter by Project", ["All"] + all_projects)
        
        # Search by Name
        search_query = st.text_input("🔍 Search by name")
        
        return branch_filter, project_filter, search_query