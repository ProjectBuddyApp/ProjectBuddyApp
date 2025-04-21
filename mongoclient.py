from pymongo import MongoClient
import os

# Connect to MongoDB (use your own URI)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)

# Use a database and collection
db = client["ProjectBuddy"]

def insert_team_data(team_name,buddy_name,buddy_email,template_id,buddy_github_username):
    collection = db["team_data"]
    team_data = {
        "team_name" : team_name,
        "buddy_name" : buddy_name,
        "buddy_email" : buddy_email,
        "template_id" : template_id,
        "buddy_github_username" : buddy_github_username
    }
    result = collection.insert_one(team_data)
    print("data has been inserted successfully in team data")
