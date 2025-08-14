import streamlit as st
import pandas as pd
import json
from datetime import datetime
from backend.opportunity_backend import OpportunityBackend
from utils.utils_opportunity import (
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
        self.backend = OpportunityBackend()
        initialize_session_state()
        self._initialize_dynamic_fields()
    
    def _initialize_dynamic_fields(self):
        """Initialize session state for dynamic fields"""
        if 'additional_fields' not in st.session_state:
            st.session_state.additional_fields = []
        if 'additional_spocs' not in st.session_state:
            st.session_state.additional_spocs = []
        if 'opportunity_data' not in st.session_state:
            st.session_state.opportunity_data = None
        if 'opportunity_shared_users' not in st.session_state:
            st.session_state.opportunity_shared_users = []
    
    def show_dashboard(self):
        """Display the main clients dashboard"""
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("➕ New Client"):
                navigate_to_view("create")
        with col2:
            if st.button("🔄 Refresh"):
                st.session_state.refresh_clients = True
                st.rerun()
        with col3:
            if st.button("📤 Export"):
                self._handle_export_clients()

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
        
        description = client.get('description', '')
        if description:
            st.markdown(f"**Description:** {description}")
        
        # Display additional fields if they exist
        additional_fields = client.get('additional_fields', [])
        for field in additional_fields:
            st.markdown(f"**{field.get('label', 'Additional Info')}:** {field.get('value', '-')}")
        
        # Display additional SPOCs if they exist
        additional_spocs = client.get('additional_spocs', [])
        if additional_spocs:
            st.markdown("**Additional SPOCs:**")
            for i, spoc in enumerate(additional_spocs, 1):
                st.markdown(f"  **SPOC {i}:** {spoc.get('name', '-')} | {spoc.get('email', '-')} | {spoc.get('phone', '-')}")
        
        st.markdown(f"**Created By:** {client.get('created_by', '-')}")
        st.markdown(f"**Created At:** {client.get('created_at', '-')}")
        
        if project_count > 0:
            # ✅ Get project names from backend
            project_names = self.backend.get_related_project_names(client.get("client_name", ""))
            tooltip_text = "\n,".join(project_names) if project_names else "No projects found"
            
            # Display with hover tooltip
            st.markdown(
                f"**Related Projects:** {project_count}",
                help=tooltip_text
            )

    def _render_client_actions(self, client, cid, project_count):
        """Render action buttons for client card"""
        col1, col2, col3 = st.columns(3)
        
        # Edit button
        if col1.button("✏ Edit", key=f"edit_{cid}"):
            navigate_to_view("edit", edit_client_id=cid)

        # To Client button (convert opportunity to client)
        if col2.button("👤 To Client", key=f"to_client_{cid}"):
            # Pre-populate with current client data for conversion
            st.session_state.opportunity_data = {
                "client_name": client.get("client_name", ""),
                "email": client.get("email", ""),
                "company": client.get("company", ""),
                "spoc_name": client.get("spoc_name", ""),
                "phone_number": client.get("phone_number", ""),
                "description": client.get("description", ""),
                "source_client_id": str(cid)
            }
            navigate_to_view("opportunity_to_client")

        # Delete button with confirmation
        confirm_key = f"confirm_delete_{cid}"
        if not st.session_state.confirm_delete_client.get(confirm_key):
            # Show different button styles based on project count
            if project_count > 0:
                # Disabled-style button for clients with projects
                if col3.button("🚫 Delete", key=f"delete_{cid}", help="Cannot delete - client has associated projects"):
                    st.session_state.confirm_delete_client[confirm_key] = True
                    st.rerun()
            else:
                # Normal delete button for clients without projects
                if col3.button("🗑 Delete", key=f"delete_{cid}"):
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
            # Clear dynamic fields and shared users when going back
            st.session_state.additional_fields = []
            st.session_state.additional_spocs = []
            st.session_state.opportunity_shared_users = []
            navigate_to_view("dashboard")

        # Form fields
        form_data = self._render_client_form()

        # Submit button
        if st.button("✅ Create Client"):
            self._handle_create_client(form_data)
    
    def show_edit_form(self):
        """Display the edit client form"""
        st.title("✏ Edit Client")
        
        # Back button
        if st.button("← Back"):
            # Clear dynamic fields and shared users when going back
            st.session_state.additional_fields = []
            st.session_state.additional_spocs = []
            st.session_state.opportunity_shared_users = []
            navigate_to_view("dashboard")

        # Get client data
        cid = st.session_state.edit_client_id
        client = self.backend.get_client_by_id(cid)
        
        if not client:
            st.error("Client not found.")
            return

        # Load existing additional fields into session state
        self._load_existing_additional_data(client)

        # Show warning about related projects
        self._show_edit_warning(client)

        # Form fields with current values
        form_data = self._render_client_form(client)

        # Submit button
        if st.button("💾 Save Changes"):
            self._handle_update_client(cid, form_data)
    
    def _load_existing_additional_data(self, client):
        """Load existing additional fields and SPOCs into session state for editing"""
        # Load additional fields if not already loaded
        if not st.session_state.additional_fields and client.get('additional_fields'):
            st.session_state.additional_fields = client.get('additional_fields', [])
        
        # Load additional SPOCs if not already loaded
        if not st.session_state.additional_spocs and client.get('additional_spocs'):
            st.session_state.additional_spocs = client.get('additional_spocs', [])
    
    def _render_client_form(self, client=None):
        """Render client form fields"""
        # Basic Information Section
        st.subheader("📋 Basic Information")
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
        
        # Created By and Sharing Section
        st.subheader("👥 Access Control")
        current_user = st.session_state.get("username", "unknown")
        is_admin = st.session_state.get("user_role", "") == "admin"
        
        # Created by field (read-only for existing clients)
        if client:
            created_by = client.get("created_by", "unknown")
            st.text_input("Created By", value=created_by, disabled=True)
        else:
            st.text_input("Created By", value=current_user, disabled=True)
        
        # Shared users section
        st.markdown("**Share with users:**")
        shared_users_text = st.text_input(
            "Shared Users",
            value=", ".join(client.get("shared_users", []) if client else st.session_state.opportunity_shared_users),
            placeholder="Enter usernames separated by commas (e.g., user1, user2, admin)",
            help="Users listed here will be able to view and edit this opportunity"
        )
        
        # Parse shared users
        shared_users = [user.strip() for user in shared_users_text.split(",") if user.strip()]
        st.session_state.opportunity_shared_users = shared_users
        
        # Display current sharing status
        if shared_users:
            st.info(f"📤 Sharing with: {', '.join(shared_users)}")
        
        # Primary SPOC Details Section
        st.subheader("👤 Primary SPOC Details")
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
        
        # Additional SPOCs Section
        st.subheader("👥 Additional SPOCs")
        self._render_additional_spocs_section()
        
        # Description Section
        st.subheader("📝 Description")
        description = st.text_area(
            "Description",
            value=client.get("description", "") if client else "",
            placeholder="Enter client description, notes, or additional information...",
            height=100,
            help="Optional field for additional client information, notes, or special requirements"
        )
        
        # Additional Fields Section
        st.subheader("📎 Additional Information")
        additional_fields = self._render_additional_fields_section()
        
        return {
            'name': name,
            'email': email, 
            'company': company,
            'spoc_name': spoc_name,
            'phone_number': phone_number,
            'description': description,
            'additional_fields': additional_fields,
            'additional_spocs': st.session_state.additional_spocs,
            'shared_users': shared_users
        }
    
    def _render_additional_fields_section(self):
        """Render the additional fields section with dynamic field addition"""
        # Button to add new field
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("➕ Add New Field", key="add_field_btn"):
                st.session_state.additional_fields.append({
                    'type': 'date',
                    'label': 'Date',
                    'value': ''
                })
                st.rerun()
        
        # Render existing additional fields
        fields_to_remove = []
        for i, field in enumerate(st.session_state.additional_fields):
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                field_type = st.selectbox(
                    "Field Type",
                    ["date", "text"],
                    index=0 if field.get('type', 'date') == 'date' else 1,
                    key=f"field_type_{i}"
                )
                st.session_state.additional_fields[i]['type'] = field_type
            
            with col2:
                if field_type == 'date':
                    st.session_state.additional_fields[i]['label'] = 'Date'
                    field_value = st.date_input(
                        "Date",
                        value=None,
                        key=f"field_date_{i}"
                    )
                    st.session_state.additional_fields[i]['value'] = str(field_value) if field_value else ''
                else:
                    label = st.text_input(
                        "Field Label",
                        value=field.get('label', 'Additional Information'),
                        key=f"field_label_{i}"
                    )
                    st.session_state.additional_fields[i]['label'] = label
                    
                    value = st.text_input(
                        "Value",
                        value=field.get('value', ''),
                        key=f"field_value_{i}"
                    )
                    st.session_state.additional_fields[i]['value'] = value
            
            with col3:
                if st.button("🗑", key=f"remove_field_{i}", help="Remove this field"):
                    fields_to_remove.append(i)
                    st.rerun()
        
        # Remove fields marked for deletion
        for i in reversed(fields_to_remove):
            st.session_state.additional_fields.pop(i)
        
        return st.session_state.additional_fields
    
    def _render_additional_spocs_section(self):
        """Render the additional SPOCs section with dynamic SPOC addition"""
        # Button to add new SPOC
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("➕ Add New SPOC", key="add_spoc_btn"):
                st.session_state.additional_spocs.append({
                    'name': '',
                    'email': '',
                    'phone': ''
                })
                st.rerun()
        
        # Render existing additional SPOCs
        spocs_to_remove = []
        for i, spoc in enumerate(st.session_state.additional_spocs):
            st.markdown("---")
            st.markdown(f"**SPOC {i + 1}**")
            
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            
            with col1:
                name = st.text_input(
                    "SPOC Name",
                    value=spoc.get('name', ''),
                    key=f"spoc_name_{i}",
                    placeholder="Enter SPOC name"
                )
                st.session_state.additional_spocs[i]['name'] = name
            
            with col2:
                email = st.text_input(
                    "Email",
                    value=spoc.get('email', ''),
                    key=f"spoc_email_{i}",
                    placeholder="Enter email address"
                )
                st.session_state.additional_spocs[i]['email'] = email
            
            with col3:
                phone = st.text_input(
                    "Phone Number",
                    value=spoc.get('phone', ''),
                    key=f"spoc_phone_{i}",
                    placeholder="Enter phone number"
                )
                st.session_state.additional_spocs[i]['phone'] = phone
            
            with col4:
                st.markdown("<br>", unsafe_allow_html=True)  # Add some spacing
                if st.button("🗑", key=f"remove_spoc_{i}", help="Remove this SPOC"):
                    spocs_to_remove.append(i)
                    st.rerun()
        
        # Remove SPOCs marked for deletion
        for i in reversed(spocs_to_remove):
            st.session_state.additional_spocs.pop(i)
    
    def _show_edit_warning(self, client):
        """Show warning about related projects when editing"""
        current_name = client.get("client_name", "")
        project_count = self.backend.count_related_projects(current_name)
        
        if project_count > 0:
            st.info(f"⚠️ This client has {project_count} associated project(s). Changing the name will update all related projects.")
    
    def _handle_create_client(self, form_data):
        """Handle client creation"""
        # Validate required fields
        errors = validate_client_data(form_data['name'], form_data['email'], form_data['company'])
        if errors:
            st.error("Please fix the following errors:")
            for error in errors:
                st.error(f"• {error}")
            return
        
        # Check for duplicate name
        if self.backend.client_exists_by_name(form_data['name']):
            st.error("A client with this name already exists.")
            return
        
        # Create client
        username = st.session_state.get("username", "unknown")
        client_data = self._create_enhanced_client_data(form_data, username)
        
        if self.backend.save_client(client_data):
            st.success("Client created successfully!")
            # Clear dynamic fields
            st.session_state.additional_fields = []
            st.session_state.additional_spocs = []
            navigate_to_view("dashboard")
    
    def _handle_update_client(self, cid, form_data):
        """Handle client update"""
        # Validate required fields
        errors = validate_client_data(form_data['name'], form_data['email'], form_data['company'])
        if errors:
            st.error("Please fix the following errors:")
            for error in errors:
                st.error(f"• {error}")
            return
        
        # Check for duplicate name (excluding current client)
        if self.backend.client_exists_by_name(form_data['name'], exclude_id=cid):
            st.error("A client with this name already exists.")
            return
        
        # Update client
        updated_data = self._create_enhanced_update_data(form_data)
        
        if self.backend.update_client(cid, updated_data):
            st.success("Client updated successfully!")
            # Clear dynamic fields
            st.session_state.additional_fields = []
            st.session_state.additional_spocs = []
            navigate_to_view("dashboard")
    
    def _create_enhanced_client_data(self, form_data, username):
        """Create enhanced client data including additional fields and SPOCs"""
        # Start with basic client data
        client_data = create_client_data(
            form_data['name'], 
            form_data['email'], 
            form_data['company'], 
            form_data['spoc_name'], 
            form_data['phone_number'], 
            username, 
            form_data['description']
        )
        
        # Add additional fields and SPOCs
        client_data['additional_fields'] = form_data['additional_fields']
        client_data['additional_spocs'] = form_data['additional_spocs']
        client_data['shared_users'] = form_data.get('shared_users', [])
        
        return client_data
    
    def _create_enhanced_update_data(self, form_data):
        """Create enhanced update data including additional fields and SPOCs"""
        # Start with basic update data
        update_data = create_update_data(
            form_data['name'], 
            form_data['email'], 
            form_data['company'], 
            form_data['spoc_name'], 
            form_data['phone_number'], 
            form_data['description']
        )
        
        # Add additional fields and SPOCs
        update_data['additional_fields'] = form_data['additional_fields']
        update_data['additional_spocs'] = form_data['additional_spocs']
        update_data['shared_users'] = form_data.get('shared_users', [])
        
        return update_data
    
    def _check_opportunity_access(self, client_data):
        """Check if current user has access to view/edit this opportunity"""
        current_user = st.session_state.get("username", "")
        user_role = st.session_state.get("user_role", "")
        created_by = client_data.get("created_by", "")
        shared_users = client_data.get("shared_users", [])
        
        # Admin has access to everything
        if user_role == "admin":
            return True
        
        # Creator has access
        if current_user == created_by:
            return True
        
        # Shared users have access
        if current_user in shared_users:
            return True
        
        return False
    
    def _handle_export_clients(self):
        """Handle client data export"""
        try:
            # Load all clients
            clients = self.backend.load_clients()
            
            if not clients:
                st.warning("No clients available to export.")
                return
            
            # Prepare data for export
            export_data = []
            for client in clients:
                # Flatten client data for CSV export
                flat_client = {
                    'ID': str(client.get('_id', '')),
                    'Client Name': client.get('client_name', ''),
                    'Email': client.get('email', ''),
                    'Company': client.get('company', ''),
                    'SPOC Name': client.get('spoc_name', ''),
                    'Phone Number': client.get('phone_number', ''),
                    'Description': client.get('description', ''),
                    'Created By': client.get('created_by', ''),
                    'Created At': client.get('created_at', ''),
                    'Updated At': client.get('updated_at', '')
                }
                
                # Add additional fields
                additional_fields = client.get('additional_fields', [])
                for i, field in enumerate(additional_fields):
                    flat_client[f'Additional Field {i+1} ({field.get("label", "Unknown")})'] = field.get('value', '')
                
                # Add additional SPOCs
                additional_spocs = client.get('additional_spocs', [])
                for i, spoc in enumerate(additional_spocs):
                    flat_client[f'SPOC {i+2} Name'] = spoc.get('name', '')
                    flat_client[f'SPOC {i+2} Email'] = spoc.get('email', '')
                    flat_client[f'SPOC {i+2} Phone'] = spoc.get('phone', '')
                
                export_data.append(flat_client)
            
            # Create DataFrame and CSV
            df = pd.DataFrame(export_data)
            csv_data = df.to_csv(index=False)
            
            # Create JSON export as well
            json_data = json.dumps(clients, indent=2, default=str)
            
            # Display export options
            st.success(f"✅ Ready to export {len(clients)} clients!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    help="Download clients data as CSV file"
                )
            
            with col2:
                st.download_button(
                    label="📥 Download JSON",
                    data=json_data,
                    file_name=f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    help="Download clients data as JSON file"
                )
                
        except Exception as e:
            st.error(f"Error exporting clients: {str(e)}")
    
    def show_opportunity_to_client_form(self):
        """Display the opportunity to client conversion form"""
        st.title("👤 Convert Opportunity to Client")
        
        # Back button
        if st.button("← Back"):
            st.session_state.opportunity_data = None
            navigate_to_view("dashboard")
        
        # Opportunity data input section
        st.subheader("📋 Opportunity Information")
        
        # Option to paste opportunity data or fill manually
        input_method = st.radio(
            "Choose input method:",
            ["Manual Entry", "Paste JSON Data"],
            horizontal=True
        )
        
        if input_method == "Paste JSON Data":
            st.markdown("**Paste opportunity JSON data:**")
            json_input = st.text_area(
                "JSON Data",
                placeholder='{"client_name": "Company Name", "email": "email@example.com", ...}',
                height=150,
                help="Paste the complete opportunity JSON data here"
            )
            
            if st.button("📝 Load from JSON"):
                try:
                    opportunity_data = json.loads(json_input)
                    st.session_state.opportunity_data = opportunity_data
                    st.success("✅ Opportunity data loaded successfully!")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("❌ Invalid JSON format. Please check your input.")
                except Exception as e:
                    st.error(f"❌ Error loading data: {str(e)}")
        
        # Form fields (with pre-filled data if available)
        opportunity_data = st.session_state.opportunity_data or {}
        
        st.subheader("📝 Client Information")
        form_data = self._render_opportunity_to_client_form(opportunity_data)
        
        # Convert button
        if st.button("🔄 Convert to Client"):
            self._handle_opportunity_to_client_conversion(form_data)
    
    def _render_opportunity_to_client_form(self, opportunity_data=None):
        """Render the opportunity to client conversion form"""
        # Extract data from opportunity if available
        opp_data = opportunity_data or {}
        
        # Basic Information Section
        st.markdown("##### 📋 Basic Information")
        name = st.text_input(
            "Client Name *", 
            value=opp_data.get("client_name", "") or opp_data.get("company_name", ""),
            placeholder="Enter client name"
        )
        email = st.text_input(
            "Email *", 
            value=opp_data.get("email", "") or opp_data.get("contact_email", ""),
            placeholder="Enter email address"
        )
        company = st.text_input(
            "Company *", 
            value=opp_data.get("company", "") or opp_data.get("client_name", "") or opp_data.get("company_name", ""),
            placeholder="Enter company name"
        )
        
        # SPOC Details Section
        st.markdown("##### 👤 SPOC Details")
        spoc_name = st.text_input(
            "SPOC Name", 
            value=opp_data.get("spoc_name", "") or opp_data.get("contact_name", "") or opp_data.get("contact_person", ""),
            placeholder="Enter SPOC full name"
        )
        phone_number = st.text_input(
            "Phone Number", 
            value=opp_data.get("phone_number", "") or opp_data.get("contact_phone", "") or opp_data.get("phone", ""),
            placeholder="Enter phone number"
        )
        
        # Description Section
        st.markdown("##### 📝 Description")
        description = st.text_area(
            "Description",
            value=opp_data.get("description", "") or opp_data.get("notes", "") or opp_data.get("details", ""),
            placeholder="Enter client description, notes, or additional information...",
            height=100,
            help="Optional field for additional client information"
        )
        
        # Show opportunity source info
        if opportunity_data:
            st.markdown("##### 📊 Source Information")
            st.info(f"**Source:** Converted from opportunity data")
            if opp_data.get("opportunity_id"):
                st.info(f"**Opportunity ID:** {opp_data.get('opportunity_id')}")
        
        return {
            'name': name,
            'email': email,
            'company': company,
            'spoc_name': spoc_name,
            'phone_number': phone_number,
            'description': description,
            'source_data': opportunity_data
        }
    
    def _handle_opportunity_to_client_conversion(self, form_data):
        """Handle conversion of opportunity data to client"""
        # Validate required fields
        errors = validate_client_data(form_data['name'], form_data['email'], form_data['company'])
        if errors:
            st.error("Please fix the following errors:")
            for error in errors:
                st.error(f"• {error}")
            return
        
        # Check for duplicate name
        if self.backend.client_exists_by_name(form_data['name']):
            st.error("A client with this name already exists.")
            return
        
        # Create client with source information
        username = st.session_state.get("username", "unknown")
        client_data = create_client_data(
            form_data['name'], 
            form_data['email'], 
            form_data['company'], 
            form_data['spoc_name'], 
            form_data['phone_number'], 
            username, 
            form_data['description']
        )
        
        # Add source information
        client_data['source'] = 'opportunity_conversion'
        client_data['source_data'] = form_data['source_data']
        client_data['converted_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if self.backend.save_client(client_data):
            st.success("✅ Client created successfully from opportunity data!")
            st.balloons()
            
            # Show summary
            st.markdown("### 📋 Conversion Summary")
            st.markdown(f"**Client Name:** {form_data['name']}")
            st.markdown(f"**Company:** {form_data['company']}")
            st.markdown(f"**Email:** {form_data['email']}")
            if form_data['spoc_name']:
                st.markdown(f"**SPOC:** {form_data['spoc_name']}")
            
            # Clear data and navigate back
            st.session_state.opportunity_data = None
            st.session_state.opportunity_shared_users = []
            
            # Auto-navigate back after 3 seconds
            import time
            time.sleep(2)
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
        elif st.session_state.client_view == "opportunity_to_client":
            self.show_opportunity_to_client_form()

def run():
    """Entry point function to maintain compatibility"""
    frontend = ClientsFrontend()
    frontend.run()