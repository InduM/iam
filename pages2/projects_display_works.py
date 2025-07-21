import streamlit as st
from datetime import datetime
import time

from backend.projects_backend import (
    update_substage_completion_in_db,
)
from utils.utils_project_core import (
    format_level,
    get_current_timestamp,
    get_overdue_stages,
)
from utils.utils_project_substage import (
    render_substage_summary_widget,
)
from .project_logic import (
    _are_all_substages_complete, 
    handle_level_change,
    _handle_project_deletion,
)
from .project_completion import(
    _auto_advance_main_stage,
    _auto_uncheck_main_stage,
    _has_substages,
)
# Helper Functions
def _detect_form_context(project_id):
    """Centralized form context detection"""
    return (project_id == "new" or 
            not project_id or 
            project_id.startswith("auto_") or
            project_id.startswith("form_"))

def _validate_sequential_access(current_index, target_index, max_completed, is_advance=True):
    """Centralized sequential validation logic"""
    if is_advance:
        return target_index == max_completed + 1
    else:
        return target_index == max_completed

def _get_completion_status(project, stage_key, substage_idx, is_form_context):
    """Centralized completion status retrieval"""
    if is_form_context:
        substage_completion = st.session_state.get("substage_completion", {})
    else:
        substage_completion = project.get("substage_completion", {}) if project else {}
    
    current_completion = substage_completion.get(stage_key, {})
    return current_completion.get(str(substage_idx), False)

def _handle_timestamp_update(project, project_id, stage_key, substage_idx, completed, is_form_context):
    """Centralized timestamp handling for both form and database contexts"""
    timestamp = get_current_timestamp() if completed else None
    
    if is_form_context:
        # Handle session state timestamps
        if "substage_timestamps" not in st.session_state:
            st.session_state.substage_timestamps = {}
        if stage_key not in st.session_state.substage_timestamps:
            st.session_state.substage_timestamps[stage_key] = {}
        
        if completed:
            st.session_state.substage_timestamps[stage_key][str(substage_idx)] = timestamp
        else:
            # Remove timestamp when unchecked
            if str(substage_idx) in st.session_state.substage_timestamps[stage_key]:
                del st.session_state.substage_timestamps[stage_key][str(substage_idx)]
    else:
        # Handle project timestamps
        if project:
            timestamp_key = "substage_timestamps"
            if timestamp_key not in project:
                project[timestamp_key] = {}
            if stage_key not in project[timestamp_key]:
                project[timestamp_key][stage_key] = {}
            
            if completed:
                project[timestamp_key][stage_key][str(substage_idx)] = timestamp
            else:
                # Remove timestamp when unchecked
                if str(substage_idx) in project[timestamp_key][stage_key]:
                    del project[timestamp_key][stage_key][str(substage_idx)]

def _update_substage_completion(project, project_id, stage_key, substage_idx, completed, is_form_context):
    """Centralized substage completion update"""
    if is_form_context:
        # Update session state
        if "substage_completion" not in st.session_state:
            st.session_state.substage_completion = {}
        if stage_key not in st.session_state.substage_completion:
            st.session_state.substage_completion[stage_key] = {}
        
        st.session_state.substage_completion[stage_key][str(substage_idx)] = completed
    else:
        # Update project data
        if project:
            if "substage_completion" not in project:
                project["substage_completion"] = {}
            if stage_key not in project["substage_completion"]:
                project["substage_completion"][stage_key] = {}
            
            project["substage_completion"][stage_key][str(substage_idx)] = completed
            
            # Update database for existing projects
            update_substage_completion_in_db(project_id, project["substage_completion"])

def _render_two_column_layout(left_content, right_content, left_ratio=1, right_ratio=3):
    """Reusable two-column layout"""
    col1, col2 = st.columns([left_ratio, right_ratio])
    with col1:
        left_content()
    with col2:
        right_content()

def _show_sequential_error(is_advance=True, is_substage=False):
    """Centralized sequential error messages"""
    if is_substage:
        if is_advance:
            st.error("❌ Complete substages sequentially!")
        else:
            st.error("❌ You can only uncheck the last completed substage!")
    else:
        if is_advance:
            st.error("❌ You can only advance to the next stage sequentially!")
        else:
            st.error("❌ You can only go back one stage at a time!")
    
    time.sleep(0.1)
    st.rerun()

def _render_completion_timestamp(timestamp, is_compact=False):
    """Centralized timestamp rendering"""
    if not timestamp:
        return
    
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if is_compact:
            st.caption(f"{dt.strftime('%m/%d %H:%M')}")
        else:
            st.caption(f"Completed: {dt.strftime('%Y-%m-%d %H:%M')}")
    except:
        st.caption(f"Completed: {timestamp}")

# Main Functions
def render_project_card(project, index):
    """Render individual project card with substage validation"""
    pid = project.get("id", f"auto_{index}")
    
    with st.expander(f"{project.get('name', 'Unnamed')}"):
        # Mobile-first layout with better spacing
        st.markdown(f"**Client:** {project.get('client', '-')}")
        st.markdown(f"**Description:** {project.get('description', '-')}")
        
        # Date information in mobile-friendly format
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Start:** {project.get('startDate', '-')}")
        with col2:
            st.markdown(f"**Due:** {project.get('dueDate', '-')}")
        
        st.markdown(f"**Manager:** {project.get('created_by', '-')}")
        
        levels = project.get("levels", ["Initial", "Invoice", "Payment"])
        current_level = project.get("level", -1)
        st.markdown(f"**📊 Current Level:** {format_level(current_level, levels)}")
        
        # Show stage assignments summary
        stage_assignments = project.get("stage_assignments", {})
        
        # Show substage completion summary
        render_substage_summary_widget(project)
        
        # Mobile-optimized overdue stages display
        overdue_stages = get_overdue_stages(stage_assignments, levels, current_level)
        if overdue_stages:
            active_overdue_stages = []
            for overdue in overdue_stages:
                stage_index = None
                for i, level in enumerate(levels):
                    if level == overdue.get('stage_name') or overdue.get('stage_name') == f"Stage {i+1}":
                        stage_index = i
                        break
                
                if stage_index is not None and stage_index > current_level:
                    active_overdue_stages.append(overdue)
            
            if active_overdue_stages:
                st.error("🔴 **Overdue Stages:**")
                for overdue in active_overdue_stages:
                    st.error(f"📍 {overdue['stage_name']}: {overdue['days_overdue']} days")
        
        # Level checkboxes with mobile optimization
        def on_change_dashboard(new_index, proj_id=pid, proj=project):
            if new_index > project.get("level", -1):
                if not _are_all_substages_complete(project, stage_assignments, new_index):
                    st.error("❌ Complete all substages first!")
                    return
            
            handle_level_change(proj,proj_id, new_index, stage_assignments,"dashboard")
        
    
        
        # Auto-advance and auto-uncheck messages
        for i in range(len(levels)):
            auto_advance_key = f"auto_advance_success_{pid}_{i}"
            if st.session_state.get(auto_advance_key, False):
                st.success(f"🎉 Stage {i + 1} completed!")
                st.session_state[auto_advance_key] = False
            
            auto_uncheck_key = f"auto_uncheck_success_{pid}_{i}"
            if st.session_state.get(auto_uncheck_key, False):
                st.warning(f"⚠️ Stage {i + 1} unchecked!")
                st.session_state[auto_uncheck_key] = False
        
        render_level_checkboxes_with_substages(
            "view", pid, int(project.get("level", -1)), 
            project.get("timestamps", {}), levels, on_change_dashboard, 
            editable=True, stage_assignments=stage_assignments, project=project
        )
        
        # Email reminder logic####IMPORTANT ::: IMplement it later
        #_handle_email_reminders(project, pid, levels, current_level)
        
        # Mobile-friendly action buttons
        _render_project_action_buttons(project, pid)

def render_level_checkboxes_with_substages(context, project_id, current_level, timestamps, levels, 
                                         on_change, editable=False, stage_assignments=None, project=None):
    """Enhanced level checkboxes that also show substages with validation"""
    if not levels:
        st.warning("No levels defined for this project.")
        return
    
    is_form_context = _detect_form_context(project_id)
    
    for i, level in enumerate(levels):
        # Create container for stage and its substages
        stage_container = st.container()
        
        with stage_container:
            def render_main_stage():
                # Main stage checkbox
                is_checked = i <= current_level
                key = f"{context}_{project_id}_level_{i}"
                
                # Check if all substages are completed for this stage
                substages_complete = _are_all_substages_complete(project, stage_assignments, i)
                can_check_stage = substages_complete or not _has_substages(stage_assignments, i)
                
                # Sequential checking logic
                can_advance_sequentially = _validate_sequential_access(current_level, i, current_level, True)
                can_go_back_sequentially = _validate_sequential_access(current_level, i, current_level, False)
                
                if editable:
                    checked = st.checkbox(
                        f"**{i+1}. {level}**",
                        value=is_checked,
                        key=key,
                        disabled=False
                    )
                    
                    # Handle state change with sequential validation
                    if checked != is_checked:
                        if checked:
                            # Trying to check a stage
                            if not can_advance_sequentially:
                                _show_sequential_error(True, False)
                            elif not can_check_stage:
                                st.error("❌ Complete all substages first before advancing to this stage!")
                                time.sleep(0.1)
                                st.rerun()
                            else:
                                # Valid advance
                                if on_change:
                                    on_change(i)
                        else:
                            # Trying to uncheck a stage
                            if not can_go_back_sequentially:
                                _show_sequential_error(False, False)
                            else:
                                # Valid go back
                                if on_change:
                                    on_change(i - 1)
                    
                    # Show status messages
                    if not can_check_stage and not is_checked:
                        st.caption("⚠️ Complete all substages first")
                    elif not can_advance_sequentially and not is_checked:
                        st.caption("🔒 Complete previous stages first")
                    elif not can_go_back_sequentially and is_checked and i < current_level:
                        st.caption("🔒 Completed stage")
                        
                else:
                    status = "✅" if is_checked else "⏳"
                    st.markdown(f"{status} **{i+1}. {level}**")
            
            def render_timestamp():
                # Show timestamp if available
                if str(i) in timestamps:
                    timestamp = timestamps[str(i)]
                    _render_completion_timestamp(timestamp)
            
            _render_two_column_layout(render_main_stage, render_timestamp)
            
            # ALWAYS show substages if they exist for this stage
            if stage_assignments and str(i) in stage_assignments:
                stage_data = stage_assignments[str(i)]
                substages = stage_data.get("substages", [])
                
                if substages:  # Only render if substages exist
                    # Create a slightly indented container for substages
                    with st.container():
                        st.markdown("") # Add some spacing
                        render_substage_progress_with_edit(
                            project, project_id, i, substages, editable
                        )
                        st.markdown("---") # Add separator after substages

def render_substage_progress_with_edit(project, project_id, stage_index, substages, editable=False):
    """Render substage progress with real-time editing capability and validation"""
    if not substages:
        return
    
    # Use a more prominent header for substages
    st.markdown(f"**Substages**")
    
    is_form_context = _detect_form_context(project_id)
    
    # Get current substage completion status
    stage_key = str(stage_index)
    if is_form_context:
        current_completion = st.session_state.get("substage_completion", {}).get(stage_key, {})
        current_level = st.session_state.get("level_index", -1)
    else:
        current_completion = project.get("substage_completion", {}).get(stage_key, {}) if project else {}
        current_level = project.get("level", -1) if project else -1
    
    # Check if this stage is accessible
    stage_accessible = stage_index <= current_level + 1
    
    substage_changed = False
    substage_unchecked = False
    
    # Find the highest completed substage for sequential logic
    highest_completed_substage = -1
    for idx in range(len(substages)):
        if _get_completion_status(project, stage_key, idx, is_form_context):
            highest_completed_substage = idx
        else:
            break  # Stop at first incomplete substage
    
    # Create a container for all substages with border
    with st.container():
        # Add background styling for substages
        st.markdown(
            """
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin: 5px 0;">
            """,
            unsafe_allow_html=True
        )
        
        for substage_idx, substage in enumerate(substages):
            substage_name = substage.get("name", f"Substage {substage_idx + 1}")
            
            # Current completion status
            is_completed = _get_completion_status(project, stage_key, substage_idx, is_form_context)
            
            def render_substage_checkbox():
                if editable and stage_accessible:
                    # Sequential substage logic
                    can_check_substage = _validate_sequential_access(highest_completed_substage, substage_idx, highest_completed_substage, True)
                    can_uncheck_substage = _validate_sequential_access(highest_completed_substage, substage_idx, highest_completed_substage, False)
                    
                    checkbox_key = f"substage_{project_id}_{stage_index}_{substage_idx}"
                    completed = st.checkbox(
                        f"  🔸 {substage_name}",
                        value=is_completed,
                        key=checkbox_key
                    )
                    
                    # Check if substage completion changed
                    if completed != is_completed:
                        if completed and not can_check_substage:
                            _show_sequential_error(True, True)
                            return
                        elif not completed and not can_uncheck_substage:
                            _show_sequential_error(False, True)
                            return
                        
                        # Valid substage change
                        nonlocal substage_changed, substage_unchecked
                        substage_changed = True
                        
                        # Track if a substage was unchecked
                        if not completed and is_completed:
                            substage_unchecked = True
                        
                        # Update substage completion
                        _update_substage_completion(project, project_id, stage_key, substage_idx, completed, is_form_context)
                        
                        # Handle timestamps
                        _handle_timestamp_update(project, project_id, stage_key, substage_idx, completed, is_form_context)
                    
                    # Show status messages for substages
                    if not can_check_substage and not is_completed:
                        st.caption("      🔒 Complete previous substages first")
                    elif not can_uncheck_substage and is_completed and substage_idx < highest_completed_substage:
                        st.caption("      🔒 Completed substage")
                        
                else:
                    # Read-only display or inaccessible stage
                    status = "✅" if is_completed else "⏳"
                    disabled_text = " (locked)" if not stage_accessible and editable else ""
                    st.markdown(f"  {status} 🔸 {substage_name}{disabled_text}")
            
            def render_substage_info():
                # Show completion timestamp if available
                if is_completed:
                    if is_form_context:
                        timestamps = st.session_state.get("substage_timestamps", {})
                    else:
                        timestamps = project.get("substage_timestamps", {}) if project else {}
                    
                    if (stage_key in timestamps and 
                        str(substage_idx) in timestamps[stage_key]):
                        timestamp = timestamps[stage_key][str(substage_idx)]
                        _render_completion_timestamp(timestamp, is_compact=True)
                
                # Show deadline if available
                if "deadline" in substage and substage["deadline"]:
                    try:
                        deadline = substage["deadline"]
                        if isinstance(deadline, str):
                            deadline_date = datetime.fromisoformat(deadline).date()
                        else:
                            deadline_date = deadline
                        
                        # Check if overdue
                        today = datetime.now().date()
                        if deadline_date < today and not is_completed:
                            st.caption(f"🔴 Due: {deadline_date.strftime('%m/%d')}")
                        else:
                            st.caption(f"📅 Due: {deadline_date.strftime('%m/%d')}")
                    except:
                        pass
            
            _render_two_column_layout(render_substage_checkbox, render_substage_info, 4, 1)
        
        # Close the styling div
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Show completion status for the stage
        if substages:
            completed_count = sum(1 for idx in range(len(substages)) 
                                if _get_completion_status(project, stage_key, idx, is_form_context))
            total_count = len(substages)
            completion_percentage = (completed_count / total_count) * 100
            
            # Progress bar
            progress_col1, progress_col2 = st.columns([3, 1])
            with progress_col1:
                st.progress(completion_percentage / 100)
            with progress_col2:
                st.caption(f"{completed_count}/{total_count}")
            
            if completed_count < total_count:
                st.info(f"📊 Stage Progress: {completion_percentage:.0f}% complete")
            else:
                st.success(f"🎉 All substages completed!")
    
    # Handle substage changes and auto-advance/auto-uncheck logic (only for existing projects)
    if substage_changed and project and not is_form_context:
        current_stage_assignments = {stage_key: {"substages": substages}}
        
        # Auto-uncheck main stage if a substage was unchecked and main stage was completed
        if substage_unchecked and current_level >= stage_index:
            _auto_uncheck_main_stage(project, project_id, stage_index)
        
        # Check if all substages are now complete and auto-advance main stage
        elif _are_all_substages_complete(project, current_stage_assignments, stage_index):
            if stage_index == current_level + 1:
                # Auto-advance main stage if all substages complete
                _auto_advance_main_stage(project, project_id, stage_index)
        
        # Show success message and rerun to update UI
        st.success("Substage status updated!")
        time.sleep(0.1)
        st.rerun()
    elif substage_changed and is_form_context:
        # For form context, just show success message without database operations
        st.success("Substage status updated!")
        time.sleep(0.1)
        st.rerun()

def render_custom_levels_editor():
    """Render custom levels editor"""
    st.subheader("Customize Progress Levels")
    if not st.session_state.custom_levels:
        st.session_state.custom_levels = ["Initial"]
    
    # Remove required levels from custom levels for editing
    for required in ["Invoice", "Payment"]:
        if required in st.session_state.custom_levels:
            st.session_state.custom_levels.remove(required)
    
    editable_levels = st.session_state.custom_levels.copy()
    for i in range(len(editable_levels)):
        cols = st.columns([5, 1])
        editable_levels[i] = cols[0].text_input(
            f"Level {i+1}", value=editable_levels[i], key=f"level_{i}"
        )
        if len(editable_levels) > 1 and cols[1].button("➖", key=f"remove_{i}"):
            editable_levels.pop(i)
            st.session_state.custom_levels = editable_levels
            st.rerun()
    
    st.session_state.custom_levels = editable_levels
    
    if st.button("➕ Add Level"):
        st.session_state.custom_levels.append(f"New Level {len(st.session_state.custom_levels) + 1}")
        st.rerun()
    
    # Add required levels back
    st.session_state.custom_levels += ["Invoice", "Payment"]

def render_progress_section(form_type):
    """Render progress section for forms with enhanced substage visibility"""
    st.subheader("Progress")
    level_index = st.session_state.get("level_index", -1)
    level_timestamps = st.session_state.get("level_timestamps", {})
    stage_assignments = st.session_state.get("stage_assignments", {})
    
    # Ensure we have a project-like structure for substage rendering
    mock_project = {
        "level": level_index,
        "substage_completion": st.session_state.get("substage_completion", {}),
        "substage_timestamps": st.session_state.get("substage_timestamps", {})
    }
    
    def on_change_create(new_index):
        st.session_state.level_index = new_index
        st.session_state.level_timestamps[str(new_index)] = get_current_timestamp()
    
    # Use a form-specific project_id that won't be confused with database operations
    form_project_id = f"form_{form_type}"
    
    render_level_checkboxes_with_substages(
        form_type, form_project_id, level_index, level_timestamps, 
        st.session_state.custom_levels, on_change_create, 
        editable=True, stage_assignments=stage_assignments, project=mock_project
    )

def _render_project_action_buttons(project, pid):
    """Render project action buttons (Edit/Delete)"""
    col1, col2 = st.columns(2)
    if col1.button("✏ Edit", key=f"edit_{pid}"):
        st.session_state.edit_project_id = pid
        st.session_state.view = "edit"
        st.rerun()
    
    confirm_key = f"confirm_delete_{pid}"
    if not st.session_state.confirm_delete.get(confirm_key):
        if col2.button("🗑 Delete", key=f"del_{pid}"):
            st.session_state.confirm_delete[confirm_key] = True
            st.rerun()
    else:
        st.warning("Are you sure you want to delete this project?")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ Yes", key=f"yes_{pid}"):
            _handle_project_deletion(pid, project)
        if col_no.button("❌ No", key=f"no_{pid}"):
            st.session_state.confirm_delete[confirm_key] = False
            st.rerun()