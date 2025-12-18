#!/usr/bin/env python

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

import dotenv

import MAIA

version = MAIA.__version__

TIMESTAMP = "{:%Y-%m-%d_%H-%M-%S}".format(datetime.datetime.now())


dotenv.load_dotenv()

EPILOG = dedent(
    """
    Example call:
    ::
        {filename} --email <recipient_email> --url <maia_platform_url>
    """.format(  # noqa: E501
        filename=Path(__file__).stem
    )
)


def get_arg_parser():
    parser = argparse.ArgumentParser(
        description="Send welcome email to new MAIA users",
        epilog=EPILOG,
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("--email", required=True, help="Recipient email address")
    parser.add_argument("--url", required=True, help="MAIA platform URL")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + version)

    return parser


def send_welcome_user_email(receiver_email, maia_url):
    """
    Send a welcome email to new MAIA users with platform information and getting started resources.

    Parameters
    ----------
    receiver_email : str
        The email address of the recipient
    maia_url : str
        The base URL of the MAIA platform
    """

    sender_email = os.environ["email_account"]
    message = MIMEMultipart()
    message["Subject"] = "Welcome to the MAIA Platform"
    message["From"] = "MAIA Team"
    message["To"] = receiver_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Welcome to MAIA!</p>
            <p>We're excited to have you join our platform. Your login details are your KTH credentials (unless otherwise provided), and you need to setup multifactor authentication to use the platform.
            Your MAIA account has been created and you can now access the platform at:<br>
            <a href="{}">{}</a></p>
            You can also setup the ssh connection here.

            <p>To see you workspace details and find the ssh connection and jupyterhub details, please visit the MAIA Dashboard at:<br>
            <a href="https://maia.app.cloud.cbh.kth.se/maia/">https://maia.app.cloud.cbh.kth.se/maia/</a></p>

            <p><b>Getting Started:</b></p>
            <ul>
                <li>Sign in to the MAIA Dashboard to access your projects</li>
                <li>Access your project workspace through JupyterLab</li>
                <li>Install additional packages using conda or pip</li>
            </ul>

            <p><b>Key Features:</b></p>
            <ul>
                <li>GPU support for machine learning workloads</li>
                <li>Persistent storage for your research data</li>
            </ul>

            <p><b>Resources:</b></p>
            <ul>
                <li>Support: Join our Discord community at, support in maia-support channel <a href="https://discord.gg/ZSe2dDzt">https://discord.gg/ZSe2dDzt</a></li>
                <li>Tutorial notebooks are available in your workspace</li>
            </ul>

            <br>
            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(  # noqa: E501, B950
        maia_url, maia_url
    )

    part1 = MIMEText(html, "html")
    message.attach(part1)

    port = 465  # For SSL
    password = os.environ["email_password"]

    # Create a secure SSL context
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(os.environ["email_smtp_server"], port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())


def main():
    args = get_arg_parser().parse_args()
    try:
        send_welcome_user_email(args.email, args.url)
        print(f"Welcome email sent successfully to {args.email}")
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
