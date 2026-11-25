#!/usr/bin/env bash
# Sign in to Open WebUI and fetch (or create) an API key.
set -euo pipefail

URL="${OPENWEBUI_URL:-}"
EMAIL="${OPENWEBUI_EMAIL:-}"
PASSWORD="${OPENWEBUI_PASSWORD:-}"
RECREATE=0
AS_JSON=0

usage() {
  cat <<EOF
Usage: $(basename "$0") --url URL --email EMAIL --password PASS [options]

Required (flag or environment variable):
  --url URL           Open WebUI base URL (or \$OPENWEBUI_URL)
  --email EMAIL       Login email (or \$OPENWEBUI_EMAIL)
  --password PASS     Login password (or \$OPENWEBUI_PASSWORD)

Options:
  --recreate          Force create a new API key (replaces any existing key)
  --json              Print JSON with api_key, url, email
  -h, --help          Show this help

Example:
  $(basename "$0") \\
    --url https://dashboard.maia.se \\
    --email admin@maia.se \\
    --password Admin
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --recreate) RECREATE=1; shift ;;
    --json) AS_JSON=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

missing=()
[[ -z "$URL" ]] && missing+=("--url / OPENWEBUI_URL")
[[ -z "$EMAIL" ]] && missing+=("--email / OPENWEBUI_EMAIL")
[[ -z "$PASSWORD" ]] && missing+=("--password / OPENWEBUI_PASSWORD")
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Error: missing required values: ${missing[*]}" >&2
  usage >&2
  exit 1
fi

URL="${URL%/}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd python3

signin_payload=$(PASSWORD="$PASSWORD" EMAIL="$EMAIL" python3 -c 'import json,os; print(json.dumps({"email":os.environ["EMAIL"],"password":os.environ["PASSWORD"]}))')

signin_resp=$(curl -sS -w "\n%{http_code}" -X POST "${URL}/api/v1/auths/signin" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "$signin_payload")

signin_body=$(printf '%s\n' "$signin_resp" | sed '$d')
signin_code=$(printf '%s\n' "$signin_resp" | tail -n1)

if [[ "$signin_code" != "200" ]]; then
  echo "Sign-in failed (HTTP ${signin_code}): ${signin_body}" >&2
  exit 1
fi

TOKEN=$(SIGNIN_BODY="$signin_body" python3 -c 'import json,os,sys; d=json.loads(os.environ["SIGNIN_BODY"]); t=d.get("token");
sys.exit("missing token in sign-in response") if not t else print(t)')

get_api_key() {
  local resp body code
  resp=$(curl -sS -w "\n%{http_code}" "${URL}/api/v1/auths/api_key" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/json")
  body=$(printf '%s\n' "$resp" | sed '$d')
  code=$(printf '%s\n' "$resp" | tail -n1)
  if [[ "$code" == "200" ]]; then
    BODY="$body" python3 -c 'import json,os,sys; d=json.loads(os.environ["BODY"]); k=d.get("api_key"); print(k) if k else sys.exit(1)'
  else
    return 1
  fi
}

create_api_key() {
  local resp body code
  resp=$(curl -sS -w "\n%{http_code}" -X POST "${URL}/api/v1/auths/api_key" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json")
  body=$(printf '%s\n' "$resp" | sed '$d')
  code=$(printf '%s\n' "$resp" | tail -n1)
  if [[ "$code" != "200" ]]; then
    echo "API key creation failed (HTTP ${code}): ${body}" >&2
    exit 1
  fi
  BODY="$body" python3 -c 'import json,os,sys; d=json.loads(os.environ["BODY"]); k=d.get("api_key");
sys.exit("missing api_key in create response") if not k else print(k)'
}

API_KEY=""
if [[ "$RECREATE" -eq 0 ]]; then
  API_KEY="$(get_api_key || true)"
fi
if [[ -z "$API_KEY" ]]; then
  API_KEY="$(create_api_key)"
fi

if [[ "$AS_JSON" -eq 1 ]]; then
  API_KEY="$API_KEY" URL="$URL" EMAIL="$EMAIL" python3 -c 'import json,os; print(json.dumps({"api_key":os.environ["API_KEY"],"url":os.environ["URL"],"email":os.environ["EMAIL"]}))'
else
  printf '%s\n' "$API_KEY"
fi
