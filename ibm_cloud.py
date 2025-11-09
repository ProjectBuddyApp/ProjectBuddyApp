import requests
from io import BytesIO
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment variables
API_KEY = os.getenv("IBM_CLOUD_API_KEY")
BUCKET_NAME = os.getenv("IBM_CLOUD_BUCKET_NAME")
VECTOR_BUCKET_NAME = os.getenv("IBM_CLOUD_VECTOR_BUCKET_NAME")
TEMPLATES_BUCKET_NAME = os.getenv("IBM_CLOUD_TEMPLATES_BUCKET_NAME")

def get_ibm_iam_access_token() -> str:
    url = "https://iam.test.cloud.ibm.com/oidc/token"
    payload = {
        "apikey": API_KEY,
        "response_type": "cloud_iam",
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"Failed to obtain access token: {response.status_code} {response.text}")
    

def save_vector_data(folder_path,team_name):
    access_token = get_ibm_iam_access_token()
    content_type = "text/plain"
    url = f"https://s3.us-west.cloud-object-storage.test.appdomain.cloud/{VECTOR_BUCKET_NAME}"
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Bearer {access_token}"
    }
    index_faiss_path = os.path.join(folder_path, "index.faiss")
    index_pkl_path = os.path.join(folder_path, "index.pkl")
    index_faiss_content = None
    index_pkl_content = None

    if os.path.isfile(index_faiss_path):
        with open(index_faiss_path, "rb") as f:
            index_faiss_content = f.read()
            print("index.faiss loaded")
    else:
        raise FileNotFoundError("index.faiss not found")

    if os.path.isfile(index_pkl_path):
        with open(index_pkl_path, "rb") as f:
            index_pkl_content = f.read()
            print("index_pkl file loaded")
    else:
        raise FileNotFoundError("index_pkl not found")
    
    faiss_url = f"{url}/{team_name}/index.faiss"
    pkl_url = f"{url}/{team_name}/index.pkl"
    response_faiss = requests.put(faiss_url, data=index_faiss_content, headers=headers)
    response_pkl = requests.put(pkl_url, data=index_pkl_content, headers=headers)
    if response_faiss.status_code in (200, 201) and response_pkl.status_code in (200, 201):
        print("Upload successful vector db.")
        return faiss_url,pkl_url
    else:
        print(f"Upload failed vector db: {response_faiss.status_code}\n{response_faiss.status_code}")


def upload_to_ibm_cos(file_name,data):
    access_token = get_ibm_iam_access_token()
    content_type = "text/plain"
    url = f"https://s3.us-west.cloud-object-storage.test.appdomain.cloud/{BUCKET_NAME}/{file_name}"
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.put(url, data=data, headers=headers)

    if response.status_code in (200, 201):
        print("Upload successful.")
        return url
    else:
        print(f"Upload failed: {response.status_code}\n{response.text}")

def fetch_file_from_cos(file_url):
    access_token = get_ibm_iam_access_token()
    headers = {
    'Authorization': f"Bearer {access_token}",
    'Content-Type': 'application/octet-stream'
    }

    response = requests.get(file_url, headers=headers)
    response.raise_for_status()
    file = BytesIO(response.content)
    file.seek(0)
    return file


def upload_template_to_cos(file_path, data):
    """
    Upload template files to the onboarding-teams-templates-bucket
    file_path: path within the bucket (e.g., 'child/template.md' or 'epic.md')
    data: file content as bytes
    """
    access_token = get_ibm_iam_access_token()
    content_type = "text/plain"
    url = f"https://s3.us-west.cloud-object-storage.test.appdomain.cloud/{TEMPLATES_BUCKET_NAME}/{file_path}"
    headers = {
        "Content-Type": content_type,
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.put(url, data=data, headers=headers)

    if response.status_code in (200, 201):
        print(f"Upload successful: {file_path}")
        return url
    else:
        print(f"Upload failed: {response.status_code}\n{response.text}")
        return None
    
    

def upload_templates_to_cos(templates_dict):
    """
    Upload categorized templates to IBM Cloud and return URLs.
    
    :param templates_dict: Dictionary with 'common', 'product', 'teams' categories
    :return: Dictionary with uploaded URLs categorized by type
    """
    access_token = get_ibm_iam_access_token()
    bucket_name = TEMPLATES_BUCKET_NAME
    base_url = f"https://s3.us-west.cloud-object-storage.test.appdomain.cloud/{bucket_name}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "text/plain"
    }
    
    uploaded_urls = {
        'common': [],
        'product': [],
        'teams': []
    }
    
    import requests
    
    # Upload common templates
    for template in templates_dict.get('common', []):
        file_response = requests.get(template['url'])
        if file_response.status_code == 200:
            file_content = file_response.content
            upload_url = f"{base_url}/{template['path']}"
            upload_response = requests.put(upload_url, data=file_content, headers=headers)
            
            if upload_response.status_code in (200, 201):
                print(f"✅ Uploaded {template['path']}")
                uploaded_urls['common'].append({
                    'name': template['name'],
                    'url': upload_url,
                    'path': template['path']
                })
            else:
                print(f"❌ Failed to upload {template['path']}: {upload_response.status_code}")
    
    # Upload product templates
    for template in templates_dict.get('product', []):
        file_response = requests.get(template['url'])
        if file_response.status_code == 200:
            file_content = file_response.content
            upload_url = f"{base_url}/{template['path']}"
            upload_response = requests.put(upload_url, data=file_content, headers=headers)
            
            if upload_response.status_code in (200, 201):
                print(f"✅ Uploaded {template['path']}")
                uploaded_urls['product'].append({
                    'name': template['name'],
                    'url': upload_url,
                    'path': template['path']
                })
            else:
                print(f"❌ Failed to upload {template['path']}: {upload_response.status_code}")
    
    # Upload team templates
    for template in templates_dict.get('teams', []):
        file_response = requests.get(template['url'])
        if file_response.status_code == 200:
            file_content = file_response.content
            upload_url = f"{base_url}/{template['path']}"
            upload_response = requests.put(upload_url, data=file_content, headers=headers)
            
            if upload_response.status_code in (200, 201):
                print(f"✅ Uploaded {template['path']}")
                uploaded_urls['teams'].append({
                    'name': template['name'],
                    'url': upload_url,
                    'path': template['path']
                })
            else:
                print(f"❌ Failed to upload {template['path']}: {upload_response.status_code}")
    
    total_uploaded = len(uploaded_urls['common']) + len(uploaded_urls['product']) + len(uploaded_urls['teams'])
    print(f"Total files uploaded: {total_uploaded}")
    
    return uploaded_urls