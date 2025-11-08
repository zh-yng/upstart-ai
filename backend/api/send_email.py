import smtplib, ssl
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

port = int(os.getenv("SMTP_PORT", "465"))  # For SSL
smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
sender_email = os.getenv("SENDER_EMAIL")

password = os.getenv("SENDER_PASSWORD")

def sendEmail(receiver_email, message):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)

