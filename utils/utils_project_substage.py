import streamlit as st
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from backend.projects_backend import update_substage_completion_in_db

def render_stage_assignments_editor_with_substages(levels: List[str], team_members: List[str], 
                                                 current_assignments: Dict = None) -> Dict:
    """
    Enhanced stage assignment editor with full substage support - Fixed version
    """    
    if current_assignments is None:
        current_assignments = {}
    
    # Initialize session state for substages if not exists
    if "stage_substages" not in st.session_state:
        st.session_state.stage_substages = {}
    
    # Initialize session state for new substage forms
    if "show_new_substage_form" not in st.session_state:
        st.session_state.show_new_substage_form = {}
    
    stage_assignments = {}
    
    for i, level in enumerate(levels):
        stage_key = str(i)
        current_stage = current_assignments.get(stage_key, {})
        
        # Initialize substages for this stage in session state
        if stage_key not in st.session_state.stage_substages:
            st.session_state.stage_substages[stage_key] = current_stage.get("substages", [])
        
        # Initialize form visibility state
        if stage_key not in st.session_state.show_new_substage_form:
            st.session_state.show_new_substage_form[stage_key] = False
        
        st.markdown(f"### Stage {i+1}: {level}")
        
        with st.container():
            # Stage-level assignments
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Assign team members to stage
                assigned_members = st.multiselect(
                    f"Assign Team Members",
                    options=team_members,
                    default=current_stage.get("members", []),
                    key=f"stage_{i}_members"
                )
            
            with col2:
                # Stage deadline
                current_deadline = None
                if current_stage.get("deadline"):
                    try:
                        current_deadline = date.fromisoformat(current_stage["deadline"])
                    except:
                        pass
                
                stage_deadline = st.date_input(
                    f"Stage Deadline",
                    value=current_deadline,
                    key=f"stage_{i}_deadline"
                )
            
            # Initialize stage data with substages from session state
            stage_assignments[stage_key] = {
                "stage_name": level,
                "members": assigned_members,
                "deadline": stage_deadline.isoformat() if stage_deadline else "",
                "substages": st.session_state.stage_substages[stage_key].copy()
            }
            
            # Substages Section
            st.markdown("**Substages:**")
            
            # Add new substage button and form
            col_btn, col_space = st.columns([1, 3])
            with col_btn:
                if st.button(f"➕ Add Substage", key=f"add_substage_btn_{i}"):
                    st.session_state.show_new_substage_form[stage_key] = True
                    st.rerun()
            
            # Show form to add new substage
            if st.session_state.show_new_substage_form[stage_key]:
                with st.container():
                    st.markdown("**Add New Substage:**")
                    
                    # Create a unique form key
                    form_key = f"new_substage_form_{i}_{len(st.session_state.stage_substages[stage_key])}"
                    
                    with st.form(form_key):
                        substage_col1, substage_col2 = st.columns([2, 1])
                        
                        with substage_col1:
                            new_substage_name = st.text_input("Substage Name")
                            new_substage_desc = st.text_area("Description (optional)")
                            new_substage_assignees = st.multiselect(
                                "Assign to Team Members",
                                options=assigned_members if assigned_members else team_members
                            )
                        
                        with substage_col2:
                            new_substage_deadline = st.date_input("Substage Deadline", value=None)
                            new_substage_priority = st.selectbox(
                                "Priority",
                                options=["Low", "Medium", "High", "Critical"],
                                index=1  # Default to Medium
                            )
                        
                        # Form submission buttons
                        submit_col1, submit_col2 = st.columns([1, 1])
                        
                        with submit_col1:
                            submitted = st.form_submit_button("✅ Add Substage")
                        
                        with submit_col2:
                            cancelled = st.form_submit_button("❌ Cancel")
                        
                        # Handle form submission
                        if submitted:
                            if new_substage_name.strip():
                                # Create new substage
                                new_substage = {
                                    "id": f"substage_{i}_{len(st.session_state.stage_substages[stage_key])}_{int(datetime.now().timestamp())}",
                                    "name": new_substage_name.strip(),
                                    "description": new_substage_desc.strip(),
                                    "assignees": new_substage_assignees,
                                    "deadline": new_substage_deadline.isoformat() if new_substage_deadline else "",
                                    "priority": new_substage_priority,
                                    "completed": False,
                                    "created_at": datetime.now().isoformat(),
                                    "completed_at": None
                                }
                                
                                # Add to session state
                                st.session_state.stage_substages[stage_key].append(new_substage)
                                
                                # Hide form and show success
                                st.session_state.show_new_substage_form[stage_key] = False
                                st.success(f"Substage '{new_substage_name}' added successfully!")
                                st.rerun()
                            else:
                                st.error("Substage name is required!")
                        
                        if cancelled:
                            st.session_state.show_new_substage_form[stage_key] = False
                            st.rerun()
            
            # Display existing substages
            current_substages = st.session_state.stage_substages[stage_key]
            
            if current_substages:
                st.markdown(f"**Current Substages ({len(current_substages)}):**")
                
                # Track substages to be removed
                substages_to_remove = []
                
                for idx, substage in enumerate(current_substages):
                    substage_key = f"substage_{stage_key}_{idx}"
                    
                    with st.expander(f"🔧 {substage.get('name', f'Substage {idx+1}')} - {substage.get('priority', 'Medium')} Priority"):
                        
                        # Substage editing
                        edit_col1, edit_col2, edit_col3 = st.columns([2, 1, 1])
                        
                        with edit_col1:
                            # Edit substage details
                            updated_name = st.text_input(
                                "Name", 
                                value=substage.get("name", ""),
                                key=f"edit_name_{substage_key}"
                            )
                            
                            updated_desc = st.text_area(
                                "Description", 
                                value=substage.get("description", ""),
                                key=f"edit_desc_{substage_key}"
                            )
                            
                            updated_assignees = st.multiselect(
                                "Assigned to",
                                options=assigned_members if assigned_members else team_members,
                                default=substage.get("assignees", []),
                                key=f"edit_assignees_{substage_key}"
                            )
                        
                        with edit_col2:
                            # Deadline and priority
                            current_substage_deadline = None
                            if substage.get("deadline"):
                                try:
                                    current_substage_deadline = date.fromisoformat(substage["deadline"])
                                except:
                                    pass
                            
                            updated_deadline = st.date_input(
                                "Deadline",
                                value=current_substage_deadline,
                                key=f"edit_deadline_{substage_key}"
                            )
                            
                            updated_priority = st.selectbox(
                                "Priority",
                                options=["Low", "Medium", "High", "Critical"],
                                index=["Low", "Medium", "High", "Critical"].index(substage.get("priority", "Medium")),
                                key=f"edit_priority_{substage_key}"
                            )
                            
                            # Completion status
                            is_completed = st.checkbox(
                                "Completed",
                                value=substage.get("completed", False),
                                key=f"edit_completed_{substage_key}"
                            )
                        
                        with edit_col3:
                            # Actions
                            st.markdown("**Actions:**")
                            
                            if st.button(f"💾 Update", key=f"update_{substage_key}"):
                                # Update substage data in session state
                                st.session_state.stage_substages[stage_key][idx].update({
                                    "name": updated_name,
                                    "description": updated_desc,
                                    "assignees": updated_assignees,
                                    "deadline": updated_deadline.isoformat() if updated_deadline else "",
                                    "priority": updated_priority,
                                    "completed": is_completed,
                                    "completed_at": datetime.now().isoformat() if is_completed and not substage.get("completed") else substage.get("completed_at"),
                                    "updated_at": datetime.now().isoformat()
                                })
                                st.success(f"Substage '{updated_name}' updated!")
                                st.rerun()
                            
                            if st.button(f"🗑️ Delete", key=f"delete_{substage_key}"):
                                substages_to_remove.append(idx)
                        
                        # Show completion info
                        if substage.get("completed"):
                            completed_at = substage.get("completed_at")
                            if completed_at:
                                try:
                                    dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                                    st.success(f"✅ Completed on: {dt.strftime('%Y-%m-%d %H:%M')}")
                                except:
                                    st.success(f"✅ Completed")
                
                # Remove substages marked for deletion (in reverse order to maintain indices)
                for idx in sorted(substages_to_remove, reverse=True):
                    removed_substage = st.session_state.stage_substages[stage_key].pop(idx)
                    st.success(f"Substage '{removed_substage.get('name', 'Unnamed')}' deleted!")
                    st.rerun()
            
            else:
                st.info("No substages defined for this stage yet.")
        
        st.markdown("---")
    
    # Update stage assignments with current substages from session state
    for stage_key in stage_assignments:
        stage_assignments[stage_key]["substages"] = st.session_state.stage_substages[stage_key].copy()
    
    return stage_assignments

def render_substage_progress(project: Dict, stage_index: int, substages: List[Dict], editable: bool = False):
    """
    Render substage progress for a specific stage
    """
    if not substages:
        return
    
    st.markdown("**Substages:**")
    
    completed_count = sum(1 for s in substages if s.get("completed", False))
    total_count = len(substages)
    
    # Progress bar
    progress = completed_count / total_count if total_count > 0 else 0
    st.progress(progress, text=f"{completed_count}/{total_count} substages completed")
    
    # Individual substage status
    for idx, substage in enumerate(substages):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            status_icon = "✅" if substage.get("completed", False) else "⏳"
            priority_icon = {
                "Critical": "🔴",
                "High": "🟠", 
                "Medium": "🟡",
                "Low": "🟢"
            }.get(substage.get("priority", "Medium"), "🟡")
            
            st.markdown(f"{status_icon} {priority_icon} **{substage.get('name', f'Substage {idx+1}')}**")
            
            if substage.get("description"):
                st.caption(substage["description"])
        
        with col2:
            assignees = substage.get("assignees", [])
            if assignees:
                st.caption(f"👥 {', '.join(assignees)}")
            
            deadline = substage.get("deadline")
            if deadline:
                try:
                    deadline_date = date.fromisoformat(deadline)
                    today = date.today()
                    days_left = (deadline_date - today).days
                    
                    if days_left < 0:
                        st.caption(f"🔴 {abs(days_left)} days overdue")
                    elif days_left == 0:
                        st.caption("🟡 Due today")
                    else:
                        st.caption(f"📅 {days_left} days left")
                except:
                    st.caption(f"📅 {deadline}")
        
        with col3:
            if editable and not substage.get("completed", False):
                substage_key = f"complete_substage_{stage_index}_{idx}_{project.get('id', 'unknown')}"
                if st.button("✅ Complete", key=substage_key):
                    # Mark substage as completed
                    substage["completed"] = True
                    substage["completed_at"] = datetime.now().isoformat()
                    
                    # Update in project data and database
                    project_id = project.get("id")
                    if project_id:
                        # This would need to be implemented to update the database
                        # update_substage_completion_in_db(project_id, stage_index, idx, True)
                        pass
                    
                    st.success(f"Substage '{substage.get('name')}' completed!")
                    st.rerun()

                    
def handle_substage_completion(project, stage_index, substage_index, completed):
    """
    Handle substage completion/incompletion
    """
    project_id = project["id"]
    stage_assignments = project.get("stage_assignments", {})
    stage_key = str(stage_index)
    
    if stage_key in stage_assignments and "substages" in stage_assignments[stage_key]:
        substages = stage_assignments[stage_key]["substages"]
        
        if substage_index < len(substages):
            substages[substage_index]["completed"] = completed
            
            if completed:
                substages[substage_index]["completed_at"] = datetime.now().isoformat()
                # Send notification to assigned members
                substage_name = substages[substage_index]["name"]
                project_name = project.get("name", "")
                assigned_members = substages[substage_index].get("assigned_members", [])
                
                if assigned_members:
                    # In a real implementation, send email notifications
                    pass
            else:
                substages[substage_index]["completed_at"] = ""
            
            # Update project in database
            from backend.projects_backend import update_project_substage_in_db
            update_project_substage_in_db(project_id, stage_index, substage_index, completed)

def get_substage_completion_stats(stage_assignments: Dict) -> Dict:
    """
    Get comprehensive substage completion statistics
    """
    stats = {
        "total_substages": 0,
        "completed_substages": 0,
        "overdue_substages": 0,
        "today_due_substages": 0,
        "upcoming_substages": 0,
        "by_priority": {"Low": 0, "Medium": 0, "High": 0, "Critical": 0},
        "by_stage": {}
    }
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {int(stage_key) + 1}")
        stage_stats = {
            "total": 0,
            "completed": 0,
            "overdue": 0,
            "pending": 0
        }
        
        substages = stage_data.get("substages", [])
        stats["total_substages"] += len(substages)
        stage_stats["total"] = len(substages)
        
        for substage in substages:
            # Count by priority
            priority = substage.get("priority", "Medium")
            if priority in stats["by_priority"]:
                stats["by_priority"][priority] += 1
            
            if substage.get("completed", False):
                stats["completed_substages"] += 1
                stage_stats["completed"] += 1
            else:
                stage_stats["pending"] += 1
                
                # Check deadline status for incomplete substages
                if substage.get("deadline"):
                    try:
                        deadline_date = date.fromisoformat(substage["deadline"])
                        days_until = (deadline_date - date.today()).days
                        
                        if days_until < 0:
                            stats["overdue_substages"] += 1
                            stage_stats["overdue"] += 1
                        elif days_until == 0:
                            stats["today_due_substages"] += 1
                        elif days_until <= 7:
                            stats["upcoming_substages"] += 1
                    except:
                        pass
        
        stats["by_stage"][stage_name] = stage_stats
    
    return stats

def render_substage_summary_widget(project: Dict):
    """
    Render a summary widget showing substage completion across all stages
    """
    stage_assignments = project.get("stage_assignments", {})
    
    if not stage_assignments:
        return
    
    total_substages = 0
    completed_substages = 0
    overdue_substages = 0
    
    # Calculate overall substage statistics
    for stage_key, stage_data in stage_assignments.items():
        substages = stage_data.get("substages", [])
        total_substages += len(substages)
        
        for substage in substages:
            if substage.get("completed", False):
                completed_substages += 1
            
            # Check if overdue
            if not substage.get("completed", False) and substage.get("deadline"):
                try:
                    deadline_date = date.fromisoformat(substage["deadline"])
                    if deadline_date < date.today():
                        overdue_substages += 1
                except:
                    pass
    
    if total_substages > 0:
        st.markdown("**📊 Substage Summary:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            completion_rate = (completed_substages / total_substages) * 100
            st.metric("Completion Rate", f"{completion_rate:.1f}%", f"{completed_substages}/{total_substages}")
        
        with col2:
            if overdue_substages > 0:
                st.metric("⚠️ Overdue", overdue_substages, delta=f"-{overdue_substages}", delta_color="inverse")
            else:
                st.metric("✅ On Track", "All substages", delta="0 overdue", delta_color="normal")
        
        with col3:
            pending_substages = total_substages - completed_substages
            st.metric("Pending", pending_substages)

def get_substage_overdue_list(stage_assignments: Dict) -> List[Dict]:
    """
    Get list of overdue substages across all stages
    """
    overdue_substages = []
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {int(stage_key) + 1}")
        substages = stage_data.get("substages", [])
        
        for idx, substage in enumerate(substages):
            if not substage.get("completed", False) and substage.get("deadline"):
                try:
                    deadline_date = date.fromisoformat(substage["deadline"])
                    days_overdue = (date.today() - deadline_date).days
                    
                    if days_overdue > 0:
                        overdue_substages.append({
                            "stage_name": stage_name,
                            "substage_name": substage.get("name", f"Substage {idx+1}"),
                            "assignees": substage.get("assignees", []),
                            "deadline": deadline_date.strftime("%Y-%m-%d"),
                            "days_overdue": days_overdue,
                            "priority": substage.get("priority", "Medium")
                        })
                except:
                    pass
    
    return sorted(overdue_substages, key=lambda x: x["days_overdue"], reverse=True)

def get_substage_upcoming_deadlines(stage_assignments: Dict, days_ahead: int = 7) -> List[Dict]:
    """
    Get list of upcoming substage deadlines
    """
    upcoming_substages = []
    
    for stage_key, stage_data in stage_assignments.items():
        stage_name = stage_data.get("stage_name", f"Stage {int(stage_key) + 1}")
        substages = stage_data.get("substages", [])
        
        for idx, substage in enumerate(substages):
            if not substage.get("completed", False) and substage.get("deadline"):
                try:
                    deadline_date = date.fromisoformat(substage["deadline"])
                    days_until = (deadline_date - date.today()).days
                    
                    if 0 <= days_until <= days_ahead:
                        upcoming_substages.append({
                            "stage_name": stage_name,
                            "substage_name": substage.get("name", f"Substage {idx+1}"),
                            "assignees": substage.get("assignees", []),
                            "deadline": deadline_date.strftime("%Y-%m-%d"),
                            "days_until": days_until,
                            "priority": substage.get("priority", "Medium")
                        })
                except:
                    pass
    
    return sorted(upcoming_substages, key=lambda x: x["days_until"])

def render_substage_assignments_editor(levels: List[str], team_members: List[str], stage_assignments: Dict = None):
    """
    Render stage assignments editor
    """
    if stage_assignments is None:
        stage_assignments = {}
    
    st.subheader("📋 Stage Assignments")
    st.markdown("Assign team members and deadlines for each project stage:")
    
    updated_assignments = {}
    
    for i, stage in enumerate(levels):
        with st.expander(f"Stage {i+1}: {stage}", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            # Get current assignment if exists
            current_assignment = stage_assignments.get(str(i), {})
            current_members = current_assignment.get('members', [])
            current_deadline = current_assignment.get('deadline', '')
            
            with col1:
                # Team member selection
                assigned_members = st.multiselect(
                    f"Assign team members to {stage}",
                    options=team_members,
                    default=current_members,
                    key=f"stage_{i}_members"
                )
            
            with col2:
                # Deadline selection
                deadline_value = None
                if current_deadline:
                    try:
                        deadline_value = date.fromisoformat(current_deadline)
                    except:
                        pass
                
                deadline = st.date_input(
                    f"Deadline for {stage}",
                    value=deadline_value,
                    key=f"stage_{i}_deadline"
                )
            
            # Store the assignment
            if assigned_members or deadline:
                updated_assignments[str(i)] = {
                    'members': assigned_members,
                    'deadline': deadline.isoformat() if deadline else '',
                    'stage_name': stage
                }
    
    return updated_assignments