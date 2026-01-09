#!/usr/bin/env bash
set -e

pip install -r docs/requirements/stable.txt
if [[ "$READTHEDOCS_VERSION" == "latest" ]]; then
    pip install git+https://github.com/minnelab/MAIA.git
fi

if [[ "$READTHEDOCS_VERSION" =~ ^v([0-9]+\.[0-9]+\.[0-9]+) ]]; then
    VERSION="${BASH_REMATCH[1]}"
    pip install "maia-toolkit==${VERSION}"
fi

