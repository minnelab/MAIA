# MAIA Inference Stack (Orthanc + Triton)

A minimal Docker Compose stack that runs:

- **Orthanc**: a DICOM server (PACS) with a REST API, DICOMweb, Orthanc Explorer 2 and the Stone Web Viewer.
- **NVIDIA Triton Inference Server**: serves models from `./model_repository` over HTTP and gRPC.

A one-shot **`orthanc-init`** job also fills Orthanc with the 3D Slicer **MRHead** sample, so there is data to test with straight away.

Both services join the same `inference` network, so they can reach each other by service name (`http://orthanc:8042`, `http://triton:8000`).

```
inference/
├── docker-compose.yaml
├── .env.example
├── init/                    # orthanc-init job (loads the MRHead sample)
│   ├── Dockerfile
│   └── populate_orthanc.py
└── model_repository/
    └── identity/            # sample Python-backend model (echoes its input)
        ├── config.pbtxt
        └── 1/model.py
```

## Prerequisites

- Docker Engine with Docker Compose v2 (`docker compose`)
- For GPU inference: an NVIDIA driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

> **No GPU?** Remove the `deploy:` block from the `triton` service in `docker-compose.yaml`. Triton then runs on CPU only.

## Quick start

```bash
cd inference
cp .env.example .env        # optional: change ports, credentials or image tags
docker compose up -d --build
docker compose ps
docker compose logs -f orthanc-init   # watch the MRHead sample upload
```

| Service | URL / Port | Notes |
|---|---|---|
| Orthanc web UI | http://localhost:8042/ui/app/ | default login `orthanc` / `orthanc` |
| Orthanc DICOMweb | http://localhost:8042/dicom-web/ | |
| Orthanc DICOM | `localhost:4242`, AET `ORTHANC` | C-STORE, C-FIND, ... |
| Triton HTTP | http://localhost:8000 | KServe v2 protocol |
| Triton gRPC | `localhost:8001` | |
| Triton metrics | http://localhost:8002/metrics | Prometheus format |

Change the default Orthanc credentials (`ORTHANC_USER`, `ORTHANC_PASSWORD` in `.env`) before you expose the stack anywhere.

To stop the stack:

```bash
docker compose down        # keeps the Orthanc database volume
docker compose down -v     # also deletes the stored DICOM data
```

## Sample data: MRHead

On every `docker compose up`, the `orthanc-init` container:

1. waits for Orthanc to respond,
2. exits straight away if a patient with `PatientID = MRHead` is already stored,
3. downloads `MR-head.nrrd` from the 3D Slicer sample data ([SlicerTestingData](https://github.com/Slicer/SlicerTestingData/releases)) and checks its SHA256,
4. converts the NRRD volume to a DICOM MR series (130 slices, 256×256) with SimpleITK,
5. uploads the slices to Orthanc.

You then find it in the Orthanc UI as patient **MRHead^Sample**, study *3D Slicer sample data*, series *MRHead*.

- To load it again from scratch: `docker compose down -v && docker compose up -d`
- To skip it: `docker compose up -d orthanc triton`
- To load more data: copy `init/populate_orthanc.py` as a starting point. Set `MRHEAD_URL` to use a mirror for the download.

## Using Orthanc

Upload a DICOM file:

```bash
curl -u orthanc:orthanc -X POST http://localhost:8042/instances \
     --data-binary @image.dcm
```

List the stored studies:

```bash
curl -u orthanc:orthanc http://localhost:8042/studies
```

Send a folder over DICOM with DCMTK:

```bash
storescu -aec ORTHANC +sd +r localhost 4242 /path/to/dicom/folder
```

## Using Triton

Check that the server is ready and list the loaded models:

```bash
curl -s localhost:8000/v2/health/ready -o /dev/null -w "%{http_code}\n"   # expect 200
curl -s -X POST localhost:8000/v2/repository/index
```

Run inference on the sample `identity` model:

```bash
curl -s -X POST localhost:8000/v2/models/identity/infer \
  -H "Content-Type: application/json" \
  -d '{"inputs":[{"name":"INPUT0","shape":[3],"datatype":"FP32","data":[1.0,2.0,3.0]}]}'
```

From Python (`pip install tritonclient[http] numpy`):

```python
import numpy as np
import tritonclient.http as httpclient

client = httpclient.InferenceServerClient(url="localhost:8000")
data = np.array([1.0, 2.0, 3.0], dtype=np.float32)

inp = httpclient.InferInput("INPUT0", data.shape, "FP32")
inp.set_data_from_numpy(data)

result = client.infer("identity", inputs=[inp])
print(result.as_numpy("OUTPUT0"))
```

### Adding your own models

Put each model in `model_repository/` using Triton's layout:

```
model_repository/
└── <model_name>/
    ├── config.pbtxt
    └── <version>/          # e.g. 1/
        └── model.onnx | model.plan | model.pt | model.savedmodel/ | model.py
```

Triton checks the repository every 30 seconds (`--model-control-mode=poll`), so it loads new or changed models without a restart. See the [Triton model repository docs](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_repository.html) for details.

## Orthanc → Triton example workflow

A typical pipeline pulls a series from Orthanc, runs inference on Triton, and pushes the result back:

```python
import requests

ORTHANC = "http://localhost:8042"   # use http://orthanc:8042 from inside the network
AUTH = ("orthanc", "orthanc")

series_id = requests.get(f"{ORTHANC}/series", auth=AUTH).json()[0]
archive = requests.get(f"{ORTHANC}/series/{series_id}/archive", auth=AUTH).content
# -> unzip, preprocess (e.g. with pydicom / SimpleITK), call Triton as shown above,
#    then upload the resulting DICOM (e.g. a SEG) with POST {ORTHANC}/instances
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ORTHANC_TAG` | `latest` | `orthancteam/orthanc` image tag |
| `ORTHANC_HTTP_PORT` | `8042` | Host port for the Orthanc HTTP API |
| `ORTHANC_DICOM_PORT` | `4242` | Host port for DICOM |
| `ORTHANC_AET` | `ORTHANC` | Orthanc DICOM AE title |
| `ORTHANC_USER` / `ORTHANC_PASSWORD` | `orthanc` / `orthanc` | Orthanc credentials |
| `TRITON_TAG` | `25.01-py3` | `nvcr.io/nvidia/tritonserver` image tag |
| `TRITON_HTTP_PORT` / `TRITON_GRPC_PORT` / `TRITON_METRICS_PORT` | `8000` / `8001` / `8002` | Triton host ports |

You can set any other Orthanc option with an `ORTHANC__<SECTION>__<KEY>` environment variable. See the [Orthanc Docker documentation](https://orthanc.uclouvain.be/book/users/docker-orthancteam.html).

## Troubleshooting

- **Triton exits with `could not select device driver "nvidia"`**: the NVIDIA Container Toolkit is missing. Install it, or remove the `deploy:` block to run on CPU.
- **A model shows as `UNAVAILABLE`**: run `docker compose logs triton`. The usual causes are a mismatch between `config.pbtxt` and the model file, or a missing version folder.
- **`orthanc-init` fails to download**: the job needs internet access to reach `github.com`. You can retry it with `docker compose up orthanc-init`.
- **Logs**: `docker compose logs -f orthanc` or `docker compose logs -f triton`.
