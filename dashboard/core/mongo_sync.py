import json
from pymongo import MongoClient
from datetime import datetime
import re
import os
from pathlib import Path


def main():
    """
    Export project documents from a MongoDB instance into per-project JSON files in a local Projects/ directory.
    
    Connects to the database using credentials from environment variables, loads all projects and users, builds a filtered project object for each project (including only users whose namespace lists include the project's namespace and a selected set of metadata fields), normalizes `date` values to `YYYY-MM-DD` when possible, sanitizes the project `namespace` for a safe filename, and writes each filtered project to Projects/<safe_namespace>.json.
    
    Raises:
        ValueError: If the sanitized project namespace is empty or would allow path traversal (unsafe filename).
    """
    db_username = os.environ["DB_USERNAME"]
    db_password = os.environ["DB_PASS"]
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_name = os.environ["DB_NAME"]
    client = MongoClient(
        host=db_host,
        port=int(db_port),
        username=db_username,
        password=db_password,
        authSource="admin",
    )

    db = client[db_name]
    collection = db["maia_projects"]
    user_collection = db["maia_users"]
    cursor = user_collection.find({})
    users = list(cursor)

    # Fetch all documents
    cursor = collection.find({})

    # Write to file
    projects = list(cursor)

    metadata = [
        "namespace",
        "email",
        "users",
        "memory_limit",
        "cpu_limit",
        "memory_request",
        "cpu_request",
        "project_tier",
        "gpu",
        "cluster",
        "date",
        "supervisor",
        "description",
        "auto_deploy",
        "auto_deploy_apps",
        "project_configuration",
    ]

    project_folder = Path("Projects")
    project_folder.mkdir(parents=True, exist_ok=True)

    filtered_table = []
    for project in projects:
        filtered_project = {"users": []}
        for user in users:
            user_namespace_value = user.get("namespace") or ""
            user_namespaces = [namespace.strip() for namespace in user_namespace_value.split(",") if namespace.strip()]
            if project["namespace"] in user_namespaces:
                user_email = user.get("email")
                if user_email:
                    filtered_project["users"].append(user_email)
        for k, v in project.items():

            if k in metadata:
                if k == "date":
                    if isinstance(v, dict):
                        date_str = v["$date"]
                        try:
                            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            filtered_project[k] = date_obj.strftime("%Y-%m-%d")
                        except Exception:
                            filtered_project[k] = date_str

                    else:
                        try:
                            if isinstance(v, str):
                                date_obj = datetime.fromisoformat(v.replace("Z", "+00:00"))
                                filtered_project[k] = date_obj.strftime("%Y-%m-%d")
                            elif isinstance(v, datetime):
                                filtered_project[k] = v.strftime("%Y-%m-%d")
                            else:
                                filtered_project[k] = str(v)
                        except Exception:
                            filtered_project[k] = str(v)

                elif k == "users":
                    pass  # users are already filtered
                else:
                    filtered_project[k] = v
        # Sanitize the namespace for use as a filename
        raw_namespace = filtered_project.get("namespace", "")
        # Allow only lowercase letters, digits, and hyphens in the filename
        safe_namespace = re.sub(r"[^a-z0-9-]", "_", raw_namespace.lower())
        # Additionally, enforce that no path traversal can happen
        if Path(safe_namespace).name != safe_namespace or not safe_namespace:
            raise ValueError(f"Unsafe or empty namespace for filename: {raw_namespace}")

        with open(project_folder.joinpath(safe_namespace + ".json"), "w") as f:
            json.dump(filtered_project, f, indent=4)

        filtered_table.append(filtered_project)


if __name__ == "__main__":
    main()
