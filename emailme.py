import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


def email_me(address: str, subject="Automatic Email via Python", body="Hello"):
    """
    Sends an email using the Gmail SMTP server.

    Parameters:
    - address (str): The email address to send the email to.
    - subject (str): The subject of the email. Default is "Automatic Email via Python".
    - body (str): The body of the email. Default is "Hello".

    Returns
    - None
    """
    sender = address
    recipient = sender

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_username = sender
    smtp_password = os.getenv("SENHA_DE_APP_GMAIL")
    if smtp_password is None:
        raise EnvironmentError("SENHA_DE_APP_GMAIL is missing from .env file")
    assert smtp_password is not None

    mime_multipart = MIMEMultipart()
    mime_multipart["from"] = sender
    mime_multipart["to"] = recipient
    mime_multipart["subject"] = subject

    email_body = MIMEText(body, "plain", "utf-8")
    mime_multipart.attach(email_body)

    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(mime_multipart)
        print("Email enviado com sucesso!")
