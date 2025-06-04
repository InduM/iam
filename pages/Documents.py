import streamlit as st
import pymongo
import base64
from dotenv import load_dotenv
import os
from utils import is_logged_in
from utils import show_sidebar

if not is_logged_in():
    st.switch_page("streamlit_app.py")

show_sidebar()


# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB Atlas
client = pymongo.MongoClient(MONGO_URI)
db = client["user_db"]
collection = db["documents"]

st.title("Documents Upload")
username = st.session_state["username"]

user_exists = collection.find_one({"username":username})

if username not in user_exists.values():
     collection.insertOne({"username":username})
     

uploaded_profile =  collection.find_one({ "username":username, 
    "profile_image":{"$exists":True}})
uploaded_aadhar =  collection.find_one({ "username":username, 
    "aadhar":{"$exists":True}})
uploaded_pan = collection.find_one({ "username":username, 
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

if submit:
    profile_data ={}
    if not uploaded_profile:
            image_bytes = profile_image.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            profile_data.update({"profile_image": {
                "filename": profile_image.name,
                "data": image_b64,
                "type": profile_image.type}})
    if not uploaded_aadhar:
            aadhar_bytes = aadhar_file.read()
            resume_b64 = base64.b64encode(aadhar_bytes).decode("utf-8")
            profile_data.update({"aadhar": {
                "filename": aadhar_file.name,
                "data": aadhar_bytes,
                "type": aadhar_file.type
            }})
        
    if not uploaded_pan:
            pan_bytes = pan_file.read()
            pan_b64 = base64.b64encode(pan_bytes).decode("utf-8")
            profile_data.update({"pan": {
                "filename": pan_file.name,
                "data": pan_bytes,
                "type": pan_file.type
            }})

    myquery = { "username": st.session_state["username"] }
    newvalues = {"$set":profile_data}

    collection.update_one(myquery,newvalues)
    st.success("✅ Documents uploaded successfully!")

        