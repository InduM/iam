import streamlit as st
from pymongo import MongoClient
import certifi    
from datetime import datetime, date
from typing import Dict, List
from bson import ObjectId
from utils.utils_log import calculate_status

class ProjectLogManager:
    def __init__(self):
        """Initialize MongoDB connection"""
        try:
            self.client = MongoClient(st.secrets["MONGO_URI"])
            self.db = self.client["user_db"]
            self.projects = self.db["projects"]
            self.logs = self.db["logs"]
            self.users = self.db["users"]
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
            st.info(f"📊 Database: user_db, Collections: {db_stats.get('collections', 'Unknown')}")
            
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
                            status = calculate_status(start_date, stage_deadline, substage_deadline, is_completed)
                            
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
                  
                    current_status = calculate_status(
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
                    from utilss import calculate_status
                    current_status = calculate_status(
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
        """Get all unique assignees from project assignments"""
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
                # Get unique assignees from all projects
                pipeline = [
                    {"$unwind": "$stage_assignments"},
                    {"$unwind": "$stage_assignments.substages"},
                    {"$unwind": "$stage_assignments.substages.assignees"},
                    {"$group": {"_id": "$stage_assignments.substages.assignees"}},
                    {"$sort": {"_id": 1}}
                ]
            
            result = list(self.projects.aggregate(pipeline))
            users = [user["_id"] for user in result if user["_id"]]
            
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

    def clear_all_logs(self) -> int:
        """Clear all logs from the database"""
        try:
            result = self.logs.delete_many({})
            return result.deleted_count
        except Exception as e:
            st.error(f"Error clearing logs: {str(e)}")
            return 0

    def update_all_statuses(self) -> int:
        """Update all task statuses based on current date"""
        try:
            logs = list(self.logs.find({"is_completed": False}))
            updated_count = 0
            
            for log in logs:
                from utilss import calculate_status
                current_status = calculate_status(
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
                    updated_count += 1
            
            return updated_count
        except Exception as e:
            st.error(f"Error updating statuses: {str(e)}")
            return 0

    def get_status_distribution(self) -> List[Dict]:
        """Get status distribution statistics"""
        try:
            pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            return list(self.logs.aggregate(pipeline))
        except Exception as e:
            st.error(f"Error getting status distribution: {str(e)}")
            return []

    def get_priority_distribution(self) -> List[Dict]:
        """Get priority distribution statistics"""
        try:
            pipeline = [
                {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            return list(self.logs.aggregate(pipeline))
        except Exception as e:
            st.error(f"Error getting priority distribution: {str(e)}")
            return []

    def export_logs_data(self) -> List[Dict]:
        """Export all logs data"""
        try:
            logs = list(self.logs.find({}))
            # Convert ObjectId to string for CSV export
            for log in logs:
                if '_id' in log:
                    log['_id'] = str(log['_id'])
                if 'project_id' in log:
                    log['project_id'] = str(log['project_id'])
            return logs
        except Exception as e:
            st.error(f"Error exporting logs: {str(e)}")
            return []
    
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
    