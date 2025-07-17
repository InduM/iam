import streamlit as st
from utils.utils_profile import decode_base64_image
from utils.utils_login import is_logged_in
from backend.profile_backend import *
from backend.projects_backend import get_project_by_name  # Adjust this import as per your structure

import streamlit as st
import time
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

@contextmanager
def loading_state(message: str = "Loading...", success_message: Optional[str] = None):
    """Context manager for showing loading spinners with optional success message"""
    try:
        with st.spinner(message):
            yield
        if success_message:
            st.success(success_message)
    except Exception as e:
        st.error(f"Error: {str(e)}")
        raise

def calculate_project_progress(project_data):
    """Calculate project progress based on current level and total levels"""
    print("\n\nPROJECT DATA::::",project_data)
    current_level = project_data.get('level', -1)
    total_levels = len(project_data.get('levels', []))
    
    if total_levels == 0:
        return 0
    
    # Level -1 means not started, 0 means first stage, etc.
    if current_level == -1:
        return 0
    elif current_level >= total_levels - 1:
        return 100
    else:
        return int(((current_level + 1) / total_levels) * 100)

def get_project_status(project_data):
    """Determine project status based on current level and dates"""
    current_level = project_data.get('level', -1)
    total_levels = len(project_data.get('levels', []))
    due_date = project_data.get('dueDate')
    
    if current_level == -1:
        return "Not Started", "⚪"
    elif current_level >= total_levels - 1:
        return "Completed", "🔵"
    else:
        # Check if overdue
        if due_date:
            try:
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                if datetime.now() > due_date_obj:
                    return "Overdue", "🔴"
            except ValueError:
                pass
        return "In Progress", "🟢"

def format_date(date_str):
    """Format date string to a more readable format"""
    if not date_str:
        return "Not set"
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%B %d, %Y')
    except ValueError:
        return date_str

def get_current_stage_info(project_data):
    """Get information about the current stage"""
    current_level = project_data.get('level', -1)
    levels = project_data.get('levels', [])
    
    if current_level == -1:
        return "Project not started", "⏳"
    elif current_level >= len(levels):
        return "Project completed", "✅"
    else:
        current_stage = levels[current_level]
        return f"Currently in: {current_stage}", "🔄"

def display_project_details():
    """Display project details with custom data structure support"""
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
    
    # Fetch project details with loading state
    with loading_state("Loading project details..."):
        project_data = get_project_by_name(selected_project)
    
    if not project_data:
        st.error("Project details not found.")
        st.stop()
    
    # Display project details
    st.markdown("---")
   
    # Project header with status and progress
    col_header, col_status, col_progress = st.columns([2, 1, 1])
    
    with col_header:
        st.subheader(f"📌 {project_data.get('name', 'Unnamed Project')}")
        if project_data.get('client'):
            st.markdown(f"**Client:** {project_data.get('client')}")
    
    with col_status:
        status_text, status_emoji = get_project_status(project_data)
        st.markdown(f"**Status:** {status_emoji} {status_text}")
        
        # Show current stage
        stage_info, stage_emoji = get_current_stage_info(project_data)
        st.markdown(f"**{stage_emoji} {stage_info}**")
    
    with col_progress:
        progress = calculate_project_progress(project_data)
        st.markdown(f"**📊 Progress:** {progress}%")
        st.progress(progress / 100)
   
    # Project information in columns
    col1, col2 = st.columns(2)
   
    with col1:
        st.markdown("**📝 Description:**")
        description = project_data.get('description', 'No description available.')
        if description.strip():
            st.write(description)
        else:
            st.write("No description available.")
        
        # Template information
        if project_data.get('template'):
            st.markdown(f"**📋 Template:** {project_data.get('template')}")
        
        # Created by and timestamps
        if project_data.get('created_by'):
            st.markdown(f"**👤 Created by:** {project_data.get('created_by')}")
        
        if project_data.get('created_at'):
            try:
                created_at = datetime.fromisoformat(project_data.get('created_at').replace('Z', '+00:00'))
                st.markdown(f"**📅 Created:** {created_at.strftime('%B %d, %Y at %I:%M %p')}")
            except:
                st.markdown(f"**📅 Created:** {project_data.get('created_at')}")
   
    with col2:
        st.markdown("**📅 Timeline:**")
        start_date = format_date(project_data.get('startDate'))
        due_date = format_date(project_data.get('dueDate'))
        
        st.write(f"**Start Date:** {start_date}")
        st.write(f"**Due Date:** {due_date}")
        
        # Calculate duration if both dates are available
        if project_data.get('startDate') and project_data.get('dueDate'):
            try:
                start = datetime.strptime(project_data.get('startDate'), '%Y-%m-%d')
                end = datetime.strptime(project_data.get('dueDate'), '%Y-%m-%d')
                duration = (end - start).days
                st.write(f"**Duration:** {duration} days")
                
                # Days remaining
                days_remaining = (end - datetime.now()).days
                if days_remaining > 0:
                    st.write(f"**Days Remaining:** {days_remaining}")
                elif days_remaining == 0:
                    st.write("**Due Today!** 🔥")
                else:
                    st.write(f"**Overdue by:** {abs(days_remaining)} days ⚠️")
            except ValueError:
                pass
        
        # Last updated
        if project_data.get('updated_at'):
            try:
                updated_at = datetime.fromisoformat(project_data.get('updated_at').replace('Z', '+00:00'))
                st.markdown(f"**🔄 Last Updated:** {updated_at.strftime('%B %d, %Y at %I:%M %p')}")
            except:
                st.markdown(f"**🔄 Last Updated:** {project_data.get('updated_at')}")
   
    # Project Stages/Levels section
    if project_data.get('levels'):
        st.markdown("---")
        st.markdown("**📋 Project Stages:**")
        
        levels = project_data.get('levels', [])
        current_level = project_data.get('level', -1)
        stage_assignments = project_data.get('stage_assignments', {})
        
        # Display stages in a nice format
        for i, level_name in enumerate(levels):
            # Determine stage status
            if i < current_level:
                status_icon = "✅"
                status_color = "green"
            elif i == current_level:
                status_icon = "🔄"
                status_color = "blue"
            else:
                status_icon = "⏳"
                status_color = "gray"
            
            # Get stage assignment info
            stage_info = stage_assignments.get(str(i), {})
            stage_name = stage_info.get('stage_name', level_name)
            members = stage_info.get('members', [])
            deadline = stage_info.get('deadline', '')
            substages = stage_info.get('substages', [])
            
            # Display stage
            with st.expander(f"{status_icon} Stage {i+1}: {stage_name}", expanded=(i == current_level)):
                col_stage1, col_stage2 = st.columns(2)
                
                with col_stage1:
                    if members:
                        st.write(f"**👥 Assigned to:** {', '.join(members)}")
                    else:
                        st.write("**👥 Assigned to:** Not assigned")
                
                with col_stage2:
                    if deadline:
                        formatted_deadline = format_date(deadline)
                        st.write(f"**📅 Deadline:** {formatted_deadline}")
                    else:
                        st.write("**📅 Deadline:** Not set")
                
                # Show substages if any
                if substages:
                    st.write("**📝 Substages:**")
                    for substage in substages:
                        st.write(f"  • {substage}")
                
                # Show stage-specific timestamps if available
                timestamps = project_data.get('timestamps', {})
                if str(i) in timestamps:
                    stage_timestamp = timestamps[str(i)]
                    st.write(f"**⏰ Completed:** {stage_timestamp}")
    
    # Team Members Summary
    if project_data.get('stage_assignments'):
        st.markdown("---")
        st.markdown("**👥 Team Members:**")
        
        # Collect all unique members
        all_members = set()
        member_stages = {}
        
        for stage_idx, stage_info in project_data.get('stage_assignments', {}).items():
            members = stage_info.get('members', [])
            for member in members:
                all_members.add(member)
                if member not in member_stages:
                    member_stages[member] = []
                member_stages[member].append(stage_info.get('stage_name', f"Stage {stage_idx}"))
        
        # Display members and their assigned stages
        for member in sorted(all_members):
            stages = member_stages.get(member, [])
            st.write(f"👤 **{member}** - Assigned to: {', '.join(stages)}")
    
    # Action buttons with loading states
    st.markdown("---")
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    
    with col_btn1:
        if st.button("✏️ Edit Project", key="edit_project"):
            with loading_state("Preparing edit interface..."):
                st.session_state.edit_project = selected_project
                st.rerun()
    
    with col_btn2:
        if st.button("📊 View Analytics", key="view_analytics"):
            with loading_state("Loading analytics..."):
                st.session_state.show_project_analytics = selected_project
                st.rerun()
    
    with col_btn3:
        if st.button("⏭️ Advance Stage", key="advance_stage"):
            current_level = project_data.get('level', -1)
            total_levels = len(project_data.get('levels', []))
            
            if current_level < total_levels - 1:
                with loading_state("Advancing to next stage..."):
                    # Add your stage advancement logic here
                    # update_project_stage(selected_project, current_level + 1)
                    st.success(f"Advanced to stage: {project_data.get('levels')[current_level + 1]}")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("Project is already at the final stage!")
    
    with col_btn4:
        if st.button("🗑️ Delete Project", key="delete_project", type="secondary"):
            st.session_state.confirm_delete = selected_project
            st.rerun()
    
    # Confirmation dialog for delete
    if st.session_state.get('confirm_delete') == selected_project:
        st.warning("Are you sure you want to delete this project? This action cannot be undone.")
        col_confirm, col_cancel = st.columns(2)
        
        with col_confirm:
            if st.button("Yes, Delete", key="confirm_delete_yes", type="primary"):
                with loading_state("Deleting project..."):
                    # Add your delete logic here
                    # delete_project(selected_project)
                    time.sleep(1)  # Simulate deletion
                    st.success("Project deleted successfully!")
                    st.session_state.confirm_delete = None
                    st.session_state.selected_project = None
                    st.session_state.show_project_details = False
                    st.rerun()
        
        with col_cancel:
            if st.button("Cancel", key="confirm_delete_no"):
                st.session_state.confirm_delete = None
                st.rerun()

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
        st.write(f"**Name:** {user_profile.get('name', 'N/A')}")
        st.write(f"**Email:** {user_profile.get('email', 'N/A')}")
        st.write(f"**Branch:** {user_profile.get('branch', 'N/A')}")
    
    with col2:
        st.write(f"**Role:** {user_profile.get('position', 'N/A')}")
        st.write(f"**Date of Joining:** {user_profile.get('DOJ', 'N/A')}")

    # Projects section
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
        if st.session_state.get("edit_mode", False):
            edit_profile(user_profile)
        else:
            display_profile(user_profile)
            
            # Update profile button
            st.markdown("---")
            if st.button("Update Profile", type="primary"):
                st.session_state.edit_mode = True
                st.rerun()