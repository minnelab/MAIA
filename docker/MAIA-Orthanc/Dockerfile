FROM nvcr.io/nvidia/pytorch:23.10-py3


RUN apt-get -y clean && apt-get -y update

RUN apt update && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata glibc-tools

MAINTAINER Simone Bendazzoli <simben@kth.se>
LABEL Description="Orthanc, free DICOM server" Vendor="The Orthanc project"


ADD ./setup-locales.sh ./setup-locales.sh
RUN bash ./setup-locales.sh

ADD ./download-orthanc.sh ./download-orthanc.sh
RUN bash ./download-orthanc.sh

ADD ./create-config.sh ./create-config.sh
RUN bash ./create-config.sh

RUN rm ./setup-locales.sh ./download-orthanc.sh ./create-config.sh

ADD ./download-plugins.sh ./download-plugins.sh
RUN bash ./download-plugins.sh

RUN rm ./download-plugins.sh

EXPOSE 4242
EXPOSE 8042

ENV MALLOC_ARENA_MAX 5


RUN apt update && apt install -y git curl
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash -
RUN apt-get install -y nodejs
RUN apt update && apt install -y git curl
RUN git clone https://github.com/Project-MONAI/MONAILabel.git
COPY requirements.sh MONAILabel/plugins/ohifv3/requirements.sh
RUN chmod 755 MONAILabel/plugins/ohifv3/requirements.sh
COPY build.sh MONAILabel/plugins/ohifv3/build.sh
RUN chmod 755 MONAILabel/plugins/ohifv3/build.sh
COPY run.sh MONAILabel/plugins/ohifv3/run.sh
RUN chmod 755 MONAILabel/plugins/ohifv3/run.sh
COPY monai_label.js MONAILabel/plugins/ohifv3/config/
RUN chmod 755 MONAILabel/plugins/ohifv3/config/monai_label.js

COPY ohif.py MONAILabel/monailabel/endpoints/ohif.py
RUN chmod 755 MONAILabel/monailabel/endpoints/ohif.py
COPY start.sh /etc/start.sh
RUN chmod 755 /etc/start.sh


RUN apt update && apt install -y nginx gettext-base
RUN apt -y install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

COPY default.template /etc/default.template

COPY orthanc.json /etc/orthanc/orthanc.json

RUN mkdir ohif && cd /workspace/ohif && git clone https://github.com/OHIF/Viewers.git && cd Viewers && git checkout 33f125940863607f8dba82c71b27a43f35431dd5
WORKDIR /workspace

#COPY mlflow_model_download.py .
#RUN pip install nnunetv2==2.5.1
#COPY nnUNetTrainerDemo.py /usr/local/lib/python3.10/dist-packages/nnunetv2/training/nnUNetTrainer/nnnUNetTrainerDemo.py
COPY process_queue.py /etc/process_queue.py
ENTRYPOINT ["/etc/start.sh"]
CMD ["Orthanc","/etc/orthanc"]