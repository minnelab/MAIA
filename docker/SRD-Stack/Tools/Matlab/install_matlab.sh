#!/bin/bash

if ! command -v matlab >/dev/null 2>&1; then
    echo "Matlab is not installed."
    exit 0
fi

if [ -f /home/ubuntu/Desktop/Matlab.desktop ]; then
    echo "Matlab desktop shortcut is already installed."
    exit 0
fi



cp /etc/Matlab.desktop /home/ubuntu/Desktop/
chmod 777 /home/ubuntu/Desktop/Matlab.desktop
chmod a+x /home/ubuntu/Desktop/Matlab.desktop
