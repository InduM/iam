import streamlit as st
from pymongo import MongoClient
import certifi
import bcrypt

# utils.py
def check_login(username, password):
    MONGO_URI = st.secrets["MONGO_URI"]  # Store securely in .streamlit/secrets.toml
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["user_db"]
    users_col = db["users"]
    user = users_col.find_one({"username": username})
    if user and user["password"] == password:
            st.session_state["role"] = user["role"]
            st.session_state["username"] = user["username"]
            return True
    else:
            return False

def logout_user():
    st.session_state.clear()
    st.rerun()

def is_logged_in():
    return st.session_state.get("logged_in", False)

# Utility functions
def is_valid_email(email):
    return email.endswith("@v-shesh.com")

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)
