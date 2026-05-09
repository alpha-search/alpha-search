#!/usr/bin/env bash
# =============================================================================
# Quant.OS - Automated Backup Script
# =============================================================================
# Backs up all persistent data to Cloudflare R2 (or local fallback)
#
# Usage:
#   ./scripts/backup.sh [options]
#
# Options:
#   --r2            Upload to Cloudflare R2 (default if configured)
#   --local         Keep local backup only
#   --retention N   Keep N days of backups (default: 30)
#   --dry-run       Show what would be backed up
#
# Cron setup:
#   0 3 * * * /opt/alpha-search/scripts/backup.sh --r2 >> /var/log/alpha-search-backup.log 2>&1
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="alpha-search-backup-$BACKUP_DATE"
RETENTION_DAYS=30
DRY_RUN=false
UPLOAD_R2=false
LOCAL_ONLY=false

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $*"; }
error() { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $*"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --r2) UPLOAD_R2=true; shift ;;
        --local) LOCAL_ONLY=true; shift ;;
        --retention) RETENTION_DAYS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Check if R2 is configured
if [[ "$LOCAL_ONLY" == false && -f "$PROJECT_DIR/.env" ]]; then
    source "$PROJECT_DIR/.env"
    if [[ -n "${R2_ACCESS_KEY_ID:-}" && -n "${R2_SECRET_ACCESS_KEY:-}" ]]; then
        UPLOAD_R2=true
    fi
fi

log "Starting backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# ── DuckDB Backup ────────────────────────────────────────────────────────
log "Backing up DuckDB database..."
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps alpha-search-api &>/dev/null; then
    if [[ "$DRY_RUN" == true ]]; then
        log "[DRY-RUN] Would backup DuckDB from container"
    else
        docker compose -f "$PROJECT_DIR/docker-compose.yml" cp \
            alpha-search-api:/data/alpha-search.duckdb \
            "$BACKUP_DIR/$BACKUP_NAME/alpha-search.duckdb" 2>/dev/null && \
            log "DuckDB backed up" || warn "DuckDB backup skipped (not found)"
    fi
else
    warn "API container not running, skipping DuckDB backup"
fi

# ── Redis Backup ─────────────────────────────────────────────────────────
log "Backing up Redis data..."
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps redis &>/dev/null; then
    if [[ "$DRY_RUN" == true ]]; then
        log "[DRY-RUN] Would backup Redis from container"
    else
        docker compose -f "$PROJECT_DIR/docker-compose.yml" exec redis \
            redis-cli BGSAVE >/dev/null 2>&1 || true
        sleep 2
        docker compose -f "$PROJECT_DIR/docker-compose.yml" cp \
            redis:/data/dump.rdb \
            "$BACKUP_DIR/$BACKUP_NAME/redis.rdb" 2>/dev/null && \
            log "Redis backed up" || warn "Redis backup skipped"
    fi
else
    warn "Redis container not running, skipping Redis backup"
fi

# ── Configuration Backup ─────────────────────────────────────────────────
log "Backing up configuration..."
if [[ "$DRY_RUN" == false ]]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/$BACKUP_NAME/env" 2>/dev/null || true
    cp "$PROJECT_DIR/docker-compose.yml" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true
    docker compose -f "$PROJECT_DIR/docker-compose.yml" config \
        > "$BACKUP_DIR/$BACKUP_NAME/docker-compose-resolved.yml" 2>/dev/null || true
fi

# ── Create Archive ───────────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    cd "$BACKUP_DIR"
    tar czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME/" && \
        rm -rf "$BACKUP_DIR/$BACKUP_NAME" && \
        log "Archive created: $BACKUP_NAME.tar.gz ($(du -h "$BACKUP_NAME.tar.gz" | cut -f1))"
fi

# ── Upload to R2 ─────────────────────────────────────────────────────────
if [[ "$UPLOAD_R2" == true && "$DRY_RUN" == false ]]; then
    log "Uploading to Cloudflare R2..."
    if command -v rclone &>/dev/null; then
        rclone copy "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
            "r2:alpha-search-backups/" && \
            log "Uploaded to R2" || warn "R2 upload failed"
    elif command -v aws &>/dev/null; then
        aws s3 cp "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
            "s3://alpha-search-backups/" \
            --endpoint-url "${R2_ENDPOINT:-}" && \
            log "Uploaded to R2 (via aws CLI)" || warn "R2 upload failed"
    else
        warn "Neither rclone nor aws CLI found. Install one for R2 uploads."
    fi
fi

# ── Cleanup Old Backups ──────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "alpha-search-backup-*.tar.gz" -mtime "+$RETENTION_DAYS" \
        -delete -print | while read -r f; do
        log "Deleted old backup: $f"
    done
fi

log "Backup complete: $BACKUP_NAME.tar.gz"