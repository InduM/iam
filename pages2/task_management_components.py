import streamlit as st
import pandas as pd
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from bson import ObjectId
from utils.utils_log import format_status_badge


class TaskManagementComponents:
    def __init__(self, log_manager):
        self.log_manager = log_manager

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

        # Pass context to make toolbar keys unique
        toolbar_context = "admin" if is_admin else "user"
        self._render_toolbar(all_logs, context=toolbar_context)

        username = st.session_state.get("username", "Unknown User")
        role = st.session_state.get("role", "user")

        # Enhanced search
        col1, col2 = st.columns([3, 1])
        with col1:
            search_key = "admin_logs_search" if is_admin else "user_logs_search"
            search_query = st.text_input("🔍 Search Tasks", key=search_key, placeholder="Search by project, task, user...")
        with col2:
            search_in_key = "admin_logs_search_in" if is_admin else "user_logs_search_in"
            search_in = st.selectbox("Search In", key=search_in_key, options=["All Fields", "Project Name", "Task Name", "User"])

        if is_admin:
            # Manager role restriction
            if role == "manager":
                all_logs = [log for log in all_logs if log.get("created_by") == username]

            with st.expander("🔍 Advanced Filters", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    try:
                        projects = self.log_manager.get_projects()
                        project_names = ["All"] + [p['name'] for p in projects]
                        selected_project = st.selectbox("Project", key="admin_project_filter", options=project_names)
                    except Exception as e:
                        st.error(f"❌ Error loading projects: {str(e)}")
                        selected_project = "All"
                
                with col2:
                    try:
                        users = ["All Users"] + self.log_manager.get_all_users()
                        selected_user = st.selectbox("User", key="admin_user_filter", options=users)
                    except Exception as e:
                        st.error(f"❌ Error loading users: {str(e)}")
                        selected_user = "All Users"
                
                with col3:
                    status_filter = st.multiselect(
                        "Status", key="admin_status_filter",
                        options=["Completed", "Pending Verification", "Overdue", "In Progress"],
                        default=["Completed", "Pending Verification", "Overdue", "In Progress"]
                    )

                col4, col5, col6 = st.columns(3)
                
                with col4:
                    priority_filter = st.multiselect(
                        "Priority", key="admin_priority_filter",
                        options=["High", "Medium", "Low", "Critical"],
                        default=["High", "Medium", "Low", "Critical"]
                    )
                
                with col5:
                    date_filter = st.date_input("Deadline Range", key="admin_date_filter", value=None, help="Filter by deadline range")
                
                with col6:
                    include_completed = st.checkbox("Include Completed", key="admin_include_completed", value=True)
                    overdue_only = st.checkbox("Show Overdue Only", key="admin_overdue_only", value=False)

            try:
                filtered_logs = self._apply_filters(
                    all_logs, selected_project, selected_user, status_filter, 
                    priority_filter, include_completed, overdue_only, search_query, search_in
                )
                filtered_logs = self._sort_logs(filtered_logs)
            except Exception as e:
                st.error(f"❌ Error applying filters: {str(e)}")
                filtered_logs = self._sort_logs(all_logs)

            st.subheader(f"📋 Showing {len(filtered_logs)} of {len(all_logs)} tasks")
            
            if len(filtered_logs) > 0:
                with st.expander("⚡ Bulk Operations", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Mark All Complete", key="admin_bulk_complete_all"):
                            if st.checkbox("Confirm bulk completion", key="admin_bulk_complete_confirm"):
                                self._bulk_complete_tasks(filtered_logs)
                    with col2:
                        if st.button("🗑️ Delete Selected", key="admin_bulk_delete_all"):
                            if st.checkbox("Confirm bulk deletion", key="admin_bulk_delete_confirm"):
                                self._bulk_delete_tasks(filtered_logs)
                    with col3:
                        priority_change = st.selectbox("Change Priority To", key="admin_bulk_priority_change", options=["High", "Medium", "Low", "Critical"])
                        if st.button("🔄 Update Priority", key="admin_bulk_update_priority"):
                            self._bulk_update_priority(filtered_logs, priority_change)

                self._render_task_table(filtered_logs, context="admin")
            else:
                st.info("📭 No tasks match your filters")

        else:
            try:
                user_logs = [log for log in all_logs if log.get("assigned_user") == username]
                if search_query:
                    user_logs = self._search_logs(user_logs, search_query, search_in)
                user_logs = self._sort_logs(user_logs)
            except Exception as e:
                st.error(f"❌ Error filtering user logs: {str(e)}")
                user_logs = []

            st.subheader(f"📋 Your Assigned Tasks ({len(user_logs)})")
            
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

    def _render_toolbar(self, logs, context="default"):
        """Enhanced toolbar with additional functionality"""
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            if st.button("🔄 Refresh", key=f"toolbar_refresh_btn_{context}", help="Refresh the current view"):
                st.rerun()

    def _apply_filters(self, logs, project, user, status, priority, include_completed, overdue_only, search_query, search_in):
        """Apply all filters to logs with improved error handling"""
        if not logs:
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
                
                # Status filter
                if status and log.get("status") not in status:
                    continue
                
                # Priority filter
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
            except Exception:
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
    
    def _sort_logs(self, logs):
        """
        Sort logs so that:
        1. Overdue tasks first (regardless of priority)
        2. Current tasks (today's date or earlier, but not overdue)
        3. Upcoming tasks (future deadlines) at the bottom
        Within each group:
            a. Incomplete before completed
            b. Priority order: Critical → High → Medium → Low
            c. Earliest deadline first
        """
        try:
            priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            today = datetime.today().date()

            def sort_key(log):
                # Parse deadline
                deadline_str = log.get("substage_deadline") or log.get("stage_deadline") or ""
                try:
                    deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d").date() if deadline_str else None
                except Exception:
                    deadline_dt = None

                # 1. Determine task group: 0 = overdue, 1 = current, 2 = upcoming
                if deadline_dt and deadline_dt < today and not log.get("is_completed", False):
                    group_flag = 0  # Overdue
                elif deadline_dt and deadline_dt > today:
                    group_flag = 2  # Upcoming
                else:
                    group_flag = 1  # Current

                # 2. Completion flag (incomplete first)
                completed_flag = 0 if not log.get("is_completed", False) else 1

                # 3. Priority rank
                priority_rank = priority_order.get(log.get("priority", "Medium"), 2)

                # 4. Earliest deadline first (None = bottom)
                deadline_sort = deadline_dt if deadline_dt else datetime.max.date()

                return (group_flag, completed_flag, priority_rank, deadline_sort)

            return sorted(logs, key=sort_key)

        except Exception as e:
            st.warning(f"⚠️ Error sorting logs: {str(e)}")
            return logs

    def _render_user_task_cards(self, user_logs):
        """Render user tasks as cards grouped into Overdue, Current, and Upcoming."""
        try:
            user_logs = self._sort_logs(user_logs)
            today = datetime.today().date()
            overdue_tasks, current_tasks, upcoming_tasks = [], [], []

            for log in user_logs:
                deadline_str = log.get("substage_deadline") or log.get("stage_deadline") or ""
                try:
                    deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d").date() if deadline_str else None
                except Exception:
                    deadline_dt = None

                if deadline_dt and deadline_dt < today and not log.get("is_completed", False):
                    overdue_tasks.append(log)
                elif deadline_dt and deadline_dt > today:
                    upcoming_tasks.append(log)
                else:
                    current_tasks.append(log)

            def render_group(title, tasks, color):
                if tasks:
                    st.markdown(f"### {title}")
                    st.markdown(f"<hr style='border:1px solid {color};'/>", unsafe_allow_html=True)
                    for log in tasks:
                        try:
                            overdue_style = "border-left: 4px solid #f44336;" if title == "Overdue Tasks" else "border-left: 4px solid #4caf50;"
                            priority = log.get('priority', 'Medium')
                            priority_colors = {
                                "High": "#ffebee",
                                "Medium": "#fff3e0",
                                "Low": "#F9F9F9",
                                "Critical": "#FF0000"
                            }
                            priority_color = priority_colors.get(priority, "#f5f5f5")
                            deadline = log.get('substage_deadline') or log.get('stage_deadline') or 'N/A'

                            st.markdown(
                                f"""
                                <div style='{overdue_style} background-color:{priority_color}; padding:12px; border-radius:8px; margin:8px 0;'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <div>
                                            <strong style='font-size: 1.1em;'>{log.get('project_name', 'Unknown Project')}</strong><br>
                                            <small style='color: #666;'>Stage: {log.get('stage_name', 'Unknown')} → {log.get('substage_name', 'Unknown')}</small><br>
                                            <small style='color: #888;'>Priority: {priority} | Deadline: {self._format_date(deadline)}</small>
                                        </div>
                                        <div style='text-align: right;'>
                                            {format_status_badge(log.get('status', 'Unknown'))}
                                        </div>
                                    </div>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )

                            # ✅ Now render task actions under each card
                            self._render_task_actions(log, context="user")

                        except Exception as e:
                            st.error(f"❌ Error rendering task card: {str(e)}")

            render_group("Overdue Tasks", overdue_tasks, "#f44336")
            render_group("Current Tasks", current_tasks, "#4caf50")
            render_group("Upcoming Tasks", upcoming_tasks, "#2196f3")

        except Exception as e:
            st.error(f"❌ Error preparing user task cards: {str(e)}")


    def _render_task_table(self, logs, context="default"):
        """Enhanced task table with better functionality, error handling, sorting, and manager restriction."""
        try:
            if not logs:
                st.info("📭 No tasks to display")
                return

            # Manager restriction for admin-style views
            username = st.session_state.get("username", "Unknown User")
            role = st.session_state.get("role", "user")
            if role == "manager" and context in ["admin", "default"]:
                logs = [log for log in logs if log.get("created_by") == username]

            if not logs:
                st.info("📭 No tasks available after applying manager restrictions")
                return

            # Apply sorting before display
            logs = self._sort_logs(logs)

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
                    # ✅ Add rejection reason column
                    "Rejection Reason": log.get("extension_rejection_notes", ""),
                    "ID": str(log["_id"])
                }
                for log in logs
            ])


            gb = GridOptionsBuilder.from_dataframe(df.drop('ID', axis=1))
            gb.configure_pagination(paginationAutoPageSize=True, paginationPageSize=20)
            gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)
            gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren=True, groupSelectsFiltered=True)

            gb.configure_column("Status", cellRenderer=self._status_cell_renderer(), width=120)
            gb.configure_column("Priority", cellRenderer=self._priority_cell_renderer(), width=100)
            gb.configure_column("Completed", width=100)
            gb.configure_column("Project", width=200)
            gb.configure_column("User", width=120)

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
                allow_unsafe_jscode=True,
                key=f"task_table_aggrid_{context}"
            )

            selected_rows = grid_response.get('selected_rows', [])
            if isinstance(selected_rows, pd.DataFrame) and not selected_rows.empty:
                selected_rows = selected_rows.to_dict('records')
            elif not isinstance(selected_rows, list):
                selected_rows = []

            if selected_rows and len(selected_rows) > 0:
                try:
                    selected_task_data = self._get_selected_tasks_data(selected_rows, df, logs)

                    if selected_task_data:
                        with st.container():
                            st.info(f"🎯 Selected {len(selected_task_data)} task(s)")

                            with st.expander(f"📋 Selected Tasks ({len(selected_task_data)})", expanded=False):
                                for task_data in selected_task_data:
                                    st.write(f"• **{task_data['log'].get('project_name', 'Unknown')}** - {task_data['log'].get('substage_name', 'Unknown')} (Priority: {task_data['log'].get('priority', 'Medium')})")

                            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

                            with col1:
                                new_priority = st.selectbox(
                                    "Change Priority for Selected",
                                    options=["High", "Medium", "Low", "Critical"],
                                    index=1,
                                    key=f"bulk_priority_select_{context}"
                                )

                            with col2:
                                if st.button("🔄 Update Priority", key=f"update_selected_priority_{context}", type="primary"):
                                    updated_count = self._update_selected_tasks_priority(selected_task_data, new_priority)
                                    if updated_count > 0:
                                        st.success(f"🔄 Priority updated to {new_priority} for {updated_count} selected task(s)!")
                                        st.rerun()
                                    else:
                                        st.warning("⚠️ No tasks were updated")

                            with col3:
                                if st.button("✅ Complete Selected", key=f"complete_selected_tasks_{context}", type="secondary"):
                                    completed_count = self._complete_selected_tasks(selected_task_data)
                                    if completed_count > 0:
                                        st.success(f"✅ Marked {completed_count} selected task(s) for verification!")
                                        st.rerun()

                            with col4:
                                pending_tasks = [task for task in selected_task_data if task['log'].get('status') == 'Pending Verification']
                                if pending_tasks:
                                    if st.button(f"✅ Verify Selected ({len(pending_tasks)})", key=f"verify_selected_tasks_{context}", type="secondary"):
                                        verified_count = self._verify_selected_tasks(pending_tasks)
                                        if verified_count > 0:
                                            st.success(f"✅ Verified {verified_count} selected task(s)!")
                                            st.rerun()

                except Exception as e:
                    st.warning(f"⚠️ Unable to load selected task details: {str(e)}")
            else:
                st.info("ℹ️ Check the boxes next to rows to perform bulk actions on selected tasks")

        except Exception as e:
            st.error(f"❌ Error rendering task table: {str(e)}")

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
                'Low': '#F9F9F9',
                'Critical': '#FF0000'
            };
            return '<span style="background-color:' + (colors[priority] || '#666') + '; color:white; padding:2px 8px; border-radius:12px; font-size:0.8em;">' + priority + '</span>';
        }
        """

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

    def _update_selected_tasks_priority(self, selected_task_data, new_priority):
        """Update priority for only the selected/checked tasks"""
        try:
            if not selected_task_data:
                return 0
            
            # Extract ObjectIds from selected tasks
            task_ids = [ObjectId(task_data['task_id']) for task_data in selected_task_data]
            
            # Update only the selected tasks
            result = self.log_manager.logs.update_many(
                {"_id": {"$in": task_ids}},
                {"$set": {
                    "priority": new_priority, 
                    "updated_at": datetime.now()
                }}
            )
            
            return result.modified_count
            
        except Exception as e:
            st.error(f"❌ Failed to update priority for selected tasks: {str(e)}")
            return 0

    def _complete_selected_tasks(self, selected_task_data):
        """Mark selected tasks as complete"""
        try:
            completed_count = 0
            
            for task_data in selected_task_data:
                try:
                    task_log = task_data['log']
                    if not task_log.get('is_completed', False):
                        self._mark_task_for_verification(task_data['task_id'])
                        completed_count += 1
                except Exception as e:
                    st.warning(f"⚠️ Failed to complete task {task_data['log'].get('substage_name', 'Unknown')}: {str(e)}")
                    continue
            
            return completed_count
            
        except Exception as e:
            st.error(f"❌ Failed to complete selected tasks: {str(e)}")
            return 0

    def _verify_selected_tasks(self, selected_task_data):
        """Verify selected tasks that are pending verification"""
        try:
            verified_count = 0
            
            for task_data in selected_task_data:
                try:
                    task_log = task_data['log']
                    if task_log.get('status') == 'Pending Verification':
                        self._verify_task_completion_with_timestamp(task_log)
                        verified_count += 1
                except Exception as e:
                    st.warning(f"⚠️ Failed to verify task {task_data['log'].get('substage_name', 'Unknown')}: {str(e)}")
                    continue
            
            return verified_count
            
        except Exception as e:
            st.error(f"❌ Failed to verify selected tasks: {str(e)}")
            return 0

    def _get_selected_tasks_data(self, selected_rows, df, logs):
        """Extract task data for selected rows, with manager restrictions."""
        try:
            username = st.session_state.get("username", "Unknown User")
            role = st.session_state.get("role", "user")
            selected_task_data = []

            for selected_row in selected_rows:
                try:
                    # Find the corresponding row in the dataframe
                    matching_rows = df[
                        (df['Project'] == selected_row.get('Project', '')) &
                        (df['Stage'] == selected_row.get('Stage', '')) &
                        (df['Substage'] == selected_row.get('Substage', '')) &
                        (df['User'] == selected_row.get('User', ''))
                    ]
                    
                    if not matching_rows.empty:
                        # Get the first match (should be unique)
                        matched_row = matching_rows.iloc[0]
                        task_id = matched_row['ID']

                        # Find the corresponding log
                        matching_log = next((log for log in logs if str(log["_id"]) == task_id), None)

                        if matching_log:
                            # Apply manager restriction
                            if role == "manager" and matching_log.get("created_by") != username:
                                continue

                            selected_task_data.append({
                                'task_id': task_id,
                                'log': matching_log
                            })
                            
                except Exception as e:
                    st.warning(f"⚠️ Error processing selected row: {str(e)}")
                    continue

            return selected_task_data

        except Exception as e:
            st.error(f"❌ Error extracting selected tasks: {str(e)}")
            return []

    def _verify_task_completion_with_timestamp(self, log):
        """Verify all logs of the same substage or stage, then update stage completion and project page."""
        try:
            project_id = log["project_id"]
            stage_key = log["stage_key"]
            substage_id = log.get("substage_id")
            current_time = datetime.now()

            if substage_id:
                # Verify all logs for the same substage
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
                
                # Update project's substage completion status
                self._update_project_substage_completion(project_id, stage_key, substage_id, True)
                
            else:
                # Stage-level log: verify all logs for this stage
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
                
                # Update project's stage completion status
                self._update_project_stage_completion(project_id, stage_key, True)

            # Recalculate and update stage completion
            self.log_manager.update_stage_completion_status(project_id, stage_key)
            
        except Exception as e:
            st.error(f"❌ Failed to verify task completion: {str(e)}")
            raise
        
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
        
    def _update_project_substage_completion(self, project_id, stage_key, substage_id, completed_status):
        """Update substage completion status in the project document"""
        try:
            from bson import ObjectId
            
            # Parse the substage_id to extract the substage index
            # Format: substage_{stage_index}_{substage_index}_{random_id}
            parts = substage_id.split('_')
            if len(parts) >= 3:
                stage_index = parts[1]
                substage_index = parts[2]
                
                # Update the project's substage_completion field
                update_field = f"substage_completion.{stage_index}.{substage_index}"
                
                self.log_manager.projects.update_one(
                    {"_id": ObjectId(project_id)},
                    {"$set": {
                        update_field: completed_status,
                        "updated_at": datetime.now()
                    }}
                )
                
                # Also update the substage timestamps if completing
                if completed_status:
                    timestamp_field = f"substage_timestamps.{stage_index}.{substage_index}"
                    self.log_manager.projects.update_one(
                        {"_id": ObjectId(project_id)},
                        {"$set": {
                            timestamp_field: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }}
                    )
                else:
                    # Remove timestamp if undoing completion
                    timestamp_field = f"substage_timestamps.{stage_index}.{substage_index}"
                    self.log_manager.projects.update_one(
                        {"_id": ObjectId(project_id)},
                        {"$unset": {timestamp_field: ""}}
                    )
                    
        except Exception as e:
            st.error(f"❌ Failed to update project substage completion: {str(e)}")
            raise


    def _update_project_stage_completion(self, project_id, stage_key, completed_status):
        """Update stage completion status in the project document"""
        try:
            from bson import ObjectId
            
            # Update the project's level (stage completion)
            if completed_status:
                # Get current project to determine next level
                project = self.log_manager.projects.find_one({"_id": ObjectId(project_id)})
                if project:
                    current_level = project.get("level", 0)
                    stage_index = int(stage_key) if stage_key.isdigit() else 0
                    
                    # Only update level if this stage is the current or next stage
                    if stage_index >= current_level:
                        new_level = stage_index + 1
                        self.log_manager.projects.update_one(
                            {"_id": ObjectId(project_id)},
                            {"$set": {
                                "level": new_level,
                                f"timestamps.{stage_key}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "updated_at": datetime.now()
                            }}
                        )
            else:
                # When undoing, we need to be careful not to break the progression
                project = self.log_manager.projects.find_one({"_id": ObjectId(project_id)})
                if project:
                    stage_index = int(stage_key) if stage_key.isdigit() else 0
                    current_level = project.get("level", 0)
                    
                    # Only decrease level if this was the most recently completed stage
                    if stage_index == current_level - 1:
                        self.log_manager.projects.update_one(
                            {"_id": ObjectId(project_id)},
                            {"$set": {
                                "level": stage_index,
                                "updated_at": datetime.now()
                            },
                            "$unset": {
                                f"timestamps.{stage_key}": ""
                            }}
                        )
                        
        except Exception as e:
            st.error(f"❌ Failed to update project stage completion: {str(e)}")
            raise

    def _render_task_actions(self, log, context="default"):
        """Render task action buttons with deadline extension"""
        col1, col2, col3 = st.columns([1, 1, 1])
        
        # ✅ Complete button
        with col1:
            if log.get("status") != "Completed" and log.get("status") != "Pending Deadline Approval":
                if st.button("✅ Complete", key=f"complete_btn_{log['_id']}_{context}"):
                    if self.log_manager.mark_task_completed(str(log["_id"]), st.session_state.get("username", "Unknown")):
                        st.success("✅ Task marked as completed!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to complete task")
        
        # ⏰ Extend Deadline button — always to the right of Complete
        with col2:
            task_status = log.get("status")
            current_task_statuses = ["In Progress", "Overdue", "Upcoming"]
            if (task_status != "Completed" and 
                task_status in current_task_statuses and 
                task_status not in ["Pending Deadline Approval", "Pending Verification"]):
                if st.button("⏰ Extend Deadline", key=f"extend_deadline_btn_{log['_id']}_{context}"):
                    st.session_state[f"show_extension_form_{log['_id']}"] = True
                    st.rerun()
        
        # Show status message for pending deadline approval
        if log.get("status") == "Pending Deadline Approval":
            st.info("⏳ Deadline extension request is pending admin approval")
        
                # Show rejection reason if present
        if log.get("extension_rejection_notes"):
            st.error(f"❌ Deadline extension request was rejected: {log['extension_rejection_notes']}")
        
        # Show deadline extension form if requested
        if st.session_state.get(f"show_extension_form_{log['_id']}", False):
            self._render_deadline_extension_form(log, context)

    def _render_deadline_extension_form(self, log, context="default"):
        """Render deadline extension request form"""
        with st.container():
            st.markdown("---")
            st.subheader("🔄 Request Deadline Extension")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Current Deadline:** {self._format_date(log.get('substage_deadline', log.get('stage_deadline')))}")
            
            with col2:
                st.write(f"**Task:** {log['stage_name']} → {log['substage_name']}")
            
            extension_reason = st.text_area(
                "Reason for Extension:",
                key=f"extension_reason_{log['_id']}_{context}",
                placeholder="Please provide a detailed reason for the deadline extension request...",
                height=100
            )
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("📤 Submit Request", key=f"submit_extension_{log['_id']}_{context}"):
                    if extension_reason.strip():
                        username = st.session_state.get("username", "Unknown")
                        if self.log_manager.request_deadline_extension(str(log["_id"]), extension_reason, username):
                            st.success("✅ Deadline extension request submitted!")
                            st.session_state[f"show_extension_form_{log['_id']}"] = False
                            st.rerun()
                        else:
                            st.error("❌ Failed to submit extension request")
                    else:
                        st.error("❌ Please provide a reason for the extension")
            
            with col2:
                if st.button("❌ Cancel", key=f"cancel_extension_{log['_id']}_{context}"):
                    st.session_state[f"show_extension_form_{log['_id']}"] = False
                    st.rerun()

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