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

st.markdown("""
    <style>
    /* Mobile font and layout tweaks */
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem 0.5rem;
        }
        .element-container {
            margin-bottom: 1rem !important;
        }
        input, textarea, select {
            font-size: 16px !important;
        }
        label {
            font-size: 15px !important;
        }
    }
    
    /* Ensure scroll containers on mobile work well */
    .scroll-container {
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 10px;
        border: 1px solid #ddd;
    }

    .block-container {
        min-width: 1100px;
        display: inline-block;
    }

    /* Prevent layout issues with checkboxes on small screens */
    .stCheckbox > div {
        padding-top: 5px;
    }
    </style>
""", unsafe_allow_html=True)


# Navigation
if not st.session_state.authenticated:
    load_page("login")
else:
    with st.sidebar:
        selected = option_menu(
            "Vshesh",
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
