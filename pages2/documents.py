import streamlit as st
import pymongo
import base64
from PIL import Image
import io
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
    
    if role == "admin":
            st.subheader(f"Uploaded Documents for {selected_user}")
            if uploaded_profile:
                st.markdown("**Profile Image:**")
                image_data = base64.b64decode(uploaded_profile["profile_image"]["data"])
                st.image(image_data, caption=uploaded_profile["profile_image"]["filename"], width=256)

            if uploaded_aadhar:
                st.markdown("**Aadhar Document:**")
                st.download_button(
                    label="Download Aadhar",
                    data=uploaded_aadhar["aadhar"]["data"],
                    file_name=uploaded_aadhar["aadhar"]["filename"],
                    mime=uploaded_aadhar["aadhar"]["type"]
                )

            if uploaded_pan:
                st.markdown("**PAN Document:**")
                st.download_button(
                    label="Download PAN",
                    data=uploaded_pan["pan"]["data"],
                    file_name=uploaded_pan["pan"]["filename"],
                    mime=uploaded_pan["pan"]["type"]
                )

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
        if not uploaded_profile and profile_image is not None:
            image = Image.open(profile_image)
            image = image.convert("RGB")
            image = image.resize((256, 256))
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            image_bytes = buffered.getvalue()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            profile_data["profile_image"] = {
                "filename": profile_image.name,
                "data": image_b64,
                "type": "image/jpeg"
            }

        if not uploaded_aadhar and aadhar_file is not None:
                aadhar_bytes = aadhar_file.read()
                aadhar_b64 = base64.b64encode(aadhar_bytes).decode("utf-8")
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
            st.rerun()
        else:
            st.warning("Please upload at least one document.")


      