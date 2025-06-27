import streamlit as st
import time
from datetime import datetime, date, timedelta
from typing import List

# Import functions from backend and utils
from .backend import (
    load_projects_from_db, save_project_to_db, update_project_in_db,
    delete_project_from_db, update_project_level_in_db, get_all_clients,
    update_client_project_count, get_team_members, move_project_to_completed,
    update_project_name_in_user_profiles, remove_project_from_all_users,
    update_users_with_project, remove_project_from_users, add_project_to_manager
)
from .utils import (
    TEMPLATES, send_invoice_email, format_level, render_level_checkboxes,
    initialize_session_state, get_current_timestamp, validate_project_dates,
    ensure_project_defaults
)

def run():
    """Main function to run the project management interface"""
    
    # Initialize session state
    initialize_session_state()
    
    # Load projects from database on first run or when explicitly refreshed
    if "projects" not in st.session_state or st.session_state.get("refresh_projects", False):
        st.session_state.projects = load_projects_from_db()
        st.session_state.refresh_projects = False
    
    # Navigation
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()

def show_dashboard():
    """Display the main dashboard with project list and controls"""
    st.query_params["_"] = str(int(time.time() // 60))  # Trigger rerun every 60 seconds

    # Action buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ New Project"):
            st.session_state.view = "create"
            st.rerun()
    with col2:
        if st.button("🔄Refresh"):
            st.session_state.refresh_projects = True
            st.rerun()

    # Filters and search
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search_query = st.text_input("Search", placeholder="Name, client, or team")
    with col2:
        filter_template = st.selectbox("Template", ["All"] + list(TEMPLATES.keys()))
    with col3:
        all_levels = sorted(set(
            lvl for proj in st.session_state.projects for lvl in proj.get("levels", [])
        ))
        filter_level = st.selectbox("Progress Level", ["All"] + all_levels)

    filter_due = st.date_input("Due Before or On", value=None)

    # Apply filters
    filtered_projects = _apply_filters(
        st.session_state.projects, search_query, filter_template, filter_level, filter_due
    )

    # Display projects
    for i, project in enumerate(filtered_projects):
        _render_project_card(project, i)

def show_create_form():
    """Display the create project form"""
    st.title("🛠 Create Project")
    
    # Back button
    _render_back_button()
    
    # Template selection
    template_options = ["Custom Template"] + list(TEMPLATES.keys())
    selected = st.selectbox("Select Template (optional)", template_options)
    
    if selected != "Custom Template":
        st.session_state.selected_template = selected
    else:
        st.session_state.selected_template = ""
    
    # Form fields
    name = st.text_input("Project Name")
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    client = st.selectbox("Client", options=clients)
    description = st.text_area("Project Description")
    start = st.date_input("Start Date")
    due = st.date_input("Due Date")
    
    team_members = get_team_members(st.session_state.get("role", ""))
    team = st.multiselect("Assign Team", team_members)
    
    # Handle template levels
    if st.session_state.selected_template:
        st.markdown(f"Using template: **{st.session_state.selected_template}**")
        levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
        for required in ["Invoice", "Payment"]:
            if required in levels_from_template:
                levels_from_template.remove(required)
        st.session_state.custom_levels = levels_from_template + ["Invoice", "Payment"]
    else:
        _render_custom_levels_editor()
    
    # Progress section
    _render_progress_section("create")
    
    # Create button
    if st.button("✅ Create Project"):
        _handle_create_project(name, client, description, start, due, team)

def show_edit_form():
    """Display the edit project form"""
    st.title("✏ Edit Project")
    
    # Back button
    _render_back_button()
    
    pid = st.session_state.edit_project_id
    project = next((p for p in st.session_state.projects if p["id"] == pid), None)
    
    if not project:
        st.error("Project not found.")
        return
    
    # Ensure project has required fields
    project = ensure_project_defaults(project)
    
    original_team = project.get("team", [])
    original_name = project.get("name", "")
    
    # Form fields
    name = st.text_input("Project Name", value=project.get("name", ""))
    clients = get_all_clients()
    if not clients:
        st.warning("⚠ No clients found in the database.")
    
    current_client = project.get("client", "")
    client_index = clients.index(current_client) if current_client in clients else 0
    client = st.selectbox("Client", options=clients, index=client_index)
    
    description = st.text_area("Project Description", value=project.get("description", ""))
    start = st.date_input("Start Date", value=date.fromisoformat(project.get("startDate", date.today().isoformat())))
    due = st.date_input("Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))
    
    team_members = get_team_members(st.session_state.get("role", ""))
    team = st.multiselect("Assign Team", team_members, default=project.get("team", []))
    
    # Progress section
    st.subheader("Progress")
    
    def on_change_edit(new_index):
        _handle_level_change_edit(project, pid, new_index)
    
    # Check for success messages
    _check_edit_success_messages(pid)
    
    render_level_checkboxes(
        "edit", pid, int(project.get("level", -1)), 
        project.get("timestamps", {}), project.get("levels", ["Initial", "Invoice", "Payment"]), 
        on_change_edit
    )
    
    # Save button
    if st.button("💾 Save"):
        _handle_save_project(pid, project, name, client, description, start, due, team, original_team, original_name)

# ───── Helper Functions ─────

def _render_back_button():
    """Render back button with styling"""
    st.markdown(
        """
        <style>
        .back-button {
            font-size: 24px;
            margin-bottom: 1rem;
            display: inline-block;
            cursor: pointer;
            color: #007BFF;
        }
        .back-button:hover {
            text-decoration: underline;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    if st.button("← Back", key="back_button"):
        st.session_state.view = "dashboard"
        st.rerun()

def _apply_filters(projects, search_query, filter_template, filter_level, filter_due):
    """Apply filters to project list"""
    filtered_projects = projects
    
    if search_query:
        q = search_query.lower()
        filtered_projects = [p for p in filtered_projects if
                            q in p.get("name", "").lower() or
                            q in p.get("client", "").lower() or
                            any(q in member.lower() for member in p.get("team", []))]
    
    if filter_template != "All":
        filtered_projects = [p for p in filtered_projects if p.get("template") == filter_template]
    
    if filter_due:
        filtered_projects = [p for p in filtered_projects if 
                           p.get("dueDate") and date.fromisoformat(p["dueDate"]) <= filter_due]
    
    if filter_level != "All":
        filtered_projects = [
            p for p in filtered_projects
            if p.get("level", -1) >= 0 and
            p.get("levels") and
            len(p["levels"]) > p.get("level", -1) and
            p["levels"][p["level"]] == filter_level
        ]
    
    return filtered_projects

def _render_project_card(project, index):
    """Render individual project card"""
    pid = project.get("id", f"auto_{index}")
    
    with st.expander(f"{project.get('name', 'Unnamed')}"):
        st.markdown(f"**Client:** {project.get('client', '-')}")
        st.markdown(f"**Description:** {project.get('description', '-')}")
        st.markdown(f"**Start Date:** {project.get('startDate', '-')}")
        st.markdown(f"**Due Date:** {project.get('dueDate', '-')}")
        st.markdown(f"**Manager/Lead:** {project.get('created_by', '-')}")
        st.markdown(f"**Team Assigned:** {', '.join(project.get('team', [])) or '-'}")
        
        levels = project.get("levels", ["Initial", "Invoice", "Payment"])
        current_level = project.get("level", -1)
        st.markdown(f"**Current Level:** {format_level(current_level, levels)}")
        
        # Level checkboxes
        def on_change_dashboard(new_index, proj_id=pid, proj=project):
            _handle_level_change_dashboard(proj_id, proj, new_index)
        
        # Check for success messages
        _check_dashboard_success_messages(pid)
        
        render_level_checkboxes(
            "view", pid, int(project.get("level", -1)), 
            project.get("timestamps", {}), levels, on_change_dashboard, editable=True
        )
        
        # Email reminder logic
        _handle_email_reminders(project, pid, levels, current_level)
        
        # Action buttons
        _render_project_action_buttons(project, pid)

def _render_custom_levels_editor():
    """Render custom levels editor"""
    st.subheader("Customize Progress Levels")
    if not st.session_state.custom_levels:
        st.session_state.custom_levels = ["Initial"]
    
    # Remove required levels from custom levels for editing
    for required in ["Invoice", "Payment"]:
        if required in st.session_state.custom_levels:
            st.session_state.custom_levels.remove(required)
    
    editable_levels = st.session_state.custom_levels.copy()
    for i in range(len(editable_levels)):
        cols = st.columns([5, 1])
        editable_levels[i] = cols[0].text_input(
            f"Level {i+1}", value=editable_levels[i], key=f"level_{i}"
        )
        if len(editable_levels) > 1 and cols[1].button("➖", key=f"remove_{i}"):
            editable_levels.pop(i)
            st.session_state.custom_levels = editable_levels
            st.rerun()
    
    st.session_state.custom_levels = editable_levels
    
    if st.button("➕ Add Level"):
        st.session_state.custom_levels.append(f"New Level {len(st.session_state.custom_levels) + 1}")
        st.rerun()
    
    # Add required levels back
    st.session_state.custom_levels += ["Invoice", "Payment"]

def _render_progress_section(form_type):
    """Render progress section for forms"""
    st.subheader("Progress")
    level_index = st.session_state.get("level_index", -1)
    level_timestamps = st.session_state.get("level_timestamps", {})
    
    def on_change_create(new_index):
        st.session_state.level_index = new_index
        st.session_state.level_timestamps[str(new_index)] = get_current_timestamp()
    
    render_level_checkboxes(
        form_type, "new", level_index, level_timestamps, 
        st.session_state.custom_levels, on_change_create
    )

def _handle_create_project(name, client, description, start, due, team):
    """Handle project creation"""
    if not validate_project_dates(start, due):
        st.error("Cannot submit: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    elif _check_project_name_exists(name):
        st.error("A project with this name already exists. Please choose a different name.")
    else:
        new_proj = _create_project_data(name, client, description, start, due, team)
        
        project_id = save_project_to_db(new_proj)
        if project_id:
            new_proj["id"] = project_id
            st.session_state.projects.append(new_proj)
            st.success("Project created and saved to database!")
            
            # Update client project count
            update_client_project_count(client)
            
            # Reset form state and navigate back
            _reset_create_form_state()
            
            # Update user profiles
            update_users_with_project(team, name)
            add_project_to_manager(st.session_state.get("username", ""), name)
            
            st.rerun()

def _handle_save_project(pid, project, name, client, description, start, due, team, original_team, original_name):
    """Handle project save"""
    if not validate_project_dates(start, due):
        st.error("Cannot save: Due date must be later than the start date.")
    elif not name or not client:
        st.error("Name and client are required.")
    else:
        updated_project = _create_updated_project_data(project, name, client, description, start, due, team)
        
        if update_project_in_db(pid, updated_project):
            success_messages = []
            
            # Update client project counts
            _update_client_counts_after_edit(project, client)
            
            # Handle name change
            if original_name != name:
                updated_count = update_project_name_in_user_profiles(original_name, name)
                if updated_count > 0:
                    success_messages.append(f"Project name updated in {updated_count} user profiles!")
            
            # Handle team changes
            success_messages.extend(_handle_team_changes(team, original_team, name))
            
            project.update(updated_project)
            
            # Display success messages
            _display_success_messages(success_messages)
            
            st.session_state.view = "dashboard"
            st.rerun()

def _handle_level_change_dashboard(proj_id, proj, new_index):
    """Handle level change in dashboard view"""
    timestamp = get_current_timestamp()
    if update_project_level_in_db(proj_id, new_index, timestamp):
        proj["level"] = new_index
        if "timestamps" not in proj:
            proj["timestamps"] = {}
        proj["timestamps"][str(new_index)] = timestamp
        
        # Check if project reached Payment stage
        _check_project_completion(proj, proj_id)
        
        st.session_state[f"level_update_success_{proj_id}"] = True

def _handle_level_change_edit(project, pid, new_index):
    """Handle level change in edit view"""
    timestamp = get_current_timestamp()
    project["level"] = new_index
    project.setdefault("timestamps", {})[str(new_index)] = timestamp
    
    # Update in database immediately
    if update_project_level_in_db(pid, new_index, timestamp):
        _check_project_completion(project, pid)
        st.session_state[f"edit_level_update_success_{pid}"] = True

def _check_project_completion(project, project_id):
    """Check if project has reached completion stage"""
    project_levels = project.get("levels", [])
    new_level = project.get("level", -1)
    
    if (new_level >= 0 and new_level < len(project_levels) and 
        project_levels[new_level] == "Payment"):
        project_name = project.get("name", "")
        team_members = project.get("team", [])
        moved_count = move_project_to_completed(project_name, team_members)
        if moved_count > 0:
            st.session_state[f"project_completed_message_{project_id}"] = \
                f"Project moved to completed for {moved_count} team member(s)!"

def _handle_email_reminders(project, pid, levels, current_level):
    """Handle email reminder logic"""
    project_name = project.get("name", "Unnamed")
    lead_email = st.secrets.get("project_leads", {}).get("Project Alpha")
    
    # Safe check for Invoice and Payment levels
    try:
        invoice_index = levels.index("Invoice") if "Invoice" in levels else -1
        payment_index = levels.index("Payment") if "Payment" in levels else -1
    except (ValueError, AttributeError):
        invoice_index = -1
        payment_index = -1
    
    email_key = f"last_email_sent_{pid}"
    if email_key not in st.session_state:
        st.session_state[email_key] = None
    
    if (0 <= invoice_index <= current_level) and (payment_index > current_level) and lead_email:
        now = datetime.now()
        last_sent = st.session_state[email_key]
        if not last_sent or now - last_sent >= timedelta(minutes=1):
            if send_invoice_email(lead_email, project_name):
                st.session_state[email_key] = now

def _render_project_action_buttons(project, pid):
    """Render project action buttons (Edit/Delete)"""
    col1, col2 = st.columns(2)
    if col1.button("✏ Edit", key=f"edit_{pid}"):
        st.session_state.edit_project_id = pid
        st.session_state.view = "edit"
        st.rerun()
    
    confirm_key = f"confirm_delete_{pid}"
    if not st.session_state.confirm_delete.get(confirm_key):
        if col2.button("🗑 Delete", key=f"del_{pid}"):
            st.session_state.confirm_delete[confirm_key] = True
            st.rerun()
    else:
        st.warning("Are you sure you want to delete this project?")
        col_yes, col_no = st.columns(2)
        if col_yes.button("✅ Yes", key=f"yes_{pid}"):
            _handle_project_deletion(pid, project)
        if col_no.button("❌ No", key=f"no_{pid}"):
            st.session_state.confirm_delete[confirm_key] = False
            st.rerun()

def _handle_project_deletion(pid, project):
    """Handle project deletion"""
    if delete_project_from_db(pid):
        st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != pid]
        remove_project_from_all_users(project.get("name", "Unnamed"))
        st.success("Project deleted from database.")
        
        # Update client project count after deletion
        client_name = project.get("client", "")
        update_client_project_count(client_name)
    
    st.session_state.confirm_delete[f"confirm_delete_{pid}"] = False
    st.rerun()

def _check_dashboard_success_messages(pid):
    """Check and display dashboard success messages"""
    if st.session_state.get(f"level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

def _check_edit_success_messages(pid):
    """Check and display edit form success messages"""
    if st.session_state.get(f"edit_level_update_success_{pid}", False):
        st.success("Project level updated!")
        st.session_state[f"edit_level_update_success_{pid}"] = False
    
    if st.session_state.get(f"project_completed_message_{pid}"):
        st.success(st.session_state[f"project_completed_message_{pid}"])
        st.session_state[f"project_completed_message_{pid}"] = False

def _check_project_name_exists(name):
    """Check if project name already exists"""
    from .backend import get_db_collections
    collections = get_db_collections()
    return collections["projects"].find_one({"name": name}) is not None

def _create_project_data(name, client, description, start, due, team):
    """Create project data dictionary"""
    return {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "team": team,
        "template": st.session_state.selected_template or "Custom",
        "levels": st.session_state.custom_levels.copy(),
        "level": st.session_state.level_index,
        "timestamps": st.session_state.level_timestamps.copy(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "created_by": st.session_state.get("username", "unknown"),
    }

def _create_updated_project_data(project, name, client, description, start, due, team):
    """Create updated project data dictionary"""
    return {
        "name": name,
        "client": client,
        "description": description,
        "startDate": start.isoformat(),
        "dueDate": due.isoformat(),
        "team": team,
        "updated_at": datetime.now().isoformat(),
        "created_at": project.get("created_at", datetime.now().isoformat()),
        "levels": project.get("levels", ["Initial", "Invoice", "Payment"]),
        "level": project.get("level", -1),
        "timestamps": project.get("timestamps", {})
    }

def _reset_create_form_state():
    """Reset create form state variables"""
    st.session_state.level_index = -1
    st.session_state.level_timestamps = {}
    st.session_state.custom_levels = []
    st.session_state.selected_template = ""
    st.session_state.view = "dashboard"

def _update_client_counts_after_edit(project, new_client):
    """Update client project counts after editing"""
    # Update new client count
    update_client_project_count(new_client)
    
    # Update old client count if client was changed
    old_client = project.get("client", "")
    if new_client != old_client:
        update_client_project_count(old_client)

def _handle_team_changes(new_team, original_team, project_name):
    """Handle team member changes and return success messages"""
    success_messages = []
    added_users = set(new_team) - set(original_team)
    removed_users = set(original_team) - set(new_team)
    
    if added_users:
        update_users_with_project(list(added_users), project_name)
        success_messages.append(f"Project added to {len(added_users)} new team member(s): {', '.join(added_users)}")
    
    if removed_users:
        remove_project_from_users(list(removed_users), [], project_name)
        success_messages.append(f"Project removed from {len(removed_users)} former team member(s): {', '.join(removed_users)}")
    
    return success_messages

def _display_success_messages(messages):
    """Display success messages"""
    if messages:
        for message in messages:
            st.success(message)
    else:
        st.success("Changes saved to database!")