"""Populate Orthanc with the 3D Slicer "MRHead" sample.

MRHead is distributed by 3D Slicer as an NRRD volume, so this script:
  1. waits for Orthanc to be reachable,
  2. skips everything if the sample is already stored (idempotent),
  3. downloads MR-head.nrrd and verifies its SHA256,
  4. converts it to a DICOM MR series (one file per slice) with SimpleITK,
  5. uploads every slice to Orthanc through the REST API.
"""
import hashlib
import os
import sys
import tempfile
import time

import requests
import SimpleITK as sitk

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://orthanc:8042").rstrip("/")
AUTH = (os.environ.get("ORTHANC_USER", "orthanc"), os.environ.get("ORTHANC_PASSWORD", "orthanc"))

MRHEAD_SHA256 = "cc211f0dfd9a05ca3841ce1141b292898b2dd2d3f08286affadf823a7e58df93"
MRHEAD_URL = os.environ.get(
    "MRHEAD_URL",
    f"https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/{MRHEAD_SHA256}",
)
PATIENT_ID = "MRHead"


def log(msg):
    print(f"[populate-orthanc] {msg}", flush=True)


def wait_for_orthanc(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{ORTHANC_URL}/system", auth=AUTH, timeout=5).ok:
                return
        except requests.RequestException:
            pass
        log("waiting for Orthanc...")
        time.sleep(5)
    sys.exit(f"Orthanc not reachable at {ORTHANC_URL} after {timeout}s")


def already_loaded():
    r = requests.post(
        f"{ORTHANC_URL}/tools/find",
        auth=AUTH,
        json={"Level": "Patient", "Query": {"PatientID": PATIENT_ID}},
        timeout=30,
    )
    r.raise_for_status()
    return len(r.json()) > 0


def download(path):
    log(f"downloading {MRHEAD_URL}")
    sha = hashlib.sha256()
    with requests.get(MRHEAD_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                sha.update(chunk)
    if sha.hexdigest() != MRHEAD_SHA256:
        sys.exit(f"checksum mismatch for MR-head.nrrd: {sha.hexdigest()}")


def nrrd_to_dicom(nrrd_path, out_dir):
    """Write a 3D volume as a DICOM MR series (based on SimpleITK's DicomSeriesFromArray example)."""
    image = sitk.Cast(sitk.ReadImage(nrrd_path), sitk.sitkInt16)

    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    now_date = time.strftime("%Y%m%d")
    now_time = time.strftime("%H%M%S")
    uid_root = "1.2.826.0.1.3680043.2.1125"
    study_uid = f"{uid_root}.1.{now_date}.{now_time}"
    series_uid = f"{uid_root}.2.{now_date}.{now_time}"
    frame_uid = f"{uid_root}.3.{now_date}.{now_time}"

    direction = image.GetDirection()
    # ImageOrientationPatient: first two columns of the direction matrix
    orientation = "\\".join(
        str(v) for v in (direction[0], direction[3], direction[6], direction[1], direction[4], direction[7])
    )
    spacing = image.GetSpacing()

    common_tags = {
        "0008|0060": "MR",                       # Modality
        "0008|0008": "DERIVED\\SECONDARY",       # Image Type
        "0008|0020": now_date,                   # Study Date
        "0008|0030": now_time,                   # Study Time
        "0008|0021": now_date,                   # Series Date
        "0008|0031": now_time,                   # Series Time
        "0008|1030": "3D Slicer sample data",    # Study Description
        "0008|103e": "MRHead",                   # Series Description
        "0010|0010": "MRHead^Sample",            # Patient Name
        "0010|0020": PATIENT_ID,                 # Patient ID
        "0020|000d": study_uid,                  # Study Instance UID
        "0020|000e": series_uid,                 # Series Instance UID
        "0020|0052": frame_uid,                  # Frame of Reference UID
        "0020|0010": "1",                        # Study ID
        "0020|0011": "1",                        # Series Number
        "0020|0037": orientation,                # Image Orientation (Patient)
        "0018|0050": str(spacing[2]),            # Slice Thickness
    }

    paths = []
    for i in range(image.GetDepth()):
        slice_img = image[:, :, i]
        for tag, value in common_tags.items():
            slice_img.SetMetaData(tag, value)
        position = image.TransformIndexToPhysicalPoint((0, 0, i))
        slice_img.SetMetaData("0020|0032", "\\".join(map(str, position)))  # Image Position (Patient)
        slice_img.SetMetaData("0020|0013", str(i + 1))                      # Instance Number
        slice_img.SetMetaData("0008|0018", f"{series_uid}.{i + 1}")         # SOP Instance UID
        path = os.path.join(out_dir, f"slice_{i:04d}.dcm")
        writer.SetFileName(path)
        writer.Execute(slice_img)
        paths.append(path)
    return paths


def upload(paths):
    for i, path in enumerate(paths, 1):
        with open(path, "rb") as f:
            r = requests.post(f"{ORTHANC_URL}/instances", auth=AUTH, data=f.read(), timeout=60)
        r.raise_for_status()
        if i % 25 == 0 or i == len(paths):
            log(f"uploaded {i}/{len(paths)} slices")


def main():
    wait_for_orthanc()
    if already_loaded():
        log(f"patient '{PATIENT_ID}' already in Orthanc, nothing to do")
        return
    with tempfile.TemporaryDirectory() as tmp:
        nrrd = os.path.join(tmp, "MR-head.nrrd")
        download(nrrd)
        dicom_dir = os.path.join(tmp, "dicom")
        os.makedirs(dicom_dir)
        log("converting NRRD to DICOM")
        upload(nrrd_to_dicom(nrrd, dicom_dir))
    log("done")


if __name__ == "__main__":
    main()
