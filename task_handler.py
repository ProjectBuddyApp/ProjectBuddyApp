import os
import httpx
from dotenv import load_dotenv
import chainlit as cl

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if GITHUB_TOKEN is None:
    print("Error: GitHub token not found in environment variables.")
    exit(1)
# GITHUB_TOKEN = "ghp_your_token_here"
REPO = "project_buddy_test_1"
GITHUB_API_URL = f"https://api.github.com/repos/Samarinnayak/project_buddy_test_1/issues"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

async def create_github_onboarding_tasks():
    tasks = [
        {"title": "Complete HR Documentation", "body": "Please finish your onboarding documents."},
        {"title": "Set Up Development Environment", "body": "Install required tools and clone repos."},
        {"title": "Review Onboarding Guide", "body": "Go through the onboarding Notion guide."},
    ]

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

