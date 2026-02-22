from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger


def send_email_approved_project_registration(
    project_name, project_owner, support_link, dashboard_url, smtp_sender_email, smtp_server, smtp_port, smtp_password
):

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
            <a href="{}namespaces/{}">{}namespaces/{}</a></p>
            
            <p>In the project workspace page you can find all the links and applications available for your project.</p>
            <br>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">{}</a></p>
            </p>

            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(project_name, dashboard_url, project_name, dashboard_url, project_name, support_link, support_link)

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


def send_email_user_registration_to_group(
    project_name, user_email, support_link, dashboard_url, smtp_sender_email, smtp_server, smtp_port, smtp_password
):

    message = MIMEMultipart()
    message["Subject"] = f"{project_name} Registration Approved"
    message["From"] = f"MAIA Admin Team <{smtp_sender_email}>"
    message["To"] = user_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>Your request to join the group <b>{}</b> has been approved and you can now access the the project workspace at:<br>
            <a href="{}namespaces/{}">{}namespaces/{}</a></p>
            
            <p>In the project workspace page you can find all the links and applications available for your project.</p>
            <br>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">{}</a></p>
            </p>

            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(project_name, dashboard_url, project_name, dashboard_url, project_name, support_link, support_link)

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
            server.sendmail(smtp_sender_email, user_email, message.as_string())
        logger.success(f"Project {project_name} registration email sent to {user_email}")
    except Exception as smtp_error:
        logger.error(f"SMTP error: {smtp_error}")
        raise


def confirm_request_registration_to_project(
    project_name, user_email, support_link, dashboard_url, smtp_sender_email, smtp_server, smtp_port, smtp_password
):
    message = MIMEMultipart()
    message["Subject"] = f"Confirmation of your request to join the MAIA project {project_name}"
    message["From"] = f"MAIA Admin Team <{smtp_sender_email}>"
    message["To"] = user_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>Your request to join the group <b>{}</b> in now being processed. You will receive a confirmation email once your request is approved.</p>
            <br>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">{}</a></p>
            </p>
            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(project_name, support_link, support_link)

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
            server.sendmail(smtp_sender_email, user_email, message.as_string())
            logger.success(f"Confirmation email sent to {user_email} for project {project_name}")
        return True
    except Exception as smtp_error:
        logger.error(f"SMTP error: {smtp_error}")
        return False


def confirm_request_registration_for_group(
    group_name, user_email, support_link, dashboard_url, smtp_sender_email, smtp_server, smtp_port, smtp_password
):
    message = MIMEMultipart()
    message["Subject"] = f"Confirmation of your request to register a new MAIA project {group_name}"
    message["From"] = f"MAIA Admin Team <{smtp_sender_email}>"
    message["To"] = user_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>Your request to register a new project <b>{}</b> is now being processed. You will receive a confirmation email once your request is approved.</p>
            <br>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">{}</a></p>
            </p>
            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(group_name, support_link, support_link)

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
            server.sendmail(smtp_sender_email, user_email, message.as_string())
            logger.success(f"Confirmation email sent to {user_email} for group {group_name}")
        return True
    except Exception as smtp_error:
        logger.error(f"SMTP error: {smtp_error}")
        return False


def send_email_approved_registration_email(email, temp_password, login_url, smtp_sender_email, smtp_server, smtp_port, smtp_password):
    message = MIMEMultipart()
    message["Subject"] = "Your MAIA Account has been approved"
    message["From"] = f"MAIA Admin Team <{smtp_sender_email}>"
    message["To"] = email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>Your MAIA account has been approved and you can now log in to MAIA at the following link: <a href="{}">{}</a></p>
            <p>Your temporary password is: {}</p>
            <p>Please change your password after logging in.</p>
            <br>
            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(login_url, login_url, temp_password)

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
            server.sendmail(smtp_sender_email, email, message.as_string())
            logger.success(f"Approved registration email sent to {email}")
        return True
    except Exception as smtp_error:
        logger.error(f"SMTP error: {smtp_error}")
        return False