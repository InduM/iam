import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Add New Project", layout="centered")

st.title("➕ Add New Project")
EMPLOYEES = ["Alice", "Bob", "Charlie", "David", "Eva"]
LOCATIONS = ["San Francisco", "New York", "Remote", "London", "Bangalore"]



with st.form("new_project_form"):
    title = st.text_input("Project Title")
    desc = st.text_area("Description")
    start_date = st.date_input("Start Date", value=datetime.today())
    submit = st.form_submit_button("Add Project")

    if submit:
        st.session_state.projects["Ongoing"].append({
            "Title": title,
            "Description": desc,
            "Start Date": start_date
        })
        st.success("Project added successfully!")
        st.switch_page("Home.py")
