import streamlit as st
import time
from datetime import datetime, date , timedelta
from typing import List
import yagmail
from pymongo import MongoClient
from bson.objectid import ObjectId

def run():
    # ───── MongoDB Connection ─────
    @st.cache_resource
    def init_connection():
        return MongoClient(st.secrets["MONGO_URI"])

    client = init_connection()
    db = client["project_dashboard"]
    projects_collection = db["projects"]

    # ───── Database Operations ─────
    def load_projects_from_db():
        """Load all projects from MongoDB"""
        try:
            projects = list(projects_collection.find())
            for project in projects:
                project["id"] = str(project["_id"])  # Convert ObjectId to string for UI
            return projects
        except Exception as e:
            st.error(f"Error loading projects: {e}")
            return []

    def save_project_to_db(project_data):
        """Save a new project to MongoDB"""
        try:
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
            object_id = ObjectId(project_id)
            result = projects_collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except Exception as e:
            st.error(f"Error deleting project: {e}")
            return False

    def update_project_level_in_db(project_id, new_level, timestamp):
        """Update project level and timestamp in MongoDB"""
        try:
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

    # ───── Email Sender ─────
    def send_invoice_email(to_email, project_name):
        try:
            yag = yagmail.SMTP(user=st.secrets["email"]["from"], password=st.secrets["email"]["password"])
            subject = f"Invoice Stage Reminder – {project_name}"
            body = f"Reminder: Project '{project_name}' has reached Invoice stage."
            yag.send(to=to_email, subject=subject, contents=body)
            return True
        except Exception as e:
            st.error(f"Failed to send email: {e}")
            return False

    # ───── Templates ─────
    TEMPLATES = {
        "Software Project": ["Planning", "Design", "Development", "Testing", "Deployment"],
        "Research Project": ["Hypothesis", "Data Collection", "Analysis", "Publication"],
        "Event Planning": ["Ideation", "Budgeting", "Vendor Selection", "Promotion", "Execution"]
    }

    TEAM_MEMBERS = ["Alice", "Bob", "Charlie", "Dana", "Eve", "Frank", "Grace", "Hannah"]

    # ───── Session State ─────
    for key, default in {
        "view": "dashboard",
        "selected_template": "",
        "custom_levels": [],
        "level_index": -1,
        "level_timestamps": {},
        "edit_project_id": None,
        "confirm_delete": {},
        "create_pressed": False,
        "edit_pressed": False
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Load projects from database on first run or when explicitly refreshed
    if "projects" not in st.session_state or st.session_state.get("refresh_projects", False):
        st.session_state.projects = load_projects_from_db()
        st.session_state.refresh_projects = False

    # ───── Helpers ─────
    def format_level(i, levels: List[str]):
        try:
            i = int(i)
            return f"Level {i+1} – {str(levels[i])}"
        except Exception:
            return f"Level {i+1}"

    def render_level_checkboxes(prefix, project_id, current_level, timestamps, levels, on_change_fn=None, editable=True):
        for i, label in enumerate(levels):
            key = f"{prefix}_{project_id}_level_{i}"
            checked = i <= current_level and current_level >= 0
            disabled = not editable or i > current_level + 1 or (i < current_level and i != current_level)
            display_label = f"{label}"
            if checked and str(i) in timestamps:
                display_label += f" ⏱️ {timestamps[str(i)]}"

            def callback(i=i, cl=current_level):
                if i == cl + 1:
                    on_change_fn(i)
                elif i == cl:
                    on_change_fn(i - 1)

            st.checkbox(
                label=display_label,
                value=checked,
                key=key,
                disabled=disabled,
                on_change=callback if editable and on_change_fn else None
            )

    # ───── Pages ─────
    def show_dashboard():
        st.title("📊 Projects Dashboard")
        st.query_params["_"]=str(int(time.time() // 60)) #Trigger rerun every 60 seconds

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("➕ New Project"):
                st.session_state.view = "create"
                st.rerun()
        with col2:
            if st.button("🔄Refresh"):
                st.session_state.refresh_projects = True
                st.rerun()

        # Responsive search + filters
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

        filtered_projects = st.session_state.projects
        if search_query:
            q = search_query.lower()
            filtered_projects = [p for p in filtered_projects if
                                q in p.get("name", "").lower() or
                                q in p.get("client", "").lower() or
                                any(q in member.lower() for member in p.get("team", []))]

        if filter_template != "All":
            filtered_projects = [p for p in filtered_projects if p.get("template") == filter_template]

        if filter_due:
            filtered_projects = [p for p in filtered_projects if p.get("dueDate") and date.fromisoformat(p["dueDate"]) <= filter_due]

        if filter_level != "All":
            filtered_projects = [
                p for p in filtered_projects
                if p.get("level", -1) >= 0 and
                p.get("levels") and
                p["levels"][p["level"]] == filter_level
            ]

        for i, p in enumerate(filtered_projects):
            pid = p.get("id", f"auto_{i}")
            with st.expander(f"{p.get('name', 'Unnamed')} – Template: {p.get('template', 'N/A')}"):
                st.markdown(f"**Client:** {p.get('client', '-')}")
                st.markdown(f"**Description:** {p.get('description', '-')}")
                st.markdown(f"**Start Date:** {p.get('startDate', '-')}")
                st.markdown(f"**Due Date:** {p.get('dueDate', '-')}")
                st.markdown(f"**Team Assigned:** {', '.join(p.get('team', [])) or '-'}")
                levels = p.get("levels", [])
                current_level = p.get("level", -1)
                st.markdown(f"**Current Level:** {format_level(current_level, levels)}")
                
                # Level checkboxes with database update functionality for dashboard view
                def on_change_dashboard(new_index, proj_id=pid, proj=p):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if update_project_level_in_db(proj_id, new_index, timestamp):
                        # Update local state
                        proj["level"] = new_index
                        if "timestamps" not in proj:
                            proj["timestamps"] = {}
                        proj["timestamps"][str(new_index)] = timestamp
                        # Store success message to show after rerun
                        st.session_state[f"level_update_success_{proj_id}"] = True
                
                # Check for success message from previous update
                if st.session_state.get(f"level_update_success_{pid}", False):
                    st.success("Project level updated!")
                    st.session_state[f"level_update_success_{pid}"] = False
                
                render_level_checkboxes("view", pid, int(p.get("level", -1)), p.get("timestamps", {}), levels, on_change_dashboard, editable=True)
                
                # --- Email Reminder ---
                project_name = p.get("name", "Unnamed")
                lead_email = st.secrets["project_leads"].get("Project Alpha")
                invoice_index = p["levels"].index("Invoice") if "Invoice" in p["levels"] else -1
                payment_index = p["levels"].index("Payment") if "Payment" in p["levels"] else -1

                email_key = f"last_email_sent_{pid}"
                if email_key not in st.session_state:
                    st.session_state[email_key] = None

                if (0 <= invoice_index <= current_level) and (payment_index > current_level) and lead_email:
                    now = datetime.now()
                    last_sent = st.session_state[email_key]
                    if not last_sent:
                        if send_invoice_email(lead_email, project_name):
                            st.session_state[email_key] = now
                    if not last_sent or now - last_sent >= timedelta(minutes=1):
                        if send_invoice_email(lead_email, project_name):
                            st.session_state[email_key] = now
            
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
                        if delete_project_from_db(pid):
                            st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != pid]
                            st.success("Project deleted from database.")
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()
                    if col_no.button("❌ No", key=f"no_{pid}"):
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()

    def show_create_form():
        st.title("🛠 Create Project")
        template_options = ["Custom Template"] + list(TEMPLATES.keys())
        selected = st.selectbox("Select Template (optional)", template_options)

        if selected != "Custom Template":
            st.session_state.selected_template = selected
        else:
            st.session_state.selected_template = ""

        name = st.text_input("Project Name")
        client = st.text_input("Client Name")
        description = st.text_area("Project Description")
        start = st.date_input("Start Date")
        due = st.date_input("Due Date")
        team = st.multiselect("Assign Team", TEAM_MEMBERS)

        if st.session_state.selected_template:
            st.markdown(f"Using template: **{st.session_state.selected_template}**")
            levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
            for required in ["Invoice", "Payment"]:
                if required in levels_from_template:
                    levels_from_template.remove(required)
            st.session_state.custom_levels = levels_from_template + ["Invoice", "Payment"]

        else:
            st.subheader("Customize Progress Levels")
            if not st.session_state.custom_levels:
                st.session_state.custom_levels = ["Initial"]

            for required in ["Invoice", "Payment"]:
                if required in st.session_state.custom_levels:
                    st.session_state.custom_levels.remove(required)

            editable_levels = st.session_state.custom_levels.copy()
            for i in range(len(editable_levels)):
                cols = st.columns([5, 1])
                editable_levels[i] = cols[0].text_input(f"Level {i+1}", value=editable_levels[i], key=f"level_{i}")
                if len(editable_levels) > 1 and cols[1].button("➖", key=f"remove_{i}"):
                    editable_levels.pop(i)
                    st.session_state.custom_levels = editable_levels
                    st.rerun()

            st.session_state.custom_levels = editable_levels

            if st.button("➕ Add Level"):
                st.session_state.custom_levels.append(f"New Level {len(st.session_state.custom_levels) + 1}")
                st.rerun()

            st.session_state.custom_levels += ["Invoice", "Payment"]

        st.subheader("Progress")
        level_index = st.session_state.get("level_index", -1)
        level_timestamps = st.session_state.get("level_timestamps", {})
        def on_change_create(new_index):
            st.session_state.level_index = new_index
            st.session_state.level_timestamps[str(new_index)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        render_level_checkboxes("create", "new", level_index, level_timestamps, st.session_state.custom_levels, on_change_create)

        if st.button("✅ Create Project"):
            if due <= start:
                st.error("Cannot submit: Due date must be later than the start date.")
            elif not name or not client:
                st.error("Name and client are required.")
            else:
                new_proj = {
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
                    "updated_at": datetime.now().isoformat()
                }
                
                project_id = save_project_to_db(new_proj)
                if project_id:
                    new_proj["id"] = project_id
                    st.session_state.projects.append(new_proj)
                    st.success("Project created and saved to database!")
                    # Reset form state
                    st.session_state.level_index = -1
                    st.session_state.level_timestamps = {}
                    st.session_state.custom_levels = []
                    st.session_state.selected_template = ""
                    st.session_state.view = "dashboard"
                    st.rerun()

    def show_edit_form():
        st.title("✏ Edit Project")
        pid = st.session_state.edit_project_id
        project = next((p for p in st.session_state.projects if p["id"] == pid), None)

        if not project:
            st.error("Project not found.")
            return

        name = st.text_input("Project Name", value=project["name"])
        client = st.text_input("Client Name", value=project["client"])
        description = st.text_area("Project Description", value=project["description"])
        start = st.date_input("Start Date", value=date.fromisoformat(project["startDate"]))
        due = st.date_input("Due Date", value=date.fromisoformat(project["dueDate"]))
        team = st.multiselect("Assign Team", TEAM_MEMBERS, default=project.get("team", []))

        st.subheader("Progress")
        def on_change_edit(new_index):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            project["level"] = new_index
            project.setdefault("timestamps", {})[str(new_index)] = timestamp
            # Update in database immediately
            if update_project_level_in_db(pid, new_index, timestamp):
                st.session_state[f"edit_level_update_success_{pid}"] = True
        
        # Check for success message from previous level update
        if st.session_state.get(f"edit_level_update_success_{pid}", False):
            st.success("Project level updated!")
            st.session_state[f"edit_level_update_success_{pid}"] = False
            
        render_level_checkboxes("edit", pid, int(project["level"]), project.get("timestamps", {}), project["levels"], on_change_edit)

        if st.button("💾 Save Changes"):
            if due <= start:
                st.error("Cannot save: Due date must be later than the start date.")
            elif not name or not client:
                st.error("Name and client are required.")
            else:
                updated_project = {
                    "name": name,
                    "client": client,
                    "description": description,
                    "startDate": start.isoformat(),
                    "dueDate": due.isoformat(),
                    "team": team,
                    "updated_at": datetime.now().isoformat()
                }
                
                if update_project_in_db(pid, updated_project):
                    project.update(updated_project)
                    st.success("Changes saved to database!")
                    st.session_state.view = "dashboard"
                    st.rerun()

    # ───── Navigation ─────
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()