#!/usr/bin/env bash
# =============================================================================
# Quant.OS - VPS Initialization Script
# =============================================================================
# Sets up a fresh VPS for Quant.OS deployment.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/alpha-search/alpha-search/main/scripts/setup-vps.sh | bash
#   # OR
#   wget -qO- https://raw.githubusercontent.com/alpha-search/alpha-search/main/scripts/setup-vps.sh | bash
#
# Supports: Ubuntu 22.04/24.04, Debian 12
# Tested on: Hostinger VPS, Oracle Cloud, Hetzner Cloud
#
# What this script does:
#   1. System update & upgrade
#   2. Install Docker + Docker Compose
#   3. Configure firewall (UFW)
#   4. Install fail2ban
#   5. Setup SSH hardening
#   6. Configure automatic security updates
#   7. Setup log rotation
#   8. Clone Quant.OS repository
#   9. Create environment configuration
#  10. Start services
#
# Requirements:
#   - Root access (or sudo)
#   - Ubuntu 22.04+ or Debian 12+
#   - At least 1GB RAM, 10GB disk
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_VERSION="1.0.0"
REQUIRED_RAM_MB=1024
REQUIRED_DISK_GB=10
GITHUB_REPO="${GITHUB_REPO:-alpha-search/alpha-search}"
INSTALL_DIR="${INSTALL_DIR:-/opt/alpha-search}"
APP_USER="${APP_USER:-quantos}"
APP_PORT_API="${APP_PORT_API:-8000}"
APP_PORT_UI="${APP_PORT_UI:-8501}"
SSH_PORT="${SSH_PORT:-22}"
TZ="${TZ:-UTC}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Logging
LOG_FILE="/var/log/alpha-search-setup-$(date +%Y%m%d-%H%M%S).log"

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local color="$NC"
    case "$level" in
        INFO)  color="$GREEN" ;;
        WARN)  color="$YELLOW" ;;
        ERROR) color="$RED" ;;
        STEP)  color="$CYAN" ;;
        *)     color="$NC" ;;
    esac
    echo -e "${color}[${timestamp}] [${level}] ${message}${NC}" | tee -a "$LOG_FILE"
}

print_banner() {
    echo -e "${BOLD}${CYAN}"
    echo '  ____             _              ___  ____  '
    echo ' / __ \ __ _  ____(_)_  __ ___   / _ \/ ___| '
    echo '/ / _` / /| |/ / / /| |/ /| _| | | | \___ \ '
    echo '| | (_|  <| / /| | <| |  <| |   | |_| |___) |'
    echo ' \__, /| |\_\_\_\| | |\_\_\|    \___/|____/ '
    echo '    |_|         VPS Setup Script v'"$SCRIPT_VERSION"
    echo -e "${NC}"
}

# ---------------------------------------------------------------------------
# System Checks
# ---------------------------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        if ! command -v sudo &>/dev/null; then
            log ERROR "This script must be run as root or with sudo"
            exit 1
        fi
        SUDO="sudo"
    else
        SUDO=""
    fi
}

check_os() {
    log STEP "Checking operating system..."

    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS_NAME="$ID"
        OS_VERSION="$VERSION_ID"
    else
        log ERROR "Cannot detect operating system"
        exit 1
    fi

    case "$OS_NAME" in
        ubuntu)
            if [[ "${OS_VERSION%%.*}" -lt 22 ]]; then
                log ERROR "Ubuntu $OS_VERSION is not supported. Use 22.04 or later."
                exit 1
            fi
            ;;
        debian)
            if [[ "${OS_VERSION%%.*}" -lt 12 ]]; then
                log WARN "Debian $OS_VERSION may not be fully supported. Use 12 or later."
            fi
            ;;
        *)
            log WARN "Unsupported OS: $OS_NAME $OS_VERSION. Continuing anyway..."
            ;;
    esac

    log INFO "OS: $OS_NAME $OS_VERSION"
}

check_resources() {
    log STEP "Checking system resources..."

    # Check RAM
    local total_ram_mb
    total_ram_mb=$(free -m | awk '/^Mem:/{print $2}')
    if [[ "$total_ram_mb" -lt "$REQUIRED_RAM_MB" ]]; then
        log WARN "Low RAM: ${total_ram_mb}MB (recommended: ${REQUIRED_RAM_MB}MB+)"
    else
        log INFO "RAM: ${total_ram_mb}MB OK"
    fi

    # Check disk
    local total_disk_gb
    total_disk_gb=$(df -BG / | awk 'NR==2{gsub(/G/,""); print $4}')
    if [[ "$total_disk_gb" -lt "$REQUIRED_DISK_GB" ]]; then
        log WARN "Low disk space: ${total_disk_gb}GB available (recommended: ${REQUIRED_DISK_GB}GB+)"
    else
        log INFO "Disk: ${total_disk_gb}GB available OK"
    fi
}

# ---------------------------------------------------------------------------
# Step 1: System Update
# ---------------------------------------------------------------------------
system_update() {
    log STEP "Step 1/10: Updating system packages..."

    export DEBIAN_FRONTEND=noninteractive

    $SUDO apt-get update -qq
    $SUDO apt-get upgrade -y -qq
    $SUDO apt-get install -y -qq \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common \
        git \
        vim \
        htop \
        jq \
        unzip \
        cron \
        logrotate \
        fail2ban \
        ufw \
        certbot \
        python3-certbot-nginx \
        ncdu \
        tree \
        net-tools \
        dnsutils \
        iftop \
        iotop

    # Set timezone
    $SUDO timedatectl set-timezone "$TZ" 2>/dev/null || true

    log INFO "System packages updated"
}

# ---------------------------------------------------------------------------
# Step 2: Docker Installation
# ---------------------------------------------------------------------------
install_docker() {
    log STEP "Step 2/10: Installing Docker..."

    # Check if Docker already installed
    if command -v docker &>/dev/null && docker version &>/dev/null; then
        log INFO "Docker is already installed: $(docker --version)"
        docker --version
    else
        # Install Docker using official script
        curl -fsSL https://get.docker.com | $SUDO bash

        # Start and enable Docker
        $SUDO systemctl enable --now docker

        log INFO "Docker installed: $(docker --version)"
    fi

    # Install Docker Compose plugin (v2)
    if docker compose version &>/dev/null; then
        log INFO "Docker Compose v2 is already installed"
        docker compose version
    else
        log INFO "Installing Docker Compose plugin..."
        $SUDO apt-get install -y -qq docker-compose-plugin
        # Create alias
        $SUDO ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose 2>/dev/null || true
    fi

    # Add current user to docker group (if not root)
    if [[ -n "$SUDO_USER" ]]; then
        $SUDO usermod -aG docker "$SUDO_USER"
        log INFO "Added $SUDO_USER to docker group (log out and back in to apply)"
    fi

    log INFO "Docker installation complete"
}

# ---------------------------------------------------------------------------
# Step 3: Firewall Configuration
# ---------------------------------------------------------------------------
setup_firewall() {
    log STEP "Step 3/10: Configuring UFW firewall..."

    # Reset UFW to known state
    $SUDO ufw --force reset

    # Default policies
    $SUDO ufw default deny incoming
    $SUDO ufw default allow outgoing

    # Allow SSH
    $SUDO ufw allow "$SSH_PORT/tcp" comment 'SSH access'

    # Allow HTTP/HTTPS
    $SUDO ufw allow 80/tcp comment 'HTTP'
    $SUDO ufw allow 443/tcp comment 'HTTPS'

    # Allow Cloudflare IPs (origin pull)
    log INFO "Configuring Cloudflare IP whitelist..."
    local cf_ips
    cf_ips=$(curl -fsSL https://www.cloudflare.com/ips-v4 2>/dev/null || true)
    if [[ -n "$cf_ips" ]]; then
        while IFS= read -r ip; do
            [[ -n "$ip" ]] && $SUDO ufw allow from "$ip" to any port 80,443 proto tcp comment 'Cloudflare' 2>/dev/null || true
        done <<< "$cf_ips"
    fi

    # Explicitly deny direct access to app ports
    $SUDO ufw deny 8000/tcp comment 'Quant.OS API (internal only)'
    $SUDO ufw deny 8501/tcp comment 'Quant.OS UI (internal only)'

    # Enable firewall
    $SUDO ufw --force enable

    log INFO "Firewall configured"
    $SUDO ufw status verbose
}

# ---------------------------------------------------------------------------
# Step 4: Fail2ban
# ---------------------------------------------------------------------------
setup_fail2ban() {
    log STEP "Step 4/10: Configuring fail2ban..."

    # Create jail.local
    $SUDO tee /etc/fail2ban/jail.local > /dev/null <<'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = auto
banaction = ufw

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 5

[nginx-badbots]
enabled = true
port = http,https
filter = nginx-badbots
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-noscript]
enabled = true
port = http,https
filter = nginx-noscript
logpath = /var/log/nginx/access.log
maxretry = 6

[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 2

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

    # Create nginx filter for bad bots
    $SUDO tee /etc/fail2ban/filter.d/nginx-badbots.conf > /dev/null <<'EOF'
[Definition]
failregex = ^<HOST> .* "(GET|POST).*HTTP.*" (404|444) .*
ignoreregex =
EOF

    $SUDO systemctl enable --now fail2ban
    $SUDO systemctl restart fail2ban

    log INFO "fail2ban configured"
    $SUDO fail2ban-client status 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Step 5: SSH Hardening
# ---------------------------------------------------------------------------
setup_ssh() {
    log STEP "Step 5/10: Hardening SSH..."

    local sshd_config="/etc/ssh/sshd_config"

    # Backup original
    $SUDO cp "$sshd_config" "${sshd_config}.bak.$(date +%s)"

    # Apply hardening
    $SUDO tee -a "$sshd_config" > /dev/null <<EOF

# Quant.OS SSH Hardening
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
EOF

    $SUDO systemctl restart sshd

    log INFO "SSH hardened - key authentication only"
}

# ---------------------------------------------------------------------------
# Step 6: Automatic Security Updates
# ---------------------------------------------------------------------------
setup_auto_updates() {
    log STEP "Step 6/10: Configuring automatic security updates..."

    $SUDO apt-get install -y -qq unattended-upgrades apt-listchanges

    $SUDO tee /etc/apt/apt.conf.d/50unattended-upgrades > /dev/null <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

    $SUDO tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    $SUDO systemctl enable --now unattended-upgrades

    log INFO "Automatic security updates configured"
}

# ---------------------------------------------------------------------------
# Step 7: Log Rotation
# ---------------------------------------------------------------------------
setup_logrotate() {
    log STEP "Step 7/10: Configuring log rotation..."

    # Docker container logs
    $SUDO tee /etc/logrotate.d/docker-containers > /dev/null <<'EOF'
/var/lib/docker/containers/*/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        /usr/bin/docker kill --signal="SIGUSR1" $(docker ps -q) 2>/dev/null || true
    endscript
}
EOF

    # Quant.OS application logs
    $SUDO tee /etc/logrotate.d/alpha-search > /dev/null <<EOF
$INSTALL_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $APP_USER $APP_USER
    dateext
    dateformat -%Y%m%d
}
EOF

    log INFO "Log rotation configured"
}

# ---------------------------------------------------------------------------
# Step 8: Clone Repository
# ---------------------------------------------------------------------------
clone_repo() {
    log STEP "Step 8/10: Cloning Quant.OS repository..."

    # Create app user
    if ! id "$APP_USER" &>/dev/null; then
        $SUDO useradd -r -s /bin/false -m -d "/home/$APP_USER" "$APP_USER"
        log INFO "Created user: $APP_USER"
    fi

    # Clone repository
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        log INFO "Repository already exists at $INSTALL_DIR, pulling latest..."
        $SUDO git -C "$INSTALL_DIR" pull origin main
    else
        $SUDO mkdir -p "$INSTALL_DIR"
        $SUDO git clone "https://github.com/$GITHUB_REPO.git" "$INSTALL_DIR"
        log INFO "Repository cloned"
    fi

    # Set ownership
    $SUDO chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

    # Create required directories
    $SUDO mkdir -p "$INSTALL_DIR/logs" "$INSTALL_DIR/backups" "$INSTALL_DIR/data"
    $SUDO chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR/logs" "$INSTALL_DIR/backups" "$INSTALL_DIR/data"

    log INFO "Repository ready at $INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# Step 9: Environment Configuration
# ---------------------------------------------------------------------------
setup_environment() {
    log STEP "Step 9/10: Setting up environment..."

    local env_file="$INSTALL_DIR/.env"

    if [[ -f "$env_file" ]]; then
        log WARN ".env file already exists, keeping existing"
        return 0
    fi

    # Generate secure secrets
    local jwt_secret
    jwt_secret=$(openssl rand -hex 32)

    $SUDO tee "$env_file" > /dev/null <<EOF
# Quant.OS Environment Configuration
# Generated on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# =============================================

# Application
APP_ENV=production
APP_VERSION=1.0.0
LOG_LEVEL=INFO
LOG_FORMAT=json

# API Configuration
API_WORKERS=2
API_HOST=0.0.0.0
API_PORT=8000
RATE_LIMIT=60

# Security
JWT_SECRET_KEY=$jwt_secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Cache
REDIS_URL=redis://redis:6379/0
CACHE_TTL=3600

# Database
DUCKDB_PATH=/data/alpha-search.duckdb

# External APIs (add your own keys)
# YAHOO_FINANCE_ENABLED=true
# FRED_API_KEY=your_fred_key_here
# WORLD_BANK_ENABLED=true
# ALPHA_VANTAGE_KEY=your_key_here

# Notifications (optional)
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
# SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Docker
COMPOSE_PROJECT_NAME=alpha-search
IMAGE_TAG=latest
GITHUB_REPOSITORY=$GITHUB_REPO

# Monitoring (Phase 3)
# PROMETHEUS_ENABLED=false
# GRAFANA_ENABLED=false
EOF

    $SUDO chmod 600 "$env_file"
    $SUDO chown "$APP_USER:$APP_USER" "$env_file"

    log INFO "Environment file created at $env_file"
    log WARN "IMPORTANT: Edit $env_file to add your API keys!"
}

# ---------------------------------------------------------------------------
# Step 10: Start Services
# ---------------------------------------------------------------------------
start_services() {
    log STEP "Step 10/10: Starting Quant.OS services..."

    cd "$INSTALL_DIR"

    # Pull images
    log INFO "Pulling Docker images..."
    $SUDO docker compose pull

    # Start services
    log INFO "Starting services..."
    $SUDO docker compose up -d --remove-orphans

    # Wait for services to be ready
    log INFO "Waiting for services to start..."
    sleep 15

    # Health check
    log INFO "Running health check..."
    local retries=0
    local max_retries=12

    while [[ $retries -lt $max_retries ]]; do
        if curl -fsS http://localhost:8000/health &>/dev/null; then
            log INFO "API is healthy!"
            break
        fi
        retries=$((retries + 1))
        log INFO "Health check attempt $retries/$max_retries - waiting..."
        sleep 10
    done

    if [[ $retries -eq $max_retries ]]; then
        log WARN "Health check failed after $max_retries attempts"
        log WARN "Check logs: $SUDO docker compose logs alpha-search-api"
    else
        log INFO "All services are running!"
    fi

    # Show status
    echo ""
    $SUDO docker compose ps
    echo ""
}

# ---------------------------------------------------------------------------
# Systemd Service (Optional)
# ---------------------------------------------------------------------------
setup_systemd() {
    log STEP "Creating systemd service for Quant.OS..."

    $SUDO tee /etc/systemd/system/alpha-search.service > /dev/null <<EOF
[Unit]
Description=Quant.OS - Quantitative Finance Platform
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose up -d
TimeoutStartSec=300
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
EOF

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable alpha-search.service

    log INFO "Systemd service created: alpha-search.service"
    log INFO "Commands:"
    log INFO "  systemctl start alpha-search"
    log INFO "  systemctl stop alpha-search"
    log INFO "  systemctl restart alpha-search"
    log INFO "  systemctl status alpha-search"
}

# ---------------------------------------------------------------------------
# Final Summary
# ---------------------------------------------------------------------------
print_summary() {
    local ip_address
    ip_address=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${BOLD}${GREEN}═════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}              QUANT.OS VPS SETUP COMPLETE                        ${NC}"
    echo -e "${BOLD}${GREEN}═════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Server IP:${NC}      $ip_address"
    echo -e "  ${BOLD}Install Dir:${NC}    $INSTALL_DIR"
    echo -e "  ${BOLD}App User:${NC}       $APP_USER"
    echo -e "  ${BOLD}Log File:${NC}       $LOG_FILE"
    echo ""
    echo -e "  ${BOLD}Services:${NC}"
    echo -e "    API:      http://$ip_address:8000"
    echo -e "    UI:       http://$ip_address:8501"
    echo -e "    Health:   http://$ip_address:8000/health"
    echo ""
    echo -e "  ${BOLD}Next Steps:${NC}"
    echo -e "    1. Edit $INSTALL_DIR/.env to add your API keys"
    echo -e "    2. Configure Cloudflare DNS to point to $ip_address"
    echo -e "    3. Set up SSL certificates (see docs)"
    echo -e "    4. Visit https://your-domain.com to verify"
    echo ""
    echo -e "  ${BOLD}Useful Commands:${NC}"
    echo -e "    cd $INSTALL_DIR && docker compose logs -f"
    echo -e "    cd $INSTALL_DIR && docker compose ps"
    echo -e "    systemctl status alpha-search"
    echo ""
    echo -e "  ${BOLD}Security:${NC}"
    echo -e "    Firewall:   ufw status verbose"
    echo -e "    Fail2ban:   fail2ban-client status"
    echo -e "    SSH config: /etc/ssh/sshd_config"
    echo ""
    echo -e "${BOLD}${GREEN}═════════════════════════════════════════════════════════════════${NC}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    print_banner

    mkdir -p "$(dirname "$LOG_FILE")"
    log INFO "Starting Quant.OS VPS setup v$SCRIPT_VERSION"

    check_root
    check_os
    check_resources

    # Run all setup steps
    system_update
    install_docker
    setup_firewall
    setup_fail2ban
    setup_ssh
    setup_auto_updates
    setup_logrotate
    clone_repo
    setup_environment
    start_services
    setup_systemd

    print_summary
    log INFO "Setup completed successfully!"
}

# Handle Ctrl+C
trap 'log WARN "Setup interrupted by user"; exit 1' INT

# Run main
main "$@"