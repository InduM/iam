import streamlit as st
from datetime import datetime
import time

from utils.utils_project_core import (
    format_level,
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
from .project_substage_manager import render_level_checkboxes_with_substages
# Main Functions
def render_project_card(project, index):
    """Render individual project card with substage validation"""
    pid = project.get("id", f"auto_{index}")
    
    with st.expander(f"{project.get('name', 'Unnamed')}"):
        # Mobile-first layout with better spacing
        template = project.get("template", "")
        if template == "Onwards":
            st.markdown(f"**Subtemplate:** {project.get('subtemplate', '-')}")
        else:
            st.markdown(f"**Client:** {project.get('client', '-')}")
        st.markdown(f"**Description:** {project.get('description', '-')}")
        
        # Date information in mobile-friendly format
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Start:** {project.get('startDate', '-')}")
        with col2:
            st.markdown(f"**Due:** {project.get('dueDate', '-')}")
        
        st.markdown(f"**Manager:** {project.get('created_by', '-')}")
        if project.get("co_manager"):
            cm = project["co_manager"]
            cm_user = cm.get("user", "-")
            cm_access = cm.get("access", "full")
            if cm_access == "limited":
                stages = ", ".join(cm.get("stages", [])) or "No stages selected"
                st.markdown(f"**Co-Manager:** {cm_user} (Limited Access: {stages})")
            else:
                st.markdown(f"**Co-Manager:** {cm_user} (Full Access)")
        
        levels = project.get("levels", ["Initial", "Invoice", "Payment"])
        current_level = project.get("level", -1)
        st.markdown(f"**📊 Current Level:** {format_level(current_level, levels)}")
        
        # Show stage assignments summary
        stage_assignments = project.get("stage_assignments", {})
        
        # Show substage completion summary
        render_substage_summary_widget(project)
        
         # --- NEW: Recent Activity log (Co-Manager related only) ---
        from backend.log_backend import ProjectLogManager
        log_manager = ProjectLogManager()
        logs = log_manager.get_logs_for_project(project.get("name", ""))

        cm_logs = [
            log for log in logs 
            if log.get("action") in ["co_manager_added", "co_manager_removed", "co_manager_updated"]
        ]

        if cm_logs:
            st.markdown("### 🕑 Recent Co-Manager Activity")
            for log in sorted(cm_logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]:
                ts = log.get("timestamp", "")
                details = log.get("details", "")
                by = log.get("performed_by", "?")
                st.markdown(f"- {ts} — {details} _(by {by})_")
        # --- End activity log ---

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


def _render_project_action_buttons(project, pid):
    """Render project action buttons (Edit/Delete) with role-based restrictions"""
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")

    # Permission checks
    can_edit = True
    if role == "user":
        created_by = project.get("created_by", "")
        co_managers = project.get("co_managers", [])
        is_creator = (created_by == username)
        is_co_manager = any(cm.get("user") == username for cm in co_managers)
        can_edit = is_creator or is_co_manager

    col1, col2 = st.columns(2)

    # Edit button only if user has edit rights
    if can_edit:
        if col1.button("✏ Edit", key=f"edit_{pid}"):
            st.session_state.edit_project_id = pid
            st.session_state.view = "edit"
            st.rerun()
    else:
        col1.caption("🔒 No edit permission")

    # Delete is always visible to admins/managers; hidden for users
    if role != "user":
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
    else:
        col2.caption("🔒 No delete permission")
