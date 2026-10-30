#!/bin/bash


if [ -d /home/ubuntu/Documents/Slicer-5.12.4-linux-amd64 ]; then
    echo "Slicer is already installed."
    exit 0
fi



cp /etc/slicer.tar.gz /home/ubuntu/Documents/

tar -xf /home/ubuntu/Documents/slicer.tar.gz -C /home/ubuntu/Documents/

#/home/ubuntu/Documents/Slicer-5.10.0-linux-amd64/Slicer --python-script /home/maia-user/Tutorials/Slicer_Extensions.py &

cp /etc/Slicer.desktop /home/ubuntu/Desktop/

