import streamlit as st
# utils.py
def check_login(username, password):
    #return username == "admin" and password == "1234"
    return True

def logout_user():
    st.session_state.clear()
    st.rerun()

def is_logged_in():
    return st.session_state.get("logged_in", False)


def login_user(username, password):
    # Replace this with your auth logic
    #if username == "admin" and password == "1234":
    #   st.session_state["logged_in"] = True
    #    return True
    #return False
    st.session_state["logged_in"] = True
    return True