# SRD-Stack — multi-stage desktop image
#
#   base      — Ubuntu + Python + Jupyter Lab + SSH (2022)
#   rdp       — adds XFCE + xrdp on 3389
#   desktop   — adds jupyter-remote-desktop-proxy (TigerVNC Desktop in Lab)
#   openshift — unprivileged desktop + SSH; UID/GID 1000670000 [default]
#
# All stages: USER ubuntu (or numeric UID), WORKDIR /home/ubuntu

ARG UBUNTU_UID=1000620000
ARG UBUNTU_GID=1000670000
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

# Install extra tools (zsh/tmux/nvim + oh-my-zsh template) at build time.
# Runtime entrypoints only seed the ubuntu home from /opt/zsh-template.
# Disable with: --build-arg INSTALL_TOOLS=false
ARG INSTALL_TOOLS=true
COPY 70-maia /etc/update-motd.d/70-maia
COPY 90-qotd /etc/update-motd.d/90-qotd
COPY Tools/ZSH/install_zsh.sh /etc/install_zsh.sh
COPY Tools/MTOP/mtop /usr/local/bin/mtop
COPY .bash_profile /etc/.bash_profile
COPY .zshrc /etc/.zshrc
COPY .tmux.conf /etc/.tmux.conf

RUN chmod +x /etc/install_zsh.sh /usr/local/bin/mtop && \
  if [ "$INSTALL_TOOLS" = "true" ]; then \
    chmod +x /etc/update-motd.d/70-maia /etc/update-motd.d/90-qotd && \
    apt-get update && apt-get install -y --no-install-recommends bc && \
    /etc/install_zsh.sh preinstall && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress && \
    apt-get clean && rm -rf /var/lib/apt/lists/*; \
  fi

COPY Tools/LibreOffice/LibreOffice.desktop /etc/LibreOffice.desktop
COPY Tools/LibreOffice/install_libreoffice.sh /etc/install_libreoffice.sh
RUN chmod 777 /etc/LibreOffice.desktop && chmod a+x /etc/LibreOffice.desktop && \
    chmod 777 /etc/install_libreoffice.sh && chmod a+x /etc/install_libreoffice.sh

RUN apt-get update && apt-get install -y --no-install-recommends \
libxcb-xinerama0 libxcb-xinerama0-dev libxcb-randr0 libxcb-randr0-dev \
libxcb-shape0 libxcb-shape0-dev libxcb-xfixes0 libxcb-xfixes0-dev \
libxcb-image0 libxcb-image0-dev libxcb-icccm4 libxcb-icccm4-dev \
libxcb-keysyms1 libxcb-keysyms1-dev libxcb-render-util0 libxcb-render-util0-dev \
libxcb-util1 libxcb-sync1 libxcb-sync-dev \
libxcb-xkb1 libxcb-xkb-dev libxkbcommon-x11-0 \
libxcb-cursor0 \
libxrender1 libxi6 \
libpcre2-16-0 \
 && rm -rf /var/lib/apt/lists/*

RUN wget https://sourceforge.net/projects/itk-snap/files/itk-snap/4.2.0/itksnap-4.2.0-20240422-Linux-gcc64.tar.gz -O /etc/itksnap-4.2.0-20240422-Linux-gcc64.tar.gz
COPY Tools/ITKSnap/ITKSnap.desktop /etc/ITKSnap.desktop
COPY Tools/ITKSnap/install_itksnap.sh /etc/install_itksnap.sh
COPY Tools/ITKSnap/ITKSnap.png /etc/ITKSnap.png
RUN chmod 777 /etc/ITKSnap.desktop && chmod a+x /etc/ITKSnap.desktop && \
    chmod 777 /etc/install_itksnap.sh && chmod a+x /etc/install_itksnap.sh

RUN wget https://www.mitk.org/download/releases/MITK-2024.12/Ubuntu%2022.04/MITK-v2024.12-linux-x86_64.tar.gz -O /etc/MITK-v2024.12-linux-x86_64.tar.gz
COPY Tools/MITK/install_mitk.sh /etc/install_mitk.sh
RUN chmod 777 /etc/install_mitk.sh && chmod a+x /etc/install_mitk.sh
COPY Tools/MITK/MITK.desktop /etc/MITK.desktop
COPY Tools/MITK/MITK.png /etc/MITK.png
RUN chmod 777 /etc/MITK.desktop && chmod a+x /etc/MITK.desktop && \
    chmod 777 /etc/MITK.png && chmod a+x /etc/MITK.png


RUN pip install 'napari[all]' --break-system-packages
COPY Tools/Napari/install_napari.sh /etc/install_napari.sh
RUN chmod 777 /etc/install_napari.sh && chmod a+x /etc/install_napari.sh
COPY Tools/Napari/Napari.desktop /etc/Napari.desktop
COPY Tools/Napari/Napari.png /etc/Napari.png
RUN chmod 777 /etc/Napari.desktop && chmod a+x /etc/Napari.desktop && \
    chmod 777 /etc/Napari.png && chmod a+x /etc/Napari.png

COPY Tools/QuPath/install_qupath.sh /etc/install_qupath.sh
RUN sudo apt update && sudo apt install xz-utils -y
RUN wget https://github.com/qupath/qupath/releases/download/v0.5.1/QuPath-v0.5.1-Linux.tar.xz -O /etc/QuPath-v0.5.1-Linux.tar.xz

RUN chmod 777 /etc/install_qupath.sh && chmod a+x /etc/install_qupath.sh
COPY Tools/QuPath/QuPath.desktop /etc/QuPath.desktop
COPY Tools/QuPath/QuPath.png /etc/QuPath.png
RUN chmod 777 /etc/QuPath.desktop && chmod a+x /etc/QuPath.desktop && \
    chmod 777 /etc/QuPath.png && chmod a+x /etc/QuPath.png
#COPY Tools/FreeSurfer/install_freesurfer.sh /etc/install_freesurfer.sh
#RUN chmod 777 /etc/install_freesurfer.sh && chmod a+x /etc/install_freesurfer.sh
#RUN /etc/install_freesurfer.sh
RUN wget https://download.slicer.org/bitstream/6aa1beb7ce9de556d3010204 -O /etc/slicer.tar.gz
COPY Tools/Slicer/install_slicer.sh /etc/install_slicer.sh
RUN chmod 777 /etc/install_slicer.sh && chmod a+x /etc/install_slicer.sh
COPY Tools/Slicer/Slicer.desktop /etc/Slicer.desktop
COPY Tools/Slicer/Slicer.png /etc/Slicer.png
RUN chmod 777 /etc/Slicer.desktop && chmod a+x /etc/Slicer.desktop && \
    chmod 777 /etc/Slicer.png && chmod a+x /etc/Slicer.png

RUN apt-get update && \
    apt-get install -y --no-install-recommends libatomic1 && \
    apt-get clean && apt-get -y autoremove && rm -rf /var/lib/apt/lists/* && \
    wget https://www.mathworks.com/mpm/glnxa64/mpm -O /etc/mpm && chmod +x /etc/mpm

ENV MATLAB_RELEASE=R2025b
RUN mkdir /opt/matlab && \
    chmod -R 777 /opt/matlab && \
    /etc/mpm install --release ${MATLAB_RELEASE} --products MATLAB --destination=/opt/matlab && \
    ln -s /opt/matlab/bin/matlab /usr/bin/matlab

RUN apt update && apt install xvfb -y && \
    pip install jupyter-matlab-proxy --break-system-packages

COPY Tools/Matlab/install_matlab.sh /etc/install_matlab.sh
RUN chmod 777 /etc/install_matlab.sh && chmod a+x /etc/install_matlab.sh
COPY Tools/Matlab/Matlab.desktop /etc/Matlab.desktop
COPY Tools/Matlab/Matlab.png /etc/Matlab.png
RUN chmod 777 /etc/Matlab.desktop && chmod a+x /etc/Matlab.desktop && \
    chmod 777 /etc/Matlab.png && chmod a+x /etc/Matlab.png

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      r-base gdebi-core \
      libssl-dev psmisc libclang-dev lsb-release && \
    wget -q https://download2.rstudio.org/server/jammy/amd64/rstudio-server-2026.10.0-233-amd64.deb -O /tmp/rstudio-server.deb && \
    gdebi /tmp/rstudio-server.deb -n && \
    rm -f /tmp/rstudio-server.deb && \
    pip install jupyter-rsession-proxy --break-system-packages && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Firefox is a snap on Ubuntu 24.04; install the .deb from Mozilla instead
RUN install -d -m 0755 /etc/apt/keyrings && \
    wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O /etc/apt/keyrings/packages.mozilla.org.asc && \
    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
      > /etc/apt/sources.list.d/mozilla.list && \
    printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' \
      > /etc/apt/preferences.d/mozilla && \
    apt-get update && apt-get install -y --no-install-recommends firefox && \
    rm -rf /var/lib/apt/lists/*

# OpenCode CLI. Installer writes to $HOME/.opencode; copy onto PATH because
# a mounted home volume hides that directory at runtime.
RUN bash -o pipefail -c 'curl -fsSL https://opencode.ai/v2/install | bash -s -- --no-modify-path' && \
    install -m 0755 /home/ubuntu/.opencode/bin/opencode /usr/local/bin/opencode && \
    rm -rf /home/ubuntu/.opencode

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
COPY bin/patch-novnc-reconnect.py /usr/local/bin/patch-novnc-reconnect.py

RUN apt-get update && apt-get install -y --no-install-recommends \
      tigervnc-standalone-server \
    && pip3 install --break-system-packages --no-cache-dir -U \
      'jupyter-server-proxy>=4.1.0' \
      'jupyter-remote-desktop-proxy>=3.0.0' \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/local/bin/vncserver \
    && test -x /usr/bin/vncserver \
    && grep -qi tigervnc /usr/bin/vncserver \
    && chmod 0755 /usr/local/bin/patch-novnc-reconnect.py \
    && python3 /usr/local/bin/patch-novnc-reconnect.py

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
# 4. openshift — unprivileged desktop + SSH (UID/GID 1000670000)
# ---------------------------------------------------------------------------
FROM desktop AS openshift

USER root
# Match the OpenShift project allocated identity (override with --build-arg).
ARG UBUNTU_UID=1000670000
ARG UBUNTU_GID=1000670000

ENV DISABLE_RDP=1 \
    SRD_MODE=openshift \
    JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP=/usr/bin/start-xfce.sh \
    NB_PREFIX=/ \
    HOME=/home/ubuntu \
    USER=ubuntu \
    NB_USER=ubuntu \
    SSH_PORT=2022 \
    DESKTOP_GEOMETRY=1280x800 \
    TMPDIR=/tmp

COPY bin/fix-permissions /usr/bin/fix-permissions
COPY bin/docker-entrypoint-openshift.sh /usr/bin/docker-entrypoint-openshift.sh
COPY Tools/SSH/start-sshd-unprivileged.sh /usr/bin/start-sshd-unprivileged.sh
COPY bin/ssh-ipv6-bridge.py /usr/bin/ssh-ipv6-bridge.py
COPY bin/vncserver-wrapper.sh /usr/local/bin/vncserver

# UID=GID=1000670000; readable shadow for user-mode PasswordAuthentication;
# /etc/passwd+/etc/group mode 666 so any OpenShift UID can rewrite identity
# (g=u alone stays root:root and GID 1000670000 cannot write → "I have no name!");
# vncserver wrapper ensures TigerVNC rfbunixpath parent exists.
RUN chmod 0755 /usr/bin/fix-permissions /usr/bin/docker-entrypoint-openshift.sh \
      /usr/bin/start-sshd-unprivileged.sh /usr/bin/ssh-ipv6-bridge.py \
      /usr/local/bin/vncserver \
 && groupadd -g ${UBUNTU_GID} ubuntu 2>/dev/null \
    || groupmod -g ${UBUNTU_GID} ubuntu 2>/dev/null \
    || true \
 && usermod -u ${UBUNTU_UID} -g ${UBUNTU_GID} ubuntu 2>/dev/null || true \
 && echo "ubuntu:ubuntu" | chpasswd \
 && chmod 666 /etc/passwd /etc/group \
 && chmod 444 /etc/shadow /etc/gshadow 2>/dev/null || true \
 && mkdir -p /etc/ssh \
 && if [ -f /ssh_orig/moduli ]; then cp /ssh_orig/moduli /etc/ssh/moduli && chmod 444 /etc/ssh/moduli; fi \
 && mkdir -p /tmp/jupyter/runtime /tmp/.X11-unix \
      /home/ubuntu/.vnc /home/ubuntu/.local/share/sshd /home/ubuntu/.ssh \
 && chmod 1777 /tmp/.X11-unix \
 && chown -R ${UBUNTU_UID}:${UBUNTU_GID} \
      /home/ubuntu \
      /usr/local \
      /tmp/jupyter \
 && chmod -R g+rwX /home/ubuntu /usr/local /tmp/jupyter \
 && grep -qi tigervnc /usr/local/bin/vncserver \
 && find /usr/sbin /usr/bin -perm -4000 -type f -exec chmod a-s {} + 2>/dev/null || true


RUN wget https://releases.hashicorp.com/vault/2.2.0/vault_2.2.0_linux_amd64.zip -O /etc/vault_2.2.0_linux_amd64.zip
RUN unzip /etc/vault_2.2.0_linux_amd64.zip -d /etc/vault
RUN chmod 777 /etc/vault/vault
RUN mv /etc/vault/vault /usr/local/bin/vault && chmod +x /usr/local/bin/vault

WORKDIR /home/ubuntu
EXPOSE 8888 2022
USER ${UBUNTU_UID}:${UBUNTU_GID}
ENTRYPOINT ["/usr/bin/docker-entrypoint-openshift.sh"]
CMD ["jupyter", "lab"]
