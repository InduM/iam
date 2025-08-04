import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from backend.log_backend import ProjectLogManager
from utils.utils_log import format_status_badge, format_priority_badge
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from streamlit_modal import Modal
from bson import ObjectId
import plotly.express as px
import plotly.graph_objects as go


class ProjectLogFrontend:
    def __init__(self):
        self.log_manager = ProjectLogManager()

    def render_toolbar(self, logs):
        """Enhanced toolbar with additional functionality"""
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            if st.button("🔄 Refresh", help="Refresh the current view"):
                st.rerun()
      
    def render_dashboard_tab(self):
        """Enhanced dashboard with visualizations"""
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("🔄 Extract Logs", type="primary", help="Extract assignments from projects"):
                with st.spinner("Extracting assignments from projects..."):
                    try:
                        logs_created = self.log_manager.extract_and_create_logs()
                        st.success(f"✅ Created {logs_created} log entries from project assignments")
                    except Exception as e:
                        st.error(f"❌ Error extracting logs: {str(e)}")
        
        with col2:
            if st.button("🧹 Clean Database", type="secondary", help="Remove orphaned logs"):
                if st.checkbox("⚠️ Confirm cleanup", help="This will remove logs for non-existent projects"):
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
        """Enhanced recent activity with better formatting"""
        st.subheader("📈 Recent Activity")
        
        # Activity filters
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            activity_filter = st.selectbox("Activity Type", 
                                         ["All Activities", "Recent Completions", "Recent Updates", "Overdue Tasks"])
        with col2:
            days_back = st.slider("Days Back", 1, 30, 7)
        with col3:
            limit = st.slider("Max Results", 5, 50, 20)
        
        # Build query based on filters
        query = {}
        if activity_filter == "Recent Completions":
            query["is_completed"] = True
        elif activity_filter == "Overdue Tasks":
            query["status"] = "Overdue"
        
        # Date filter
        cutoff_date = datetime.now() - timedelta(days=days_back)
        query["updated_at"] = {"$gte": cutoff_date}
        
        recent_logs = list(self.log_manager.logs.find(query).sort("updated_at", -1).limit(limit))
        
        if len(recent_logs) == 0:
            st.info(f"📭 No {activity_filter.lower()} found in the last {days_back} days")
            return

        # Enhanced data presentation
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

        # Enhanced AgGrid configuration
        gb = GridOptionsBuilder.from_dataframe(df.drop('ID', axis=1))
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)
        gb.configure_selection('single', use_checkbox=True)
        gb.configure_column("Status", cellRenderer=self._status_cell_renderer())
        gb.configure_column("Priority", cellRenderer=self._priority_cell_renderer())
        
        gridOptions = gb.build()
        grid_response = AgGrid(
            df.drop('ID', axis=1), 
            gridOptions=gridOptions, 
            height=400, 
            fit_columns_on_grid_load=True,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED
        )
        
        # Handle row selection - FIXED: Added proper error handling for DataFrame selection
        if grid_response.get('selected_rows') and len(grid_response['selected_rows']) > 0:
            try:
                selected_row = grid_response['selected_rows'][0]
                if '_selectedRowNodeInfo' in selected_row and 'nodeRowIndex' in selected_row['_selectedRowNodeInfo']:
                    selected_idx = selected_row['_selectedRowNodeInfo']['nodeRowIndex']
                    if 0 <= selected_idx < len(df):
                        selected_log_id = df.iloc[selected_idx]['ID']
                        selected_log = next((log for log in recent_logs if str(log["_id"]) == selected_log_id), None)
                        if selected_log:
                            self._show_task_modal(selected_log)
            except (KeyError, IndexError, TypeError) as e:
                st.warning("⚠️ Unable to load selected task details")

    def render_user_logs_tab(self, is_admin=True):
        """Enhanced user logs with better filtering and bulk operations"""
        try:
            all_logs = list(self.log_manager.logs.find({}))
        except Exception as e:
            st.error(f"❌ Error fetching logs: {str(e)}")
            return
            
        if not all_logs:
            st.warning("📭 No logs available")
            return

        self.render_toolbar(all_logs)
        current_user = st.session_state.get("username", "Unknown User")
        
        # Enhanced search
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input("🔍 Search Tasks", placeholder="Search by project, task, user...")
        with col2:
            search_in = st.selectbox("Search In", ["All Fields", "Project Name", "Task Name", "User"])

        if is_admin:
            with st.expander("🔍 Advanced Filters", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    try:
                        projects = self.log_manager.get_projects()
                        project_names = ["All"] + [p['name'] for p in projects]
                        selected_project = st.selectbox("Project", project_names)
                    except Exception as e:
                        st.error(f"❌ Error loading projects: {str(e)}")
                        selected_project = "All"
                
                with col2:
                    try:
                        users = ["All Users"] + self.log_manager.get_all_users()
                        selected_user = st.selectbox("User", users)
                    except Exception as e:
                        st.error(f"❌ Error loading users: {str(e)}")
                        selected_user = "All Users"
                
                with col3:
                    status_filter = st.multiselect(
                        "Status", ["Completed", "Pending Verification", "Overdue", "In Progress"],
                        default=["Completed", "Pending Verification", "Overdue", "In Progress"]
                    )

                col4, col5, col6 = st.columns(3)
                
                with col4:
                    priority_filter = st.multiselect(
                        "Priority", ["High", "Medium", "Low","Critical"],
                        default=["High", "Medium", "Low","Critical"]
                    )
                
                with col5:
                    # Date range filter
                    date_filter = st.date_input("Deadline Range", value=None, help="Filter by deadline range")
                
                with col6:
                    # Additional filters
                    include_completed = st.checkbox("Include Completed", value=True)
                    overdue_only = st.checkbox("Show Overdue Only", value=False)

            # Apply filters - FIXED: Improved error handling
            try:
                filtered_logs = self._apply_filters(
                    all_logs, selected_project, selected_user, status_filter, 
                    priority_filter, include_completed, overdue_only, search_query, search_in
                )
            except Exception as e:
                st.error(f"❌ Error applying filters: {str(e)}")
                filtered_logs = all_logs

            st.subheader(f"📋 Showing {len(filtered_logs)} of {len(all_logs)} tasks")
            
            # Bulk operations for admin
            if len(filtered_logs) > 0:
                with st.expander("⚡ Bulk Operations", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Mark All Complete"):
                            if st.checkbox("Confirm bulk completion"):
                                self._bulk_complete_tasks(filtered_logs)
                    with col2:
                        if st.button("🗑️ Delete Selected"):
                            if st.checkbox("Confirm bulk deletion"):
                                self._bulk_delete_tasks(filtered_logs)
                    with col3:
                        priority_change = st.selectbox("Change Priority To", ["High", "Medium", "Low","Critical"])
                        if st.button("🔄 Update Priority"):
                            self._bulk_update_priority(filtered_logs, priority_change)

                self._render_task_table(filtered_logs)
            else:
                st.info("📭 No tasks match your filters")

        else:
            # Non-admin view
            try:
                user_logs = [log for log in all_logs if log.get("assigned_user") == current_user]
                if search_query:
                    user_logs = self._search_logs(user_logs, search_query, search_in)
            except Exception as e:
                st.error(f"❌ Error filtering user logs: {str(e)}")
                user_logs = []

            st.subheader(f"📋 Your Assigned Tasks ({len(user_logs)})")
            
            # User task summary
            if len(user_logs) > 0:
                try:
                    user_stats = self._get_user_stats(user_logs)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Total", user_stats['total'])
                    with col2: st.metric("Completed", user_stats['completed'])
                    with col3: st.metric("Pending", user_stats['pending'])
                    with col4: st.metric("Overdue", user_stats['overdue'])
                    
                    st.divider()
                    self._render_user_task_cards(user_logs)
                except Exception as e:
                    st.error(f"❌ Error rendering user stats: {str(e)}")
            else:
                st.info("📭 You have no assigned tasks")

    def render_verification_tab(self):
        """Enhanced verification tab with batch processing"""
        st.subheader("✅ Pending Verification")
        
        try:
            pending_logs = list(self.log_manager.logs.find({"status": "Pending Verification"}))
        except Exception as e:
            st.error(f"❌ Error fetching pending logs: {str(e)}")
            return
            
        if len(pending_logs) == 0:
            st.success("🎉 No tasks pending verification.")
            return

        # Verification stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Tasks", len(pending_logs))
        with col2:
            users_count = len(set(log['assigned_user'] for log in pending_logs))
            st.metric("Users Involved", users_count)
        with col3:
            projects_count = len(set(log['project_name'] for log in pending_logs))
            st.metric("Projects Affected", projects_count)

        # Batch verification
        with st.expander("⚡ Batch Verification", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Verify All", type="primary"):
                    if st.checkbox("⚠️ Confirm batch verification"):
                        verified_count = self._batch_verify_tasks(pending_logs)
                        st.success(f"✅ Verified {verified_count} tasks!")
                        st.rerun()
            with col2:
                selected_user = st.selectbox("Verify by User", 
                                           ["Select User"] + list(set(log['assigned_user'] for log in pending_logs)))
                if selected_user != "Select User":
                    user_tasks = [log for log in pending_logs if log['assigned_user'] == selected_user]
                    if st.button(f"✅ Verify {selected_user}'s Tasks ({len(user_tasks)})"):
                        verified_count = self._batch_verify_tasks(user_tasks)
                        st.success(f"✅ Verified {verified_count} tasks for {selected_user}!")
                        st.rerun()

        # Individual verification
        st.divider()
        st.markdown("### Individual Verification")
        
        # Enhanced verification table
        try:
            df = pd.DataFrame([
                {
                    "Project": log["project_name"],
                    "Member": log["assigned_user"],
                    "Stage": log["stage_name"],
                    "Substage": log["substage_name"],
                    "Completed At": self._format_datetime(log.get("completed_clicked_at")),
                    "Priority": log.get("priority", "Medium"),
                    "ID": str(log["_id"])
                }
                for log in pending_logs
            ])
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
        except Exception as e:
            st.error(f"❌ Error creating verification table: {str(e)}")

        # Individual verification controls
        for i, log in enumerate(pending_logs):
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                
                with col1:
                    st.write(f"**{log['project_name']}**")
                with col2:
                    st.write(f"👤 {log['assigned_user']}")
                with col3:
                    st.write(f"📋 {log['substage_name']}")
                with col4:
                    priority_badge = format_priority_badge(log.get('priority', 'Medium'))
                    st.markdown(priority_badge, unsafe_allow_html=True)
                with col5:
                    if st.button("✅", key=f"verify_{log['_id']}", help="Verify this task"):
                        try:
                            self._verify_task_completion_with_timestamp(log)
                            st.success(f"✅ Verified: {log['substage_name']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Verification failed: {str(e)}")
                
                if i < len(pending_logs) - 1:
                    st.divider()

    # Helper methods - FIXED: Improved error handling and boolean logic
    def _apply_filters(self, logs, project, user, status, priority, include_completed, overdue_only, search_query, search_in):
        """Apply all filters to logs with improved error handling"""
        if not logs:  # Handle empty logs list
            return []
            
        filtered_logs = []
        for log in logs:
            try:
                # Project filter
                if project != "All" and log.get("project_name") != project:
                    continue
                
                # User filter
                if user != "All Users" and log.get("assigned_user") != user:
                    continue
                
                # Status filter - FIXED: Handle empty status filter
                if status and log.get("status") not in status:
                    continue
                
                # Priority filter - FIXED: Handle empty priority filter
                if priority and log.get("priority", "Medium") not in priority:
                    continue
                
                # Completed filter
                if not include_completed and log.get("is_completed", False):
                    continue
                
                # Overdue filter
                if overdue_only and log.get("status") != "Overdue":
                    continue
                
                # Search filter
                if search_query and search_query.strip():
                    if not self._matches_search(log, search_query, search_in):
                        continue
                
                filtered_logs.append(log)
                
            except Exception as e:
                # Log the error but continue processing
                st.warning(f"⚠️ Error processing log {log.get('_id', 'unknown')}: {str(e)}")
                continue
        
        return filtered_logs

    def _search_logs(self, logs, query, search_in):
        """Search logs with improved error handling"""
        if not query or not query.strip():
            return logs
            
        filtered_logs = []
        for log in logs:
            try:
                if self._matches_search(log, query, search_in):
                    filtered_logs.append(log)
            except Exception as e:
                # Continue processing even if one log fails
                continue
        return filtered_logs

    def _matches_search(self, log, query, search_in):
        """Check if log matches search query with improved error handling"""
        try:
            query = str(query).lower().strip()
            if not query:
                return True
            
            if search_in == "All Fields":
                searchable_fields = [
                    log.get('project_name', ''),
                    log.get('stage_name', ''),
                    log.get('substage_name', ''),
                    log.get('assigned_user', ''),
                    log.get('description', '')
                ]
                searchable_text = ' '.join(str(field) for field in searchable_fields).lower()
                return query in searchable_text
            elif search_in == "Project Name":
                return query in str(log.get('project_name', '')).lower()
            elif search_in == "Task Name":
                return query in str(log.get('substage_name', '')).lower()
            elif search_in == "User":
                return query in str(log.get('assigned_user', '')).lower()
            
            return False
        except Exception:
            return False

    def _get_user_stats(self, user_logs):
        """Get user statistics with error handling"""
        try:
            total = len(user_logs)
            completed = sum(1 for log in user_logs if log.get('is_completed', False))
            overdue = sum(1 for log in user_logs if log.get('status') == 'Overdue')
            pending = total - completed
            
            return {
                'total': total,
                'completed': completed,
                'pending': pending,
                'overdue': overdue
            }
        except Exception as e:
            st.error(f"❌ Error calculating user stats: {str(e)}")
            return {'total': 0, 'completed': 0, 'pending': 0, 'overdue': 0}

    def _render_user_task_cards(self, user_logs):
        """Render user tasks as cards with error handling"""
        for log in user_logs:
            try:
                overdue_style = "border-left: 4px solid #f44336;" if log.get("status") == "Overdue" else "border-left: 4px solid #4caf50;"
                priority = log.get('priority', 'Medium')
                priority_colors = {"High": "#ffebee", "Medium": "#fff3e0", "Low": "#e8f5e8"}
                priority_color = priority_colors.get(priority, "#f5f5f5")
                
                with st.container():
                    st.markdown(
                        f"""
                        <div style='{overdue_style} background-color:{priority_color}; padding:12px; border-radius:8px; margin:8px 0;'>
                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                <div>
                                    <strong style='font-size: 1.1em;'>{log.get('project_name', 'Unknown Project')}</strong><br>
                                    <small style='color: #666;'>Stage: {log.get('stage_name', 'Unknown')} → {log.get('substage_name', 'Unknown')}</small><br>
                                    <small style='color: #888;'>Priority: {priority} | Deadline: {self._format_date(log.get('substage_deadline', log.get('stage_deadline')))}</small>
                                </div>
                                <div style='text-align: right;'>
                                    {format_status_badge(log.get('status', 'Unknown'))}
                                </div>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # Action buttons
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if log.get('status') == "Pending Verification":
                            st.info("⏳ Awaiting Verification")
                        elif not log.get('is_completed', False):
                            if st.button("✅ Complete", key=f"complete_{log['_id']}"):
                                try:
                                    self._mark_task_for_verification(str(log['_id']))
                                    st.success("⏳ Task marked for verification!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Failed to complete task: {str(e)}")
                        else:
                            pass
                    
            except Exception as e:
                st.error(f"❌ Error rendering task card: {str(e)}")

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

    def _batch_verify_tasks(self, tasks):
        """Verify multiple tasks at once"""
        verified_count = 0
        for task in tasks:
            try:
                self._verify_task_completion_with_timestamp(task)
                verified_count += 1
            except Exception as e:
                st.error(f"❌ Failed to verify task {task.get('substage_name', 'Unknown')}: {str(e)}")
        return verified_count

    def _bulk_complete_tasks(self, tasks):
        """Mark multiple tasks as complete"""
        completed_count = 0
        for task in tasks:
            try:
                if not task.get('is_completed', False):
                    self._mark_task_for_verification(str(task['_id']))
                    completed_count += 1
            except Exception as e:
                st.error(f"❌ Failed to complete task {task.get('substage_name', 'Unknown')}: {str(e)}")
        
        if completed_count > 0:
            st.success(f"✅ Marked {completed_count} tasks for verification!")
            st.rerun()

    def _bulk_delete_tasks(self, tasks):
        """Delete multiple tasks"""
        try:
            task_ids = [task['_id'] for task in tasks]
            result = self.log_manager.logs.delete_many({"_id": {"$in": task_ids}})
            st.success(f"🗑️ Deleted {result.deleted_count} tasks!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Bulk deletion failed: {str(e)}")

    def _bulk_update_priority(self, tasks, new_priority):
        """Update priority for multiple tasks"""
        try:
            task_ids = [task['_id'] for task in tasks]
            result = self.log_manager.logs.update_many(
                {"_id": {"$in": task_ids}},
                {"$set": {"priority": new_priority, "updated_at": datetime.now()}}
            )
            st.success(f"🔄 Updated priority for {result.modified_count} tasks!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Bulk priority update failed: {str(e)}")

    def _status_cell_renderer(self):
        """Custom cell renderer for status column"""
        return """
        function(params) {
            const status = params.value;
            const colors = {
                'Completed': '#4CAF50',
                'In Progress': '#FF9800',
                'Overdue': '#F44336',
                'Pending Verification': '#2196F3'
            };
            return '<span style="background-color:' + (colors[status] || '#666') + '; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em;">' + status + '</span>';
        }
        """

    def _priority_cell_renderer(self):
        """Custom cell renderer for priority column"""
        return """
        function(params) {
            const priority = params.value;
            const colors = {
                'High': '#FF5722',
                'Medium': '#FF9800',
                'Low': '#4CAF50'
            };
            return '<span style="background-color:' + (colors[priority] || '#666') + '; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em;">' + priority + '</span>';
        }
        """

    # Keep existing methods with improved error handling
    def _mark_task_for_verification(self, task_id):
        """Mark task for verification with error handling"""
        try:
            self.log_manager.logs.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {
                    "status": "Pending Verification",
                    "verified": False,
                    "completed_clicked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": datetime.now()
                }}
            )
        except Exception as e:
            st.error(f"❌ Failed to mark task for verification: {str(e)}")
            raise

    def _verify_task_completion_with_timestamp(self, log):
        """Verify all logs of the same substage or stage, then update stage completion."""
        try:
            project_id = log["project_id"]
            stage_key = log["stage_key"]
            substage_id = log.get("substage_id")
            current_time = datetime.now()

            if substage_id:
                # ✅ Verify all logs for the same substage
                self.log_manager.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key, "substage_id": substage_id},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "verified": True,
                        "verified_at": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_at": current_time
                    }}
                )
            else:
                # ✅ Stage-level log: verify all logs for this stage
                self.log_manager.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "verified": True,
                        "verified_at": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "updated_at": current_time
                    }}
                )

            # ✅ Recalculate and update stage completion
            self.log_manager.update_stage_completion_status(project_id, stage_key)
        except Exception as e:
            st.error(f"❌ Failed to verify task completion: {str(e)}")
            raise

    def _render_task_table(self, logs):
        """Enhanced task table with better functionality and error handling"""
        try:
            if not logs:
                st.info("📭 No tasks to display")
                return
                
            df = pd.DataFrame([
                {
                    "Project": log.get("project_name", "Unknown"),
                    "Stage": log.get("stage_name", "Unknown"),
                    "Substage": log.get("substage_name", "Unknown"),
                    "User": log.get("assigned_user", "Unknown"),
                    "Status": log.get("status", "Unknown"),
                    "Priority": log.get("priority", "Medium"),
                    "Start Date": self._format_date(log.get("start_date")),
                    "Deadline": self._format_date(log.get("substage_deadline", log.get("stage_deadline"))),
                    "Completed": "✅ Yes" if log.get("is_completed") else "❌ No",
                    "Updated": self._format_datetime(log.get("updated_at")),
                    "ID": str(log["_id"])
                }
                for log in logs
            ])
            
            # Enhanced grid configuration
            gb = GridOptionsBuilder.from_dataframe(df.drop('ID', axis=1))
            gb.configure_pagination(paginationAutoPageSize=True, paginationPageSize=20)
            gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)
            gb.configure_selection('single', use_checkbox=True)
            
            # Custom cell renderers
            gb.configure_column("Status", cellRenderer=self._status_cell_renderer(), width=120)
            gb.configure_column("Priority", cellRenderer=self._priority_cell_renderer(), width=100)
            gb.configure_column("Completed", width=100)
            gb.configure_column("Project", width=200)
            gb.configure_column("User", width=120)
            
            # Grid options
            gridOptions = gb.build()
            gridOptions['rowHeight'] = 40
            gridOptions['headerHeight'] = 45
            
            grid_response = AgGrid(
                df.drop('ID', axis=1), 
                gridOptions=gridOptions, 
                height=500, 
                fit_columns_on_grid_load=True,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                allow_unsafe_jscode=True  # Required for custom cell renderers
            )
            
            # Handle row selection for modal - FIXED: Improved error handling
            if grid_response.get('selected_rows') and len(grid_response['selected_rows']) > 0:
                try:
                    selected_row = grid_response['selected_rows'][0]
                    if '_selectedRowNodeInfo' in selected_row and 'nodeRowIndex' in selected_row['_selectedRowNodeInfo']:
                        selected_idx = selected_row['_selectedRowNodeInfo']['nodeRowIndex']
                        if 0 <= selected_idx < len(df):
                            selected_log_id = df.iloc[selected_idx]['ID']
                            selected_log = next((log for log in logs if str(log["_id"]) == selected_log_id), None)
                            if selected_log:
                                self._show_task_modal(selected_log)
                except (KeyError, IndexError, TypeError) as e:
                    st.warning("⚠️ Unable to load selected task details")
                    
        except Exception as e:
            st.error(f"❌ Error rendering task table: {str(e)}")

    def _show_task_modal(self, log):
        """Enhanced task modal with more functionality and error handling"""
        try:
            modal = Modal(f"Task Details: {log.get('substage_name', 'Unknown Task')}", 
                         key=f"task_modal_{log['_id']}", max_width=800)
            
            if modal.is_open():
                with modal.container():
                    # Header with key info
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"### 📝 {log.get('substage_name', 'Unknown Task')}")
                        st.markdown(f"**Project:** {log.get('project_name', 'Unknown')}")
                        st.markdown(f"**Stage:** {log.get('stage_name', 'Unknown')}")
                    with col2:
                        st.markdown(f"**Status:**")
                        st.markdown(format_status_badge(log.get('status', 'Unknown')), unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"**Priority:**")
                        st.markdown(format_priority_badge(log.get('priority', 'Medium')), unsafe_allow_html=True)
                    
                    st.divider()
                    
                    # Detailed information in tabs
                    tab1, tab2, tab3 = st.tabs(["📋 Details", "📅 Timeline", "⚡ Actions"])
                    
                    with tab1:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Assignment Info:**")
                            st.write(f"👤 **Assigned User:** {log.get('assigned_user', 'Unknown')}")
                            st.write(f"📅 **Start Date:** {self._format_date(log.get('start_date'))}")
                            st.write(f"⏰ **Stage Deadline:** {self._format_date(log.get('stage_deadline'))}")
                            st.write(f"⏰ **Substage Deadline:** {self._format_date(log.get('substage_deadline'))}")
                        
                        with col2:
                            st.markdown("**Progress Info:**")
                            st.write(f"✅ **Completed:** {'Yes' if log.get('is_completed') else 'No'}")
                            st.write(f"🔍 **Verified:** {'Yes' if log.get('verified') else 'No'}")
                            if log.get('completed_at'):
                                st.write(f"📅 **Completed At:** {self._format_datetime(log.get('completed_at'))}")
                            if log.get('verified_at'):
                                st.write(f"📅 **Verified At:** {log.get('verified_at')}")
                        
                        st.divider()
                        
                        # Editable description
                        current_desc = log.get('description', 'No description available')
                        new_desc = st.text_area("📝 **Description:**", value=current_desc, height=120, key=f"desc_{log['_id']}")
                        
                        if new_desc != current_desc:
                            if st.button("💾 Save Description", key=f"save_desc_{log['_id']}"):
                                try:
                                    self.log_manager.logs.update_one(
                                        {"_id": log["_id"]}, 
                                        {"$set": {"description": new_desc, "updated_at": datetime.now()}}
                                    )
                                    st.success("✅ Description updated!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Failed to update description: {str(e)}")
                    
                    with tab2:
                        st.markdown("**📅 Task Timeline:**")
                        
                        timeline_events = []
                        if log.get('created_at'):
                            timeline_events.append(("🆕 Created", log['created_at']))
                        if log.get('completed_clicked_at'):
                            timeline_events.append(("✅ Marked Complete", log['completed_clicked_at']))
                        if log.get('verified_at'):
                            timeline_events.append(("🔍 Verified", log['verified_at']))
                        if log.get('updated_at'):
                            timeline_events.append(("🔄 Last Updated", log['updated_at']))
                        
                        for event_name, event_time in timeline_events:
                            formatted_time = self._format_datetime(event_time)
                            st.write(f"**{event_name}:** {formatted_time}")
                        
                        # Progress visualization
                        if log.get('start_date') and log.get('substage_deadline'):
                            try:
                                start_date = datetime.strptime(log['start_date'], '%Y-%m-%d')
                                end_date = datetime.strptime(log['substage_deadline'], '%Y-%m-%d')
                                current_date = datetime.now()
                                
                                total_days = (end_date - start_date).days
                                elapsed_days = (current_date - start_date).days
                                progress = min(max(elapsed_days / total_days if total_days > 0 else 0, 0), 1)
                                
                                st.markdown("**📊 Time Progress:**")
                                st.progress(progress)
                                st.write(f"Days elapsed: {elapsed_days} / {total_days}")
                            except Exception:
                                st.write("Unable to calculate time progress")
                    
                    with tab3:
                        st.markdown("**⚡ Available Actions:**")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if log.get('status') == "Pending Verification":
                                if st.button("✅ Verify Completion", key=f"verify_modal_{log['_id']}", type="primary"):
                                    try:
                                        self._verify_task_completion_with_timestamp(log)
                                        st.success("✅ Task verified and marked completed!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Verification failed: {str(e)}")
                            elif not log.get('is_completed', False):
                                if st.button("✅ Mark Complete", key=f"complete_modal_{log['_id']}", type="primary"):
                                    try:
                                        if self.log_manager.complete_task(str(log['_id'])):
                                            st.success("✅ Task completed!")
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to complete task")
                                    except Exception as e:
                                        st.error(f"❌ Completion failed: {str(e)}")
                            else:
                                st.success("✅ Task Completed")
                        
                        with col2:
                            # Priority change
                            current_priority = log.get('priority', 'Medium')
                            new_priority = st.selectbox(
                                "Change Priority", 
                                ["High", "Medium", "Low","Critical"], 
                                index=["High", "Medium", "Low","Critical"].index(current_priority),
                                key=f"priority_{log['_id']}"
                            )
                            if new_priority != current_priority:
                                if st.button("🔄 Update Priority", key=f"update_priority_{log['_id']}"):
                                    try:
                                        self.log_manager.logs.update_one(
                                            {"_id": log["_id"]}, 
                                            {"$set": {"priority": new_priority, "updated_at": datetime.now()}}
                                        )
                                        st.success(f"🔄 Priority updated to {new_priority}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Priority update failed: {str(e)}")
                        
                        with col3:
                            # Danger zone
                            st.markdown("**⚠️ Danger Zone:**")
                            if st.button("🗑️ Delete Task", key=f"delete_modal_{log['_id']}", type="secondary"):
                                if st.checkbox("⚠️ Confirm deletion", key=f"confirm_delete_{log['_id']}"):
                                    try:
                                        self.log_manager.logs.delete_one({"_id": log["_id"]})
                                        st.warning("🗑️ Task deleted!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Deletion failed: {str(e)}")
                    
                    # Close modal button
                    st.divider()
                    if st.button("❌ Close", key=f"close_modal_{log['_id']}"):
                        modal.close()
                        
        except Exception as e:
            st.error(f"❌ Error displaying task modal: {str(e)}")

    def run(self):
        """Main application runner with enhanced error handling"""
        if not self.log_manager.client:
            st.error("❌ Cannot proceed without database connection")
            with st.expander("🔧 Database Connection Debug"):
                if st.button("🔍 Test Connection"):
                    self.log_manager.debug_database_connection()
            return

        try:
            user_role = st.session_state.get("role", "user")
            current_user = st.session_state.get("username", "Guest")
            
            if user_role in ["admin", "manager"]:
                # Admin/Manager interface
                try:
                    pending_count = self.log_manager.logs.count_documents({"status": "Pending Verification"})
                    verification_tab_label = f"✅ Verification ({pending_count})" if pending_count > 0 else "✅ Verification"
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch pending count: {str(e)}")
                    verification_tab_label = "✅ Verification"

                tab_dashboard, tab_user_logs, tab_verification = st.tabs([
                    "📊 Dashboard", "👤 Task Management", verification_tab_label
                ])
                
                with tab_dashboard:
                    try:
                        self.render_dashboard_tab()
                    except Exception as e:
                        st.error(f"❌ Dashboard error: {str(e)}")
                        st.exception(e)
                
                with tab_user_logs:
                    try:
                        self.render_user_logs_tab(is_admin=True)
                    except Exception as e:
                        st.error(f"❌ Task management error: {str(e)}")
                        st.exception(e)
                
                with tab_verification:
                    try:
                        self.render_verification_tab()
                    except Exception as e:
                        st.error(f"❌ Verification error: {str(e)}")
                        st.exception(e)
            else:
                # Regular user interface
                try:
                    self.render_user_logs_tab(is_admin=False)
                except Exception as e:
                    st.error(f"❌ User interface error: {str(e)}")
                    st.exception(e)
        
        except Exception as e:
            st.error(f"❌ Application error: {str(e)}")
            st.exception(e)


def run():
    """Application entry point"""
    try:
        app = ProjectLogFrontend()
        app.run()
    except Exception as e:
        st.error(f"❌ Failed to start application: {str(e)}")
        st.exception(e)