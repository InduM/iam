import streamlit as st
import time
from datetime import datetime
from utils.utils_login import is_logged_in
from backend.profile_backend import *
from backend.projects_backend import get_project_by_name  # Adjust this import as per your structure
from contextlib import contextmanager
from typing import Optional
from utils.utils_profile import (decode_base64_image,calculate_project_progress,
                                 get_project_status,format_date,get_current_stage_info,
                                 get_substage_completion_status,get_substage_timestamp)

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



def update_project_stage(project_name, new_stage):
    """
    Update project stage in database
    Replace this with your actual database update logic
    """
    # Example MongoDB update (uncomment and modify for your setup):
    # from pymongo import MongoClient
    # client = MongoClient('your_mongodb_connection_string')
    # db = client['your_database_name']
    # collection = db['your_collection_name']
    # 
    # current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # result = collection.update_one(
    #     {'name': project_name},
    #     {
    #         '$set': {
    #             'level': new_stage,
    #             'updated_at': datetime.now().isoformat(),
    #             f'timestamps.{new_stage}': current_time
    #         }
    #     }
    # )
    # return result.modified_count > 0
    
    # For demo purposes
    return True


def update_substage_completion(project_name, stage_idx, substage_idx, completed=True):
    """
    Update substage completion status in database
    """
    # Example MongoDB update (uncomment and modify for your setup):
    # from pymongo import MongoClient
    # client = MongoClient('your_mongodb_connection_string')
    # db = client['your_database_name']
    # collection = db['your_collection_name']
    # 
    # current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # update_data = {
    #     f'substage_completion.{stage_idx}.{substage_idx}': completed,
    #     'updated_at': datetime.now().isoformat()
    # }
    # 
    # if completed:
    #     update_data[f'substage_timestamps.{stage_idx}.{substage_idx}'] = current_time
    # 
    # result = collection.update_one(
    #     {'name': project_name},
    #     {'$set': update_data}
    # )
    # return result.modified_count > 0
    
    # For demo purposes
    return True

def display_project_details():
    """Display project details with custom data structure support"""
   
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
   
    # Project Stages/Levels section with detailed substages
    if project_data.get('levels'):
        st.markdown("---")
        st.markdown("**📋 Project Stages:**")
        
        # Add stage filter options
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
        
        levels = project_data.get('levels', [])
        current_level = project_data.get('level', -1)
        stage_assignments = project_data.get('stage_assignments', {})
        
        # Filter stages based on selection
        stages_to_display = []
        for i, level_name in enumerate(levels):
            should_display = False
            
            # Apply status filter
            if stage_filter == "All Stages":
                should_display = True
            elif stage_filter == "Completed" and i < current_level:
                should_display = True
            elif stage_filter == "Current" and i == current_level:
                should_display = True
            elif stage_filter == "Upcoming" and i > current_level:
                should_display = True
            
            # Apply search filter
            if should_display and search_term:
                stage_info = stage_assignments.get(str(i), {})
                stage_name = stage_info.get('stage_name', level_name)
                substages = stage_info.get('substages', [])
                
                search_lower = search_term.lower()
                stage_matches = search_lower in stage_name.lower()
                substage_matches = any(
                    search_lower in substage.get('name', '').lower() or 
                    search_lower in substage.get('description', '').lower()
                    for substage in substages
                )
                
                should_display = stage_matches or substage_matches
            
            if should_display:
                stages_to_display.append(i)
        
        # Display filtered stages
        if not stages_to_display:
            st.info("No stages match the current filter criteria.")
        else:
            # Display stages in a nice format
            for i in stages_to_display:
                level_name = levels[i]
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
            
            # Get stage completion timestamp
            stage_timestamp = project_data.get('timestamps', {}).get(str(i), None)
            
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
                
                # Show stage completion timestamp
                if stage_timestamp:
                    st.write(f"**⏰ Stage Completed:** {stage_timestamp}")
                
                # Show substage progress if substages exist
                if substages:
                    completed_count = sum(1 for k in range(len(substages)) 
                                        if get_substage_completion_status(project_data, i, k))
                    total_count = len(substages)
                    substage_progress = (completed_count / total_count) * 100 if total_count > 0 else 0
                    
                    st.write(f"**📊 Substage Progress:** {completed_count}/{total_count} ({substage_progress:.0f}%)")
                    st.progress(substage_progress / 100)
                
                # Show substages with detailed information
                if substages:
                    st.write("**📝 Substages:**")
                    for j, substage in enumerate(substages):
                        # Check if substage is completed
                        is_completed = get_substage_completion_status(project_data, i, j)
                        completion_timestamp = get_substage_timestamp(project_data, i, j)
                        
                        # Substage status icon
                        substage_icon = "✅" if is_completed else "⏳"
                        
                        # Priority color coding
                        priority = substage.get('priority', 'Medium')
                        if priority == 'High':
                            priority_color = "🔴"
                        elif priority == 'Medium':
                            priority_color = "🟡"
                        else:
                            priority_color = "🟢"
                        
                        st.markdown(f"{substage_icon} **{substage.get('name', 'Unnamed Substage')}**")
                        st.markdown(f" 📝 {substage.get('description', 'No description')}")
                        
                        # Substage details in columns
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
                            st.markdown(f"{priority_color} **Priority:** {priority}")
                            
                            start_date = substage.get('start_date', '')
                            if start_date:
                                formatted_start = format_date(start_date)
                                st.markdown(f"📅 **Start:** {formatted_start}")
                        
                        # Show completion timestamp if available
                        if completion_timestamp:
                            st.markdown(f"    ✅ **Completed:** {completion_timestamp}")
                        
                        # Add substage completion toggle for current stage
                        if i == current_level:
                            col_toggle, col_space = st.columns([1, 3])
                            with col_toggle:
                                if st.button(
                                    "✅ Complete" if not is_completed else "↩️ Undo",
                                    key=f"toggle_substage_{i}_{j}",
                                    type="secondary"
                                ):
                                    with loading_state(f"Updating substage status..."):
                                        success = update_substage_completion(
                                            selected_project, i, j, not is_completed
                                        )
                                        if success:
                                            st.success("Substage updated successfully!")
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.error("Failed to update substage!")
                        
                        st.markdown("---")
    
    # Team Members Summary
    if project_data.get('stage_assignments'):
        st.markdown("---")
        st.markdown("**👥 Team Members:**")
        
        # Collect all unique members
        all_members = set()
        member_stages = {}
        
        for stage_idx, stage_info in project_data.get('stage_assignments', {}).items():
            members = stage_info.get('members', [])
            substages = stage_info.get('substages', [])
            
            # Add stage members
            for member in members:
                all_members.add(member)
                if member not in member_stages:
                    member_stages[member] = []
                member_stages[member].append(stage_info.get('stage_name', f"Stage {stage_idx}"))
            
            # Add substage assignees
            for substage in substages:
                assignees = substage.get('assignees', [])
                for assignee in assignees:
                    all_members.add(assignee)
                    if assignee not in member_stages:
                        member_stages[assignee] = []
                    if stage_info.get('stage_name') not in member_stages[assignee]:
                        member_stages[assignee].append(stage_info.get('stage_name', f"Stage {stage_idx}"))
        
        # Display members and their assigned stages
        for member in sorted(all_members):
            stages = member_stages.get(member, [])
            st.write(f"👤 **{member}** - Assigned to: {', '.join(stages)}")
    
    # Project Statistics
    st.markdown("---")
    st.markdown("**📊 Project Statistics:**")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        total_stages = len(project_data.get('levels', []))
        st.metric("Total Stages", total_stages)
    
    with col_stat2:
        current_stage = project_data.get('level', -1) + 1
        st.metric("Current Stage", f"{current_stage}/{total_stages}")
    
    with col_stat3:
        # Count total substages
        total_substages = 0
        completed_substages = 0
        
        for stage_idx, stage_info in project_data.get('stage_assignments', {}).items():
            substages = stage_info.get('substages', [])
            total_substages += len(substages)
            
            completion_data = project_data.get('substage_completion', {}).get(stage_idx, {})
            completed_substages += sum(1 for completed in completion_data.values() if completed)
        
        st.metric("Substages Completed", f"{completed_substages}/{total_substages}")
    
    with col_stat4:
        # Calculate days since start
        if project_data.get('startDate'):
            try:
                start_date = datetime.strptime(project_data.get('startDate'), '%Y-%m-%d')
                days_elapsed = (datetime.now() - start_date).days
                st.metric("Days Elapsed", days_elapsed)
            except ValueError:
                st.metric("Days Elapsed", "N/A")
        else:
            st.metric("Days Elapsed", "N/A")
    
    # Action buttons with loading states
    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("✏️ Edit Project", key="edit_project"):
            with loading_state("Preparing edit interface..."):
                st.session_state.edit_project = selected_project
                st.rerun()
    
   
    
    with col_btn3:
        if st.button("⏭️ Advance Stage", key="advance_stage"):
            current_level = project_data.get('level', -1)
            total_levels = len(project_data.get('levels', []))
            
            if current_level < total_levels - 1:
                with loading_state("Advancing to next stage..."):
                    success = update_project_stage(selected_project, current_level + 1)
                    if success:
                        st.success(f"Advanced to stage: {project_data.get('levels')[current_level + 1]}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to advance stage!")
            else:
                st.info("Project is already at the final stage!")

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