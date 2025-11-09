import chainlit as cl
import mongoclient
import email_integration
import utils

# Import startup_init to load vector data once at application startup
import startup_init


@cl.on_message
async def main(message: str):
    # Handle buddy email input for login
    if cl.user_session.get("awaiting_buddy_login"):
        buddy_email = message.content
        if not utils.is_valid_email(buddy_email):
            await cl.Message(content="Please provide a valid email address").send()
            return
        
        cl.user_session.set("awaiting_buddy_login", False)
        
        # Get joiners assigned to this buddy
        joiners = mongoclient.get_joiners_by_buddy_email(buddy_email)
        
        if not joiners:
            await cl.Message(content="❌ No joiners found assigned to this email. Please check with your administrator.").send()
            return
        
        # Store buddy email in session
        cl.user_session.set("buddy_email", buddy_email)
        cl.user_session.set("buddy_name", joiners[0].get("buddy_name", "Buddy"))
        
        # Show dashboard
        await show_buddy_dashboard(buddy_email, joiners)
        return
    
    # Handle link input for sending to joiner
    if cl.user_session.get("awaiting_links_input"):
        links_text = message.content
        cl.user_session.set("awaiting_links_input", False)
        
        selected_joiner_email = cl.user_session.get("selected_joiner_email")
        buddy_email = cl.user_session.get("buddy_email")
        buddy_name = cl.user_session.get("buddy_name")
        
        # Send email with links
        result = email_integration.send_links_to_joiner(
            joiner_email=selected_joiner_email,
            buddy_email=buddy_email,
            buddy_name=buddy_name,
            links_text=links_text
        )
        
        if result:
            await cl.Message(content=f"✅ Important links have been sent to {selected_joiner_email}!").send()
        else:
            await cl.Message(content="❌ Failed to send email. Please try again.").send()
        
        # Show dashboard again
        joiners = mongoclient.get_joiners_by_buddy_email(buddy_email)
        await show_buddy_dashboard(buddy_email, joiners)
        return


async def show_buddy_dashboard(buddy_email, joiners):
    """Display the buddy dashboard with assigned joiners."""
    buddy_name = cl.user_session.get("buddy_name", "Buddy")
    
    # Create a warm, personalized greeting
    greeting = f"🎉 Welcome back, **{buddy_name}**!\n\n"
    
    if len(joiners) == 0:
        greeting += "📊 **Your Dashboard**\n\n" \
                   "You don't have any assigned joiners at the moment. " \
                   "When new team members join, they'll appear here and you'll be notified!\n\n" \
                   "Stay tuned for your next opportunity to make a difference! 🌟"
    elif len(joiners) == 1:
        greeting += "📊 **Your Dashboard**\n\n" \
                   f"You're currently guiding **1 new team member** through their onboarding journey. " \
                   f"Your support is making their transition smooth and welcoming! 🚀"
    else:
        greeting += "📊 **Your Dashboard**\n\n" \
                   f"You're currently supporting **{len(joiners)} new team members**! " \
                   f"Your dedication to helping multiple joiners is truly appreciated. " \
                   f"You're building a stronger team, one person at a time! 💪"
    
    await cl.Message(content=greeting).send()
    
    # Create action buttons for each joiner
    joiner_actions = []
    for joiner in joiners:
        joiner_email = joiner.get("joinee_email")
        team_name = joiner.get("team_name")
        joined_date = joiner.get("joined_date", "Unknown")[:10]  # Get date only
        
        joiner_actions.append(
            cl.Action(
                name="view_joiner",
                label=f"{joiner_email} ({team_name})",
                payload={
                    "joiner_email": joiner_email,
                    "team_name": team_name,
                    "joined_date": joined_date
                }
            )
        )
    
    await cl.Message(
        content="👥 **Your Assigned Joiners:**\n\nClick on a joiner to view details and manage their onboarding:",
        actions=joiner_actions
    ).send()


@cl.on_chat_start
async def start():
    """Start the buddy application."""
    await cl.Message(
        content="👋 **Welcome to Your Buddy Dashboard!**\n\n"
                "🌟 Thank you for being an amazing buddy and helping new team members feel at home!\n\n"
                "Your guidance and support make all the difference in creating a welcoming onboarding experience. "
                "This dashboard is your command center to track, support, and celebrate the journey of your assigned joiners.\n\n"
                "✨ **Ready to make an impact?**\n\n"
                "Please enter your email address to access your personalized dashboard:"
    ).send()
    cl.user_session.set("awaiting_buddy_login", True)


@cl.action_callback("view_joiner")
async def handle_view_joiner(action: cl.Action):
    """Handle viewing a specific joiner's details."""
    joiner_email = action.payload.get("joiner_email")
    team_name = action.payload.get("team_name")
    joined_date = action.payload.get("joined_date")
    
    # Store selected joiner in session
    cl.user_session.set("selected_joiner_email", joiner_email)
    
    # Get full joiner details
    joiner = mongoclient.get_joiner_by_email(joiner_email)
    
    if not joiner:
        await cl.Message(content="❌ Joiner details not found.").send()
        return
    
    # Display joiner details
    github_issues = joiner.get("github_issues", [])
    status = joiner.get("status", "Active")
    
    details_message = (
        f"📋 **Joiner Details**\n\n"
        f"**Email:** {joiner_email}\n"
        f"**Team:** {team_name}\n"
        f"**Joined Date:** {joined_date}\n"
        f"**Status:** {status}\n\n"
        f"**GitHub Issues ({len(github_issues)}):**\n"
    )
    
    if github_issues:
        for i, issue_url in enumerate(github_issues, 1):
            details_message += f"{i}. {issue_url}\n"
    else:
        details_message += "No GitHub issues assigned yet.\n"
    
    await cl.Message(content=details_message).send()
    
    # Show action options
    await cl.Message(
        content="**What would you like to do?**",
        actions=[
            cl.Action(
                name="joiner_action",
                label="📧 Send Important Links",
                payload={"action": "send_links", "joiner_email": joiner_email}
            ),
            cl.Action(
                name="joiner_action",
                label="🔙 Back to Dashboard",
                payload={"action": "back_to_dashboard"}
            )
        ]
    ).send()


@cl.action_callback("joiner_action")
async def handle_joiner_action(action: cl.Action):
    """Handle actions for a specific joiner."""
    action_type = action.payload.get("action")
    
    if action_type == "send_links":
        joiner_email = action.payload.get("joiner_email")
        await cl.Message(
            content=f"📧 **Send Important Links to {joiner_email}**\n\n"
                    f"Please enter the links you want to share (one per line or separated by commas):\n\n"
                    f"Example:\n"
                    f"https://confluence.company.com/onboarding\n"
                    f"https://wiki.company.com/team-resources\n"
                    f"https://docs.company.com/getting-started"
        ).send()
        cl.user_session.set("awaiting_links_input", True)
        cl.user_session.set("selected_joiner_email", joiner_email)
    
    elif action_type == "back_to_dashboard":
        buddy_email = cl.user_session.get("buddy_email")
        joiners = mongoclient.get_joiners_by_buddy_email(buddy_email)
        await show_buddy_dashboard(buddy_email, joiners)