import streamlit as st
from utils import is_logged_in
from utils import show_sidebar
import pymongo
import base64
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB Atlas
client = pymongo.MongoClient(MONGO_URI)
db = client["user_db"]
collection = db["users"]

st.set_page_config(page_title="Profile", layout="wide")

# Add custom CSS styles
st.markdown(
    """
    <style>
    .sidebar .sidebar-content {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if not is_logged_in():
    st.switch_page("streamlit_app.py")

show_sidebar()
col1, col2, col3 = st.columns(3)
with col1:
    st.title(st.session_state["username"])

# you can create columns to better manage the flow of your page
# this command makes 3 columns of equal width

user_profile = collection.find_one({"username": st.session_state["username"]})
if user_profile:
        with col3:
            st.button("Update profile")
        with col2:
            collection2 = db["documents"]
            user_doc = collection2.find_one({"username": st.session_state["username"]})
            profile_image_data = user_doc.get("profile_image", {}).get("data", None)
            if  profile_image_data:
                # Decode base64 and display image
                image_data = base64.b64decode(profile_image_data)
                st.image(image_data, use_container_width=False, width=200)
            else:
                # Default image if none uploaded
                st.image("images/img_avatar.png", use_container_width=False, width=200)

        st.write(f"**Name:** {user_profile.get('name', 'N/A')}")
        st.write(f"**Email:** {user_profile.get('email', 'N/A')}")
        st.write(f"**Role:** {user_profile.get('role', 'N/A')}")
        st.write(f"**Date of Joining:** {user_profile.get('joiningDate', 'N/A')}")
        st.write(f"**Branch:** {user_profile.get('branch', 'N/A')}")
        st.write(f"**Current Projects:** {user_profile.get('projects', 'N/A')}")
else:
        st.warning("No user found with that username.")

