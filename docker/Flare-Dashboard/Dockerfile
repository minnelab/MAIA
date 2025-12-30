#ARG PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:23.02-py3
ARG PYTORCH_IMAGE=nvflare/nvflare:2.4.0
FROM ${PYTORCH_IMAGE}
ARG DEBIAN_FRONTEND=noninteractive
ARG NVF_VERSION=2.4.0rc6
ENV NVF_BRANCH=${NVF_VERSION}

COPY blob.py /opt/NVFlare/nvflare/dashboard/application/blob.py
#RUN python3 -m pip install -U pip
#RUN python3 -m pip install -U setuptools


#RUN mkdir /workspace/NVIDIA_FLARE
#WORKDIR /workspace/NVIDIA_FLARE
#RUN git clone https://github.com/NVIDIA/NVFlare.git --branch ${NVF_BRANCH} --single-branch NVFlare
#COPY blob.py NVFlare/nvflare/dashboard/application/blob.py
#RUN apt-get update && apt-get install -y build-essential && apt install wget zip -y
#RUN pip install -e NVFlare

#CMD ["sh", "-c","nvflare dashboard --start --local -f /tmp/nvflare --cred $ADMIN_USERNAME:$ADMIN_PASSWORD"]