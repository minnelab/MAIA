# SRD-Stack

Multi-stage image. Working directory is always `/home/ubuntu`. Default user is `ubuntu` (UID **1000620000**).

| Target | Contents | Ports |
|--------|----------|-------|
| `base` | Ubuntu 24.04 + Python + Jupyter Lab + SSH | `8888`, `2022` |
| `rdp` | + XFCE remote desktop via xrdp | `8888`, `2022`, `3389` |
| `desktop` | Jupyter Remote Desktop proxy (TigerVNC); **RDP off** | `8888`, `2022` |
| `openshift` (default) | Unprivileged `desktop` for OpenShift | `8888` |

```mermaid
flowchart LR
  base --> rdp --> desktop --> openshift
```

## Build

```bash
docker build -t srd-base --target base docker/SRD-Stack
docker build -t srd-rdp --target rdp docker/SRD-Stack
docker build -t srd-desktop --target desktop docker/SRD-Stack
docker build -t srd-os docker/SRD-Stack
```

Build-arg: `UBUNTU_UID` (default `1000620000`).

## PVC home (`/home/ubuntu`)

Mounting a PVC at `/home/ubuntu` is supported. On start the entrypoint:

- Recreates Desktop/Documents/Tutorials and Jupyter/XFCE dirs on the volume
- Seeds `.xsession` / `.Xclients` from `/etc/skel` when missing
- Keeps **Jupyter runtime** and VNC **Xauthority** on `/tmp` (avoids NFS/Ceph `flock` failures)
- Uses best-effort ownership + `g+rwX` (works with `fsGroup: 0`)

## Run

### Base — Jupyter + SSH

```bash
docker run --rm -p 8888:8888 -p 2022:2022 \
  -v srd-home:/home/ubuntu srd-base
```

### RDP — Jupyter + SSH + XFCE (Guacamole)

```bash
docker run --rm -p 8888:8888 -p 2022:2022 -p 3389:3389 \
  -e XRDP_PASSWORD=ubuntu \
  -v srd-home:/home/ubuntu srd-rdp
```

### Desktop — Jupyter Desktop proxy only (no RDP)

```bash
docker run --rm -p 8888:8888 -p 2022:2022 \
  -v srd-home:/home/ubuntu srd-desktop
```

### OpenShift (`openshift` image)

Jupyter Lab + Remote Desktop proxy only (no RDP, no SSH, no root/sudo).

```yaml
securityContext:
  runAsUser: 1000620000   # or omit for arbitrary UID
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
  seccompProfile: { type: RuntimeDefault }
  fsGroup: 0
# Leave runAsGroup unset
volumeMounts:
  - name: home
    mountPath: /home/ubuntu
```

- Lab → **Desktop** (TigerVNC via jupyter-remote-desktop-proxy)
- Set `NB_PREFIX` for the Jupyter base URL (default `/`)

If an old PVC still has a broken `.xsession` / `.Xsession`, delete those files once so they are re-seeded from `/etc/skel`.
