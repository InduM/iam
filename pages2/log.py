import streamlit as st
import pandas as pd
from datetime import datetime
from backend.log_backend import ProjectLogManager
from utils.utils_log import format_status_badge, format_priority_badge
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_modal import Modal


class ProjectLogFrontend:
    def __init__(self):
        self.log_manager = ProjectLogManager()

    def setup_page_config(self):
        st.set_page_config(
            page_title="Project Logs Dashboard",
            page_icon="📊",
            layout="wide",
        )
        st.title("📊 Project Logs Dashboard")
        st.caption("Manage and track all your project tasks in one place.")

    def render_toolbar(self, logs):
        """Render refresh and export options"""
        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            if st.button("🔄 Refresh"):
                st.rerun()
        with col2:
            if logs:
                df = pd.DataFrame(logs)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇ Export CSV", csv, "project_logs.csv", "text/csv")

    def render_dashboard_tab(self):
        if st.button("🔄 Extract Logs", type="secondary"):
            with st.spinner("Extracting assignments from projects..."):
                logs_created = self.log_manager.extract_and_create_logs()
                st.success(f"✅ Created {logs_created} log entries from project assignments")

        overview = self.log_manager.get_project_overview()
        if overview:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("📁 Projects", overview.get("total_projects", 0))
            with col2: st.metric("📋 Tasks", overview.get("total_logs", 0))
            with col3: st.metric("✅ Completed", overview.get("completed_tasks", 0))
            with col4: st.metric("🔴 Overdue", overview.get("overdue_tasks", 0))
            with col5: st.metric("🟡 In Progress", overview.get("in_progress_tasks", 0))

        st.divider()
        self._render_recent_activity()

    def _render_recent_activity(self):
        st.subheader("📈 Recent Activity")
        recent_logs = list(self.log_manager.logs.find({}).sort("updated_at", -1).limit(20))
        if not recent_logs:
            st.info("📭 No recent activity found")
            return

        df = pd.DataFrame([
            {
                "Project": log["project_name"],
                "Stage": log["stage_name"],
                "Substage": log["substage_name"],
                "User": log["assigned_user"],
                "Status": log["status"],
                "Priority": log.get("priority", "Medium"),
                "Deadline": log.get("substage_deadline", log.get("stage_deadline")),
                "Updated": log.get("updated_at", log.get("created_at"))
            }
            for log in recent_logs
        ])
        df["Updated"] = df["Updated"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M") if x else "N/A")

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True)
        gridOptions = gb.build()
        AgGrid(df, gridOptions=gridOptions, height=400, fit_columns_on_grid_load=True)

    def render_user_logs_tab(self, is_admin=True):
        all_logs = list(self.log_manager.logs.find({}))
        if not all_logs:
            st.warning("📭 No logs available")
            return

        self.render_toolbar(all_logs)

        # Global search
        search_query = st.text_input("🔍 Search Tasks (Project, Stage, User)", placeholder="Type to search...")

        # Filters inside an expander
        with st.expander("🔍 Filters", expanded=False):
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                projects = self.log_manager.get_projects()
                project_names = ["All"] + [p['name'] for p in projects]
                selected_project = st.selectbox("Project", project_names)

            with col2:
                users = ["All Users"] + self.log_manager.get_all_users()
                selected_user = st.selectbox("User", users)

            with col3:
                status_filter = st.multiselect(
                    "Status",
                    ["Completed", "Overdue", "In Progress","Upcoming"],
                    default=["Completed", "Overdue", "In Progress", "Upcoming"]
                )

            col4, col5, col6 = st.columns([1, 1, 1])
            with col4:
                priority_filter = st.multiselect(
                    "Priority",
                    ["High", "Medium", "Low","Critical"],
                    default=["High", "Medium", "Low","Critical"]
                )
            with col5:
                include_completed = st.checkbox("Include Completed", value=True)
            with col6:
                overdue_only = st.checkbox("Show Overdue Only", value=False)

        # Apply filters
        filtered_logs = []
        for log in all_logs:
            if selected_project != "All" and log["project_name"] != selected_project:
                continue
            if selected_user != "All Users" and log["assigned_user"] != selected_user:
                continue
            if log["status"] not in status_filter:
                continue
            if log.get("priority", "Medium") not in priority_filter:
                continue
            if not include_completed and log.get("is_completed", False):
                continue
            if overdue_only and log.get("status") != "Overdue":
                continue
            if search_query and search_query.lower() not in str(log).lower():
                continue
            filtered_logs.append(log)

        st.subheader(f"📋 Showing {len(filtered_logs)} tasks")
        if filtered_logs:
            self._render_task_table(filtered_logs)
        else:
            st.info("📭 No tasks match your filters")

    def _render_task_table(self, logs):
        """Display logs in AgGrid table and open modal on selection"""
        df = pd.DataFrame([
            {
                "Project": log["project_name"],
                "Stage": log["stage_name"],
                "Substage": log["substage_name"],
                "User": log["assigned_user"],
                "Status": log["status"],
                "Priority": log.get("priority", "Medium"),
                "Deadline": log.get("substage_deadline", log.get("stage_deadline")),
                "Completed": "✅ Yes" if log.get("is_completed") else "❌ No"
            }
            for log in logs
        ])

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True)
        gb.configure_selection('single')
        gridOptions = gb.build()

        grid_response = AgGrid(df, gridOptions=gridOptions, height=450, fit_columns_on_grid_load=True)
        selected_rows = grid_response['selected_rows']
        if selected_rows:
            task_id = selected_rows[0]["ID"]
            selected_log = next((log for log in logs if str(log["_id"]) == task_id), None)
            if selected_log:
                self._show_task_modal(selected_log)

    def _show_task_modal(self, log):
        """Show modal with task details, edit and actions"""
        modal = Modal(f"Task: {log['substage_name']}", key="task_modal", max_width=700)
        with modal.container():
            st.subheader(f"📝 Task Details")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Project:** {log['project_name']}")
                st.write(f"**Stage:** {log['stage_name']}")
                st.write(f"**User:** {log['assigned_user']}")
                st.write(f"**Status:** {format_status_badge(log['status'])}", unsafe_allow_html=True)
                st.write(f"**Priority:** {format_priority_badge(log.get('priority', 'Medium'))}", unsafe_allow_html=True)
            with col2:
                st.write(f"**Start Date:** {log['start_date'] or 'Not Set'}")
                st.write(f"**Stage Deadline:** {log['stage_deadline'] or 'Not Set'}")
                st.write(f"**Substage Deadline:** {log['substage_deadline'] or 'Not Set'}")

            st.divider()
            desc = st.text_area("Description", value=log.get('description', 'No description'), height=120)

            # Actions
            st.divider()
            col_action1, col_action2, col_action3 = st.columns(3)
            with col_action1:
                if not log.get('is_completed', False):
                    if st.button("✅ Mark Complete"):
                        if self.log_manager.complete_task(str(log['_id'])):
                            st.success("✅ Task completed!")
                            st.rerun()
                else:
                    st.success("✅ Completed")

            with col_action2:
                if st.button("💾 Save Changes"):
                    self.log_manager.logs.update_one({"_id": log["_id"]}, {"$set": {"description": desc}})
                    st.success("✅ Description updated!")
                    st.rerun()

            with col_action3:
                if st.button("🗑 Delete Task"):
                    self.log_manager.logs.delete_one({"_id": log["_id"]})
                    st.warning("🗑 Task deleted!")
                    st.rerun()

    def render_project_overview_tab(self):
        projects = self.log_manager.get_projects()
        if not projects:
            st.warning("⚠️ No projects found")
            return

        st.subheader("🏢 Project Overview")
        for project in projects:
            project_logs = list(self.log_manager.logs.find({"project_name": project['name']}))
            total_tasks = len(project_logs)
            completed = sum(1 for log in project_logs if log.get('is_completed', False))
            overdue = sum(1 for log in project_logs if log.get('status') == 'Overdue')
            progress = completed / total_tasks if total_tasks else 0

            st.markdown(f"### 🏢 {project['name']} ({project['client']})")
            st.progress(progress)
            st.caption(f"✅ {completed}/{total_tasks} tasks completed | 🔴 {overdue} overdue")

    def run(self):
        if not self.log_manager.client:
            st.error("❌ Cannot proceed without database connection")
            return

        user_role = st.session_state.get("role", "user")
        tab_dashboard, tab_user_logs, tab_project_overview = st.tabs([
            "📊 Dashboard", "👤 User Logs", "🏢 Project Overview"
        ])

        with tab_dashboard:
            self.render_dashboard_tab()
        with tab_user_logs:
            self.render_user_logs_tab(is_admin=(user_role == "admin"))
        with tab_project_overview:
            self.render_project_overview_tab()


def run():
    app = ProjectLogFrontend()
    app.run()
