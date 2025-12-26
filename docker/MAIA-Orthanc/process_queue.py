#!/usr/bin/env python3
import time
import os
import subprocess
import json

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


models = {
    "MSP-Spleen": {"label_info": "params={\"label_info\":[{\"name\":\"spleen\",\"model_name\":\"MAIA-Segmentation-Portal\"}]}","host":"https://spleen-segmentation.maia-segmentation.maia-medium.cloud.cbh.kth.se"},
    "MSP-BraTS": {"label_info": "params={\"label_info\":[{\"name\":\"ET\",\"model_name\":\"MAIA-Segmentation-Portal\"},{\"name\":\"NETC\",\"model_name\":\"MAIA-Segmentation-Portal\"},{\"name\":\"SNFH\",\"model_name\":\"MAIA-Segmentation-Portal\"}]}","host":"https://brats.maia-segmentation.maia-medium.cloud.cbh.kth.se"},
    "MSP-Lymphoma": {"label_info": "params={\"label_info\":[{\"name\":\"lesion\",\"model_name\":\"MAIA-Segmentation-Portal\"}]}", "host":"https://lymphoma-segmentation.maia-segmentation.maia-medium.cloud.cbh.kth.se"},
    "MSP-LungNodule": {"label_info": "params={\"label_info\":[{\"name\":\"nodule\",\"model_name\":\"MAIA-Segmentation-Portal\"}]}", "host":"https://lung-nodule-segmentation.maia-segmentation.maia-medium.cloud.cbh.kth.se"},
}
