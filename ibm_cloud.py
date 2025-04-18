import requests

API_KEY="C3ePfiQHqD_PbHuo6rHivG1fDa_AgOcqMdmzHOawUyi1"
BUCKET_NAME="hacker-01"

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