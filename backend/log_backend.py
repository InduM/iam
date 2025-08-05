import streamlit as st
from pymongo import MongoClient
from datetime import datetime
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
        """Debug database connection and permissions"""
        try:
            self.client.admin.command('ping')
            st.success("✅ Database connection is active")
            db_stats = self.db.command("dbstats")
            st.info(f"📊 Database: user_db, Collections: {db_stats.get('collections', 'Unknown')}")
            collection_count = self.logs.count_documents({})
            st.info(f"📋 Logs collection has {collection_count} documents")
            return True
        except Exception as e:
            st.error(f"❌ Database connection issue: {str(e)}")
            return False

    def extract_and_create_logs(self,project_name = None):
        """Extract assignments from projects and create logs for substages and stage-level tasks"""
        try:
            projects = list(self.projects.find({}))
            logs_created = 0

            for project in projects:
                project_name = project.get('name', 'Unknown Project')
                stage_assignments = project.get('stage_assignments', {})

                # Remove old logs for this project
                self.logs.delete_many({"project_name": project_name})

                for stage_key, stage_data in stage_assignments.items():
                    stage_name = stage_data.get('stage_name', f'Stage {stage_key}')
                    stage_deadline = stage_data.get('deadline', '')
                    substages = stage_data.get('substages', [])
                    members = stage_data.get('members', [])

                    if substages:
                        # ✅ Handle substages
                        for substage in substages:
                            substage_id = substage.get('id')
                            substage_name = substage.get('name', 'Unnamed Substage')
                            assignees = substage.get('assignees', [])
                            substage_deadline = substage.get('deadline', '1970-01-01 00:00:00')
                            start_date = substage.get('start_date', '1970-01-01 00:00:00')
                            is_completed = substage.get('completed', False)
                            priority = substage.get('priority', 'Medium')
                            description = substage.get('description', '')

                            # Completion status from substage_completion
                            substage_completion = project.get('substage_completion', {})
                            stage_completion = substage_completion.get(str(stage_key), {})
                            substage_index = next((i for i, s in enumerate(substages) if s.get('id') == substage_id), None)
                            if substage_index is not None:
                                is_completed = stage_completion.get(str(substage_index), False)

                            # Completion timestamp
                            completed_at = None
                            if is_completed:
                                substage_timestamps = project.get('substage_timestamps', {})
                                stage_timestamps = substage_timestamps.get(str(stage_key), {})
                                if str(substage_index) in stage_timestamps:
                                    try:
                                        completed_at = datetime.strptime(stage_timestamps[str(substage_index)],
                                                                         "%Y-%m-%d %H:%M:%S")
                                    except:
                                        completed_at = None

                            # Create logs for each assignee
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
                    else:
                        # ✅ Handle stages without substages
                        for member in members:
                            start_date = stage_data.get('start_date', '1970-01-01 00:00:00')
                            is_completed = stage_data.get('completed', False)
                            status = calculate_status(start_date, stage_deadline, stage_deadline, is_completed)

                            log_entry = {
                                "project_id": project['_id'],
                                "project_name": project_name,
                                "client": project.get('client', ''),
                                "stage_key": stage_key,
                                "stage_name": stage_name,
                                "substage_id": None,
                                "substage_name": "N/A",
                                "assigned_user": member,
                                "start_date": start_date,
                                "stage_deadline": stage_deadline,
                                "substage_deadline": None,
                                "priority": "Medium",
                                "description": f"Stage task: {stage_name}",
                                "status": status,
                                "is_completed": is_completed,
                                "completed_at": None,
                                "created_at": datetime.now(),
                                "updated_at": datetime.now()
                            }
                            self.logs.insert_one(log_entry)
                            logs_created += 1

            return logs_created
        except Exception as e:
            st.error(f"Error extracting assignments: {str(e)}")
            return 0

    def complete_task(self, log_id: str) -> bool:
        """Mark a task as completed and handle cascading updates for substages and stages."""
        try:
            log_entry = self.logs.find_one({"_id": ObjectId(log_id)})
            if not log_entry:
                return False

            project_id = log_entry["project_id"]
            stage_key = log_entry["stage_key"]
            substage_id = log_entry.get("substage_id")

            if substage_id:
                # ✅ Mark ALL logs for this substage as completed
                self.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key, "substage_id": substage_id},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )

                # Update project structure for this substage
                project = self.projects.find_one({"_id": project_id})
                if project:
                    substages = project.get("stage_assignments", {}).get(stage_key, {}).get("substages", [])
                    substage_index = next((i for i, s in enumerate(substages) if s.get('id') == substage_id), None)
                    if substage_index is not None:
                        completion_path = f"substage_completion.{stage_key}.{substage_index}"
                        timestamp_path = f"substage_timestamps.{stage_key}.{substage_index}"
                        substage_completed_path = f"stage_assignments.{stage_key}.substages.{substage_index}.completed"
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.projects.update_one(
                            {"_id": project_id},
                            {"$set": {
                                completion_path: True,
                                timestamp_path: current_time,
                                substage_completed_path: True,
                                "updated_at": datetime.now().isoformat()
                            }}
                        )

            else:
                # ✅ Stage-level task: mark all logs for this stage as completed
                self.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "completed_at": datetime.now(),
                        "updated_at": datetime.now()
                    }}
                )
                self.projects.update_one(
                    {"_id": project_id},
                    {"$set": {
                        f"stage_assignments.{stage_key}.completed": True,
                        "updated_at": datetime.now().isoformat()
                    }}
                )

            # ✅ After updating, recalculate stage completion
            self.update_stage_completion_status(project_id, stage_key)
            return True
        except Exception as e:
            st.error(f"Error completing task: {str(e)}")
            return False

    def verify_task(self, project_id: ObjectId, stage_key: str, substage_id: str = None) -> bool:
        """Verify logs and update project structure for a substage or entire stage."""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if substage_id:
                # ✅ Verify all logs for the substage
                self.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key, "substage_id": substage_id},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "verified": True,
                        "verified_at": current_time,
                        "updated_at": datetime.now()
                    }}
                )

                # ✅ Update project structure for the substage
                project = self.projects.find_one({"_id": project_id})
                if project:
                    substages = project.get("stage_assignments", {}).get(stage_key, {}).get("substages", [])
                    substage_index = next((i for i, s in enumerate(substages) if s.get('id') == substage_id), None)
                    if substage_index is not None:
                        self.projects.update_one(
                            {"_id": project_id},
                            {"$set": {
                                f"substage_completion.{stage_key}.{substage_index}": True,
                                f"substage_timestamps.{stage_key}.{substage_index}": current_time,
                                f"stage_assignments.{stage_key}.substages.{substage_index}.completed": True,
                                "updated_at": datetime.now().isoformat()
                            }}
                        )
            else:
                # ✅ Stage-level verification: all logs in stage
                self.logs.update_many(
                    {"project_id": project_id, "stage_key": stage_key},
                    {"$set": {
                        "is_completed": True,
                        "status": "Completed",
                        "verified": True,
                        "verified_at": current_time,
                        "updated_at": datetime.now()
                    }}
                )

                # ✅ Update project stage completion
                self.projects.update_one(
                    {"_id": project_id},
                    {"$set": {
                        f"stage_assignments.{stage_key}.completed": True,
                        "updated_at": datetime.now().isoformat()
                    }}
                )

            # ✅ Finally, recalculate stage completion
            self.update_stage_completion_status(project_id, stage_key)
            return True
        except Exception as e:
            st.error(f"Error verifying task: {str(e)}")
            return False

    def remove_project_from_logs(self, project_name):
        """Delete logs for a given project from MongoDB and return count."""
        try:
            result = self.logs.delete_many({"project_name": project_name})
            return result.deleted_count
        except Exception as e:
            st.error(f"Error deleting project logs: {e}")
            return 0

    def update_stage_completion_status(self, project_id: ObjectId, stage_key: str):
        """Check if all logs in a stage are completed, then update project stage status."""
        try:
            logs = list(self.logs.find({"project_id": project_id, "stage_key": stage_key}))
            if logs and all(log.get("is_completed", False) for log in logs):
                self.projects.update_one(
                    {"_id": project_id},
                    {"$set": {f"stage_assignments.{stage_key}.completed": True}}
                )
                return True
            return False
        except Exception as e:
            st.error(f"Error updating stage completion: {str(e)}")
            return False

    def get_all_users(self, project_name: str = None) -> List[str]:
        try:
            users = set()
            if project_name:
                project = self.projects.find_one({"name": project_name})
                if project:
                    projects_to_process = [project]
                else:
                    return []
            else:
                projects_to_process = list(self.projects.find({}))

            for project in projects_to_process:
                stage_assignments = project.get("stage_assignments", {})
                for stage_key, stage_data in stage_assignments.items():
                    members = stage_data.get("members", [])
                    users.update(members)

            return sorted([user for user in users if user and user.strip()])
        except Exception as e:
            st.error(f"Error fetching users: {str(e)}")
            return []

    def get_projects(self) -> List[Dict]:
        try:
            return list(self.projects.find({}))
        except Exception as e:
            st.error(f"Error fetching projects: {str(e)}")
            return []

    def get_project_overview(self) -> Dict:
        try:
            return {
                "total_projects": self.projects.count_documents({}),
                "total_logs": self.logs.count_documents({}),
                "completed_tasks": self.logs.count_documents({"is_completed": True}),
                "overdue_tasks": self.logs.count_documents({"status": "Overdue"}),
                "in_progress_tasks": self.logs.count_documents({"status": "In Progress"})
            }
        except Exception as e:
            st.error(f"Error fetching overview: {str(e)}")
            return {}
