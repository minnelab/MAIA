#!/bin/bash -e

USERNAMES="maia-demo,demo"

IFS=',' read -r -a USERNAMES <<< "$USERNAMES"

for USERNAME in "${USERNAMES[@]}"; do
  sudo useradd -m -s /bin/zsh $USERNAME
  sudo adduser $USERNAME sudo
  echo "$USERNAME ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers
  echo "$USERNAME:$USERNAME" | sudo chpasswd
done
#Only for debugging and development
exec "$@"
