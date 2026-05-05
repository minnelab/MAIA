import json
from pymongo import MongoClient
from bson import json_util
from datetime import datetime
import yaml
import os
from pathlib import Path


def main():
    db_username = os.environ["DB_USERNAME"]
    db_password = os.environ["DB_PASS"]
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_name = os.environ["DB_NAME"]
    uri = f"mongodb://{db_username}:{db_password}@{db_host}:{db_port}/?authSource=admin"
    client = MongoClient(uri)

    db = client[db_name]
    collection = db['maia_projects']
    user_collection = db['maia_users']
    cursor = user_collection.find({})
    users = list(cursor)

    # Fetch all documents
    cursor = collection.find({})

    # Write to file
    projects = list(cursor)

    metadata = ["namespace", "email", "users", "memory_limit", "cpu_limit", "memory_request", "cpu_request", "project_tier", "gpu", "cluster", "date", "supervisor", "description", "auto_deploy", "auto_deploy_apps", "project_configuration"]


    project_folder = Path('Projects')
    project_folder.mkdir(parents=True, exist_ok=True)

    filtered_table = []
    for project in projects:
        filtered_project = {'users': []}
        for user in users:
            user_namespaces = [namespace.strip() for namespace in user['namespace'].split(',') if namespace.strip()]
            if project['namespace'] in user_namespaces:
                filtered_project['users'].append(user['email'])
        for k, v in project.items():
        
            if k in metadata:
                if k == "date":
                    if isinstance(v, dict):
                        date_str = v["$date"]
                        try:
                            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            filtered_project[k] = date_obj.strftime('%Y-%m-%d')
                        except Exception:
                            filtered_project[k] = date_str
                
                    else:
                        try:
                            if isinstance(v, str):
                                date_obj = datetime.fromisoformat(v.replace('Z', '+00:00'))
                                filtered_project[k] = date_obj.strftime('%Y-%m-%d')
                            elif isinstance(v, datetime):
                                filtered_project[k] = v.strftime('%Y-%m-%d')
                            else:
                                filtered_project[k] = str(v)
                        except Exception:
                            filtered_project[k] = str(v)
                    
                
                elif k == "users":
                    ... # users are already filtered
                else:
                    filtered_project[k] = v
        with open(project_folder.joinpath(filtered_project['namespace']+'.json'), 'w') as f:
            json.dump(filtered_project, f, indent=4)
        filtered_table.append(filtered_project)

if __name__ == "__main__":
    main()