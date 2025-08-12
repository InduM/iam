import streamlit as st
from backend.clients_backend import ClientsBackend
from utils.utils_clients import (
    initialize_session_state, 
    filter_clients_by_search,
    validate_client_data,
    create_client_data,
    create_update_data,
    format_project_count_text,
    get_client_display_name,
    navigate_to_view
)

class ClientsFrontend:
    def __init__(self):
        self.backend = ClientsBackend()
        initialize_session_state()
    
    def show_dashboard(self):
        """Display the main clients dashboard"""
        # Action buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("➕ New Client"):
                navigate_to_view("create")
        with col2:
            if st.button("🔄 Refresh"):
                st.session_state.refresh_clients = True
                st.rerun()

        # Search Filter
        search_query = st.text_input("🔍 Search", placeholder="Name, Email, Company, SPOC, Phone or Description")

        # Load and filter clients
        clients = self.backend.load_clients()
        filtered_clients = filter_clients_by_search(clients, search_query)

        # Display clients
        for client in filtered_clients:
            self._render_client_card(client)
    
    def _render_client_card(self, client):
        """Render individual client card"""
        cid = client["_id"]
        client_name = client.get('client_name', 'Unnamed')
        
        # Get project count
        project_count = self.backend.count_related_projects(client_name)
        project_info = format_project_count_text(project_count)
        
        # Display client card
        display_name = get_client_display_name(client)
        with st.expander(f"{display_name}{project_info}"):
            self._render_client_details(client, project_count)
            self._render_client_actions(client, cid, project_count)
    
    def _render_client_details(self, client, project_count):
        """Render client details within the card"""
        st.markdown(f"**Email:** {client.get('email', '-')}")
        st.markdown(f"**SPOC Name:** {client.get('spoc_name', '-')}")
        st.markdown(f"**Phone Number:** {client.get('phone_number', '-')}")
        
        # Display description if it exists
        description = client.get('description', '')
        if description:
            st.markdown(f"**Description:** {description}")
        
        st.markdown(f"**Created By:** {client.get('created_by', '-')}")
        st.markdown(f"**Created At:** {client.get('created_at', '-')}")
        if project_count > 0:
            st.markdown(f"**Related Projects:** {project_count}")
    
    def _render_client_actions(self, client, cid, project_count):
        """Render action buttons for client card"""
        col1, col2 = st.columns(2)
        
        # Edit button
        if col1.button("✏ Edit", key=f"edit_{cid}"):
            navigate_to_view("edit", edit_client_id=cid)

        # Delete button with confirmation
        confirm_key = f"confirm_delete_{cid}"
        if not st.session_state.confirm_delete_client.get(confirm_key):
            # Show different button styles based on project count
            if project_count > 0:
                # Disabled-style button for clients with projects
                if col2.button("🚫 Delete", key=f"delete_{cid}", help="Cannot delete - client has associated projects"):
                    st.session_state.confirm_delete_client[confirm_key] = True
                    st.rerun()
            else:
                # Normal delete button for clients without projects
                if col2.button("🗑 Delete", key=f"delete_{cid}"):
                    st.session_state.confirm_delete_client[confirm_key] = True
                    st.rerun()
        else:
            self._render_delete_confirmation(cid, project_count, confirm_key)
        
    def _render_cancel_action(self, cid, confirm_key):
        """Render cancel action for clients with projects"""
        if st.button("❌ Cancel", key=f"cancel_{cid}"):
            st.session_state.confirm_delete_client[confirm_key] = False
            st.rerun()

    def _render_confirmation_actions(self, cid, confirm_key):
        """Render confirmation actions for clients without projects"""
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ Yes, Delete", key=f"yes_{cid}"):
            if self.backend.delete_client(cid):
                st.success("Client deleted successfully!")
                st.session_state.confirm_delete_client[confirm_key] = False
                st.rerun()
            else:
                st.error("Failed to delete client. Please try again.")
        
        if col_no.button("❌ Cancel", key=f"no_{cid}"):
            st.session_state.confirm_delete_client[confirm_key] = False
            st.rerun()

    def _render_delete_confirmation(self, cid, project_count, confirm_key):
        """Render delete confirmation dialog"""
        if project_count > 0:
            st.error(f"⚠️ Cannot delete client! This client has {project_count} associated project(s).")
            st.info("Please delete or reassign all associated projects before deleting this client.")
            
            # Only show cancel button when there are projects
            self._render_cancel_action(cid, confirm_key)
        else:
            # Only show Yes/No buttons when there are no projects
            st.warning("Are you sure you want to delete this client?")
            self._render_confirmation_actions(cid, confirm_key)
    
    def show_create_form(self):
        """Display the create client form"""
        st.title("➕ Create Client")
        
        # Back button
        if st.button("← Back"):
            navigate_to_view("dashboard")

        # Form fields
        name, email, company, spoc_name, phone_number, description = self._render_client_form()

        # Submit button
        if st.button("✅ Create Client"):
            self._handle_create_client(name, email, company, spoc_name, phone_number, description)
    
    def show_edit_form(self):
        """Display the edit client form"""
        st.title("✏ Edit Client")
        
        # Back button
        if st.button("← Back"):
            navigate_to_view("dashboard")

        # Get client data
        cid = st.session_state.edit_client_id
        client = self.backend.get_client_by_id(cid)
        
        if not client:
            st.error("Client not found.")
            return

        # Show warning about related projects
        self._show_edit_warning(client)

        # Form fields with current values
        name, email, company, spoc_name, phone_number, description = self._render_client_form(client)

        # Submit button
        if st.button("💾 Save Changes"):
            self._handle_update_client(cid, name, email, company, spoc_name, phone_number, description)
    
    def _render_client_form(self, client=None):
        """Render client form fields"""
        # Basic Information Section
        name = st.text_input(
            "Client Name *", 
            value=client.get("client_name", "") if client else "",
            placeholder="Enter client name"
        )
        email = st.text_input(
            "Email *", 
            value=client.get("email", "") if client else "",
            placeholder="Enter email address"
        )
        company = st.text_input(
            "Company *", 
            value=client.get("company", "") if client else "",
            placeholder="Enter company name"
        )
        
        # SPOC Details Section
        spoc_name = st.text_input(
            "SPOC Name", 
            value=client.get("spoc_name", "") if client else "",
            placeholder="Enter SPOC full name"
        )
        phone_number = st.text_input(
            "Phone Number", 
            value=client.get("phone_number", "") if client else "",
            placeholder="Enter phone number"
        )
        
        # Description Section
        description = st.text_area(
            "Description",
            value=client.get("description", "") if client else "",
            placeholder="Enter client description, notes, or additional information...",
            height=100,
            help="Optional field for additional client information, notes, or special requirements"
        )
        
        return name, email, company, spoc_name, phone_number, description
    
    def _show_edit_warning(self, client):
        """Show warning about related projects when editing"""
        current_name = client.get("client_name", "")
        project_count = self.backend.count_related_projects(current_name)
        
        if project_count > 0:
            st.info(f"⚠️ This client has {project_count} associated project(s). Changing the name will update all related projects.")
    
    def _handle_create_client(self, name, email, company, spoc_name, phone_number, description):
        """Handle client creation"""
        # Validate required fields
        errors = validate_client_data(name, email, company)
        if errors:
            st.error("Please fix the following errors:")
            for error in errors:
                st.error(f"• {error}")
            return
        
        # Check for duplicate name
        if self.backend.client_exists_by_name(name):
            st.error("A client with this name already exists.")
            return
        
        # Create client
        username = st.session_state.get("username", "unknown")
        client_data = create_client_data(name, email, company, spoc_name, phone_number, username, description)
        
        if self.backend.save_client(client_data):
            st.success("Client created successfully!")
            navigate_to_view("dashboard")
    
    def _handle_update_client(self, cid, name, email, company, spoc_name, phone_number, description):
        """Handle client update"""
        # Validate required fields
        errors = validate_client_data(name, email, company)
        if errors:
            st.error("Please fix the following errors:")
            for error in errors:
                st.error(f"• {error}")
            return
        
        # Check for duplicate name (excluding current client)
        if self.backend.client_exists_by_name(name, exclude_id=cid):
            st.error("A client with this name already exists.")
            return
        
        # Update client
        updated_data = create_update_data(name, email, company, spoc_name, phone_number, description)
        
        if self.backend.update_client(cid, updated_data):
            st.success("Client updated successfully!")
            navigate_to_view("dashboard")
    
    def run(self):
        """Main entry point for the clients module"""
        # Navigation based on current view
        if st.session_state.client_view == "dashboard":
            self.show_dashboard()
        elif st.session_state.client_view == "create":
            self.show_create_form()
        elif st.session_state.client_view == "edit":
            self.show_edit_form()

def run():
    """Entry point function to maintain compatibility"""
    frontend = ClientsFrontend()
    frontend.run()