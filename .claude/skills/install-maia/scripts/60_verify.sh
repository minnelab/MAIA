#!/usr/bin/env bash
# 60_verify.sh: verification steps 1–4 and 6. Ingress is checked through an SSH tunnel from the control node.
# Usage: 60_verify.sh [--hypervisor <ssh-alias>] [--guest maia-vm] [--domain maia.local] [--cluster-api on|off] [--local-port 8443]
#   remote-hypervisor: tunnel = ssh -L <local>:127.0.0.1:$HTTPS_PORT <hypervisor>. Local: no tunnel needed.
#   existing-ssh-host: tunnel = ssh -L <local>:127.0.0.1:443 <guest>  (pass --hypervisor "" and --https-port 443)
#   Check 7 records what the cluster runs (MAIA commit, k3s, ArgoCD sources/revisions, Helm releases, image digests) in
#   /etc/maia-config/deployed-versions.md and ~/.maia-vm/<name>/deployed/ (latest.md + one file per change), and prints the
#   diff against the previous record. It never fails VERIFY. --versions-only runs just check 7.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
LPORT=8443; VERSIONS_ONLY=0; set -- "${REST[@]+"${REST[@]}"}"
while [[ $# -gt 0 ]]; do case "$1" in --local-port) LPORT="$2"; shift 2 ;; --versions-only) VERSIONS_ONLY=1; shift ;;
  *) echo "unknown arg $1"; exit 2 ;; esac; done
fail=0

# 7. Record of what is deployed. Informational: a failure here is reported but doesn't fail VERIFY.
record_versions() {
  echo "== 7. deployed versions"
  { echo "python3 - > /etc/maia-config/deployed-versions.md.tmp <<'PY'"; cat "$SKILL_DIR/scripts/deployed_versions.py"; echo "PY"
    echo "mv /etc/maia-config/deployed-versions.md.tmp /etc/maia-config/deployed-versions.md"
    echo "sed -n '/^## MAIA/,/^## k3s/p' /etc/maia-config/deployed-versions.md | grep '^| [nd]'"
    echo "echo \"argocd sources: \$(sed -n '/^## ArgoCD/,/^## Helm/p' /etc/maia-config/deployed-versions.md | grep -c '^| maia\\|^| ml'), images: \$(grep -c 'sha256:' /etc/maia-config/deployed-versions.md)\""
  } | run guest verify-7-versions || { echo "WARN: could not collect deployed versions"; return 0; }
  run ctl verify-7-record <<EOF || echo "WARN: could not save the deployed-versions record"
D="$STATE_DIR/deployed"; mkdir -p "\$D"; new="\$D/\$(date +%Y%m%d-%H%M%S).md"
# -n: this script reaches bash on stdin; without it ssh would swallow the rest of the script
ssh -n ${GUEST_SSH_OPTS[*]} $GUEST cat /etc/maia-config/deployed-versions.md > "\$new"
prev=\$(ls "\$D"/2*.md 2>/dev/null | grep -vxF "\$new" | tail -n 1 || true)
cp "\$new" "\$D/latest.md"
# Line 1 is the timestamp; compare the rest. Keep one file per distinct state.
if [[ -z "\$prev" ]]; then echo "first record: \$new"
elif cmp -s <(tail -n +2 "\$prev") <(tail -n +2 "\$new"); then rm -f "\$new"; echo "unchanged since \$(basename "\$prev") (latest.md refreshed)"
else echo "changed since \$(basename "\$prev") (- before, + now):"; { diff <(tail -n +2 "\$prev") <(tail -n +2 "\$new") || true; } | sed -n 's/^</-/p; s/^>/+/p' | cut -c1-220 | head -n 80 || true
  echo "record: \$new"; fi
EOF
}
if [[ $VERSIONS_ONLY == 1 ]]; then record_versions; exit 0; fi

echo "== 1. cluster"
run guest verify-1-cluster <<'EOF' || fail=1
K="sudo -n k3s kubectl"
$K get nodes -o wide
# Right after configure_maia_dashboard a rollout is still in progress (seen: 2 dashboard pods ContainerCreating 50 s after the
# install ended), so wait up to 10 min for pods to settle before failing. Check 2 then sees the apps Healthy instead of Progressing.
for i in $(seq 60); do
  bad=$($K get pods -A --no-headers | awk '$4!="Running" && $4!="Completed"')
  [[ -z "$bad" ]] && break
  [[ $i == 1 ]] && { echo "waiting up to 10 min for:"; echo "$bad"; }
  sleep 10
done
[[ -z "$bad" ]] && echo "all pods Running/Completed" || { echo "NOT READY after 10 min:"; echo "$bad"; exit 1; }
EOF

echo "== 2. argocd apps"
run guest verify-2-argocd <<'EOF' || fail=1
# Expected = the apps install-maia asked for (config.yaml core + admin lists), the dashboard, and Kubeflow's ml-* children.
# The MAIA app-of-apps also defines apps that are deliberately not synced (gpu-*, loki, prometheus, tempo…); those are listed only.
want=$(python3 -c 'import yaml; c=yaml.safe_load(open("/etc/maia-config/config.yaml")); print(" ".join(c["install_maia_core"]["maia_core_argocd_applications"]+c["install_maia_admin"]["maia_admin_argocd_applications"]))')
sudo -n k3s kubectl get applications.argoproj.io -A --no-headers -o custom-columns=A:.metadata.name,S:.status.sync.status,H:.status.health.status > /tmp/apps.$$
bad=0
while read -r a s h; do
  exp=0; for w in $want; do [[ $a == "$w" ]] && exp=1; done; [[ $a == ml-* || $a == *dashboard* ]] && exp=1
  if [[ $exp == 1 ]]; then
    if [[ $h != Healthy ]]; then echo "BAD   $a $s/$h"; bad=1
    elif [[ $s == Synced ]]; then echo "OK    $a"
    else
      # OutOfSync but Healthy: accept only known-benign drift (references/troubleshooting.md "ArgoCD drift"):
      # controller-filled CRDs/ClusterRoles/webhook configs (caBundle), k3s's own coredns ConfigMap, and Bitnami's random keycloak-postgresql Secret
      # (NEVER sync that app to "fix" it: a sync rotates the DB password and breaks Keycloak).
      drift=$(sudo -n k3s kubectl -n argocd get application "$a" -o json | python3 -c '
import json,sys
ok={("CustomResourceDefinition",None),("ClusterRole",None),("MutatingWebhookConfiguration",None),("ValidatingWebhookConfiguration",None),("ConfigMap","kube-system/coredns"),("Secret","keycloak/maia-admin-keycloak-postgresql")}
for r in json.load(sys.stdin)["status"].get("resources",[]):
    if r.get("status")=="Synced": continue
    key=r.get("namespace","")+"/"+r["name"]
    benign=(r["kind"],None) in ok or (r["kind"],key) in ok
    print(("benign " if benign else "UNEXPECTED ")+r["kind"]+" "+key)')
      if grep -q UNEXPECTED <<<"$drift"; then echo "BAD   $a OutOfSync:"; grep UNEXPECTED <<<"$drift" | sed 's/^/        /'; bad=1
      else echo "OK    $a (Healthy; benign drift: $(grep -c benign <<<"$drift") resources)"; fi
    fi
  else echo "skip  $a $s/$h (not in the install set)"; fi
done < /tmp/apps.$$
for w in $want; do grep -q "^$w " /tmp/apps.$$ || { echo "MISSING app $w"; bad=1; }; done
rm -f /tmp/apps.$$
[[ $bad == 0 ]] && echo "all expected apps Healthy (Synced, or only benign drift)" || exit 1
EOF

echo "== 3+4. ingress + OIDC through tunnel"
TUN=""
if [[ -n "$HYPERVISOR" ]]; then
  CP="$STATE_DIR/tunnel.sock"
  ssh -o ExitOnForwardFailure=yes -o ControlMaster=yes -o ControlPath="$CP" -fN -L "127.0.0.1:$LPORT:127.0.0.1:$HTTPS_PORT" "$HYPERVISOR"
  TUN="$CP"; trap 'ssh -o ControlPath="$CP" -O exit "$HYPERVISOR" 2>/dev/null || true' EXIT
else LPORT=$HTTPS_PORT; fi
# The dashboard pod pip-installs MAIA at start (2–10 min after configure_maia_dashboard): wait for it instead of failing on 502
run ctl verify-wait-dashboard <<EOF || true
for i in \$(seq 1 60); do
  c=\$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 --resolve maia.$CLUSTER_DOMAIN:$LPORT:127.0.0.1 https://maia.$CLUSTER_DOMAIN:$LPORT/maia/)
  [[ \$c =~ ^(200|301|302)\$ ]] && { echo "dashboard up (http \$c) after ~\$(( (i-1)*10 ))s"; exit 0; }; sleep 10
done
echo "dashboard still not up after 10 min (last http \$c)"; exit 1
EOF
run ctl verify-3-ingress <<EOF || fail=1
f=0; T=\$(mktemp)
for h in maia iam registry kubeflow chat login; do
  code=\$(curl -sk -o \$T -w '%{http_code}' --max-time 20 --resolve \$h.$CLUSTER_DOMAIN:$LPORT:127.0.0.1 https://\$h.$CLUSTER_DOMAIN:$LPORT/)
  note=""
  # kubeflow sits behind oauth2-proxy, which serves its "Sign In" page with HTTP 403 when unauthenticated
  [[ \$code == 403 ]] && grep -q '<title>Sign In</title>' \$T && note=" (oauth2-proxy sign-in page)" && code=OK403
  echo "\$h.$CLUSTER_DOMAIN -> \$code\$note"; [[ \$code =~ ^(200|301|302|303|307|308|OK403)\$ ]] || f=1
done
rm -f \$T; exit \$f
EOF
rm -f "$STATE_DIR/.verify-login-rejected"
run ctl verify-4-oidc <<EOF || fail=1
R="--resolve iam.$CLUSTER_DOMAIN:$LPORT:127.0.0.1 --resolve maia.$CLUSTER_DOMAIN:$LPORT:127.0.0.1"; J=\$(mktemp); P=\$(mktemp)
curl -sk \$R --max-time 20 https://iam.$CLUSTER_DOMAIN:$LPORT/realms/maia/.well-known/openid-configuration | jq -r '"issuer: " + .issuer'
echo "dashboard /maia/ -> \$(curl -sk \$R --max-time 20 -o /dev/null -w '%{http_code} %{redirect_url}' https://maia.$CLUSTER_DOMAIN:$LPORT/maia/)"
# mozilla-django-oidc entry point → Keycloak authorize URL (Keycloak's hostname has no port, so rewrite it onto the tunnel)
loc=\$(curl -sk \$R --max-time 20 -c \$J -o /dev/null -w '%{redirect_url}' https://maia.$CLUSTER_DOMAIN:$LPORT/maia/oidc/authenticate/)
echo "\$loc" | grep -q "/realms/maia/protocol/openid-connect/auth?.*client_id=maia" || { echo "no redirect to Keycloak: \$loc"; exit 1; }
echo "oidc/authenticate -> Keycloak authorize (client_id=maia)"
kc=\$(echo "\$loc" | sed "s#https://iam.$CLUSTER_DOMAIN/#https://iam.$CLUSTER_DOMAIN:$LPORT/#")
code=\$(curl -sk \$R --max-time 30 -b \$J -c \$J -o \$P -w '%{http_code}' "\$kc")   # -c: keep Keycloak's AUTH_SESSION cookie
grep -q 'id="kc-form-login"' \$P && echo "Keycloak login form OK (http \$code)" || { echo "no Keycloak login form (http \$code)"; grep -o 'Invalid parameter[^<]*' \$P; rm -f \$J \$P; exit 1; }
# First-access login (Installation README: <ADMIN_EMAIL> / temporary "admin"; not a generated secret)
act=\$(grep -o 'id="kc-form-login"[^>]*action="[^"]*"' \$P | sed 's/.*action="//; s/"\$//; s/&amp;/\&/g' | sed "s#https://iam.$CLUSTER_DOMAIN/#https://iam.$CLUSTER_DOMAIN:$LPORT/#")
res=\$(curl -sk \$R --max-time 30 -b \$J -c \$J -o \$P -w '%{http_code} %{redirect_url}' --data-urlencode "username=admin@$CLUSTER_DOMAIN" --data-urlencode "password=admin" --data credentialId= "\$act")
if grep -q 'kc-passwd-update-form' \$P || [[ "\$res" == *"required-action?execution=UPDATE_PASSWORD"* ]]; then echo "first-access login admin@$CLUSTER_DOMAIN OK: Keycloak asks for a new password (UPDATE_PASSWORD)"
elif [[ "\$res" == *"/maia/oidc/callback/"* ]]; then echo "login admin@$CLUSTER_DOMAIN OK: redirected to dashboard callback"
elif grep -q 'Invalid username or password' \$P; then
  # Expected once someone has logged in and replaced the temporary password; the guest-side check below tells the cases apart.
  echo "first-access login rejected (Invalid username or password): checking the account in Keycloak"; touch "$STATE_DIR/.verify-login-rejected"
else echo "first-access login failed: unexpected response (\$res)"; rm -f \$J \$P; exit 1; fi
rm -f \$J \$P
EOF
# A rejected temporary password is a WARN only if the account exists, is enabled and has no pending UPDATE_PASSWORD, i.e. a
# permanent password was set. Missing/disabled account, or UPDATE_PASSWORD still pending (temporary password should work), fail.
if [[ -f "$STATE_DIR/.verify-login-rejected" ]]; then
  rm -f "$STATE_DIR/.verify-login-rejected"
  run guest verify-4-admin-account <<'EOF' || fail=1
D=$(python3 -c 'import yaml; print(yaml.safe_load(open("/etc/maia-config/config.yaml"))["env"]["CLUSTER_DOMAIN"])')
E=$(python3 -c 'import yaml; print(yaml.safe_load(open("/etc/maia-config/config.yaml"))["env"]["ADMIN_EMAIL"])')
AP=$(jq -r .keycloak_admin_password /etc/maia-config/env.json)
T=$(curl -sk --max-time 20 "https://iam.$D/realms/master/protocol/openid-connect/token" -d grant_type=password -d client_id=admin-cli \
    -d username=user --data-urlencode "password=$AP" | jq -r '.access_token // empty'); unset AP
[[ -n "$T" ]] || { echo "cannot get a Keycloak admin token (console user 'user'): can't tell why the login was rejected"; exit 1; }
U=$(curl -sk --max-time 20 -H "Authorization: Bearer $T" "https://iam.$D/admin/realms/maia/users?email=$E&exact=true")
n=$(jq 'length' <<<"$U")
[[ "$n" == 1 ]] || { unset T; echo "first-access admin $E NOT found in realm maia (users matching: $n): re-run 50_install.sh --only-step keycloak-admin"; exit 1; }
id=$(jq -r '.[0].id' <<<"$U"); en=$(jq -r '.[0].enabled' <<<"$U"); ra=$(jq -r '.[0].requiredActions | join(",")' <<<"$U")
pw=$(curl -sk --max-time 20 -H "Authorization: Bearer $T" "https://iam.$D/admin/realms/maia/users/$id/credentials" \
     | jq -r '[.[] | select(.type=="password")][0].createdDate // empty'); unset T
set_at=$([[ -n "$pw" ]] && date -d "@$((pw/1000))" -Is || echo unknown)
echo "account $E: enabled=$en requiredActions=[${ra}] password set: $set_at"
[[ "$en" == true ]] || { echo "account is disabled"; exit 1; }
if [[ ",$ra," == *",UPDATE_PASSWORD,"* ]]; then echo "UPDATE_PASSWORD is still pending, so the temporary password should work, yet it was rejected"; exit 1; fi
echo "WARN: the temporary password was already replaced (expected after the first login). The login form and OIDC flow are OK;"
echo "      the full login can't be tested without the new password."
EOF
fi

record_versions

echo "== 6. no generated secret values in skill dir or logs"
# Dashboard Cluster API matches --cluster-api: on = the token from secrets.env authenticates (status 200, enabled) and no token
# is refused; off = 404 "disabled". The token is read at run time and passed via a file descriptor: never in this text or argv.
run ctl verify-cluster-api <<EOF || fail=1
U=https://maia.$CLUSTER_DOMAIN:$LPORT/maia/cluster-api/; R="--resolve maia.$CLUSTER_DOMAIN:$LPORT:127.0.0.1"; B=\$(mktemp)
if [[ "$CLUSTER_API" == on ]]; then
  tok=\$(sed -n 's/^MAIA_CLUSTER_API_TOKEN=//p' "$STATE_DIR/secrets.env")
  [[ -n "\$tok" ]] || { echo "MAIA_CLUSTER_API_TOKEN missing from secrets.env: run 40_render_config.sh"; exit 1; }
  c=\$(curl -sk \$R --max-time 20 -o \$B -w '%{http_code}' -H @<(printf 'Authorization: Bearer %s\n' "\$tok") \$U); unset tok
  echo "with token -> \$c \$(jq -c '{enabled, caller, credentials, tools: (.tools // {} | map_values(.available))}' \$B 2>/dev/null)"
  [[ \$c == 200 ]] && jq -e '.enabled == true and .caller == "cluster-api-token"' \$B >/dev/null || { rm -f \$B; exit 1; }
  c=\$(curl -sk \$R --max-time 20 -o /dev/null -w '%{http_code}' \$U); echo "without token -> \$c"
  rm -f \$B; [[ \$c =~ ^(401|403)\$ ]]
else
  c=\$(curl -sk \$R --max-time 20 -o \$B -w '%{http_code}' \$U); echo "cluster api (expected disabled) -> \$c \$(head -c 120 \$B)"
  grep -q disabled \$B; r=\$?; rm -f \$B; [[ \$c == 404 && \$r == 0 ]]
fi
EOF
run ctl verify-6-secrets <<EOF || fail=1
hits=0
while IFS='=' read -r k v; do
  [[ -n "\$v" ]] || continue
  if grep -rqF -- "\$v" "$SKILL_DIR"; then echo "LEAK: value of \$k found in $SKILL_DIR"; hits=1; fi
done < "$STATE_DIR/secrets.env"
# keyword sweep: show matches that carry a long hex/random-looking value. Skip this check's own logs: they quote what it flagged.
grep -rnE '(password|secret|token)[^ ]*[:=] *"?[A-Za-z0-9+/_-]{20,}' --exclude='*-verify-6-secrets.log' "$SKILL_DIR" | grep -vE 'openssl rand|\\\$|\{\{' | head && hits=1 || true
[[ \$hits -eq 0 ]] && echo "no generated secrets found" || exit 1
EOF
[[ $fail -eq 0 ]] && echo "VERIFY OK" || { echo "VERIFY FAILED"; exit 1; }
