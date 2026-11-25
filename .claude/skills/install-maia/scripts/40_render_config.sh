#!/usr/bin/env bash
# 40_render_config.sh: generate secrets once (openssl rand) in $STATE_DIR/secrets.env (0600, control node only),
# derive secrets.yml for `ansible-playbook -e @…`, and render the inventory from inventory.ini.j2.
# Re-running keeps existing secrets. Never prints them.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
umask 077
SEC="$STATE_DIR/secrets.env"
# Add any missing key, so a secrets.env from an older run picks up newly introduced secrets; existing values are kept.
touch "$SEC"
for k in MAIA_KEYCLOAK_CLIENT_SECRET MAIA_OPENWEBUI_ADMIN_PASSWORD MAIA_WEBUI_SECRET_KEY MAIA_GUACAMOLE_PASSWORD \
         MAIA_HARBOR_ADMIN_PASSWORD; do
  if grep -q "^$k=" "$SEC"; then echo "keeping $k"; else echo "$k=$(openssl rand -hex 24)" >> "$SEC"; echo "generated $k"; fi
done
chmod 600 "$SEC"
awk -F= 'NF==2{printf "%s: \"%s\"\n", tolower($1), $2}' "$SEC" > "$STATE_DIR/secrets.yml"; chmod 600 "$STATE_DIR/secrets.yml"
GUEST_USER="$(ssh -G "$GUEST" | awk '/^user /{print $2}')"
sed -e "s|{{GUEST}}|$GUEST|" -e "s|{{GUEST_USER}}|$GUEST_USER|" -e "s|{{STATE_DIR}}|$STATE_DIR|" \
  "$SKILL_DIR/ansible/inventory.ini.j2" > "$STATE_DIR/inventory.ini"
echo "inventory: $STATE_DIR/inventory.ini (guest user from ssh -G: $GUEST_USER)"
ls -l "$STATE_DIR" | sed 1d | awk '{print $1, $NF}'
