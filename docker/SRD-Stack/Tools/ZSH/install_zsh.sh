#!/bin/bash
# Build-time: preinstall zsh stack into the image.
# Runtime: seed / configure the ubuntu user's home (PVC-safe).
#
# Usage:
#   /etc/install_zsh.sh preinstall   # Dockerfile RUN (as root)
#   /etc/install_zsh.sh configure    # entrypoint / prepare-home
set -euo pipefail

ZSH_TEMPLATE_DIR="${ZSH_TEMPLATE_DIR:-/opt/zsh-template}"
TARGET_USER="${TARGET_USER:-ubuntu}"
TARGET_HOME="${TARGET_HOME:-/home/ubuntu}"

seed_tree() {
  local src="$1"
  local dest="$2"
  if [ ! -e "${src}" ]; then
    return 0
  fi
  if [ -e "${dest}" ]; then
    return 0
  fi
  mkdir -p "$(dirname "${dest}")"
  cp -a "${src}" "${dest}"
}

seed_file() {
  local src="$1"
  local dest="$2"
  if [ ! -f "${src}" ]; then
    return 0
  fi
  if [ -f "${dest}" ]; then
    return 0
  fi
  mkdir -p "$(dirname "${dest}")"
  cp -a "${src}" "${dest}"
}

install_packages() {
  apt-get update
  apt-get install -y --no-install-recommends zsh tmux neovim git curl ca-certificates
  rm -rf /var/lib/apt/lists/*
}

build_template() {
  local zsh_custom="${ZSH_TEMPLATE_DIR}/.oh-my-zsh/custom"

  rm -rf "${ZSH_TEMPLATE_DIR}"
  mkdir -p \
    "${ZSH_TEMPLATE_DIR}" \
    "${ZSH_TEMPLATE_DIR}/.tmux/plugins" \
    "${ZSH_TEMPLATE_DIR}/.config/nvim/pack/github/start"

  # Clone oh-my-zsh first (creates .oh-my-zsh/custom); then add plugins/themes
  git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git \
    "${ZSH_TEMPLATE_DIR}/.oh-my-zsh"
  mkdir -p "${zsh_custom}/plugins" "${zsh_custom}/themes"
  git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting.git \
    "${zsh_custom}/plugins/zsh-syntax-highlighting"
  git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions.git \
    "${zsh_custom}/plugins/zsh-autosuggestions"
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \
    "${zsh_custom}/themes/powerlevel10k"

  # Pre-download gitstatusd so powerlevel10k does not fetch it at shell start.
  # Use GITSTATUS_CACHE_DIR (not GITSTATUS_DAEMON): GITSTATUS_DAEMON forces
  # build.info's version (currently v1.5.5) while install.info ships v1.5.4,
  # which causes "Version mismatch" at runtime.
  local gitstatus_cache=/opt/gitstatus
  local gitstatus_install="${zsh_custom}/themes/powerlevel10k/gitstatus/install"
  rm -rf "${gitstatus_cache}"
  mkdir -p "${gitstatus_cache}" "${ZSH_TEMPLATE_DIR}/.cache"
  GITSTATUS_CACHE_DIR="${gitstatus_cache}" "${gitstatus_install}" -f
  local daemon
  daemon="$(find "${gitstatus_cache}" -type f -name 'gitstatusd-*' | head -n 1)"
  if [ -z "${daemon}" ] || [ ! -x "${daemon}" ]; then
    echo "install_zsh: failed to download gitstatusd" >&2
    exit 1
  fi
  chmod 755 "${daemon}"
  # Mirror into the home template for PVC seeding
  cp -a "${gitstatus_cache}" "${ZSH_TEMPLATE_DIR}/.cache/gitstatus"
  # Shared cache for all users (PVC-safe; keeps original gitstatusd-* name)
  printf '%s\n' 'export GITSTATUS_CACHE_DIR=/opt/gitstatus' \
    > /etc/profile.d/gitstatus.sh
  chmod 644 /etc/profile.d/gitstatus.sh

  git clone --depth=1 https://github.com/tmux-plugins/tpm.git \
    "${ZSH_TEMPLATE_DIR}/.tmux/plugins/tpm"
  git clone --depth=1 https://github.com/github/copilot.vim.git \
    "${ZSH_TEMPLATE_DIR}/.config/nvim/pack/github/start/copilot.vim"

  # Drop git history to keep the image smaller
  find "${ZSH_TEMPLATE_DIR}" -name .git -type d -prune -exec rm -rf {} +
  chmod -R a+rX "${ZSH_TEMPLATE_DIR}"
}

set_default_shell() {
  local zsh_path
  zsh_path="$(command -v zsh)"
  if getent passwd "${TARGET_USER}" >/dev/null 2>&1; then
    usermod -s "${zsh_path}" "${TARGET_USER}" || true
  fi
  # Persist for entrypoints / OpenShift passwd rewrite
  if [ -d /etc ]; then
    printf '%s\n' "${zsh_path}" > /etc/default-shell
  fi
}

# Populate a home directory from the image template + /etc configs.
seed_home() {
  local home_dir="${1:-${HOME:-${TARGET_HOME}}}"

  if [ ! -d "${ZSH_TEMPLATE_DIR}/.oh-my-zsh" ]; then
    echo "install_zsh: template missing at ${ZSH_TEMPLATE_DIR}; skipping configure"
    return 0
  fi

  mkdir -p \
    "${home_dir}" \
    "${home_dir}/.config" \
    "${home_dir}/.tmux/plugins" \
    "${home_dir}/.config/nvim/pack/github/start"

  seed_tree "${ZSH_TEMPLATE_DIR}/.oh-my-zsh" "${home_dir}/.oh-my-zsh"
  seed_tree "${ZSH_TEMPLATE_DIR}/.tmux/plugins/tpm" "${home_dir}/.tmux/plugins/tpm"
  seed_tree \
    "${ZSH_TEMPLATE_DIR}/.config/nvim/pack/github/start/copilot.vim" \
    "${home_dir}/.config/nvim/pack/github/start/copilot.vim"
  seed_tree "${ZSH_TEMPLATE_DIR}/.cache/gitstatus" "${home_dir}/.cache/gitstatus"

  seed_file /etc/.zshrc "${home_dir}/.zshrc"
  seed_file /etc/.tmux.conf "${home_dir}/.tmux.conf"
  seed_file /etc/.bash_profile "${home_dir}/.bash_profile"

  # Migrate PVC homes that still set GITSTATUS_DAEMON (causes v1.5.4 vs v1.5.5 mismatch)
  if [ -f "${home_dir}/.zshrc" ] && grep -q 'GITSTATUS_DAEMON' "${home_dir}/.zshrc"; then
    sed -i \
      -e '/GITSTATUS_DAEMON/d' \
      -e '/\[\[ -x \/opt\/gitstatus\/gitstatusd \]\]/d' \
      "${home_dir}/.zshrc"
  fi
  if [ -f "${home_dir}/.zshrc" ] && [ -d /opt/gitstatus ] \
     && ! grep -q 'GITSTATUS_CACHE_DIR=/opt/gitstatus' "${home_dir}/.zshrc"; then
    sed -i '/^export ZSH=/i\
if [[ -d /opt/gitstatus ]]; then\
  unset GITSTATUS_DAEMON\
  export GITSTATUS_CACHE_DIR=/opt/gitstatus\
fi
' "${home_dir}/.zshrc"
  fi

  if [ -f /etc/MAIA.png ] && [ ! -f "${home_dir}/MAIA.png" ]; then
    cp -a /etc/MAIA.png "${home_dir}/MAIA.png" || true
  fi
}

preinstall() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "install_zsh preinstall must run as root" >&2
    exit 1
  fi
  install_packages
  build_template
  set_default_shell
  seed_home "${TARGET_HOME}"
  if id "${TARGET_USER}" >/dev/null 2>&1; then
    chown -R "${TARGET_USER}:0" \
      "${TARGET_HOME}/.oh-my-zsh" \
      "${TARGET_HOME}/.tmux" \
      "${TARGET_HOME}/.config" \
      "${TARGET_HOME}/.cache" \
      "${TARGET_HOME}/.zshrc" \
      "${TARGET_HOME}/.tmux.conf" \
      "${TARGET_HOME}/.bash_profile" \
      2>/dev/null || true
  fi
  echo "install_zsh: preinstall complete (template=${ZSH_TEMPLATE_DIR})"
}

configure() {
  local home_dir="${HOME:-${TARGET_HOME}}"
  seed_home "${home_dir}"
  echo "install_zsh: configured home=${home_dir}"
}

usage() {
  echo "Usage: $0 {preinstall|configure}" >&2
  exit 1
}

case "${1:-}" in
  preinstall|install|build) preinstall ;;
  configure|runtime) configure ;;
  *) usage ;;
esac
