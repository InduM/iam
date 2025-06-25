import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

def run():
    # ───── MongoDB Connection ─────
    @st.cache_resource
    def init_connection():
        return MongoClient(st.secrets["MONGO_URI"])

    client = init_connection()
    db = client["user_db"]
    clients_collection = db["clients"]
    projects_collection = db["projects"]  # Added projects collection reference

    # ───── Session State ─────
    for key, default in {
        "client_view": "dashboard",
        "edit_client_id": None,
        "confirm_delete_client": {},
        "refresh_clients": False
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # ───── Database Operations ─────
    def load_clients():
        try:
            role = st.session_state.get("role", "")
            username = st.session_state.get("username", "")

            if role == "manager":
                # Managers can see clients created by themselves and by admins
                query = {"$or": [{"created_by": username}, {"created_by": {"$regex": "admin", "$options": "i"}}]}
            else:
                # Admins and other roles can see all clients
                query = {}

            clients = list(clients_collection.find(query))
            for c in clients:
                c["id"] = str(c["_id"])
            return clients
        except Exception as e:
            st.error(f"Error loading clients: {e}")
            return []

    def save_client(data):
        try:
            result = clients_collection.insert_one(data)
            return str(result.inserted_id)
        except Exception as e:
            st.error(f"Error saving client: {e}")
            return None

    def update_client(cid, data):
        try:
            object_id = ObjectId(cid)
            
            # Get the old client data before updating
            old_client = clients_collection.find_one({"_id": object_id})
            if not old_client:
                st.error("Client not found.")
                return False
            
            old_name = old_client.get("name", "")
            new_name = data.get("name", "")
            
            # Update the client
            result = clients_collection.update_one({"_id": object_id}, {"$set": data})
            
            # If client name changed, update all related projects
            if result.modified_count > 0 and old_name != new_name:
                try:
                    # Update all projects that reference this client
                    projects_update_result = projects_collection.update_many(
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

    def delete_client(cid):
        try:
            object_id = ObjectId(cid)
            
            # Get client name before deletion to check for related projects
            client_to_delete = clients_collection.find_one({"_id": object_id})
            if client_to_delete:
                client_name = client_to_delete.get("name", "")
                
                # Check if there are any projects using this client
                related_projects = projects_collection.count_documents({"client": client_name})
                if related_projects > 0:
                    st.error(f"Cannot delete client. There are {related_projects} project(s) associated with this client. Please delete or reassign those projects first.")
                    return False
            
            result = clients_collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except Exception as e:
            st.error(f"Error deleting client: {e}")
            return False

    # ───── Pages ─────
    def show_dashboard():
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("➕ New Client"):
                st.session_state.client_view = "create"
                st.rerun()
        with col2:
            if st.button("🔄 Refresh"):
                st.session_state.refresh_clients = True
                st.rerun()

        # Search Filter
        search_query = st.text_input("🔍 Search", placeholder="Name, Email, or Company")

        clients = load_clients()

        if search_query:
            q = search_query.lower()
            clients = [c for c in clients if
                    q in c.get("name", "").lower() or
                    q in c.get("email", "").lower() or
                    q in c.get("company", "").lower()]

        for client in clients:
            cid = client["id"]
            client_name = client.get('name', 'Unnamed')
            
            # Count related projects for this client
            try:
                project_count = projects_collection.count_documents({"client": client_name})
                project_info = f" ({project_count} project{'s' if project_count != 1 else ''})"
            except:
                project_info = ""
            
            with st.expander(f"{client_name} – {client.get('company', '-')}{project_info}"):
                st.markdown(f"**Email:** {client.get('email', '-')}")
                st.markdown(f"**Created By:** {client.get('created_by', '-')}")
                st.markdown(f"**Created At:** {client.get('created_at', '-')}")
                if project_count > 0:
                    st.markdown(f"**Related Projects:** {project_count}")

                col1, col2 = st.columns(2)
                if col1.button("✏ Edit", key=f"edit_{cid}"):
                    st.session_state.edit_client_id = cid
                    st.session_state.client_view = "edit"
                    st.rerun()

                confirm_key = f"confirm_delete_{cid}"
                if not st.session_state.confirm_delete_client.get(confirm_key):
                    if col2.button("🗑 Delete", key=f"delete_{cid}"):
                        st.session_state.confirm_delete_client[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("Are you sure?")
                    if project_count > 0:
                        st.error(f"This client has {project_count} associated project(s). Delete or reassign them first.")
                    col_yes, col_no = st.columns(2)
                    if col_yes.button("✅ Yes", key=f"yes_{cid}"):
                        if delete_client(cid):
                            st.success("Client deleted.")
                            st.session_state.confirm_delete_client[confirm_key] = False
                            st.rerun()
                    if col_no.button("❌ No", key=f"no_{cid}"):
                        st.session_state.confirm_delete_client[confirm_key] = False
                        st.rerun()

    def show_create_form():
        if st.button("← Back"):
            st.session_state.client_view = "dashboard"
            st.rerun()

        name = st.text_input("Name")
        email = st.text_input("Email")
        company = st.text_input("Company")

        if st.button("✅ Create"):
            if not name or not email or not company:
                st.error("All fields are required.")
            else:
                client_data = {
                    "name": name,
                    "email": email,
                    "company": company,
                    "created_by": st.session_state.get("username", "unknown"),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                existing = clients_collection.find_one({"name": name})
                if existing:
                    st.error("A client with this name already exists.")
                elif save_client(client_data):
                    st.success("Client created!")
                    st.session_state.client_view = "dashboard"
                    st.rerun()

    def show_edit_form():
        st.title("✏ Edit Client")
        if st.button("← Back"):
            st.session_state.client_view = "dashboard"
            st.rerun()

        cid = st.session_state.edit_client_id
        client = clients_collection.find_one({"_id": ObjectId(cid)})
        if not client:
            st.error("Client not found.")
            return

        # Show current client name and related projects count
        current_name = client.get("name", "")
        try:
            project_count = projects_collection.count_documents({"client": current_name})
            if project_count > 0:
                st.info(f"⚠️ This client has {project_count} associated project(s). Changing the name will update all related projects.")
        except:
            pass

        name = st.text_input("Name", value=client.get("name", ""))
        email = st.text_input("Email", value=client.get("email", ""))
        company = st.text_input("Company", value=client.get("company", ""))

        if st.button("💾 Save"):
            if not name or not email or not company:
                st.error("All fields are required.")
            else:
                updated = {
                    "name": name,
                    "email": email,
                    "company": company,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                existing = clients_collection.find_one({"name": name, "_id": {"$ne": ObjectId(cid)}})
                if existing:
                    st.error("A client with this name already exists.")
                elif update_client(cid, updated):
                    st.success("Client updated.")
                    st.session_state.client_view = "dashboard"
                    st.rerun()

    # ───── Navigation ─────
    if st.session_state.client_view == "dashboard":
        show_dashboard()
    elif st.session_state.client_view == "create":
        show_create_form()
    elif st.session_state.client_view == "edit":
        show_edit_form()