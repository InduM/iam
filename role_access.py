import streamlit as st

# Dummy user database
users = {
    "alice": {"password": "1234", "role": "employee"},
    "bob": {"password": "5678", "role": "manager"},
    "admin": {"password": "admin", "role": "admin"},
}

# Define dashboards per role
def admin_dashboard(username):
    st.title(f"🔒 Admin Dashboard - {username}")
    st.write("You have full access to all system settings, user management, and analytics.")

def manager_dashboard(username):
    st.title(f"📈 Manager Dashboard - {username}")
    st.write("You can oversee team performance and project updates.")

def employee_dashboard(username):
    st.title(f"👤 Employee Dashboard - {username}")
    st.write("Welcome to your personal workspace and task list.")

# Role dispatch map
role_dashboards = {
    "admin": admin_dashboard,
    "manager": manager_dashboard,
    "employee": employee_dashboard,
}

# Login page
def login():
    st.title("🔐 Login Page")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        user = users.get(username)
        if user and user["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("❌ Invalid username or password.")

# Main app logic
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login()
    else:
        username = st.session_state.username
        role = st.session_state.role
        st.sidebar.success(f"Logged in as: {username} ({role})")

        # Load the role-based dashboard
        dashboard = role_dashboards.get(role)
        if dashboard:
            dashboard(username)
        else:
            st.error("🚫 Unauthorized: Role not recognized.")

        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
