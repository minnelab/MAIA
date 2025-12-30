FROM ghcr.io/selkies-project/nvidia-egl-desktop:24.04-20250918220126
#FROM ghcr.io/selkies-project/nvidia-egl-desktop:22.04-20240225071130


USER root
RUN mv -f /usr/bin/sudo-root /usr/bin/sudo && \
    apt update && apt install nginx -y && \
    apt update && apt install -y zsh

COPY supervisord.conf   /etc/supervisord.conf
COPY entrypoint.sh /etc/entrypoint.sh
COPY update_user_credentials.sh /etc/update_user_credentials.sh
RUN chmod 755 /etc/supervisord.conf && \
    chmod 755 /etc/entrypoint.sh && \
    chmod 755 /etc/update_user_credentials.sh

COPY MAIA.png /etc/MAIA.png

RUN usermod --login maia-user --move-home --home /home/maia-user ubuntu && groupmod --new-name maia-user ubuntu && \
    chsh -s /bin/zsh maia-user && \
    echo "maia-user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

COPY Tutorials /etc/Tutorials
COPY Welcome.ipynb /etc/Welcome.ipynb
RUN chmod -R 777 /etc/Tutorials && \
    chmod 777 /etc/Welcome.ipynb

COPY 70-maia /etc/update-motd.d/70-maia
COPY 90-qotd /etc/update-motd.d/90-qotd
RUN chmod +x /etc/update-motd.d/70-maia && chmod 777 /etc/update-motd.d/70-maia && \
    chmod +x /etc/update-motd.d/90-qotd && chmod 777 /etc/update-motd.d/90-qotd

COPY Tools/ZSH/install_zsh.sh /etc/install_zsh.sh
RUN chmod 777 /etc/install_zsh.sh && \
    chmod a+x /etc/install_zsh.sh


USER 1000
ENV HOME=/home/maia-user
ENV SHELL /bin/zsh


ENV USER maia-user
WORKDIR /home/maia-user
COPY .bash_profile /etc/.bash_profile
COPY .zshrc /etc/.zshrc
COPY .tmux.conf /etc/.tmux.conf


ENTRYPOINT ["bash", "/etc/entrypoint.sh"]

