#!/bin/bash

if [ -d /home/ubuntu/Documents/MITK-v2024.12-linux-x86_64 ]; then
    echo "MITK is already installed."
    exit 0
fi


#tar --help
tar -xvf /etc/MITK-v2024.12-linux-x86_64.tar.gz -C /home/ubuntu/Documents/ && rm /etc/MITK-v2024.12-linux-x86_64.tar.gz
chmod u+x /home/ubuntu/Documents/MITK-v2024.12-linux-x86_64/MitkWorkbench.sh


cp /etc/MITK.desktop /home/ubuntu/Desktop/