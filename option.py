import streamlit as st
from streamlit_option_menu import option_menu
import importlib

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

# Dynamic loader
def load_page(module_name):
    module = importlib.import_module(f"pages2.{module_name}")
    module.run()

st.set_page_config(layout="centered")
# Custom CSS for mobile-friendly UI
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Segoe UI', sans-serif;
    }

    .login-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 90vh;
        padding: 1rem;
    }

    .form-title {
        text-align: center;
        margin-bottom: 1.5rem;
        color: #333;
    } 
    </style>
""", unsafe_allow_html=True)

# Navigation
if not st.session_state.authenticated:
    load_page("login")
else:
    st.sidebar.image(
        "https://i0.wp.com/v-shesh.com/wp-content/uploads/2020/09/v-shesh.png?fit=188%2C70&ssl=1",
        use_container_width=True,
    )
    with st.sidebar:
        if st.session_state["role"] == "user":
            selected = option_menu(
                None,
                ["Profile", "Documents", "Log","Logout"],
                icons=["person", "file-earmark-richtext", "file-spreadsheet","box-arrow-right"],
               
                default_index=0
            )
        if st.session_state["role"] == "admin":
            selected = option_menu(
                None,
                ["Profile", "Documents","Log","Users","Projects","Clients","Logout"],
                icons=["person", "file-earmark-richtext", "file-spreadsheet","people","kanban","wallet","box-arrow-right"],
                default_index=0
            )
        if st.session_state["role"] == "manager":
            selected = option_menu(
                None,
                ["Profile", "Documents","Log","Users","Projects","Clients","Logout"],
                icons=["person", "file-earmark-richtext", "file-spreadsheet","people","kanban","wallet","box-arrow-right"],
                default_index=0
            )
    # Detect tab switch and trigger rerun for fresh data
    if "last_selected" not in st.session_state:
        st.session_state.last_selected = selected

    if selected != st.session_state.last_selected:
        st.session_state.last_selected = selected
        st.rerun()

    if selected == "Logout":
        st.session_state.authenticated = False
        st.rerun()
    else:
        load_page(selected.lower())  # Load 'profile' or 'settings'""
