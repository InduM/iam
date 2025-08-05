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


def calculate_status(start_date_str: str, stage_deadline_str: str, 
                    substage_deadline_str: str, is_completed: bool = False) -> str:
    """Calculate project status based on dates and completion"""
    if is_completed:
        return "Completed"
    
    try:
        # Parse dates - handle both string formats from your DB
        if isinstance(start_date_str, str):
            if len(start_date_str) == 10:  # Format: 2025-05-05
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:  # Format: 2025-07-01 14:28:43
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S").date()
        else:
            start_date = start_date_str
        
        # Parse stage deadline
        if stage_deadline_str and stage_deadline_str.strip():
            if len(stage_deadline_str) == 10:
                stage_deadline = datetime.strptime(stage_deadline_str, "%Y-%m-%d").date()
            else:
                stage_deadline = datetime.strptime(stage_deadline_str, "%Y-%m-%d %H:%M:%S").date()
        else:
            stage_deadline = None
        
        # Parse substage deadline
        substage_deadline = None
        if substage_deadline_str and substage_deadline_str.strip():
            if len(substage_deadline_str) == 10:
                substage_deadline = datetime.strptime(substage_deadline_str, "%Y-%m-%d").date()
            else:
                substage_deadline = datetime.strptime(substage_deadline_str, "%Y-%m-%d %H:%M:%S").date()
        
        current_date = date.today()
        
        # Use the earlier deadline (stage or substage) if both exist
        if stage_deadline and substage_deadline:
            effective_deadline = min(stage_deadline, substage_deadline)
        elif substage_deadline:
            effective_deadline = substage_deadline
        elif stage_deadline:
            effective_deadline = stage_deadline
        else:
            return "No Deadline Set"
        
        if current_date > effective_deadline:
            return "Overdue"
        elif start_date <= current_date <= effective_deadline:
            return "In Progress"
        elif start_date > current_date:
            return "Upcoming"
        else:
            return "Unknown"
            
    except Exception as e:
        st.error(f"Date parsing error: {str(e)}")
        return "Error"

def format_status_badge(status: str) -> str:
    """Format status with colored badges"""
    colors = {
        "Completed": "🟢",
        "In Progress": "🟡",
        "Overdue": "🔴",
        "Upcoming": "🔵",
        "No Deadline Set": "⚪",
        "Error": "❌"
    }
    return f"{colors.get(status, '⚪')}{status}"

def format_priority_badge(priority: str) -> str:
    """Format priority with colored badges"""
    colors = {
        "High": "🔥",
        "Medium": "🟡",
        "Low": "🟢"
    }
    return f"{colors.get(priority, '⚪')} {priority}"

def format_datetime(dt) -> str:
    """Format datetime object for display"""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M')
    return str(dt)

def format_date(date_str: str) -> str:
    """Format date string for display"""
    if not date_str or date_str.strip() == "":
        return "Not Set"
    return date_str

def get_project_progress(total_tasks: int, completed_tasks: int) -> dict:
    """Calculate project progress statistics"""
    if total_tasks == 0:
        return {
            "progress": 0.0,
            "percentage": "0.0%",
            "completion_text": "0/0 tasks completed"
        }
    
    progress = completed_tasks / total_tasks
    percentage = f"{progress:.1%}"
    completion_text = f"{completed_tasks}/{total_tasks} tasks completed"
    
    return {
        "progress": progress,
        "percentage": percentage,
        "completion_text": completion_text
    }

def filter_logs(logs: list, status_filter: list, priority_filter: list, project_filter: list = None) -> list:
    """Filter logs based on multiple criteria"""
    filtered_logs = []
    
    for log in logs:
        # Check status filter
        if log["status"] not in status_filter:
            continue
            
        # Check priority filter
        if log.get("priority", "Medium") not in priority_filter:
            continue
            
        # Check project filter (if provided)
        if project_filter and log["project_name"] not in project_filter:
            continue
            
        filtered_logs.append(log)
    
    return filtered_logs

def get_unique_values(logs: list, field: str, default_value: str = None) -> list:
    """Get unique values from a list of logs for a specific field"""
    values = set()
    
    for log in logs:
        value = log.get(field, default_value)
        if value:
            values.add(value)
    
    return sorted(list(values))

def validate_date_format(date_string: str) -> bool:
    """Validate if a date string is in the expected format"""
    if not date_string or date_string.strip() == "":
        return True  # Empty dates are valid
    
    try:
        if len(date_string) == 10:  # Format: 2025-05-05
            datetime.strptime(date_string, "%Y-%m-%d")
            return True
        else:  # Format: 2025-07-01 14:28:43
            datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            return True
    except ValueError:
        return False

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length with ellipsis"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + "..."

def get_task_counts_by_status(logs: list) -> dict:
    """Get task counts grouped by status"""
    counts = {}
    
    for log in logs:
        status = log.get("status", "Unknown")
        counts[status] = counts.get(status, 0) + 1
    
    return counts

def get_task_counts_by_priority(logs: list) -> dict:
    """Get task counts grouped by priority"""
    counts = {}
    
    for log in logs:
        priority = log.get("priority", "Medium")
        counts[priority] = counts.get(priority, 0) + 1
    
    return counts

def calculate_stage_progress(stage_logs: list) -> dict:
    """Calculate progress statistics for a stage"""
    total = len(stage_logs)
    completed = sum(1 for log in stage_logs if log.get('is_completed', False))
    
    return {
        'total': total,
        'completed': completed,
        'progress': completed / total if total > 0 else 0,
        'percentage': f"{(completed / total * 100):.1f}%" if total > 0 else "0%"
    }

def sort_logs(logs: list, sort_by: str = "updated_at", ascending: bool = False) -> list:
    """Sort logs by a specific field"""
    reverse = not ascending
    
    try:
        if sort_by in ["created_at", "updated_at", "completed_at"]:
            # Sort by datetime fields
            return sorted(logs, 
                         key=lambda x: x.get(sort_by, datetime.min) if x.get(sort_by) else datetime.min, 
                         reverse=reverse)
        else:
            # Sort by string fields
            return sorted(logs, 
                         key=lambda x: x.get(sort_by, ""), 
                         reverse=reverse)
    except Exception as e:
        st.error(f"Error sorting logs: {str(e)}")
        return logs