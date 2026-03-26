#!/bin/bash

helm repo add maia https://minnelab.github.io/MAIA/
helm repo update

if [ -n "$DEV_TAG" ]; then
    pip install git+https://github.com/minnelab/MAIA.git@$DEV_TAG
else
    pip install --pre --upgrade maia-toolkit==$MAIA_VERSION
fi

python manage.py makemigrations authentication
python manage.py makemigrations gpu_scheduler
python manage.py makemigrations
python manage.py migrate



#python manage.py runserver 0.0.0.0:8000 --insecure &
#wait
exec "$@"