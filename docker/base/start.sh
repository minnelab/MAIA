#!/bin/bash

n_users=${n_users}

if [ $n_users == "1" ]
then
    echo "SingleUser"
else
    echo "Multiple Users"
    n=$((n_users - 1))
    user=""
    password=""
    ssh_publickey=""
    for i in $(seq 0 1 $n)
    do
        user_var=user_$i
        user+=${!user_var},

        password_var=password_$i
        password+=${!password_var},

        key_var=ssh_publickey_$i
        ssh_publickey+=${!key_var},
    done
    user=${user%?}
    password=${password%?}
    ssh_publickey=${ssh_publickey%?}
fi

if [ $RUN_MLFLOW_SERVER == "True" ]
then
    envsubst '${NAMESPACE} ${MLFLOW_PATH} ${MINIO_CONSOLE_PATH}' < /etc/default.template > default
    sudo mv default /etc/nginx/sites-enabled/
    sudo nginx -c /etc/nginx/nginx.conf -g 'daemon off;' &
fi



python3 /workspace/generate_user_environment.py --user $user --password "$password" --authorized-keys "$ssh_publickey" --run-file-browser $RUN_FILEBROWSER --run-mlflow-server $RUN_MLFLOW_SERVER

if [ $RUN_FILEBROWSER == "True" ]
then
    filebrowser -r /home -c /config/settings.json -d /database/filebrowser.db &
fi

rm generate_user_environment.py


exec "$@"
