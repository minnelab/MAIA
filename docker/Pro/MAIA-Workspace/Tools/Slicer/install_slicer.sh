#!/bin/bash


if [ -d $HOME/Documents/Slicer-5.8.1-2025-03-03-linux-amd64 ]; then
    echo "Slicer is already installed."
    exit 0
fi

sudo chmod 777 /etc/
wget https://download.slicer.org/bitstream/67c51fc129825655577cfee9 -O /etc/slicer.tar.gz

sudo cp /etc/slicer.tar.gz $HOME/Documents/

tar -xf $HOME/Documents/slicer.tar.gz -C $HOME/Documents/

$HOME/Documents/Slicer-5.8.1-linux-amd64/Slicer --python-script /home/maia-user/Tutorials/Slicer_Extensions.py &

cp /etc/Slicer.desktop $HOME/Desktop/

