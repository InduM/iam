import streamlit as st
# utils.py
def check_login(username, password):
    return username == "admin" and password == "1234"

def logout_user():
    st.session_state.clear()
    st.rerun()

def is_logged_in():
    return st.session_state.get("logged_in", False)

def show_sidebar():
    with st.sidebar:
        st.page_link("pages/Profile.py", label="Profile", icon="🏠")
        st.page_link("pages/Log.py", label="Log", icon="👤")
        st.button("🚪 Logout", on_click=logout_user)

def login_user(username, password):
    # Replace this with your auth logic
    if username == "admin" and password == "1234":
        st.session_state["logged_in"] = True
        return True
    return False