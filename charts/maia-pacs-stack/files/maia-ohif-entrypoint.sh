#!/bin/sh
# Runtime OHIF base path — image is built once with PUBLIC_URL=/ (assets at web root).
set -e

OHIF_PUBLIC_PATH="${OHIF_PUBLIC_PATH:-/ohif/}"
case "$OHIF_PUBLIC_PATH" in
  */) ;;
  *) OHIF_PUBLIC_PATH="${OHIF_PUBLIC_PATH}/" ;;
esac

DICOMWEB_PUBLIC_PATH="${DICOMWEB_PUBLIC_PATH:-/dicom-web}"
AI_ASSIST_PUBLIC_PATH="${AI_ASSIST_PUBLIC_PATH:-/ai-api}"
export OHIF_PUBLIC_PATH DICOMWEB_PUBLIC_PATH AI_ASSIST_PUBLIC_PATH PORT="${PORT:-80}"

HTML_ROOT=/usr/share/nginx/html
INDEX="${HTML_ROOT}/index.html"
ORIG="${HTML_ROOT}/index.html.orig"

if [ ! -f "$ORIG" ]; then
  cp "$INDEX" "$ORIG"
fi
cp "$ORIG" "$INDEX"

# PUBLIC_URL for OHIF runtime; __webpack_public_path__ (chunks may still load from / — front nginx proxies those)
sed -i "s|window.PUBLIC_URL = '[^']*'|window.PUBLIC_URL = '${OHIF_PUBLIC_PATH}'; __webpack_public_path__ = window.PUBLIC_URL;|g" "$INDEX"
# First script in <head> so public path is set before any module runs
sed -i '/id="maia-webpack-public-path"/d' "$INDEX"
sed -i "s|<head>|<head><script id=\"maia-webpack-public-path\">__webpack_public_path__='${OHIF_PUBLIC_PATH}';</script>|" "$INDEX"
# Idempotent: strip any existing prefix before re-applying
sed -i "s|src=\"${OHIF_PUBLIC_PATH}|src=\"/__MAIA__/|g; s|href=\"${OHIF_PUBLIC_PATH}|href=\"/__MAIA__/|g" "$INDEX"
sed -i "s|src=\"/|src=\"${OHIF_PUBLIC_PATH}|g; s|href=\"/|href=\"${OHIF_PUBLIC_PATH}|g" "$INDEX"
sed -i "s|/__MAIA__/|${OHIF_PUBLIC_PATH}|g" "$INDEX"

envsubst '${OHIF_PUBLIC_PATH} ${DICOMWEB_PUBLIC_PATH} ${AI_ASSIST_PUBLIC_PATH}' \
  < /etc/maia/ohif-config.js.template > "${HTML_ROOT}/app-config.js"
rm -f "${HTML_ROOT}/app-config.js.gz"
gzip -kf "${HTML_ROOT}/app-config.js" 2>/dev/null || true
touch "${HTML_ROOT}/app-config.js"

envsubst '${PORT} ${DICOMWEB_PUBLIC_PATH}' \
  < /usr/src/default.conf.template > /etc/nginx/conf.d/default.conf

echo "MAIA OHIF: serving under ${OHIF_PUBLIC_PATH} (runtime), DICOMweb at ${DICOMWEB_PUBLIC_PATH}, AI Assist at ${AI_ASSIST_PUBLIC_PATH}"
exec "$@"
