#!/usr/bin/env bash
# One-time: install Docker inside WSL Ubuntu (needs your sudo password once).
# After this finishes, tell Claude — it will restart WSL and run the stack.
set -e
echo ">> installing docker.io + compose plugin ..."
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2
echo ">> enabling docker daemon (systemd) ..."
sudo systemctl enable --now docker
echo ">> adding $USER to the docker group ..."
sudo usermod -aG docker "$USER"
echo ">> docker version:"
sudo docker --version
sudo docker compose version
echo
echo "DONE. Now go back to Claude — it will run 'wsl --shutdown' so the docker"
echo "group takes effect, then bring up Roundcube."
