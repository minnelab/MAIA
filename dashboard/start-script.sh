#!/bin/bash

helm repo add maia https://minnelab.github.io/MAIA/
helm repo update
#python -m pip install maia-toolkit
git clone https://github.com/minnelab/MAIA.git
pip install ./MAIA


python manage.py makemigrations authentication
python manage.py makemigrations gpu_scheduler
python manage.py makemigrations
python manage.py migrate



#python manage.py runserver 0.0.0.0:8000 --insecure &
#wait
exec "$@"