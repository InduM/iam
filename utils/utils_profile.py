import base64
from datetime import datetime


def decode_base64_image(data):
    return base64.b64decode(data) if data else None

def calculate_project_progress(project_data):
    """Calculate project progress based on current level and total levels"""
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

def get_substage_completion_status(project_data, stage_idx, substage_idx):
    """Check if a substage is completed"""
    completion_data = project_data.get('substage_completion', {})
    stage_completion = completion_data.get(str(stage_idx), {})
    return stage_completion.get(str(substage_idx), False)

def get_substage_timestamp(project_data, stage_idx, substage_idx):
    """Get the completion timestamp for a substage"""
    timestamp_data = project_data.get('substage_timestamps', {})
    stage_timestamps = timestamp_data.get(str(stage_idx), {})
    return stage_timestamps.get(str(substage_idx), None)
