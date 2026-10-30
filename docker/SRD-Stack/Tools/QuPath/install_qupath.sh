#!/bin/bash

if [ -d /home/ubuntu/Documents/QuPath-v0.5.1-Linux ]; then
    echo "QuPath is already installed."
    exit 0
fi


tar -xf /etc/QuPath-v0.5.1-Linux.tar.xz -C /home/ubuntu/Documents/ && rm /etc/QuPath-v0.5.1-Linux.tar.xz
chmod u+x /home/ubuntu/Documents/QuPath-v0.5.1-Linux/QuPath/bin/QuPath

cp /etc/QuPath.desktop /home/ubuntu/Desktop/