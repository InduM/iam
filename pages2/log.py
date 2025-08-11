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

    def render_toolbar(self, logs, context="default"):
        """Enhanced toolbar with additional functionality"""
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            if st.button("🔄 Refresh", key=f"toolbar_refresh_btn_{context}", help="Refresh the current view"):
                st.rerun()

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

    def run(self):
        """Main application runner with enhanced error handling"""
        if not self.log_manager.client:
            st.error("❌ Cannot proceed without database connection")
            with st.expander("🔧 Database Connection Debug"):
                if st.button("🔍 Test Connection", key="main_debug_test_connection"):
                    self.log_manager.debug_database_connection()
            return

        try:
            user_role = st.session_state.get("role", "user")
            
            if user_role in ["admin", "manager"]:
                # Admin/Manager interface
                try:
                    pending_count = self.log_manager.logs.count_documents({"status": "Pending Verification"})
                    verification_tab_label = f"✅ Verification ({pending_count})" if pending_count > 0 else "✅ Verification"
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch pending count: {str(e)}")
                    verification_tab_label = "✅ Verification"

                # Import here to avoid circular imports
                from pages2.dashboard_components import DashboardComponents
                from pages2.verification_components import VerificationComponents, TaskModalComponents
                from pages2.task_management_components import TaskManagementComponents
                
                dashboard = DashboardComponents(self.log_manager)
                verification = VerificationComponents(self.log_manager)
                task_mgmt = TaskManagementComponents(self.log_manager)

                tab_dashboard, tab_user_logs, tab_verification, tab_logs = st.tabs([
                    "📊 Dashboard", "👤 Task Management", verification_tab_label, "Logs"
                ])
                
                with tab_dashboard:
                    try:
                        dashboard.render_dashboard_tab()
                    except Exception as e:
                        st.error(f"❌ Dashboard error: {str(e)}")
                        st.exception(e)
                
                with tab_user_logs:
                    try:
                        task_mgmt.render_user_logs_tab(is_admin=True)
                    except Exception as e:
                        st.error(f"❌ Task management error: {str(e)}")
                        st.exception(e)
                
                with tab_verification:
                    try:
                        verification.render_verification_tab()
                    except Exception as e:
                        st.error(f"❌ Verification error: {str(e)}")
                        st.exception(e)
                
                with tab_logs:
                    try:
                        # Use different context for logs tab to avoid conflicts
                        task_mgmt.render_user_logs_tab(is_admin=False)
                    except Exception as e:
                        st.error(f"❌ User interface error: {str(e)}")
                        st.exception(e)
            else:
                # Regular user interface
                try:
                    from task_management_components import TaskManagementComponents
                    task_mgmt = TaskManagementComponents(self.log_manager)
                    task_mgmt.render_user_logs_tab(is_admin=False)
                except Exception as e:
                    st.error(f"❌ User interface error: {str(e)}")
                    st.exception(e)
        
        except Exception as e:
            st.error(f"❌ Application error: {str(e)}")
            st.exception(e)


def run():
    try:
        app = ProjectLogFrontend()
        app.run()
    except Exception as e:
        st.error(f"❌ Failed to start application: {str(e)}")
        st.exception(e)