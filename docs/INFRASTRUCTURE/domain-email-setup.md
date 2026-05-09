# Alpha Search Domain & Email Setup Guide

> Complete step-by-step guide to set up `alpha-search.io` with professional email forwarding for under $2/month.
> All services used have free tiers. Total ongoing cost: approximately $1-2/month (domain renewal only).

---

## Architecture Overview

```
User sends email to hello@alpha-search.io
         |
         v
[Cloudflare Email Routing] (FREE)
         |
         v
[ImprovMX] (FREE tier)
         |
         v
+----------------------------+
| Forward to:                |
| your-email@example.com  |
+----------------------------+
```

### Why This Architecture?

| Service | Role | Why Chosen |
|---------|------|------------|
| **Porkbun** | Domain registrar | Lowest prices, free WHOIS privacy, clean UX |
| **Cloudflare** | DNS + Email Routing | Free, fast, secure, excellent ecosystem |
| **ImprovMX** | Email forwarding | Free tier: 1 domain, unlimited aliases, reliable delivery |

### Alternative Architecture (Simpler)

If you want to minimize services, you can use **Cloudflare Email Routing alone** (no ImprovMX needed):

```
User sends email to hello@alpha-search.io
         |
         v
[Cloudflare Email Routing] (FREE)
         |
         v
+----------------------------+
| Forward to:                |
| your-email@example.com  |
+----------------------------+
```

This works perfectly for receiving. However, ImprovMX adds the ability to **send** emails from your domain (via SMTP), which is valuable for professional communication. The recommended hybrid setup below uses both.

---

## 1. Domain Purchase

### Step 1: Check Availability

Visit these registrars to check `alpha-search.io` availability:

```bash
# Check availability via command line (optional)
curl -s "https://api.porkbun.com/api/json/v3/ping"
```

Or simply visit:
- https://porkbun.com (recommended — lowest cost)
- https://namecheap.com
- https://cloudflare.com/registrar

### Step 2: Purchase at Porkbun (Recommended)

1. Go to **https://porkbun.com**
2. Search for `alpha-search.io`
3. If available, add to cart
4. Create account (if new user):
   - Use a strong, unique password
   - Enable 2FA immediately (Settings → Security)
5. Complete purchase:
   - 1-year registration: ~$30-45
   - Optional: Add email forwarding ($12/year — **skip this**, we'll use free alternatives)
   - Optional: Add web hosting (**skip this**, we'll use GitHub Pages or Cloudflare Pages)
6. Confirm ownership in your Porkbun dashboard

### Porkbun Cost Breakdown

| Item | Cost |
|------|------|
| `alpha-search.io` registration (1 year) | ~$30-45 |
| WHOIS privacy | FREE (included) |
| **Total first year** | **~$30-45** |
| **Renewal (annual)** | **~$30-45** |

> Note: `.io` domains are more expensive than `.com`. If budget is tight, consider `quantos.dev` at ~$12/year as the primary domain instead.

### Step 3: Secure Your Account

After purchase, immediately:
1. Enable 2FA on Porkbun (TOTP app like Authy or Aegis)
2. Save recovery codes offline
3. Verify the domain appears in your dashboard

---

## 2. DNS Setup with Cloudflare

### Step 1: Create Cloudflare Account

1. Go to **https://dash.cloudflare.com/sign-up**
2. Sign up with `your-email@example.com` or a dedicated project email
3. Verify email address
4. Enable 2FA on Cloudflare (critical)

### Step 2: Add Site to Cloudflare

1. In Cloudflare dashboard, click **"Add a Site"**
2. Enter: `alpha-search.io`
3. Select plan: **Free** (sufficient for all needs)
4. Click **Continue**
5. Cloudflare will scan for existing DNS records (there won't be any yet)
6. Click **Continue** to proceed to nameserver setup

### Step 3: Change Nameservers at Porkbun

Cloudflare will provide two nameservers like:
```
adaline.ns.cloudflare.com
kellen.ns.cloudflare.com
```
(Your specific nameservers will be different — use what Cloudflare gives you.)

At Porkbun:
1. Go to **Domain Management** → `alpha-search.io`
2. Click **Authoritative Nameservers**
3. Delete existing nameservers
4. Add the two Cloudflare nameservers
5. Save changes
6. Wait 5-30 minutes for propagation

Back in Cloudflare:
1. Click **"Done, check nameservers"**
2. Wait for Cloudflare to detect the change (can take up to 24 hours, usually 5-30 minutes)
3. You'll receive an email when active

### Step 4: Configure DNS Records

Once Cloudflare shows "Active", add these DNS records:

#### For GitHub Pages (Documentation Site)

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|-------------|-----|
| A | `@` | `185.199.108.153` | Proxied | Auto |
| A | `@` | `185.199.109.153` | Proxied | Auto |
| A | `@` | `185.199.110.153` | Proxied | Auto |
| A | `@` | `185.199.111.153` | Proxied | Auto |
| CNAME | `www` | `alpha-search.github.io` | Proxied | Auto |

These are GitHub's Pages IPs. They route `alpha-search.io` to your GitHub Pages site.

#### For API/Backend (Future)

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|-------------|-----|
| A | `api` | `[your-server-ip]` | Proxied | Auto |

(Leave unset until you have a backend server.)

#### For Email (MX Records — via ImprovMX)

Add these MX records for ImprovMX:

| Type | Name | Content | Priority | Proxy Status |
|------|------|---------|----------|-------------|
| MX | `@` | `mx1.improvmx.com` | 10 | DNS only |
| MX | `@` | `mx2.improvmx.com` | 20 | DNS only |

> **Important**: MX records must be set to **DNS only** (gray cloud), not Proxied (orange cloud).

### Step 5: Enable Security Features

In Cloudflare dashboard for `alpha-search.io`:

1. **SSL/TLS** → Set to **Full (strict)**
2. **Always Use HTTPS**: ON
3. **Automatic HTTPS Rewrites**: ON
4. **DNSSEC**: Enable (go to DNS → DNSSEC → Enable DNSSEC)
5. **Security Level**: Medium (default)
6. **Bot Fight Mode**: ON (free tier)

---

## 3. Cloudflare Email Routing (FREE)

Cloudflare Email Routing provides a simple, free way to receive emails at custom addresses.

### Step 1: Enable Email Routing

1. In Cloudflare dashboard, go to **Email** → **Email Routing**
2. Click **"Get started"**
3. Choose **"Route to a email address you own"**
4. Enter your destination email: `your-email@example.com`
5. Verify ownership:
   - Cloudflare sends a verification code to `your-email@example.com`
   - Check Gmail, click the verification link
   - Return to Cloudflare, click **"Refresh"**
6. Click **"Save"**

### Step 2: Create Custom Addresses

In Cloudflare Email Routing, add these routes:

| Custom Address | Action | Destination |
|----------------|--------|-------------|
| `hello@alpha-search.io` | Send to | `your-email@example.com` |
| `research@alpha-search.io` | Send to | `your-email@example.com` |
| `support@alpha-search.io` | Send to | `your-email@example.com` |
| `team@alpha-search.io` | Send to | `your-email@example.com` |
| `kalyan@alpha-search.io` | Send to | `your-email@example.com` |
| `security@alpha-search.io` | Send to | `your-email@example.com` |

### Step 3: Configure Catch-All

1. In Email Routing settings, enable **Catch-all address**
2. Set to forward to: `your-email@example.com`
3. This ensures ANY email sent to `@alpha-search.io` reaches you, even if you forget to configure a specific alias

### Step 4: Disable ImprovMX (if using Cloudflare-only)

If you're using **only** Cloudflare Email Routing (no ImprovMX):

1. Skip the ImprovMX section below
2. Delete any MX records pointing to `improvmx.com`
3. Add Cloudflare's MX records:

| Type | Name | Content | Priority |
|------|------|---------|----------|
| MX | `@` | `route1.mx.cloudflare.net` | 19 |
| MX | `@` | `route2.mx.cloudflare.net` | 43 |
| MX | `@` | `route3.mx.cloudflare.net` | 95 |

These are automatically managed by Cloudflare when you enable Email Routing. You typically don't need to add them manually — Cloudflare handles it.

---

## 4. ImprovMX Setup (FREE Tier)

ImprovMX adds professional email **sending** capability (via SMTP) in addition to forwarding.

### Why Both Cloudflare AND ImprovMX?

| Feature | Cloudflare Email Routing | ImprovMX |
|---------|--------------------------|----------|
| Receive emails | YES (free) | YES (free) |
| Forward to Gmail | YES | YES |
| Send emails from your domain | NO | YES (via SMTP) |
| SPF/DKIM/DMARC support | Basic | Full |
| Reliability | Excellent | Excellent |

Using **ImprovMX for MX records** + **Cloudflare Email Routing as backup** gives you the best of both worlds.

### Step 1: Sign Up at ImprovMX

1. Go to **https://improvmx.com**
2. Click **"Get Started"** (free plan)
3. Sign up with `your-email@example.com`
4. Verify your email
5. Enable 2FA on your account

### Step 2: Add Your Domain

1. In ImprovMX dashboard, click **"Add Domain"**
2. Enter: `alpha-search.io`
3. Click **"Add Domain"**

ImprovMX will provide MX records:
```
mx1.improvmx.com (priority 10)
mx2.improvmx.com (priority 20)
```

### Step 3: Add MX Records in Cloudflare DNS

(If not already added in Step 4 of DNS Setup)

1. In Cloudflare dashboard → DNS
2. Add:

| Type | Name | Target | Priority | Proxy Status |
|------|------|--------|----------|-------------|
| MX | `@` | `mx1.improvmx.com` | 10 | DNS only |
| MX | `@` | `mx2.improvmx.com` | 20 | DNS only |

3. **Important**: Set Proxy Status to **DNS only** (gray cloud) for MX records

### Step 4: Create Email Aliases

In ImprovMX dashboard for `alpha-search.io`:

| Alias | Forward To |
|-------|------------|
| `hello` | `your-email@example.com` |
| `research` | `your-email@example.com` |
| `support` | `your-email@example.com` |
| `team` | `your-email@example.com` |
| `kalyan` | `your-email@example.com` |
| `security` | `your-email@example.com` |
| `*` (catch-all) | `your-email@example.com` |

The catch-all (`*`) ensures any email to `@alpha-search.io` is forwarded.

### Step 5: Verify DNS

ImprovMX will check your MX records. Wait 5-30 minutes, then click **"Verify DNS"**.

Once verified, email forwarding is active.

---

## 5. Sending Emails from Your Domain (via ImprovMX SMTP)

To **send** emails that appear to come from `hello@alpha-search.io`:

### Step 1: Get SMTP Credentials

1. In ImprovMX dashboard → `alpha-search.io` → **SMTP / Credentials**
2. Click **"Generate new credential"**
3. Name it: `primary-sender`
4. Save the username and password securely (1Password/Bitwarden)

### Step 2: Configure Gmail to Send As

1. Open Gmail → **Settings** (gear icon) → **See all settings**
2. Go to **Accounts and Import** tab
3. Under **"Send mail as"**, click **"Add another email address"**
4. Fill in:
   - Name: `Alpha Search Team`
   - Email: `hello@alpha-search.io`
   - Treat as alias: **Checked**
5. Click **Next Step**
6. Configure SMTP:
   - SMTP Server: `smtp.improvmx.com`
   - Port: `587`
   - Username: `[your ImprovMX SMTP username]`
   - Password: `[your ImprovMX SMTP password]`
   - Secured connection: **TLS**
7. Click **Add Account**
8. Gmail sends a verification code to `hello@alpha-search.io`
9. The code forwards to `your-email@example.com` via ImprovMX
10. Enter the verification code in Gmail
11. Done — you can now send as `hello@alpha-search.io`

Repeat steps 2-11 for additional send-as addresses (`research@`, `support@`, etc.)

---

## 6. SPF, DKIM, and DMARC Setup

These records ensure your emails don't end up in spam folders.

### SPF Record (Sender Policy Framework)

Add this TXT record in Cloudflare DNS:

| Type | Name | Content |
|------|------|---------|
| TXT | `@` | `v=spf1 include:spf.improvmx.com include:_spf.google.com ~all` |

**What this does:**
- Authorizes ImprovMX servers to send email for your domain
- Also authorizes Gmail (for your forwarded replies)
- `~all` means soft-fail for unauthorized senders (recommended for initial setup)

> After 30 days of stable operation, you can change `~all` to `-all` for hard-fail (stricter).

### DKIM (DomainKeys Identified Mail)

**Cloudflare Email Routing DKIM** (if using Cloudflare):

Cloudflare automatically manages DKIM when Email Routing is enabled. No manual configuration needed.

**ImprovMX DKIM** (if using ImprovMX):

1. In ImprovMX dashboard → `alpha-search.io` → **DNS Records**
2. Look for DKIM records
3. Add the provided CNAME records to Cloudflare DNS
4. Wait for propagation
5. Verify in ImprovMX dashboard

### DMARC Record

Add this TXT record in Cloudflare DNS:

| Type | Name | Content |
|------|------|---------|
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:your-email@example.com; ruf=mailto:your-email@example.com; fo=1; adkim=r; aspf=r;` |

**What this does:**
- `p=none`: Monitor only (no rejection) — safe for initial setup
- `rua=`: Aggregate report destination
- `ruf=`: Forensic (detailed) report destination
- `adkim=r; aspf=r`: Relaxed alignment

After 30 days of stable email operation, you can strengthen:
```
v=DMARC1; p=quarantine; rua=mailto:your-email@example.com; adkim=r; aspf=r;
```

Or even stricter:
```
v=DMARC1; p=reject; rua=mailto:your-email@example.com; adkim=s; aspf=s;
```

### Complete DNS Record Summary

Your final Cloudflare DNS records should look like this:

```
; A Records (GitHub Pages)
A     @      185.199.108.153    Proxied
A     @      185.199.109.153    Proxied
A     @      185.199.110.153    Proxied
A     @      185.199.111.153    Proxied

; CNAME Records
CNAME www    alpha-search.github.io  Proxied

; MX Records (ImprovMX)
MX    @      mx1.improvmx.com   10    DNS only
MX    @      mx2.improvmx.com   20    DNS only

; SPF
TXT   @      "v=spf1 include:spf.improvmx.com include:_spf.google.com ~all"

; DMARC
TXT   _dmarc "v=DMARC1; p=none; rua=mailto:your-email@example.com; ruf=mailto:your-email@example.com; fo=1"

; DKIM (if provided by ImprovMX)
CNAME [selector]._domainkey [value from ImprovMX]  DNS only
```

---

## 7. Security Checklist

### Cloudflare Security Settings

| Setting | Value | Location |
|---------|-------|----------|
| SSL/TLS mode | Full (strict) | SSL/TLS → Overview |
| Always Use HTTPS | ON | SSL/TLS → Edge Certificates |
| Automatic HTTPS Rewrites | ON | SSL/TLS → Edge Certificates |
| HSTS | Enable | SSL/TLS → Edge Certificates |
| Minimum TLS Version | 1.2 | SSL/TLS → Edge Certificates |
| DNSSEC | Enabled | DNS → DNSSEC |
| Security Level | Medium | Security → Settings |
| Bot Fight Mode | ON | Security → Bots |
| Challenge Passage | 30 minutes | Security → Settings |

### DNSSEC Setup

1. In Cloudflare dashboard → **DNS** → **DNSSEC**
2. Click **"Enable DNSSEC"**
3. Cloudflare will provide DS record information
4. Copy the DS record details
5. In Porkbun → Domain Management → `alpha-search.io` → **DNSSEC**
6. Add the DS record from Cloudflare
7. Save
8. Return to Cloudflare, click **"Confirm"**
9. Wait for propagation (up to 24 hours)

### Account Security

| Account | Action |
|---------|--------|
| Porkbun | 2FA enabled, recovery codes saved |
| Cloudflare | 2FA enabled, API tokens restricted |
| ImprovMX | 2FA enabled |
| Gmail | 2FA enabled, app password for SMTP |

---

## 8. Testing Everything

### Test Email Flow

Send test emails to each address and verify they arrive at `your-email@example.com`:

```bash
# Using a different email account, send to:
hello@alpha-search.io
research@alpha-search.io
support@alpha-search.io
kalyan@alpha-search.io
test123@alpha-search.io    # Tests catch-all
```

Check:
1. [ ] Email arrives in Gmail inbox (not spam)
2. [ ] Reply-to address shows correctly
3. [ ] No SPF/DKIM warnings in Gmail headers

### Test Website

```bash
# Verify DNS propagation
dig alpha-search.io A
dig alpha-search.io MX
dig alpha-search.io TXT

# Check website (after GitHub Pages setup)
curl -I https://alpha-search.io
```

### Test Email Sending

1. Compose email in Gmail
2. Click **From** dropdown
3. Select `hello@alpha-search.io`
4. Send to a test address
5. Verify sender shows `hello@alpha-search.io`
6. Check SPF/DKIM pass in headers

---

## 9. Monthly Cost Summary

| Service | Monthly Cost | Annual Cost | Notes |
|---------|-------------|-------------|-------|
| Domain (`alpha-search.io`) | ~$3.00 | ~$35 | Porkbun — varies by market |
| Cloudflare DNS + Proxy | FREE | FREE | Free plan |
| Cloudflare Email Routing | FREE | FREE | Free plan |
| ImprovMX | FREE | FREE | Free tier: 1 domain |
| DNSSEC | FREE | FREE | Included |
| SSL/TLS Certificate | FREE | FREE | Cloudflare auto-provides |
| **TOTAL** | **~$3/month** | **~$35/year** | |

### Cost Comparison: Alternatives

| Provider | Monthly Cost | Notes |
|----------|-------------|-------|
| **This setup** (Cloudflare + ImprovMX) | ~$3 | Recommended |
| Google Workspace | $6/user | Overkill for 1 person |
| Microsoft 365 | $6/user | Overkill for 1 person |
| Zoho Mail (free tier) | FREE | Requires Zoho branding, 5GB limit |
| Fastmail | $3/user | Paid only, no free tier |

---

## 10. Troubleshooting

### Emails Going to Spam

1. Check SPF record is correct: `dig alpha-search.io TXT`
2. Verify DKIM is configured
3. Check DMARC policy isn't too strict (`p=none` for monitoring)
4. Send test via https://www.mail-tester.com
5. Aim for score 8/10+

### MX Record Conflicts

If using both Cloudflare Email Routing and ImprovMX:
- **Do NOT** mix their MX records
- Use ONE set: either ImprovMX OR Cloudflare Email Routing MX records
- Recommendation: Use ImprovMX MX records (more features)
- Disable Cloudflare Email Routing if using ImprovMX exclusively

### DNS Not Propagating

1. Check at https://dnschecker.org
2. Wait up to 48 hours (usually 5-30 minutes)
3. Verify nameservers at Porkbun are correct
4. Clear local DNS cache: `sudo killall -HUP mDNSResponder` (macOS)

### ImprovMX Verification Failing

1. Double-check MX records are set to **DNS only** (gray cloud, NOT orange)
2. Verify no conflicting MX records exist
3. Wait 30 minutes and retry
4. Check ImprovMX status page: https://status.improvmx.com

---

## 11. Future Upgrades

When the project grows, consider these upgrades:

| Upgrade | When | Cost |
|---------|------|------|
| Google Workspace | Team of 3+ people | $6/user/month |
| Custom SMTP server | High email volume | $5-20/month |
| Additional domains (`quantos.ai`) | Budget allows | ~$10/year |
| Cloudflare Pro | Need advanced analytics | $20/month |

---

*Document version: 1.0*
*Last updated: 2025-01-15*
*Next review: After domain purchase and setup completion*
