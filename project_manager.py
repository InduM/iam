import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Project Manager", layout="centered")

# ---------- Styling ----------
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            max-width: 800px;
            margin: auto;
        }
        label[data-testid="stCheckboxLabel"] > div {
            font-size: 1rem;
        }
        @media (max-width: 768px) {
            label[data-testid="stCheckboxLabel"] > div {
                font-size: 0.95rem;
            }
        }
    </style>
""", unsafe_allow_html=True)

# ---------- Levels ----------
levels = [
    "Level 1 - Initiation",
    "Level 2 - Planning",
    "Level 3 - Design",
    "Level 4 - Development",
    "Level 5 - Testing",
    "Level 6 - Deployment",
    "Level 7 - Maintenance"
]

# ---------- Init State ----------
if "all_projects" not in st.session_state:
    st.session_state.all_projects = []

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

# ---------- Nav Buttons ----------
with st.sidebar:
    if st.button("📊 View Dashboard"):
        st.session_state.active_page = "dashboard"
        st.session_state.editing_index = None
    if st.button("➕ Create New Project"):
        st.session_state.active_page = "create"
        st.session_state.editing_index = None

# ---------- Helper ----------
def init_project_data(existing=None):
    if existing:
        return {
            "name": existing["name"],
            "client": existing["client"],
            "description": existing["description"],
            "levels": existing["levels"].copy(),
            "checked_levels": existing["checked_levels"].copy(),
            "last_updated": existing["last_updated"]
        }
    else:
        return {
            "name": "",
            "client": "",
            "description": "",
            "levels": {level: None for level in levels},
            "checked_levels": {level: False for level in levels},
            "last_updated": None
        }

# =============== CREATE/EDIT PAGE ===============
if st.session_state.active_page == "create":
    is_editing = st.session_state.editing_index is not None
    st.title("✏️ Edit Project" if is_editing else "🆕 Create New Project")

    if "project_data" not in st.session_state or not is_editing:
        existing = st.session_state.all_projects[st.session_state.editing_index] if is_editing else None
        st.session_state.project_data = init_project_data(existing)

    # Input Fields
    st.text_input("Project Name", key="project_name", value=st.session_state.project_data["name"])
    st.text_input("Client Name", key="client_name", value=st.session_state.project_data["client"])
    st.text_area("Project Description", height=100, key="project_description", value=st.session_state.project_data["description"])

    st.subheader("📈 Track Progress")
    last_checked_index = -1
    for i, level in enumerate(levels):
        if st.session_state.project_data["checked_levels"][level]:
            last_checked_index = i

    for i, level in enumerate(levels):
        prev_checked = st.session_state.project_data["checked_levels"][level]
        timestamp = st.session_state.project_data["levels"][level]

        can_check = (i == 0 or st.session_state.project_data["checked_levels"][levels[i - 1]])
        can_uncheck = (i == last_checked_index)

        label = f"{level}"
        if timestamp:
            label += f"  🕒 *({timestamp})*"

        disabled = False
        if not can_check and not prev_checked:
            disabled = True
        if prev_checked and not can_uncheck:
            disabled = True

        checked = st.checkbox(label, value=prev_checked, key=f"{level}_box", disabled=disabled)

        if checked and not prev_checked:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.project_data["levels"][level] = now
            st.session_state.project_data["checked_levels"][level] = True
            st.session_state.project_data["last_updated"] = now
            st.rerun()

        elif not checked and prev_checked:
            st.warning(f"You unchecked **{level}**. Timestamp removed.")
            st.session_state.project_data["levels"][level] = None
            st.session_state.project_data["checked_levels"][level] = False
            st.session_state.project_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

    # Save
    if st.button("💾 Save Project"):
        st.session_state.project_data["name"] = st.session_state.project_name
        st.session_state.project_data["client"] = st.session_state.client_name
        st.session_state.project_data["description"] = st.session_state.project_description

        if is_editing:
            st.session_state.all_projects[st.session_state.editing_index] = st.session_state.project_data.copy()
            st.success("✅ Project updated.")
        else:
            names = [p['name'] for p in st.session_state.all_projects]
            if st.session_state.project_data["name"] in names:
                st.warning("⚠️ Project with this name already exists.")
            else:
                st.session_state.all_projects.append(st.session_state.project_data.copy())
                st.success("✅ Project created.")
        st.session_state.active_page = "dashboard"

# =============== DASHBOARD PAGE ===============
elif st.session_state.active_page == "dashboard":
    st.title("📊 Project Dashboard")

    # Filters
    st.subheader("🔍 Filter & Sort")
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Search")
    with col2:
        sort_by = st.selectbox("Sort by", ["Project Name", "Client Name", "Status (Last Level)", "Date Updated"])

    # Filter
    filtered = [p for p in st.session_state.all_projects if
                search_query.lower() in p["name"].lower() or
                search_query.lower() in p.get("client", "").lower()]

    # Sort
    if sort_by == "Project Name":
        filtered.sort(key=lambda p: p["name"].lower())
    elif sort_by == "Client Name":
        filtered.sort(key=lambda p: p.get("client", "").lower())
    elif sort_by == "Status (Last Level)":
        def last_index(p):
            for i in reversed(range(len(levels))):
                if p["checked_levels"][levels[i]]:
                    return i
            return -1
        filtered.sort(key=last_index, reverse=True)
    elif sort_by == "Date Updated":
        filtered.sort(key=lambda p: p["last_updated"] or "", reverse=True)

    if not filtered:
        st.info("No matching projects.")
    else:
        for idx, project in enumerate(filtered):
            with st.expander(f"📁 {project['name']}"):
                st.write(f"**Client:** {project.get('client', 'N/A')}")
                st.write(f"**Description:** {project['description'] or 'N/A'}")
                st.write(f"**Last Updated:** {project['last_updated'] or 'N/A'}")

                st.markdown("**Progress:**")
                for level, ts in project["levels"].items():
                    st.markdown(f"- {'✅' if ts else '⬜️'} **{level}** {'at ' + ts if ts else ''}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"edit_{idx}"):
                        st.session_state.editing_index = st.session_state.all_projects.index(project)
                        st.session_state.active_page = "create"
                        st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{idx}"):
                        st.session_state.all_projects.remove(project)
                        st.success("🗑️ Project deleted.")
                        st.rerun()
