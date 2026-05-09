#!/usr/bin/env bash
# =============================================================================
# Quant.OS - One-Command Deployment Script
# =============================================================================
# Usage:
#   ./scripts/deploy.sh [vps-host] [options]
#
# Options:
#   --tag <tag>       Deploy specific image tag (default: latest)
#   --no-pull         Skip docker pull (use local images)
#   --rollback        Rollback to previous deployment
#   --backup          Create backup before deployment
#   --dry-run         Show what would be done without doing it
#   --help            Show this help message
#
# Examples:
#   ./scripts/deploy.sh my-vps.hostinger.com
#   ./scripts/deploy.sh my-vps.hostinger.com --tag v1.2.3
#   ./scripts/deploy.sh --rollback
#   ./scripts/deploy.sh my-vps.hostinger.com --backup --dry-run
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_NAME="alpha-search"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/logs/deploy-$(date +%Y%m%d-%H%M%S).log"
HEALTH_CHECK_TIMEOUT=120
MAX_RETRIES=12
RETRY_INTERVAL=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
print_banner() {
    echo ""
    echo -e "${BOLD}${CYAN}"
    echo '  ____             _              ___  ____  '
    echo ' / __ \ __ _  ____(_)_  __ ___   / _ \/ ___| '
    echo '/ / _` / /| |/ / / /| |/ /| _| | | | \___ \ '
    echo '| | (_|  <| / /| | <| |  <| |   | |_| |___) |'
    echo ' \__, /| |\_\_\_\| | |\_\_\|    \___/|____/ '
    echo '    |_|                      Deploy Script   '
    echo -e "${NC}"
    echo -e "  ${BOLD}Version:${NC} 1.0.0"
    echo -e "  ${BOLD}Date:${NC}    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo ""
}

print_help() {
    echo "Quant.OS Deployment Script"
    echo ""
    echo "Usage: $0 [vps-host] [options]"
    echo ""
    echo "Arguments:"
    echo "  vps-host          Target VPS hostname or IP (optional if local)"
    echo ""
    echo "Options:"
    echo "  --tag <tag>       Deploy specific image tag (default: latest)"
    echo "  --no-pull         Skip docker pull (use local images)"
    echo "  --rollback        Rollback to previous deployment"
    echo "  --backup          Create backup before deployment"
    echo "  --dry-run         Show what would be done without doing it"
    echo "  --local           Deploy to local Docker (no SSH)"
    echo "  --verbose         Enable verbose output"
    echo "  --help            Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  VPS_HOST          Default VPS hostname"
    echo "  VPS_USER          SSH username (default: root)"
    echo "  SSH_KEY           Path to SSH private key"
    echo "  COMPOSE_PROJECT   Docker compose project name"
    echo ""
    echo "Examples:"
    echo "  $0 my-vps.hostinger.com"
    echo "  $0 my-vps.hostinger.com --tag v1.2.3 --backup"
    echo "  $0 --local --dry-run"
    echo "  $0 --rollback"
}

# Parse command line arguments
parse_args() {
    VPS_HOST="${VPS_HOST:-}"
    VPS_USER="${VPS_USER:-root}"
    SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
    DEPLOY_TAG="latest"
    NO_PULL=false
    ROLLBACK=false
    BACKUP=false
    DRY_RUN=false
    LOCAL=false
    VERBOSE=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tag)
                DEPLOY_TAG="$2"
                shift 2
                ;;
            --no-pull)
                NO_PULL=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --backup)
                BACKUP=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --local)
                LOCAL=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                print_help
                exit 0
                ;;
            -*)
                log ERROR "Unknown option: $1"
                print_help
                exit 1
                ;;
            *)
                if [[ -z "$VPS_HOST" ]]; then
                    VPS_HOST="$1"
                else
                    log ERROR "Unexpected argument: $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Validate
    if [[ "$LOCAL" == false && "$ROLLBACK" == false && -z "$VPS_HOST" && -z "${VPS_HOST:-}" ]]; then
        if [[ -f "$ENV_FILE" ]]; then
            source "$ENV_FILE"
        fi
        if [[ -z "${VPS_HOST:-}" ]]; then
            log ERROR "No VPS host specified. Use --local for local deployment or provide hostname."
            print_help
            exit 1
        fi
    fi
}

# Execute command (local or remote via SSH)
run_cmd() {
    local cmd="$1"
    if [[ "$DRY_RUN" == true ]]; then
        log STEP "[DRY-RUN] Would execute: $cmd"
        return 0
    fi

    if [[ "$LOCAL" == true ]]; then
        if [[ "$VERBOSE" == true ]]; then
            log INFO "Executing: $cmd"
        fi
        eval "$cmd"
    else
        if [[ "$VERBOSE" == true ]]; then
            log INFO "Executing on $VPS_HOST: $cmd"
        fi
        ssh -i "$SSH_KEY" \
            -o StrictHostKeyChecking=accept-new \
            -o ConnectTimeout=10 \
            "$VPS_USER@$VPS_HOST" \
            "$cmd"
    fi
}

# Check prerequisites
check_prerequisites() {
    log STEP "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &>/dev/null; then
        log ERROR "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
        log ERROR "Docker Compose is not installed."
        exit 1
    fi

    # Check SSH if remote
    if [[ "$LOCAL" == false && "$ROLLBACK" == false ]]; then
        if ! command -v ssh &>/dev/null; then
            log ERROR "SSH client is not installed."
            exit 1
        fi

        if [[ ! -f "$SSH_KEY" ]]; then
            log ERROR "SSH key not found: $SSH_KEY"
            exit 1
        fi

        # Test SSH connection
        log INFO "Testing SSH connection to $VPS_HOST..."
        if ! ssh -i "$SSH_KEY" \
            -o StrictHostKeyChecking=accept-new \
            -o ConnectTimeout=10 \
            -o BatchMode=yes \
            "$VPS_USER@$VPS_HOST" "echo 'SSH OK'" &>/dev/null; then
            log ERROR "Cannot connect to $VPS_HOST via SSH"
            exit 1
        fi
        log INFO "SSH connection successful"
    fi

    # Check compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log ERROR "docker-compose.yml not found at $COMPOSE_FILE"
        exit 1
    fi

    log INFO "All prerequisites met"
}

# Create backup
create_backup() {
    if [[ "$BACKUP" == false ]]; then
        return 0
    fi

    log STEP "Creating pre-deployment backup..."

    local backup_timestamp
    backup_timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_path="$BACKUP_DIR/$backup_timestamp"

    if [[ "$DRY_RUN" == true ]]; then
        log STEP "[DRY-RUN] Would create backup at: $backup_path"
        return 0
    fi

    mkdir -p "$backup_path"

    # Backup DuckDB
    log INFO "Backing up DuckDB database..."
    run_cmd "cd ~/alpha-search && \
        docker compose cp alpha-search-api:/data/alpha-search.duckdb \
        ./backups/$backup_timestamp/alpha-search.duckdb 2>/dev/null || \
        echo 'No DuckDB to backup'"

    # Backup Redis
    log INFO "Backing up Redis data..."
    run_cmd "cd ~/alpha-search && \
        docker compose exec redis redis-cli BGSAVE && \
        docker compose cp redis:/data/dump.rdb \
        ./backups/$backup_timestamp/redis.rdb 2>/dev/null || \
        echo 'No Redis data to backup'"

    # Backup .env
    log INFO "Backing up environment configuration..."
    run_cmd "cp ~/alpha-search/.env ~/alpha-search/backups/$backup_timestamp/.env 2>/dev/null || echo 'No .env to backup'"

    log INFO "Backup completed: $backup_path"
}

# Pull latest images
pull_images() {
    if [[ "$NO_PULL" == true ]]; then
        log INFO "Skipping image pull (--no-pull)"
        return 0
    fi

    log STEP "Pulling latest Docker images (tag: $DEPLOY_TAG)..."

    # Update .env with deploy tag
    if [[ "$DEPLOY_TAG" != "latest" ]]; then
        if [[ "$DRY_RUN" == false ]]; then
            run_cmd "cd ~/alpha-search && \
                sed -i 's/IMAGE_TAG=.*/IMAGE_TAG=$DEPLOY_TAG/' .env 2>/dev/null || \
                echo 'IMAGE_TAG=$DEPLOY_TAG' >> .env"
        fi
    fi

    run_cmd "cd ~/alpha-search && \
        echo '${GITHUB_TOKEN:-}' | docker login ghcr.io -u '${GITHUB_ACTOR:-}' --password-stdin 2>/dev/null || true && \
        docker compose pull"

    log INFO "Images pulled successfully"
}

# Deploy services
deploy_services() {
    log STEP "Deploying services..."

    # Store current deployment for potential rollback
    if [[ "$DRY_RUN" == false ]]; then
        run_cmd "cd ~/alpha-search && \
            docker compose config > .docker-compose.last.yml 2>/dev/null || true"
    fi

    # Deploy with zero downtime
    run_cmd "cd ~/alpha-search && \
        docker compose up -d --remove-orphans"

    log INFO "Services deployed"
}

# Health checks
health_checks() {
    log STEP "Running health checks..."

    local services=("alpha-search-api" "alpha-search-ui" "nginx")
    local all_healthy=true

    for service in "${services[@]}"; do
        log INFO "Checking $service..."
        local healthy=false

        for i in $(seq 1 $MAX_RETRIES); do
            local status
            status=$(run_cmd "cd ~/alpha-search && docker compose ps $service --format json 2>/dev/null | grep -o '\"Health\":\"[^\"]*\"' | cut -d'\"' -f4" 2>/dev/null || echo "unknown")

            if [[ "$status" == "healthy" ]]; then
                log INFO "$service is healthy"
                healthy=true
                break
            fi

            # Alternative: check HTTP endpoint directly
            case "$service" in
                alpha-search-api)
                    if run_cmd "curl -fsS http://localhost:8000/health >/dev/null 2>&1"; then
                        log INFO "$service is responding to HTTP"
                        healthy=true
                        break
                    fi
                    ;;
                alpha-search-ui)
                    if run_cmd "curl -fsS http://localhost:8501/healthz >/dev/null 2>&1"; then
                        log INFO "$service is responding to HTTP"
                        healthy=true
                        break
                    fi
                    ;;
                nginx)
                    if run_cmd "curl -fsS http://localhost/health >/dev/null 2>&1"; then
                        log INFO "$service is responding to HTTP"
                        healthy=true
                        break
                    fi
                    ;;
            esac

            if [[ "$i" -eq "$MAX_RETRIES" ]]; then
                log WARN "$service health check failed after $MAX_RETRIES attempts"
                healthy=false
            else
                log INFO "  Attempt $i/$MAX_RETRIES - waiting ${RETRY_INTERVAL}s..."
                sleep "$RETRY_INTERVAL"
            fi
        done

        if [[ "$healthy" == false ]]; then
            all_healthy=false
        fi
    done

    if [[ "$all_healthy" == false ]]; then
        log ERROR "One or more services failed health checks"
        return 1
    fi

    log INFO "All services are healthy!"
    return 0
}

# Cleanup old resources
cleanup() {
    log STEP "Cleaning up..."

    # Remove old images
    run_cmd "docker image prune -af --filter 'until=72h' --filter 'label=com.docker.compose.project=$PROJECT_NAME' 2>/dev/null || true"

    # Remove unused volumes (be careful!)
    # run_cmd "docker volume prune -f 2>/dev/null || true"

    # Clean system
    run_cmd "docker system prune -f 2>/dev/null || true"

    # Clean old backups (keep last 30 days)
    run_cmd "find ~/alpha-search/backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true"

    log INFO "Cleanup completed"
}

# Rollback to previous deployment
rollback() {
    log STEP "Rolling back to previous deployment..."

    if [[ "$DRY_RUN" == true ]]; then
        log STEP "[DRY-RUN] Would rollback to previous docker-compose config"
        return 0
    fi

    # Check if previous config exists
    if ! run_cmd "test -f ~/alpha-search/.docker-compose.last.yml" 2>/dev/null; then
        log ERROR "No previous deployment found for rollback"
        exit 1
    fi

    # Restore previous config
    run_cmd "cd ~/alpha-search && \
        cp .docker-compose.last.yml docker-compose.yml && \
        docker compose up -d"

    log INFO "Rollback completed. Checking health..."

    if health_checks; then
        log INFO "Rollback successful - all services healthy"
    else
        log ERROR "Rollback services are not healthy - manual intervention required"
        exit 1
    fi
}

# Print deployment summary
print_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}                    DEPLOYMENT COMPLETE                        ${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Timestamp:${NC}     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo -e "  ${BOLD}Tag:${NC}           $DEPLOY_TAG"
    echo -e "  ${BOLD}VPS:${NC}           ${VPS_HOST:-local}"
    echo -e "  ${BOLD}Rollback:${NC}      ${ROLLBACK:-false}"
    echo ""
    echo -e "  ${BOLD}Services:${NC}"
    echo -e "    API:      http://${VPS_HOST:-localhost}/api"
    echo -e "    UI:       http://${VPS_HOST:-localhost}"
    echo -e "    Health:   http://${VPS_HOST:-localhost}/health"
    echo ""
    echo -e "  ${BOLD}Logs:${NC}         $LOG_FILE"
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════${NC}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    print_banner
    parse_args "$@"

    # Handle rollback first
    if [[ "$ROLLBACK" == true ]]; then
        rollback
        exit 0
    fi

    # Setup
    log INFO "Starting deployment..."
    log INFO "Target: ${VPS_HOST:-local}"
    log INFO "Tag: $DEPLOY_TAG"
    log INFO "Dry run: $DRY_RUN"

    mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_DIR"

    # Pre-deployment checks
    check_prerequisites

    # Create backup if requested
    create_backup

    # Deploy
    pull_images
    deploy_services

    # Post-deployment checks
    if health_checks; then
        cleanup
        print_summary
        log INFO "Deployment completed successfully!"
    else
        log ERROR "Health checks failed! Initiating rollback..."
        rollback
        log ERROR "Deployment failed. Rollback completed."
        exit 1
    fi
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi