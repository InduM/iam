import streamlit as st
from datetime import datetime, date, timedelta


def create_default_log():
    """Create a default log entry with current time"""
    return {
        "Time": datetime.now().strftime("%H:%M"),
        "Project Name": "",
        "Client Name": "",
        "Priority": "",
        "Description": "",
        "Category": "",
        "Status": "",
        "Follow up": ""
    }


def get_date_constraints():
    """Get date constraints for log entry (current week and previous week)"""
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_prev_week = start_of_week - timedelta(days=7)
    end_of_week = start_of_week + timedelta(days=6)
    
    return {
        "today": today,
        "start_of_prev_week": start_of_prev_week,
        "end_of_week": end_of_week
    }


def can_add_log_for_date(selected_date):
    """Check if user can add logs for the selected date"""
    date_constraints = get_date_constraints()
    return (date_constraints["start_of_prev_week"] <= 
            selected_date <= 
            date_constraints["end_of_week"])


def initialize_session_state():
    """Initialize required session state variables"""
    if "last_selected_date" not in st.session_state:
        st.session_state.last_selected_date = None
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "refresh_triggered" not in st.session_state:
        st.session_state.refresh_triggered = False
    if "client_selections" not in st.session_state:
        st.session_state.client_selections = {}


def ensure_log_fields(log):
    """Ensure all required fields exist in log with default values"""
    default_log = create_default_log()
    for key in default_log:
        if key not in log:
            log[key] = default_log[key]
    return log


def get_log_columns():
    """Get log column definitions"""
    return [
        ("Time", 200), ("Project Name", 200), ("Client Name", 200), ("Priority", 200),
        ("Description", 200), ("Category", 300), ("Status", 150), ("Follow up", 300)
    ]


def get_category_options():
    """Get category options for logs"""
    return [
        "Audit-Physical", "Audit-Digital", "Audit-Design", "Audit-Accessibility",
        "Audit-Policy", "Training-Onwards", "Training-Regular", "Sessions-Kiosk",
        "Sessions-Sensitization", "Sessions-Awareness", "Recruitment", "Other"
    ]


def get_priority_options():
    """Get priority options for logs"""
    return ["Low", "Medium", "High"]


def get_status_options():
    """Get status options for logs"""
    return ["", "Completed", "InProgress", "Incomplete"]


def format_log_summary(log):
    """Format log summary for expander title"""
    time = log.get('Time', '--')
    project = log.get('Project Name', 'No Project')
    status = log.get('Status', '') or 'No Status'
    return f"{time} | {project} | {status}"


def display_spoc_info(col_widget, client_dict, selected_client):
    """Display SPOC information for selected client"""
    if selected_client and selected_client in client_dict:
        client_info = client_dict[selected_client]
        spoc_name = client_info.get("spoc_name", "")
        spoc_email = client_info.get("email", "")
        spoc_phone = client_info.get("phone_number", "")
        
        if spoc_name or spoc_email or spoc_phone:
            display_string = []
            col_widget.markdown("**📞 SPOC Details:**")
            if spoc_name:
                display_string.append(f"**👤 Name:** {spoc_name}")
            if spoc_email:
                display_string.append(f"**📧 Email:** {spoc_email}")
            if spoc_phone:
                display_string.append(f"**📱 Phone:** {spoc_phone}")
            col_widget.info('\n'.join(display_string))
        else:
            col_widget.warning("⚠️ No SPOC information available for this client")