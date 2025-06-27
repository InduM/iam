import streamlit as st
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import yagmail

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
    """Validate stage assignments and return list of issues"""
    issues = []
    
    for i, level in enumerate(levels):
        if str(i) in stage_assignments:
            assignment = stage_assignments[str(i)]
            deadline = assignment.get('deadline', '')
            
            # Check if deadline is in the past
            if deadline:
                try:
                    deadline_date = date.fromisoformat(deadline)
                    if deadline_date < date.today():
                        issues.append(f"Stage '{level}' deadline is in the past")
                except:
                    issues.append(f"Stage '{level}' has invalid deadline format")
    
    return issues

def get_overdue_stages(stage_assignments: Dict, levels: List[str], current_level: int) -> List[Dict]:
    """Get list of overdue stages"""
    overdue = []
    today = date.today()
    
    for i in range(current_level + 1):  # Only check current and previous stages
        if str(i) in stage_assignments:
            assignment = stage_assignments[str(i)]
            deadline = assignment.get('deadline', '')
            
            if deadline:
                try:
                    deadline_date = date.fromisoformat(deadline)
                    if deadline_date < today:
                        overdue.append({
                            'stage_index': i,
                            'stage_name': levels[i] if i < len(levels) else f"Stage {i+1}",
                            'deadline': deadline,
                            'days_overdue': (today - deadline_date).days,
                            'assigned_members': assignment.get('members', [])
                        })
                except:
                    pass
    
    return overdue

def get_upcoming_deadlines(stage_assignments: Dict, levels: List[str], days_ahead: int = 7) -> List[Dict]:
    """Get stages with deadlines in the next N days"""
    upcoming = []
    today = date.today()
    cutoff_date = today + timedelta(days=days_ahead)
    
    for i, assignment in stage_assignments.items():
        deadline = assignment.get('deadline', '')
        
        if deadline:
            try:
                deadline_date = date.fromisoformat(deadline)
                if today <= deadline_date <= cutoff_date:
                    stage_index = int(i)
                    upcoming.append({
                        'stage_index': stage_index,
                        'stage_name': levels[stage_index] if stage_index < len(levels) else f"Stage {stage_index+1}",
                        'deadline': deadline,
                        'days_until': (deadline_date - today).days,
                        'assigned_members': assignment.get('members', [])
                    })
            except:
                pass
    
    return sorted(upcoming, key=lambda x: x['days_until'])

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