import chainlit as cl
import mongoclient
import ibm_cloud
import utils
import github_handler
import markdown_processor
from rag_model import embedding_model, AskQuestion, load_all_teams_data
import asyncio
import threading

# Import startup_init to load vector data once at application startup
import startup_init


@cl.on_message
async def main(message: cl.Message):
    # Handle Teams Administrator GitHub link input
    if cl.user_session.get("awaiting_github_repo_link"):
        github_link = message.content
        cl.user_session.set("awaiting_github_repo_link", False)
        
        # Validate GitHub link format
        if not ("github.com" in github_link or "raw.githubusercontent.com" in github_link):
            await cl.Message(content="Please provide a valid GitHub repository link.").send()
            cl.user_session.set("awaiting_github_repo_link", True)
            return
        
        cl.user_session.set("github_repo_link", github_link)
        
        # Process the GitHub repository
        await cl.Message(content="Thank you! We will proceed with the repository you provided.").send()
        
        try:
            # Step 1: Fetch templates from GitHub
            async with cl.Step(name="Fetching templates from GitHub", type="tool") as step:
                templates = github_handler.fetch_github_templates(github_link)
                
                if not templates:
                    step.output = "❌ Failed to fetch templates"
                    await cl.Message(content="❌ Failed to fetch templates. Please check the repository structure and try again.").send()
                    return
                
                step.output = f"✅ Successfully fetched templates from repository"
            
            # Step 2: Upload templates to IBM Cloud
            async with cl.Step(name="Uploading templates to IBM Cloud", type="tool") as step:
                uploaded_urls = ibm_cloud.upload_templates_to_cos(templates)
                total_count = len(uploaded_urls['common']) + len(uploaded_urls['product']) + len(uploaded_urls['teams'])
                step.output = f"✅ Uploaded {total_count} templates to IBM Cloud"
            
            # Step 3: Store URLs in MongoDB
            async with cl.Step(name="Storing template metadata in MongoDB", type="tool") as step:
                for template in uploaded_urls['common']:
                    mongoclient.insert_common_template(template['name'], template['url'], template['path'])
                
                for template in uploaded_urls['product']:
                    mongoclient.insert_product_template(template['name'], template['url'], template['path'])
                
                for template in uploaded_urls['teams']:
                    mongoclient.insert_team_template(template['name'], template['url'], template['path'])
                
                step.output = f"✅ Stored metadata for {total_count} templates"
            
            if total_count > 0:
                await cl.Message(content=f"✅ **Thank you!** {total_count} templates have been successfully uploaded").send()
                
                # Extract team names from uploaded templates
                uploaded_teams = {
                    'product': [t['name'].replace('.md', '') for t in uploaded_urls['product']],
                    'teams': [t['name'].replace('.md', '') for t in uploaded_urls['teams']]
                }
                
                # Notify user that vector creation is happening in background
                await cl.Message(
                    content="🔄 **Vector embeddings are being created in the background.**\n\n"
                            "This process may take a few minutes depending on the number of templates and URLs to process.\n\n"
                            "✅ You can continue using the app - the Q&A feature will be updated automatically once processing is complete.\n\n"
                            ).send()
                
                # Start vector creation in background thread
                def create_vectors_background():
                    try:
                        print(f"🚀 Background: Starting vector creation for {len(uploaded_teams['product']) + len(uploaded_teams['teams'])} teams...")
                        results = markdown_processor.create_vectors_for_uploaded_teams(
                            embedding_model,
                            uploaded_teams
                        )
                        
                        success_count = len(results['success'])
                        total_teams = results['total']
                        
                        print(f"✅ Background: Vector creation complete - {success_count}/{total_teams} successful")
                        
                        # Reload vectors to make them available for Q&A
                        if success_count > 0:
                            print(f"🔄 Background: Loading {success_count} new team vectors...")
                            load_all_teams_data()
                            print(f"✅ Background: Vectors loaded successfully!")
                        
                    except Exception as e:
                        print(f"❌ Background: Error creating vectors: {str(e)}")
                        import traceback
                        traceback.print_exc()
                
                # Run in separate thread to not block the UI
                vector_thread = threading.Thread(target=create_vectors_background, daemon=True)
                vector_thread.start()
                
                # Important reminder about team configuration
                await cl.Message(
                    content="🎯 **Important Next Step!**\n\n"
                            "Your templates are now ready, but there's one crucial step remaining:\n\n"
                            "**⚙️ Configure Team Details** is essential for the onboarding experience!\n\n"
                            "Without configuring team details, new joiners won't be able to:\n"
                            "• 👥 Connect with their assigned buddy\n"
                            "• 📧 Receive personalized onboarding emails\n"
                            "• 🤝 Know who their manager and team lead are\n\n"
                            "**Please go back to the main menu and select '⚙️ Configure Team Details'** to set up:\n"
                            "✓ Buddy name, github userid and email\n"
                            "✓ Manager github user id\n"
                            "✓ Team lead user id\n\n"
                            "This ensures every new joiner gets a seamless, personalized onboarding journey! 🚀"
                ).send()
            else:
                await cl.Message(content="❌ No templates were uploaded. Please check the repository structure.").send()
                
        except Exception as e:
            await cl.Message(content=f"❌ Error processing repository: {str(e)}").send()
            import traceback
            traceback.print_exc()
        
        return
    
    # Handle field update for existing team details
    if cl.user_session.get("awaiting_field_update"):
        new_value = message.content
        field = cl.user_session.get("updating_field")
        team_name = cl.user_session.get("selected_config_team")
        team_type = cl.user_session.get("selected_config_team_type")
        
        # Validate email if updating buddy_email
        if field == "buddy_email" and not utils.is_valid_email(new_value):
            await cl.Message(content="Please provide a valid email address").send()
            return
        
        cl.user_session.set("awaiting_field_update", False)
        
        # Get existing details
        existing_details = mongoclient.get_team_details(team_name, team_type)
        
        if existing_details:
            # Update only the specific field
            update_data = {
                "team_name": team_name,
                "team_type": team_type,
                "buddy_name": existing_details.get("buddy_name"),
                "buddy_email": existing_details.get("buddy_email"),
                "buddy_github": existing_details.get("buddy_github"),
                "manager_github": existing_details.get("manager_github"),
                "team_lead_github": existing_details.get("team_lead_github")
            }
            
            # Update the specific field
            if field == "buddy_name":
                update_data["buddy_name"] = new_value
            elif field == "buddy_email":
                update_data["buddy_email"] = new_value
            elif field == "buddy_github":
                update_data["buddy_github"] = new_value
            elif field == "manager_github":
                update_data["manager_github"] = new_value
            elif field == "team_lead_github":
                update_data["team_lead_github"] = new_value
            
            # Save to MongoDB
            mongoclient.insert_team_details(
                update_data["team_name"],
                update_data["team_type"],
                update_data["buddy_name"],
                update_data["buddy_email"],
                update_data["buddy_github"],
                update_data["manager_github"],
                update_data["team_lead_github"]
            )
            
            field_display = field.replace("_", " ").title()
            await cl.Message(content=f"✅ {field_display} for '{team_name}' has been updated successfully!").send()
        else:
            await cl.Message(content="❌ Error: Team details not found.").send()
        
        return
    
    # Handle Configure Team Details flow
    if cl.user_session.get("awaiting_team_detail_buddy_name"):
        buddy_name = message.content
        cl.user_session.set("awaiting_team_detail_buddy_name", False)
        cl.user_session.set("team_detail_buddy_name", buddy_name)
        await cl.Message(content="Please enter the buddy's email:").send()
        cl.user_session.set("awaiting_team_detail_buddy_email", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_buddy_email"):
        buddy_email = message.content
        if not utils.is_valid_email(buddy_email):
            await cl.Message(content="Please provide a valid email address").send()
            return
        cl.user_session.set("awaiting_team_detail_buddy_email", False)
        cl.user_session.set("team_detail_buddy_email", buddy_email)
        await cl.Message(content="Please enter the buddy's GitHub username").send()
        cl.user_session.set("awaiting_team_detail_buddy_github", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_buddy_github"):
        buddy_github = message.content.strip().lstrip('@')  # Remove @ if user includes it
        cl.user_session.set("awaiting_team_detail_buddy_github", False)
        cl.user_session.set("team_detail_buddy_github", buddy_github)
        await cl.Message(content="Please enter the manager's GitHub username").send()
        cl.user_session.set("awaiting_team_detail_manager_github", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_manager_github"):
        manager_github = message.content.strip().lstrip('@')
        cl.user_session.set("awaiting_team_detail_manager_github", False)
        cl.user_session.set("team_detail_manager_github", manager_github)
        await cl.Message(content="Please enter the team lead's GitHub username").send()
        cl.user_session.set("awaiting_team_detail_lead_github", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_lead_github"):
        lead_github = message.content.strip().lstrip('@')
        cl.user_session.set("awaiting_team_detail_lead_github", False)
        cl.user_session.set("team_detail_lead_github", lead_github)
        
        # Save all team details to MongoDB
        team_name = cl.user_session.get("selected_config_team")
        team_type = cl.user_session.get("selected_config_team_type")
        buddy_name = cl.user_session.get("team_detail_buddy_name")
        buddy_email = cl.user_session.get("team_detail_buddy_email")
        buddy_github = cl.user_session.get("team_detail_buddy_github")
        manager_github = cl.user_session.get("team_detail_manager_github")
        lead_github = cl.user_session.get("team_detail_lead_github")
        
        mongoclient.insert_team_details(
            team_name, team_type, buddy_name, buddy_email,
            buddy_github, manager_github, lead_github
        )
        
        await cl.Message(content=f"✅ Team details for '{team_name}' have been saved successfully!").send()
        return
    
    # If not in any flow, treat the message as a general question
    user_question = message.content.strip()
    print('Admin asking question:', user_question)
    response = AskQuestion(user_question)
    await cl.Message(content=response).send()


@cl.on_chat_start
async def start():
    """Start the admin application."""
    # Vector data is already loaded at application startup via startup_init module
    await cl.Message(
        content="🔧 **Welcome to IBM Onboarding Admin Portal**\n\n"
                "👋 Hello, Administrator!\n\n"
                "This is your central hub for managing the onboarding experience across all teams. "
                "From here, you can upload onboarding templates and configure team structures to ensure "
                "every new joiner gets the best possible start.\n\n"
                "**Your Impact:**\n"
                "• 📚 Maintain up-to-date onboarding resources\n"
                "• 👥 Assign buddies to support new team members\n"
                "• 🎯 Ensure smooth onboarding workflows\n"
                "• 💬 Answer questions about onboarding templates\n\n"
                "**Let's get started!** Choose an action below, or ask me any questions about the templates:"
    ).send()
    
    # Send buttons
    await cl.Message(
        content="**Available Options:**",
        actions=[
            cl.Action(
                name="role_selected",
                label="🔧 Teams Administrator",
                payload={"role": "TeamsAdmin"}
            ),
            cl.Action(
                name="role_selected",
                label="⚙️ Configure Team Details",
                payload={"role": "ConfigureTeam"}
            ),
        ]
    ).send()


@cl.action_callback("role_selected")
async def handle_action(action: cl.Action):
    """Handle role selection."""
    role = action.payload.get("role")
    
    if role == "TeamsAdmin":
        await cl.Message(
            content="🔧 **Welcome, Teams Administrator!**\n\n"
                    "📚 **Upload Onboarding Templates**\n\n"
                    "Let's make onboarding resources available to all teams! Simply provide your GitHub repository link, "
                    "and we'll take care of organizing everything.\n\n"
                    "**What you need:**\n"
                    "• A GitHub repository link with your onboarding templates\n"
                    "• Templates organized in folders: common, product-specific, and team-specific\n\n"
                    "**Ready?** Paste your GitHub repository link below:"
        ).send()
        cl.user_session.set("awaiting_github_repo_link", True)
    
    elif role == "ConfigureTeam":
        # Get all team names from templates
        team_names_dict = mongoclient.get_all_team_names_from_templates()
        
        # Combine product and teams into one list with type info
        all_teams = []
        for team in team_names_dict['product']:
            all_teams.append({"name": team, "type": "product"})
        for team in team_names_dict['teams']:
            all_teams.append({"name": team, "type": "teams"})
        
        if not all_teams:
            await cl.Message(
                content="❌ **No Teams Found**\n\n"
                        "It looks like you haven't uploaded any templates yet. "
                        "Please use the **Teams Administrator** option first to upload your onboarding templates."
            ).send()
            return
        
        # Create action buttons for all teams
        team_actions = [
            cl.Action(
                name="config_team_select",
                label=team['name'],
                payload={"team_name": team['name'], "team_type": team['type']}
            )
            for team in all_teams
        ]
        
        await cl.Message(
            content="⚙️ **Configure Team Details**\n\n"
                    "👥 **Set Up Your Team Structure**\n\n"
                    "For each team, you'll assign:\n"
                    "• A **Buddy** to guide new joiners\n"
                    "• A **Manager** for oversight\n"
                    "• A **Team Lead** for technical guidance\n\n"
                    "This ensures every new team member knows exactly who to reach out to! 🤝\n\n"
                    "**Select a team to configure:**",
            actions=team_actions
        ).send()


@cl.action_callback("config_team_select")
async def handle_config_team_select(action: cl.Action):
    """Handle team selection for configuration."""
    team_name = action.payload.get("team_name")
    team_type = action.payload.get("team_type")
    
    # Store in session
    cl.user_session.set("selected_config_team", team_name)
    cl.user_session.set("selected_config_team_type", team_type)
    
    # Check if team details already exist
    existing_details = mongoclient.get_team_details(team_name, team_type)
    
    if existing_details:
        # Show existing details and ask if user wants to edit
        await cl.Message(
            content=f"📋 **Current details for {team_name}:**\n\n"
                    f"**Buddy:** {existing_details.get('buddy_name')} ({existing_details.get('buddy_email')}) - @{existing_details.get('buddy_github')}\n"
                    f"**Manager:** @{existing_details.get('manager_github')}\n"
                    f"**Team Lead:** @{existing_details.get('team_lead_github')}\n\n"
                    f"Would you like to update these details?",
            actions=[
                cl.Action(
                    name="edit_team_details",
                    label="✏️ Edit Details",
                    payload={"edit": True}
                ),
                cl.Action(
                    name="edit_team_details",
                    label="❌ Cancel",
                    payload={"edit": False}
                )
            ]
        ).send()
    else:
        # No existing details, start collecting
        await cl.Message(content=f"⚙️ **Configuring details for {team_name}**\n\nPlease enter the buddy's name:").send()
        cl.user_session.set("awaiting_team_detail_buddy_name", True)


@cl.action_callback("edit_team_details")
async def handle_edit_team_details(action: cl.Action):
    """Handle editing team details."""
    should_edit = action.payload.get("edit")
    
    if should_edit:
        team_name = cl.user_session.get("selected_config_team")
        # Show field selection options
        await cl.Message(
            content=f"✏️ **Which field would you like to update for {team_name}?**",
            actions=[
                cl.Action(
                    name="field_to_update",
                    label="Buddy Name",
                    payload={"field": "buddy_name"}
                ),
                cl.Action(
                    name="field_to_update",
                    label="Buddy Email",
                    payload={"field": "buddy_email"}
                ),
                cl.Action(
                    name="field_to_update",
                    label="Buddy GitHub",
                    payload={"field": "buddy_github"}
                ),
                cl.Action(
                    name="field_to_update",
                    label="Manager GitHub",
                    payload={"field": "manager_github"}
                ),
                cl.Action(
                    name="field_to_update",
                    label="Team Lead GitHub",
                    payload={"field": "team_lead_github"}
                )
            ]
        ).send()
    else:
        await cl.Message(content="Operation cancelled.").send()


@cl.action_callback("field_to_update")
async def handle_field_to_update(action: cl.Action):
    """Handle field selection for update."""
    field = action.payload.get("field")
    team_name = cl.user_session.get("selected_config_team")
    
    # Store which field is being updated
    cl.user_session.set("updating_field", field)
    
    # Ask for the new value based on field
    field_display = field.replace("_", " ").title()
    await cl.Message(content=f"Please enter the new **{field_display}** for **{team_name}**:").send()
    cl.user_session.set("awaiting_field_update", True)



