#!/bin/bash

helm repo add maia https://minnelab.github.io/MAIA/
helm repo update

cd /etc
git clone --single-branch --branch $DEV_BRANCH  https://github.com/minnelab/MAIA.git
cd MAIA
git fetch origin $DEV_BRANCH:refs/remotes/origin/$DEV_BRANCH
git checkout -b $DEV_BRANCH origin/$DEV_BRANCH
git pull

pip install -e .
git config --global user.email $GIT_EMAIL
git config --global user.name $GIT_NAME
gpg --import $GPG_KEY
git config --global user.signingkey "$(gpg --list-secret-keys --with-colons | awk -F: '$1=="sec"{print $5; exit}')"

#python manage.py runserver 0.0.0.0:8000 --insecure &
#wait
exec "$@"