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
                query = {"created_by": username}
            else:
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
            result = clients_collection.update_one({"_id": object_id}, {"$set": data})
            return result.modified_count > 0
        except Exception as e:
            st.error(f"Error updating client: {e}")
            return False

    def delete_client(cid):
        try:
            object_id = ObjectId(cid)
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
            with st.expander(f"{client.get('name', 'Unnamed')} – {client.get('company', '-')}"):
                st.markdown(f"**Email:** {client.get('email', '-')}")
                st.markdown(f"**Created By:** {client.get('created_by', '-')}")
                st.markdown(f"**Created At:** {client.get('created_at', '-')}")

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
        st.title("➕ Create Client")
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
                if save_client(client_data):
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
                if update_client(cid, updated):
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
