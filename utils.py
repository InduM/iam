import streamlit as st
from pymongo import MongoClient
import certifi

# utils.py
def check_login(username, password):
    MONGO_URI = st.secrets["MONGO_URI"]  # Store securely in .streamlit/secrets.toml
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["user_db"]
    users_col = db["users"]
    user = users_col.find_one({"username": username})
    if user and user["password"] == password:
            st.session_state["role"] = user["role"]
            return True
    else:
            return False

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