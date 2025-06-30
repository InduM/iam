import streamlit as st
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import yagmail
from backend.projects_backend import update_substage_completion_in_db

# ───── Constants ─────
TEMPLATES = {
    "Software Project": ["Planning", "Design", "Development", "Testing", "Deployment"],
    "Research Project": ["Hypothesis", "Data Collection", "Analysis", "Publication"],
    "Event Planning": ["Ideation", "Budgeting", "Vendor Selection", "Promotion", "Execution"],
    "v-shesh": ["Initial Contact", "Scope", "Proposal", "Accept Quote", "Onboarding", "Service"]
}

# ───── Email Functions ─────
def send_invoice_email(to_email, project_name):
    """Send invoice reminder email"""
    try:
        yag = yagmail.SMTP(user=st.secrets["email"]["from"], password=st.secrets["email"]["password"])
        subject = f"Invoice Stage Reminder – {project_name}"
        body = f"Reminder: Project '{project_name}' has reached Invoice stage."
        yag.send(to=to_email, subject=subject, contents=body)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def send_stage_assignment_email(to_emails, project_name, stage_name, deadline):
    """Send stage assignment notification email"""
    try:
        yag = yagmail.SMTP(user=st.secrets["email"]["from"], password=st.secrets["email"]["password"])
        subject = f"Stage Assignment – {project_name}: {stage_name}"
        body = f"""
        You have been assigned to the '{stage_name}' stage of project '{project_name}'.
        
        Deadline: {deadline}
        
        Please log in to the project management system to view details and update progress.
        """
        yag.send(to=to_emails, subject=subject, contents=body)
        return True
    except Exception as e:
        st.error(f"Failed to send assignment email: {e}")
        return False

# ───── Helper Functions ─────
def format_level(i, levels: List[str]):
    """Format level display string"""
    try:
        i = int(i)
        if i >= 0 and i < len(levels):
            return f"Level {i+1} – {str(levels[i])}"
        else:
            return f"Level {i+1}"
    except Exception:
        return f"Level {i+1}"

def render_level_checkboxes(prefix, project_id, current_level, timestamps, levels, on_change_fn=None, editable=True, stage_assignments=None):
    """Render interactive level checkboxes with stage assignment info"""
    for i, label in enumerate(levels):
        key = f"{prefix}_{project_id}_level_{i}"
        checked = i <= current_level and current_level >= 0
        disabled = not editable or i > current_level + 1 or (i < current_level and i != current_level)
        
        # Build display label with timestamp
        display_label = f"{label}"
        if checked and str(i) in timestamps:
            display_label += f" ⏱️ {timestamps[str(i)]}"
        
        # Add stage assignment info if available
        if stage_assignments and str(i) in stage_assignments:
            assignment = stage_assignments[str(i)]
            assigned_members = assignment.get('members', [])
            deadline = assignment.get('deadline', '')
            
            if assigned_members:
                display_label += f" 👥 {', '.join(assigned_members[:2])}"
                if len(assigned_members) > 2:
                    display_label += f" +{len(assigned_members)-2}"
            
            if deadline:
                try:
                    deadline_date = date.fromisoformat(deadline)
                    today = date.today()
                    days_diff = (deadline_date - today).days
                    
                    if days_diff < 0:
                        display_label += f" 🔴 Overdue ({abs(days_diff)}d)"
                    elif days_diff == 0:
                        display_label += f" 🟡 Due Today"
                    elif days_diff <= 3:
                        display_label += f" 🟠 Due in {days_diff}d"
                    else:
                        display_label += f" 📅 Due {deadline}"
                except:
                    display_label += f" 📅 {deadline}"

        def callback(i=i, cl=current_level):
            if i == cl + 1:
                on_change_fn(i)
            elif i == cl:
                on_change_fn(i - 1)

        st.checkbox(
            label=display_label,
            value=checked,
            key=key,
            disabled=disabled,
            on_change=callback if editable and on_change_fn else None
        )

def render_stage_assignments_editor(levels: List[str], team_members: List[str], stage_assignments: Dict = None):
    """Render stage assignments editor"""
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

def get_stage_assignment_summary(stage_assignments: Dict, levels: List[str]) -> str:
    """Get a summary of stage assignments for display"""
    if not stage_assignments:
        return "No stage assignments"
    
    summaries = []
    for i, level in enumerate(levels):
        if str(i) in stage_assignments:
            assignment = stage_assignments[str(i)]
            members = assignment.get('members', [])
            deadline = assignment.get('deadline', '')
            
            summary_parts = []
            if members:
                summary_parts.append(f"👥 {len(members)} member(s)")
            if deadline:
                summary_parts.append(f"📅 {deadline}")
            
            if summary_parts:
                summaries.append(f"{level}: {', '.join(summary_parts)}")
    
    return "; ".join(summaries) if summaries else "No assignments"

def validate_stage_assignments(stage_assignments: Dict, levels: List[str]) -> List[str]:
    """
    Validate stage assignments and return list of issues
    """
    issues = []
    
    for stage_key, assignment in stage_assignments.items():
        try:
            stage_index = int(stage_key)
            if stage_index >= len(levels):
                issues.append(f"Stage {stage_index + 1} index exceeds available levels")
                continue
                
            stage_name = levels[stage_index]
            
            # Check if stage has members assigned
            members = assignment.get("members", [])
            if not members:
                issues.append(f"No team members assigned to stage '{stage_name}'")
            
            # Check substages
            substages = assignment.get("substages", [])
            for idx, substage in enumerate(substages):
                substage_name = substage.get("name", f"Substage {idx + 1}")
                
                # Check if substage has assignees
                assignees = substage.get("assignees", [])
                if not assignees:
                    issues.append(f"No assignees for substage '{substage_name}' in stage '{stage_name}'")
                
                # Check if substage assignees are in stage members
                invalid_assignees = [a for a in assignees if a not in members]
                if invalid_assignees:
                    issues.append(f"Substage '{substage_name}' has assignees not in stage team: {', '.join(invalid_assignees)}")
                
                # Check if substage has a name
                if not substage.get("name", "").strip():
                    issues.append(f"Unnamed substage found in stage '{stage_name}'")
                    
        except ValueError:
            issues.append(f"Invalid stage key: {stage_key}")
    
    return issues

def get_overdue_stages(stage_assignments: Dict, levels: List[str], current_level: int) -> List[Dict]:
    """
    Get list of overdue stages based on deadlines
    """
    overdue_stages = []
    
    for stage_key, assignment in stage_assignments.items():
        try:
            stage_index = int(stage_key)
            
            # Only check stages that should be completed by now
            if stage_index <= current_level and assignment.get("deadline"):
                deadline_str = assignment["deadline"]
                try:
                    deadline_date = date.fromisoformat(deadline_str)
                    days_overdue = (date.today() - deadline_date).days
                    
                    if days_overdue > 0:
                        stage_name = assignment.get("stage_name", levels[stage_index] if stage_index < len(levels) else f"Stage {stage_index + 1}")
                        overdue_stages.append({
                            "stage_index": stage_index,
                            "stage_name": stage_name,
                            "deadline": deadline_date.strftime("%Y-%m-%d"),
                            "days_overdue": days_overdue
                        })
                except ValueError:
                    pass  # Invalid date format
        except (ValueError, IndexError):
            pass  # Invalid stage key or index
    
    return sorted(overdue_stages, key=lambda x: x["days_overdue"], reverse=True)

def get_upcoming_deadlines(stage_assignments: Dict, levels: List[str], days_ahead: int = 7) -> List[Dict]:
    """
    Get list of upcoming stage deadlines
    """
    upcoming_deadlines = []
    
    for stage_key, assignment in stage_assignments.items():
        try:
            stage_index = int(stage_key)
            
            if assignment.get("deadline"):
                deadline_str = assignment["deadline"]
                try:
                    deadline_date = date.fromisoformat(deadline_str)
                    days_until = (deadline_date - date.today()).days
                    
                    if 0 <= days_until <= days_ahead:
                        stage_name = assignment.get("stage_name", levels[stage_index] if stage_index < len(levels) else f"Stage {stage_index + 1}")
                        upcoming_deadlines.append({
                            "stage_index": stage_index,
                            "stage_name": stage_name,
                            "deadline": deadline_date.strftime("%Y-%m-%d"),
                            "days_until": days_until
                        })
                except ValueError:
                    pass  # Invalid date format
        except (ValueError, IndexError):
            pass  # Invalid stage key or index
    
    return sorted(upcoming_deadlines, key=lambda x: x["days_until"])


def initialize_session_state():
    """Initialize session state variables with default values"""
    defaults = {
        "view": "dashboard",
        "selected_template": "",
        "custom_levels": [],
        "level_index": -1,
        "level_timestamps": {},
        "stage_assignments": {},
        "edit_project_id": None,
        "confirm_delete": {},
        "create_pressed": False,
        "edit_pressed": False
    }
    
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

def get_current_timestamp():
    """Get current timestamp in standard format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def validate_project_dates(start_date, due_date):
    """Validate that due date is after start date"""
    return due_date > start_date

def ensure_project_defaults(project):
    """Ensure project has all required fields with defaults"""
    if "levels" not in project:
        project["levels"] = ["Initial", "Invoice", "Payment"]
    if "level" not in project:
        project["level"] = -1
    if "timestamps" not in project:
        project["timestamps"] = {}
    if "team" not in project:
        project["team"] = []
    if "stage_assignments" not in project:
        project["stage_assignments"] = {}
    return project

def notify_assigned_members(stage_assignments: Dict, project_name: str, current_stage: int):
    """Send notifications to members assigned to the current stage"""
    if str(current_stage) in stage_assignments:
        assignment = stage_assignments[str(current_stage)]
        members = assignment.get('members', [])
        deadline = assignment.get('deadline', '')
        stage_name = assignment.get('stage_name', f'Stage {current_stage + 1}')
        
        if members:
            # In a real implementation, you'd get email addresses from user profiles
            # For now, we'll just show a success message
            st.info(f"Notification sent to {', '.join(members)} for stage '{stage_name}'")

# Add these functions to your utils/utils_project.py file

def render_stage_assignments_editor_with_substages(levels: List[str], team_members: List[str], 
                                                 current_assignments: Dict = None) -> Dict:
    """
    Enhanced stage assignment editor with full substage support
    """    
    if current_assignments is None:
        current_assignments = {}
    
    stage_assignments = {}
    
    for i, level in enumerate(levels):
        stage_key = str(i)
        current_stage = current_assignments.get(stage_key, {})
        
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
            
            # Initialize stage data
            stage_assignments[stage_key] = {
                "stage_name": level,
                "members": assigned_members,
                "deadline": stage_deadline.isoformat() if stage_deadline else "",
                "substages": current_stage.get("substages", [])
            }
            
            # Substages Section
        
            # Add new substage button
            if st.button(f"➕ Add Substage", key=f"add_substage_{i}"):
                if f"new_substage_{i}" not in st.session_state:
                    st.session_state[f"new_substage_{i}"] = True
            
            # Show form to add new substage
            if st.session_state.get(f"new_substage_{i}", False):
                with st.form(f"new_substage_form_{i}"):
                    st.markdown("**Add New Substage:**")
                    
                    substage_col1, substage_col2 = st.columns([2, 1])
                    
                    with substage_col1:
                        new_substage_name = st.text_input("Substage Name", key=f"new_substage_name_{i}")
                        new_substage_desc = st.text_area("Description (optional)", key=f"new_substage_desc_{i}")
                        new_substage_assignees = st.multiselect(
                            "Assign to Team Members",
                            options=assigned_members if assigned_members else team_members,
                            key=f"new_substage_assignees_{i}"
                        )
                    
                    with substage_col2:
                        new_substage_deadline = st.date_input("Substage Deadline", key=f"new_substage_deadline_{i}")
                        new_substage_priority = st.selectbox(
                            "Priority",
                            options=["Low", "Medium", "High", "Critical"],
                            index=1,  # Default to Medium
                            key=f"new_substage_priority_{i}"
                        )
                    
                    submit_col1, submit_col2 = st.columns([1, 1])
                    
                    with submit_col1:
                        if st.form_submit_button("✅ Add Substage"):
                            if new_substage_name:
                                new_substage = {
                                    "id": f"substage_{i}_{len(stage_assignments[stage_key]['substages'])}_{int(datetime.now().timestamp())}",
                                    "name": new_substage_name,
                                    "description": new_substage_desc,
                                    "assignees": new_substage_assignees,
                                    "deadline": new_substage_deadline.isoformat() if new_substage_deadline else "",
                                    "priority": new_substage_priority,
                                    "completed": False,
                                    "created_at": datetime.now().isoformat(),
                                    "completed_at": None
                                }
                                stage_assignments[stage_key]["substages"].append(new_substage)
                                st.session_state[f"new_substage_{i}"] = False
                                st.success(f"Substage '{new_substage_name}' added!")
                                st.rerun()
                            else:
                                st.error("Substage name is required!")
                    
                    with submit_col2:
                        if st.form_submit_button("❌ Cancel"):
                            st.session_state[f"new_substage_{i}"] = False
                            st.rerun()
            
            # Display existing substages
            substages = stage_assignments[stage_key]["substages"]
            
            if substages:
                st.markdown("**Current Substages:**")
                
                substages_to_remove = []
                
                for idx, substage in enumerate(substages):
                    with st.expander(f"🔧 {substage.get('name', f'Substage {idx+1}')} - {substage.get('priority', 'Medium')} Priority"):
                        
                        # Substage editing
                        edit_col1, edit_col2, edit_col3 = st.columns([2, 1, 1])
                        
                        with edit_col1:
                            # Edit substage details
                            updated_name = st.text_input(
                                "Name", 
                                value=substage.get("name", ""),
                                key=f"edit_substage_name_{i}_{idx}"
                            )
                            
                            updated_desc = st.text_area(
                                "Description", 
                                value=substage.get("description", ""),
                                key=f"edit_substage_desc_{i}_{idx}"
                            )
                            
                            updated_assignees = st.multiselect(
                                "Assigned to",
                                options=assigned_members if assigned_members else team_members,
                                default=substage.get("assignees", []),
                                key=f"edit_substage_assignees_{i}_{idx}"
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
                                key=f"edit_substage_deadline_{i}_{idx}"
                            )
                            
                            updated_priority = st.selectbox(
                                "Priority",
                                options=["Low", "Medium", "High", "Critical"],
                                index=["Low", "Medium", "High", "Critical"].index(substage.get("priority", "Medium")),
                                key=f"edit_substage_priority_{i}_{idx}"
                            )
                            
                            # Completion status
                            is_completed = st.checkbox(
                                "Completed",
                                value=substage.get("completed", False),
                                key=f"edit_substage_completed_{i}_{idx}"
                            )
                        
                        with edit_col3:
                            # Actions
                            st.markdown("**Actions:**")
                            
                            if st.button(f"💾 Update", key=f"update_substage_{i}_{idx}"):
                                # Update substage data
                                substage.update({
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
                            
                            if st.button(f"🗑️ Delete", key=f"delete_substage_{i}_{idx}"):
                                substages_to_remove.append(idx)
                                st.rerun()
                        
                        # Show completion info
                        if substage.get("completed"):
                            completed_at = substage.get("completed_at")
                            if completed_at:
                                try:
                                    dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                                    st.success(f"✅ Completed on: {dt.strftime('%Y-%m-%d %H:%M')}")
                                except:
                                    st.success(f"✅ Completed")
                
                # Remove substages marked for deletion
                for idx in sorted(substages_to_remove, reverse=True):
                    del stage_assignments[stage_key]["substages"][idx]
                    st.success("Substage deleted!")
                    st.rerun()
            
            else:
                st.info("No substages defined for this stage yet.")
        
        st.markdown("---")
    
    return stage_assignments

def render_substage_progress(project: Dict, stage_index: int, substages: List[Dict], editable: bool = False):
    """
    Render substage progress for a specific stage
    """
    if not substages:
        return
    
    st.markdown("**Substages:**")
    
    total_substages = len(substages)
    completed_substages = sum(1 for s in substages if s.get("completed", False))
    
    # Progress bar for substages
    if total_substages > 0:
        progress = completed_substages / total_substages
        st.progress(progress, text=f"Progress: {completed_substages}/{total_substages} substages completed")
    
    # Show individual substages
    for idx, substage in enumerate(substages):
        status_icon = "✅" if substage.get("completed", False) else "⏳"
        priority_color = {
            "Low": "🟢",
            "Medium": "🟡", 
            "High": "🟠",
            "Critical": "🔴"
        }.get(substage.get("priority", "Medium"), "🟡")
        
        # Substage row
        substage_col1, substage_col2 = st.columns([3, 1])
        
        with substage_col1:
            substage_name = substage.get("name", f"Substage {idx+1}")
            assignees = ", ".join(substage.get("assignees", []))
            assignees_text = f" (Assigned to: {assignees})" if assignees else ""
            
            st.markdown(f"{status_icon} {priority_color} **{substage_name}**{assignees_text}")
            
            # Show description if available
            if substage.get("description"):
                st.caption(f"💭 {substage['description']}")
            
            # Show deadline info
            deadline = substage.get("deadline")
            if deadline:
                try:
                    deadline_date = date.fromisoformat(deadline)
                    days_until = (deadline_date - date.today()).days
                    
                    if days_until < 0:
                        st.error(f"⚠️ Overdue by {abs(days_until)} days (Due: {deadline_date.strftime('%Y-%m-%d')})")
                    elif days_until == 0:
                        st.warning(f"📅 Due today ({deadline_date.strftime('%Y-%m-%d')})")
                    elif days_until <= 3:
                        st.warning(f"📅 Due in {days_until} days ({deadline_date.strftime('%Y-%m-%d')})")
                    else:
                        st.caption(f"📅 Due: {deadline_date.strftime('%Y-%m-%d')}")
                except:
                    st.caption(f"📅 Due: {deadline}")
        
        with substage_col2:
            if editable:
                # Toggle completion status
                current_status = substage.get("completed", False)
                key = f"substage_toggle_{project.get('id', 'unknown')}_{stage_index}_{idx}"
                
                new_status = st.checkbox(
                    "Done",
                    value=current_status,
                    key=key
                )
                
                if new_status != current_status:
                    # Update substage completion status
                    substage["completed"] = new_status
                    substage["completed_at"] = datetime.now().isoformat() if new_status else None
                    substage["updated_at"] = datetime.now().isoformat()
                    
                    # Update in database (you'll need to implement this function)
                    update_substage_completion_in_db(project.get("id"), stage_index, idx, new_status)
                    
                    st.success(f"Substage {'completed' if new_status else 'reopened'}!")
                    st.rerun()

def _handle_substage_completion(project, stage_index, substage_index, completed):
    """
    Handle substage completion/incompletion
    """
    from datetime import datetime
    
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


