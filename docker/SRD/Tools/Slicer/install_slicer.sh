#!/bin/bash


if [ -d /home/ubuntu/Documents/Slicer-5.10.0-linux-amd64 ]; then
    echo "Slicer is already installed."
    exit 0
fi

mkdir -p /home/ubuntu/Documents/
mkdir -p /home/ubuntu/Desktop/

cp -r /etc/tmp-home/Slicer-5.10.0-linux-amd64 /home/ubuntu/Documents/
cp /etc/Slicer.desktop /home/ubuntu/Desktop/

chmod -R 777 /home/ubuntu/Documents/Slicer-5.10.0-linux-amd64
chmod a+x /home/ubuntu/Documents/Slicer-5.10.0-linux-amd64/Slicer

chmod 777 /home/ubuntu/Desktop/Slicer.desktop
chmod a+x /home/ubuntu/Desktop/Slicer.desktop