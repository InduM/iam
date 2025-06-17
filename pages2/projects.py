import streamlit as st
from datetime import datetime, date , timedelta
from typing import List
import yagmail
from email.message import EmailMessage

def run():
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
        "projects": [],
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

    # ───── Helpers ─────
    def format_level(i, levels: List[str]):
        try:
            i = int(i)
            return f"Level {i+1} – {str(levels[i])}"
        except Exception:
            return f"Level {i+1}"

    def render_level_checkboxes(prefix, project_id, current_level, timestamps, levels, on_change_fn=None, editable=True):
        for i, label in enumerate(levels):
            key = f"{prefix}_{project_id}_level_{i}_{datetime.now().timestamp()}"
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
                on_change=callback if editable else None
            )

    # ───── Pages ─────
    def show_dashboard():
        st.title("📊 Projects Dashboard")
        st.button("➕ Create New Project", on_click=lambda: st.session_state.update(view="create"))

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
                render_level_checkboxes("view", pid, int(p.get("level", -1)), p.get("timestamps", {}), levels, editable=False)
                # --- Email Reminder ---
                project_name = p.get("name", "Unnamed")
                ## HArdcoding the lead email for now
                #lead_email = st.secrets["project_leads"].get(project_name)
                lead_email = st.secrets["project_leads"].get("Project Alpha")
                invoice_index = p["levels"].index("Invoice") if "Invoice" in p["levels"] else -1
                payment_index = p["levels"].index("Payment") if "Payment" in p["levels"] else -1

                email_key = f"last_email_sent_{pid}"
                if email_key not in st.session_state:
                    st.session_state[email_key] = None

                if (0 <= invoice_index <= current_level) and (payment_index > current_level) and lead_email:
                    now = datetime.now()
                    last_sent = st.session_state[email_key]
                # Send immediately on first Invoice check
                    if not last_sent:
                        if send_invoice_email(lead_email, project_name):
                            st.session_state[email_key] = now
                    if not last_sent or now - last_sent >= timedelta(minutes=1):
                        if send_invoice_email(lead_email, project_name):
                            st.session_state[email_key] = now
            #----------------------------------------------------- 
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
                        st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != pid]
                        st.success("Project deleted.")
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()
                    if col_no.button("❌ No", key=f"no_{pid}"):
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()

    def show_create_form():
        st.title("🛠 Create Project")
        st.session_state.selected_template = st.selectbox("Select Template (optional)", [""] + list(TEMPLATES.keys()))
        name = st.text_input("Project Name")
        client = st.text_input("Client Name")
        description = st.text_area("Project Description")
        start = st.date_input("Start Date")
        due = st.date_input("Due Date")
        team = st.multiselect("Assign Team", TEAM_MEMBERS)

        if st.session_state.selected_template:
            st.markdown(f"Using template: **{st.session_state.selected_template}**")
            levels_from_template = TEMPLATES[st.session_state.selected_template].copy()
    # Remove "Invoice" and "Payment" if present in the template
            for required in ["Invoice", "Payment"]:
                if required in levels_from_template:
                    levels_from_template.remove(required)
            # Enforce them at the end
            st.session_state.custom_levels = levels_from_template + ["Invoice", "Payment"]

        else:
            st.subheader("Customize Progress Levels")
            if not st.session_state.custom_levels:
                st.session_state.custom_levels = ["Initial"]

            # ✅ Enforce Invoice & Payment as final levels
            for required in ["Invoice", "Payment"]:
                if required in st.session_state.custom_levels:
                    st.session_state.custom_levels.remove(required)

            # UI to edit levels before final two
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

            # Ensure final two
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
                    "id": str(len(st.session_state.projects) + 1),
                    "name": name,
                    "client": client,
                    "description": description,
                    "startDate": start.isoformat(),
                    "dueDate": due.isoformat(),
                    "team": team,
                    "template": st.session_state.selected_template or "Custom",
                    "levels": st.session_state.custom_levels.copy(),
                    "level": st.session_state.level_index,
                    "timestamps": st.session_state.level_timestamps.copy()
                }
                st.session_state.projects.append(new_proj)
                st.success("Project created successfully!")
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
            project["level"] = new_index
            project.setdefault("timestamps", {})[str(new_index)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        render_level_checkboxes("edit", pid, int(project["level"]), project.get("timestamps", {}), project["levels"], on_change_edit)

        if st.button("💾 Save Changes"):
            if due <= start:
                st.error("Cannot save: Due date must be later than the start date.")
            elif not name or not client:
                st.error("Name and client are required.")
            else:
                project.update({
                    "name": name,
                    "client": client,
                    "description": description,
                    "startDate": start.isoformat(),
                    "dueDate": due.isoformat(),
                    "team": team
                })
                st.success("Changes saved successfully!")
                st.session_state.view = "dashboard"
                st.rerun()

    # ───── Navigation ─────
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create_form()
    elif st.session_state.view == "edit":
        show_edit_form()
