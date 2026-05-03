ARG BASE_IMAGE
FROM ${BASE_IMAGE}



ARG DEBIAN_FRONTEND=noninteractive

USER root
RUN chown -R maia-user:maia-user /home/maia-user/.cache && \
curl -sL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh && \
    bash /tmp/nodesource_setup.sh && \
    apt install nodejs && \
    mkdir -p /opt/conda && \
    chmod -R 777 /opt/conda/
USER 1000
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /opt/conda/miniconda.sh && \
    bash /opt/conda/miniconda.sh -b -u -p /opt/conda && \
    rm -rf /opt/conda/miniconda.sh && \
     . /opt/conda/etc/profile.d/conda.sh

USER root
#RUN pip install jupyterhub==4.0.2  notebook==6.* jupyterlab==4.1.5
RUN pip install jupyterhub  notebook jupyterlab --break-system-packages && \
    pip install jupyterlab-git jupyter_scheduler --break-system-packages && \
    pip install jupyter_contrib_nbextensions --break-system-packages  && pip install nbgitpuller --break-system-packages && \
    pip install python-dotenv jupyter-server-proxy --break-system-packages && \
    pip install light-the-torch --break-system-packages
#&& jupyter contrib nbextension install --user
ENV PATH="$PATH:/root/.local/bin"

USER 1000
COPY start.sh /etc/start.sh
RUN sudo chmod 755 /etc/start.sh


ENTRYPOINT ["/etc/start.sh"]