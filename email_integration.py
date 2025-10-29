import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging Configuration
logger = logging.getLogger(__name__)

# Email configuration from environment variables
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USERNAME)

def send_email(to_email, subject, message_body, cc_email=None):
    """
    Send an email using SMTP.
    
    :param to_email: Recipient email address
    :param subject: Email subject
    :param message_body: Email body (HTML)
    :param cc_email: CC recipient email address (optional)
    :return: True if successful, False otherwise
    """
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        logger.error("Email credentials not set in environment variables")
        logger.info(f"Using default credentials from environment variables")
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = to_email
    if cc_email:
        msg['Cc'] = cc_email
    msg['Subject'] = subject
    
    # Add HTML body
    msg.attach(MIMEText(message_body, 'html'))
    
    try:
        # Connect to SMTP server
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        
        # Send email
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        server.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def notify_buddy_about_new_joinee(buddy_email, joinee_email, team_name, tasks=None):
    """
    Send an email to notify the buddy about a new joinee.
    
    :param buddy_email: Email of the buddy
    :param joinee_email: Email of the new joinee
    :param team_name: Name of the team
    :param tasks: List of tasks created for the new joinee
    :return: True if successful, False otherwise
    """
    # Extract username from email
    joinee_username = joinee_email.split('@')[0]
    
    # Create email subject
    subject = f"New Team Member: {joinee_username} has joined {team_name}"
    
    # Create email body
    body = f"""
    <html>
    <body>
        <h2>New Team Member Onboarding</h2>
        <p>Hello,</p>
        <p>A new team member, <b>{joinee_username}</b>, has joined the <b>{team_name}</b> team.</p>
        <p>You have been assigned as their buddy to help with the onboarding process.</p>
        
        <p>Contact information:</p>
        <ul>
            <li>Email: {joinee_email}</li>
        </ul>
    """
    
    if tasks:
        body += """
        <p>The following tasks have been created for them:</p>
        <ul>
        """
        for task in tasks:
            body += f"""
            <li><a href="{task['url']}">{task['title']}</a></li>
            """
        body += "</ul>"
    else:
        body += "<p>Please help them get started with their onboarding tasks.</p>"
    
    body += """
        <p>Thank you for your support!</p>
    </body>
    </html>
    """
    
    # Send email to buddy with CC to joinee
    return send_email(buddy_email, subject, body, cc_email=joinee_email)

def send_welcome_email_to_joinee(joinee_email, buddy_email, buddy_name, team_name, tasks=None):
    """
    Send a welcome email to the new joinee.
    
    :param joinee_email: Email of the new joinee
    :param buddy_email: Email of the buddy
    :param buddy_name: Name of the buddy
    :param team_name: Name of the team
    :param tasks: List of tasks created for the new joinee
    :return: True if successful, False otherwise
    """
    # Create email subject
    subject = f"Welcome to the {team_name} team!"
    
    # Create email body
    body = f"""
    <html>
    <body>
        <h2>Welcome to the Team!</h2>
        <p>Hello,</p>
        <p>Welcome to the <b>{team_name}</b> team! We're excited to have you join us.</p>
        
        <p>Your onboarding buddy is <b>{buddy_name}</b> ({buddy_email}). They will help you get settled in.</p>
    """
    
    if tasks:
        body += """
        <p>Here are your onboarding tasks:</p>
        <ul>
        """
        for task in tasks:
            body += f"""
            <li><a href="{task['url']}">{task['title']}</a></li>
            """
        body += "</ul>"
    
    body += """
        <p>Don't hesitate to reach out if you have any questions!</p>
        <p>Best regards,<br>The Team</p>
    </body>
    </html>
    """
    
    # Send email to joinee with CC to buddy
    return send_email(joinee_email, subject, body, cc_email=buddy_email)
