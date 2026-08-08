#!/usr/bin/env bash
# =============================================================================
# Mohamed Job Agent — Docker & n8n Setup Script
# =============================================================================
# This script installs Docker Engine from the official Docker APT repository
# and runs n8n Community Edition in a container.
#
# Target: Ubuntu 22.04.5 LTS (x86_64)
# Run as: ./setup-docker-n8n.sh   (NOT with sudo — the script calls sudo itself)
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------------------------------------------------------------------------
# Step 1: Remove any old/conflicting Docker packages
# ---------------------------------------------------------------------------
info "Step 1/8: Removing any conflicting Docker packages..."
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
sudo snap remove docker 2>/dev/null || true
info "  ✅ Cleanup done."

# ---------------------------------------------------------------------------
# Step 2: Install prerequisites for Docker's APT repository
# ---------------------------------------------------------------------------
info "Step 2/8: Installing prerequisites (ca-certificates, curl, gnupg)..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
info "  ✅ Prerequisites installed."

# ---------------------------------------------------------------------------
# Step 3: Add Docker's official GPG key
# ---------------------------------------------------------------------------
info "Step 3/8: Adding Docker's official GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
info "  ✅ GPG key added."

# ---------------------------------------------------------------------------
# Step 4: Add Docker's APT repository
# ---------------------------------------------------------------------------
info "Step 4/8: Adding Docker APT repository for Ubuntu Jammy..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
info "  ✅ Docker repository added."

# ---------------------------------------------------------------------------
# Step 5: Install Docker Engine, CLI, Containerd, and Compose plugin
# ---------------------------------------------------------------------------
info "Step 5/8: Installing Docker Engine + Compose plugin..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
info "  ✅ Docker Engine installed."

# ---------------------------------------------------------------------------
# Step 6: Add current user to the 'docker' group (run without sudo)
# ---------------------------------------------------------------------------
info "Step 6/8: Adding user '$(whoami)' to the 'docker' group..."
sudo usermod -aG docker "$(whoami)"
info "  ✅ User added to docker group."
info "  ⚠️  Group change takes effect after you log out and back in,"
info "     or you can run: newgrp docker"

# ---------------------------------------------------------------------------
# Step 7: Verify Docker installation
# ---------------------------------------------------------------------------
info "Step 7/8: Verifying Docker installation..."
# Use 'sg docker' to temporarily activate the docker group in this session
sg docker -c "docker --version"
sg docker -c "docker compose version"
sg docker -c "docker run --rm hello-world" && info "  ✅ Docker is working correctly." || warn "  Docker test failed — try logging out and back in."

# ---------------------------------------------------------------------------
# Step 8: Create volume and run n8n
# ---------------------------------------------------------------------------
info "Step 8/8: Creating n8n_data volume and starting n8n container..."

sg docker -c "docker volume create n8n_data"
info "  ✅ Volume 'n8n_data' created."

sg docker -c "docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -e GENERIC_TIMEZONE=Africa/Cairo \
  -e TZ=Africa/Cairo \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n:latest"

info "  ✅ n8n container started."

# ---------------------------------------------------------------------------
# Wait for n8n to be ready
# ---------------------------------------------------------------------------
info "Waiting for n8n to become available at http://localhost:5678 ..."
for i in $(seq 1 30); do
    if sg docker -c "curl -s -o /dev/null -w '%{http_code}' http://localhost:5678" | grep -qE '(200|301|302)'; then
        echo ""
        info "============================================="
        info "  🎉 n8n is running at http://localhost:5678"
        info "============================================="
        info ""
        info "Container name:  n8n"
        info "Volume:          n8n_data"
        info "Timezone:        Africa/Cairo"
        info "Restart policy:  unless-stopped"
        info ""
        info "Useful commands:"
        info "  docker logs -f n8n         # View n8n logs"
        info "  docker stop n8n            # Stop n8n"
        info "  docker start n8n           # Start n8n"
        info "  docker restart n8n         # Restart n8n"
        info ""
        exit 0
    fi
    echo -n "."
    sleep 2
done

warn "n8n did not respond within 60 seconds."
warn "Check the logs with: docker logs n8n"
exit 1
