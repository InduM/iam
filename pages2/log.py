import streamlit as st
import pandas as pd
from datetime import datetime
from backend.log_backend import ProjectLogManager
from utils.utils_log import format_status_badge, format_priority_badge
from st_aggrid import AgGrid, GridOptionsBuilder

class ProjectLogFrontend:
    def __init__(self):
        self.log_manager = ProjectLogManager()

        

    def render_toolbar(self, logs):
        """Render top toolbar with refresh and export options"""
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
        """Dashboard Tab: Show overview metrics and recent activity"""
        # Quick refresh
        if st.button("🔄 Extract Logs", type="secondary"):
            with st.spinner("Extracting assignments from projects..."):
                logs_created = self.log_manager.extract_and_create_logs()
                st.success(f"✅ Created {logs_created} log entries from project assignments")

        # Overview metrics
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
        """Show recent activity in a table"""
        st.subheader("📈 Recent Activity")
        recent_logs = list(self.log_manager.logs.find({}).sort("updated_at", -1).limit(20))
        if not recent_logs:
            st.info("📭 No recent activity found")
            return

        # Convert to DataFrame
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

        # AgGrid table
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True)
        gridOptions = gb.build()
        AgGrid(df, gridOptions=gridOptions, height=400, fit_columns_on_grid_load=True)

    def render_user_logs_tab(self, is_admin=True):
        """Render user logs tab with filters and table view"""
        all_logs = list(self.log_manager.logs.find({}))
        if not all_logs:
            st.warning("📭 No logs available")
            return

        self.render_toolbar(all_logs)

        # Sidebar Filters
        with st.sidebar:
            st.header("🔍 Filters")
            projects = self.log_manager.get_projects()
            project_names = ["All"] + [p['name'] for p in projects]
            selected_project = st.selectbox("Project", project_names)
            users = ["All Users"] + self.log_manager.get_all_users()
            selected_user = st.selectbox("User", users)
            status_filter = st.multiselect("Status", ["Completed", "Overdue", "In Progress"], default=["Completed", "Overdue", "In Progress"])
            priority_filter = st.multiselect("Priority", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
            include_completed = st.checkbox("Include Completed", value=True)
            overdue_only = st.checkbox("Show Overdue Only", value=False)

        # Global search
        search_query = st.text_input("🔍 Search tasks (project, stage, user)")
        
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
        """Display logs in AgGrid table"""
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
        gb.configure_selection('single')  # Select a task for detail view
        gridOptions = gb.build()

        AgGrid(df, gridOptions=gridOptions, height=450, fit_columns_on_grid_load=True)

    def render_project_overview_tab(self):
        """Show all projects with progress bars and breakdown"""
        projects = self.log_manager.get_projects()
        if not projects:
            st.warning("⚠️ No projects found")
            return

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
