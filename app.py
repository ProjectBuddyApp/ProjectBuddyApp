import chainlit as cl
from docx import Document
from constant import buddy_steps
import mongoclient
import ibm_cloud
from rag_model import MyBuddy, AskQuestion, load_vector_db_for_selected_team, load_all_teams_data
import utils
import task_handler
import email_integration
import github_handler

# Import startup_init to load vector data once at application startup
import startup_init



@cl.on_message
async def main(message:str):
    myBuddy: MyBuddy
    if cl.user_session.get("awaiting_buddy_name"):
        cl.user_session.set("awaiting_buddy_name",False)
        buddy_name = message.content
        cl.user_session.set("buddy_name", buddy_name)
        await cl.Message(content=buddy_steps[0]).send()
        cl.user_session.set("awaiting_buddy_email", True)
        return

    if cl.user_session.get("awaiting_buddy_email"):
        buddy_email = message.content
        if not utils.is_valid_email(buddy_email):
             await cl.Message(content="Please provide valid email address").send()
             return
        cl.user_session.set("awaiting_buddy_email",False)
        cl.user_session.set("buddy_email", buddy_email)
        await cl.Message(content=buddy_steps[1]).send()
        cl.user_session.set("awaiting_github-username", True)
        return
    
    if cl.user_session.get("awaiting_github-username"):
        cl.user_session.set("awaiting_github-username",False)
        buddy_github_username = message.content
        cl.user_session.set("buddy_github_username", buddy_github_username)
        await cl.Message(content=buddy_steps[2]).send()
        cl.user_session.set("awaiting_team_name", True)
        return

    if cl.user_session.get("awaiting_team_name"):
        cl.user_session.set("awaiting_team_name",False)
        team_name = message.content
        cl.user_session.set("team_name", team_name)
        await cl.Message(content=buddy_steps[3]).send()
        elements = [
            cl.File(name="template",path="./Project_Onboarding.xlsm",display="inline",
        )]
        await cl.Message(content="Here you go", elements=elements).send()
        cl.user_session.set("awaiting_team_template", True)
        return
        
    # Existing buddy flow
    if cl.user_session.get("awaiting_existing_buddy_email"):
        buddy_email = message.content
        if not utils.is_valid_email(buddy_email):
            await cl.Message(content="Please provide valid email address").send()
            return
        
        # Find buddy information in MongoDB
        buddy_info = mongoclient.find_buddy_by_email(buddy_email)
        if not buddy_info:
            await cl.Message(content="Sorry, we couldn't find your information. Please try again or register as a new buddy.").send()
            cl.user_session.set("awaiting_existing_buddy_email", False)
            return
            
        # Store buddy info in session
        cl.user_session.set("awaiting_existing_buddy_email", False)
        cl.user_session.set("existing_buddy_email", buddy_email)
        cl.user_session.set("existing_buddy_name", buddy_info.get("buddy_name"))
        cl.user_session.set("existing_buddy_github", buddy_info.get("buddy_github_username"))
        cl.user_session.set("existing_buddy_team", buddy_info.get("team_name"))
        
        # Show update options
        await cl.Message(
            content=f"Welcome back, {buddy_info.get('buddy_name')}! What would you like to update?",
            actions=[
                cl.Action(
                    name="update_option",
                    value="name",
                    label="Update Name",
                    payload={"update": "name"}
                ),
                cl.Action(
                    name="update_option",
                    value="email",
                    label="Update Email",
                    payload={"update": "email"}
                ),
                cl.Action(
                    name="update_option",
                    value="github",
                    label="Update GitHub Username",
                    payload={"update": "github"}
                ),
                cl.Action(
                    name="update_option",
                    value="excel",
                    label="Upload New Excel File",
                    payload={"update": "excel"}
                )
            ]
        ).send()
        return
        
    # Handle update options for existing buddy
    if cl.user_session.get("awaiting_update_name"):
        cl.user_session.set("awaiting_update_name", False)
        new_name = message.content
        cl.user_session.set("new_buddy_name", new_name)
        
        # Update in MongoDB
        mongoclient.update_buddy_info(
            cl.user_session.get("existing_buddy_email"),
            {"buddy_name": new_name}
        )
        
        await cl.Message(content=f"Your name has been updated to {new_name}. Is there anything else you'd like to update?").send()
        return
        
    if cl.user_session.get("awaiting_update_email"):
        new_email = message.content
        if not utils.is_valid_email(new_email):
            await cl.Message(content="Please provide valid email address").send()
            return
            
        cl.user_session.set("awaiting_update_email", False)
        cl.user_session.set("new_buddy_email", new_email)
        
        # Update in MongoDB
        old_email = cl.user_session.get("existing_buddy_email")
        mongoclient.update_buddy_info(old_email, {"buddy_email": new_email})
        cl.user_session.set("existing_buddy_email", new_email)
        
        await cl.Message(content=f"Your email has been updated to {new_email}. Is there anything else you'd like to update?").send()
        return
        
    if cl.user_session.get("awaiting_update_github"):
        cl.user_session.set("awaiting_update_github", False)
        new_github = message.content
        cl.user_session.set("new_buddy_github", new_github)
        
        # Update in MongoDB
        mongoclient.update_buddy_info(
            cl.user_session.get("existing_buddy_email"),
            {"buddy_github_username": new_github}
        )
        
        await cl.Message(content=f"Your GitHub username has been updated to {new_github}. Is there anything else you'd like to update?").send()
        return
        
    if cl.user_session.get("awaiting_update_excel"):
        if message.elements:
            team_name = cl.user_session.get("existing_buddy_team")
            template_id = await handle_file_upload(message, cl.user_session)
            if template_id:
                # Update in MongoDB
                mongoclient.update_buddy_info(
                    cl.user_session.get("existing_buddy_email"),
                    {"template_id": template_id}
                )
                
                # Update vector database
                file = ibm_cloud.fetch_file_from_cos(template_id)
                myBuddy = MyBuddy(file)
                myBuddy.create_or_load_vector_embedding_for_excel(team_name)
                
                cl.user_session.set("awaiting_update_excel", False)
                await cl.Message(content="Your Excel file has been updated successfully. The onboarding information has been refreshed.").send()
        return

    #if some file is uploaded then redirect to handle_upload
    if cl.user_session.get("awaiting_team_template"):
        if message.elements:
            template_id = await handle_file_upload(message,cl.user_session)
            if template_id:
                cl.user_session.set("template_id", template_id)
                team_name = cl.user_session.get("team_name")
                await save_to_mongo_db(cl.user_session)
                file = ibm_cloud.fetch_file_from_cos(template_id)
                myBuddy = MyBuddy(file)
                myBuddy.create_or_load_vector_embedding_for_excel(team_name)

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
            # Fetch templates from GitHub
            templates = github_handler.fetch_github_templates(github_link)
            
            if not templates:
                await cl.Message(content="❌ Failed to fetch templates. Please check the repository structure and try again.").send()
                return
            
            # Upload templates to IBM Cloud
            uploaded_urls = ibm_cloud.upload_templates_to_cos(templates)
            
            # Store URLs in MongoDB
            for template in uploaded_urls['common']:
                mongoclient.insert_common_template(template['name'], template['url'], template['path'])
            
            for template in uploaded_urls['product']:
                mongoclient.insert_product_template(template['name'], template['url'], template['path'])
            
            for template in uploaded_urls['teams']:
                mongoclient.insert_team_template(template['name'], template['url'], template['path'])
            
            total_count = len(uploaded_urls['common']) + len(uploaded_urls['product']) + len(uploaded_urls['teams'])
            
            if total_count > 0:
                await cl.Message(content=f"✅ Sounds good! {total_count} templates have been successfully uploaded to IBM Cloud and stored in MongoDB.").send()
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
                "manager_name": existing_details.get("manager_name"),
                "manager_email": existing_details.get("manager_email", ""),
                "team_lead_name": existing_details.get("team_lead_name"),
                "team_lead_email": existing_details.get("team_lead_email", "")
            }
            
            # Update the specific field
            if field == "buddy_name":
                update_data["buddy_name"] = new_value
            elif field == "buddy_email":
                update_data["buddy_email"] = new_value
            elif field == "manager_name":
                update_data["manager_name"] = new_value
            elif field == "team_lead_name":
                update_data["team_lead_name"] = new_value
            
            # Save to MongoDB
            mongoclient.insert_team_details(
                update_data["team_name"],
                update_data["team_type"],
                update_data["buddy_name"],
                update_data["buddy_email"],
                update_data["manager_name"],
                update_data["manager_email"],
                update_data["team_lead_name"],
                update_data["team_lead_email"]
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
        await cl.Message(content="Please enter the manager's name:").send()
        cl.user_session.set("awaiting_team_detail_manager_name", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_manager_name"):
        manager_name = message.content
        cl.user_session.set("awaiting_team_detail_manager_name", False)
        cl.user_session.set("team_detail_manager_name", manager_name)
        await cl.Message(content="Please enter the team lead's name:").send()
        cl.user_session.set("awaiting_team_detail_lead_name", True)
        return
    
    if cl.user_session.get("awaiting_team_detail_lead_name"):
        lead_name = message.content
        cl.user_session.set("awaiting_team_detail_lead_name", False)
        cl.user_session.set("team_detail_lead_name", lead_name)
        
        # Save all team details to MongoDB
        team_name = cl.user_session.get("selected_config_team")
        team_type = cl.user_session.get("selected_config_team_type")
        buddy_name = cl.user_session.get("team_detail_buddy_name")
        buddy_email = cl.user_session.get("team_detail_buddy_email")
        manager_name = cl.user_session.get("team_detail_manager_name")
        
        mongoclient.insert_team_details(
            team_name, team_type, buddy_name, buddy_email,
            manager_name, "", lead_name, ""
        )
        
        await cl.Message(content=f"✅ Team details for '{team_name}' have been saved successfully!").send()
        return
    
    # Handle joinee email input
    if cl.user_session.get("awaiting_joinee_email"):
        joinee_email = message.content
        if not utils.is_valid_email(joinee_email):
            await cl.Message(content="Please provide valid email address").send()
            return
            
        cl.user_session.set("awaiting_joinee_email", False)
        cl.user_session.set("joinee_email", joinee_email)
        
        # Get team and buddy information
        selected_team = cl.user_session.get("selected_team")
        buddy_name, buddy_email, buddy_github_username = mongoclient.get_buddy_information(selected_team)
        
        # Display welcome message to joinee FIRST
        await cl.Message(
            f"🎉 Welcome to the **{selected_team}** team!\n\n"
            f"Your onboarding buddy is **{buddy_name}**, "
            f"and their W3 ID is `{buddy_email}`.\n\n"
            f"They'll help you get settled in — don't hesitate to reach out!"
        ).send()
        
        # Create GitHub tasks (this will send messages for each issue)
        tasks = await task_handler.create_github_onboarding_tasks(selected_team)
        
        # Send emails to buddy and joinee
        buddy_email_result = email_integration.notify_buddy_about_new_joinee(
            buddy_email=buddy_email,
            joinee_email=joinee_email,
            team_name=selected_team,
            tasks=tasks
        )
        
        joinee_email_result = email_integration.send_welcome_email_to_joinee(
            joinee_email=joinee_email,
            buddy_email=buddy_email,
            buddy_name=buddy_name,
            team_name=selected_team,
            tasks=tasks
        )
        
        # Notify about GitHub tasks
        await cl.Message(content="✅ We've set up your onboarding tasks in GitHub! Check your assigned issues.").send()
        
        # Notify about emails
        if buddy_email_result or joinee_email_result:
            await cl.Message(content="📧 Welcome emails have been sent to you and your buddy with onboarding information.").send()
        
        return
    
    # If not in any flow, treat the message as a general question
    if not any([
        cl.user_session.get("awaiting_buddy_name"),
        cl.user_session.get("awaiting_buddy_email"),
        cl.user_session.get("awaiting_github-username"),
        cl.user_session.get("awaiting_team_name"),
        cl.user_session.get("awaiting_team_template"),
        cl.user_session.get("awaiting_existing_buddy_email"),
        cl.user_session.get("awaiting_update_name"),
        cl.user_session.get("awaiting_update_email"),
        cl.user_session.get("awaiting_update_github"),
        cl.user_session.get("awaiting_update_excel"),
        cl.user_session.get("awaiting_joinee_email")
    ]):
        user_question = message.content.strip()
        print('Calling AskQuestion.')
        response = AskQuestion(user_question)
        await cl.Message(content=response).send()


async def save_to_mongo_db(session):
    buddy_name = session.get("buddy_name")
    buddy_email = session.get("buddy_email")
    team_name = session.get("team_name")
    template_id = session.get("template_id")
    buddy_github_username = session.get("buddy_github_username")
    mongoclient.insert_team_data(team_name,buddy_name,buddy_email,template_id,buddy_github_username)
    # Clear session data if you don't need it anymore
    session.set("buddy_name", None)
    session.set("buddy_email", None)
    session.set("team_name", None)
    session.set("template_id", None)
    session.set("buddy_github_username",None)

@cl.on_chat_start
async def start():
    # Vector data is already loaded at application startup via startup_init module
    # No need to call load_all_teams_data() here anymore - it's cached and ready to use
    await cl.Message(content=f"Welcome to IBM!\nAre you a buddy or new joinee?").send()
    # Send buttons
    await cl.Message(
        content="Please choose:",
        actions=[
            cl.Action(
                name="role_selected",
                value="Buddy",
                label="👥 I'm a Buddy",
                payload={"role": "Buddy"}
            ),
            cl.Action(
                name="role_selected",
                value="ExistingBuddy",
                label="👤 I'm an Existing Buddy",
                payload={"role": "ExistingBuddy"}
            ),
            cl.Action(
                name="role_selected",
                value="Joinee",
                label="🧑‍💼 I'm a New Joinee",
                payload={"role": "Joinee"}
            ),
            cl.Action(
                name="role_selected",
                value="TeamsAdmin",
                label="🔧 Teams Administrator",
                payload={"role": "TeamsAdmin"}
            ),
            cl.Action(
                name="role_selected",
                value="ConfigureTeam",
                label="⚙️ Configure Team Details",
                payload={"role": "ConfigureTeam"}
            ),
        ]
    ).send()

@cl.action_callback("update_option")
async def handle_update_option(action: cl.Action):
    update_type = action.payload.get("update")
    
    if update_type == "name":
        await cl.Message(content="Please enter your new name:").send()
        cl.user_session.set("awaiting_update_name", True)
    
    elif update_type == "email":
        await cl.Message(content="Please enter your new email address:").send()
        cl.user_session.set("awaiting_update_email", True)
    
    elif update_type == "github":
        await cl.Message(content="Please enter your new GitHub username:").send()
        cl.user_session.set("awaiting_update_github", True)
    
    elif update_type == "excel":
        await cl.Message(content="Please upload your new Excel file:").send()
        cl.user_session.set("awaiting_update_excel", True)

@cl.action_callback("role_selected")
async def handle_action(action: cl.Action):
    role = action.payload.get("role")
    if role == "Buddy":
        await cl.Message(content="Awesome! What's your name, Buddy?").send()
        cl.user_session.set("awaiting_buddy_name", True)
    elif role == "ExistingBuddy":
        await cl.Message(content="Welcome back! Please enter your email to identify yourself:").send()
        cl.user_session.set("awaiting_existing_buddy_email", True)
    elif role == "TeamsAdmin":
        await cl.Message(content="🔧 Welcome, Teams Administrator!\n\nPlease provide the GitHub repository link containing your onboarding templates.\n\nThe repository should have an 'onboarding' folder with the following structure:\n- child/\n- product/\n- teams/\n- epic.md").send()
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
            await cl.Message(content="❌ No teams found. Please upload templates first using Teams Administrator option.").send()
            return
        
        # Create action buttons for all teams
        team_actions = [
            cl.Action(
                name="config_team_select",
                value=f"{team['name']}|{team['type']}",
                label=team['name'],
                payload={"team_name": team['name'], "team_type": team['type']}
            )
            for team in all_teams
        ]
        
        await cl.Message(
            content="⚙️ Configure Team Details\n\nSelect a team to configure:",
            actions=team_actions
        ).send()
    elif role == "Joinee":
        team_names = mongoclient.get_all_teams()
        print(team_names)
        options = [cl.Action(name="team_select",label=str(name), value=str(name),payload={}) for name in team_names if name]
        await cl.Message(content="Welcome aboard! Let's get you started. 🚀 \nSelect your team:",actions=options).send()

@cl.action_callback("config_team_select")
async def handle_config_team_select(action: cl.Action):
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
            content=f"📋 Current details for **{team_name}**:\n\n"
                    f"**Buddy:** {existing_details.get('buddy_name')} ({existing_details.get('buddy_email')})\n"
                    f"**Manager:** {existing_details.get('manager_name')}\n"
                    f"**Team Lead:** {existing_details.get('team_lead_name')}\n\n"
                    f"Would you like to update these details?",
            actions=[
                cl.Action(
                    name="edit_team_details",
                    value="yes",
                    label="✏️ Edit Details",
                    payload={"edit": True}
                ),
                cl.Action(
                    name="edit_team_details",
                    value="no",
                    label="❌ Cancel",
                    payload={"edit": False}
                )
            ]
        ).send()
    else:
        # No existing details, start collecting
        await cl.Message(content=f"⚙️ Configuring details for **{team_name}**\n\nPlease enter the buddy's name:").send()
        cl.user_session.set("awaiting_team_detail_buddy_name", True)

@cl.action_callback("edit_team_details")
async def handle_edit_team_details(action: cl.Action):
    should_edit = action.payload.get("edit")
    
    if should_edit:
        team_name = cl.user_session.get("selected_config_team")
        # Show field selection options
        await cl.Message(
            content=f"✏️ Which field would you like to update for **{team_name}**?",
            actions=[
                cl.Action(
                    name="field_to_update",
                    value="buddy_name",
                    label="Buddy Name",
                    payload={"field": "buddy_name"}
                ),
                cl.Action(
                    name="field_to_update",
                    value="buddy_email",
                    label="Buddy Email",
                    payload={"field": "buddy_email"}
                ),
                cl.Action(
                    name="field_to_update",
                    value="manager_name",
                    label="Manager Name",
                    payload={"field": "manager_name"}
                ),
                cl.Action(
                    name="field_to_update",
                    value="team_lead_name",
                    label="Team Lead Name",
                    payload={"field": "team_lead_name"}
                )
            ]
        ).send()
    else:
        await cl.Message(content="Operation cancelled.").send()

@cl.action_callback("field_to_update")
async def handle_field_to_update(action: cl.Action):
    field = action.payload.get("field")
    team_name = cl.user_session.get("selected_config_team")
    
    # Store which field is being updated
    cl.user_session.set("updating_field", field)
    
    # Ask for the new value based on field
    if field == "buddy_name":
        await cl.Message(content=f"Please enter the new buddy name for **{team_name}**:").send()
        cl.user_session.set("awaiting_field_update", True)
    elif field == "buddy_email":
        await cl.Message(content=f"Please enter the new buddy email for **{team_name}**:").send()
        cl.user_session.set("awaiting_field_update", True)
    elif field == "manager_name":
        await cl.Message(content=f"Please enter the new manager name for **{team_name}**:").send()
        cl.user_session.set("awaiting_field_update", True)
    elif field == "team_lead_name":
        await cl.Message(content=f"Please enter the new team lead name for **{team_name}**:").send()
        cl.user_session.set("awaiting_field_update", True)

@cl.action_callback("team_select")
async def on_action(action: cl.Action):
    if action.name == "team_select":
        selected_team = action.label
        load_vector_db_for_selected_team(selected_team)
        
        # Store selected team in session
        cl.user_session.set("selected_team", selected_team)
        
        # Ask for joinee's email
        await cl.Message(content="Please enter your email address:").send()
        cl.user_session.set("awaiting_joinee_email", True)
        




async def handle_file_upload(message: cl.Message,session):
    if message.elements:
        for file in message.elements:
            # ✅ file.path gives you the local path to the uploaded file
            await cl.Message(content=f"Thanks for uploading we will review it").send()
            # You can now open/read/process it like any local file
            with open(file.path, "rb") as f:
              fileContent = f.read()
            #   doc = Document(io.BytesIO(fileContent))
            #   file_validated = await file_validator(file,doc)
              file_validated = True
              if file_validated:
                team_name = session.get("team_name")
                if team_name:
                    template_id = ibm_cloud.upload_to_ibm_cos(team_name,fileContent)
                    return template_id
                  
    else:
        await cl.Message(
            content="Please upload your filled Word template here."
        ).send()


async def file_validator(file,doc):
    try:
        # Example: Check for a required heading or placeholder text
        required_texts = ["Buddy"]
        found_all = all(
            any(req in para.text for para in doc.paragraphs)
            for req in required_texts
        )
        if found_all:
            cl.user_session.set("awaiting_team_template",False)
            await cl.Message(content=f"Your template is validated successfully").send()
            return True
        if not found_all:
            await cl.Message(content="⚠️ The uploaded document is missing required fields. Please use the provided template.").send()
        return False
    except Exception as e:
        await cl.Message(content=f"❌ Failed to read the document. Error: {e}").send()
