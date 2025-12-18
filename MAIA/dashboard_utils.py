from __future__ import annotations

import asyncio
import email
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
from kubernetes import config
from minio import Minio
from pyhelm3 import Client

from MAIA.keycloak_utils import get_groups_in_keycloak
from MAIA.kubernetes_utils import generate_kubeconfig, get_namespaces
from MAIA_scripts.MAIA_install_project_toolkit import verify_installed_maia_toolkit


def verify_gpu_availability(global_existing_bookings, new_booking, gpu_specs):
    """
    Verify GPU availability for a new booking.

    Parameters
    ----------
    global_existing_bookings : list of dict
        A list of existing bookings where each booking is represented as a dictionary
        with keys "gpu", "start_date", and "end_date".
    new_booking : dict
        A dictionary representing the new booking with keys "gpu", "start_date", and "end_date".
    gpu_specs : list of dict
        A list of GPU specifications where each specification is represented as a dictionary
        with keys "name", "replicas", and "count".

    Returns
    -------
    overlapping_time_points : list of datetime
        A list of time points where bookings overlap.
    gpu_availability_per_slot : list of int
        A list of available GPU counts for each overlapping time slot.
    total_gpus : int
        The total number of GPUs available for the specified GPU type.
    """

    gpu_name = new_booking["gpu"]

    gpu_count = 0
    gpu_replicas = 0

    for gpu_spec in gpu_specs:
        if gpu_spec["name"] == gpu_name:

            gpu_replicas = gpu_spec["replicas"]
            gpu_count = gpu_spec["count"]

    overlapping_allocations = []
    for existing_booking in global_existing_bookings:
        if existing_booking["gpu"] == gpu_name:
            if isinstance(existing_booking["start_date"], str):
                existing_booking_start = datetime.strptime(existing_booking["start_date"], "%Y-%m-%d %H:%M:%S")
            else:
                existing_booking_start = existing_booking["start_date"]

            if isinstance(existing_booking["end_date"], str):
                existing_booking_end = datetime.strptime(existing_booking["end_date"], "%Y-%m-%d %H:%M:%S")
            else:
                existing_booking_end = existing_booking["end_date"]

            new_booking_start = datetime.strptime(new_booking["starting_time"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=existing_booking_start.tzinfo
            )
            new_booking_end = datetime.strptime(new_booking["ending_time"], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=existing_booking_end.tzinfo
            )

            if new_booking_start >= existing_booking_end or new_booking_end <= existing_booking_start:
                continue
            if new_booking_start <= existing_booking_start and new_booking_end >= existing_booking_start:
                overlapping_allocations.append([existing_booking_start, existing_booking_end])
            elif new_booking_start <= existing_booking_start and new_booking_end <= existing_booking_end:
                overlapping_allocations.append([existing_booking_start, new_booking_end])
            elif new_booking_start >= existing_booking_start and new_booking_end >= existing_booking_end:
                overlapping_allocations.append([new_booking_start, existing_booking_end])
            elif new_booking_start >= existing_booking_start and new_booking_end <= existing_booking_end:
                overlapping_allocations.append([new_booking_start, new_booking_end])

    overlapping_time_points = []
    gpu_availability_per_slot = []
    for overlapping_allocation in overlapping_allocations:
        overlapping_time_points.append(overlapping_allocation[0])
        overlapping_time_points.append(overlapping_allocation[1])

    if len(global_existing_bookings) == 0:
        overlapping_time_points.append(datetime.strptime(new_booking["starting_time"], "%Y-%m-%d %H:%M:%S"))
        overlapping_time_points.append(datetime.strptime(new_booking["ending_time"], "%Y-%m-%d %H:%M:%S"))
    else:
        overlapping_time_points.append(
            datetime.strptime(new_booking["starting_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=new_booking_start.tzinfo)
        )
        overlapping_time_points.append(
            datetime.strptime(new_booking["ending_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=new_booking_end.tzinfo)
        )
    overlapping_time_points = sorted(set(overlapping_time_points))

    for overlapping_time_point in overlapping_time_points[:-1]:
        overlapping_window = [
            overlapping_time_point,
            overlapping_time_points[overlapping_time_points.index(overlapping_time_point) + 1],
        ]
        overlapping_window_start = overlapping_window[0]
        overlapping_window_end = overlapping_window[1]

        available_gpus = gpu_replicas * gpu_count
        gpu_availability_per_slot.append(available_gpus)
        for existing_booking in global_existing_bookings:
            if isinstance(existing_booking["start_date"], str):
                existing_booking_start = datetime.strptime(existing_booking["start_date"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=new_booking_start.tzinfo
                )
            else:
                existing_booking_start = existing_booking["start_date"]

            if isinstance(existing_booking["end_date"], str):
                existing_booking_end = datetime.strptime(existing_booking["end_date"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=new_booking_end.tzinfo
                )
            else:
                existing_booking_end = existing_booking["end_date"]

            if existing_booking_start < overlapping_window_end and existing_booking_end > overlapping_window_start:
                available_gpus -= 1
        gpu_availability_per_slot[-1] = available_gpus

    return overlapping_time_points, gpu_availability_per_slot, gpu_replicas * gpu_count


def verify_gpu_booking_policy(existing_bookings, new_booking, global_existing_bookings, gpu_specs):
    """
    Verify GPU booking policy to ensure the new booking does not exceed the allowed days and GPU availability.

    Parameters
    ----------
    existing_bookings : list
        A list of existing booking objects with `start_date` and `end_date` attributes.
    new_booking : dict
        A dictionary containing the `starting_time` and `ending_time` of the new booking in "%Y-%m-%d %H:%M:%S" format.
    global_existing_bookings : list
        A list of all existing bookings globally.
    gpu_specs : dict
        A dictionary containing the specifications of the GPUs.

    Returns
    -------
    bool
        True if the booking policy is verified, False otherwise.
    str or None
        An error message if the booking policy is not verified, None otherwise.
    """

    ending_time = datetime.strptime(new_booking["ending_time"], "%Y-%m-%d %H:%M:%S")
    starting_time = datetime.strptime(new_booking["starting_time"], "%Y-%m-%d %H:%M:%S")

    for booking in existing_bookings:
        if booking.start_date <= datetime.now(tz=booking.start_date.tzinfo) and booking.end_date >= datetime.now(
            tz=booking.end_date.tzinfo
        ):
            return False, "There is an active booking, you cannot book a new one while another is active."
        if booking.start_date <= datetime.now(tz=booking.start_date.tzinfo) and booking.end_date <= datetime.now(
            tz=booking.end_date.tzinfo
        ):
            # Ensure starting_time is timezone-aware to match booking.end_date
            if booking.end_date.tzinfo is not None and starting_time.tzinfo is None:
                starting_time_tz = starting_time.replace(tzinfo=booking.end_date.tzinfo)
            else:
                starting_time_tz = starting_time
            if (starting_time_tz - booking.end_date).days < 14:
                return (
                    False,
                    "The time between your old booking and the new booking must be at least 14 days. You can start a new booking on {}.".format(
                        booking.end_date + timedelta(days=14)
                    ),
                )
        if booking.start_date >= datetime.now(tz=booking.start_date.tzinfo) and booking.end_date >= datetime.now(
            tz=booking.end_date.tzinfo
        ):
            return False, "You already have a planned booking [{} - {}], you cannot book a new one.".format(
                booking.start_date, booking.end_date
            )

    new_booking_days = (ending_time - starting_time).days

    if new_booking_days <= 0:
        return False, "The booking must be at least one day long."

    if new_booking_days > 14:
        return False, "The booking cannot exceed 14 days."
    # Verify that the sum of existing bookings and the new booking does not exceed 60 days
    # if total_days + new_booking_days > 60:
    #    return False, "The total number of days for all bookings cannot exceed 60 days."

    overlapping_time_slots, gpu_availability_per_slot, total_replicas = verify_gpu_availability(
        global_existing_bookings=global_existing_bookings, new_booking=new_booking, gpu_specs=gpu_specs
    )

    for idx, gpu_availability in enumerate(gpu_availability_per_slot):
        if gpu_availability == 0:
            error_msg = "GPU not available between the selected time slots: {} - {}".format(
                overlapping_time_slots[idx], overlapping_time_slots[idx + 1]
            )
            return False, error_msg

    return True, None


def send_maia_info_email(receiver_email, register_project_url, register_user_url, discord_support_link):
    """
    Send an email with registration information for the MAIA platform.
    Parameters
    ----------
    receiver_email : str
        The email address of the recipient.
    register_project_url : str
        The URL for project registration.
    register_user_url : str
        The URL for user registration.
    discord_support_link : str
        The URL for the MAIA support Discord.
    Returns
    -------
    None
    """

    sender_email = os.environ["email_account"]
    message = MIMEMultipart()
    message["Subject"] = "Registration Information for the MAIA Platform"
    message["From"] = f"MAIA Admin Team <{sender_email}>"
    message["To"] = receiver_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Thank you for your interest in the MAIA platform. Below are the steps to register:</p>
            <p><b>Project Registration:</b><br>
            If you are starting a research work and you want to have it hosted in MAIA, please first register your project here:<br>
            <a href="{}">MAIA Project Registration</a></p>
            <p><b>User Registration:</b><br>
            To create a user account, an active project must be available to select. Once a project is registered, you can sign up for an account linked to that project here:<br>
            <a href="{}">MAIA User Registration</a></p>
            <p>If you have any questions or need further assistance, feel free to join our Discord community:<br>
            <a href="{}">MAIA Support Discord</a></p>
            <br>
            <p>Best regards,</p>
            <p>The MAIA Admin Team</p>
        </body>
    </html>
    """.format(  # noqa: B950
        register_project_url, register_user_url, discord_support_link
    )

    # Turn these into plain/html MIMEText objects
    part1 = MIMEText(html, "html")

    message.attach(part1)

    port = 587  # For SSL
    password = os.environ["email_password"]

    # Create a secure SSL context
    # context = ssl.create_default_context()

    with smtplib.SMTP(os.environ["email_smtp_server"], port) as server:
        server.ehlo()  # identify ourselves to SMTP server
        server.starttls()  # encrypt the session
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())


def verify_minio_availability(settings):
    """
    Verifies the availability of a MinIO server.

    Parameters
    ----------
    settings : object
        An object containing the MinIO configuration settings.

        MINIO_URL : str
            The URL of the MinIO server.
        MINIO_ACCESS_KEY : str
            The access key for the MinIO server.
        MINIO_SECRET_KEY : str
            The secret key for the MinIO server.
        BUCKET_NAME : str
            The name of the bucket to check for existence.

    Returns
    -------
    bool
        True if the MinIO server is available and the bucket exists, False otherwise.
    """
    try:
        client = Minio(
            settings.MINIO_URL,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        client.bucket_exists(settings.BUCKET_NAME)
        minio_available = True
    except Exception as e:
        print(e)
        minio_available = False

    return minio_available


def send_approved_registration_email(receiver_email, login_url, temp_password):
    """
    Sends an email to notify the user that their MAIA account registration has been approved.

    Parameters
    ----------
    receiver_email : str
        The email address of the recipient.
    login_url : str
        The URL where the user can log in to MAIA.
    temp_password : str
        The temporary password assigned to the user.

    Raises
    ------
    KeyError
        If the environment variables 'email_account' or 'email_password' are not set.
    smtplib.SMTPException
        If there is an error sending the email.
    """

    sender_email = os.environ["email_account"]
    message = MIMEMultipart()
    message["Subject"] = "Account Registration Approved"
    message["From"] = f"MAIA Registration <{sender_email}>"
    message["To"] = receiver_email

    html = """\
    <html>
        <head></head>
        <body>
            <p>Your MAIA Account has been approved.</p>
            <p>Log in to MAIA at the following link: <a href="{}">MAIA</a></p>
            <p>Your temporary password is: {}</p>
            <p>Please change your password after logging in.</p>
            <br>
            <p>Best Regards,</p>
            <p>MAIA Admin Team</p>
        </body>
    </html>
    """.format(
        login_url, temp_password
    )

    # Turn these into plain/html MIMEText objects
    part1 = MIMEText(html, "html")

    message.attach(part1)

    port = 587  # For SSL
    password = os.environ["email_password"]

    # Create a secure SSL context
    # context = ssl.create_default_context()

    with smtplib.SMTP(os.environ["email_smtp_server"], port) as server:
        server.ehlo()  # identify ourselves to SMTP server
        server.starttls()  # encrypt the session
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())


def send_discord_message(username, namespace, url, project_registration=False):
    """
    Sends a message to a Discord webhook to request a MAIA account.

    Parameters
    ----------
    username : str
        The username of the person requesting the account.
    namespace : str
        The project namespace for which the account is being requested.
    url : str
        The Discord webhook URL to which the message will be sent.
    project_registration : bool, optional
        If True, indicates that a project registration is also being requested (default is False).

    Raises
    ------
    requests.exceptions.HTTPError
        If the HTTP request returned an unsuccessful status code.

    Prints
    ------
    str
        Success message with the HTTP status code if the payload is delivered successfully.
    str
        Error message if the HTTP request fails.
    """
    data = {"content": f"{username} is requesting a MAIA account for the project {namespace}.", "username": "MAIA-Bot"}

    data["embeds"] = [{"description": "MAIA User Registration Request", "title": "MAIA Account Request"}]
    if project_registration:
        data["embeds"][0]["description"] = "MAIA Project Registration Request"
        data["embeds"][0]["title"] = "MAIA Project Registration Request"
        data["content"] = f"{username} is requesting a MAIA account and a new project registration for {namespace}."

    result = requests.post(url, json=data)

    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)
    else:
        print("Payload delivered successfully, code {}.".format(result.status_code))


def get_pending_projects(settings, maia_project_model):
    """
    Retrieve a list of pending projects that are not in the active groups.

    Parameters
    ----------
    settings : dict
        Configuration settings required to access Keycloak.
    maia_project_model : Django model
        The Django model representing the MAIA projects.

    Returns
    -------
    list
        A list of namespaces of pending projects.
    """
    pending_projects = []
    try:
        active_groups = get_groups_in_keycloak(settings)

        for project in maia_project_model.objects.all():
            if project.namespace not in active_groups.values():
                pending_projects.append(project.namespace)
    except Exception:
        ...

    return pending_projects


def get_user_table(settings, maia_user_model, maia_project_model):
    """
    Retrieve user and project information from Keycloak and Minio, and organize it into a dictionary.

    Parameters
    ----------
    settings : object
        An object containing configuration settings such as OIDC and Minio credentials.
    maia_user_model : Django model
        The Django model representing MAIA users.
    maia_project_model : Django model
        The Django model representing MAIA projects.

    Returns
    -------
    tuple
        A tuple containing:
        - users_to_register_in_group (dict): Users to be registered in Keycloak groups.
        - users_to_register_in_keycloak (list): Users to be registered in Keycloak.
        - maia_group_dict (dict): Dictionary containing group information including users, conda environments, and project details.
        - users_to_remove_from_group (dict): Users to be removed from Keycloak groups.
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
    users_to_register_in_group = {}

    groups = keycloak_admin.get_groups()

    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}

    pending_projects = get_pending_projects(settings=settings, maia_project_model=maia_project_model)

    maia_group_dict = {}

    try:
        client = Minio(
            settings.MINIO_URL,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )

        minio_envs = [env.object_name[: -len("_env")] for env in list(client.list_objects(settings.BUCKET_NAME))]
    except Exception:
        minio_envs = []

    for maia_group in maia_groups:
        if maia_groups[maia_group] == "users":
            continue
        users = keycloak_admin.get_group_members(group_id=maia_group)

        admin_users = []
        cpu_limit = None
        memory_limit = None
        date = None
        cluster = None
        gpu = None
        environment = None
        conda_envs = []

        if maia_project_model.objects.filter(namespace=maia_groups[maia_group]).exists():
            project = maia_project_model.objects.filter(namespace=maia_groups[maia_group]).first()

            admin_users = [project.email]
            cpu_limit = project.cpu_limit
            memory_limit = project.memory_limit
            date = project.date
            cluster = project.cluster
            gpu = project.gpu
            environment = project.minimal_env

        if maia_groups[maia_group] in minio_envs:
            conda_envs.append(maia_groups[maia_group])
        else:
            conda_envs.append("N/A")

        group_users = []
        for user in users:
            if user["username"] in admin_users:
                group_users.append(user["email"] + " [Project Admin]")
            else:
                group_users.append(user["email"])

        maia_group_dict[maia_groups[maia_group]] = {
            "users": group_users,
            "conda": conda_envs,
            "admin_users": admin_users,
            "cpu_limit": cpu_limit,
            "memory_limit": memory_limit,
            "date": date,
            "cluster": cluster,
            "gpu": gpu,
            "environment": environment,
        }

    for pending_project in pending_projects:
        conda_envs = []
        if pending_project in minio_envs:
            conda_envs.append(pending_project)
        else:
            conda_envs.append("N/A")

        users = []

        for user in maia_user_model.objects.all():
            if user.namespace and pending_project in user.namespace.split(","):
                users.append(user.email)

        project = maia_project_model.objects.filter(namespace=pending_project).first()
        maia_group_dict[pending_project] = {
            "users": users,
            "pending": True,
            "conda": conda_envs,
            "admin_users": [],
            "cpu_limit": project.cpu_limit,
            "memory_limit": project.memory_limit,
            "date": project.date,
            "cluster": "N/A",
            "gpu": project.gpu,
            "environment": "Minimal",
        }

    users_to_register_in_keycloak = []
    users_to_remove_from_group = {}

    for user in maia_user_model.objects.all():
        user_groups = []
        user_in_keycloak = False
        for keycloak_user in keycloak_admin.get_users():

            if "email" in keycloak_user:
                if keycloak_user["email"] == user.email:
                    user_in_keycloak = True
                    user_keycloak_groups = keycloak_admin.get_user_groups(user_id=keycloak_user["id"])
                    for user_keycloak_group in user_keycloak_groups:
                        if user_keycloak_group["name"].startswith("MAIA:"):
                            user_groups.append(user_keycloak_group["name"][len("MAIA:") :])
        if not user_in_keycloak:
            users_to_register_in_keycloak.append(user.email)

        requested_namespaces = user.namespace.split(",") if user.namespace else []
        for requested_namespace in requested_namespaces:
            if requested_namespace not in user_groups and requested_namespace != "N/A":
                if user.email not in users_to_register_in_group:
                    users_to_register_in_group[user.email] = [requested_namespace]
                else:
                    users_to_register_in_group[user.email].append(requested_namespace)
            for user_group in user_groups:
                if user_group not in requested_namespaces:
                    if user.email not in users_to_remove_from_group:
                        users_to_remove_from_group[user.email] = [user_group]
                    else:
                        users_to_remove_from_group[user.email].append(user_group)

    return users_to_register_in_group, users_to_register_in_keycloak, maia_group_dict, users_to_remove_from_group


def register_cluster_for_project_in_db(project_model, settings, namespace, cluster):
    """
    Registers a cluster for a project in the database.
    This function connects to Keycloak to retrieve group information and
    associates a cluster with a project based on the provided namespace.
    If the project already exists, it updates the cluster information;
    otherwise, it creates a new project entry with the specified cluster.

    Parameters
    ----------
    project_model : Django model
        The Django model representing the project.
    settings : object
        An object containing configuration settings.
    namespace : str
        The namespace associated with the project.
    cluster : str
        The cluster to be registered for the project.

    Returns
    -------
    None
    """

    keycloak_connection = KeycloakOpenIDConnection(
        server_url=settings.OIDC_SERVER_URL,
        username=settings.OIDC_USERNAME,
        password="",
        realm_name=settings.OIDC_REALM_NAME,
        client_id=settings.OIDC_RP_CLIENT_ID,
        client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
        verify=False,
    )

    group_id = namespace
    keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
    groups = keycloak_admin.get_groups()

    maia_groups = {group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")}
    for maia_group in maia_groups:
        if maia_groups[maia_group].lower().replace("_", "-") == namespace:
            group_id = maia_groups[maia_group]

    print("Registering Existing Cluster for Group: ", group_id)

    if project_model.objects.filter(namespace=group_id).exists():
        project = project_model.objects.filter(namespace=group_id).first()
        if project:
            project.cluster = cluster
            project.save()
    else:
        project_model.objects.create(namespace=group_id, cluster=cluster, memory_limit="2 Gi", cpu_limit="2")


def update_user_table(form, user_model, maia_user_model, project_model):
    """
    Updates user and project information based on the cleaned data from a form.

    Parameters
    ----------
    form : Form
        The form containing cleaned data to update the user and project models.
    user_model : Model
        The user model to query and update user information.
    maia_user_model : Model
        The MAIA user model to query and update namespace information.
    project_model : Model
        The project model to query and update project information.
    Notes
    -----
    - The function processes entries in the form's cleaned data to update user namespaces and project details.
    - User namespaces are updated or created in the `maia_user_model` based on the user's email.
    - Project details are updated or created in the `project_model` based on the namespace.
    """

    project_entries = ["memory_limit", "cpu_limit", "date", "cluster", "gpu", "minimal_environment"]

    namespace_list = []

    for entry in form.cleaned_data:
        if entry.startswith("namespace_"):
            user = user_model.objects.filter(email=entry.replace("namespace_", "")).first()
            if user:
                user_id = user.id
                if maia_user_model.objects.filter(id=user_id).exists():
                    namespace = form.cleaned_data[entry]
                    # namespaces = []
                    # for namespace in namespace_list:
                    #    if namespace.endswith(" (Pending)"):
                    #        namespaces.append(namespace[:-len(" (Pending)")])
                    #    else:
                    #        namespaces.append(namespace)
                    maia_user_model.objects.filter(id=user_id).update(namespace=namespace)
                else:
                    if user_id is not None:
                        if user_model.objects.filter(id=user_id).exists():
                            namespace = form.cleaned_data[entry]
                            # namespaces = []
                            # for namespace in namespace_list:
                            #    if namespace.endswith(" (Pending)"):
                            #        namespaces.append(namespace[:-len(" (Pending)")])
                            #    else:
                            #        namespaces.append(namespace)
                            maia_user_model.objects.create(id=user_id, namespace=namespace)
                        else:
                            namespace = form.cleaned_data[entry]
                            # namespaces = []
                            # for namespace in namespace_list:
                            #    if namespace.endswith(" (Pending)"):
                            #        namespaces.append(namespace[:-len(" (Pending)")])
                            #    else:
                            #        namespaces.append(namespace)
                            maia_user_model.objects.create(id=user_id, namespace=namespace)
        for project_entry in project_entries:
            if entry.startswith(project_entry + "_"):
                namespace = entry[len(project_entry + "_") :]
                namespace_list.append(namespace)

    for namespace in namespace_list:
        # namespaced_entries = [entry for entry in form.cleaned_data if entry.endswith(namespace)]
        if project_model.objects.filter(namespace=namespace).exists():
            project_model.objects.filter(namespace=namespace).update(
                memory_limit=form.cleaned_data["memory_limit_" + namespace],
                cpu_limit=form.cleaned_data["cpu_limit_" + namespace],
                date=form.cleaned_data["date_" + namespace],
                cluster=form.cleaned_data["cluster_" + namespace],
                gpu=form.cleaned_data["gpu_" + namespace],
                minimal_env=form.cleaned_data["minimal_environment_" + namespace],
            )
        else:
            project_model.objects.create(
                namespace=namespace,
                memory_limit=form.cleaned_data["memory_limit_" + namespace],
                cpu_limit=form.cleaned_data["cpu_limit_" + namespace],
                date=form.cleaned_data["date_" + namespace],
                cluster=form.cleaned_data["cluster_" + namespace],
                gpu=form.cleaned_data["gpu_" + namespace],
                minimal_env=form.cleaned_data["minimal_environment_" + namespace],
            )


def get_project(group_id, settings, maia_project_model, is_namespace_style=False):
    """
    Retrieve project details and associated cluster ID based on the group ID.

    Parameters
    ----------
    group_id : str
        The ID of the group to search for.
    settings : object
        The settings object containing OIDC configuration.
    maia_project_model : Django model
        The Django model representing MAIA projects.
    is_namespace_style : bool, optional
        Flag indicating whether the group ID is in namespace style (default is False).

    Returns
    -------
    tuple
        A tuple containing:
        - namespace_form (dict): A dictionary with project details and resource limits.
        - cluster_id (str or None): The ID of the associated cluster, or None if not applicable.
    """

    cluster_id = None

    for project in maia_project_model.objects.all():
        if is_namespace_style:
            if str(project.namespace).lower().replace("_", "-") == group_id:
                keycloak_connection = KeycloakOpenIDConnection(
                    server_url=settings.OIDC_SERVER_URL,
                    username=settings.OIDC_USERNAME,
                    password="",
                    realm_name=settings.OIDC_REALM_NAME,
                    client_id=settings.OIDC_RP_CLIENT_ID,
                    client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
                    verify=False,
                )

                keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
                groups = keycloak_admin.get_groups()

                maia_groups = {
                    group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")
                }

                group_users = []

                for maia_group in maia_groups:
                    if maia_groups[maia_group] == group_id:
                        users = keycloak_admin.get_group_members(group_id=maia_group)

                        for user in users:
                            group_users.append(user["email"])

                namespace_form = {
                    "group_ID": group_id,
                    "group_subdomain": group_id.lower().replace("_", "-"),
                    "users": group_users,
                    "resources_limits": {
                        "memory": [str(int(int(project.memory_limit[: -len(" Gi")]) / 2)) + " Gi", project.memory_limit],
                        "cpu": [str(int(int(project.cpu_limit) / 2)), project.cpu_limit],
                    },
                    "environment": project.minimal_env,
                }
                if project.gpu != "N/A" and project.gpu != "NO":
                    namespace_form["gpu"] = "1"

                if project.conda != "N/A" and project.conda is not None:
                    namespace_form["minio_env_name"] = group_id + "_env"

                cluster_id = project.cluster
                if cluster_id == "N/A":
                    cluster_id = None
                return namespace_form, cluster_id
        else:
            if project.namespace == group_id:
                keycloak_connection = KeycloakOpenIDConnection(
                    server_url=settings.OIDC_SERVER_URL,
                    username=settings.OIDC_USERNAME,
                    password="",
                    realm_name=settings.OIDC_REALM_NAME,
                    client_id=settings.OIDC_RP_CLIENT_ID,
                    client_secret_key=settings.OIDC_RP_CLIENT_SECRET,
                    verify=False,
                )

                keycloak_admin = KeycloakAdmin(connection=keycloak_connection)
                groups = keycloak_admin.get_groups()

                maia_groups = {
                    group["id"]: group["name"][len("MAIA:") :] for group in groups if group["name"].startswith("MAIA:")
                }

                group_users = []

                for maia_group in maia_groups:
                    if maia_groups[maia_group] == group_id:
                        users = keycloak_admin.get_group_members(group_id=maia_group)

                        for user in users:
                            group_users.append(user["email"])

                namespace_form = {
                    "group_ID": group_id,
                    "group_subdomain": group_id.lower().replace("_", "-"),
                    "users": group_users,
                    "resources_limits": {
                        "memory": [str(int(int(project.memory_limit[: -len(" Gi")]) / 2)) + " Gi", project.memory_limit],
                        "cpu": [str(int(int(project.cpu_limit) / 2)), project.cpu_limit],
                    },
                    "environment": project.minimal_env,
                }
                if project.gpu != "N/A" and project.gpu != "NO":
                    namespace_form["gpu_request"] = "1"

                if project.conda != "N/A" and project.conda is not None:
                    namespace_form["minio_env_name"] = group_id + "_env"

                cluster_id = project.cluster
                if cluster_id == "N/A":
                    cluster_id = None
                return namespace_form, cluster_id

    return None, None


def get_argocd_project_status(argocd_namespace, project_id):
    return verify_installed_maia_toolkit(project_id=project_id, namespace=argocd_namespace, get_chart_metadata=False)


def get_allocation_date_for_project(maia_project_model, group_id, is_namespace_style=False):
    """
    Retrieves the allocation date for a project based on the given group ID.

    Parameters
    ----------
    maia_project_model : Model
        The Django model representing the MAIA project.
    group_id : str
        The group ID to match against the project's namespace.
    is_namespace_style : bool, optional
        If True, the group ID comparison will be done in a namespace style
        (lowercase and underscores replaced with hyphens). Default is False.

    Returns
    -------
    date or None
        The allocation date of the project if a match is found, otherwise None.
    """

    for project in maia_project_model.objects.all():
        if is_namespace_style:
            if str(project.namespace).lower().replace("_", "-") == group_id:
                return project.date
        else:
            if project.namespace == group_id:
                return project.date

    return None


async def get_list_of_deployed_projects():
    """
    Asynchronously retrieves a list of deployed projects from the Argo CD namespace.
    This function uses a Kubernetes client to list all releases in the "argocd" namespace
    and returns the names of these releases.

    Returns
    -------
    list of str
        A list containing the names of the deployed projects.

    Raises
    ------
    KeyError
        If the "KUBECONFIG" environment variable is not set.
    kubernetes.client.exceptions.ApiException
        If there is an error communicating with the Kubernetes API.
    """
    if "BACKEND" in os.environ and os.environ["BACKEND"] == "compose":
        return [os.environ["PROJECT_NAME"]]
    client = Client(kubeconfig=os.environ["KUBECONFIG"])

    releases = await client.list_releases(namespace="argocd")

    return [release.name for release in releases]


def get_project_argo_status_and_user_table(request, settings, maia_user_model, maia_project_model):
    """
    Retrieves the Argo CD project status and user table information.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object containing session and user information.
    settings : Settings
        The settings object containing configuration values.
    maia_user_model : Model
        The Django model representing MAIA users.
    maia_project_model : Model
        The Django model representing MAIA projects.

    Returns
    -------
    tuple
        A tuple containing:
        - user_table (dict): The user table information.
        - to_register_in_groups (list): List of users to register in groups.
        - to_register_in_keycloak (list): List of users to register in Keycloak.
        - maia_groups_dict (dict): Dictionary of MAIA groups.
        - project_argo_status (dict): Dictionary containing the Argo CD project status for each project.
    """
    argocd_cluster_id = settings.ARGOCD_CLUSTER

    id_token = request.session.get("oidc_id_token")
    if argocd_cluster_id is None or argocd_cluster_id == "N/A":
        ...
    else:
        kubeconfig_dict = generate_kubeconfig(id_token, request.user.username, "default", argocd_cluster_id, settings=settings)
        config.load_kube_config_from_dict(kubeconfig_dict)
        with open(Path("/tmp").joinpath("kubeconfig-argo"), "w") as f:
            yaml.dump(kubeconfig_dict, f)
            os.environ["KUBECONFIG"] = str(Path("/tmp").joinpath("kubeconfig-argo"))

    to_register_in_groups, to_register_in_keycloak, maia_groups_dict, users_to_remove_from_group = get_user_table(
        settings=settings, maia_user_model=maia_user_model, maia_project_model=maia_project_model
    )
    project_argo_status = {}

    namespaces = get_namespaces(id_token, api_urls=settings.API_URL, private_clusters=settings.PRIVATE_CLUSTERS)

    deployed_projects = asyncio.run(get_list_of_deployed_projects())
    for project_id in maia_groups_dict:
        if project_id.lower().replace("_", "-") in deployed_projects:
            project_argo_status[project_id] = 1
        else:
            project_argo_status[project_id] = -1
        if "ARGOCD_DISABLED" in os.environ and os.environ["ARGOCD_DISABLED"] == "True":
            if project_id.lower().replace("_", "-") in namespaces:
                project_argo_status[project_id] = 1
            else:
                project_argo_status[project_id] = -1
        # project_argo_status[project_id] = asyncio.run(get_argocd_project_status(argocd_namespace="argocd", project_id=project_id.lower().replace("_", "-")))  # noqa: B950

    return to_register_in_groups, to_register_in_keycloak, maia_groups_dict, project_argo_status, users_to_remove_from_group


def send_maia_message_email(receiver_emails, subject, message_body):
    """
    Send an email with a custom message to multiple recipients with improved deliverability.
    """
    try:
        sender_email = os.environ["email_account"]
        message = MIMEMultipart("alternative")  # Changed to alternative for better compatibility

        # Add proper headers to improve deliverability
        message["Subject"] = subject
        message["From"] = f"MAIA Team <{sender_email}>"  # Use proper From format
        message["To"] = ", ".join(receiver_emails)
        message["Reply-To"] = sender_email
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain=sender_email.split("@")[1])

        html = f"""\
        <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
                {message_body}
                <br>
                <p>Best regards,</p>
                <p>The MAIA Admin Team</p>
                <hr>
                <p style="font-size: 12px; color: #666666;">
                    This is an automated message from the MAIA Platform.
                    If you believe you received this in error, please contact support.
                </p>
            </body>
        </html>
        """

        # Create plain text version
        text = BeautifulSoup(html, "html.parser").get_text()

        # Attach both plain text and HTML versions
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        port = 465  # For SSL
        password = os.environ["email_password"]
        smtp_server = os.environ["email_smtp_server"]

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sender_email, password)
            server.send_message(message)  # Using send_message instead of sendmail

        return True

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


def generate_encryption_keys(folder_path):
    """
    Generate RSA encryption keys and save them to files.

    Parameters
    ----------
    folder_path : str
        The path to the folder where the keys will be saved.

    Returns
    -------
    None
    """

    # Generate RSA key pair
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Extract public key
    public_key = private_key.public_key()

    # Save private key to a file
    with open(Path(folder_path).joinpath("private_key.pem"), "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Save public key to a file
    with open(Path(folder_path).joinpath("public_key.pem"), "wb") as f:
        f.write(
            public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        )

    print("Keys generated successfully!")


def encrypt_string(public_key, string):
    """
    Encrypts a given string using the provided public key.

    Parameters
    ----------
    public_key : str
        The file path to the public key in PEM format.
    string : str
        The string to be encrypted.

    Returns
    -------
    str
        The encrypted string in hexadecimal format.

    Raises
    ------
    ValueError
        If the public key file cannot be read or is invalid.
    """

    # Load public key
    with open(public_key, "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    def encrypt_message(message, public_key):
        encrypted = public_key.encrypt(
            message.encode(), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )
        return encrypted

    encrypted_message = encrypt_message(string, public_key)

    return encrypted_message.hex()


def decrypt_string(private_key, string):
    """
    Decrypts an encrypted string using a given private key.

    Parameters
    ----------
    private_key : str
        Path to the private key file in PEM format.
    string : bytes
        The encrypted string to be decrypted.

    Returns
    -------
    str
        The decrypted string.

    Raises
    ------
    ValueError
        If the decryption process fails.
    """

    with open(private_key, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    def decrypt_message(encrypted, private_key):
        decrypted = private_key.decrypt(
            encrypted, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )
        return decrypted.decode()

    decrypted_message = decrypt_message(string, private_key)

    return decrypted_message
