import requests


def fetch_github_templates(github_link: str):
    """
    Fetch templates from GitHub repository.
    Returns a dictionary with categorized templates:
    {
        'common': [{'name': 'file.md', 'url': 'download_url', 'path': 'child/file.md'}, ...],
        'product': [{'name': 'file.md', 'url': 'download_url', 'path': 'product/file.md'}, ...],
        'teams': [{'name': 'file.md', 'url': 'download_url', 'path': 'teams/file.md'}, ...]
    }
    """
    try:
        # Extract owner, repo, and branch from the GitHub URL
        github_link = github_link.strip()
        
        # Remove trailing slash if present
        if github_link.endswith('/'):
            github_link = github_link[:-1]
        
        # Parse the URL
        parts = github_link.replace("https://github.com/", "").split("/")
        owner = parts[0]
        repo = parts[1]
        
        # Check if branch is specified in URL
        if len(parts) > 3 and parts[2] == "tree":
            branch = parts[3]
        else:
            branch = "main"
        
        print(f"Fetching from: {owner}/{repo} (branch: {branch})")
        
        # GitHub API - find the onboarding folder (case-insensitive)
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        # Get root contents to find the onboarding folder
        root_response = requests.get(f"https://api.github.com/repos/{owner}/{repo}/contents?ref={branch}", headers=headers)
        
        if root_response.status_code != 200:
            print(f"Failed to fetch repository contents: {root_response.status_code} - {root_response.text}")
            return None
        
        # Find the onboarding folder (case-insensitive)
        root_contents = root_response.json()
        onboarding_folder = None
        for item in root_contents:
            if item["type"] == "dir" and item["name"].lower() == "onboarding":
                onboarding_folder = item["name"]
                break
        
        if not onboarding_folder:
            print("Could not find 'onboarding' folder in repository")
            return None
        
        print(f"Found folder: {onboarding_folder}")
        
        # Fetch the onboarding directory structure
        api_base = f"https://api.github.com/repos/{owner}/{repo}/contents/{onboarding_folder}"
        response = requests.get(f"{api_base}?ref={branch}", headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch {onboarding_folder} directory: {response.status_code} - {response.text}")
            return None
        
        onboarding_contents = response.json()
        
        # Categorize templates
        templates = {
            'common': [],
            'product': [],
            'teams': []
        }
        
        # Process each item in the onboarding directory
        for item in onboarding_contents:
            item_name = item["name"]
            
            if item["type"] == "file":
                # epic.md goes to common templates
                if item_name == "epic.md":
                    templates['common'].append({
                        'name': item_name,
                        'url': item["download_url"],
                        'path': item_name
                    })
            
            elif item["type"] == "dir":
                # Fetch all files in the directory
                dir_response = requests.get(item["url"], headers=headers)
                if dir_response.status_code == 200:
                    dir_contents = dir_response.json()
                    
                    for file_item in dir_contents:
                        if file_item["type"] == "file":
                            file_info = {
                                'name': file_item['name'],
                                'url': file_item["download_url"],
                                'path': f"{item_name}/{file_item['name']}"
                            }
                            
                            # Categorize based on folder
                            if item_name.lower() == "child":
                                templates['common'].append(file_info)
                            elif item_name.lower() == "product":
                                templates['product'].append(file_info)
                            elif item_name.lower() == "teams":
                                templates['teams'].append(file_info)
        
        print(f"Found {len(templates['common'])} common templates, {len(templates['product'])} product templates, {len(templates['teams'])} team templates")
        return templates
        
    except Exception as e:
        print(f"Error in fetch_github_templates: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Made with Bob
