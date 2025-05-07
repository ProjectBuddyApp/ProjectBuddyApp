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

def get_all_teams():
    collection = db["team_data"]
    team_names = collection.distinct("team_name")
    return team_names

def get_buddy_information(team_name):
    collection = db["team_data"]
    team_doc = collection.find_one(
    {"team_name": team_name},
    {"_id": 0, "buddy_name": 1, "buddy_email": 1,"buddy_github_username" : 1})
    if team_doc:
        buddy_name = team_doc["buddy_name"]
        buddy_email = team_doc["buddy_email"]
        buddy_github_username = team_doc["buddy_github_username"]
        print(f"Buddy: {buddy_name}, Email: {buddy_email}")
    else:
        print("Team not found.")
    return buddy_name, buddy_email, buddy_github_username


def fetch_file_url(team_name):
    collection = db["team_data"]
    team_doc = collection.find_one(
    {"team_name": team_name},
    {"template_id": 1})
    print(team_doc)
    if team_doc:
        return team_doc["template_id"]
    else:
        print("Template not found")



