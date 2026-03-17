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


if [ $RUN_FILEBROWSER == "True" ]
then
    python3 /workspace/generate_user_environment.py --user $user --password "$password" --authorized-keys "$ssh_publickey" --run-file-browser $RUN_FILEBROWSER --run-mlflow-server $RUN_MLFLOW_SERVER
    filebrowser -r /home -b $FILEBROWSER_PATH -c /config/settings.json -d /database/filebrowser.db &
fi

if [ $RUN_MLFLOW_SERVER == "True" ]
then
    python3 /workspace/generate_user_environment.py --user $user --password "$password" --authorized-keys "$ssh_publickey" --run-file-browser $RUN_FILEBROWSER --run-mlflow-server $RUN_MLFLOW_SERVER &
    envsubst '${MLFLOW_PATH}' < /etc/default.template > default
    sudo mv default /etc/nginx/sites-enabled/
    if [ $RUN_MINIO_PROXY == "True" ]
    then
        envsubst '${NAMESPACE} ${MINIO_CONSOLE_PATH} ${KUBEFLOW_URL}' < /etc/minio.conf.template > minio.conf
        sudo mv minio.conf /etc/
        echo "Waiting for MinIO Console at http://${NAMESPACE}-console:9090/ to become active..."
    
        # Loop until curl successfully connects to the endpoint
        # -s: silent, -o /dev/null: hide output, -m 2: max 2 seconds per try
        while ! curl -s -m 2 -o /dev/null http://${NAMESPACE}-console:9090/; do
            echo "MinIO Console is unavailable - sleeping for 2 seconds..."
            sleep 2
        done
        echo "MinIO Console is up and responding!"
    fi

    

    sudo nginx -c /etc/nginx/nginx.conf -g 'daemon off;' &
fi


exec "$@"
