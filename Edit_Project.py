import streamlit as st

st.set_page_config(page_title="Edit Project", layout="centered")

if "edit_index" not in st.session_state or "edit_project_type" not in st.session_state:
    st.error("No project selected to edit.")
    st.stop()

index = st.session_state.edit_index
ptype = st.session_state.edit_project_type
project = st.session_state.projects[ptype][index]

st.title("✏️ Edit Project")

with st.form("edit_project_form"):
    title = st.text_input("Project Title", value=project["Title"])
    desc = st.text_area("Description", value=project["Description"])
    date = st.date_input("Start Date", value=project["Start Date"])

    submitted = st.form_submit_button("Update Project")
    if submitted:
        project["Title"] = title
        project["Description"] = desc
        project["Start Date"] = date
        st.success("Project updated successfully!")
        st.switch_page("Home.py")
