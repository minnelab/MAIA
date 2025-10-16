#!/bin/bash

/opt/conda/bin/conda init bash

python3 /opt/generate_user_environment.py --authorized-keys "$ssh_publickey"

exec "$@" &
/usr/bin/supervisord &


if [ "$INSTALL_ZSH" = "1" ]; then
    /etc/install_zsh.sh
fi


#if [ ! -f "$HOME/.zshrc" ]; then
  cp /etc/.zshrc "$HOME/"
#fi

#if [ ! -f "$HOME/.tmux.conf" ]; then
  cp /etc/.tmux.conf "$HOME/"
#fi

if [ -n "$CUSTOM_SETUP_LINK" ]; then
  if [ ! -f "$HOME/.custom_setup_done" ]; then
    http_code=$(curl -L -r 0-99 -o /dev/null -w "%{http_code}" "$CUSTOM_SETUP_LINK")
    if [ "$http_code" = "200" ] || [ "$http_code" = "206" ]; then
      wget "$CUSTOM_SETUP_LINK" -O /tmp/setup.zip
      unzip -o /tmp/setup.zip -d "$HOME/setup"
    else
      echo "CUSTOM_SETUP_LINK is not valid or not reachable, skipping download."
    fi

    if [ -f "$HOME/setup/setup.sh" ]; then
      /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
      /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
      bash "$HOME/setup/setup.sh"
    elif [ -f "$HOME/setup"/*/setup.sh ]; then
      /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
      /opt/conda/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
      bash "$HOME/setup"/*/setup.sh
    fi

    touch "$HOME/.custom_setup_done"
  fi
else
  echo "CUSTOM_SETUP_LINK is not set, skipping custom setup."
fi

/opt/conda/bin/conda init zsh
sleep infinity

