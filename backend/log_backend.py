import streamlit as st
from pymongo import MongoClient
import certifi
from datetime import datetime


class LogBackend:
    def __init__(self):
        self.MONGO_URI = st.secrets["MONGO_URI"]
        self.client = MongoClient(self.MONGO_URI, tlsCAFile=certifi.where())
        self.db = self.client["user_db"]
        self.logs_collection = self.db["logs"]
        self.users_collection = self.db["users"]
        self.clients_collection = self.db["clients"]

    def get_user_projects(self, username):
        """Get user's assigned projects from MongoDB"""
        try:
            user_doc = self.users_collection.find_one({"username": username})
            assigned_projects = user_doc.get("project", []) if user_doc else []
            if isinstance(assigned_projects, str):
                assigned_projects = [assigned_projects]
            return sorted(assigned_projects) if assigned_projects else []
        except Exception as e:
            st.error(f"Error getting user projects: {e}")
            return []

    def get_client_data(self):
        """Fetch client names and details from MongoDB"""
        try:
            # Fetch clients with all necessary fields
            clients = list(self.clients_collection.find({}, {
                "client_name": 1, 
                "spoc_name": 1, 
                "email": 1, 
                "phone_number": 1, 
                "_id": 0
            }))
            
            # Create a dictionary for easy lookup
            client_dict = {}
            client_names = []
            
            for client in clients:
                if client.get("client_name"):
                    client_name = client.get("client_name", "")
                    client_names.append(client_name)
                    client_dict[client_name] = {
                        "spoc_name": client.get("spoc_name", ""),
                        "email": client.get("email", ""),
                        "phone_number": client.get("phone_number", "")
                    }
            
            return sorted(client_names), client_dict
        except Exception as e:
            st.error(f"Error fetching clients: {e}")
            return [], {}

    def fetch_logs(self, date_str, username):
        """Fetch logs from MongoDB for a specific date and user"""
        try:
            query = {"Date": date_str, "Username": username}
            logs = list(self.logs_collection.find(query, {"_id": 0, "Date": 0, "Username": 0}))
            return logs
        except Exception as e:
            st.error(f"Error fetching logs: {e}")
            return []

    def save_logs(self, date_str, username, logs):
        """Save logs to MongoDB"""
        try:
            # Delete existing logs for the date
            self.logs_collection.delete_many({"Date": date_str, "Username": username})
            
            # Insert new logs
            for log in logs:
                self.logs_collection.insert_one({"Date": date_str, "Username": username, **log})
            
            return True
        except Exception as e:
            st.error(f"Error saving logs: {e}")
            return False

    def delete_log(self, date_str, username, log_time):
        """Delete a specific log entry"""
        try:
            self.logs_collection.delete_one({
                "Date": date_str,
                "Time": log_time,
                "Username": username
            })
            return True
        except Exception as e:
            st.error(f"Error deleting log: {e}")
            return False