import streamlit as st
from datetime import datetime
import pandas as pd

# Configure page
st.set_page_config(
    page_title="Create New Project",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-friendly design
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .stCheckbox {
        padding: 0.5rem 0;
    }
    
    .level-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.8rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007acc;
    }
    
    .completed-level {
        background-color: #d4edda;
        border-left-color: #28a745;
    }
    
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    @media (max-width: 768px) {
        .stContainer {
            padding: 0.5rem;
        }
        
        .level-container {
            padding: 0.8rem;
            margin: 0.3rem 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'project_name' not in st.session_state:
    st.session_state.project_name = ""

if 'project_description' not in st.session_state:
    st.session_state.project_description = ""

if 'levels' not in st.session_state:
    st.session_state.levels = {
        1: {"name": "Planning & Research", "completed": False, "timestamp": None},
        2: {"name": "Design & Architecture", "completed": False, "timestamp": None},
        3: {"name": "Development Setup", "completed": False, "timestamp": None},
        4: {"name": "Core Implementation", "completed": False, "timestamp": None},
        5: {"name": "Testing & Quality Assurance", "completed": False, "timestamp": None},
        6: {"name": "Deployment & Integration", "completed": False, "timestamp": None},
        7: {"name": "Documentation & Handover", "completed": False, "timestamp": None}
    }

if 'history' not in st.session_state:
    st.session_state.history = []

if 'show_warning' not in st.session_state:
    st.session_state.show_warning = False

if 'warning_message' not in st.session_state:
    st.session_state.warning_message = ""

def get_current_level():
    """Get the current highest completed level"""
    for level in range(7, 0, -1):
        if st.session_state.levels[level]["completed"]:
            return level
    return 0

def get_next_available_level():
    """Get the next level that can be checked"""
    current = get_current_level()
    return current + 1 if current < 7 else None

def can_check_level(level):
    """Check if a level can be checked (sequential enforcement)"""
    current = get_current_level()
    return level == current + 1

def can_uncheck_level(level):
    """Check if a level can be unchecked (must be the highest completed level)"""
    current = get_current_level()
    return level == current and current > 0

def update_level(level, checked):
    """Update level status and record history"""
    old_status = st.session_state.levels[level]["completed"]
    
    if checked and not old_status:
        # Checking a level
        if can_check_level(level):
            st.session_state.levels[level]["completed"] = True
            timestamp = datetime.now()
            st.session_state.levels[level]["timestamp"] = timestamp
            
            # Record history
            st.session_state.history.append({
                "action": "completed",
                "level": level,
                "level_name": st.session_state.levels[level]["name"],
                "timestamp": timestamp,
                "previous_level": get_current_level() - 1 if get_current_level() > 1 else None
            })
            
            st.session_state.show_warning = False
            st.success(f"✅ Level {level}: {st.session_state.levels[level]['name']} completed!")
        else:
            st.session_state.show_warning = True
            next_level = get_next_available_level()
            if next_level:
                st.session_state.warning_message = f"⚠️ You must complete levels sequentially. Next available level is {next_level}: {st.session_state.levels[next_level]['name']}"
            else:
                st.session_state.warning_message = "⚠️ All levels are already completed!"
    
    elif not checked and old_status:
        # Unchecking a level
        if can_uncheck_level(level):
            st.session_state.levels[level]["completed"] = False
            old_timestamp = st.session_state.levels[level]["timestamp"]
            st.session_state.levels[level]["timestamp"] = None
            
            # Record history
            st.session_state.history.append({
                "action": "unchecked",
                "level": level,
                "level_name": st.session_state.levels[level]["name"],
                "timestamp": datetime.now(),
                "previous_timestamp": old_timestamp
            })
            
            st.session_state.show_warning = False
            st.info(f"ℹ️ Level {level}: {st.session_state.levels[level]['name']} unchecked")
        else:
            st.session_state.show_warning = True
            st.session_state.warning_message = f"⚠️ You can only uncheck the highest completed level. Complete levels in sequence first."

# Header
st.title("📊 Create New Project")
st.markdown("---")

# Project Information Section
st.header("Project Information")

# Project name and description in a clean layout
st.session_state.project_name = st.text_input(
    "Project Name",
    value=st.session_state.project_name,
    placeholder="Enter your project name...",
    help="Give your project a descriptive name"
)

st.session_state.project_description = st.text_area(
    "Project Description",
    value=st.session_state.project_description,
    placeholder="Describe your project goals, scope, and objectives...",
    height=100,
    help="Provide details about what this project aims to achieve"
)

st.markdown("---")

# Progress Tracking Section
st.header("🎯 Project Progress Levels")

# Show warning if needed
if st.session_state.show_warning:
    st.markdown(f'<div class="warning-box">{st.session_state.warning_message}</div>', unsafe_allow_html=True)

st.markdown("### Progress Levels")

# Display levels without nested columns
for level in range(1, 8):
    level_data = st.session_state.levels[level]
    is_completed = level_data["completed"]
    timestamp = level_data["timestamp"]
    
    # Create container for each level
    container_class = "completed-level" if is_completed else "level-container"
    
    with st.container():
        st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
        
        # Level header and checkbox
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"**Level {level}: {level_data['name']}**")
            if timestamp:
                st.markdown(f"*Completed: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")
        
        with col2:
            # Create unique key for each checkbox
            checkbox_key = f"level_{level}_checkbox"
            
            # Handle checkbox state change
            new_state = st.checkbox(
                "Complete",
                value=is_completed,
                key=checkbox_key,
                help=f"Mark Level {level} as complete"
            )
            
            # Check if state changed
            if new_state != is_completed:
                update_level(level, new_state)
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# History Section
if st.session_state.history:
    st.header("📈 Progress History")
    
    # Create a DataFrame for better display
    history_data = []
    for entry in st.session_state.history:
        history_data.append({
            "Action": "✅ Completed" if entry["action"] == "completed" else "❌ Unchecked",
            "Level": f"Level {entry['level']}",
            "Level Name": entry["level_name"],
            "Timestamp": entry["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
        })
    
    if history_data:
        df = pd.DataFrame(history_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

# Project Summary
st.markdown("---")
st.header("📋 Project Summary")

if st.session_state.project_name:
    completed_count = sum(1 for level in st.session_state.levels.values() if level["completed"])
    progress_percentage = (completed_count / 7) * 100
    
    summary_col1, summary_col2 = st.columns(2)
    
    with summary_col1:
        st.metric("Project Name", st.session_state.project_name)
        st.metric("Completed Levels", f"{completed_count}/7")
    
    with summary_col2:
        st.metric("Progress", f"{progress_percentage:.1f}%")
        if completed_count > 0:
            last_completed = max([level for level, data in st.session_state.levels.items() if data["completed"]])
            st.metric("Latest Milestone", f"Level {last_completed}")

    # Progress bar
    st.progress(progress_percentage / 100)
else:
    st.info("👆 Enter a project name above to see the project summary")

# Footer
st.markdown("---")
st.markdown("*Levels must be completed sequentially. You can only uncheck the highest completed level.*")