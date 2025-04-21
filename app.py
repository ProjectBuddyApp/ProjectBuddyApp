import chainlit as cl
from docx import Document
import io
from constant import buddy_steps
import mongoclient
import ibm_cloud
import utils



@cl.on_message
async def main(message:str):
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
            cl.File(name="template",path="./onboarding_template.xlsx",display="inline",
        )]
        await cl.Message(content="Here you go", elements=elements).send()
        cl.user_session.set("awaiting_team_template", True)
        return

    #if some file is uploaded then redirect to handle_upload
    if cl.user_session.get("awaiting_team_template"):
        if message.elements:
            template_id = await handle_file_upload(message,cl.user_session)
            if template_id:
                cl.user_session.set("template_id", template_id)
                await save_to_mongo_db(cl.user_session)
                

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
    await cl.Message(content=f"Welcome to IBM!\nAre you a buddy or new joinee?").send()
    # Send buttons
    await cl.Message(
        content="Please choose:",
        actions=[
            cl.Action(
                name="role_selected",
                value="Buddy",
                label="👥 I'm a Buddy",
                payload={"role": "Buddy"}  # You can put anything here
            ),
            cl.Action(
                name="role_selected",
                value="Joinee",
                label="🧑‍💼 I'm a New Joinee",
                payload={"role": "Joinee"}
            ),
        ]
    ).send()

@cl.action_callback("role_selected")
async def handle_action(action: cl.Action):
    role = action.payload.get("role")
    if role == "Buddy":
        await cl.Message(content="Awesome! What’s your name, Buddy?").send()
        cl.user_session.set("awaiting_buddy_name", True)
    elif role == "Joinee":
        await cl.Message(content="Welcome aboard! Let's get you started. 🚀").send()


async def handle_file_upload(message: cl.Message,session):
    if message.elements:
        for file in message.elements:
            if not file.name.lower().endswith(".xlsx"):
             await cl.Message(content="❌ Please upload a excel document.").send()
             return
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
