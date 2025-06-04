import streamlit as st
from utils import is_logged_in
from utils import show_sidebar

if not is_logged_in():
    st.switch_page("streamlit_app.py")

show_sidebar()
st.title("Log Page")
st.write("Here's how you can reach us.")
