import pymongo
import streamlit as st

def get_db():
    MONGO_URI = st.secrets["MONGO_URI"]
    client = pymongo.MongoClient(MONGO_URI)
    return client["user_db"]

def get_user_profile(username):
    db = get_db()
    collection = db["users"]
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

def update_user_profile(username, profile_data):
    db = get_db()
    collection = db["users"]
    collection.update_one({"username": username}, {"$set": profile_data}, upsert=True)

def get_profile_image(username):
    db = get_db()
    collection = db["documents"]
    user_doc = collection.find_one({"username": username})
    if user_doc and "profile_image" in user_doc:
        return user_doc["profile_image"]["data"]
    return None
