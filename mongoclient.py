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
    """
    Get all team names that have vector embeddings.
    This is used for loading vector data at startup.
    """
    collection = db["vector_meta_data"]
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

def save_vector_metadata_to_mongo(team_name, faiss_url, pkl_url):
    """
    Insert or update vector metadata in MongoDB.
    Uses upsert to prevent duplicates.
    
    :param team_name: Name of the team (primary key)
    :param faiss_url: URL to FAISS index file
    :param pkl_url: URL to PKL file
    """
    collection = db["vector_meta_data"]
    vector_meta_data = {
        "team_name": team_name,
        "faiss_url": faiss_url,
        "pkl_url": pkl_url
    }
    result = collection.update_one(
        {"team_name": team_name},
        {"$set": vector_meta_data},
        upsert=True
    )
    if result.upserted_id:
        print(f"Vector metadata for '{team_name}' inserted successfully")
    else:
        print(f"Vector metadata for '{team_name}' updated successfully")


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
    Insert or update a common template (child folder files and epic.md) into MongoDB.
    Uses upsert to prevent duplicates.
    
    :param template_name: Name of the template file (primary key)
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'child/file.md' or 'epic.md')
    :return: Operation result
    """
    collection = db["common-templates"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.update_one(
        {"template_name": template_name},
        {"$set": template_data},
        upsert=True
    )
    if result.upserted_id:
        print(f"Common template '{template_name}' inserted successfully")
    else:
        print(f"Common template '{template_name}' updated successfully")
    return result


def insert_product_template(template_name, ibm_cloud_url, file_path):
    """
    Insert or update a product template into MongoDB.
    Uses upsert to prevent duplicates.
    
    :param template_name: Name of the template file (primary key)
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'product/file.md')
    :return: Operation result
    """
    collection = db["product"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.update_one(
        {"template_name": template_name},
        {"$set": template_data},
        upsert=True
    )
    if result.upserted_id:
        print(f"Product template '{template_name}' inserted successfully")
    else:
        print(f"Product template '{template_name}' updated successfully")
    return result


def insert_team_template(template_name, ibm_cloud_url, file_path):
    """
    Insert or update a team template into MongoDB.
    Uses upsert to prevent duplicates.
    
    :param template_name: Name of the template file (primary key)
    :param ibm_cloud_url: IBM Cloud Object Storage URL
    :param file_path: Path within the bucket (e.g., 'teams/file.md')
    :return: Operation result
    """
    collection = db["teams"]
    template_data = {
        "template_name": template_name,
        "ibm_cloud_url": ibm_cloud_url,
        "file_path": file_path
    }
    result = collection.update_one(
        {"template_name": template_name},
        {"$set": template_data},
        upsert=True
    )
    if result.upserted_id:
        print(f"Team template '{template_name}' inserted successfully")
    else:
        print(f"Team template '{template_name}' updated successfully")
    return result


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


def insert_team_details(team_name, team_type, buddy_name, buddy_email, buddy_github, manager_github, team_lead_github):
    """
    Insert or update team details (buddy, manager, team lead information).
    
    :param team_name: Name of the team (without .md extension)
    :param team_type: Type of team ('product' or 'teams')
    :param buddy_name: Name of the buddy
    :param buddy_email: Email of the buddy
    :param buddy_github: GitHub username of the buddy
    :param manager_github: GitHub username of the manager
    :param team_lead_github: GitHub username of the team lead
    :return: Result of the operation
    """
    from datetime import datetime
    
    collection = db["team_details"]
    team_details = {
        "team_name": team_name,
        "team_type": team_type,
        "buddy_name": buddy_name,
        "buddy_email": buddy_email,
        "buddy_github": buddy_github,
        "manager_github": manager_github,
        "team_lead_github": team_lead_github,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Use upsert to insert or update
    result = collection.update_one(
        {"team_name": team_name, "team_type": team_type},
        {"$set": team_details, "$setOnInsert": {"created_at": datetime.utcnow().isoformat()}},
        upsert=True
    )
    
    if result.upserted_id:
        print(f"Team details for '{team_name}' inserted successfully")
    else:
        print(f"Team details for '{team_name}' updated successfully")
    
    return result


def get_team_details(team_name, team_type):
    """
    Get team details by team name and type.
    
    :param team_name: Name of the team
    :param team_type: Type of team ('product' or 'teams')
    :return: Team details dictionary or None
    """
    collection = db["team_details"]
    team_details = collection.find_one(
        {"team_name": team_name, "team_type": team_type},
        {"_id": 0}
    )
    return team_details


def get_all_team_names_from_templates():
    """
    Get all team names from product and teams collections (without .md extension).
    
    :return: Dictionary with 'product' and 'teams' lists
    """
    product_collection = db["product"]
    teams_collection = db["teams"]
    
    # Get product team names
    product_templates = product_collection.find({}, {"template_name": 1, "_id": 0})
    product_names = [t["template_name"].replace(".md", "") for t in product_templates if t.get("template_name")]
    
    # Get team names
    team_templates = teams_collection.find({}, {"template_name": 1, "_id": 0})
    team_names = [t["template_name"].replace(".md", "") for t in team_templates if t.get("template_name")]
    
    return {
        "product": sorted(product_names),
        "teams": sorted(team_names)
    }
def get_all_teams_from_team_details():
    """
    Get all unique team names from team_details collection.
    
    :return: List of team names
    """
    collection = db["team_details"]
    team_names = collection.distinct("team_name")
    return sorted(team_names)


def insert_new_joiner(joinee_name, joinee_email, team_name, buddy_email, buddy_name, github_issues=None):
    """
    Insert or update a new joiner's information in MongoDB.
    Uses upsert to prevent duplicates based on joinee_email.
    
    :param joinee_name: Name of the new joiner
    :param joinee_email: Email of the new joiner (unique key)
    :param team_name: Team name
    :param buddy_email: Email of assigned buddy
    :param buddy_name: Name of assigned buddy
    :param github_issues: List of GitHub issue URLs (optional)
    :return: Upserted document ID or modified count
    """
    from datetime import datetime
    
    collection = db["new_joiners"]
    joiner_data = {
        "joinee_name": joinee_name,
        "joinee_email": joinee_email,
        "team_name": team_name,
        "buddy_email": buddy_email,
        "buddy_name": buddy_name,
        "github_issues": github_issues or [],
        "status": "Active",
        "last_updated": datetime.utcnow().isoformat()
    }
    
    # Use upsert to insert or update
    result = collection.update_one(
        {"joinee_email": joinee_email},
        {"$set": joiner_data, "$setOnInsert": {"joined_date": datetime.utcnow().isoformat()}},
        upsert=True
    )
    
    if result.upserted_id:
        print(f"New joiner '{joinee_name}' ({joinee_email}) added successfully")
    else:
        print(f"New joiner '{joinee_name}' ({joinee_email}) updated successfully")
    
    return str(result.upserted_id) if result.upserted_id else "updated"


def get_joiners_by_buddy_email(buddy_email):
    """
    Get all joiners assigned to a specific buddy.
    
    :param buddy_email: Email of the buddy
    :return: List of joiner documents
    """
    collection = db["new_joiners"]
    joiners = list(collection.find(
        {"buddy_email": buddy_email},
        {"_id": 0}
    ).sort("joined_date", -1))
    return joiners


def update_joiner_github_issues(joinee_email, github_issues):
    """
    Update GitHub issues for a joiner.
    
    :param joinee_email: Email of the joiner
    :param github_issues: List of GitHub issue URLs
    :return: True if successful
    """
    from datetime import datetime
    
    collection = db["new_joiners"]
    result = collection.update_one(
        {"joinee_email": joinee_email},
        {
            "$set": {
                "github_issues": github_issues,
                "last_updated": datetime.utcnow().isoformat()
            }
        }
    )
    
    return result.modified_count > 0


def get_joiner_by_email(joinee_email):
    """
    Get joiner information by email.
    
    :param joinee_email: Email of the joiner
    :return: Joiner document or None
    """
    collection = db["new_joiners"]
    joiner = collection.find_one(
        {"joinee_email": joinee_email},
        {"_id": 0}
    )
    return joiner




