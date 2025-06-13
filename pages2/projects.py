import streamlit as st
from datetime import datetime, date


def run():
    # ───────────── Constants ─────────────
    LEVELS = {
        "1": "Planning",
        "2": "Design",
        "3": "Development",
        "4": "Testing",
        "5": "Deployment",
        "6": "Maintenance",
        "7": "Completed"
    }

    TEAM_MEMBERS = ["Alice", "Bob", "Charlie", "Dana", "Eve", "Frank", "Grace", "Hannah"]

    def format_level(lv):
        return f"Level {lv} – {LEVELS.get(str(lv), 'Unknown')}"

    # ───────────── Session State ─────────────
    if "projects" not in st.session_state:
        st.session_state.projects = []

    if "view" not in st.session_state:
        st.session_state.view = "dashboard"

    if "new_level" not in st.session_state:
        st.session_state.new_level = 0

    if "new_timestamps" not in st.session_state:
        st.session_state.new_timestamps = {}

    if "edit_project_id" not in st.session_state:
        st.session_state.edit_project_id = None

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = {}

    if "create_pressed" not in st.session_state:
        st.session_state.create_pressed = False

    if "edit_pressed" not in st.session_state:
        st.session_state.edit_pressed = False

    # ───────────── Checkbox Renderer ─────────────
    def render_checkboxes(prefix, project_id, current_level, timestamps, on_change_fn=None, editable=True):
        st.markdown("**Progress Level:**")
        for i in range(1, 8):
            level_id = str(i)
            key = f"{prefix}_{project_id}_level_{i}"
            checked = i <= current_level
            disabled = (
                not editable or
                i > current_level + 1 or
                (i < current_level and i != current_level)
            )

            label = f"Level {i} – {LEVELS[level_id]}"
            if checked and level_id in timestamps:
                label += f" ⏱️ {timestamps[level_id]}"

            def callback(i=i, cl=current_level):
                if i == cl + 1:
                    on_change_fn(i)
                elif i == cl:
                    on_change_fn(i - 1)

            st.checkbox(label,
                        value=checked,
                        key=key,
                        disabled=disabled,
                        on_change=callback if editable else None)

    # ───────────── Dashboard View ─────────────
    def show_dashboard():
        st.title("📊 Projects Dashboard")
        st.button("➕ Create New Project", on_click=lambda: st.session_state.update(view="create"))

        search = st.text_input("🔍 Search by name, client, or team member")
        due_filter = st.date_input("📅 Due before or on", value=None)
        sort_by = st.selectbox("📌 Show projects at level", ["All"] + list(LEVELS.values()))

        projs = st.session_state.projects.copy()

        if search:
            projs = [p for p in projs if search.lower() in p.get("name", "").lower() or
                    search.lower() in p.get("description", "").lower() or
                    search.lower() in p.get("client", "").lower() or
                    any(search.lower() in member.lower() for member in p.get("team", []))]

        if due_filter:
            projs = [p for p in projs if p.get("dueDate") and date.fromisoformat(p["dueDate"]) <= due_filter]

        if sort_by != "All":
            level_code = next(k for k, v in LEVELS.items() if v == sort_by)
            projs = [p for p in projs if p.get("level") == level_code]

        for i, p in enumerate(projs):
            project_id = p.get("id", f"auto_{i}")
            with st.expander(f"{p.get('name', 'Unnamed')} – 👤 {p.get('client', 'Unknown Client')}"):
                st.markdown(f"**Description:** {p.get('description', '-')}")
                st.markdown(f"**Client:** {p.get('client', '-')}")
                st.markdown(f"**Start Date:** {p.get('startDate', '-')}")
                st.markdown(f"**Due Date:** {p.get('dueDate', '-')}")
                st.markdown(f"**Team Assigned:** {', '.join(p.get('team', [])) or '-'}")
                st.markdown(f"**Current Level:** {format_level(p.get('level', '0'))}")

                col1, col2 = st.columns([1, 1])
                if col1.button("📝 Edit", key=f"edit_button_{project_id}"):
                    st.session_state.edit_project_id = project_id
                    st.session_state.view = "edit"
                    st.rerun()

                confirm_key = f"confirm_delete_{project_id}"
                if not st.session_state.confirm_delete.get(confirm_key):
                    if col2.button("🗑️ Delete", key=f"delete_button_{project_id}"):
                        st.session_state.confirm_delete[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("Are you sure you want to delete this project?")
                    if st.button("✅ Yes, Delete", key=f"yes_delete_{project_id}"):
                        st.session_state.projects = [proj for proj in st.session_state.projects if proj["id"] != project_id]
                        st.success(f"Deleted project")
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()
                    if st.button("❌ Cancel", key=f"cancel_delete_{project_id}"):
                        st.session_state.confirm_delete[confirm_key] = False
                        st.rerun()

                render_checkboxes(
                    "view",
                    project_id,
                    int(p.get("level", 0)),
                    p.get("timestamps", {}),
                    editable=False
                )

    # ───────────── Create New Project ─────────────
    def show_create():
        st.title("🛠️ Create New Project")
        st.button("← Back to Dashboard", on_click=lambda: st.session_state.update(view="dashboard"))

        name = st.text_input("Project Name")
        client = st.text_input("Client Name")
        desc = st.text_area("Description")
        start = st.date_input("Start Date")
        due = st.date_input("Due Date")
        team = st.multiselect("Assign Team", TEAM_MEMBERS)

        def on_change_create(new_level):
            st.session_state.new_timestamps[str(new_level)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.new_level = new_level

        render_checkboxes("create", "new", st.session_state.new_level, st.session_state.new_timestamps, on_change_create, editable=True)

        if st.button("Create Project") and not st.session_state.create_pressed:
            st.session_state.create_pressed = True
            if not name or not client:
                st.error("Project name and client are required.")
                st.session_state.create_pressed = False
            else:
                new_proj = {
                    "id": str(len(st.session_state.projects) + 1),
                    "name": name,
                    "client": client,
                    "description": desc,
                    "startDate": start.strftime("%Y-%m-%d"),
                    "dueDate": due.strftime("%Y-%m-%d"),
                    "team": team,
                    "level": str(st.session_state.new_level),
                    "createdAt": datetime.now().isoformat(),
                    "timestamps": st.session_state.new_timestamps.copy()
                }
                st.session_state.projects.append(new_proj)
                st.success(f"✅ Created “{name}” for client {client}")
                st.session_state.new_level = 0
                st.session_state.new_timestamps = {}
                st.session_state.view = "dashboard"
                st.session_state.create_pressed = False
                st.rerun()

    # ───────────── Edit Project ─────────────
    def show_edit():
        pid = st.session_state.edit_project_id
        project = next((p for p in st.session_state.projects if p["id"] == pid), None)

        if not project:
            st.error("Project not found.")
            st.session_state.view = "dashboard"
            return

        st.title("✏️ Edit Project")
        st.button("← Back to Dashboard", on_click=lambda: st.session_state.update(view="dashboard"))

        name = st.text_input("Project Name", value=project.get("name", ""))
        client = st.text_input("Client Name", value=project.get("client", ""))
        desc = st.text_area("Description", value=project.get("description", ""))
        start_str = project.get("startDate")
        start = st.date_input("Start Date", value=date.fromisoformat(start_str) if start_str else date.today())
        due = st.date_input("Due Date", value=date.fromisoformat(project.get("dueDate", date.today().isoformat())))
        team = st.multiselect("Assign Team", TEAM_MEMBERS, default=project.get("team", []))

        def on_change_edit(new_level):
            project.setdefault("timestamps", {})[str(new_level)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            project["level"] = str(new_level)

        render_checkboxes("edit", pid, int(project.get("level", 0)), project.get("timestamps", {}), on_change_edit, editable=True)

        if st.button("Save Changes") and not st.session_state.edit_pressed:
            st.session_state.edit_pressed = True
            project.update({
                "name": name,
                "client": client,
                "description": desc,
                "startDate": start.strftime("%Y-%m-%d"),
                "dueDate": due.strftime("%Y-%m-%d"),
                "team": team
            })
            st.success("Project updated successfully!")
            st.session_state.view = "dashboard"
            st.session_state.edit_pressed = False
            st.rerun()

    # ───────────── Main Controller ─────────────
    if st.session_state.view == "dashboard":
        show_dashboard()
    elif st.session_state.view == "create":
        show_create()
    elif st.session_state.view == "edit":
        show_edit()
