import streamlit as st
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId

# ───── MongoDB Connection ─────
@st.cache_resource
def init_connection():
    """Initialize MongoDB connection"""
    return MongoClient(st.secrets["MONGO_URI"])

def get_db_collections():
    """Get database collections"""
    client = init_connection()
    db = client["user_db"]
    return {
        "projects": db["projects"],
        "clients": db["clients"],
        "users": db["users"]
    }

# ───── Project Database Operations ─────
from pymongo import MongoClient

def get_project_by_name(project_name):
    
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        project = projects_collection.find_one({"name": project_name})
        return project
    except Exception as e:
        st.error(f"Error fetching project by name: {e}")
        return None

def load_projects_from_db():
    """Load projects from database based on user role"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        
        role = st.session_state.get("role", "")
        username = st.session_state.get("username", "")
        
        if role == "manager":
            query = {"created_by": username}
        else:
            query = {}  # Admins or others can see all
        
        projects = list(projects_collection.find(query))
        for project in projects:
            project["id"] = str(project["_id"])  # Convert ObjectId for Streamlit
            # Ensure all projects have required fields with defaults
            if "levels" not in project:
                project["levels"] = ["Initial", "Invoice", "Payment"]
            if "level" not in project:
                project["level"] = -1
            if "timestamps" not in project:
                project["timestamps"] = {}
            if "team" not in project:
                project["team"] = []
        return projects
    except Exception as e:
        st.error(f"Error loading projects: {e}")
        return []

def save_project_to_db(project_data):
    """Save a new project to MongoDB"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        
        # Remove the 'id' field if it exists (MongoDB will generate _id)
        if "id" in project_data:
            del project_data["id"]
        
        result = projects_collection.insert_one(project_data)
        return str(result.inserted_id)
    except Exception as e:
        st.error(f"Error saving project: {e}")
        return None

def update_project_in_db(project_id, project_data):
    """Update an existing project in MongoDB"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        
        # Convert string ID back to ObjectId for MongoDB query
        object_id = ObjectId(project_id)
        
        # Remove the 'id' field from update data
        update_data = project_data.copy()
        if "id" in update_data:
            del update_data["id"]
        
        result = projects_collection.update_one(
            {"_id": object_id}, 
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Error updating project: {e}")
        return False

def delete_project_from_db(project_id):
    """Delete a project from MongoDB"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        
        object_id = ObjectId(project_id)
        result = projects_collection.delete_one({"_id": object_id})
        return result.deleted_count > 0
    except Exception as e:
        st.error(f"Error deleting project: {e}")
        return False

def update_project_level_in_db(project_id, new_level, timestamp):
    """Update project level and timestamp in MongoDB"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        
        object_id = ObjectId(project_id)
        result = projects_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "level": new_level,
                    f"timestamps.{new_level}": timestamp
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Error updating project level: {e}")
        return False

# ───── Client Database Operations ─────
def get_all_clients():
    """Get all client names from database"""
    collections = get_db_collections()
    clients_collection = collections["clients"]
    return [c["client_name"] for c in clients_collection.find({}, {"client_name": 1}) if "client_name" in c]

def update_client_project_count(client_name):
    """Update project count for a specific client"""
    try:
        collections = get_db_collections()
        projects_collection = collections["projects"]
        clients_collection = collections["clients"]
        
        project_count = projects_collection.count_documents({"client": client_name})
        clients_collection.update_one(
            {"name": client_name},
            {"$set": {"project_count": project_count}}
        )
        return True
    except Exception as e:
        st.warning(f"Failed to update project count for client {client_name}: {e}")
        return False

# ───── User Database Operations ─────
@st.cache_data
def get_team_members(role):
    """Get team members based on role"""
    collections = get_db_collections()
    users_collection = collections["users"]
    
    if role == "manager":
        return [u["name"] for u in users_collection.find({"role": "user"}) if "name" in u]
    else:
        return [u["name"] for u in users_collection.find() if "name" in u]

def move_project_to_completed(project_name, team_members):
    """Move project from 'projects' to 'completed_projects' for all team members"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        
        # Get all users who have this project in their projects list
        users_to_update = list(users_collection.find({"project": project_name}))
        
        for user in users_to_update:
            # Initialize completed_projects field if it doesn't exist
            if "completed_projects" not in user:
                users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"completed_projects": []}}
                )
            
            # Move project from projects to completed_projects
            users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$pull": {"project": project_name},
                    "$addToSet": {"completed_projects": project_name}
                }
            )
        
        return len(users_to_update)
    except Exception as e:
        st.error(f"Error moving project to completed: {e}")
        return 0

def update_project_name_in_user_profiles(old_name, new_name):
    """Update project name in all user profiles when a project name is changed"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        projects_collection = collections["projects"]
        
        # Check if another project with the new name already exists
        existing_project = projects_collection.find_one({"name": new_name})
        if existing_project and str(existing_project["_id"]) != st.session_state.edit_project_id:
            st.error("Another project with this name already exists.")
            st.stop()
        
        # Update all users who have the old project name in their project list
        result = users_collection.update_many(
            {"project": old_name},
            {"$set": {"project.$": new_name}}
        )
        return result.modified_count
    except Exception as e:
        st.error(f"Error updating project name in user profiles: {e}")
        return 0

def remove_project_from_all_users(project_name):
    """Remove a project from all user profiles"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        
        users_collection.update_many(
            {"project": project_name},
            {"$pull": {"project": project_name}}
        )
    except Exception as e:
        st.error(f"Error removing project from user profiles: {e}")

def update_users_with_project(team_list, project_name):
    """Add project to user profiles for team members"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        
        for user in team_list:
            # Step 1: Ensure the project field is a list if it exists as a string
            user_doc = users_collection.find_one({"name": user})
            if user_doc:
                if "project" in user_doc and isinstance(user_doc["project"], str):
                    users_collection.update_one(
                        {"name": user},
                        {"$set": {"project": [user_doc["project"]]}}
                    )
                elif "project" not in user_doc:
                    users_collection.update_one(
                        {"name": user},
                        {"$set": {"project": []}}
                    )

            # Step 2: Add new project without duplicates
            users_collection.update_one(
                {"name": user},
                {"$addToSet": {"project": project_name}}
            )
    except Exception as e:
        st.error(f"Error updating users with project: {e}")

def remove_project_from_users(old_team, new_team, project_name):
    """Remove project from users who are no longer on the team"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        
        removed_users = set(old_team) - set(new_team)
        for user in removed_users:
            users_collection.update_one(
                {"name": user},
                {"$pull": {"project": project_name}}
            )
    except Exception as e:
        st.error(f"Error removing project from users: {e}")

def add_project_to_manager(username, project_name):
    """Add project to manager's profile"""
    try:
        collections = get_db_collections()
        users_collection = collections["users"]
        
        users_collection.update_one(
            {"username": username},
            {"$addToSet": {"project": project_name}}
        )
    except Exception as e:
        st.error(f"Error adding project to manager profile: {e}")

def update_substage_completion_in_db(project_id: str, stage_index: int, substage_index: int, completed: bool):
    """
    Update substage completion status in database
    This function should be implemented based on your database structure
    """
    try:        
        collections = get_db_collections()
        
        # Prepare the update path
        update_path = f"stage_assignments.{stage_index}.substages.{substage_index}.completed"
        completed_at_path = f"stage_assignments.{stage_index}.substages.{substage_index}.completed_at"
        updated_at_path = f"stage_assignments.{stage_index}.substages.{substage_index}.updated_at"
        
        update_data = {
            update_path: completed,
            updated_at_path: datetime.now().isoformat()
        }
        
        if completed:
            update_data[completed_at_path] = datetime.now().isoformat()
        else:
            # Remove completed_at when marking as incomplete
            collections["projects"].update_one(
                {"id": project_id},
                {"$unset": {completed_at_path: ""}}
            )
        
        result = collections["projects"].update_one(
            {"id": project_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        st.error(f"Error updating substage completion: {str(e)}")
        return False
