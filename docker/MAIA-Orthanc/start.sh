#!/bin/bash -e

if [[ -f /mnt/orthanc.json ]]; then
  jq -s '.[0] * .[1]' /etc/orthanc/orthanc.json /mnt/orthanc.json > /etc/orthanc/orthanc_merged.json
  mv /etc/orthanc/orthanc_merged.json /etc/orthanc/orthanc.json
else
  echo "File /mnt/orthanc.json does not exist."
fi

sed -i 's|worker_processes .*|worker_processes 1;|' /etc/nginx/nginx.conf

envsubst '${INGRESS_PATH} ${MONAI_LABEL_INGRESS_PATH}' < /etc/default.template > default
mv default /etc/nginx/sites-enabled/
nginx -c /etc/nginx/nginx.conf -g 'daemon off;' &

sed -i "s+OHIF_PATH+$INGRESS_PATH/ohif/+g" /etc/orthanc/orthanc.json

sed -i "s+INGRESS_PATH+$MONAI_LABEL_INGRESS_PATH+g" /workspace/MONAILabel/plugins/ohifv3/build.sh
sed -i "s+INGRESS_PATH+$MONAI_LABEL_INGRESS_PATH+g" /workspace/MONAILabel/plugins/ohifv3/run.sh
sed -i "s+INGRESS_PATH+$MONAI_LABEL_INGRESS_PATH+g" /workspace/MONAILabel/plugins/ohifv3/config/monai_label.js

python /etc/process_queue.py &

exec "$@" 
#&

#if [[ -n "${ENABLE_MONAI_LABEL}" ]]; then
#  cd MONAILabel && BUILD_OHIF=true pip install -e .

#  pip install dicomweb-client[gcp]
#  pip install opencv-python==3.4.18.65 mlflow

#  if [[ -z "${BUNDLE_MODEL_NAME}" ]]; then
#    monailabel apps --name radiology --download --output .
#    MONAI_LABEL_API_STR=$MONAI_LABEL_INGRESS_PATH monailabel start_server --app radiology --studies $ORTHANC_DICOMWEB_ADDRESS --conf models deepedit &

#  else
#    if [[ -z "${NIFTI_FOLDER}" ]]; then
#      monailabel apps --name monaibundle --download --output .
#      python /workspace/mlflow_model_download.py
#      MONAI_LABEL_API_STR=$MONAI_LABEL_INGRESS_PATH monailabel start_server --app monaibundle --studies $ORTHANC_DICOMWEB_ADDRESS --conf models $BUNDLE_MODEL_NAME &

#    else
#      monailabel apps --name monaibundle --download --output .
#      python /workspace/mlflow_model_download.py
#      MONAI_LABEL_API_STR=$MONAI_LABEL_INGRESS_PATH monailabel start_server --app monaibundle --studies $NIFTI_FOLDER --conf models $BUNDLE_MODEL_NAME &

#    fi
#  fi
#fi

#sleep infinity