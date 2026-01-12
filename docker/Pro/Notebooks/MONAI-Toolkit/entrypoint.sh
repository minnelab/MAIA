#!/bin/bash

# Copyright (c) MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

if [ $# -gt 0 ]; then
    exec "$@"
else
    if [ ! -z "$MONAI_INSTALL_GITHASH" ]; then
        export MONAI_VER=$(python -c "import monai; print(monai.__version__)")
    fi
    if [ ! -z "$MONAILABEL_INSTALL_GITHASH" ]; then
        export MONAI_LABEL_VER=$(python -c "import monailabel; print(monailabel.__version__)")
    fi

    echo "Welcome to MONAI Toolkit"
    echo ""
    echo "MONAI toolkit components:"
    echo ""
    echo "MONAI Core, Version: ${MONAI_VER}"
    echo "MONAI Label, Version: ${MONAI_LABEL_VER}"
    echo "NVFlare, Version: ${NVFLARE_VER}"
    echo "Jupyter Port is set to: ${JUPYTER_PORT}"

    # check if the port is available on the host
    echo "checking port ${JUPYTER_PORT} availability";
    isPortUsed=$(python -c "import socket; \
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); \
        port_used = True if s.connect_ex(('localhost', ${JUPYTER_PORT})) == 0 else False; \
        print(port_used)
        ")

    if [ $isPortUsed = "True" ]
    then
        echo "Port ${JUPYTER_PORT} is unavailable."
        echo "Please consider one of the these two options:"
        echo "1. Set the environment variable JUPYTER_PORT when the container is being started."
        echo "   For example, users can try adding \"-e JUPYTER_PORT=8900\" to the docker command."
        echo "2. Use the original jupyter commands to start a Jupyter instance"
        echo "   For example, users can try running the docker run command with: "
        echo "   docker run ... nvcr.io/nvidia/clara/monai-toolkit jupyter lab --ip=0.0.0.0 --allow-root --no-browser"
        echo "Exiting."
        exit 1
    else:
        echo "Starting Jupyter Lab"
    fi

    jupyter lab /opt/toolkit \
                --ip=0.0.0.0 \
                --allow-root \
                --no-browser \
                --port=${JUPYTER_PORT} \
                --NotebookApp.custom_display_url=http://localhost:${JUPYTER_PORT}
fi
