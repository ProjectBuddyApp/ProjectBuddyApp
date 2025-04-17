import chainlit as cl
from docx import Document
import io


#continuously on loop
@cl.on_message
async def main(message:str):
    #our logic will be here
    #if some file is uploaded then redirect to handle_upload
    if message.elements:
        await handle_file_upload(message)
    
    #send a response back to the user
    await cl.Message(content=f"sure here is a message: {message.content}").send()

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
        await cl.Message(
            content="Awesome! Please download the pdf and fill it." \
            "\nOnce you've filled the template, please upload it below using the chat file upload option."
        ).send()

        elements = [
            cl.File(name="template",path="./dummy.docx",display="inline",
        )
        ]
        await cl.Message(content="Here you go", elements=elements).send()

    elif role == "Joinee":
        await cl.Message(content="Welcome aboard! Let's get you started. 🚀").send()


@cl.on_message
async def handle_file_upload(message: cl.Message):
    if message.elements:
        for file in message.elements:
            if not file.name.lower().endswith(".docx"):
             await cl.Message(content="❌ Please upload a docx document.").send()
             return
            # ✅ file.path gives you the local path to the uploaded file
            await cl.Message(content=f"Thanks for uploading we will review it").send()
            # You can now open/read/process it like any local file
            with open(file.path, "rb") as f:
              fileContent = f.read()
              doc = Document(io.BytesIO(fileContent))
              await file_validator(file,doc)
    else:
        await cl.Message(
            content="Please upload your filled Word template here."
        ).send()

async def file_validator(file,doc):
    try:
        await cl.Message(content="file.path").send()
        # Example: Check for a required heading or placeholder text
        required_texts = ["Buddy"]
        found_all = all(
            any(req in para.text for para in doc.paragraphs)
            for req in required_texts
        )
        if not found_all:
            await cl.Message(content="⚠️ The uploaded document is missing required fields. Please use the provided template.").send()
    except Exception as e:
        await cl.Message(content=f"❌ Failed to read the document. Error: {e}").send()
