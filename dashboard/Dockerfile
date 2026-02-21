ARG BASE_IMAGE
FROM $BASE_IMAGE


USER root
# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG MAIA_DASHBOARD_PATH="/etc/MAIA-Dashboard"
RUN apt-get update
RUN apt-get install -y default-libmysqlclient-dev build-essential pkg-config
RUN git clone https://github.com/minnelab/MAIA.git@v2.4.4 /etc/MAIA
RUN mkdir /etc/MAIA-Dashboard
WORKDIR /etc/MAIA-Dashboard
COPY /etc/MAIA/dashboard/requirements.txt /etc/MAIA-Dashboard
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY /etc/MAIA/dashboard/manage.py /etc/MAIA-Dashboard
COPY /etc/MAIA/dashboard/apps /etc/MAIA-Dashboard/apps
COPY /etc/MAIA/dashboard/core /etc/MAIA-Dashboard/core

COPY /etc/MAIA/dashboard/start-script.sh /etc/MAIA-Dashboard
COPY /etc/MAIA/dashboard/start-script_dev.sh /etc/MAIA-Dashboard

RUN chmod +x /etc/MAIA-Dashboard/start-script.sh
RUN chmod 777 /etc/MAIA-Dashboard/start-script.sh

ARG DEVEL=0
RUN if [ "$DEVEL" = "1" ]; then \
    cd /etc && \
    git clone https://github.com/minnelab/MAIA.git && \
    cd /etc/MAIA/dashboard && \
    mv /etc/MAIA-Dashboard/start-script_dev.sh start-script.sh && \
    chmod 777 start-script.sh && \
    chmod +x start-script.sh ; \
fi
WORKDIR $MAIA_DASHBOARD_PATH

ENTRYPOINT ["bash", "start-script.sh"]
# gunicorn
CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000","--insecure"]
#CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]

