import streamlit as st
import pandas as pd
from datetime import datetime
from backend.log_backend import ProjectLogManager
from utils.utils_log import format_status_badge, format_priority_badge


class ProjectLogFrontend:
    def __init__(self):
        """Initialize the frontend with backend connection"""
        self.log_manager = ProjectLogManager()
        
    def setup_page_config(self):
        """Setup Streamlit page configuration"""
        pass
    
        
    def render_dashboard_tab(self):
        """Render the Dashboard tab content"""
        
        # Refresh logs button
        if st.button("🔄 Refresh Logs from Projects", type="primary"):
            with st.spinner("Extracting assignments from projects..."):
                logs_created = self.log_manager.extract_and_create_logs()
                st.success(f"✅ Created {logs_created} log entries from project assignments")
        
        # Overview metrics
        overview = self.log_manager.get_project_overview()
        if overview:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("📁 Total Projects", overview.get("total_projects", 0))
            with col2:
                st.metric("📋 Total Tasks", overview.get("total_logs", 0))
            with col3:
                st.metric("✅ Completed", overview.get("completed_tasks", 0))
            with col4:
                st.metric("🔴 Overdue", overview.get("overdue_tasks", 0))
            with col5:
                st.metric("🟡 In Progress", overview.get("in_progress_tasks", 0))
        
        # Recent activity
        self._render_recent_activity()
        
    def _render_recent_activity(self):
        """Render recent activity section"""
        st.subheader("📈 Recent Activity")
        recent_logs = list(self.log_manager.logs.find({}).sort("updated_at", -1).limit(10))
        
        if recent_logs:
            for log in recent_logs:
                with st.expander(f"{log['project_name']} - {log['substage_name']} ({log['assigned_user']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Status:** {format_status_badge(log['status'])}")
                        st.write(f"**Priority:** {format_priority_badge(log.get('priority', 'Medium'))}")
                        st.write(f"**Client:** {log.get('client', 'N/A')}")
                    with col2:
                        st.write(f"**Stage:** {log['stage_name']}")
                        st.write(f"**Deadline:** {log.get('substage_deadline', log.get('stage_deadline', 'Not Set'))}")
                        updated_time = log.get('updated_at', log.get('created_at'))
                        if updated_time:
                            st.write(f"**Updated:** {updated_time.strftime('%Y-%m-%d %H:%M')}")
                        else:
                            st.write("**Updated:** N/A")
    
    def render_user_logs_tab(self, is_admin=True):
        """Render the User Logs tab content"""        
        # Get current user info
        current_user = st.session_state.get("username", "Unknown User")
        user_role = st.session_state.get("role", "user")
        
        # Project selection
        projects = self.log_manager.get_projects()
        project_options = ["All Projects"] + [p['name'] for p in projects]
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_project = st.selectbox(
                "Select Project", 
                project_options,
                format_func=lambda x: x if x == "All Projects" else f"{x} ({next((p['client'] for p in projects if p['name'] == x), 'N/A')})"
            )
        
        # Get users based on project selection and role
        if selected_project == "All Projects":
            if is_admin:
                users = self.log_manager.get_all_users()
            else:
                users = [current_user] if current_user in self.log_manager.get_all_users() else []
            project_filter = None
        else:
            if is_admin:
                users = self.log_manager.get_project_users(selected_project)
            else:
                project_users = self.log_manager.get_project_users(selected_project)
                users = [current_user] if current_user in project_users else []
            project_filter = selected_project
        
        with col2:
            if users:
                if is_admin:
                    selected_user = st.selectbox("Select User", users)
                else:
                    # For non-admin users, automatically select current user
                    selected_user = current_user
                    st.selectbox("Select User", [current_user], disabled=True)
            else:
                if is_admin:
                    st.warning(f"⚠️ No users found for {selected_project}")
                else:
                    st.warning(f"⚠️ You have no tasks in {selected_project}")
                selected_user = None
        
        if selected_user:
            self._render_user_tasks(selected_user, project_filter)
        else:
            if selected_project != "All Projects":
                if is_admin:
                    st.info(f"ℹ️ No users assigned to tasks in {selected_project}")
                else:
                    st.info(f"ℹ️ You have no tasks assigned in {selected_project}")
            else:
                if is_admin:
                    st.info("ℹ️ Please select a user to view their tasks")
                else:
                    st.info("ℹ️ You have no tasks assigned")
    
    def _render_user_tasks(self, selected_user, project_filter):
        """Render tasks for selected user"""
        # Get logs for selected user and project
        if project_filter:
            user_logs = self.log_manager.get_user_logs_by_project(selected_user, project_filter)
            st.subheader(f"📋 Tasks for {selected_user} in {project_filter}")
        else:
            user_logs = self.log_manager.get_user_logs(selected_user)
            st.subheader(f"📋 All Tasks for {selected_user}")
        
        if user_logs:
            # Filters
            filtered_logs = self._render_user_filters(user_logs, project_filter)
            
            # Display logs
            self._render_task_list(filtered_logs)
            
            st.info(f"📊 Showing {len(filtered_logs)} of {len(user_logs)} tasks")
        else:
            if project_filter:
                st.info(f"📭 No logs found for {selected_user} in {project_filter}")
            else:
                st.info(f"📭 No logs found for {selected_user}")
    
    def _render_user_filters(self, user_logs, project_filter):
        """Render filter controls for user logs"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            all_statuses = list(set([log["status"] for log in user_logs]))
            status_filter = st.multiselect("Filter by Status", all_statuses, default=all_statuses)
        
        with col2:
            all_priorities = list(set([log.get("priority", "Medium") for log in user_logs]))
            priority_filter = st.multiselect("Filter by Priority", all_priorities, default=all_priorities)
        
        with col3:
            if project_filter is None:
                all_user_projects = list(set([log["project_name"] for log in user_logs]))
                user_project_filter = st.multiselect("Filter by Project", all_user_projects, default=all_user_projects)
            else:
                user_project_filter = [project_filter]
        
        # Apply filters
        filtered_logs = [
            log for log in user_logs 
            if log["status"] in status_filter 
            and log.get("priority", "Medium") in priority_filter
            and log["project_name"] in user_project_filter
        ]
        
        return filtered_logs
    
    def _render_task_list(self, filtered_logs):
        """Render the list of tasks"""
        for log in filtered_logs:
            with st.expander(f"🏗️ {log['project_name']} - {log['stage_name']} > {log['substage_name']}"):
                col1, col2, col3 = st.columns([3, 3, 2])
                
                with col1:
                    st.write(f"**Project:** {log['project_name']}")
                    st.write(f"**Client:** {log.get('client', 'N/A')}")
                    st.write(f"**Stage:** {log['stage_name']}")
                    st.write(f"**Substage:** {log['substage_name']}")
                    st.write(f"**Status:** {format_status_badge(log['status'])}")
                    st.write(f"**Priority:** {format_priority_badge(log.get('priority', 'Medium'))}")
                
                with col2:
                    st.write(f"**Start Date:** {log['start_date'] or 'Not Set'}")
                    st.write(f"**Stage Deadline:** {log['stage_deadline'] or 'Not Set'}")
                    st.write(f"**Substage Deadline:** {log['substage_deadline'] or 'Not Set'}")
                    if log.get('description'):
                        desc = log['description']
                        st.write(f"**Description:** {desc[:100]}{'...' if len(desc) > 100 else ''}")
                
                with col3:
                    if not log.get('is_completed', False):
                        if st.button(f"✅ Mark Complete", key=f"complete_{log['_id']}"):
                            if self.log_manager.complete_task(str(log['_id'])):
                                st.success("✅ Task completed successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to complete task")
                    else:
                        st.success("✅ Completed")
                        if log.get('completed_at'):
                            st.write(f"**Completed:** {log['completed_at'].strftime('%Y-%m-%d %H:%M')}")
    
    def render_project_overview_tab(self):
        """Render the Project Overview tab content"""        
        projects = self.log_manager.get_projects()
        
        if projects:
            selected_project = st.selectbox(
                "Select Project", 
                options=[p['name'] for p in projects],
                format_func=lambda x: f"{x} ({next(p['client'] for p in projects if p['name'] == x)})"
            )
            
            # Get logs for selected project
            project_logs = list(self.log_manager.logs.find({"project_name": selected_project}))
            
            if project_logs:
                self._render_project_statistics(project_logs)
                self._render_stage_breakdown(project_logs)
            else:
                st.info(f"📭 No tasks found for {selected_project}")
        else:
            st.warning("⚠️ No projects found")
    
    def _render_project_statistics(self, project_logs):
        """Render project statistics"""
        col1, col2, col3, col4 = st.columns(4)
        
        total_tasks = len(project_logs)
        completed_tasks = sum(1 for log in project_logs if log.get('is_completed', False))
        overdue_tasks = sum(1 for log in project_logs if log.get('status') == 'Overdue')
        in_progress_tasks = sum(1 for log in project_logs if log.get('status') == 'In Progress')
        
        with col1:
            st.metric("📋 Total Tasks", total_tasks)
        with col2:
            st.metric("✅ Completed", completed_tasks)
        with col3:
            st.metric("🔴 Overdue", overdue_tasks)
        with col4:
            st.metric("🟡 In Progress", in_progress_tasks)
        
        # Progress bar
        if total_tasks > 0:
            progress = completed_tasks / total_tasks
            st.progress(progress)
            st.write(f"**Progress: {progress:.1%} ({completed_tasks}/{total_tasks} tasks completed)**")
    
    def _render_stage_breakdown(self, project_logs):
        """Render task breakdown by stage"""
        st.subheader("📊 Task Breakdown by Stage")
        stage_data = {}
        
        for log in project_logs:
            stage = log['stage_name']
            if stage not in stage_data:
                stage_data[stage] = {'total': 0, 'completed': 0}
            stage_data[stage]['total'] += 1
            if log.get('is_completed', False):
                stage_data[stage]['completed'] += 1
        
        for stage, data in stage_data.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                if data['total'] > 0:
                    progress = data['completed'] / data['total']
                    st.progress(progress)
            with col2:
                st.write(f"**{stage}:** {data['completed']}/{data['total']}")  
        
    def _render_delete_operations(self):
        """Render delete operations with confirmation"""
        # Show current log count
        current_count = self.log_manager.logs.count_documents({})
        st.info(f"📊 Current logs in database: {current_count}")
        
        # Delete confirmation logic
        if st.button("🗑️ Clear All Logs", type="secondary"):
            st.session_state.confirm_delete = True
        
        if st.session_state.get('confirm_delete', False):
            st.warning("⚠️ **WARNING:** This will permanently delete ALL log entries!")
            
            col_confirm1, col_confirm2 = st.columns(2)
            
            with col_confirm1:
                if st.button("✅ Yes, Delete All", type="primary", key="confirm_delete_yes"):
                    try:
                        # Check database connection
                        self.log_manager.client.admin.command('ping')
                        
                        # Count and delete
                        count_before = self.log_manager.logs.count_documents({})
                        st.info(f"📊 Found {count_before} documents to delete")
                        
                        result = self.log_manager.logs.delete_many({})
                        count_after = self.log_manager.logs.count_documents({})
                        
                        if result.deleted_count > 0:
                            st.success(f"🗑️ Successfully deleted {result.deleted_count} log entries")
                            st.info(f"📊 Remaining logs: {count_after}")
                        elif count_before == 0:
                            st.info("📭 No logs found to delete")
                        else:
                            st.error(f"❌ Deletion may have failed. Documents before: {count_before}, after: {count_after}")
                        
                        st.session_state.confirm_delete = False
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error during deletion: {str(e)}")
            
            with col_confirm2:
                if st.button("❌ Cancel", key="confirm_delete_no"):
                    st.session_state.confirm_delete = False
                    st.rerun()
    
    
    
    def run(self):
        """Main method to run the Streamlit application"""
        self.setup_page_config()
        
        # Check database connection
        if not self.log_manager.client:
            st.error("Cannot proceed without database connection")
            return        
        # Check user role from session state
        user_role = st.session_state.get("role", "user")
        
        if user_role == "admin":
            # Show all tabs for admin users
            tab_dashboard, tab_user_logs, tab_project_overview = st.tabs([
                "Dashboard", "User Logs", "Project Overview", 
            ])
            
            with tab_dashboard:
                self.render_dashboard_tab()
                
            with tab_user_logs:
                self.render_user_logs_tab(is_admin=True)
                
            with tab_project_overview:
                self.render_project_overview_tab()
                
            
        else:
            # Show only User Logs tab for regular users
            st.header("My Tasks")
            self.render_user_logs_tab(is_admin=False)


def run():
    """Entry point for the Streamlit application"""
    app = ProjectLogFrontend()
    app.run()