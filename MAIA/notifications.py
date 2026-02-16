from __future__ import annotations

import argparse
import datetime
import os
import smtplib
import ssl
import sys
from argparse import RawTextHelpFormatter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from textwrap import dedent
from email.message import EmailMessage

from loguru import logger

def send_email_approved_project_registration(project_name, project_owner, discord_support_link, dashboard_url, smtp_sender_email, smtp_server, smtp_port, smtp_password):

    message = MIMEMultipart()
    message["Subject"] = f"{project_name} Project Approved"
    message["From"] = f"MAIA Admin Team <{smtp_sender_email}>"
    message["To"] = project_owner

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>Your project <b>{}</b> has been approved and you can now access the the project workspace at:<br>
            <a href="{}namespaces/{}/">{}namespaces/{}/</a></p>
            
            <p>In the project workspace page you can find all the links and applications available for your project.</p>
            <br>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">{}</a></p>
            </p>

            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(project_name, dashboard_url, project_name, dashboard_url, project_name, discord_support_link, discord_support_link)
    
    part1 = MIMEText(html, "html")
    message.attach(part1)

    _ = ssl.create_default_context()

    try:
        
        if not smtp_server or not smtp_sender_email or not smtp_password:
            raise ValueError("Missing required email environment variables.")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()  # identify ourselves to SMTP server
            server.starttls()  # encrypt the session
            server.login(smtp_sender_email, smtp_password)
            server.sendmail(smtp_sender_email, project_owner, message.as_string())
        logger.success(f"Project {project_name} registration email sent to {project_owner}")
    except Exception as smtp_error:
        logger.error(f"SMTP error: {smtp_error}")
        raise