#!/bin/bash

if ! command -v libreoffice >/dev/null 2>&1; then
    echo "LibreOffice is not installed."
    exit 0
fi

if [ -f /home/ubuntu/Desktop/LibreOffice.desktop ]; then
    echo "LibreOffice desktop shortcut is already installed."
    exit 0
fi

mkdir -p /home/ubuntu/Desktop/

cp /etc/LibreOffice.desktop /home/ubuntu/Desktop/
chmod 777 /home/ubuntu/Desktop/LibreOffice.desktop
chmod a+x /home/ubuntu/Desktop/LibreOffice.desktop
