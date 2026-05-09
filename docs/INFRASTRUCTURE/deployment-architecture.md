# Alpha Search - Deployment Architecture

> **Version:** 1.0.0  
> **Last Updated:** 2025-01-XX  
> **Status:** Phase 1 - Active Development  
> **Owner:** Alpha Search DevOps Team  

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: Basic (Current)](#phase-1-basic-current)
3. [Phase 2: Enhanced (Month 3-4)](#phase-2-enhanced-month-3-4)
4. [Phase 3: Scaled (Month 6+)](#phase-3-scaled-month-6)
5. [Architecture Diagrams](#architecture-diagrams)
6. [Network Topology](#network-topology)
7. [Security Model](#security-model)
8. [Disaster Recovery](#disaster-recovery)
9. [Monitoring & Observability](#monitoring--observability)
10. [Decision Log](#decision-log)

---

## Overview

Alpha Search uses a **phased deployment strategy** that prioritizes:

1. **Low cost** - Start at ~$5/month, scale only when revenue justifies
2. **Simplicity** - Docker-native, minimal moving parts
3. **Cloudflare-first** - CDN, DNS, security, and analytics in one free tier
4. **Zero-downtime deployments** - Rolling updates with health checks
5. **Infrastructure as Code** - Everything versioned in Git

### Core Principles

| Principle | Implementation |
|-----------|---------------|
| Stateless services | All state in volumes, config in env vars |
| Immutable infrastructure | Docker images, no server mutations |
| GitOps | Git is the single source of truth |
| Observability | Structured logging, health checks, basic metrics |
| Security by default | Non-root containers, minimal attack surface |

---

## Phase 1: Basic (Current)

**Timeline:** Now - Month 2  
**Monthly Cost:** ~$5  
**Target Users:** 1-10 concurrent users

### Infrastructure Stack

| Component | Technology | Purpose | Cost |
|-----------|-----------|---------|------|
| **VPS** | Hostinger KVM 1 (1 vCPU, 1GB RAM, 20GB SSD) | Application host | $3.99/mo |
| **CDN/DNS** | Cloudflare Free Tier | DDoS protection, caching, DNS | Free |
| **SSL** | Cloudflare Origin CA + Let's Encrypt | HTTPS termination | Free |
| **Domain** | Namecheap / Cloudflare Registrar | alpha-search.dev | ~$1/mo |
| **Email** | ImprovMX | Forwarding dev@alpha-search.dev | Free |
| **CI/CD** | GitHub Actions | Build, test, deploy | Free (public repo) |
| **Container Registry** | GitHub Container Registry (GHCR) | Docker image storage | Free |
| **Database** | DuckDB (file-based) | Local analytics cache | Free |
| **Cache** | Redis (Docker) | Session & API caching | Free |
| **Monitoring** | Docker Healthchecks + UptimeRobot | Basic availability | Free |

### Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE EDGE                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   DNS / CDN  │  │  DDoS Prot.  │  │   WAF / Bot Management   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘  │
│         └──────────────────┼──────────────────────┘                  │
└────────────────────────────┼────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      HOSTINGER VPS (1GB)                            │
│                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │   Nginx     │───▶│  Docker      │───▶│  alpha-search-api:8000   │   │
│  │  (reverse   │    │  Compose     │    │  (FastAPI/Uvicorn)   │   │
│  │   proxy)    │    │              │    └──────────────────────┘   │
│  │  :80,:443   │    │              │    ┌──────────────────────┐   │
│  └─────────────┘    │  Services:   │───▶│  alpha-search-ui:8501    │   │
│                     │              │    │  (Streamlit)         │   │
│  SSL: CF Origin CA  │  - API       │    └──────────────────────┘   │
│                     │  - UI        │    ┌──────────────────────┐   │
│  UFW Firewall       │  - Redis     │───▶│  redis:6379          │   │
│  fail2ban           │  - DuckDB    │    │  (session cache)     │   │
│                     │  - Nginx     │    └──────────────────────┘   │
│                     │  - Watchtower│    ┌──────────────────────┐   │
│                     │              │───▶│  duckdb (volume)     │   │
│                     │              │    │  (analytics data)    │   │
│                     └──────────────┘    └──────────────────────┘   │
│                                                                     │
│  Volumes: alpha-search-cache, redis-data, duckdb-data, nginx-logs     │
│  Network: 172.28.0.0/16 (bridge)                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
User Request
    │
    ▼
┌─────────────┐
│  Cloudflare │  ← DNS resolution, DDoS protection, edge caching
│    Proxy    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Nginx    │  ← SSL termination, rate limiting, routing
│  (VPS :443) │
└──────┬──────┘
       │
   ┌───┴───────────────┐
   │                   │
   ▼                   ▼
┌──────────┐    ┌──────────┐
│ /api/*   │    │ /*       │
│   │      │    │   │      │
│   ▼      │    │   ▼      │
│ API:8000 │    │ UI:8501  │
└──────────┘    └──────────┘
```

### Data Flow

```
External Data Sources                    Alpha Search
┌─────────────────┐                ┌──────────────────┐
│ Yahoo Finance   │───HTTP API───▶│  alpha-search-api    │
│ (free)          │                │                  │
└─────────────────┘                │  ┌────────────┐  │
                                   │  │  DuckDB    │  │
┌─────────────────┐                │  │ (cache)    │  │
│  FRED (St. Louis│───HTTP API───▶│  └────────────┘  │
│  Fed)           │                │                  │
└─────────────────┘                │  ┌────────────┐  │
                                   │  │  Redis     │  │
┌─────────────────┐                │  │ (session)  │  │
│  World Bank     │───HTTP API───▶│  └────────────┘  │
│                 │                │                  │
└─────────────────┘                └──────────────────┘
```

### File System Layout (VPS)

```
/home/quantos/
├── alpha-search/                      # Git repository
│   ├── docker-compose.yml         # Production compose
│   ├── .env                       # Environment variables (600 perms)
│   ├── nginx/
│   │   ├── nginx.conf             # Main nginx config
│   │   ├── conf.d/
│   │   │   ├── api.conf           # API vhost
│   │   │   └── ui.conf            # UI vhost
│   │   └── ssl/                   # Cloudflare Origin CA certs
│   ├── scripts/
│   │   ├── deploy.sh              # Deployment script
│   │   ├── setup-vps.sh           # VPS initialization
│   │   └── backup.sh              # Backup script
│   └── data/                      # Docker volume mount points
│
├── backups/                       # Automated backups
│   ├── duckdb-$(date).duckdb
│   └── redis-$(date).rdb
│
└── logs/                          # Centralized logs
    ├── nginx/
    ├── api/
    └── docker-events.log
```

### Configuration Files

#### Nginx Main Config (`nginx/nginx.conf`)

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging format (structured)
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50m;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Include vhosts
    include /etc/nginx/conf.d/*.conf;
}
```

#### API Vhost (`nginx/conf.d/api.conf`)

```nginx
server {
    listen 80;
    server_name api.alpha-search.dev;

    # Cloudflare IP ranges (for real_ip)
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;
    real_ip_header CF-Connecting-IP;

    location / {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://alpha-search-api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout 10s;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass http://alpha-search-api:8000/health;
        access_log off;
    }
}
```

---

## Phase 2: Enhanced (Month 3-4)

**Timeline:** Month 3-4  
**Monthly Cost:** ~$15-20  
**Target Users:** 10-50 concurrent users  
**Triggers:** Revenue > $100/mo OR active users > 10

### New Components

| Component | Technology | Purpose | Cost |
|-----------|-----------|---------|------|
| **Upgraded VPS** | Hostinger KVM 2 (2 vCPU, 4GB RAM) | Handle more load | $7.99/mo |
| **Message Queue** | Redpanda (Kafka-compatible) | Real-time data streaming | Free (self-hosted) |
| **Database** | PostgreSQL 15 | Persistent user data, logs | Free (self-hosted) |
| **WebSockets** | Socket.IO / native WS | Live price streaming | Free |
| **Object Storage** | Cloudflare R2 | Backups, exports | Free tier (10GB) |
| **Broker API** | Zerodha Kite Connect | Indian market data | Rs 2000/mo (~$24) |

### Enhanced Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLOUDFLARE                                   │
│  CDN / DNS / WAF / Analytics / R2 (object storage)                      │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        HOSTINGER VPS (4GB)                                │
│                                                                          │
│  ┌──────────┐  ┌──────────────────────────────────────────────────┐      │
│  │  Nginx   │──│  Docker Compose Stack                            │      │
│  └──────────┘  │                                                  │      │
│                │  ┌───────────┐  ┌───────────┐  ┌──────────────┐ │      │
│                │  │   API     │  │    UI     │  │  WebSocket   │ │      │
│                │  │  (x2)     │  │  (x1)     │  │   Server     │ │      │
│                │  └─────┬─────┘  └───────────┘  └──────┬───────┘ │      │
│                │        │                                │         │      │
│                │  ┌─────┴──────────┐  ┌──────────────────┴───────┐ │      │
│                │  │  PostgreSQL    │  │     Redpanda (Kafka)      │ │      │
│                │  │  (persistent)  │  │  - price streams          │ │      │
│                │  └────────────────┘  │  - event log              │ │      │
│                │                      │  - agent tasks            │ │      │
│                │                      └──────────────────────────┘ │      │
│                │  ┌──────────────┐  ┌──────────────────────────┐   │      │
│                │  │    Redis     │  │    DuckDB (analytics)    │   │      │
│                │  │  (sessions)  │  │  (kept for OLAP)         │   │      │
│                │  └──────────────┘  └──────────────────────────┘   │      │
│                └──────────────────────────────────────────────────┘      │
│                                                                          │
│  Data Sources:  Yahoo Finance  FRED  World Bank  Zerodha Kite           │
│                     │             │        │          │                  │
│                     └─────────────┴────────┴──────────┘                  │
│                                          │                               │
│                                          ▼                               │
│                                ┌──────────────────┐                      │
│                                │  Redpanda Topics │                      │
│                                │  - prices.raw    │                      │
│                                │  - prices.ohlc   │                      │
│                                │  - signals       │                      │
│                                │  - trades        │                      │
│                                └──────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────┘
```

### WebSocket Architecture

```
┌──────────┐    WS /wss/live    ┌──────────────────┐
│  Client  │◄─────────────────►│  WS Gateway      │
│ (Browser)│                   │  (Socket.IO)     │
└──────────┘                   └────────┬─────────┘
                                        │
                            ┌───────────┼───────────┐
                            │           │           │
                            ▼           ▼           ▼
                       ┌────────┐  ┌──────────┐  ┌──────────┐
                       │ Redis  │  │ Redpanda │  │  Client  │
                       │ PubSub │  │ Consumer │  │ Manager  │
                       └────────┘  └──────────┘  └──────────┘
```

---

## Phase 3: Scaled (Month 6+)

**Timeline:** Month 6+  
**Monthly Cost:** $30-80  
**Target Users:** 50-500 concurrent users  
**Triggers:** Revenue > $500/mo OR active users > 50

### Architecture: Docker Swarm

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLOUDFLARE                                   │
│  Load Balancing / Argo Tunnel / Advanced DDoS / Bot Management          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌──────────────────────────┐     ┌──────────────────────────┐
│      VPS Node 1          │     │      VPS Node 2          │
│   (Manager)              │◄───►│   (Worker)               │
│   $7.99/mo               │     │   $7.99/mo               │
│                          │     │                          │
│ ┌─────────────┐         │     │ ┌─────────────┐          │
│ │ Nginx (VIP) │         │     │ │ Nginx (VIP) │          │
│ └──────┬──────┘         │     │ └──────┬──────┘          │
│        │ Docker Swarm   │     │        │ Docker Swarm    │
│        ▼                │     │        ▼                 │
│ ┌──────────────┐       │     │ ┌──────────────┐         │
│ │ API Replica  │       │     │ │ API Replica  │         │
│ └──────────────┘       │     │ └──────────────┘         │
│ ┌──────────────┐       │     │ ┌──────────────┐         │
│ │ UI Replica   │       │     │ │ Worker Proc  │         │
│ └──────────────┘       │     │ └──────────────┘         │
│ ┌──────────────┐       │     │ ┌──────────────┐         │
│ │ Redpanda     │◄──────┘     │ │ Scanner      │         │
│ └──────────────┘ Raft conn   │ └──────────────┘         │
│ ┌──────────────┐             │                          │
│ │ PostgreSQL   │             │                          │
│ │ (primary)    │             │                          │
│ └──────────────┘             │                          │
└──────────────────────────────┘             └──────────────────────────────┘
```

### New Components

| Component | Technology | Purpose | Cost |
|-----------|-----------|---------|------|
| **Orchestration** | Docker Swarm Mode | Multi-node container orchestration | Free |
| **Vector Database** | Qdrant or Chroma | AI agent memory, semantic search | Free (self-hosted) |
| **Task Queue** | Celery + Redis | Background job processing | Free |
| **Scraper Cluster** | Multiple workers | Distributed data collection | Free |
| **Monitoring** | Grafana + Prometheus + Loki | Full observability stack | Free |
| **Log Aggregation** | Loki + Promtail | Centralized logging | Free |

### Multi-Agent Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Agent Orchestrator                   │
│              (FastAPI + Celery + Redis)               │
└──────────┬──────────┬──────────┬──────────────────────┘
           │          │          │
           ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌──────────┐
    │  Market  ││  Risk    ││Portfolio │
    │  Agent   ││  Agent   ││  Agent   │
    └────┬─────┘└────┬─────┘└────┬─────┘
         │           │           │
         └───────────┼───────────┘
                     │
                     ▼
           ┌──────────────────┐
           │  Shared Memory   │
           │  (Qdrant Vector  │
           │   + PostgreSQL)  │
           └──────────────────┘
```

### Data Pipeline (Phase 3)

```
Data Sources                    Processing                      Storage
┌──────────────┐           ┌─────────────────┐           ┌──────────────────┐
│ Yahoo Finance│──────────▶│                 │──────────▶│ PostgreSQL       │
└──────────────┘           │                 │           │ (time series)    │
                           │   Redpanda      │           └──────────────────┘
┌──────────────┐           │   Stream        │
│ Zerodha Kite │──────────▶│   Processing    │──────────▶┌──────────────────┐
└──────────────┘           │                 │           │ DuckDB (OLAP)    │
                           │                 │           │ (analytics)      │
┌──────────────┐           │   ┌─────────┐   │           └──────────────────┘
│ RSS/News     │──────────▶│   │Transform│   │
└──────────────┘           │   │Enrich   │   │──────────▶┌──────────────────┐
                           │   │Route    │   │           │ Qdrant           │
┌──────────────┐           │   └─────────┘   │           │ (vector memory)  │
│ Social Media │──────────▶│                 │           └──────────────────┘
└──────────────┘           └─────────────────┘
```

---

## Architecture Diagrams

### Full System Overview (ASCII)

```
                          QUANT.OS SYSTEM OVERVIEW
                    "Quantitative Finance, Simplified"

┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│                                                                          │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│   │  Web Browser │  │  Mobile App  │  │  CLI Tool    │  │  Jupyter  │  │
│   │  (Streamlit) │  │  (PWA)       │  │  (Python)    │  │  Notebook │  │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘  │
└──────────┼────────────────┼────────────────┼────────────────┼──────────┘
           │                │                │                │
           └────────────────┴────────────────┴────────────────┘
                                    │
                              HTTPS / WSS
                                    │
┌───────────────────────────────────┼──────────────────────────────────────┐
│                              EDGE LAYER                                  │
│                              (Cloudflare)                                │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  DNS  │  CDN Cache  │  DDoS Protection  │  WAF  │  SSL/TLS    │   │
│   │  .dev │  Static     │  Rate Limiting    │  Rules│  Termination│   │
│   └─────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┼──────────────────────────────────────┘
                                    │
                         Origin Pull (Authenticated)
                                    │
┌───────────────────────────────────┼──────────────────────────────────────┐
│                         APPLICATION LAYER                                │
│                        (Hostinger VPS / OCI)                             │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    Nginx Reverse Proxy                       │        │
│  │         SSL, Rate Limiting, Routing, Static Files            │        │
│  └───────────────┬──────────────────────────────┬──────────────┘        │
│                  │                              │                        │
│        ┌─────────▼──────────┐        ┌──────────▼─────────┐             │
│        │  FastAPI Backend   │        │  Streamlit Frontend │             │
│        │  /api/v1/*         │        │  /* (UI)            │             │
│        │                    │        │                     │             │
│        │  ┌──────────────┐  │        │  ┌──────────────┐   │             │
│        │  │ REST API     │  │        │  │ Pages        │   │             │
│        │  │ WebSocket    │  │        │  │ Components   │   │             │
│        │  │ Auth/JWT     │  │        │  │ Charts       │   │             │
│        │  │ Rate Limit   │  │        │  │ Data Grids   │   │             │
│        │  └──────────────┘  │        │  └──────────────┘   │             │
│        └─────────┬──────────┘        └─────────────────────┘             │
│                  │                                                       │
│  ┌───────────────┼───────────────────────────────────────────────┐       │
│  │               ▼                                               │       │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐     │       │
│  │  │  Redis      │  │  DuckDB     │  │  Redpanda/Kafka  │     │       │
│  │  │  (Cache)    │  │  (OLAP)     │  │  (Streaming)     │     │       │
│  │  └─────────────┘  └─────────────┘  └──────────────────┘     │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │ Watchtower   │  │ Promtail     │  │ Node Exporter│  │ cAdvisor     ││
│  │ (Updates)    │  │ (Log Ship)   │  │ (Metrics)    │  │ (Containers) ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼──────────────────────────────────────┐
│                         DATA SOURCE LAYER                                │
│                                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│   │  Yahoo   │  │  FRED    │  │  World   │  │  Zerodha │  │  RSS/    │ │
│   │  Finance │  │  (Fed)   │  │  Bank    │  │  Kite    │  │  News    │ │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Container Communication

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Docker Network: alpha-search-net                     │
│                         172.28.0.0/16                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Nginx (172.28.0.10)                                        │   │
│  │  - Port 80/443 exposed to host                              │   │
│  │  - Routes to internal services                              │   │
│  └──────┬──────────────┬──────────────────────┬────────────────┘   │
│         │              │                      │                      │
│         ▼              ▼                      ▼                      │
│  ┌──────────────┐ ┌──────────┐  ┌──────────────────────┐          │
│  │ API (8000)   │ │UI (8501) │  │   Health Checks      │          │
│  │ 172.28.0.20  │ │172.28.0.30│  │   /health            │          │
│  └──────┬───────┘ └──────────┘  └──────────────────────┘          │
│         │                                                           │
│         └───────────┬───────────────┐                               │
│                     │               │                               │
│                     ▼               ▼                               │
│              ┌──────────────┐ ┌──────────────┐                     │
│              │ Redis (6379) │ │DuckDB (file) │                     │
│              │ 172.28.0.40  │ │172.28.0.50   │                     │
│              └──────────────┘ └──────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Network Topology

### Port Map

| Port | Service | Protocol | Access | Notes |
|------|---------|----------|--------|-------|
| 80 | Nginx | HTTP | Public | Redirects to 443 |
| 443 | Nginx | HTTPS | Public | Cloudflare origin pull |
| 8000 | FastAPI | HTTP | Localhost only | Via Nginx proxy |
| 8501 | Streamlit | HTTP | Localhost only | Via Nginx proxy |
| 6379 | Redis | TCP | Internal | Docker network only |
| 9090 | Prometheus | HTTP | Localhost | Phase 3 monitoring |
| 3000 | Grafana | HTTP | Localhost | Phase 3 dashboards |

### Firewall Rules (UFW)

```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     LIMIT       Anywhere           # SSH (rate limited)
80/tcp                     ALLOW       Anywhere           # HTTP
443/tcp                    ALLOW       Anywhere           # HTTPS
8000/tcp                   DENY        Anywhere           # API (local only)
8501/tcp                   DENY        Anywhere           # UI (local only)

# Cloudflare IPs only (origin pull)
# Managed by cloudflare-ufw script
```

---

## Security Model

### Defense in Depth

```
Layer 1: Cloudflare Edge
├── DDoS Protection (unmetered)
├── Bot Management
├── WAF Rules
├── IP Reputation filtering
└── SSL/TLS encryption

Layer 2: VPS Host
├── UFW Firewall (deny-all default)
├── fail2ban (SSH, nginx brute force)
├── Automatic security updates
├── Unattended-upgrades
└── SSH key-only (no password)

Layer 3: Docker
├── Non-root containers
├── Read-only filesystems
├── No new privileges
├── Resource limits (CPU/memory)
├── Network isolation
└── Security labels

Layer 4: Application
├── JWT authentication
├── Rate limiting per IP
├── Input validation
├── SQL injection prevention (ORM)
├── XSS protection (headers)
└── Secure defaults
```

### Secret Management

| Secret | Location | Access |
|--------|----------|--------|
| API keys (data sources) | `.env` file (600 perms) | API container only |
| JWT signing key | `.env` file / Docker secret | API container only |
| Database passwords | `.env` file / Docker secret | API container only |
| SSH deploy key | GitHub Secrets | CI/CD only |
| VPS credentials | GitHub Secrets | CI/CD only |
| Cloudflare tokens | GitHub Secrets | CI/CD only |

---

## Disaster Recovery

### Backup Strategy

| Data | Method | Frequency | Retention | Location |
|------|--------|-----------|-----------|----------|
| DuckDB database | `cp` to R2 | Daily | 30 days | Cloudflare R2 |
| Redis data | `BGSAVE` + copy | Hourly | 7 days | R2 + local |
| PostgreSQL | `pg_dump` | Daily | 30 days | R2 |
| Nginx logs | Logrotate + rclone | Weekly | 90 days | R2 |
| Code/config | Git | Every push | Forever | GitHub |

### Recovery Procedures

```
Scenario: VPS failure
Time to recover: < 15 minutes

1. Provision new VPS (Hostinger: ~2 min)
2. Run setup-vps.sh (automated: ~5 min)
3. Restore DuckDB from R2 backup (< 1 min)
4. Update Cloudflare DNS to new IP (< 1 min)
5. Verify health checks pass (~2 min)

Total: ~15 minutes maximum
```

```
Scenario: Data corruption
Time to recover: < 5 minutes

1. Stop affected service: docker compose stop alpha-search-api
2. Restore DuckDB from backup: rclone copy R2:backup/duckdb-latest ./data/
3. Restart service: docker compose up -d alpha-search-api
4. Verify: curl http://localhost:8000/health

Total: ~5 minutes
```

---

## Monitoring & Observability

### Phase 1: Basic (Now)

| Tool | Purpose | Cost |
|------|---------|------|
| Docker Healthchecks | Container health | Free |
| UptimeRobot | External uptime monitoring | Free (5 min intervals) |
| Nginx access logs | Request analytics | Free |
| Application logs (JSON) | Structured logging | Free |
| `docker stats` | Resource usage | Free |

### Phase 3: Full Observability Stack

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Prometheus  │    │    Loki      │    │   Grafana    │
│  (metrics)   │    │  (logs)      │    │ (dashboards) │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Agents    │
                    │             │
                    │ Node Exporter (system)
                    │ cAdvisor (containers)
                    │ Promtail (logs)
                    │ API /metrics endpoint
                    └─────────────┘
```

### Alerting Rules (Phase 3)

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| API Down | health != 200 for 2m | Critical | Discord notify |
| High CPU | usage > 80% for 5m | Warning | Scale alert |
| High Memory | usage > 85% for 5m | Warning | Discord notify |
| Disk Full | usage > 85% | Critical | Discord + cleanup |
| Error Rate | 5xx > 5% for 5m | Critical | Discord notify |

---

## Decision Log

| Date | Decision | Alternatives | Rationale |
|------|----------|--------------|-----------|
| 2025-01 | Hostinger VPS | AWS, DO, Hetzner | Cheapest managed VPS with good Asia connectivity |
| 2025-01 | Cloudflare Free | AWS CloudFront | Free tier covers all current needs |
| 2025-01 | DuckDB | PostgreSQL, SQLite | Better analytics performance, zero config |
| 2025-01 | Redis (Docker) | Redis Cloud, Memcached | Self-hosted is free, sufficient for cache |
| 2025-01 | Docker Compose | K8s, Nomad, Swarm | Simplest option, no orchestration overhead |
| 2025-01 | GHCR | Docker Hub, ECR | Integrated with GitHub, free for public repos |
| 2025-01 | GitHub Actions | Jenkins, Drone, Travis | Free for public repos, native GH integration |
| 2025-01 | Redpanda (planned) | Kafka, NATS | Kafka-compatible, lower resource usage |
| 2025-01 | Nginx | Caddy, Traefik | Battle-tested, extensive documentation |
| 2025-01 | Watchtower | ArgoCD, Flux | Simple auto-updates without complexity |

---

## Appendix

### Useful Commands

```bash
# View all container status
docker compose ps

# View logs
docker compose logs -f alpha-search-api
docker compose logs -f --tail=100 alpha-search-ui

# Restart a service
docker compose restart alpha-search-api

# Scale API replicas (Phase 3 Swarm)
docker compose up -d --scale alpha-search-api=3

# Enter a container
docker compose exec alpha-search-api /bin/sh

# Database backup
docker compose exec -T alpha-search-api \
  sh -c 'cp /data/alpha-search.duckdb /backups/alpha-search-$(date +%Y%m%d).duckdb'

# Resource usage
docker stats

# Update all images
docker compose pull && docker compose up -d

# Full system prune (careful!)
docker system prune -a --volumes
```

### Links & Resources

- [Hostinger VPS Panel](https://hpanel.hostinger.com/vps)
- [Cloudflare Dashboard](https://dash.cloudflare.com)
- [GitHub Container Registry](https://github.com/alpha-search/alpha-search/pkgs/container/alpha-search)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Nginx Configuration](https://nginx.org/en/docs/)