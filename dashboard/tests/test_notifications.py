import os
import sys
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(root_dir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.core.settings")

from django.conf import settings


from MAIA.notifications import send_email_approved_project_registration


send_email_approved_project_registration(
    project_name="test-project",
    project_owner="test@example.com",
    discord_support_link=settings.DISCORD_SUPPORT_URL,
    dashboard_url=settings.HOSTNAME + "/maia/",
    smtp_sender_email=settings.SMTP_SENDER_EMAIL,
    smtp_server=settings.SMTP_SERVER,
    smtp_port=settings.SMTP_PORT,
    smtp_password=settings.SMTP_PASSWORD,
)