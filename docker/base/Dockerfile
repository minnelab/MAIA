ARG BASE_IMAGE="python:3.9.18"
FROM ${BASE_IMAGE}
USER root

ARG RUN_FILEBROWSER="False"
ARG RUN_MLFLOW_SERVER="False"

ENV DEBIAN_FRONTEND=noninteractive

ENV RUN_FILEBROWSER=${RUN_FILEBROWSER}
ENV RUN_MLFLOW_SERVER=${RUN_MLFLOW_SERVER}

#RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC
# SSH-PYCHARM
#RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A4B469963BF863CC
#RUN rm /etc/apt/sources.list.d/cuda.list
RUN apt-get update && apt-get install -y openssh-server build-essential nginx
RUN apt-get install -y sudo screen git nano tmux vim curl tree htop gettext #itksnap
#RUN mkdir /var/run/sshd
RUN mkdir /run/sshd

#RUN rm -rf /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1
EXPOSE 22

WORKDIR /workspace
COPY start.sh start.sh
COPY sshd_config /etc/ssh/
COPY generate_user_environment.py generate_user_environment.py
COPY settings.json /config/settings.json


RUN apt-get update && \
    apt-get install -yq tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Stockholm /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

ENV TZ="Europe/Stockholm"

COPY default.template /etc/default.template
ENTRYPOINT ["bash", "./start.sh"]
CMD ["/usr/sbin/sshd", "-D"]
