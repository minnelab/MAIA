#!/usr/bin/env bash
# 05_install_smolvm.sh: install a pinned smolvm into ~/.smolvm and ~/.local/bin on the hypervisor (no sudo).
# Usage: 05_install_smolvm.sh [--hypervisor <ssh-alias>] [--approve-host-changes]
#   SMOLVM_VERSION (default 1.14.1). The tarball is checked against the release's checksums.sha256 and
#   against the pinned SHA256 below. Without --approve-host-changes it only prints the plan.
source "$(dirname "$0")/lib.sh"
parse_common_args "$@"
: "${SMOLVM_VERSION:=1.14.1}"
# GitHub release asset digest for smolvm-1.14.1-linux-x86_64.tar.gz (api.github.com .../releases/tags/v1.14.1)
: "${SMOLVM_SHA256:=e91786c12808ce87655aa190eb5f6692672cd659a89367b5ec18dace5756af2f}"
cat <<EOF
Plan on $(hv_label):
  download https://github.com/smol-machines/smolvm/releases/download/v$SMOLVM_VERSION/smolvm-$SMOLVM_VERSION-linux-x86_64.tar.gz
  verify   checksums.sha256 + pinned sha256 $SMOLVM_SHA256
  extract  -> ~/.smolvm/ ; symlink ~/.local/bin/smolvm -> ~/.smolvm/smolvm   (refuses if ~/.smolvm exists)
EOF
require_approval
run hv smolvm-install <<EOF
if [[ -x ~/.local/bin/smolvm ]] && ~/.local/bin/smolvm --version | grep -q " $SMOLVM_VERSION\$"; then echo "already installed"; exit 0; fi
test ! -e ~/.smolvm || { echo "~/.smolvm exists but is not $SMOLVM_VERSION; refusing to overwrite"; exit 1; }
T=smolvm-$SMOLVM_VERSION-linux-x86_64.tar.gz; mkdir -p ~/.cache; D=\$(mktemp -d ~/.cache/smolvm-dl.XXXX); cd "\$D"
B=https://github.com/smol-machines/smolvm/releases/download/v$SMOLVM_VERSION
curl -fsSLO \$B/\$T; curl -fsSLO \$B/checksums.sha256
sha256sum -c --ignore-missing checksums.sha256
echo "$SMOLVM_SHA256  \$T" | sha256sum -c -
mkdir -p ~/.smolvm ~/.local/bin; tar -xzf \$T -C ~/.smolvm --strip-components=1
ln -sfn ~/.smolvm/smolvm ~/.local/bin/smolvm; ~/.local/bin/smolvm --version; cd ~; rm -rf "\$D"
EOF
