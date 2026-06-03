#!/usr/bin/env python3
import time
import os
import subprocess
import json
import requests

with open("/mnt/models.json", "r") as f:
    models = json.load(f)
while True:
    for model, model_info in models.items():
        QUEUE_FILE = f"/tmp/{model}_inference_queue.txt"
        MONAI_LABEL_HOST = model_info["host"]
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r") as f:
                uids = f.read().splitlines()
            open(QUEUE_FILE, "w").close()  # clear queue

            for studyUID in uids:
                outputFile = f"/tmp/{model}_pred.dcm"
                # Verify if Auth is enabled
                auth = False
                auth_enabled = requests.get(f"{MONAI_LABEL_HOST}/auth/")
                if auth_enabled.status_code != 200:
                    print(f"Auth is not enabled for {MONAI_LABEL_HOST}")
                    continue
                elif auth_enabled.json()["enabled"] == False:
                    print(f"Auth is not enabled for {MONAI_LABEL_HOST}")
                    continue
                else:
                    print(f"Auth is enabled for {MONAI_LABEL_HOST}")
                    auth = True

                if auth:
                    username = os.environ.get("MONAI_LABEL_USERNAME", None)
                    password = os.environ.get("MONAI_LABEL_PASSWORD", None)
                    if username is None or password is None:
                        print(f"Username or password is not set for {MONAI_LABEL_HOST}. Please set the MONAI_LABEL_USERNAME and MONAI_LABEL_PASSWORD environment variables.")
                        continue
                    token = requests.post(f"{MONAI_LABEL_HOST}/auth/token",
                            data={"username": username, "password": password},
                            )
                    access_token = token.json()["access_token"]
                    # Run inference with Authorization header
                    subprocess.run([
                        "curl", "-s", "-X", "POST", "-H", f"Authorization: Bearer {access_token}",
                        f"{MONAI_LABEL_HOST}/infer/MONetBundle?image={studyUID}&output=dicom_seg",
                        "-F", model_info["label_info"],
                        "--output", outputFile
                    ])
                else:
                    # Run inference
                    subprocess.run([
                        "curl", "-s", "-X", "POST",
                        f"{MONAI_LABEL_HOST}/infer/MONetBundle?image={studyUID}&output=dicom_seg",
                        "-F", model_info["label_info"],
                        "--output", outputFile
                    ])

              
                # Post result to Orthanc
                subprocess.run([
                    "curl", "-s", "-X", "POST",
                    f"http://127.0.0.1:8042/instances",
                    "--data-binary", f"@{outputFile}"
                ])
                print(f">>> Inference completed for {studyUID}")

    time.sleep(2)  # check every 5 seconds
