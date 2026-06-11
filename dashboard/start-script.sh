#!/bin/bash

helm repo add maia https://minnelab.github.io/MAIA/
helm repo update

if [ -n "$MAIA_TAG" ]; then
    pip install git+https://github.com/minnelab/MAIA.git@$MAIA_TAG
else
    pip install --pre --upgrade maia-toolkit==$MAIA_VERSION
fi


#python manage.py runserver 0.0.0.0:8000 --insecure &
#wait
exec "$@"