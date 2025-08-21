import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode


class DashboardComponents:
    def __init__(self, log_manager):
        self.log_manager = log_manager

    def render_dashboard_tab(self):
        """Enhanced dashboard with visualizations"""
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("🔄 Extract Logs", key="dashboard_extract_logs_btn", help="Extract assignments from projects"):
                with st.spinner("Extracting assignments from projects..."):
                    try:
                        logs_created = self.log_manager.extract_and_create_logs()
                        st.success(f"✅ Created {logs_created} log entries from project assignments")
                    except Exception as e:
                        st.error(f"❌ Error extracting logs: {str(e)}")
        
        with col2:
            if st.button("🧹 Clean Database", key="dashboard_clean_db_btn", type="secondary", help="Remove orphaned logs"):
                if st.checkbox("⚠️ Confirm cleanup", key="dashboard_confirm_cleanup", help="This will remove logs for non-existent projects"):
                    with st.spinner("Cleaning database..."):
                        cleaned = self._cleanup_orphaned_logs()
                        st.success(f"🧹 Cleaned {cleaned} orphaned logs")

        # Enhanced overview metrics
        overview = self.log_manager.get_project_overview()
        if overview:
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            with col1: 
                st.metric("📁 Projects", overview.get("total_projects", 0))
            with col2: 
                st.metric("📋 Total Tasks", overview.get("total_logs", 0))
            with col3: 
                completed = overview.get("completed_tasks", 0)
                total = overview.get("total_logs", 1)
                completion_rate = (completed / total * 100) if total > 0 else 0
                st.metric("✅ Completed", completed, f"{completion_rate:.1f}%")
            with col4: 
                st.metric("🔴 Overdue", overview.get("overdue_tasks", 0))
            with col5: 
                st.metric("🟡 In Progress", overview.get("in_progress_tasks", 0))
            with col6:
                pending = self.log_manager.logs.count_documents({"status": "Pending Verification"})
                st.metric("⏳ Pending", pending)

        st.divider()
        
        # Visualizations
        self._render_dashboard_charts()
        
        st.divider()
        self._render_recent_activity()

    def _render_dashboard_charts(self):
        """Render dashboard charts and analytics"""
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Task Status Distribution")
            try:
                status_data = list(self.log_manager.logs.aggregate([
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                ]))
                
                if len(status_data) > 0:
                    df_status = pd.DataFrame(status_data)
                    df_status.columns = ['Status', 'Count']
                    
                    fig = px.pie(df_status, values='Count', names='Status', 
                               color_discrete_map={
                                   'Completed': '#4CAF50',
                                   'In Progress': '#FF9800', 
                                   'Overdue': '#F44336',
                                   'Pending Verification': '#2196F3'
                               })
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("📊 No task data available for visualization")
            except Exception as e:
                st.error(f"❌ Error loading status chart: {str(e)}")
        
        with col2:
            st.subheader("👥 User Workload")
            try:
                user_data = list(self.log_manager.logs.aggregate([
                    {"$group": {"_id": "$assigned_user", "total": {"$sum": 1}, 
                               "completed": {"$sum": {"$cond": ["$is_completed", 1, 0]}}}},
                    {"$sort": {"total": -1}},
                    {"$limit": 10}
                ]))
                
                if len(user_data) > 0:
                    df_users = pd.DataFrame(user_data)
                    df_users.columns = ['User', 'Total Tasks', 'Completed']
                    df_users['Pending'] = df_users['Total Tasks'] - df_users['Completed']
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='Completed', x=df_users['User'], y=df_users['Completed'], marker_color='#4CAF50'))
                    fig.add_trace(go.Bar(name='Pending', x=df_users['User'], y=df_users['Pending'], marker_color='#FF9800'))
                    
                    fig.update_layout(barmode='stack', height=300, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("👥 No user data available for visualization")
            except Exception as e:
                st.error(f"❌ Error loading user chart: {str(e)}")

    def _render_recent_activity(self):
        """Render recent activity section"""
        st.subheader("📈 Recent Activity")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            activity_filter = st.selectbox("Activity Type", key="recent_activity_filter",
                                        options=["All Activities", "Recent Completions", "Recent Updates", "Overdue Tasks"])
        with col2:
            days_back = st.slider("Days Back", key="recent_activity_days", min_value=1, max_value=30, value=7)
        with col3:
            limit = st.slider("Max Results", key="recent_activity_limit", min_value=5, max_value=50, value=20)

        query = {}
        if activity_filter == "Recent Completions":
            query["is_completed"] = True
        elif activity_filter == "Overdue Tasks":
            query["status"] = "Overdue"

        cutoff_date = datetime.now() - timedelta(days=days_back)
        query["updated_at"] = {"$gte": cutoff_date}
        recent_logs = list(self.log_manager.logs.find(query).sort("updated_at", -1).limit(limit))
        
        if len(recent_logs) == 0:
            st.info(f"📭 No {activity_filter.lower()} found in the last {days_back} days")
            return

        df = pd.DataFrame([
            {
                "Project": log["project_name"],
                "Stage": log["stage_name"],
                "Substage": log["substage_name"],
                "User": log["assigned_user"],
                "Status": log["status"],
                "Priority": log.get("priority", "Medium"),
                "Deadline": self._format_date(log.get("substage_deadline", log.get("stage_deadline"))),
                "Updated": self._format_datetime(log.get("updated_at", log.get("created_at"))),
                "ID": str(log["_id"])
            }
            for log in recent_logs
        ])

        gb = GridOptionsBuilder.from_dataframe(df.drop('ID', axis=1))
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)
        gb.configure_selection('single', use_checkbox=True)
        #gb.configure_column("Status", cellRenderer=self._status_cell_renderer())
        #gb.configure_column("Priority", cellRenderer=self._priority_cell_renderer())
        gridOptions = gb.build()
        
        grid_response = AgGrid(
            df.drop('ID', axis=1),
            gridOptions=gridOptions,
            height=400,
            fit_columns_on_grid_load=True,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            key="recent_activity_aggrid"
        )

        selected_rows = grid_response.get('selected_rows', [])
        if isinstance(selected_rows, pd.DataFrame):
            selected_rows = selected_rows.to_dict('records')

        if selected_rows and len(selected_rows) > 0:
            try:
                selected_row = selected_rows[0]
                if '_selectedRowNodeInfo' in selected_row and 'nodeRowIndex' in selected_row['_selectedRowNodeInfo']:
                    selected_idx = selected_row['_selectedRowNodeInfo']['nodeRowIndex']
                    if 0 <= selected_idx < len(df):
                        selected_log_id = df.iloc[selected_idx]['ID']
                        selected_log = next((log for log in recent_logs if str(log["_id"]) == selected_log_id), None)
                        if selected_log:
                            from verification_components import TaskModalComponents
                            modal = TaskModalComponents(self.log_manager)
                            modal.show_task_modal(selected_log)
            except (KeyError, IndexError, TypeError):
                st.warning("⚠️ Unable to load selected task details")

    def _format_date(self, date_str):
        """Format date string for display with improved error handling"""
        if not date_str or date_str in ['1970-01-01 00:00:00', None, '']:
            return "Not Set"
        try:
            if isinstance(date_str, str):
                # Try different date formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                return str(date_str)
            elif isinstance(date_str, datetime):
                return date_str.strftime('%Y-%m-%d')
            return str(date_str)
        except Exception:
            return "Invalid Date"

    def _format_datetime(self, dt):
        """Format datetime for display with improved error handling"""
        try:
            if dt is None:
                return "Not Recorded"
            elif isinstance(dt, str):
                return dt
            elif isinstance(dt, datetime):
                return dt.strftime('%Y-%m-%d %H:%M')
            return str(dt)
        except Exception:
            return "Invalid DateTime"

    def _cleanup_orphaned_logs(self):
        """Remove logs for non-existent projects"""
        try:
            project_ids = [p['_id'] for p in self.log_manager.get_projects()]
            result = self.log_manager.logs.delete_many({"project_id": {"$nin": project_ids}})
            return result.deleted_count
        except Exception as e:
            st.error(f"❌ Cleanup failed: {str(e)}")
            return 0