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

# Navigation
if not st.session_state.authenticated:
    load_page("login")
else:
    with st.sidebar:
        selected = option_menu(
            "Vshesh",
            ["Profile", "Documents", "Log","Logout"],
            icons=["person", "gear", "box-arrow-left","box-arrow-left"],
            menu_icon="cast",
            default_index=0
        )

    if selected == "Logout":
        st.session_state.authenticated = False
        st.rerun()
    else:
        load_page(selected.lower())  # Load 'profile' or 'settings'
