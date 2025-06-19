import streamlit as st
import pymongo
import base64
from dotenv import load_dotenv
import os
from utils import is_logged_in

def run():
    if not is_logged_in():
        st.switch_page("option.py")

    # Load environment variables
    MONGO_URI = st.secrets["MONGO_URI"]

    # Connect to MongoDB Atlas
    client = pymongo.MongoClient(MONGO_URI)
    db = client["user_db"]
    collection = db["documents"]

    st.title("Documents Upload")
    username = st.session_state["username"]
    role = st.session_state.get("role", "user")  # Default to 'user' if not set

# Store selected user in session state to preserve across reruns

    if role == "admin":
        usernames = collection.distinct("username")
        
        # Default value for selected_user
        if "selected_user" not in st.session_state:
            st.session_state.selected_user = username

        selected_user = st.selectbox("Select a user to view documents", usernames, index=usernames.index(st.session_state.selected_user))

        # If new selection differs from previous, update and rerun
        if selected_user != st.session_state.selected_user:
            st.session_state.selected_user = selected_user
            st.rerun()
    else:
        selected_user = username

    user_exists = collection.find_one({"username":selected_user})

    if username not in user_exists.values():
        collection.insert_one({"username":selected_user})
      

    uploaded_profile =  collection.find_one({ "username":selected_user, 
        "profile_image":{"$exists":True}})
    uploaded_aadhar =  collection.find_one({ "username":selected_user, 
        "aadhar":{"$exists":True}})
    uploaded_pan = collection.find_one({ "username":selected_user, 
        "pan":{"$exists":True}})


    # Form for user input
    with st.form("profile_form"):
        if not uploaded_profile:
            profile_image = st.file_uploader("Upload Profile Image", type=["png", "jpg", "jpeg"])
        if not uploaded_aadhar:
            aadhar_file = st.file_uploader("Upload Aadhar (PDF/DOCX)", type=["pdf", "docx"])
        if not uploaded_pan:
            pan_file = st.file_uploader("Upload PAN (PDF/DOCX)", type=["pdf", "docx"])

        if uploaded_pan and uploaded_aadhar and uploaded_profile:
            st.write("**All Documents have been uploaded**")
            isDisabled = True
        else:
            isDisabled = False
        submit = st.form_submit_button("Submit",disabled = isDisabled)

    if submit and role != "admin":
        profile_data ={}
        if not uploaded_profile and profile_image is not None:
                image_bytes = profile_image.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                profile_data.update({"profile_image": {
                    "filename": profile_image.name,
                    "data": image_b64,
                    "type": profile_image.type}})
        if not uploaded_aadhar and aadhar_file is not None:
                aadhar_bytes = aadhar_file.read()
                resume_b64 = base64.b64encode(aadhar_bytes).decode("utf-8")
                profile_data.update({"aadhar": {
                    "filename": aadhar_file.name,
                    "data": aadhar_bytes,
                    "type": aadhar_file.type
                }})
            
        if not uploaded_pan and pan_file is not None:
                pan_bytes = pan_file.read()
                pan_b64 = base64.b64encode(pan_bytes).decode("utf-8")
                profile_data.update({"pan": {
                    "filename": pan_file.name,
                    "data": pan_bytes,
                    "type": pan_file.type
                }})

        if profile_data:
            myquery = { "username": selected_user }
            newvalues = {"$set":profile_data}
            collection.update_one(myquery,newvalues)
            st.success("✅ Documents uploaded successfully!")
        else:
            st.warning("Please upload at least one document.")


            