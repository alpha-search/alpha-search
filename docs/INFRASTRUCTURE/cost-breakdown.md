# Alpha Search - Infrastructure Cost Breakdown

> **Version:** 1.0.0  
> **Last Updated:** 2025-01-XX  
> **Currency:** USD (monthly unless noted)  

---

## Executive Summary

| Phase | Timeline | Monthly Cost | Annual Cost | Max Concurrent Users |
|-------|----------|-------------|-------------|---------------------|
| **Phase 1: Basic** | Now - Month 2 | **~$5** | **~$60** | 1-10 |
| **Phase 2: Enhanced** | Month 3-4 | **~$15-25** | **~$180-300** | 10-50 |
| **Phase 3: Scaled** | Month 6+ | **~$30-80** | **~$360-960** | 50-500 |

---

## Phase 1: Basic (Now - Month 2)

**Strategy:** Minimal viable infrastructure. Every dollar must be justified.

### Monthly Cost Table

| # | Service | Provider | Specs | Monthly | Annual | Notes |
|---|---------|----------|-------|---------|--------|-------|
| 1 | **VPS** | Hostinger | 1 vCPU, 1GB RAM, 20GB NVMe SSD | **$3.99** | $47.88 | KVM 1 plan; 4-year prepaid = $2.99/mo |
| 2 | **CDN / DNS** | Cloudflare | Free Tier | **$0.00** | $0.00 | Unlimited bandwidth, DDoS protection |
| 3 | **Domain** | Cloudflare Registrar | .dev TLD | **~$0.83** | ~$9.99 | First year often discounted |
| 4 | **Email Forwarding** | ImprovMX | Free plan (25 domains) | **$0.00** | $0.00 | dev@alpha-search.dev forwarded to Gmail |
| 5 | **SSL Certificates** | Cloudflare Origin CA + Let's Encrypt | Unlimited | **$0.00** | $0.00 | Auto-renewal via certbot |
| 6 | **CI/CD** | GitHub Actions | Public repository | **$0.00** | $0.00 | 2,000 minutes/month free |
| 7 | **Container Registry** | GitHub Container Registry | Public images | **$0.00** | $0.00 | Unlimited public pulls |
| 8 | **Container Orchestration** | Docker Compose | Self-managed | **$0.00** | $0.00 | Included with Docker |
| 9 | **Database (Cache)** | Redis 7 | Docker container | **$0.00** | $0.00 | 128MB memory limit |
| 10 | **Database (Analytics)** | DuckDB | File-based | **$0.00** | $0.00 | Zero operational cost |
| 11 | **Reverse Proxy** | Nginx | Alpine Linux container | **$0.00** | $0.00 | Official nginx:alpine image |
| 12 | **Uptime Monitoring** | UptimeRobot | Free plan (50 monitors) | **$0.00** | $0.00 | 5-minute check intervals |
| 13 | **Log Storage** | Local filesystem | Docker volumes | **$0.00** | $0.00 | Rotated via logrotate |

### Phase 1 Summary

```
┌──────────────────────────────────────────┐
│         PHASE 1: MONTHLY COST            │
├──────────────────────────────────────────┤
│  Infrastructure     $3.99                │
│  Domain             $0.83                │
│  Services           $0.00                │
│  ─────────────────────────               │
│  TOTAL              $4.82  (~$5/month)   │
│                                          │
│  Year 1 Total: ~$58                      │
│  Per-user cost: $0.48 (at 10 users)      │
└──────────────────────────────────────────┘
```

### Free Alternatives Considered

| Service | Our Choice | Alternative | Why Not Alternative |
|---------|-----------|-------------|-------------------|
| VPS ($3.99) | Hostinger | Oracle Cloud Free Tier | OCI ARM is free but requires credit card, complex setup, no IPv4 |
| Domain ($0.83) | Cloudflare | Freenom (.tk/.ml) | Freenom domains are often reclaimed; bad for credibility |
| Monitoring ($0) | UptimeRobot | Datadog / New Relic | Overkill and expensive at this stage |
| Email ($0) | ImprovMX | Google Workspace ($6/mo) | Too expensive for a single email address |

---

## Phase 2: Enhanced (Month 3-4)

**Trigger:** Revenue > $100/month OR active users > 10 OR need real-time data

### New / Upgraded Services

| # | Service | Provider | Specs | Monthly | Change | Notes |
|---|---------|----------|-------|---------|--------|-------|
| 1 | **VPS (upgraded)** | Hostinger | 2 vCPU, 4GB RAM, 50GB NVMe | **$7.99** | +$4.00 | KVM 2 plan; handles ~50 concurrent |
| 2 | **CDN / DNS** | Cloudflare | Pro plan (optional) | **$0.00** | $0 | Free tier still sufficient |
| 3 | **Message Queue** | Redpanda | Self-hosted Docker | **$0.00** | +$0 | Kafka-compatible, low resource |
| 4 | **Database (Persistent)** | PostgreSQL 15 | Self-hosted Docker | **$0.00** | +$0 | For user accounts, trade logs |
| 5 | **Object Storage** | Cloudflare R2 | Free tier (10GB/month) | **$0.00** | +$0 | Backups, data exports |
| 6 | **Indian Market Data** | Zerodha Kite | Connect API | **~$24.00** | +$24 | Rs 2000/month; optional if not trading IN |
| 7 | **WebSocket Server** | Socket.IO | Self-hosted | **$0.00** | +$0 | Part of API container |
| 8 | **Auto SSL** | Let's Encrypt + certbot | Automated renewal | **$0.00** | +$0 | Cron-based renewal |

### Phase 2 Summary

```
┌──────────────────────────────────────────────┐
│          PHASE 2: MONTHLY COST               │
├──────────────────────────────────────────────┤
│  Infrastructure          $7.99               │
│  Domain                  $0.83               │
│  Indian Market Data      $24.00  (optional)  │
│  Services                $0.00               │
│  ─────────────────────────────────           │
│  WITHOUT Zerodha:        $8.82  (~$9/month)  │
│  WITH Zerodha:           $32.82 (~$33/month) │
│                                              │
│  Year 1 (w/ Zerodha): ~$394                  │
│  Per-user cost: $0.66 (at 50 users)          │
└──────────────────────────────────────────────┘
```

---

## Phase 3: Scaled (Month 6+)

**Trigger:** Revenue > $500/month OR active users > 50 OR need high availability

### Multi-Node Setup

| # | Service | Provider | Specs | Monthly | Notes |
|---|---------|----------|-------|---------|-------|
| 1 | **VPS Node 1 (Manager)** | Hostinger | 2 vCPU, 4GB RAM | **$7.99** | Docker Swarm manager + Nginx |
| 2 | **VPS Node 2 (Worker)** | Hostinger | 2 vCPU, 4GB RAM | **$7.99** | Application workloads |
| 3 | **VPS Node 3 (Worker)** | Hostinger | 2 vCPU, 4GB RAM | **$7.99** | Optional; add when needed |
| 4 | **Load Balancer** | Nginx (self) | Active-passive HA | **$0.00** | Keepalived + VRRP |
| 5 | **CDN / DNS** | Cloudflare | Pro ($20) or Free | **$0.00** | Free tier often sufficient |
| 6 | **Message Queue** | Redpanda cluster | 3-node Raft | **$0.00** | Self-hosted across nodes |
| 7 | **Database (Primary)** | PostgreSQL | On manager node | **$0.00** | Self-hosted |
| 8 | **Vector Database** | Qdrant | Docker container | **$0.00** | AI agent memory |
| 9 | **Task Queue** | Celery + Redis | Distributed workers | **$0.00** | Background jobs |
| 10 | **Object Storage** | Cloudflare R2 | >10GB tier | **~$0.36** | $0.036/GB after 10GB free |
| 11 | **Monitoring Stack** | Grafana + Prometheus + Loki | Self-hosted | **$0.00** | Full observability |
| 12 | **Log Aggregation** | Loki + Promtail | Centralized logs | **$0.00** | Query logs via Grafana |
| 13 | **Backup Storage** | Cloudflare R2 | 100GB estimated | **~$1.50** | Compressed backups |
| 14 | **Indian Market Data** | Zerodha Kite | Connect API | **~$24.00** | Optional |

### Phase 3 Configurations

#### Minimal (2 nodes)

```
┌──────────────────────────────────────────────┐
│       PHASE 3 MINIMAL: 2 NODES               │
├──────────────────────────────────────────────┤
│  VPS Node 1 (Manager)     $7.99              │
│  VPS Node 2 (Worker)      $7.99              │
│  R2 Storage               $0.50              │
│  Domain                   $0.83              │
│  ─────────────────────────────────           │
│  TOTAL:                   $17.31/month       │
│  Annual:                  ~$208               │
└──────────────────────────────────────────────┘
```

#### Full (3 nodes + monitoring)

```
┌──────────────────────────────────────────────┐
│        PHASE 3 FULL: 3 NODES                 │
├──────────────────────────────────────────────┤
│  VPS Node 1 (Manager)     $7.99              │
│  VPS Node 2 (Worker)      $7.99              │
│  VPS Node 3 (Worker)      $7.99              │
│  R2 Storage               $1.50              │
│  Domain                   $0.83              │
│  Zerodha Kite (optional)  $24.00             │
│  ─────────────────────────────────           │
│  WITHOUT Zerodha:         $26.30/month       │
│  WITH Zerodha:            $50.30/month       │
│                                              │
│  Annual (w/ Zerodha):     ~$604              │
│  Per-user cost:           $0.10 (at 500)     │
└──────────────────────────────────────────────┘
```

---

## Cost Comparison: Self-Hosted vs Cloud Providers

### Annual Cost for Equivalent Setup (Phase 2 level)

| Provider | Setup | Monthly | Annual | Notes |
|----------|-------|---------|--------|-------|
| **Our Stack (Hostinger)** | 1x 4GB VPS | $8-33 | $96-396 | Best value for small scale |
| AWS Lightsail | 1x 4GB instance | $24 | $288 | Managed, but 3x cost |
| DigitalOcean | 1x 4GB droplet | $24 | $288 | Good developer experience |
| Hetzner Cloud | 1x 4GB (CPX21) | $9 | $108 | Great value, EU-only datacenters |
| Vultr | 1x 4GB instance | $24 | $288 | Global presence |
| Linode (Akamai) | 1x 4GB instance | $24 | $288 | Good support |
| Render | Web service + DB | $25-50 | $300-600 | Fully managed, limited control |
| Railway | Containers | $20-40 | $240-480 | Easy deploy, can get expensive |
| Fly.io | VMs | $15-30 | $180-360 | Good for global edge |
| Heroku | Dyno + Postgres | $50+ | $600+ | Very expensive at scale |

```
Cost Efficiency Ranking (Phase 2 equivalent):
┌──────────────────────────────────────────────────────┐
│  1. Our Stack (Hostinger)  ████████████████ $96-396 │
│  2. Hetzner Cloud          ████████████████████ $108 │
│  3. AWS Lightsail          ██████████████████████████████████████████ $288 │
│  4. DigitalOcean           ██████████████████████████████████████████ $288 │
│  5. Fly.io                 ████████████████████████████████ $180-360 │
│  6. Railway                ████████████████████████████████████ $240-480 │
│  7. Render                 ████████████████████████████████████████ $300-600 │
│  8. Heroku                 ██████████████████████████████████████████████████████████ $600+ │
└──────────────────────────────────────────────────────┘
```

---

## Cost Optimization Strategies

### 1. Prepayment Discounts

| Provider | Term | Discount | Effective Monthly |
|----------|------|----------|-------------------|
| Hostinger VPS | 4 years | ~25% | $2.99 (vs $3.99) |
| Hostinger VPS | 1 year | ~10% | $3.59 (vs $3.99) |
| Cloudflare Registrar | Multi-year | Bulk pricing | Slight savings |

### 2. Oracle Cloud Free Tier (Alternative VPS)

Oracle Cloud Infrastructure offers a genuinely free tier:
- **Always Free:** 4-core ARM + 24GB RAM + 200GB storage
- **Catch:** Requires credit card (for verification), limited regions
- **Good for:** Development, testing, low-traffic production
- **Risk:** Terms can change; not suitable for business-critical

```
Oracle Cloud Free Tier Setup:
┌──────────────────────────────────────────┐
│  4-core ARM Ampere (Always Free)         │
│  24 GB RAM                               │
│  200 GB Block Storage                    │
│  ─────────────────────────────           │
│  TOTAL: $0.00/month  FOREVER             │
│                                          │
│  Caveats:                                │
│  - IPv4 address may incur ~$2-3/month    │
│  - Must keep account active              │
│  - Limited to certain regions            │
└──────────────────────────────────────────┘
```

### 3. Multi-Cloud Strategy (Phase 3)

| Component | Primary | Fallback | Rationale |
|-----------|---------|----------|-----------|
| Application | Hostinger | OCI Free | Cost + redundancy |
| CDN/DNS | Cloudflare | - | Best in class, free |
| Backups | Cloudflare R2 | AWS S3 Glacier | R2 cheaper egress |
| Monitoring | Self-hosted Grafana | UptimeRobot (free) | Double coverage |

### 4. When to Upgrade

| Metric | Current | Upgrade At | Target |
|--------|---------|-----------|--------|
| CPU usage | <50% | >70% sustained | 2x VPS |
| Memory usage | <70% | >85% sustained | 2x VPS |
| Disk usage | <70% | >80% sustained | Add storage |
| Response time (p95) | <200ms | >500ms | 2x VPS or optimize |
| Error rate | <1% | >5% | Debug or scale |
| Concurrent users | <10 | >10 | 2x VPS |

---

## Total Cost of Ownership (5-Year Projection)

| Year | Phase | Monthly | Annual | Cumulative | Users |
|------|-------|---------|--------|-----------|-------|
| 1 | 1 | $5 | $60 | $60 | 1-10 |
| 2 | 1-2 | $10 | $120 | $180 | 10-30 |
| 3 | 2-3 | $20 | $240 | $420 | 30-100 |
| 4 | 3 | $35 | $420 | $840 | 100-300 |
| 5 | 3 | $50 | $600 | $1,440 | 300-500 |

```
5-Year Cost Trajectory:
Year 1   $60    ███
Year 2   $120   ██████
Year 3   $240   ████████████
Year 4   $420   █████████████████████
Year 5   $600   ██████████████████████████████
─────────────────────────────────────────────────
Total   $1,440

Compare to:
- Single AWS EC2 t3.medium ($36/mo): $2,160 over 5 years
- Heroku Standard 2X ($50/mo): $3,000 over 5 years
- Savings vs AWS: $720 (33%)
- Savings vs Heroku: $1,560 (52%)
```

---

## Budget Approval Template

```
TO: Finance / Decision Maker
FROM: Alpha Search DevOps
RE: Infrastructure Budget Request - Phase [1/2/3]

Requested Amount: $[amount]/month ($[amount]/year)
Effective Date: [date]
Duration: [term] months

JUSTIFICATION:
- Current users: [N]
- Expected growth: [N] users/month
- Revenue per user: $[N]
- Infrastructure cost per user: $[N]
- Target margin: [N]%

BREAKDOWN:
| Service | Monthly |
|---------|---------|
| [list]  | [costs] |
| TOTAL   | [sum]   |

ALTERNATIVES CONSIDERED:
1. [Alternative] - $[cost] - Rejected: [reason]
2. [Alternative] - $[cost] - Rejected: [reason]

APPROVAL: _________________  DATE: _______
```

---

*This document is a living document. Update as infrastructure evolves and new pricing becomes available.*