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

async def read_task_from_excel(csv_file):
    df = pd.read_excel(csv_file, sheet_name="FinalSheet", header=0)
    payloads = []
    task_types = df['Task Type'].dropna().unique()
    for task_type in task_types:
            task_df = df[df['Task Type'] == task_type]
            if task_df.empty:
                continue
            body = await format_task_body(task_df)

            payload = {
                "title": task_type.strip(),
                "body": body,
            }
            payloads.append(payload)
    return payloads

async def format_task_body(task_df):
    formatted_rows = []
    for _, row in task_df.iterrows():
        task_name = row['Task Name'].strip() if pd.notna(row['Task Name']) else ""
        task_info = row['Task Info'].strip() if pd.notna(row['Task Info']) else ""
        task_links = row['Task Related Links'].strip() if pd.notna(row['Task Related Links']) else ""
        task_duration = row['Task Duration'].strip() if pd.notna(row['Task Duration']) else ""
        additional_info = row['Additional Information'].strip() if pd.notna(row['Additional Information']) else ""

        # Format the row as a checklist item
        line = f"- [ ] **{task_name}**"
        if task_duration:
            line += f" ({task_duration})"
        if task_info:
            line += f"\n      {task_info}"
        if task_links:
            line += f"\n      🔗 [Link]({task_links})"
        if additional_info:
            line += f"\n      {additional_info}"

        formatted_rows.append(line)

    return "\n\n".join(formatted_rows)


async def create_github_onboarding_tasks(selected_team):
    file_url = mongoclient.fetch_file_url(selected_team)
    print(file_url)

    if file_url:
        onboarding_excel = ibm_cloud.fetch_file_from_cos(file_url)
        item_lists = await read_task_from_excel(onboarding_excel)
        print("========> Item list: ", item_lists)

        async with httpx.AsyncClient() as client:
            # Create issues asynchronously
            for task in item_lists:
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

