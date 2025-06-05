# login.py
import streamlit as st
from utils import check_login

#def login():
def run():
    st.title("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if check_login(username, password):
            st.session_state["logged_in"] = True
            st.session_state.authenticated = True 
            st.session_state["username"] = username
            st.success("Logged in successfully")
            st.rerun()
        else:
            st.error("Invalid username or password")
