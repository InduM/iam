import streamlit as st
from utils.utils_profile import decode_base64_image
from utils.utils_login import is_logged_in
from backend.profile_backend import *
from backend.projects_backend import get_project_by_name  # Adjust this import as per your structure

def display_project_details():
    """Display project details on a separate page with back button"""
    st.title("📁 Project Details")
    
    # Back button at the top
    if st.button("⬅️ Back to Profile", key="back_to_profile"):
        st.session_state.selected_project = None
        st.session_state.show_project_details = False
        st.rerun()

    # Check if project was selected
    selected_project = st.session_state.get("selected_project", None)

    if not selected_project:
        st.error("No project selected.")
        st.stop()

    # Fetch project details from MongoDB
    project_data = get_project_by_name(selected_project)

    if not project_data:
        st.error("Project details not found.")
        st.stop()

    # Display project details in a nice format
    st.markdown("---")
    
    # Project header
    st.subheader(f"📌 {project_data.get('name', 'Unnamed Project')}")
    
    # Project information in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📝 Description:**")
        st.write(project_data.get('description', 'No description available.'))
        
        st.markdown("**👥 Team Members:**")
        members = project_data.get('members', [])
        if members:
            for member in members:
                st.write(f"• {member}")
        else:
            st.write("No team members listed.")
    
    with col2:
        st.markdown("**📅 Timeline:**")
        st.write(f"**Start Date:** {project_data.get('start_date', 'N/A')}")
        st.write(f"**End Date:** {project_data.get('end_date', 'N/A')}")
        
        # Additional project details if available
        if project_data.get('status'):
            st.write(f"**Status:** {project_data.get('status')}")
        
        if project_data.get('priority'):
            st.write(f"**Priority:** {project_data.get('priority')}")
    
    # Additional sections can be added here
    if project_data.get('tasks'):
        st.markdown("---")
        st.markdown("**📋 Tasks:**")
        tasks = project_data.get('tasks', [])
        for task in tasks:
            st.write(f"• {task}")
    
    if project_data.get('notes'):
        st.markdown("---")
        st.markdown("**📝 Notes:**")
        st.write(project_data.get('notes'))

def edit_profile(profile):
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

def display_profile(user_profile):
    # Profile image
    col1, col2, col3 = st.columns(3)
    with col2:
        image_data = decode_base64_image(get_profile_image(st.session_state["username"]))
        if not image_data:
            image_data = decode_base64_image(get_profile_image("admin"))
        if image_data:
            st.image(image_data, use_container_width=False, width=200)

    # Profile information
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**👤 Name:** {user_profile.get('name', 'N/A')}")
        st.write(f"**📧 Email:** {user_profile.get('email', 'N/A')}")
        st.write(f"**🌿 Branch:** {user_profile.get('branch', 'N/A')}")
    
    with col2:
        st.write(f"**💼 Role:** {user_profile.get('position', 'N/A')}")
        st.write(f"**📅 Date of Joining:** {user_profile.get('DOJ', 'N/A')}")

    # Projects section
    st.markdown("---")
    st.markdown("### 📁 Current Projects")
    
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

def run():
    st.markdown("""
        <style>
        .sidebar .sidebar-content {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        /* Custom styling for buttons */
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
    """, unsafe_allow_html=True)

    # Check if user is logged in
    if not is_logged_in():
        st.switch_page("option.py")

    # Initialize session state variables
    if "show_project_details" not in st.session_state:
        st.session_state.show_project_details = False
    if "selected_project" not in st.session_state:
        st.session_state.selected_project = None
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False

    # Get user profile
    user_profile = get_user_profile(st.session_state["username"])
    
    if not user_profile:
        st.error("User profile not found.")
        return

    # Navigation logic
    if st.session_state.show_project_details:
        # Show project details page
        display_project_details()
    else:
        # Show profile page
        st.title(f"👤 {user_profile.get('name', 'User')} Profile")
        
        if st.session_state.get("edit_mode", False):
            edit_profile(user_profile)
        else:
            display_profile(user_profile)
            
            # Update profile button
            st.markdown("---")
            if st.button("✏️ Update Profile", type="primary"):
                st.session_state.edit_mode = True
                st.rerun()