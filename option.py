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

    .login-box {
        background: #ffffff;
        border-radius: 16px;
        max-width: 350px;
        width: 100%;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    .stTextInput > div > div > input,
    .stTextInput input {
        text-align: center;
        font-size: 16px;
    }

    @media (max-width: 600px) {
        .login-box {
            padding: 1.5rem;
        }
    }

    .form-title {
        text-align: center;
        margin-bottom: 1.5rem;
        color: #333;
    }

    .btn-login {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)
# Navigation
if not st.session_state.authenticated:
    load_page("login")
else:
    with st.sidebar:
        selected = option_menu(
            "v-shesh",
            ["Profile", "Documents", "Log","Logout"],
            icons=["person", "gear", "box-arrow-left","box-arrow-right"],
            menu_icon="cast",
            default_index=0
        )

    if selected == "Logout":
        st.session_state.authenticated = False
        st.rerun()
    else:
        load_page(selected.lower())  # Load 'profile' or 'settings'
