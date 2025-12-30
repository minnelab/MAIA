ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ENV INSTALL_ZSH="1"
USER maia-user

CMD bash -c "jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
  --NotebookApp.notebook_dir=/home/maia-user \
  --NotebookApp.token='' \
  --NotebookApp.password='' \
  --NotebookApp.base_url=${NB_PREFIX} \
  --NotebookApp.allow_origin='*'"


ENTRYPOINT ["bash", "/opt/start.sh"]
