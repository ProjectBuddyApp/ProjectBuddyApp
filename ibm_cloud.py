import requests
from io import BytesIO
import os


API_KEY="C3ePfiQHqD_PbHuo6rHivG1fDa_AgOcqMdmzHOawUyi1"
BUCKET_NAME="hacker-01"
VECTOR_BUCKET_NAME="vector-db-bucket"

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
    print(team_name)
    print(faiss_url)
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
    