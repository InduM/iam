import streamlit as st
from datetime import datetime
import time
import pandas as pd
from typing import List, Dict, Any

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
from .project_helpers import get_project_team
# Main Functions

import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
import streamlit as st

st.markdown("""
    <style>
    /* Remove grey horizontal rules inside expanders */
    div[data-testid="stExpander"] hr {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

def render_projects_table(projects):
    """Ag-Grid table with inline Edit/Delete and robust confirmation that disappears on Cancel/Yes."""
    if not projects:
        st.info("No projects to display.")
        return

    # --- one-time session state ---
    if "projects_grid_version" not in st.session_state:
        st.session_state.projects_grid_version = 0
    if "pending_delete_id" not in st.session_state:
        st.session_state.pending_delete_id = None

    # --- rows ---
    rows = []
    for p in projects:
        levels = p.get("levels", [])
        level_idx = int(p.get("level", -1))
        # format_level comes from utils.utils_project_core
        current_level_name = format_level(level_idx, levels)
        stage_assignments = p.get("stage_assignments", {})
        overdue = get_overdue_stages(stage_assignments, levels, level_idx)

        cms = p.get("co_managers", [])
        cm_text = ", ".join(
            f"{cm.get('user','?')} ({cm.get('access','full')}"
            + (f": {', '.join(cm.get('stages', []))}" if cm.get('access') == 'limited' else "")
            + ")"
            for cm in cms
        )

        rows.append({
            "ID": p.get("id", ""),  # hidden in grid; used internally
            "Name": p.get("name", ""),
            "Template": p.get("template", ""),
            "Subtemplate / Client": p.get("subtemplate", "") if p.get("template") == "Onwards" else p.get("client", ""),
            "Start": p.get("startDate", ""),
            "Due": p.get("dueDate", ""),
            "Current Level": current_level_name,
            "Manager": p.get("created_by", ""),
            "Co-Managers": cm_text,
            "Team": ", ".join(get_project_team(p)), 
            "Overdue Stages": ", ".join([o["stage_name"] for o in overdue]) if overdue else "",
            "EditAction": "",
            "DeleteAction": "",
        })

    df = pd.DataFrame(rows)

    # --- grid options ---
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=False, wrapText=True, autoHeight=True, resizable=True)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_side_bar()

    # Hide internal ID column
    gb.configure_column("ID", hide=True)

    # Inline buttons via JS: write row ID into the action cell to signal click
    edit_button_renderer = JsCode("""
    class BtnCellRenderer {
      init(params) {
        this.params = params;
        this.eGui = document.createElement('button');
        this.eGui.innerText = '✏ Edit';
        this.eGui.style.padding = '2px 8px';
        this.eGui.style.cursor = 'pointer';
        this.eGui.addEventListener('click', () => {
          params.api.stopEditing();
          params.node.setDataValue('EditAction', params.data.ID);
        });
      }
      getGui() { return this.eGui; }
    }
    """)

    delete_button_renderer = JsCode("""
    class BtnCellRenderer {
      init(params) {
        this.params = params;
        this.eGui = document.createElement('button');
        this.eGui.innerText = '🗑 Delete';
        this.eGui.style.padding = '2px 8px';
        this.eGui.style.cursor = 'pointer';
        this.eGui.style.color = 'red';
        this.eGui.addEventListener('click', () => {
          params.api.stopEditing();
          params.node.setDataValue('DeleteAction', params.data.ID);
        });
      }
      getGui() { return this.eGui; }
    }
    """)

    gb.configure_column("EditAction", headerName="", cellRenderer=edit_button_renderer, width=100, pinned="right")
    gb.configure_column("DeleteAction", headerName="", cellRenderer=delete_button_renderer, width=110, pinned="right")

    grid_options = gb.build()
    # Let grid grow with content (avoids fixed 400px)
    grid_options["domLayout"] = "autoHeight"

    # Bumpable key ensures a fresh grid after click/cancel/confirm
    grid_key = f"projects_grid_{st.session_state.projects_grid_version}"

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        key=grid_key,
        reload_data=True
    )

    # --- handle inline button clicks ---
    data = grid_response.get("data")
    if data is not None and not data.empty:
        # iterate with index so we can clear the cell to prevent re-trigger on rerun
        for idx, row in data.iterrows():
            # EDIT
            if row.get("EditAction"):
                pid = row["EditAction"]
                st.session_state.edit_project_id = pid
                st.session_state.view = "edit"
                # clear trigger & force grid refresh
                data.at[idx, "EditAction"] = ""
                st.session_state.projects_grid_version += 1
                st.rerun()

            # DELETE → show confirm, but do NOT delete yet
            if row.get("DeleteAction"):
                pid = row["DeleteAction"]
                role = st.session_state.get("role", "")
                if role != "user":
                    st.session_state.pending_delete_id = pid
                    # clear trigger & force grid refresh so it doesn't auto-reopen on rerun
                    data.at[idx, "DeleteAction"] = ""
                    st.session_state.projects_grid_version += 1
                    st.rerun()
                else:
                    st.error("🚫 No permission to delete.")

    # --- confirmation UI (disappears on Cancel or Yes) ---
    if st.session_state.pending_delete_id:
        pid = st.session_state.pending_delete_id
        proj = next((p for p in projects if p.get("id") == pid), None)
        if proj:
            st.warning(f"⚠️ Are you sure you want to delete project: **{proj.get('name','')}**?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Yes, Delete", key="confirm_yes"):
                _handle_project_deletion(pid, proj)
                st.session_state.pending_delete_id = None
                st.session_state.projects_grid_version += 1
                st.rerun()
            if c2.button("❌ Cancel", key="confirm_no"):
                st.session_state.pending_delete_id = None  # <- remove pending state
                st.session_state.projects_grid_version += 1  # <- force fresh grid
                st.rerun()


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
        st.markdown(f"**Team:** {', '.join(get_project_team(project)) or '-'}")
         # --- Show multiple co-managers if available ---
        co_managers = project.get("co_managers", [])
        if co_managers:
            st.markdown("**Co-Managers:**")
            for cm in co_managers:
                cm_user = cm.get("user", "-")
                cm_access = cm.get("access", "full")
                if cm_access == "limited":
                    stages = ", ".join(cm.get("stages", [])) or "No stages selected"
                    st.markdown(f"- {cm_user} (Limited Access: {stages})")
                else:
                    st.markdown(f"- {cm_user} (Full Access)")

        # --- Legacy single co_manager (backward compatibility) ---
        elif project.get("co_manager"):
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
        
        # Show substage completion summary (without grey divider)
        with st.container():
            render_substage_summary_widget(project)
            # override the default expander/divider styling
            st.markdown("<hr style='border:none; margin:0;'>", unsafe_allow_html=True)
        
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
                st.success(f"Stage {i + 1} completed!")
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

