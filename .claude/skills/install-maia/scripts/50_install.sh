#!/usr/bin/env bash
# 50_install.sh: render /etc/maia-config with Ansible, then run the MAIA install in the guest one step at a time.
# Usage: 50_install.sh [--guest maia-vm] [--branch B] [--domain maia.local] [--cluster-api on|off] [--from-step <step>] [--only-step <step>]
#   Steps: render bootstrap prepare_hosts configure_hosts install_k3s k3s-traefik-cleanup kyverno-proxy-fix external-ca install_maia_core local-path-sync
#          install_maia_admin keycloak-admin configure_oidc_authentication configure_maia_dashboard
#   Check the last line: "INSTALL DONE" means success; a "FAILED: [where] <step>" line names the step to fix and resume from.
#   "bootstrap" is main.sh (install_MAIA.sh: tooling, then prepare_hosts, configure_hosts, install_k3s).
#   "prepare_hosts", "configure_hosts", "install_k3s" re-run only that step (maia-step.sh). They're skipped when bootstrap ran in
#   the same invocation.
#   Long-running work runs detached in the guest (setsid nohup) and is followed with tail, so an SSH drop
#   doesn't kill it. Re-running the same step resumes by following the existing job.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
FROM=render; ONLY=""
set -- "${REST[@]+"${REST[@]}"}"
while [[ $# -gt 0 ]]; do case "$1" in --from-step) FROM="$2"; shift 2 ;; --only-step) ONLY="$2"; shift 2 ;; *) echo "unknown arg $1"; exit 2 ;; esac; done
STEPS=(render bootstrap prepare_hosts configure_hosts install_k3s k3s-traefik-cleanup kyverno-proxy-fix external-ca install_maia_core local-path-sync install_maia_admin keycloak-admin configure_oidc_authentication configure_maia_dashboard)
want() { [[ -n "$ONLY" ]] && { [[ "$1" == "$ONLY" ]]; return; }; local s seen=0; for s in "${STEPS[@]}"; do [[ $s == "$FROM" ]] && seen=1; [[ $s == "$1" ]] && return $((1-seen)); done; return 1; }
A="$SKILL_DIR/ansible"
[[ -s "$STATE_DIR/secrets.yml" && -s "$STATE_DIR/inventory.ini" ]] || { echo "run 40_render_config.sh first"; exit 1; }

# guest_job <name> <command>: start detached in the guest unless already running, then follow it to completion.
guest_job() {
  local name="$1" cmd="$2" try rc
  # ssh exit 255 = connection failure (seen as "timed out during banner exchange" while the node is busy pulling images).
  # The job is idempotent (it re-attaches to a running job), so retry it.
  for try in 1 2 3 4 5; do
    rc=0; _guest_job_once "$name" "$cmd" || rc=$?
    [[ $rc -ne 255 ]] && return $rc
    echo "ssh failed (255), retry $try/5 in 30s" >&2; sleep 30
  done
  return 255
}
_guest_job_once() {
  local name="$1" cmd="$2"
  run guest "job-$name" <<EOF
J=/etc/maia-config/logs/job-$name; mkdir -p /etc/maia-config/logs
if [[ -f \$J.pid ]] && kill -0 "\$(cat \$J.pid)" 2>/dev/null; then echo "resuming: following running job $name"; else
  rm -f \$J.rc; setsid nohup bash -c 'cd /etc/maia-config; $cmd; echo \$? > \$0.rc.tmp; mv \$0.rc.tmp \$0.rc' "\$J" > "\$J.log" 2>&1 < /dev/null &
  echo \$! > \$J.pid; echo "started $name pid \$(cat \$J.pid)"; fi
tail -n +1 --pid="\$(cat \$J.pid)" -F "\$J.log" 2>/dev/null
for i in 1 2 3 4 5; do [[ -f \$J.rc ]] && break; sleep 1; done
rc=\$(cat \$J.rc 2>/dev/null || echo 255); echo "job $name rc=\$rc"
free -m | sed -n 2p; sudo -n k3s kubectl top nodes 2>/dev/null || true
sudo -n k3s kubectl get pods -A --no-headers 2>/dev/null | awk '\$4!="Running" && \$4!="Completed"{print "  not-running:", \$1, \$2, \$4}' | head -30 || true
exit \$rc
EOF
}

if want render; then
  run ctl ansible-galaxy <<EOF
cd "$A" && ansible-galaxy collection install -r requirements.yml 2>&1 | tail -3
EOF
  run ctl ansible-render <<EOF
cd "$A" && ANSIBLE_CONFIG="$A/ansible.cfg" ansible-playbook -i "$STATE_DIR/inventory.ini" install-maia.yml \
  -e maia_branch="$MAIA_BRANCH" -e maia_cluster_domain="$CLUSTER_DOMAIN" -e maia_cluster_name="$CLUSTER_NAME" -e maia_cluster_api="$CLUSTER_API" \
  -e '{"maia_steps": ["prepare_hosts", "configure_hosts", "install_k3s"]}' \
  -e @"$STATE_DIR/secrets.yml" 2>&1 | grep -vE '^\s*$' | tail -40
EOF
fi

RAN_BOOTSTRAP=0
want bootstrap && { guest_job bootstrap 'bash /etc/maia-config/main.sh'; RAN_BOOTSTRAP=1; }
for s in prepare_hosts configure_hosts install_k3s; do
  want $s && [[ $RAN_BOOTSTRAP == 0 ]] && guest_job $s "/etc/maia-config/maia-step.sh $s"
done

# Upstream roles/k3s starts k3s before /etc/rancher/k3s/config.yaml has `disable: [traefik]`, so k3s applies its bundled
# traefik/traefik-crd HelmCharts, then (after the restart with the final config) deletes them. Their helm-delete jobs mount the
# chart-content-traefik ConfigMap, which k3s never creates for a disabled chart, so the jobs stay in ContainerCreating and the
# finalizer wrangler.cattle.io/on-helm-chart-remove never clears (60_verify check 1 fails). MAIA ships its own traefik
# (maia-core-traefik), so with traefik disabled: drop the finalizers and the leftover helm jobs. Idempotent; a no-op when clean.
if want k3s-traefik-cleanup; then
  run guest k3s-traefik-cleanup <<'EOF'
K="sudo -n k3s kubectl -n kube-system"
if ! sudo cat /etc/rancher/k3s/config.yaml /etc/rancher/k3s/config.yaml.d/*.yaml 2>/dev/null | python3 -c '
import sys,yaml
d=[x for x in yaml.safe_load_all(sys.stdin) if x]
sys.exit(0 if any("traefik" in (c.get("disable") or []) + (c.get("disable+") or []) for c in d) else 1)'; then
  echo "traefik is not disabled in the k3s config: leaving its HelmCharts alone"; exit 0; fi
n=0
for hc in traefik traefik-crd; do
  $K get helmchart "$hc" >/dev/null 2>&1 || continue
  # k3s marks a disabled chart for deletion within seconds of starting; give it up to 60 s
  for i in $(seq 1 12); do [[ -n "$($K get helmchart "$hc" -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null)" ]] && break; sleep 5; done
  if [[ -z "$($K get helmchart "$hc" -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null)" ]]; then
    echo "WARN: helmchart $hc exists and is not being deleted although traefik is disabled; leaving it"; continue; fi
  $K patch helmchart "$hc" --type=merge -p '{"metadata":{"finalizers":null}}'; n=$((n+1))
done
for j in helm-install-traefik helm-install-traefik-crd helm-delete-traefik helm-delete-traefik-crd; do
  $K delete job "$j" --ignore-not-found --wait=false
done
echo "stuck traefik HelmCharts released: $n"
sleep 10; $K get helmchart,jobs,pods 2>/dev/null | grep -E "traefik" | grep -v svclb-maia-core-traefik || echo "no k3s traefik leftovers"
EOF
fi

# Upstream roles/argocd applies the Kyverno ClusterPolicy inject-proxy-env-vars whenever Kyverno is freshly installed, with no
# proxy condition, so with no proxy every new pod gets HTTP(S)_PROXY=":3130" (argocd-server can't reach the API, and
# install_maia_core fails at "Login to ArgoCD using CLI"). With no proxy configured: delete the policy and the controller-owned
# pods that already got the bogus env, so their controllers recreate them clean. Idempotent; a no-op when nothing was injected.
if want kyverno-proxy-fix; then
  run guest kyverno-proxy-fix <<'EOF'
K="sudo -n k3s kubectl"
P=$(python3 -c 'import yaml; c=yaml.safe_load(open("/etc/maia-config/config.yaml")); print(c.get("install_k3s",{}).get("proxy_ip") or "")')
if [[ -n "$P" ]]; then echo "proxy_ip is set ($P): leaving the Kyverno proxy policy alone"; exit 0; fi
if $K get clusterpolicy inject-proxy-env-vars >/dev/null 2>&1; then
  $K get clusterpolicy inject-proxy-env-vars -o yaml > /etc/maia-config/inject-proxy-env-vars.removed.yaml
  $K delete clusterpolicy inject-proxy-env-vars
else echo "no inject-proxy-env-vars policy"; fi
$K get pods -A -o json | python3 -c '
import json,sys
for p in json.load(sys.stdin)["items"]:
    cs=p["spec"].get("containers",[])+p["spec"].get("initContainers",[])
    if any(e["name"].lower() in ("http_proxy","https_proxy") and str(e.get("value","")).startswith(":") for c in cs for e in (c.get("env") or [])):
        print(p["metadata"]["namespace"], p["metadata"]["name"], "owned" if p["metadata"].get("ownerReferences") else "bare")' > /tmp/proxy-pods.$$
n=0; while read -r ns name own; do
  if [[ $own == owned ]]; then $K -n "$ns" delete pod "$name" --wait=false; n=$((n+1)); else echo "WARN: bare pod $ns/$name has the bogus proxy env; recreate it by hand"; fi
done < /tmp/proxy-pods.$$; rm -f /tmp/proxy-pods.$$
echo "pods recreated: $n"
[[ $n -gt 0 ]] && $K -n argocd wait --for=condition=Ready pod --all --timeout=300s >/dev/null && echo "argocd pods Ready"
true
EOF
fi

# Selfsigned alone breaks install_maia_admin (upstream rootCA["cert"] bug), and upstream only creates OpenWebUI's
# custom-ca-cert from externalCA. So write the CA that signs the ingress certs (the k3s server CA, kept by install_k3s as
# cert-manager/kubernetes-ca) to /etc/maia-config/maia-ca.crt, trust it on the node, and re-render: the role then adds externalCA.
if want external-ca; then
  run guest external-ca <<'EOF'
K="sudo -n k3s kubectl"
$K -n cert-manager get secret kubernetes-ca -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/maia-ca.crt
[[ -s /tmp/maia-ca.crt ]] || { echo "cert-manager/kubernetes-ca missing: did install_k3s run with enable_ca: true?"; exit 1; }
openssl x509 -in /tmp/maia-ca.crt -noout -subject -enddate
cmp -s /tmp/maia-ca.crt /etc/maia-config/ca.crt && echo "same as rootCA (/etc/maia-config/ca.crt)" || echo "WARN: differs from rootCA"
sudo install -m 0644 /tmp/maia-ca.crt /usr/local/share/ca-certificates/maia-ca.crt && sudo update-ca-certificates 2>&1 | tail -1
install -m 0644 /tmp/maia-ca.crt /etc/maia-config/maia-ca.crt; rm -f /tmp/maia-ca.crt
EOF
  run ctl ansible-render-ca <<EOF
cd "$A" && ANSIBLE_CONFIG="$A/ansible.cfg" ansible-playbook -i "$STATE_DIR/inventory.ini" install-maia.yml \
  -e maia_branch="$MAIA_BRANCH" -e maia_cluster_domain="$CLUSTER_DOMAIN" -e maia_cluster_name="$CLUSTER_NAME" -e maia_cluster_api="$CLUSTER_API" \
  -e '{"maia_steps": ["prepare_hosts", "configure_hosts", "install_k3s"]}' \
  -e @"$STATE_DIR/secrets.yml" 2>&1 | grep -vE '^\s*$' | tail -4
EOF
  run guest external-ca-check <<'EOF'
python3 -c 'import yaml; c=yaml.safe_load(open("/etc/maia-config/config.yaml")); e=c["cluster_config_extra_env"]["externalCA"]; print("externalCA:", e["name"], e["cert"])'
EOF
fi

want install_maia_core && guest_job install_maia_core "/etc/maia-config/maia-step.sh install_maia_core"

# maia-core-local-path ends up OutOfSync (health unknown) on every install: the core layer first creates its objects with
# kubectl apply, so ArgoCD doesn't consider them its own. One sync adopts them. Safe: the app has no generated secrets.
if want local-path-sync; then
  run guest local-path-sync <<'EOF'
K="sudo -n k3s kubectl -n argocd"
st=$($K get application maia-core-local-path -o jsonpath='{.status.sync.status}/{.status.health.status}')
if [[ $st == Synced/Healthy ]]; then echo "maia-core-local-path already $st"; exit 0; fi
echo "maia-core-local-path is $st: syncing"
$K patch application maia-core-local-path --type=merge -p '{"operation":{"initiatedBy":{"username":"install-maia"},"sync":{"prune":false}}}'
for i in $(seq 1 60); do p=$($K get application maia-core-local-path -o jsonpath='{.status.operationState.phase}'); [[ $p == Succeeded || $p == Failed || $p == Error ]] && break; sleep 5; done
st=$($K get application maia-core-local-path -o jsonpath='{.status.operationState.phase} {.status.sync.status}/{.status.health.status}'); echo "after sync: $st"
[[ $st == "Succeeded Synced/Healthy" ]]
EOF
fi

want install_maia_admin && guest_job install_maia_admin "/etc/maia-config/maia-step.sh install_maia_admin"

# Upstream install_maia_admin only runs MAIA_configure_keycloak (it creates the first-access admin: <ADMIN_EMAIL>, temporary
# password "admin") when the Keycloak app was *not yet synced*, so after a resumed run the realm can have no users. Run it again,
# and treat its 409 "already exists" (it creates the maia-public client without catching that) as success. Then confirm through the
# Keycloak admin API that the admin user exists.
if want keycloak-admin; then
  run guest keycloak-admin <<'EOF'
export PATH="$HOME/.local/bin:$PATH"
D=$(python3 -c 'import yaml; print(yaml.safe_load(open("/etc/maia-config/config.yaml"))["env"]["CLUSTER_DOMAIN"])')
E=$(python3 -c 'import yaml; print(yaml.safe_load(open("/etc/maia-config/config.yaml"))["env"]["ADMIN_EMAIL"])')
S=$(jq -r .keycloak_client_secret /etc/maia-config/env.json)
rc=0; out=$(MAIA_configure_keycloak --server_url "https://iam.$D" --client_secret "$S" --admin_email "$E" 2>&1) || rc=$?; unset S
echo "$out" | grep -vE "InsecureRequestWarning|warnings.warn|^\s*$" | tail -3
if [[ $rc -ne 0 ]] && ! grep -q "already exists" <<<"$out"; then echo "MAIA_configure_keycloak failed (rc=$rc)"; exit 1; fi
[[ $rc -ne 0 ]] && echo "(409 'already exists': Keycloak was already configured, which is fine)"
# Keycloak admin console user is Bitnami's "user"; its password is MAIA's keycloak_admin_password (env.json)
AP=$(jq -r .keycloak_admin_password /etc/maia-config/env.json)
T=$(curl -sk --max-time 20 "https://iam.$D/realms/master/protocol/openid-connect/token" -d grant_type=password -d client_id=admin-cli \
    -d username=user --data-urlencode "password=$AP" | jq -r '.access_token // empty'); unset AP
n=$(curl -sk --max-time 20 -H "Authorization: Bearer $T" "https://iam.$D/admin/realms/maia/users?email=$E&exact=true" | jq 'length'); unset T
[[ "$n" == 1 ]] || { echo "first-access admin $E NOT found in realm maia"; exit 1; }
echo "first-access admin: $E exists (temporary password from the Installation README; Keycloak forces a change at first login)"
EOF
fi

for s in configure_oidc_authentication configure_maia_dashboard; do want "$s" && guest_job "$s" "/etc/maia-config/maia-step.sh $s"; done
want configure_maia_dashboard && echo "NOTE: the dashboard pod pip-installs MAIA at start; maia.<domain> answers 502 for up to ~10 min (60_verify waits)."
echo "INSTALL DONE (steps from '$FROM'${ONLY:+, only $ONLY})"
