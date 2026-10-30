#!/bin/bash

if [ -d $HOME/Documents/itksnap-4.2.0-20240422-Linux-gcc64 ]; then
    echo "ITK-SNAP is already installed."
    exit 0
fi


#tar --help
tar -xvf /etc/itksnap-4.2.0-20240422-Linux-gcc64.tar.gz -C /home/ubuntu/Documents/
chmod u+x /home/ubuntu/Documents/itksnap-4.2.0-20240422-Linux-gcc64/bin/itksnap


cp /etc/ITKSnap.desktop /home/ubuntu/Desktop/