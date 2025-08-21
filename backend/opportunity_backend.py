import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

class OpportunityBackend:
    def __init__(self):
        self.client = self._init_connection()
        self.db = self.client["user_db"]
        self.clients_collection = self.db["clients"]
        self.projects_collection = self.db["projects"]
    
    @st.cache_resource
    def _init_connection(_self):
        return MongoClient(st.secrets["MONGO_URI"])
    
    def load_clients(self):
        """Load clients based on user role and permissions"""
        try:
            role = st.session_state.get("role", "")
            username = st.session_state.get("username", "")

            if role == "manager":
                # Managers can see clients created by themselves and by admins
                query = {"$or": [{"created_by": username}, {"created_by": {"$regex": "admin", "$options": "i"}}]}
            else:
                # Admins and other roles can see all clients
                query = {}

            clients = list(self.clients_collection.find(query))
            for c in clients:
                c["id"] = str(c["_id"])
            return clients
        except Exception as e:
            st.error(f"Error loading clients: {e}")
            return []
    
    def save_client(self, data):
        """Save a new client to the database"""
        try:
            result = self.clients_collection.insert_one(data)
            return str(result.inserted_id)
        except Exception as e:
            st.error(f"Error saving client: {e}")
            return None
    
    def update_client(self, cid, data):
        """Update an existing client and handle related projects"""
        try:
            object_id = ObjectId(cid)
            
            # Get the old client data before updating
            old_client = self.clients_collection.find_one({"_id": object_id})
            if not old_client:
                st.error("Client not found.")
                return False
            
            old_name = old_client.get("client_name", "")
            new_name = data.get("client_name", "")
            
            # Update the client
            result = self.clients_collection.update_one({"_id": object_id}, {"$set": data})
            
            # If client name changed, update all related projects
            if result.modified_count > 0 and old_name != new_name:
                try:
                    # Update all projects that reference this client (using "client" field)
                    projects_update_result = self.projects_collection.update_many(
                        {"client": old_name},
                        {"$set": {"client": new_name}}
                    )
                    
                    if projects_update_result.modified_count > 0:
                        st.info(f"Updated {projects_update_result.modified_count} project(s) with new client name.")
                except Exception as e:
                    st.warning(f"Client updated but failed to update related projects: {e}")
            
            return result.modified_count > 0
        except Exception as e:
            st.error(f"Error updating client: {e}")
            return False
    
    def delete_client(self, cid):
        """Delete a client after checking for related projects"""
        try:
            object_id = ObjectId(cid)
            
            # Get client name before deletion to check for related projects
            client_to_delete = self.clients_collection.find_one({"_id": object_id})
            if client_to_delete:
                client_name = client_to_delete.get("client_name", "")
                
                # Check if there are any projects using this client (using "client" field)
                related_projects = self.projects_collection.count_documents({"client": client_name})
                if related_projects > 0:
                    st.error(f"Cannot delete client. There are {related_projects} project(s) associated with this client. Please delete or reassign those projects first.")
                    return False
            
            result = self.clients_collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except Exception as e:
            st.error(f"Error deleting client: {e}")
            return False
    
    def get_client_by_id(self, cid):
        """Get a single client by ID"""
        try:
            return self.clients_collection.find_one({"_id": ObjectId(cid)})
        except Exception as e:
            st.error(f"Error fetching client: {e}")
            return None
    
    def client_exists_by_name(self, name, exclude_id=None):
        """Check if a client with the given name already exists"""
        try:
            query = {"client_name": name}
            if exclude_id:
                query["_id"] = {"$ne": ObjectId(exclude_id)}
            return self.clients_collection.find_one(query) is not None
        except Exception as e:
            st.error(f"Error checking client existence: {e}")
            return False
    
    def count_related_projects(self, client_name):
        """Count projects associated with a client"""
        try:
            return self.projects_collection.count_documents({"client": client_name})
        except Exception as e:
            st.error(f"Error counting related projects: {e}")
            return 0
    # Optional: Add this method to the backend for additional safety
    def can_delete_client(self, client_name):
        """Check if a client can be safely deleted (no associated projects)"""
        project_count = self.count_related_projects(client_name)
        return project_count == 0

    # Optional: Enhanced delete method with safety check
    def delete_client_safe(self, cid):
        """Delete client only if no associated projects exist"""
        # Get client data first
        client = self.get_client_by_id(cid)
        if not client:
            return False
        
        # Check for associated projects
        client_name = client.get('client_name', '')
        if not self.can_delete_client(client_name):
            return False
        
        # Proceed with deletion
        return self.delete_client(cid)

    def get_related_project_names(self, client_name):
        """Return a list of project names linked to the given client"""
        try:
            projects = self.projects_collection.find(
                {"client": client_name},
                {"name": 1, "_id": 0}  # Only return the 'name' field
            )
            return [p.get("name", "Unnamed Project") for p in projects]
        except Exception as e:
            st.error(f"Error fetching related projects: {e}")
            return []
