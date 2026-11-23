#!/bin/sh
# Download TorchScript model weights into the Triton model repository.
# MODELS is a space-separated list of "<model-name>=<url>" entries; each file
# is saved as /models/<model-name>/1/model.ts. Existing files are kept.
set -eu

for entry in ${MODELS}; do
  name="${entry%%=*}"
  url="${entry#*=}"
  target="/models/${name}/1/model.ts"
  if [ -s "${target}" ]; then
    echo "[triton-init] ${name}: already present, skipping"
    continue
  fi
  echo "[triton-init] ${name}: downloading ${url}"
  mkdir -p "$(dirname "${target}")"
  curl -fsSL --retry 3 -o "${target}.part" "${url}"
  mv "${target}.part" "${target}"
done
echo "[triton-init] done"
