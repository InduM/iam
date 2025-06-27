import streamlit as st
from datetime import datetime
from typing import List
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

def render_level_checkboxes(prefix, project_id, current_level, timestamps, levels, on_change_fn=None, editable=True):
    """Render interactive level checkboxes"""
    for i, label in enumerate(levels):
        key = f"{prefix}_{project_id}_level_{i}"
        checked = i <= current_level and current_level >= 0
        disabled = not editable or i > current_level + 1 or (i < current_level and i != current_level)
        display_label = f"{label}"
        if checked and str(i) in timestamps:
            display_label += f" ⏱️ {timestamps[str(i)]}"

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

def initialize_session_state():
    """Initialize session state variables with default values"""
    defaults = {
        "view": "dashboard",
        "selected_template": "",
        "custom_levels": [],
        "level_index": -1,
        "level_timestamps": {},
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
    return project