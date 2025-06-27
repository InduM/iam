import streamlit as st
from pymongo import MongoClient
import certifi


class DatabaseManager:
    """Handle all database operations and connections"""
    
    def __init__(self):
        self.uri = st.secrets["MONGO_URI"]
        self.client = MongoClient(self.uri, tlsCAFile=certifi.where())
        self.db = self.client["user_db"]
    
    @st.cache_resource
    def get_mongo_collection(_self):
        return _self.db["users"]

    @st.cache_resource
    def get_logs_collection(_self):
        return _self.db["logs"]
    
    @st.cache_resource
    def get_documents_collection(_self):
        return _self.db["documents"]
    
    @st.cache_resource
    def get_projects_collection(_self):
        return _self.db["projects"]


class UserService:
    """Handle user-related operations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.collection = db_manager.get_mongo_collection()
    
    def load_team_data(self):
        """Load and normalize team data"""
        data = list(self.collection.find({}, {"_id": 0}))
        for d in data:
            proj = d.get("project")
            if isinstance(proj, list):
                continue
            elif isinstance(proj, str):
                d["project"] = [proj]
            else:
                d["project"] = []
        return data
    
    def fetch_user_data(self, email):
        """Fetch the latest user data from MongoDB by email"""
        user_data = self.collection.find_one({"email": email}, {"_id": 0})
        if user_data:
            # Normalize project field
            proj = user_data.get("project")
            if isinstance(proj, list):
                pass  # Already a list
            elif isinstance(proj, str):
                user_data["project"] = [proj]
            else:
                user_data["project"] = []
        return user_data
    
    def update_member(self, original_email, updated_data):
        """Update team member details"""
        # Get the current member data to compare projects
        current_member = self.collection.find_one({"email": original_email})
        current_projects = current_member.get("project", []) if current_member else []
        new_projects = updated_data.get("project", [])
        
        # Find removed projects
        removed_projects = [proj for proj in current_projects if proj not in new_projects]
        
        # Update the user document
        self.collection.update_one(
            {"email": original_email},
            {"$set": updated_data}
        )
        
        # Remove user from projects table for removed projects
        if removed_projects:
            projects_collection = self.db_manager.get_projects_collection()
            username = original_email.split("@")[0]  # Extract username from email
            
            for project_name in removed_projects:
                # Remove the user from the project's user list
                projects_collection.update_one(
                    {"project_name": project_name},
                    {"$pull": {"users": username}}
                )
    
    def get_all_projects(self):
        """Get all unique projects from team data"""
        team_data = self.load_team_data()
        return sorted({
            p for m in team_data
            if isinstance(m.get("project"), list)
            for p in m.get("project", [])
        })


class LogService:
    """Handle log-related operations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logs_collection = db_manager.get_logs_collection()
    
    def fetch_user_logs(self, username, date_str):
        """Fetch the latest logs for a user on a specific date"""
        logs = list(self.logs_collection.find(
            {"Date": date_str, "Username": username},
            {"_id": 0, "Date": 0, "Username": 0}
        ))
        return logs


class ProjectService:
    """Handle project-related operations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.projects_collection = db_manager.get_projects_collection()
    
    def add_user_to_projects(self, username, project_names):
        """Add user to multiple projects"""
        for project_name in project_names:
            self.projects_collection.update_one(
                {"project_name": project_name},
                {"$addToSet": {"users": username}},  # $addToSet prevents duplicates
                upsert=True  # Create project document if it doesn't exist
            )


class ProfileService:
    """Handle profile image operations"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.documents_collection = db_manager.get_documents_collection()
    
    def get_profile_image(self, username):
        """Get profile image data for a user"""
        user_doc = self.documents_collection.find_one({"username": username})
        if user_doc:
            return user_doc.get("profile_image", {}).get("data", None)
        return None
    
    def get_default_profile_image(self):
        """Get default profile image (admin's profile image)"""
        user_doc = self.documents_collection.find_one({"username": "admin"})
        if user_doc:
            return user_doc.get("profile_image", {}).get("data", None)
        return None