import streamlit as st
from projects_logic import (
    are_all_substages_complete, auto_advance_main_stage,
    auto_uncheck_main_stage
)
from projects_helpers import display_success_messages


def render_project_card(project, index):
    """Render individual project card with substage validation
    Updated to show auto-uncheck messages
    """
    pid = project.get("id", f"auto_{index}")
    
    with st.expander(f"{project.get('name', 'Unnamed')}"):
        st.markdown(f"**Client:** {project.get('client', '-')}")
        st.markdown(f"**Description:** {project.get('description', '-')}")
        st.markdown(f"**Start Date:** {project.get('startDate', '-')}")
        st.markdown(f"**Due Date:** {project.get('dueDate', '-')}")
        st.markdown(f"**Manager/Lead:** {project.get('created_by', '-')}")
        
        levels = project.get("levels", ["Initial", "Invoice", "Payment"])
        current_level = project.get("level", -1)
        st.markdown(f"**Current Level:** {format_level(current_level, levels)}")
        
        # Show stage assignments summary
        stage_assignments = project.get("stage_assignments", {})
        
        # Show substage completion summary
        render_substage_summary_widget(project)
        
        # Show overdue stages for this project
        overdue_stages = get_overdue_stages(stage_assignments, levels, current_level)
        if overdue_stages:
            st.error("🔴 **Overdue Stages:**")
            for overdue in overdue_stages:
                st.error(f"  • {overdue['stage_name']}: {overdue['days_overdue']} days overdue")
        
        # Level checkboxes with substages and validation
        def on_change_dashboard(new_index, proj_id=pid, proj=project):
            # Validate substages before allowing stage change
            if new_index > project.get("level", -1):
                # Check if all substages are complete for the new stage
                if not _are_all_substages_complete(project, stage_assignments, new_index):
                    st.error("❌ Cannot advance to this stage - complete all substages first!")
                    return
            
            _handle_level_change_dashboard(proj_id, proj, new_index, stage_assignments)
        
        # Check for success messages
        _check_dashboard_success_messages(pid)
        
        # Check for auto-advance success messages
        for i in range(len(levels)):
            auto_advance_key = f"auto_advance_success_{pid}_{i}"
            if st.session_state.get(auto_advance_key, False):
                st.success(f"🎉 Stage {i + 1} automatically completed!")
                st.session_state[auto_advance_key] = False
            
            # Check for auto-uncheck success messages
            auto_uncheck_key = f"auto_uncheck_success_{pid}_{i}"
            if st.session_state.get(auto_uncheck_key, False):
                st.warning(f"⚠️ Stage {i + 1} automatically unchecked!")
                st.session_state[auto_uncheck_key] = False
        
        render_level_checkboxes_with_substages(
            "view", pid, int(project.get("level", -1)), 
            project.get("timestamps", {}), levels, on_change_dashboard, 
            editable=True, stage_assignments=stage_assignments, project=project
        )
        
        # Email reminder logic
        _handle_email_reminders(project, pid, levels, current_level)
        
        # Action buttons
        _render_project_action_buttons(project, pid)

def render_level_checkboxes_with_substages(context, project_id, current_level, timestamps, levels, 
                                         on_change, editable=False, stage_assignments=None, project=None):
    """
    Enhanced level checkboxes that also show substages with validation
    Updated to enforce sequential checking/unchecking
    """
    if not levels:
        st.warning("No levels defined for this project.")
        return
    
    for i, level in enumerate(levels):
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Main stage checkbox
            is_checked = i <= current_level
            key = f"{context}_{project_id}_level_{i}"
            
            # Check if all substages are completed for this stage
            substages_complete = _are_all_substages_complete(project, stage_assignments, i)
            can_check_stage = substages_complete or not _has_substages(stage_assignments, i)
            
            # Sequential checking logic
            can_advance_sequentially = (i == current_level + 1)  # Can only check next stage
            can_go_back_sequentially = (i == current_level)  # Can only uncheck current stage
            
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
                            st.error("❌ You can only advance to the next stage sequentially!")
                            time.sleep(0.1)
                            st.rerun()
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
                            st.error("❌ You can only go back one stage at a time!")
                            time.sleep(0.1)
                            st.rerun()
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

def render_substage_progress_with_edit(project, project_id, stage_index, substages, editable=False):
    """
    Render substage progress with real-time editing capability and validation
    Enhanced with sequential substage checking
    """
    if not substages:
        return
    
    st.caption(f"**Substages for Stage {stage_index + 1}:**")
    
    # Get current substage completion status
    substage_completion = project.get("substage_completion", {})
    stage_key = str(stage_index)
    current_completion = substage_completion.get(stage_key, {})
    
    # Check if this stage is accessible (current stage or previous stages)
    current_level = project.get("level", -1)
    stage_accessible = stage_index <= current_level + 1
    
    substage_changed = False
    substage_unchecked = False
    
    # Find the highest completed substage for sequential logic
    highest_completed_substage = -1
    for idx in range(len(substages)):
        if current_completion.get(str(idx), False):
            highest_completed_substage = idx
        else:
            break  # Stop at first incomplete substage
    
    for substage_idx, substage in enumerate(substages):
        substage_key = f"{stage_key}_{substage_idx}"
        substage_name = substage.get("name", f"Substage {substage_idx + 1}")
        
        # Current completion status
        is_completed = current_completion.get(str(substage_idx), False)
        
        if editable and stage_accessible:
            # Sequential substage logic
            can_check_substage = (substage_idx == highest_completed_substage + 1)  # Can only check next substage
            can_uncheck_substage = (substage_idx == highest_completed_substage)  # Can only uncheck last completed substage
            
            checkbox_key = f"substage_{project_id}_{stage_index}_{substage_idx}"
            completed = st.checkbox(
                f"  • {substage_name}",
                value=is_completed,
                key=checkbox_key
            )
            
            # Check if substage completion changed
            if completed != is_completed:
                if completed:
                    # Trying to check a substage
                    if not can_check_substage:
                        st.error("❌ Complete substages sequentially!")
                        time.sleep(0.1)
                        st.rerun()
                        return
                else:
                    # Trying to uncheck a substage
                    if not can_uncheck_substage:
                        st.error("❌ You can only uncheck the last completed substage!")
                        time.sleep(0.1)
                        st.rerun()
                        return
                
                # Valid substage change
                substage_changed = True
                
                # Track if a substage was unchecked
                if not completed and is_completed:
                    substage_unchecked = True
                
                # Update the project's substage completion immediately
                if "substage_completion" not in project:
                    project["substage_completion"] = {}
                if stage_key not in project["substage_completion"]:
                    project["substage_completion"][stage_key] = {}
                
                project["substage_completion"][stage_key][str(substage_idx)] = completed
                
                # Add/remove timestamp
                timestamp_key = f"substage_timestamps"
                if completed:
                    if timestamp_key not in project:
                        project[timestamp_key] = {}
                    if stage_key not in project[timestamp_key]:
                        project[timestamp_key][stage_key] = {}
                    project[timestamp_key][stage_key][str(substage_idx)] = get_current_timestamp()
                else:
                    # Remove timestamp when unchecked
                    if (timestamp_key in project and 
                        stage_key in project[timestamp_key] and 
                        str(substage_idx) in project[timestamp_key][stage_key]):
                        del project[timestamp_key][stage_key][str(substage_idx)]
                
                # Update in database immediately
                update_substage_completion_in_db(project_id, project["substage_completion"])
            
            # Show status messages for substages
            if not can_check_substage and not is_completed:
                st.caption("    🔒 Complete previous substages first")
            elif not can_uncheck_substage and is_completed and substage_idx < highest_completed_substage:
                st.caption("    🔒 Completed substage")
                
        else:
            # Read-only display or inaccessible stage
            status = "✅" if is_completed else "⏳"
            disabled_text = " (locked)" if not stage_accessible and editable else ""
            st.caption(f"  {status} {substage_name}{disabled_text}")
            
            # Show completion timestamp if available
            if is_completed:
                timestamps = project.get("substage_timestamps", {})
                if (stage_key in timestamps and 
                    str(substage_idx) in timestamps[stage_key]):
                    timestamp = timestamps[stage_key][str(substage_idx)]
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        st.caption(f"    Completed: {dt.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        st.caption(f"    Completed: {timestamp}")
    
    # Handle substage changes and auto-advance/auto-uncheck logic
    if substage_changed:
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
    
    # Show completion status for the stage
    if substages:
        completed_count = sum(1 for idx in range(len(substages)) 
                            if current_completion.get(str(idx), False))
        total_count = len(substages)
        completion_percentage = (completed_count / total_count) * 100
        
        if completed_count < total_count:
            st.info(f"📊 Progress: {completed_count}/{total_count} substages ({completion_percentage:.0f}%)")
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
    """Render progress section for forms"""
    st.subheader("Progress")
    level_index = st.session_state.get("level_index", -1)
    level_timestamps = st.session_state.get("level_timestamps", {})
    stage_assignments = st.session_state.get("stage_assignments", {})
    
    def on_change_create(new_index):
        st.session_state.level_index = new_index
        st.session_state.level_timestamps[str(new_index)] = get_current_timestamp()
    
    render_level_checkboxes(
        form_type, "new", level_index, level_timestamps, 
        st.session_state.custom_levels, on_change_create, 
        editable=True, stage_assignments=stage_assignments
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
