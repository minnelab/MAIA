ARG BASE_IMAGE
FROM $BASE_IMAGE


USER root
# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt-get update
RUN apt-get install -y default-libmysqlclient-dev build-essential pkg-config
WORKDIR /etc

COPY start-script.sh /etc
COPY start-script_dev.sh /etc

RUN chmod +x /etc/start-script.sh
RUN chmod 777 /etc/start-script.sh

ARG DEVEL=0
RUN if [ "$DEVEL" = "1" ]; then \
    mv /etc/start-script_dev.sh start-script.sh && \
    chmod 777 start-script.sh && \
    chmod +x start-script.sh ; \
fi

ENTRYPOINT ["bash", "start-script.sh"]
# gunicorn
CMD ["/root/.local/bin/MAIA_setup_dashboard"]
#CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000","--insecure"]
#CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]

