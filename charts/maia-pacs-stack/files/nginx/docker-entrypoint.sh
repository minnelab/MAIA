#!/bin/sh
set -e
export OHIF_PUBLIC_PATH="${OHIF_PUBLIC_PATH:-/ohif/}"
export DICOMWEB_PUBLIC_PATH="${DICOMWEB_PUBLIC_PATH:-/dicom-web}"
export ORTHANC_PUBLIC_PATH="${ORTHANC_PUBLIC_PATH:-/orthanc}"
export OAUTH2_PUBLIC_PATH="${OAUTH2_PUBLIC_PATH:-/oauth2}"
export AI_ASSIST_PUBLIC_PATH="${AI_ASSIST_PUBLIC_PATH:-/ai-api}"
case "$OHIF_PUBLIC_PATH" in */) ;; *) OHIF_PUBLIC_PATH="${OHIF_PUBLIC_PATH}/" ;; esac

envsubst '$OHIF_PUBLIC_PATH $DICOMWEB_PUBLIC_PATH $ORTHANC_PUBLIC_PATH $OAUTH2_PUBLIC_PATH $AI_ASSIST_PUBLIC_PATH' \
  < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

echo "MAIA nginx: OHIF=${OHIF_PUBLIC_PATH} DICOMweb=${DICOMWEB_PUBLIC_PATH} Orthanc=${ORTHANC_PUBLIC_PATH} OAuth2=${OAUTH2_PUBLIC_PATH}"
exec "$@"
