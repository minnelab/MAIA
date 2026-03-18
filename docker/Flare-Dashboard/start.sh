#!/bin/bash -e


sed -i 's|worker_processes .*|worker_processes 1;|' /etc/nginx/nginx.conf

envsubst '${INGRESS_PATH}' < /etc/default.template > default
mv default /etc/nginx/sites-enabled/
nginx -c /etc/nginx/nginx.conf -g 'daemon off;' &

exec "$@" 