FROM python:3.12-slim
RUN pip install --no-cache-dir SimpleITK requests
COPY populate_orthanc.py /populate_orthanc.py
ENTRYPOINT ["python", "/populate_orthanc.py"]
