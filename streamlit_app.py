import streamlit as st
from utils import login_user, is_logged_in

st.set_page_config(page_title="Login", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

if is_logged_in():
    st.switch_page("pages/Profile.py")
st.title("🔐 Login")

with st.form("login_form"):
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    submit = st.form_submit_button("Login")

    if submit:
        if login_user(username, password):
            st.session_state["username"] = username
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid credentials")
