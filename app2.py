import streamlit as st
import pymongo
from datetime import datetime, date
import pandas as pd
from typing import Dict, List, Optional
import os
from bson import ObjectId

# MongoDB Configuration
MONGODB_URI =  st.secrets["MONGO_URI"]
DATABASE_NAME = "user_db"
PROJECTS_COLLECTION = "projects"
LOGS_COLLECTION = "logs"
USERS_COLLECTION = "users"

class ProjectLogManager:
    def __init__(self):
        """Initialize MongoDB connection"""
        try:
            self.client = pymongo.MongoClient(MONGODB_URI)
            self.db = self.client[DATABASE_NAME]
            self.projects = self.db[PROJECTS_COLLECTION]
            self.logs = self.db[LOGS_COLLECTION]
            self.users = self.db[USERS_COLLECTION]
            # Test connection
            self.client.admin.command('ping')
            st.success("✅ Connected to MongoDB Atlas")
        except Exception as e:
            st.error(f"❌ Failed to connect to MongoDB: {str(e)}")
            self.client = None

    def debug_database_connection(self):
        """Debug method to check database connection and permissions"""
        try:
            # Test basic connection
            self.client.admin.command('ping')
            st.success("✅ Database connection is active")
            
            # Test database access
            db_stats = self.db.command("dbstats")
            st.info(f"📊 Database: {DATABASE_NAME}, Collections: {db_stats.get('collections', 'Unknown')}")
            
            # Test collection access
            collection_count = self.logs.count_documents({})
            st.info(f"📋 Logs collection has {collection_count} documents")
            
            # Test write permissions with a dummy operation
            dummy_result = self.logs.find_one_and_update(
                {"_test_dummy": "test"},
                {"$set": {"_test_dummy": "test", "timestamp": datetime.now()}},
                upsert=True,
                return_document=True
            )
            
            if dummy_result:
                # Clean up the test document
                self.logs.delete_one({"_id": dummy_result["_id"]})
                st.success("✅ Write permissions confirmed")
            else:
                st.warning("⚠️ Write permission test failed")
                
            return True
            
        except Exception as e:
            st.error(f"❌ Database connection issue: {str(e)}")
            return False

    
    def calculate_status(self, start_date_str: str, stage_deadline_str: str, 
                        substage_deadline_str: str, is_completed: bool = False) -> str:
        """Calculate project status based on dates and completion"""
        if is_completed:
            return "Completed"
        
        try:
            # Parse dates - handle both string formats from your DB
            if isinstance(start_date_str, str):
                if len(start_date_str) == 10:  # Format: 2025-05-05
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                else:  # Format: 2025-07-01 14:28:43
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S").date()
            else:
                start_date = start_date_str
            
            # Parse stage deadline
            if stage_deadline_str and stage_deadline_str.strip():
                if len(stage_deadline_str) == 10:
                    stage_deadline = datetime.strptime(stage_deadline_str, "%Y-%m-%d").date()
                else:
                    stage_deadline = datetime.strptime(stage_deadline_str, "%Y-%m-%d %H:%M:%S").date()
            else:
                stage_deadline = None
            
            # Parse substage deadline
            substage_deadline = None
            if substage_deadline_str and substage_deadline_str.strip():
                if len(substage_deadline_str) == 10:
                    substage_deadline = datetime.strptime(substage_deadline_str, "%Y-%m-%d").date()
                else:
                    substage_deadline = datetime.strptime(substage_deadline_str, "%Y-%m-%d %H:%M:%S").date()
            
            current_date = date.today()
            
            # Use the earlier deadline (stage or substage) if both exist
            if stage_deadline and substage_deadline:
                effective_deadline = min(stage_deadline, substage_deadline)
            elif substage_deadline:
                effective_deadline = substage_deadline
            elif stage_deadline:
                effective_deadline = stage_deadline
            else:
                return "No Deadline Set"
            
            if current_date > effective_deadline:
                return "Overdue"
            elif start_date <= current_date <= effective_deadline:
                return "In Progress"
            elif start_date > current_date:
                return "Upcoming"
            else:
                return "Unknown"
                
        except Exception as e:
            st.error(f"Date parsing error: {str(e)}")
            return "Error"
    
    def extract_and_create_logs(self):
        """Extract assignments from project structure and create logs"""
        try:
            projects = list(self.projects.find({}))
            logs_created = 0
            
            for project in projects:
                project_name = project.get('name', 'Unknown Project')
                stage_assignments = project.get('stage_assignments', {})
                
                # Clear existing logs for this project to avoid duplicates
                self.logs.delete_many({"project_name": project_name})
                
                for stage_key, stage_data in stage_assignments.items():
                    stage_name = stage_data.get('stage_name', f'Stage {stage_key}')
                    stage_deadline = stage_data.get('deadline', '')
                    substages = stage_data.get('substages', [])
                    
                    for substage in substages:
                        substage_id = substage.get('id')
                        substage_name = substage.get('name', 'Unnamed Substage')
                        assignees = substage.get('assignees', [])
                        substage_deadline = substage.get('deadline', '')
                        start_date = substage.get('start_date', '')
                        is_completed = substage.get('completed', False)
                        priority = substage.get('priority', 'Medium')
                        description = substage.get('description', '')
                        
                        # Check if completed in substage_completion
                        substage_completion = project.get('substage_completion', {})
                        stage_completion = substage_completion.get(str(stage_key), {})
                        substage_index = next((i for i, s in enumerate(substages) if s.get('id') == substage_id), None)
                        if substage_index is not None:
                            is_completed = stage_completion.get(str(substage_index), False)
                        
                        # Get completion timestamp if available
                        completed_at = None
                        if is_completed:
                            substage_timestamps = project.get('substage_timestamps', {})
                            stage_timestamps = substage_timestamps.get(str(stage_key), {})
                            if str(substage_index) in stage_timestamps:
                                timestamp_str = stage_timestamps[str(substage_index)]
                                try:
                                    completed_at = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                except:
                                    completed_at = None
                        
                        # Create log entry for each assignee
                        for assignee in assignees:
                            status = self.calculate_status(start_date, stage_deadline, substage_deadline, is_completed)
                            
                            log_entry = {
                                "project_id": project['_id'],
                                "project_name": project_name,
                                "client": project.get('client', ''),
                                "stage_key": stage_key,
                                "stage_name": stage_name,
                                "substage_id": substage_id,
                                "substage_name": substage_name,
                                "assigned_user": assignee,
                                "start_date": start_date,
                                "stage_deadline": stage_deadline,
                                "substage_deadline": substage_deadline,
                                "priority": priority,
                                "description": description,
                                "status": status,
                                "is_completed": is_completed,
                                "completed_at": completed_at,
                                "created_at": datetime.now(),
                                "updated_at": datetime.now()
                            }
                            
                            self.logs.insert_one(log_entry)
                            logs_created += 1
            
            return logs_created
            
        except Exception as e:
            st.error(f"Error extracting assignments: {str(e)}")
            return 0
    
    def get_user_logs(self, user_name: str) -> List[Dict]:
        """Get all logs for a specific user"""
        try:
            logs = list(self.logs.find({"assigned_user": user_name}).sort("created_at", -1))
            
            # Update statuses based on current date
            for log in logs:
                if not log.get("is_completed", False):
                    current_status = self.calculate_status(
                        log["start_date"],
                        log["stage_deadline"],
                        log.get("substage_deadline", ""),
                        log.get("is_completed", False)
                    )
                    if current_status != log["status"]:
                        self.logs.update_one(
                            {"_id": log["_id"]},
                            {"$set": {"status": current_status, "updated_at": datetime.now()}}
                        )
                        log["status"] = current_status
            
            return logs
        except Exception as e:
            st.error(f"Error fetching user logs: {str(e)}")
            return []
    
    def complete_task(self, log_id: str) -> bool:
        """Mark a task as completed and update project structure"""
        try:
            # Get the log entry
            log_entry = self.logs.find_one({"_id": ObjectId(log_id)})
            if not log_entry:
                return False
            
            # Update log entry
            result = self.logs.update_one(
                {"_id": ObjectId(log_id)},
                {
                    "$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                # Update project structure
                project_id = log_entry["project_id"]
                stage_key = log_entry["stage_key"]
                substage_id = log_entry["substage_id"]
                
                # Find the substage index
                project = self.projects.find_one({"_id": project_id})
                if project:
                    substages = project.get("stage_assignments", {}).get(stage_key, {}).get("substages", [])
                    substage_index = next((i for i, s in enumerate(substages) if s.get('id') == substage_id), None)
                    
                    if substage_index is not None:
                        # Update substage completion
                        completion_path = f"substage_completion.{stage_key}.{substage_index}"
                        timestamp_path = f"substage_timestamps.{stage_key}.{substage_index}"
                        substage_completed_path = f"stage_assignments.{stage_key}.substages.{substage_index}.completed"
                        
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        update_result = self.projects.update_one(
                            {"_id": project_id},
                            {
                                "$set": {
                                    completion_path: True,
                                    timestamp_path: current_time,
                                    substage_completed_path: True,
                                    "updated_at": datetime.now().isoformat()
                                }
                            }
                        )
                        
                        return update_result.modified_count > 0
                
                return True
            return False
        except Exception as e:
            st.error(f"Error completing task: {str(e)}")
            return False
    
    def get_all_users(self, project_name: str = None) -> List[str]:
        """Get all unique assignees from project assignments
        If project_name is provided, get users only from that project
        If project_name is None, get all users from all projects
        """
        try:
            if project_name:
                # Get unique assignees from specific project
                pipeline = [
                    {"$match": {"name": project_name}},
                    {"$unwind": "$stage_assignments"},
                    {"$unwind": "$stage_assignments.substages"},
                    {"$unwind": "$stage_assignments.substages.assignees"},
                    {"$group": {"_id": "$stage_assignments.substages.assignees"}},
                    {"$sort": {"_id": 1}}
                ]
            else:
                # Get unique assignees from all projects (original behavior)
                pipeline = [
                    {"$unwind": "$stage_assignments"},
                    {"$unwind": "$stage_assignments.substages"},
                    {"$unwind": "$stage_assignments.substages.assignees"},
                    {"$group": {"_id": "$stage_assignments.substages.assignees"}},
                    {"$sort": {"_id": 1}}
                ]
            
            result = list(self.projects.aggregate(pipeline))
            users = [user["_id"] for user in result if user["_id"]]
            
            # Debug logging
            if not project_name:
                st.write(f"Debug: Found {len(users)} users across all projects: {users}")
            
            return users
        except Exception as e:
            st.error(f"Error fetching users: {str(e)}")
            return []
    def get_project_users(self, project_name: str) -> List[str]:
        """Get all unique assignees for a specific project"""
        try:
            # Get the specific project
            project = self.projects.find_one({"name": project_name})
            if not project:
                return []
            
            users = set()
            stage_assignments = project.get('stage_assignments', {})
            
            for stage_key, stage_data in stage_assignments.items():
                substages = stage_data.get('substages', [])
                for substage in substages:
                    assignees = substage.get('assignees', [])
                    users.update(assignees)
            
            return sorted(list(users))
        except Exception as e:
            st.error(f"Error fetching project users: {str(e)}")
            return []

    def get_user_logs_by_project(self, user_name: str, project_name: str = None) -> List[Dict]:
        """Get all logs for a specific user, optionally filtered by project"""
        try:
            query = {"assigned_user": user_name}
            if project_name:
                query["project_name"] = project_name
                
            logs = list(self.logs.find(query).sort("created_at", -1))
            
            # Update statuses based on current date
            for log in logs:
                if not log.get("is_completed", False):
                    current_status = self.calculate_status(
                        log["start_date"],
                        log["stage_deadline"],
                        log.get("substage_deadline", ""),
                        log.get("is_completed", False)
                    )
                    if current_status != log["status"]:
                        self.logs.update_one(
                            {"_id": log["_id"]},
                            {"$set": {"status": current_status, "updated_at": datetime.now()}}
                        )
                        log["status"] = current_status
            
            return logs
        except Exception as e:
            st.error(f"Error fetching user logs: {str(e)}")
            return []
    def get_projects(self) -> List[Dict]:
        """Get all projects from the database"""
        try:
            return list(self.projects.find({}, {"_id": 1, "name": 1, "client": 1}))
        except Exception as e:
            st.error(f"Error fetching projects: {str(e)}")
            return []
    
    def get_project_overview(self) -> Dict:
        """Get overview statistics for all projects"""
        try:
            total_projects = self.projects.count_documents({})
            total_logs = self.logs.count_documents({})
            completed_tasks = self.logs.count_documents({"is_completed": True})
            overdue_tasks = self.logs.count_documents({"status": "Overdue"})
            in_progress_tasks = self.logs.count_documents({"status": "In Progress"})
            
            return {
                "total_projects": total_projects,
                "total_logs": total_logs,
                "completed_tasks": completed_tasks,
                "overdue_tasks": overdue_tasks,
                "in_progress_tasks": in_progress_tasks
            }
        except Exception as e:
            st.error(f"Error fetching overview: {str(e)}")
            return {}

def format_status_badge(status: str) -> str:
    """Format status with colored badges"""
    colors = {
        "Completed": "🟢",
        "In Progress": "🟡",
        "Overdue": "🔴",
        "Upcoming": "🔵",
        "No Deadline Set": "⚪",
        "Error": "❌"
    }
    return f"{colors.get(status, '⚪')} {status}"

def format_priority_badge(priority: str) -> str:
    """Format priority with colored badges"""
    colors = {
        "High": "🔥",
        "Medium": "🟡",
        "Low": "🟢"
    }
    return f"{colors.get(priority, '⚪')} {priority}"

def main():
    st.set_page_config(
        page_title="V-Shesh Project Log System",
        page_icon="📋",
        layout="wide"
    )
    
    st.title("📋 V-Shesh Project Log Management System")
    st.markdown("---")
    
    # Initialize the log manager
    log_manager = ProjectLogManager()
    
    if not log_manager.client:
        st.error("Cannot proceed without database connection")
        return
    tabA, tabB ,tabC,tabD = st.tabs(["Dashboard", "User Logs", "Project Overview", "Admin Panel"])
    
    with tabA:
        st.header("📊 Dashboard Overview")
        
        # Refresh logs button
        if st.button("🔄 Refresh Logs from Projects", type="primary"):
            with st.spinner("Extracting assignments from projects..."):
                logs_created = log_manager.extract_and_create_logs()
                st.success(f"✅ Created {logs_created} log entries from project assignments")
        
        # Overview metrics
        overview = log_manager.get_project_overview()
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
        st.subheader("📈 Recent Activity")
        recent_logs = list(log_manager.logs.find({}).sort("updated_at", -1).limit(10))
        
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
                        st.write(f"**Updated:** {log.get('updated_at', log.get('created_at')).strftime('%Y-%m-%d %H:%M') if log.get('updated_at') else 'N/A'}")
    
    # Replace the existing tabB section with this updated version:

    # Replace the existing tabB section with this updated version:

    with tabB:
        st.header("👤 User Logs")
        
        # Project selection first
        projects = log_manager.get_projects()
        project_options = ["All Projects"] + [p['name'] for p in projects]
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_project = st.selectbox(
                "Select Project", 
                project_options,
                format_func=lambda x: x if x == "All Projects" else f"{x} ({next((p['client'] for p in projects if p['name'] == x), 'N/A')})"
            )
        
        # Get users based on project selection
        if selected_project == "All Projects":
            users = log_manager.get_all_users()  # Call without project_name parameter
            project_filter = None
        else:
            users = log_manager.get_project_users(selected_project)
            project_filter = selected_project
        
        with col2:
            if users:
                selected_user = st.selectbox("Select User", users)
            else:
                st.warning(f"⚠️ No users found for {selected_project}")
                selected_user = None
        
        if selected_user:
            # Get logs for selected user and project
            if project_filter:
                user_logs = log_manager.get_user_logs_by_project(selected_user, project_filter)
                st.subheader(f"📋 Tasks for {selected_user} in {selected_project}")
            else:
                user_logs = log_manager.get_user_logs(selected_user)
                st.subheader(f"📋 All Tasks for {selected_user}")
            
            if user_logs:
                # Additional filters (only show if there are logs)
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    all_statuses = list(set([log["status"] for log in user_logs]))
                    status_filter = st.multiselect("Filter by Status", all_statuses, default=all_statuses)
                
                with col2:
                    all_priorities = list(set([log.get("priority", "Medium") for log in user_logs]))
                    priority_filter = st.multiselect("Filter by Priority", all_priorities, default=all_priorities)
                
                with col3:
                    if project_filter is None:  # Only show project filter if "All Projects" is selected
                        all_user_projects = list(set([log["project_name"] for log in user_logs]))
                        user_project_filter = st.multiselect("Filter by Project", all_user_projects, default=all_user_projects)
                    else:
                        user_project_filter = [project_filter]
                
                # Filter logs
                filtered_logs = [
                    log for log in user_logs 
                    if log["status"] in status_filter 
                    and log.get("priority", "Medium") in priority_filter
                    and log["project_name"] in user_project_filter
                ]
                
                # Display logs
                for i, log in enumerate(filtered_logs):
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
                                st.write(f"**Description:** {log['description'][:100]}{'...' if len(log['description']) > 100 else ''}")
                        
                        with col3:
                            if not log.get('is_completed', False):
                                if st.button(f"✅ Mark Complete", key=f"complete_{log['_id']}"):
                                    if log_manager.complete_task(str(log['_id'])):
                                        st.success("✅ Task completed successfully!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to complete task")
                            else:
                                st.success("✅ Completed")
                                if log.get('completed_at'):
                                    st.write(f"**Completed:** {log['completed_at'].strftime('%Y-%m-%d %H:%M')}")
                
                st.info(f"📊 Showing {len(filtered_logs)} of {len(user_logs)} tasks")
            else:
                if project_filter:
                    st.info(f"📭 No logs found for {selected_user} in {selected_project}")
                else:
                    st.info(f"📭 No logs found for {selected_user}")
        else:
            if selected_project != "All Projects":
                st.info(f"ℹ️ No users assigned to tasks in {selected_project}")
            else:
                st.info("ℹ️ Please select a user to view their tasks")
    with tabC:
        st.header("🏗️ Project Overview")
        
        projects = log_manager.get_projects()
        
        if projects:
            selected_project = st.selectbox(
                "Select Project", 
                options=[p['name'] for p in projects],
                format_func=lambda x: f"{x} ({next(p['client'] for p in projects if p['name'] == x)})"
            )
            
            # Get logs for selected project
            project_logs = list(log_manager.logs.find({"project_name": selected_project}))
            
            if project_logs:
                # Project statistics
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
                
                # Task breakdown by stage
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
                
            else:
                st.info(f"📭 No tasks found for {selected_project}")
        else:
            st.warning("⚠️ No projects found")
    
    with tabD:
        st.header("🔧 Admin Panel")
        
        tab1, tab2, tab3 = st.tabs(["Database Operations", "Statistics", "Data Export"])
        
        with tab1:
            st.subheader("🔄 Database Operations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Extract All Assignments", type="primary"):
                    with st.spinner("Extracting assignments from all projects..."):
                        logs_created = log_manager.extract_and_create_logs()
                        st.success(f"✅ Created {logs_created} log entries")
                
                if st.button("🔄 Update All Statuses"):
                    with st.spinner("Updating all task statuses..."):
                        logs = list(log_manager.logs.find({"is_completed": False}))
                        updated_count = 0
                        
                        for log in logs:
                            current_status = log_manager.calculate_status(
                                log["start_date"],
                                log["stage_deadline"],
                                log.get("substage_deadline", ""),
                                log.get("is_completed", False)
                            )
                            if current_status != log["status"]:
                                log_manager.logs.update_one(
                                    {"_id": log["_id"]},
                                    {"$set": {"status": current_status, "updated_at": datetime.now()}}
                                )
                                updated_count += 1
                        
                        st.success(f"✅ Updated {updated_count} task statuses")
            
            with col2:
                # Show current log count before deletion
                current_count = log_manager.logs.count_documents({})
                st.info(f"📊 Current logs in database: {current_count}")
                
                # First button to initiate deletion
                if st.button("🗑️ Clear All Logs", type="secondary"):
                    st.session_state.confirm_delete = True
                
                # Confirmation button (only appears after first button is clicked)
                if st.session_state.get('confirm_delete', False):
                    st.warning("⚠️ **WARNING:** This will permanently delete ALL log entries!")
                    
                    col_confirm1, col_confirm2 = st.columns(2)
                    
                    with col_confirm1:
                        if st.button("✅ Yes, Delete All", type="primary", key="confirm_delete_yes"):
                            try:
                                # Check database connection first
                                log_manager.client.admin.command('ping')
                                
                                # Count documents before deletion
                                count_before = log_manager.logs.count_documents({})
                                st.info(f"📊 Found {count_before} documents to delete")
                                
                                # Perform deletion with error handling
                                result = log_manager.logs.delete_many({})
                                
                                # Verify deletion
                                count_after = log_manager.logs.count_documents({})
                                
                                if result.deleted_count > 0:
                                    st.success(f"🗑️ Successfully deleted {result.deleted_count} log entries")
                                    st.info(f"📊 Remaining logs: {count_after}")
                                elif count_before == 0:
                                    st.info("📭 No logs found to delete")
                                else:
                                    st.error(f"❌ Deletion may have failed. Documents before: {count_before}, after: {count_after}")
                                
                                # Clear the confirmation state
                                st.session_state.confirm_delete = False
                                st.rerun()
                                
                            except pymongo.errors.PyMongoError as e:
                                st.error(f"❌ Database error during deletion: {str(e)}")
                            except Exception as e:
                                st.error(f"❌ Unexpected error during deletion: {str(e)}")
                    
                    with col_confirm2:
                        if st.button("❌ Cancel", key="confirm_delete_no"):
                            st.session_state.confirm_delete = False
                            st.rerun()
        
        with tab2:
            st.subheader("📊 Detailed Statistics")
            
            # Status distribution
            try:
                status_pipeline = [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}
                ]
                status_data = list(log_manager.logs.aggregate(status_pipeline))
                
                if status_data:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Status Distribution:**")
                        df_status = pd.DataFrame(status_data)
                        df_status.columns = ['Status', 'Count']
                        st.bar_chart(df_status.set_index('Status'))
                    
                    with col2:
                        st.write("**Priority Distribution:**")
                        priority_pipeline = [
                            {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
                            {"$sort": {"count": -1}}
                        ]
                        priority_data = list(log_manager.logs.aggregate(priority_pipeline))
                        if priority_data:
                            df_priority = pd.DataFrame(priority_data)
                            df_priority.columns = ['Priority', 'Count']
                            st.bar_chart(df_priority.set_index('Priority'))
                else:
                    st.info("📭 No data available for statistics")
            except Exception as e:
                st.error(f"❌ Error generating statistics: {str(e)}")
        
        with tab3:
            st.subheader("📤 Data Export")
            
            if st.button("📊 Export All Logs to CSV"):
                try:
                    logs = list(log_manager.logs.find({}))
                    if logs:
                        # Convert to DataFrame
                        df = pd.DataFrame(logs)
                        # Remove MongoDB ObjectId columns
                        if '_id' in df.columns:
                            df['_id'] = df['_id'].astype(str)
                        if 'project_id' in df.columns:
                            df['project_id'] = df['project_id'].astype(str)
                        
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="💾 Download CSV",
                            data=csv,
                            file_name=f"project_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        st.success(f"📊 Ready to download {len(logs)} log entries")
                    else:
                        st.info("📭 No logs available to export")
                except Exception as e:
                    st.error(f"❌ Error exporting data: {str(e)}")
                    
if __name__ == "__main__":
    main()