#!/bin/bash -e

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

trap "echo TRAPed signal" HUP INT QUIT TERM

# Create and modify permissions of XDG_RUNTIME_DIR
sudo -u jovyan mkdir -pm700 /tmp/runtime-user
sudo chown jovyan:users /tmp/runtime-user
sudo -u jovyan chmod 700 /tmp/runtime-user
# Make user directory owned by the user in case it is not
sudo chown jovyan:users /home/jovyan || sudo chown jovyan:users /home/jovyan/* || { echo "Failed to change jovyan directory permissions. There may be permission issues."; }
# Change operating system password to environment variable

touch /home/jovyan/.env
JUPYTERHUB_POD_NAME=jupyter-$(echo "$JUPYTERHUB_USER" sed -r 's/[-]+/-2d/g' | sed -r 's/[@]+/-40/g' | sed -r 's/[.]+/-2e/g')
if grep -Fx "JUPYTERHUB_POD_NAME=${JUPYTERHUB_POD_NAME}" /home/jovyan/.env;
then
    echo "Environment variable already set"
else
  echo "JUPYTERHUB_POD_NAME=${JUPYTERHUB_POD_NAME}" >> /home/jovyan/.env
fi

echo "jovyan:$PASSWD" | sudo chpasswd


cp /etc/.bash_profile /home/jovyan/
cp /etc/.bashrc /home/jovyan/

exec "$@"