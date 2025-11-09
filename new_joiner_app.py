import chainlit as cl
from rag_model import MyBuddy, AskQuestion, load_vector_db_for_selected_team, load_all_teams_data
import mongoclient
import utils
import task_handler
import email_integration

# Import startup_init to load vector data once at application startup
import startup_init


@cl.on_message
async def main(message:str):
    # Handle joinee name input
    if cl.user_session.get("awaiting_joinee_name"):
        joinee_name = message.content.strip()
        cl.user_session.set("awaiting_joinee_name", False)
        cl.user_session.set("joinee_name", joinee_name)
        
        # Ask for email after name
        await cl.Message(content=f"Great! Now please enter your IBM email address:").send()
        cl.user_session.set("awaiting_joinee_email", True)
        return
    
    # Handle joinee email input
    if cl.user_session.get("awaiting_joinee_email"):
        joinee_email = message.content
        if not utils.is_valid_email(joinee_email):
            await cl.Message(content="Please provide valid email address").send()
            return
            
        cl.user_session.set("awaiting_joinee_email", False)
        cl.user_session.set("joinee_email", joinee_email)
        joinee_name = cl.user_session.get("joinee_name")
        
        # Get team and buddy information from team_details
        selected_team = cl.user_session.get("selected_team")
        
        # Get team details to find buddy information
        team_details = mongoclient.get_team_details(selected_team, "teams")
        team_type = "teams"
        if not team_details:
            team_details = mongoclient.get_team_details(selected_team, "product")
            team_type = "product"
        
        if not team_details:
            await cl.Message(content="❌ Team details not found. Please contact your administrator.").send()
            return
        
        buddy_name = team_details.get("buddy_name")
        buddy_email = team_details.get("buddy_email")
        
        # Display welcome message to joinee FIRST
        await cl.Message(
            f"🎉 Welcome to the **{selected_team}** team!\n\n"
            f"Your onboarding buddy is **{buddy_name}**, "
            f"and their W3 ID is `{buddy_email}`.\n\n"
            f"They'll help you get settled in — don't hesitate to reach out!"
        ).send()
        
        # Important GitHub access notice BEFORE creating issues
        await cl.Message(
            content="⚠️ **Important: GitHub Access Required**\n\n"
                    "Please ensure you have GitHub Enterprise access.\n\n"
                    "**If you don't have access yet:**\n"
                    "1. 🤝 Connect with your buddy for assistance\n"
                    "2. 📚 Or refer to the access guide: [CICS Wiki - Main Page](https://cicswiki.hursley.ibm.com:9443/wiki/Main_Page)\n\n"
                    "Once you have access, your GitHub issues will be visible and you can start tracking your onboarding tasks! ✅"
        ).send()
        
        # Create GitHub tasks (this will send messages for each issue)
        tasks = await task_handler.create_github_onboarding_tasks(selected_team, team_type, joinee_name)
        
        # Extract GitHub issue URLs from tasks
        github_issues = [task.get('url') for task in tasks if task.get('url')]
        
        # Save new joiner information to MongoDB
        mongoclient.insert_new_joiner(
            joinee_name=joinee_name,
            joinee_email=joinee_email,
            team_name=selected_team,
            buddy_email=buddy_email,
            buddy_name=buddy_name,
            github_issues=github_issues
        )
        
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
    if not cl.user_session.get("awaiting_joinee_email"):
        user_question = message.content.strip()
        print('Calling AskQuestion.')
        response = AskQuestion(user_question)
        await cl.Message(content=response).send()


@cl.on_chat_start
async def start():
    # Vector data is already loaded at application startup via startup_init module
    await cl.Message(
        content="🎉 **Welcome to IBM!**\n\n"
                "We're thrilled to have you join our team! 🌟\n\n"
                "This is the beginning of an exciting journey, and we're here to make your onboarding experience "
                "smooth, engaging, and memorable. You'll be paired with a dedicated buddy who will guide you "
                "every step of the way.\n\n"
                "**Let's get started!** 🚀"
    ).send()
    
    # Get all teams from team_details collection
    team_names = mongoclient.get_all_teams_from_team_details()
    print(team_names)
    options = [cl.Action(name="team_select", label=str(name), value=str(name), payload={}) for name in team_names if name]
    await cl.Message(
        content="👥 **Select Your Team**\n\n"
                "Choose the team you'll be joining. Your buddy and onboarding resources are waiting for you!",
        actions=options
    ).send()


@cl.action_callback("team_select")
async def on_action(action: cl.Action):
    if action.name == "team_select":
        selected_team = action.label
        
        # Try to load vector database, but don't fail if it doesn't exist
        try:
            load_vector_db_for_selected_team(selected_team)
        except Exception as e:
            print(f"Warning: Could not load vector database for {selected_team}: {e}")
            # Continue anyway - Q&A will work with LLM fallback
        
        # Store selected team in session
        cl.user_session.set("selected_team", selected_team)
        
        # Ask for joinee's name first
        await cl.Message(
            content=f"✨ **Great choice!** You've selected the **{selected_team}** team.\n\n"
                    f"👤 **Let's get to know you!**\n\n"
                    f"Please enter your full name:"
        ).send()
        cl.user_session.set("awaiting_joinee_name", True)
