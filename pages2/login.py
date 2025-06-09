# login.py
import streamlit as st
from utils import check_login

#def login():
def run():

    st.markdown("""
    <style>
    .centered {
        align-items: center;
        padding: 0 1rem;
    }
    @media (max-width: 600px) {
        .login-box {
            padding: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="centered">', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.title("Login")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")

        if login_btn:
            if check_login(username, password):
                st.session_state["logged_in"] = True
                st.session_state.authenticated = True 
                st.session_state["username"] = username
                st.success("Logged in successfully")
                st.rerun()
            else:
                st.error("Invalid username or password")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
