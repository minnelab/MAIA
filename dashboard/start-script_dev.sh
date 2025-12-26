#!/bin/bash

helm repo add maia https://minnelab.github.io/MAIA/
helm repo update

cd /etc/MAIA/
git checkout $DEV_BRANCH
git pull

pip install -e .
git config --global user.email $GIT_EMAIL
git config --global user.name $GIT_NAME
gpg --import $GPG_KEY
git config --global user.signingkey "$(gpg --list-secret-keys --with-colons | awk -F: '$1=="sec"{print $5; exit}')"

cd /etc/MAIA/dashboard
python manage.py makemigrations authentication
python manage.py makemigrations gpu_scheduler
python manage.py makemigrations
python manage.py migrate



#python manage.py runserver 0.0.0.0:8000 --insecure &
#wait
exec "$@"