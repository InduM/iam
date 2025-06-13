import streamlit as st
import bcrypt
import re

# Initialize session state
if "users" not in st.session_state:
    st.session_state["users"] = {}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "page" not in st.session_state:
    st.session_state["page"] = "signin"

# Branch list
branches = ["Chennai", "Bangalore", "Hyderabad", "Pune"]

# Utility functions
def is_valid_email(email):
    return email.endswith("@v-shesh.com")

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def switch_page(page_name):
    st.session_state["page"] = page_name

# Sign Up page
def signup():
    st.title("Sign Up")

    name = st.text_input("Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    branch = st.selectbox("Branch", branches)

    if st.button("Create Account"):
        if not all([name, email, password, branch]):
            st.warning("Please fill all fields.")
        elif not is_valid_email(email):
            st.error("Email must be a valid @v-shesh.com address.")
        elif email in st.session_state["users"]:
            st.error("Email already registered.")
        else:
            hashed_pw = hash_password(password)
            st.session_state["users"][email] = {
                "name": name,
                "password": hashed_pw,
                "branch": branch
            }
            st.success("Account created successfully! Please sign in.")
            switch_page("signin")

    st.button("Go to Sign In", on_click=lambda: switch_page("signin"))

# Sign In page
def signin():
    st.title("Sign In")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = st.session_state["users"].get(email)
        if user and check_password(password, user["password"]):
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = email
            switch_page("dashboard")
        else:
            st.error("Invalid email or password.")

    st.button("Go to Sign Up", on_click=lambda: switch_page("signup"))

# Dashboard page
def dashboard():
    st.title("Welcome!")

    email = st.session_state.get("user_email", "")
    user = st.session_state["users"].get(email, {})

    st.markdown(f"**Name:** {user.get('name')}")
    st.markdown(f"**Email:** {email}")
    st.markdown(f"**Branch:** {user.get('branch')}")

    if st.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["user_email"] = None
        switch_page("signin")

# Routing logic
if st.session_state["page"] == "signin":
    signin()
elif st.session_state["page"] == "signup":
    signup()
elif st.session_state["page"] == "dashboard":
    if st.session_state["logged_in"]:
        dashboard()
    else:
        st.warning("Please log in first.")
        switch_page("signin")
