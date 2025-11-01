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

def save_vector_metadata_to_mongo(team_name,faiss_url,pkl_url):
    collection = db["vector_meta_data"]
    vector_meta_data = {
        "team_name" : team_name,
        "faiss_url" : faiss_url,
        "pkl_url" : pkl_url
    }
    result = collection.insert_one(vector_meta_data)
    print("data has been inserted successfully in vector_meta_data")


def fetch_vector_urls(team_name):
    collection = db["vector_meta_data"]
    vector_urls = collection.find_one(
    {"team_name": team_name},
    {"faiss_url": 1,"pkl_url": 2})
    print(vector_urls)
    if vector_urls:
        return vector_urls["faiss_url"],vector_urls["pkl_url"]
    else:
        raise FileNotFoundError("urls not found in mongodb")


def find_buddy_by_email(buddy_email):
    """
    Find a buddy by their email address.
    
    :param buddy_email: The email address of the buddy to find
    :return: The buddy's information as a dictionary, or None if not found
    """
    collection = db["team_data"]
    buddy_doc = collection.find_one(
        {"buddy_email": buddy_email},
        {"_id": 0}  # Exclude the MongoDB _id field
    )
    
    if buddy_doc:
        print(f"Found buddy: {buddy_doc['buddy_name']}")
        return buddy_doc
    else:
        print(f"No buddy found with email: {buddy_email}")
        return None

def update_buddy_info(buddy_email, update_data):
    """
    Update a buddy's information in the database.
    
    :param buddy_email: The email address of the buddy to update
    :param update_data: Dictionary containing the fields to update and their new values
    :return: True if successful, False otherwise
    """
    collection = db["team_data"]
    result = collection.update_one(
        {"buddy_email": buddy_email},
        {"$set": update_data}
    )
    
    if result.modified_count > 0:
        print(f"Successfully updated buddy information for {buddy_email}")
        return True
    else:
        print(f"Failed to update buddy information for {buddy_email}")
        return False



def insert_common_template(template_name, ibm_cloud_url, file_path):
    """
    Insert a common template (child folder files and epic.md) into MongoDB.
    
    :param template_name: Name of the template file
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'child/file.md' or 'epic.md')
    :return: Inserted document ID
    """
    collection = db["common-templates"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.insert_one(template_data)
    print(f"Common template '{template_name}' inserted successfully")
    return str(result.inserted_id)


def insert_product_template(template_name, ibm_cloud_url, file_path):
    """
    Insert a product template into MongoDB.
    
    :param template_name: Name of the template file
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'product/file.md')
    :return: Inserted document ID
    """
    collection = db["product"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.insert_one(template_data)
    print(f"Product template '{template_name}' inserted successfully")
    return str(result.inserted_id)


def insert_team_template(template_name, ibm_cloud_url, file_path):
    """
    Insert a team template into MongoDB.
    
    :param template_name: Name of the template file
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'teams/file.md')
    :return: Inserted document ID
    """
    collection = db["teams"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.insert_one(template_data)
    print(f"Team template '{template_name}' inserted successfully")
    return str(result.inserted_id)


def get_all_common_templates():
    """Get all common templates from MongoDB."""
    collection = db["common-templates"]
    return list(collection.find({}, {"_id": 0}))


def get_all_product_templates():
    """Get all product templates from MongoDB."""
    collection = db["product"]
    return list(collection.find({}, {"_id": 0}))


def get_all_team_templates():
    """Get all team templates from MongoDB."""
    collection = db["teams"]
    return list(collection.find({}, {"_id": 0}))
