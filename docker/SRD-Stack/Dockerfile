# SRD-Stack — multi-stage desktop image
#
#   base      — Ubuntu + Python + Jupyter Lab + SSH (2022)
#   rdp       — adds XFCE + xrdp on 3389
#   desktop   — adds jupyter-remote-desktop-proxy (TigerVNC Desktop in Lab)
#   openshift — unprivileged wrap of desktop; UID 1000620000 [default]
#
# All stages: USER ubuntu (or numeric UID), WORKDIR /home/ubuntu

ARG UBUNTU_UID=1000620000

# ---------------------------------------------------------------------------
# 1. base — Ubuntu + Python + Jupyter Lab + SSH
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS base
ARG UBUNTU_UID=1000620000

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    SHELL=/bin/bash \
    HOME=/home/ubuntu \
    USER=ubuntu \
    NB_USER=ubuntu \
    NB_PREFIX=/ \
    JUPYTER_RUNTIME_DIR=/tmp/jupyter/runtime \
    JUPYTER_DATA_DIR=/home/ubuntu/.local/share/jupyter \
    XDG_RUNTIME_DIR=/tmp/runtime-ubuntu

RUN userdel -r ubuntu 2>/dev/null || true \
 && apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl locales tzdata sudo \
      python3 python3-pip python3-venv \
      openssh-server openssl supervisor \
      git nano vim htop less wget unzip \
 && locale-gen en_US.UTF-8 \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && useradd --create-home -u ${UBUNTU_UID} -g 0 -d /home/ubuntu -s /bin/bash ubuntu \
 && echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu \
 && chmod 0440 /etc/sudoers.d/ubuntu \
 && echo "ubuntu:ubuntu" | chpasswd \
 && mkdir -p \
      /home/ubuntu/Desktop \
      /home/ubuntu/Documents \
      /home/ubuntu/Tutorials \
      /home/ubuntu/.local/share/jupyter/runtime \
      /home/ubuntu/.jupyter \
      /tmp/jupyter/runtime \
      /tmp/runtime-ubuntu \
      /var/log/supervisor \
      /var/run/sshd \
      /etc/ssh/sshd_config.d \
 && cp -a /etc/ssh /ssh_orig && rm -rf /etc/ssh/* \
 && pip3 install --break-system-packages --no-cache-dir \
      jupyterlab \
      jupyter-server-proxy \
 && chown -R ${UBUNTU_UID}:0 /home/ubuntu /tmp/jupyter /tmp/runtime-ubuntu \
 && chmod 0700 /tmp/jupyter/runtime /tmp/runtime-ubuntu \
 && rm -rf /var/lib/apt/lists/*
COPY Tools/SSH/install_ssh_server.sh /etc/install_ssh_server.sh
COPY Tools/SSH/sshd.supervisor.conf /etc/ssh-server/sshd.supervisor.conf
COPY Tools/SSH/sftp.conf /etc/ssh-server/sftp.conf
COPY etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf
COPY etc/supervisor/conf.d/jupyter.conf /etc/supervisor/conf.d/jupyter.conf
COPY etc/skel /etc/skel
COPY bin/prepare-home.sh /usr/bin/prepare-home.sh
COPY bin/start-jupyter.sh /usr/bin/start-jupyter.sh
COPY bin/docker-entrypoint-base.sh /usr/bin/docker-entrypoint-base.sh

RUN chmod 0755 /etc/install_ssh_server.sh /usr/bin/prepare-home.sh \
      /usr/bin/start-jupyter.sh /usr/bin/docker-entrypoint-base.sh \
      /etc/skel/.xsession && \
    chmod 0644 /etc/skel/.Xsession /etc/skel/.Xclients

WORKDIR /home/ubuntu
EXPOSE 8888 2022
USER ubuntu
ENTRYPOINT ["/usr/bin/docker-entrypoint-base.sh"]
CMD ["supervisord"]

# ---------------------------------------------------------------------------
# 2. rdp — XFCE + xrdp on 3389
# ---------------------------------------------------------------------------
FROM base AS rdp

USER root
ARG UBUNTU_UID=1000620000

ENV XRDP_PASSWORD=ubuntu

# Match docker/SRD desktop package set (pulseaudio + xfce + xrdp)
RUN apt-get update && apt-get install -y --no-install-recommends \
      dbus-x11 pulseaudio \
      xfce4 xfce4-terminal xfce4-session xfce4-panel \
      xfce4-settings xfce4-clipman-plugin xfce4-screenshooter \
      xfce4-taskmanager xfce4-xkb-plugin \
      xubuntu-icon-theme fonts-dejavu \
      xorg xauth xautolock xprintidle x11-xserver-utils \
      xserver-xorg-legacy xorgxrdp xrdp \
      crudini uuid-runtime \
 && apt-get remove -y light-locker xscreensaver xfce4-screensaver 2>/dev/null || true \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/lib/xrdp-pulseaudio-installer /var/run/dbus

COPY etc/supervisor/conf.d/xrdp.conf /etc/supervisor/conf.d/xrdp.conf
COPY etc/supervisor/conf.d/xrdp-sesman.conf /etc/supervisor/conf.d/xrdp-sesman.conf
COPY etc/asound.conf /etc/asound.conf
COPY etc/xrdp/pulse/default.pa /etc/xrdp/pulse/default.pa
COPY bin/docker-entrypoint-rdp.sh /usr/bin/docker-entrypoint-rdp.sh

# Same xrdp/X11 setup as docker/SRD — keep package /etc/xrdp/startwm.sh
# (it execs /etc/X11/Xsession → ~/.Xsession with pulseaudio + xfce4-session)
RUN chmod 0755 /usr/bin/docker-entrypoint-rdp.sh \
 && cp /etc/X11/xrdp/xorg.conf /etc/X11/ \
 && sed -i "s/console/anybody/g" /etc/X11/Xwrapper.config \
 && sed -i "s|xrdp/xorg|xorg|g" /etc/xrdp/sesman.ini \
 && printf '%s\n' \
      'pulseaudio -D --enable-memfd=True' \
      'xfce4-session' > /etc/skel/.Xsession \
 && printf '%s\n' 'xfce4-session' > /etc/skel/.Xclients \
 && printf '%s\n' '#!/bin/sh' 'pulseaudio -D --enable-memfd=True' 'exec xfce4-session' \
      > /etc/skel/.xsession \
 && chmod 0755 /etc/skel/.xsession \
 && rm -f /etc/xrdp/rsakeys.ini /etc/xrdp/*.pem \
 && chmod 777 /var/log \
 && chown -R ${UBUNTU_UID}:0 /home/ubuntu

WORKDIR /home/ubuntu
EXPOSE 8888 2022 3389
USER ubuntu
ENTRYPOINT ["/usr/bin/docker-entrypoint-rdp.sh"]
CMD ["supervisord"]

# ---------------------------------------------------------------------------
# 3. desktop — Jupyter Remote Desktop proxy only (RDP disabled)
# ---------------------------------------------------------------------------
FROM rdp AS desktop

USER root
ARG UBUNTU_UID=1000620000

ENV JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP=/usr/bin/start-xfce.sh \
    DISABLE_RDP=1 \
    SRD_MODE=desktop

# Use real /usr/bin/vncserver (TigerVNC). Do not shadow it with a wrapper —
# jupyter-remote-desktop-proxy needs -rfbunixpath and detects TigerVNC by
# reading the vncserver script; a wrapper also must not delete
# /tmp/jupyter-server-proxy-* (that is the unix socket path).
RUN apt-get update && apt-get install -y --no-install-recommends \
      tigervnc-standalone-server \
    && pip3 install --break-system-packages --no-cache-dir -U \
      'jupyter-server-proxy>=4.1.0' \
      'jupyter-remote-desktop-proxy>=3.0.0' \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/local/bin/vncserver \
    && test -x /usr/bin/vncserver \
    && grep -qi tigervnc /usr/bin/vncserver

COPY bin/start-xfce.sh /usr/bin/start-xfce.sh
COPY bin/docker-entrypoint-desktop.sh /usr/bin/docker-entrypoint-desktop.sh

# Disable xrdp so TigerVNC is the only desktop path
RUN chmod 0755 /usr/bin/start-xfce.sh /usr/bin/docker-entrypoint-desktop.sh \
 && mkdir -p /etc/supervisor/conf.d-disabled \
 && mv /etc/supervisor/conf.d/xrdp.conf \
       /etc/supervisor/conf.d/xrdp-sesman.conf \
       /etc/supervisor/conf.d-disabled/ 2>/dev/null || true \
 && mkdir -p /home/ubuntu/.vnc \
 && chown -R ${UBUNTU_UID}:0 /home/ubuntu

WORKDIR /home/ubuntu
EXPOSE 8888 2022
USER ubuntu
ENTRYPOINT ["/usr/bin/docker-entrypoint-desktop.sh"]
CMD ["supervisord"]

# ---------------------------------------------------------------------------
# 4. openshift — unprivileged desktop (Jupyter + Remote Desktop proxy)
# ---------------------------------------------------------------------------
FROM desktop AS openshift

USER root
ARG UBUNTU_UID=1000620000

ENV DISABLE_RDP=1 \
    SRD_MODE=openshift \
    JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP=/usr/bin/start-xfce.sh \
    NB_PREFIX=/ \
    HOME=/home/ubuntu \
    USER=ubuntu \
    NB_USER=ubuntu

COPY bin/fix-permissions /usr/bin/fix-permissions
COPY bin/docker-entrypoint-openshift.sh /usr/bin/docker-entrypoint-openshift.sh

RUN chmod 0755 /usr/bin/fix-permissions /usr/bin/docker-entrypoint-openshift.sh \
 && chmod g=u /etc/passwd \
 && usermod -u ${UBUNTU_UID} ubuntu 2>/dev/null || true \
 && mkdir -p /tmp/jupyter/runtime /tmp/runtime-ubuntu /home/ubuntu/.vnc \
 && chown -R ${UBUNTU_UID}:0 \
      /home/ubuntu \
      /usr/local \
      /tmp/jupyter \
      /tmp/runtime-ubuntu \
 && /usr/bin/fix-permissions \
      /home/ubuntu \
      /usr/local \
      /tmp/jupyter \
      /tmp/runtime-ubuntu \
 && find /usr/sbin /usr/bin -perm -4000 -type f -exec chmod a-s {} + 2>/dev/null || true

WORKDIR /home/ubuntu
EXPOSE 8888
USER ${UBUNTU_UID}
ENTRYPOINT ["/usr/bin/docker-entrypoint-openshift.sh"]
CMD ["jupyter", "lab"]
