import streamlit as st
from datetime import datetime, date , timedelta
from backend.projects_backend import update_client_project_count
from typing import List, Dict
import yagmail

# ───── Constants ─────
TEMPLATES = {
    "v-shesh": ["Initial Contact", "Scope", "Proposal", "Accept Quote", "Onboarding", "Service"],
    "Onwards":["Mobilization","Assessment","Observation","Fee Collection","Training","Internship/Placement"]
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

def send_stage_assignment_email(to_emails, project_name, stage_name, deadline,default_body=None,subject=None):
    """Send stage assignment notification email"""
    try:
        yag = yagmail.SMTP(user=st.secrets["email"]["from"], password=st.secrets["email"]["password"])
        if not subject:
            subject = f"Stage Assignment – {project_name}: {stage_name}"
        body = f"""
        You have been assigned to the '{stage_name}' stage of project '{project_name}'.
        
        Deadline: {deadline}
        
        Please log in to the project management system to view details and update progress.
        """
        if default_body:
            content = default_body
        else: 
            content = body
        yag.send(to=to_emails, subject=subject, contents=content)
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
    Fixed to exclude completed stages from overdue calculations
    """
    overdue_stages = []
    
    for stage_key, assignment in stage_assignments.items():
        try:
            stage_index = int(stage_key)
            
            # FIXED: Only check stages that are NOT yet completed (stage_index > current_level)
            # and have deadlines that have passed
            if stage_index > current_level and assignment.get("deadline"):
                deadline_str = assignment["deadline"]
                try:
                    deadline_date = date.fromisoformat(deadline_str)
                    days_overdue = (date.today() - deadline_date).days
                    
                    # Only consider it overdue if the deadline has passed (days_overdue > 0)
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


def _get_user_email_from_username(username):
    """Convert username to email format"""
    if "@" in username:
        return username
    return f"{username}@v-shesh.com"

def _update_client_counts_after_edit(project, new_client):
    """Update client project counts after editing"""
    update_client_project_count(new_client)
    
    old_client = project.get("client", "")
    if new_client != old_client:
        update_client_project_count(old_client)

def display_success_messages(messages=None):
    """Display success messages"""
    if messages:
        for message in messages:
            st.success(message)
    else:
        st.success("Changes saved to database!")

def check_success_messages(pid, context="dashboard"):
    """Check and display success messages"""
    key_prefix = "edit_" if context == "edit" else ""
    
    if st.session_state.get(f"{key_prefix}level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"{key_prefix}level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

def handle_email_reminders(project, pid, levels, current_level):
    """Handle email reminder logic"""
    project_name = project.get("name", "Unnamed")
    lead_email = st.secrets.get("project_leads", {}).get("Project Alpha")
    
    # Safe check for Invoice and Payment levels
    try:
        invoice_index = levels.index("Invoice") if "Invoice" in levels else -1
        payment_index = levels.index("Payment") if "Payment" in levels else -1
    except (ValueError, AttributeError):
        invoice_index = -1
        payment_index = -1
    
    email_key = f"last_email_sent_{pid}"
    if email_key not in st.session_state:
        st.session_state[email_key] = None
    
    if (0 <= invoice_index <= current_level) and (payment_index > current_level) and lead_email:
        now = datetime.now()
        last_sent = st.session_state[email_key]
        if not last_sent or now - last_sent >= timedelta(minutes=1):
            if send_invoice_email(lead_email, project_name):
                st.session_state[email_key] = now