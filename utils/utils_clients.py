import streamlit as st
from datetime import datetime

def initialize_session_state():
    """Initialize session state variables for clients module"""
    defaults = {
        "client_view": "dashboard",
        "edit_client_id": None,
        "confirm_delete_client": {},
        "refresh_clients": False
    }
    
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

def filter_clients_by_search(clients, search_query):
    """Filter clients based on search query"""
    if not search_query:
        return clients
    
    q = search_query.lower()
    return [c for c in clients if
            q in c.get("client_name", "").lower() or
            q in c.get("email", "").lower() or
            q in c.get("company", "").lower() or
            q in c.get("spoc_name", "").lower() or
            q in c.get("phone_number", "").lower()]

def validate_client_data(name, email, company):
    """Validate required client fields"""
    errors = []
    
    if not name or not name.strip():
        errors.append("Client Name is required")
    
    if not email or not email.strip():
        errors.append("Email is required")
    
    if not company or not company.strip():
        errors.append("Company is required")
    
    return errors

def create_client_data(name, email, company, spoc_name, phone_number, username):
    """Create client data dictionary with metadata"""
    return {
        "client_name": name,
        "email": email,
        "company": company,
        "spoc_name": spoc_name,
        "phone_number": phone_number,
        "created_by": username,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def create_update_data(name, email, company, spoc_name, phone_number):
    """Create update data dictionary with metadata"""
    return {
        "client_name": name,
        "email": email,
        "company": company,
        "spoc_name": spoc_name,
        "phone_number": phone_number,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def format_project_count_text(count):
    """Format project count for display"""
    if count == 0:
        return ""
    elif count == 1:
        return " (1 project)"
    else:
        return f" ({count} projects)"

def get_client_display_name(client):
    """Get formatted display name for client"""
    client_name = client.get('client_name', 'Unnamed')
    company = client.get('company', '-')
    return f"{client_name} – {company}"

def navigate_to_view(view_name, **kwargs):
    """Navigate to a specific view and update session state"""
    st.session_state.client_view = view_name
    
    # Set additional session state variables if provided
    for key, value in kwargs.items():
        st.session_state[key] = value
    
    st.rerun()

def reset_confirmation_state():
    """Reset confirmation states"""
    st.session_state.confirm_delete_client = {}