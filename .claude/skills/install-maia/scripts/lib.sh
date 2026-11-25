#!/usr/bin/env bash
# Shared helpers for the install-maia scripts. Source it; don't execute it.
#
# Three places a command can run:
#   ctl    the control node (where these scripts run, e.g. WSL)
#   hv     the hypervisor: `ssh $HYPERVISOR` when --hypervisor is set, else the control node itself
#   guest  the MAIA VM/server, reached as `ssh $GUEST` (an ssh_config alias, e.g. maia-vm with ProxyJump)
#
# run <ctl|hv|guest> <label>  reads a bash script on stdin, runs it there, tees the output
# to $LOG_DIR/<ts>-<label>.log and adds a row (where, label, duration, rc, output tail) to $JOURNAL.
# Never put secret values in the script text: it is logged. Read secrets from files on the target.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${VM_NAME:=maia-vm}"
: "${GUEST:=maia-vm}"
: "${HYPERVISOR:=}"
: "${MAIA_BRANCH:=157-add-tool-for-mcp-server-to-execute-helm-commands-from-dashboard}"
: "${VM_CPUS:=8}"   # 4 is too few: MAIA's CPU requests (Keycloak alone asks for 2) exceed 4 cores
: "${VM_MEM_GB:=16}"
: "${VM_DISK_GB:=150}"
# QEMU -drive cache mode. writeback = QEMU default (durable). unsafe = ignore guest flushes: needed on HDD hypervisors,
# where ~67 ms fsyncs make MAIA's DB first-init outlast liveness probes. Risk: a hypervisor crash can corrupt the VM disk.
: "${VM_DISK_CACHE:=writeback}"
: "${SSH_PORT:=2222}"
: "${HTTPS_PORT:=8443}"
: "${HTTP_PORT:=8080}"
: "${API_PORT:=16443}"
: "${CLUSTER_DOMAIN:=maia.local}"
: "${CLUSTER_NAME:=$VM_NAME}"
# Dashboard Cluster API (kubectl/helm/argocd over HTTPS, token MAIA_CLUSTER_API_TOKEN from secrets.env): on | off
: "${CLUSTER_API:=off}"
: "${SSH_PUBKEY:=$HOME/.ssh/id_ed25519.pub}"
APPROVED=0

parse_common_args() {
  REST=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --hypervisor) HYPERVISOR="$2"; shift 2 ;;
      --name) VM_NAME="$2"; CLUSTER_NAME="$2"; shift 2 ;;
      --guest) GUEST="$2"; shift 2 ;;
      --branch) MAIA_BRANCH="$2"; shift 2 ;;
      --domain) CLUSTER_DOMAIN="$2"; shift 2 ;;
      --ssh-port) SSH_PORT="$2"; shift 2 ;;
      --https-port) HTTPS_PORT="$2"; shift 2 ;;
      --http-port) HTTP_PORT="$2"; shift 2 ;;
      --api-port) API_PORT="$2"; shift 2 ;;
      --disk-cache) VM_DISK_CACHE="$2"; shift 2 ;;
      --cluster-api) CLUSTER_API="$2"; shift 2 ;;
      --approve-host-changes) APPROVED=1; shift ;;
      -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d'; exit 0 ;;
      *) REST+=("$1"); shift ;;
    esac
  done
  case "$CLUSTER_API" in on|off) ;; *) echo "--cluster-api must be on or off (got: $CLUSTER_API)"; exit 2 ;; esac
  # Control-node state (secrets, known_hosts, rendered inventory). Never on the hypervisor, never in the repo.
  STATE_DIR="$HOME/.maia-vm/$VM_NAME"
  LOG_DIR="${MAIA_LOG_DIR:-$SKILL_DIR/logs}"
  JOURNAL="$LOG_DIR/journal.md"
  mkdir -p "$STATE_DIR" "$LOG_DIR"; chmod 700 "$HOME/.maia-vm" "$STATE_DIR"
  [[ -f "$LOG_DIR/.gitignore" ]] || printf '*\n' > "$LOG_DIR/.gitignore"
  GUEST_SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=60 -o StrictHostKeyChecking=accept-new
                  -o UserKnownHostsFile="$STATE_DIR/known_hosts" -o ServerAliveInterval=30)
  export VM_NAME GUEST HYPERVISOR MAIA_BRANCH STATE_DIR LOG_DIR
}

hv_label() { [[ -n "$HYPERVISOR" ]] && echo "$HYPERVISOR" || echo "ctl(local)"; }

_exec_on() {
  case "$1" in
    ctl) bash -s ;;
    hv) if [[ -n "$HYPERVISOR" ]]; then ssh -o BatchMode=yes "$HYPERVISOR" bash -s; else bash -s; fi ;;
    guest) ssh "${GUEST_SSH_OPTS[@]}" "$GUEST" bash -s ;;
    *) echo "unknown target $1" >&2; return 2 ;;
  esac
}

# redact: replace every generated secret value (secrets.env) with <redacted:NAME> in the stream. Upstream MAIA_Install
# logs config.yaml env values (GUACAMOLE_PASSWORD, ...) at INFO level, and job logs are streamed here.
redact() {
  local sec="$STATE_DIR/secrets.env"
  if [[ -s "$sec" ]]; then
    python3 -u -c '
import sys
pairs=[l.rstrip("\n").split("=",1) for l in open(sys.argv[1]) if "=" in l]
pairs=[(k,v) for k,v in pairs if len(v)>=8]
for line in sys.stdin:
    for k,v in pairs: line=line.replace(v,"<redacted:"+k+">")
    sys.stdout.write(line); sys.stdout.flush()
' "$sec"
  else cat; fi
}

run() {
  local where="$1" label="$2" script ts log rc start dur shown
  script="$(cat)"
  ts="$(date +%Y%m%d-%H%M%S)"; log="$LOG_DIR/$ts-$label.log"
  case "$where" in hv) shown="$(hv_label)" ;; guest) shown="$GUEST" ;; *) shown="ctl" ;; esac
  printf '\n\033[1m[%s] %s\033[0m  (log: %s)\n' "$shown" "$label" "$log" >&2
  { echo "# where: $shown  label: $label  start: $(date -Is)"; echo "$script"; echo "# ---- output ----"; } > "$log"
  start=$(date +%s)
  set +e
  printf 'set -euo pipefail\n%s\n' "$script" | _exec_on "$where" 2>&1 | redact | tee -a "$log"
  rc=${PIPESTATUS[1]}
  set -e
  dur=$(( $(date +%s) - start ))
  echo "# rc=$rc duration=${dur}s" >> "$log"
  [[ -f "$JOURNAL" ]] || printf '| time | where | step | dur | rc | output (tail) |\n|---|---|---|---|---|---|\n' > "$JOURNAL"
  local tail; tail="$(grep -v '^#' "$log" | sed '/^\s*$/d' | tail -n 3 | tr '\n|' ' /' | cut -c1-240)"
  printf '| %s | %s | %s | %ss | %s | %s |\n' "$(date +%H:%M:%S)" "$shown" "$label" "$dur" "$rc" "$tail" >> "$JOURNAL"
  if [[ $rc -ne 0 ]]; then echo "FAILED: [$shown] $label (rc=$rc) — see $log" >&2; return "$rc"; fi
}

# Host-changing actions require --approve-host-changes, after a human has seen the plan.
require_approval() {
  if [[ $APPROVED -ne 1 ]]; then
    echo; echo "=== The step above changes state on $(hv_label). Show it to the user, then re-run with --approve-host-changes ==="
    exit 3
  fi
}

state_set() { mkdir -p "$STATE_DIR"; echo "$2" > "$STATE_DIR/$1"; }
state_get() { cat "$STATE_DIR/$1" 2>/dev/null || true; }
