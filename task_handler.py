import os
import httpx
from dotenv import load_dotenv
import chainlit as cl
import ibm_cloud
import mongoclient

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

async def create_github_onboarding_tasks(team_name, team_type, joinee_name):
    """
    Create GitHub issues from templates for a new joiner.
    
    :param team_name: Name of the team (without .md extension)
    :param team_type: Type of team ('product' or 'teams')
    :param joinee_name: Name of the new joiner
    :return: List of created GitHub issue URLs
    """
    created_tasks = []
    
    try:
        # Step 1: Get team details (buddy, manager, team lead)
        team_details = mongoclient.get_team_details(team_name, team_type)
        if not team_details:
            error_msg = f"Team details not found for '{team_name}' ({team_type})"
            print(error_msg)
            await cl.Message(content=error_msg).send()
            return created_tasks
        
        # Extract team member information
        buddy_name = team_details.get("buddy_name", "")
        buddy_github = team_details.get("buddy_github", "")
        manager_github = team_details.get("manager_github", "")
        team_lead_github = team_details.get("team_lead_github", "")
        
        print(f"Team details - Buddy: {buddy_name} (@{buddy_github}), Manager: @{manager_github}, Team Lead: @{team_lead_github}")
        
        # Step 2: Query templates from MongoDB
        templates_to_process = []
        
        # Get product or team-specific template
        if team_type == "product":
            collection = mongoclient.db["product"]
        else:  # team_type == "teams"
            collection = mongoclient.db["teams"]
        
        team_template = collection.find_one(
            {"template_name": f"{team_name}.md"},
            {"_id": 0}
        )
        
        if team_template:
            templates_to_process.append({
                "name": team_template["template_name"],
                "url": team_template["ibm_cloud_url"],
                "type": team_type
            })
            print(f"Found {team_type} template: {team_template['template_name']}")
        else:
            print(f"No {team_type} template found for {team_name}")
        
        # Get all common templates
        common_templates = mongoclient.get_all_common_templates()
        for template in common_templates:
            templates_to_process.append({
                "name": template["template_name"],
                "url": template["ibm_cloud_url"],
                "type": "common"
            })
        
        print(f"Total templates to process: {len(templates_to_process)}")
        
        # Step 3: Process each template
        async with httpx.AsyncClient() as client:
            for template in templates_to_process:
                try:
                    # Fetch template content from IBM Cloud
                    print(f"Fetching template: {template['name']}")
                    template_content = ibm_cloud.fetch_file_from_cos(template['url'])
                    content_text = template_content.read().decode('utf-8')
                    
                    # Parse template: first line = title, rest = body
                    lines = content_text.strip().split('\n')
                    if not lines:
                        print(f"Empty template: {template['name']}")
                        continue
                    
                    # Extract title (first line, remove markdown heading symbols)
                    title = lines[0].strip().lstrip('#').strip()
                    
                    # Extract body (rest of the content)
                    body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
                    
                    # Step 4: Replace placeholders with GitHub mentions
                    replacements = {
                        "${onboardee}": joinee_name,
                        "${buddy}": f"@{buddy_github}",
                        "${teamlead}": f"@{team_lead_github}",
                        "${manager}": f"@{manager_github}"
                    }
                    
                    for placeholder, value in replacements.items():
                        title = title.replace(placeholder, value)
                        body = body.replace(placeholder, value)
                    
                    # Step 5: Fix checkbox format for GitHub
                    # GitHub requires exact format: "- [ ] " for clickable checkboxes
                    import re
                    
                    # Replace all checkbox patterns with GitHub's clickable format
                    # This handles: ☐, □, [ ], [], [x], [X], ✓, ✔, etc.
                    
                    # First, normalize checkbox symbols at the start of lines (with or without dash)
                    # Match standalone checkbox symbols and add dash if missing
                    body = re.sub(r'^(\s*)☐\s*', r'\1- [ ] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)□\s*', r'\1- [ ] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)☑\s*', r'\1- [x] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)✓\s*', r'\1- [x] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)✔\s*', r'\1- [x] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)✅\s*', r'\1- [x] ', body, flags=re.MULTILINE)
                    
                    # Now normalize all list items with brackets to proper checkbox format
                    # Match: "- []", "- [ ]", "-[]", "-[ ]", "- [x]", "- [X]", etc.
                    # Replace with: "- [ ] " or "- [x] "
                    body = re.sub(r'^(\s*)-\s*\[\s*\]', r'\1- [ ]', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)-\s*\[[xX✓✔]\]', r'\1- [x]', body, flags=re.MULTILINE)
                    
                    # Handle standalone brackets at start of line (without dash)
                    body = re.sub(r'^(\s*)\[\s*\]\s*', r'\1- [ ] ', body, flags=re.MULTILINE)
                    body = re.sub(r'^(\s*)\[[xX]\]\s*', r'\1- [x] ', body, flags=re.MULTILINE)
                    
                    # Step 6: Create GitHub issue
                    issue_data = {
                        "title": title,
                        "body": body,
                    }
                    
                    print(f"Creating GitHub issue: {title}")
                    response = await client.post(GITHUB_API_URL, json=issue_data, headers=HEADERS)
                    
                    if response.status_code == 201:
                        issue = response.json()
                        issue_url = issue.get("html_url", "No URL available")
                        success_message = f"✅ Issue created: [{title}]({issue_url})"
                        print(success_message)
                        await cl.Message(content=success_message).send()
                        
                        # Add to created tasks list
                        created_tasks.append({
                            "title": title,
                            "url": issue_url,
                            "template": template['name']
                        })
                    else:
                        error_message = f"❌ Failed to create issue '{title}': {response.status_code} - {response.text}"
                        print(error_message)
                        await cl.Message(content=error_message).send()
                
                except Exception as e:
                    error_msg = f"Error processing template '{template['name']}': {str(e)}"
                    print(error_msg)
                    await cl.Message(content=error_msg).send()
        
        # Step 6: Return created tasks
        print(f"Total GitHub issues created: {len(created_tasks)}")
        return created_tasks
    
    except Exception as e:
        error_msg = f"Error in create_github_onboarding_tasks: {str(e)}"
        print(error_msg)
        await cl.Message(content=error_msg).send()
        return created_tasks

