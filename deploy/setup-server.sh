#!/bin/sh
# One-time setup of a fresh Ubuntu server (Azure for Students or Oracle Cloud Always Free): Docker, the firewall, swap.
# Run ON the server:  sh setup-server.sh
set -eu

echo "== Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "== Firewall: open 80 and 443 (Oracle's Ubuntu images block them in iptables by default); SSH stays open"
# Inserted at the top, so the rule comes before Oracle's final REJECT. On Azure the
# list is empty (its firewall is the network security group), and this is harmless.
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
done
sudo apt-get install -y iptables-persistent >/dev/null 2>&1 || true
sudo netfilter-persistent save >/dev/null 2>&1 || true

echo "== Swap (2 GB), so building the images never runs out of memory"
if ! sudo swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== Automatic security updates"
sudo apt-get install -y unattended-upgrades >/dev/null 2>&1 || true

echo "Done. Log out and back in once (so 'docker' works without sudo)."
