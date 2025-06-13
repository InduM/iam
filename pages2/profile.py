import streamlit as st
from utils import is_logged_in
import pymongo
import base64
import os

def run():
    
    # Load MongoDB URI from Streamlit secrets
    MONGO_URI = st.secrets["MONGO_URI"]

    # Connect to MongoDB Atlas
    client = pymongo.MongoClient(MONGO_URI)
    db = client["user_db"]
    collection = db["users"]

    def update_user_profile(username, profile_data):
        collection.update_one({"username": username}, {"$set": profile_data}, upsert=True)

    def edit_profile(profile):
        st.subheader("✏️ Edit Profile")
        name = st.text_input("Name", value=profile["name"])
        email = st.text_input("Email", value=profile["email"])
        branch = st.text_input("Branch", value=profile["branch"])
        #profile_image_file = st.file_uploader("Upload Profile Picture", type=["jpg", "jpeg", "png"])

        if st.button("Save Changes"):
            updated = {
                "username": profile["username"],
                "name": name,
                "email": email,
                "branch": branch,
            }
    #        if profile_image_file:
    #           updated["profile_image"] = base64.b64encode(profile_image_file.read()).decode("utf-8")

            update_user_profile(profile["username"], updated)
            st.success("✅ Profile updated!")
            st.session_state.edit_mode = False
            st.rerun()


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


    def get_user_profile(username):
        profile = collection.find_one({"username": username})
        if profile:
            return profile
        else:
            default = {
                "username": username,
                "name": username,
                "email": f"{username}@example.com",
                "branch": "",
            }
            collection.insert_one(default)
            return default



    def display_profile(user_profile):
        if user_profile:
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
                        #image_path = os.path.join(os.path.dirname(__file__), "images", "img_avatar.png")
                        #print("IMAGE PATH!!!!", image_path)
                        user_doc = collection2.find_one({"username": "admin"}) # change it to default user later
                        profile_image_data = user_doc.get("profile_image", {}).get("data", None)
                        image_data = base64.b64decode(profile_image_data)
                        st.image(image_data, use_container_width=False, width=200)

                st.write(f"**Name:** {user_profile.get('name', 'N/A')}")
                st.write(f"**Email:** {user_profile.get('email', 'N/A')}")
                st.write(f"**Role:** {user_profile.get('role', 'N/A')}")
                st.write(f"**Date of Joining:** {user_profile.get('joiningDate', 'N/A')}")
                st.write(f"**Branch:** {user_profile.get('branch', 'N/A')}")
                st.write(f"**Current Projects:** {user_profile.get('projects', 'N/A')}")
        else:
                st.warning("No user found with that username.")


    if not is_logged_in():
        st.switch_page("option.py")

    col1, col2, col3 = st.columns(3)
    user_profile = get_user_profile(st.session_state["username"])

    if st.session_state.edit_mode:
        edit_profile(user_profile)
    else:
        display_profile(user_profile)
        if st.button("Update Profile"):
            st.session_state.edit_mode = True
            st.rerun()
