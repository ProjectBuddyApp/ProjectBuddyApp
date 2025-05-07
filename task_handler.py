import os
import httpx
from dotenv import load_dotenv
import chainlit as cl
import ibm_cloud
import mongoclient
import pandas as pd

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if GITHUB_TOKEN is None:
    print("Error: GitHub token not found in environment variables.")
    exit(1)
REPO = "TestRepo"
GITHUB_API_URL = f"https://api.github.com/repos/Samarinnayak/project_buddy_test_1/issues"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

async def read_excel(onboarding_excel):
    df = pd.read_excel(onboarding_excel)
    df.columns = df.columns.str.strip()
    df['Section'] = df['Section'].str.strip().str.capitalize()
    sections = df['Section'].dropna().unique()
    print(sections)
    payloads = []
    for section in sections:
        section_df = df[df['Section'] == section]
        if section_df.empty:
            continue

        issue_title = f"[Onboarding] {section} Tasks"
        issue_body = f"### Subtasks for {section} onboarding:\n\n" + await format_subtasks(section_df)


        payload = {
            "title": issue_title,
            "body": issue_body,
        }
        payloads.append(payload)
    return payloads

async def format_subtasks(section_df):
    checklist = []
    for _, row in section_df.iterrows():
        item = row['Item']
        duration = row.get('Duration', '')
        task_info = row.get('Task Info', '')
        link = row.get('Link/Instructions', '')

        line = f"- [ ] **{item}**"
        if pd.notna(duration):
            line += f" ({duration} day{'s' if duration != 1 else ''})"
        if pd.notna(task_info):
            line += f"\n      {task_info.strip()}"
        if pd.notna(link):
            line += f"\n      🔗 [Link]({link.strip()})"
        checklist.append(line)
    return "\n\n".join(checklist)


async def create_github_onboarding_tasks(selected_team):
    file_url = mongoclient.fetch_file_url(selected_team)
    print(file_url)
    if file_url:
        onboarding_excel = ibm_cloud.fetch_file_from_cos(file_url)
        print(onboarding_excel)
        tasks = await read_excel(onboarding_excel)

        async with httpx.AsyncClient() as client:
            # Create issues asynchronously
            for task in tasks:
                issue_data = {
                    "title": task["title"],
                    "body": task["body"],
                    # "assignees": [username],  # Optional: must be a collaborator in the repo
                }
                
                # Asynchronous POST request to GitHub API
                response = await client.post(GITHUB_API_URL, json=issue_data, headers=HEADERS)
                
                if response.status_code == 201:
                    issue = response.json()
                    issue_url = issue.get("html_url", "No URL available")  # Get the URL of the created issue
                    success_message = f"Issue '{issue_url}' created successfully."
                    print(success_message)
                    await cl.Message(content=success_message).send()  # Send success message with link to chat
                else:
                    error_message = f"Failed to create issue '{task['title']}': {response.json()}"
                    print(error_message)
                    await cl.Message(content=error_message).send()  # Send failure message to chat

