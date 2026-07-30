#!/bin/bash
# setup-ubuntu-lxd.sh — Check & install prerequisites for HieraChain on Ubuntu
# Usage: bash docker/scripts/setup-ubuntu-lxd.sh
set -e

if [ "$(uname -s)" != "Linux" ]; then
  echo "ERROR: setup-ubuntu-lxd.sh is only supported on Linux OS (got $(uname -s))."
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "ERROR: Do NOT run setup-ubuntu-lxd.sh with sudo directly."
  echo "Run as regular user (e.g. bash docker/scripts/setup-ubuntu-lxd.sh)."
  echo "The script will automatically prompt for sudo password when needed."
  exit 1
fi

LXD_USER="$(whoami)"

echo ""
echo "=========================================="
echo " HieraChain — Ubuntu Environment Setup"
echo " User: $LXD_USER"
echo "=========================================="

echo ""
echo "[1/5] Basic Tools & Ansible"
if command -v ansible-playbook &>/dev/null; then
  echo "  OK"
else
  echo "  Installing basic tools and ansible (requires sudo)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq snapd curl git ansible
  echo "  OK"
fi

echo ""
echo "[2/5] uv"
if command -v uv &>/dev/null || [ -f "$HOME/.local/bin/uv" ] || [ -f "$HOME/.cargo/bin/uv" ]; then
  echo "  OK"
else
  echo "  Installing uv for user ($LXD_USER)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  echo "  OK"
fi

# Ensure uv is in PATH for current script context
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo ""
echo "[3/5] LXD"
if command -v lxc &>/dev/null; then
  echo "  OK"
else
  echo "  Installing lxd (requires sudo)..."
  sudo snap install lxd
  echo "  OK"
fi

# Auto-initialize LXD if storage pool does not exist
if ! lxc storage list 2>/dev/null | grep -qE "DIR|ZFS|BTRFS|CEPH|lvm"; then
  echo "  Initializing LXD with default bridge and storage..."
  sudo lxd init --auto
fi

echo ""
echo "[4/5] User permissions ($LXD_USER)"
if groups "$LXD_USER" 2>/dev/null | grep -qw lxd; then
  echo "  OK"
else
  echo "  Adding $LXD_USER to lxd group (requires sudo)..."
  sudo usermod -aG lxd "$LXD_USER"
  echo "  Added $LXD_USER to lxd group"
fi

echo ""
echo "[5/5] PATH environment check"
if ! grep -q '\.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"' >> "$HOME/.bashrc"
  echo "  Added ~/.local/bin to ~/.bashrc"
fi

echo ""
echo "=========================================="
echo " Done! Please run 'source ~/.bashrc' and 'newgrp lxd' (or re-login)."
echo "=========================================="