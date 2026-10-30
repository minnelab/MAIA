# SRD-Stack

Multi-stage image. Working directory is always `/home/ubuntu`.

| Target | Contents | Ports | Default identity |
|--------|----------|-------|------------------|
| `base` | Ubuntu 24.04 + Python + Jupyter Lab + SSH | `8888`, `2022` | UID **1000620000** |
| `rdp` | + XFCE remote desktop via xrdp | `8888`, `2022`, `3389` | UID **1000620000** |
| `desktop` | Jupyter Remote Desktop proxy (TigerVNC); **RDP off** | `8888`, `2022` | UID **1000620000** |
| `openshift` (default) | Unprivileged desktop + user-mode SSH | `8888`, `2022` | UID/GID **1000670000** |

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

Build-args:
- `UBUNTU_UID` / `UBUNTU_GID` (openshift defaults **1000670000** / **1000670000**)

## PVC home (`/home/ubuntu`)

Mounting a PVC at `/home/ubuntu` is supported. On start the entrypoint:

- Recreates Desktop/Documents/Tutorials and Jupyter/XFCE dirs on the volume
- Seeds `.xsession` / `.Xclients` from `/etc/skel` when missing
- Keeps **Jupyter runtime** and VNC **Xauthority** on `/tmp` (avoids NFS/Ceph `flock` failures)

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

Unprivileged (no root/sudo): Jupyter Lab + Desktop proxy + **user-mode SSH on 2022**.

Default identity: **UID=GID=1000670000**. The entrypoint rewrites `/etc/passwd` and `/etc/group` if the platform assigns a different UID/GID.

```yaml
securityContext:
  runAsUser: 1000670000
  runAsGroup: 1000670000
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
  seccompProfile: { type: RuntimeDefault }
volumeMounts:
  - name: home
    mountPath: /home/ubuntu
```

- Lab → **Desktop** (TigerVNC via jupyter-remote-desktop-proxy)
- SSH: `oc port-forward pod/<name> 2022:2022` then `ssh -p 2022 ubuntu@127.0.0.1` (password `ubuntu`, or set `SSH_PUBLIC_KEY`)
- Host keys under `~/.local/share/sshd` (persist on PVC)
- Disable SSH with `DISABLE_SSH=1`
- Set `NB_PREFIX` for the Jupyter base URL (default `/`)
- On **GPU nodes**, VNC forces Mesa software OpenGL (`llvmpipe`) so Xtigervnc does not load NVIDIA EGL (which crashes GLX init). Slicer/Qt GUIs work over Desktop; CUDA still works. Hardware-accelerated OpenGL in VNC needs VirtualGL separately.
- Desktop viewer is patched to **auto-reconnect** after clean websocket closes (browser tab switch / idle proxy). Hard-refresh once after image update if the old JS is cached.

If an old PVC still has a broken `.xsession` / `.Xsession`, delete those files once so they are re-seeded from `/etc/skel`.
