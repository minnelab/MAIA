#!/bin/bash

/opt/conda/bin/conda create -y -n napari-env -c conda-forge python=3.11
/opt/conda/bin/conda install -n napari-env -c conda-forge napari pyqt -y

cp /etc/Napari.desktop $HOME/Desktop/