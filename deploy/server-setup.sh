#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu server (Oracle Cloud Always Free, ARM or x86) for Bento.
#   curl -fsSL https://raw.githubusercontent.com/shak5hi/bento/main/deploy/server-setup.sh | bash
# Installs Docker, opens ports 80/443 in the server's own firewall, and clones Bento.
# It never touches secrets: you create backend/.env yourself afterwards (see deploy/README.md).
set -euo pipefail

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Opening ports 80 and 443"
# Oracle's Ubuntu images ship iptables rules that block everything but SSH, on top of the cloud
# security list. Insert ACCEPT rules before the REJECT rule and make them survive reboots.
if command -v iptables >/dev/null; then
  for port in 80 443; do
    sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null \
      || sudo iptables -I INPUT 5 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
  done
  sudo iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p udp --dport 443 -j ACCEPT
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent >/dev/null
  sudo netfilter-persistent save >/dev/null
fi

echo "==> Getting Bento"
if [ ! -d "$HOME/bento" ]; then
  git clone https://github.com/shak5hi/bento.git "$HOME/bento"
else
  git -C "$HOME/bento" pull --ff-only
fi
cp -n "$HOME/bento/backend/.env.example" "$HOME/bento/backend/.env" 2>/dev/null || true
chmod 600 "$HOME/bento/backend/.env"

cat <<'DONE'

Done. Next:
  1. Log out and back in (so docker works without sudo).
  2. Fill in ~/bento/backend/.env   (nano ~/bento/backend/.env)
  3. cd ~/bento/backend && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
DONE
