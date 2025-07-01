import streamlit as st
from datetime import datetime, date, timedelta
from utils.utils_project_core import send_stage_assignment_email
from backend.projects_backend import update_client_project_count

def create_project_data(name, client, description, start, due):
    """Create project data dictionary"""
    return {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "template": st.session_state.selected_template or "Custom",
        "levels": st.session_state.custom_levels.copy(),
        "level": st.session_state.level_index,
        "timestamps": st.session_state.level_timestamps.copy(),
        "stage_assignments": st.session_state.stage_assignments.copy(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "created_by": st.session_state.get("username", "unknown"),
    }


def create_updated_project_data(project, name, client, description, start, due, stage_assignments):
    """Create updated project data dictionary including substage data"""
    updated_data = {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "stage_assignments": stage_assignments,
        "updated_at": datetime.now().isoformat(),
        "created_at": project.get("created_at", datetime.now().isoformat()),
        "levels": project.get("levels", ["Initial", "Invoice", "Payment"]),
        "level": project.get("level", -1),
        "timestamps": project.get("timestamps", {})
    }
    
    # Include substage completion data if it exists
    if "substage_completion" in project:
        updated_data["substage_completion"] = project["substage_completion"]
    if "substage_timestamps" in project:
        updated_data["substage_timestamps"] = project["substage_timestamps"]
    
    return updated_data

def _reset_create_form_state():
    """Reset create form state variables"""
    st.session_state.level_index = -1
    st.session_state.level_timestamps = {}
    st.session_state.custom_levels = []
    st.session_state.selected_template = ""
    st.session_state.view = "dashboard"

def _update_client_counts_after_edit(project, new_client):
    """Update client project counts after editing"""
    # Update new client count
    update_client_project_count(new_client)
    
    # Update old client count if client was changed
    old_client = project.get("client", "")
    if new_client != old_client:
        update_client_project_count(old_client)

def _display_success_messages(messages):
    """Display success messages"""
    if messages:
        for message in messages:
            st.success(message)
    else:
        st.success("Changes saved to database!")

def send_stage_assignment_notifications(project):
    """Send notifications for stage assignments in new project"""
    stage_assignments = project.get("stage_assignments", {})
    project_name = project.get("name", "Unnamed")
    
    for stage_index, assignment in stage_assignments.items():
        members = assignment.get("members", [])
        deadline = assignment.get("deadline", "")
        stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
        
        if members:
            # In a real implementation, you'd get email addresses from user profiles
            # For now, we'll use the send_stage_assignment_email function from utils
            member_emails = [f"{member}@company.com" for member in members]  # Mock email addresses
            send_stage_assignment_email(member_emails, project_name, stage_name, deadline)

def _send_stage_assignment_change_notifications(new_assignments, old_assignments, project_name):
    """Send notifications when stage assignments change"""
    # Compare old and new assignments to find changes
    for stage_index, assignment in new_assignments.items():
        old_assignment = old_assignments.get(stage_index, {})
        new_members = set(assignment.get("members", []))
        old_members = set(old_assignment.get("members", []))
        
        # Find newly assigned members
        newly_assigned = new_members - old_members
        if newly_assigned:
            deadline = assignment.get("deadline", "")
            stage_name = assignment.get("stage_name", f"Stage {int(stage_index) + 1}")
            member_emails = [f"{member}@company.com" for member in newly_assigned]
            send_stage_assignment_email(member_emails, project_name, stage_name, deadline)

def _handle_email_reminders(project, pid, levels, current_level):
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

def _check_dashboard_success_messages(pid):
    """Check and display dashboard success messages"""
    if st.session_state.get(f"level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

def _check_edit_success_messages(pid):
    """Check and display edit form success messages"""
    if st.session_state.get(f"edit_level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"edit_level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False
