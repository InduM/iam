import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_modal import Modal
from bson import ObjectId
from utils.utils_log import format_status_badge, format_priority_badge


class VerificationComponents:
    def __init__(self, log_manager):
        self.log_manager = log_manager

    def render_verification_tab(self):
        """Enhanced verification tab with batch processing"""
        st.subheader("✅ Pending Verification")
        
        try:
            pending_logs = list(self.log_manager.logs.find({"status": "Pending Verification"}))
        except Exception as e:
            st.error(f"❌ Error fetching pending logs: {str(e)}")
            return
            
        if len(pending_logs) == 0:
            st.success("No tasks pending verification.")
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
                if st.button("✅ Verify All", key="batch_verify_all", type="primary"):
                    if st.checkbox("⚠️ Confirm batch verification", key="batch_verify_confirm"):
                        verified_count = self._batch_verify_tasks(pending_logs)
                        st.success(f"✅ Verified {verified_count} tasks!")
                        st.rerun()
            with col2:
                selected_user = st.selectbox("Verify by User", key="batch_verify_user_select",
                                        options=["Select User"] + list(set(log['assigned_user'] for log in pending_logs)))
                if selected_user != "Select User":
                    user_tasks = [log for log in pending_logs if log['assigned_user'] == selected_user]
                    if st.button(f"✅ Verify {selected_user}'s Tasks ({len(user_tasks)})", key=f"batch_verify_user_{selected_user}"):
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
                    if st.button("✅", key=f"verify_individual_{log['_id']}", help="Verify this task"):
                        try:
                            self._verify_task_completion_with_timestamp(log)
                            st.success(f"✅ Verified: {log['substage_name']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Verification failed: {str(e)}")
                
                if i < len(pending_logs) - 1:
                    st.divider()

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

    def _verify_task_completion_with_timestamp(self, log):
        """Verify all logs of the same substage or stage, then update stage completion."""
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

            # Recalculate and update stage completion
            self.log_manager.update_stage_completion_status(project_id, stage_key)
        except Exception as e:
            st.error(f"❌ Failed to verify task completion: {str(e)}")
            raise

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


class TaskModalComponents:
    def __init__(self, log_manager):
        self.log_manager = log_manager

    def show_task_modal(self, log):
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
                                ["High", "Medium", "Low", "Critical"], 
                                index=["High", "Medium", "Low", "Critical"].index(current_priority),
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

    def _verify_task_completion_with_timestamp(self, log):
        """Verify all logs of the same substage or stage, then update stage completion."""
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