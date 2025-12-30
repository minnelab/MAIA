FROM jupyter/datascience-notebook

USER root


#RUN usermod --login maia-user --move-home --home /home/maia-user jovyan && groupmod --new-name maia-user users

COPY entrypoint.sh /etc/entrypoint.sh
RUN chmod 755 /etc/entrypoint.sh
RUN echo "jovyan ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers


ENV SHELL /bin/bash


ENV USER jovyan
WORKDIR /home/jovyan
COPY .bash_profile /etc/.bash_profile
COPY .bashrc /etc/.bashrc


RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && mv kubectl /usr/local/bin && chmod +x /usr/local/bin/kubectl

RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && chmod 700 get_helm.sh && ./get_helm.sh

RUN curl https://dl.min.io/client/mc/release/linux-amd64/mc --create-dirs -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc
RUN cd /usr/local/bin && curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh"  | bash

RUN curl -sL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh
RUN bash /tmp/nodesource_setup.sh
RUN apt install nodejs
RUN pip install jupyterhub  notebook jupyterlab
RUN pip install jupyterlab-git jupyter_scheduler
RUN pip install jupyter_contrib_nbextensions  && pip install nbgitpuller 
#&& jupyter contrib nbextension install --user
USER 1000

ENTRYPOINT ["/etc/entrypoint.sh"]







