# Alpha Search Branding Strategy

> **Positioning**: Alpha Search is a research-grade open-source quantitative analysis toolkit — institutional quality, developer-first, openly licensed. It is NOT a hedge fund, trading bot, or investment advisory service.

---

## 1. GitHub Organization Names

Each name evaluated on five criteria (1-10 scale) and scored by weighted average.

| Criterion | Weight |
|-----------|--------|
| Professionalism | 25% |
| Memorability | 20% |
| Hedge-fund-grade feel | 20% |
| Open-source friendly | 20% |
| Availability likelihood | 15% |

---

### Option 1: `alpha-search`

| Criterion | Score |
|-----------|-------|
| Professionalism | 8/10 |
| Memorability | 8/10 |
| Hedge-fund-grade feel | 6/10 |
| Open-source friendly | 9/10 |
| Availability likelihood | 9/10 |

**Weighted Score: 7.85 / 10**

**Pros:**
- Matches the product name exactly (`alpha-search` package on PyPI)
- Descriptive and discoverable — developers searching "quant os" find it
- Clean, hyphenated naming is standard in OSS (e.g., `vscode`, `eslint`, `prettier`)
- Very high availability on GitHub (unused as of evaluation)
- Clear differentiation from commercial offerings

**Cons:**
- Hyphen can sometimes be awkward in URLs or verbal communication
- Slightly generic; doesn't signal "premium" or "institutional" on its own
- May be perceived as more utilitarian than aspirational

**Recommendation:** STRONG CANDIDATE — Best for clarity and developer discovery.

---

### Option 2: `quantos`

| Criterion | Score |
|-----------|-------|
| Professionalism | 7/10 |
| Memorability | 8/10 |
| Hedge-fund-grade feel | 7/10 |
| Open-source friendly | 8/10 |
| Availability likelihood | 6/10 |

**Weighted Score: 7.30 / 10**

**Pros:**
- Single-word, no hyphens — cleaner in branding
- Sounds more like a product/company name ("Quantos")
- Easy to say and spell verbally
- Slightly more premium feel than hyphenated version

**Cons:**
- Risk of confusion with the existing `Quantos` (NCR financial systems brand)
- May already be claimed or squatted on GitHub
- Doesn't map cleanly to the PyPI package (`alpha-search`) — creates a name gap
- Less discoverable — "quantos" doesn't obviously mean "quant OS"

**Recommendation:** REJECT — Name collision risk with existing financial tech brand and mismatch with PyPI package name.

---

### Option 3: `vector-alpha`

| Criterion | Score |
|-----------|-------|
| Professionalism | 8/10 |
| Memorability | 6/10 |
| Hedge-fund-grade feel | 9/10 |
| Open-source friendly | 5/10 |
| Availability likelihood | 7/10 |

**Weighted Score: 7.00 / 10**

**Pros:**
- Distinctive and premium — sounds like a quant research lab or framework
- "Alpha" signals outperformance/research edge in finance
- "Vector" signals computational/mathematical orientation
- Strong hedge-fund-grade feel
- Unique — unlikely to collide with existing brands

**Cons:**
- Disconnects from the "Alpha Search" product name entirely — confusing
- Sounds like a closed-source proprietary fund, not an open-source toolkit
- Less discoverable by developers searching for quant tools
- May set expectations of a commercial hedge fund product
- Verbal ambiguity: "is it VectorAlpha or Vector-Alpha?"

**Recommendation:** REJECT — Too disconnected from the product identity. Better suited for a closed-source trading firm than an OSS toolkit.

---

### Option 4: `openquant-labs`

| Criterion | Score |
|-----------|-------|
| Professionalism | 7/10 |
| Memorability | 7/10 |
| Hedge-fund-grade feel | 5/10 |
| Open-source friendly | 9/10 |
| Availability likelihood | 8/10 |

**Weighted Score: 7.10 / 10**

**Pros:**
- "Open" signals open-source clearly
- "Labs" signals research and experimentation
- Descriptive and discoverable
- Friendly, collaborative feel
- High availability likelihood

**Cons:**
- Feels more like a community/learning platform than a serious toolkit
- Slightly generic — "OpenQuant" is used by several existing projects
- "Labs" may suggest the software itself is experimental/unstable
- Less institutional feel — positions as hobbyist/educational rather than professional
- Longer and more awkward in URLs

**Recommendation:** REJECT — Signals the wrong positioning. Projects in "-labs" orgs are often perceived as experimental. Alpha Search is production-quality tooling.

---

### Option 5: `axiom-alpha`

| Criterion | Score |
|-----------|-------|
| Professionalism | 9/10 |
| Memorability | 7/10 |
| Hedge-fund-grade feel | 9/10 |
| Open-source friendly | 5/10 |
| Availability likelihood | 7/10 |

**Weighted Score: 7.50 / 10**

**Pros:**
- "Axiom" signals foundational, mathematically rigorous tooling
- "Alpha" signals research edge and outperformance
- Extremely premium and institutional feel
- Unique and memorable
- Suggests first principles, provable correctness — aligns with quant research

**Cons:**
- Complete disconnect from "Alpha Search" product name
- Sounds like a proprietary hedge fund or premium SaaS, not open-source
- May intimidate casual contributors
- Less discoverable by the target developer audience
- Could be confused with existing "Axiom" projects (there are several)

**Recommendation:** REJECT — Beautiful name, wrong context. Save for a future proprietary product or fund. Does not serve an OSS toolkit well.

---

## FINAL RECOMMENDATION: `alpha-search`

### Justification

| Factor | Rationale |
|--------|-----------|
| **Name-product alignment** | `alpha-search` is the GitHub org, `alpha-search` is the PyPI package, `alpha-search` is the CLI command. One name everywhere. |
| **Developer discoverability** | Developers searching GitHub or Google for "quant os" will find the org directly. |
| **OSS convention** | Hyphenated org names are standard (eslint, rust-lang, nodejs, etc.). |
| **No collisions** | No existing major brand or GitHub org uses this exact name. |
| **Verbal clarity** | "Quant dash OS" is clear and unambiguous when spoken. |
| **Future-proof** | Can grow into a family of repos under a single coherent namespace. |

The primary purpose of the GitHub org is to host repositories that developers will install and import. The name should match the package they already know. Everything else is secondary.

---

## 2. Repository Naming Convention

Under the `alpha-search` GitHub organization, the following repository structure is recommended:

| Purpose | Repo Name | Rationale |
|---------|-----------|-----------|
| **Main product** | `alpha-search` | Same name as the package. `pip install alpha-search` installs from `alpha-search/alpha-search`. Clean and canonical. |
| **Documentation** | `docs` | Standard OSS convention. Simple, expected. Source for alpha-search.ai/docs. |
| **Examples / Cookbook** | `examples` | Standard naming. Contains Jupyter notebooks, sample strategies, tutorials. |
| **Agent / Skills framework** | `agent-skills` | Descriptive. Houses the AI agent integration layer and skill definitions. |
| **Strategy research lab** | `strategy-lab` | Signals research-oriented, not production trading. Contains backtesting templates and research notebooks. |
| **Community / Discussions** | `community` | (Optional) For GitHub Discussions, Q&A, show-and-tell. Keeps main repo issues clean. |

### Naming Principles Applied

1. **No `alpha-search-` prefix on sub-repos**: Since they're already under the `alpha-search` org, `alpha-search/docs` would be redundant. Use short names.
2. **Descriptive over clever**: `examples` beats `cookbook` or `playground`. `agent-skills` beats `neural-glue`.
3. **Research-only signals**: `strategy-lab` not `live-trading`. `backtest` not `algo-trader`.

### Example GitHub URLs

```
https://github.com/alpha-search/alpha-search      # Main package
https://github.com/alpha-search/docs           # Documentation
https://github.com/alpha-search/examples       # Examples & tutorials
https://github.com/alpha-search/agent-skills   # Agent framework
https://github.com/alpha-search/strategy-lab   # Research templates
```

---

## 3. Package Naming (Already Decided)

| Context | Name | Status |
|---------|------|--------|
| PyPI package name | `alpha-search` | DECIDED |
| Python import name | `alpha_search` | DECIDED |
| CLI command | `alpha-search` | DECIDED |

### Rationale Confirmation

These decisions are correct and should not be changed:

- **PyPI: `alpha-search`** — Hyphenated package names are standard. The package appears as `alpha-search` in `pip install` commands and on PyPI.
- **Import: `alpha_search`** — Python requires underscores in module names. `import alpha_search` is the correct, PEP-8-compliant import.
- **CLI: `alpha-search`** — Matches the package name. Users type `alpha-search --help` after installation. Consistent with tools like `docker-compose`, `aws-cli`, `cookiecutter`.

### Example Usage Flow

```bash
# Install
pip install alpha-search

# Import in Python
import alpha_search
from alpha_search.data import load_prices
from alpha_search.backtest import Backtester

# CLI usage
alpha-search --version
alpha-search data fetch AAPL --start 2023-01-01
alpha-search backtest --strategy momentum --symbols SPY,QQQ
```

---

## 4. Domain Names

### Evaluation Criteria

| Criterion | Weight |
|-----------|--------|
| Professionalism | 30% |
| Memorability | 25% |
| Cost / availability | 20% |
| Brand alignment | 25% |

---

### Option 1: `quantos.ai`

| Attribute | Assessment |
|-----------|------------|
| **Professionalism** | 9/10 — `.ai` signals modern/technical; single word is clean |
| **Memorability** | 9/10 — "quantos dot ai" is punchy and easy to remember |
| **Cost estimate** | $80-200/year (`.ai` domains are premium) |
| **Availability** | High likelihood — check registrar for exact status |
| **Brand alignment** | 9/10 — matches the product identity perfectly |

**Pros:**
- Cleanest, most brandable option
- `.ai` TLD signals artificial intelligence / machine learning alignment
- No hyphen — easier to say and type
- Works well for a research toolkit with AI/agent components
- Premium feel without being pretentious

**Cons:**
- `.ai` renewal is expensive ($80-200/year vs $10-15 for `.io`)
- Slight spelling risk: "quantos" vs "alpha-search" mismatch
- Some developers distrust `.ai` domains as hype-driven

---

### Option 2: `alpha-search.io`

| Attribute | Assessment |
|-----------|------------|
| **Professionalism** | 9/10 — `.io` is the standard OSS/developer TLD |
| **Memorability** | 8/10 — slightly more to say, but clear |
| **Cost estimate** | $30-50/year |
| **Availability** | Very high likelihood |
| **Brand alignment** | 10/10 — exact match to package and org name |

**Pros:**
- `.io` is the de facto standard for open-source developer tools
- Exact name match: `alpha-search` org → `alpha-search.io` domain → `alpha-search` package
- Zero ambiguity — every asset points to the same name
- Moderate cost
- Trusted by developers; feels like a real project

**Cons:**
- `.io` is associated with British Indian Ocean Territory (geopolitical considerations)
- Hyphen in domain is slightly less clean than `quantos.ai`
- Not as "modern" as `.ai` for AI-oriented messaging

---

### Option 3: `quantos.dev`

| Attribute | Assessment |
|-----------|------------|
| **Professionalism** | 8/10 — `.dev` is Google-backed and developer-focused |
| **Memorability** | 9/10 — short and clear |
| **Cost estimate** | $15-20/year |
| **Availability** | Very high likelihood |
| **Brand alignment** | 8/10 — good, but not exact match |

**Pros:**
- `.dev` explicitly signals developer tooling
- Lowest cost option
- Clean, no hyphen
- Good availability
- Strong with developer audience

**Cons:**
- `.dev` can feel generic — many projects use it
- Mismatch between `alpha-search` (product) and `quantos.dev` (domain)
- Less established than `.io` for OSS projects
- Slightly less institutional feel

---

### Option 4: `openquantlabs.ai`

| Attribute | Assessment |
|-----------|------------|
| **Professionalism** | 6/10 — long and compound |
| **Memorability** | 5/10 — too many syllables |
| **Cost estimate** | $80-200/year |
| **Availability** | High likelihood |
| **Brand alignment** | 4/10 — doesn't match product name |

**Pros:**
- Descriptive and open-source-friendly
- High availability

**Cons:**
- Too long for a primary domain
- Does not match the `alpha-search` product identity
- Sounds more like a community/bootcamp than a toolkit
- Three-word compound is hard to say clearly

**Recommendation:** REJECT

---

## FINAL RECOMMENDATION: `alpha-search.io`

### Primary Justification

| Factor | Rationale |
|--------|-----------|
| **Exact name match** | Every asset uses the same identifier: `alpha-search`. Zero cognitive overhead. |
| **OSS convention** | `.io` is the established TLD for developer tools and open-source projects (see: pytest.org exception, but most use .io). |
| **Developer trust** | `.io` domains are expected for serious open-source projects. |
| **Cost-effective** | At ~$30-50/year, reasonable for a long-term project. |
| **Availability** | Very high likelihood of being available. |

### Secondary Domain Strategy

| Domain | Purpose | Priority |
|--------|---------|----------|
| `alpha-search.io` | **PRIMARY** — main website, docs, email | Must-have |
| `quantos.ai` | Redirect to primary; reserve for future AI-focused landing page | Nice-to-have (acquire if budget allows) |
| `quantos.dev` | Redirect to primary | Optional |

### Registrar Recommendation

**Primary:** Porkbun — lowest cost, clean interface, free WHOIS privacy
**Alternative:** Cloudflare Registrar — at-cost pricing, excellent DNS ecosystem integration

---

## 5. Email Structure

Using the primary domain `alpha-search.io`, the following professional email addresses are recommended:

| Address | Purpose | Notes |
|---------|---------|-------|
| `hello@alpha-search.io` | General inquiries, partnerships, press | Primary public-facing address |
| `research@alpha-search.io` | Research collaborations, academic inquiries, methodology questions | Signals research-first positioning |
| `support@alpha-search.io` | Technical support, bug reports, installation issues | Expects to forward to GitHub Issues eventually |
| `team@alpha-search.io` | Team-wide distribution, internal coordination | Group alias |
| `kalyan@alpha-search.io` | Founder direct address | Personal professional email |
| `security@alpha-search.io` | Security disclosures | Standard OSS practice (see security.txt) |

### Email Philosophy

- **Use `hello@` not `info@`**: `info` feels impersonal and dated. `hello` is modern and approachable.
- **Use `research@` not `sales@`**: Reinforces the research-only positioning. No sales, no commercial pitches.
- **No `admin@` or `webmaster@`**: These are legacy and unnecessary for a modern OSS project.
- **All forward to a single inbox initially**: As the project grows, emails can be split across team members.

---

## 6. Logo / Visual Identity Notes

### Design Principles

1. **Institutional, not retail** — Think Two Sigma, not Robinhood. Think academia, not casino.
2. **Serious, not playful** — No gradients, no cartoon mascots, no neon colors.
3. **Modern minimalism** — Clean geometry, generous whitespace, precise typography.
4. **Research-first signaling** — The brand should look like it belongs in a PhD thesis or an institutional white paper.

### Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Primary Dark** | Deep Navy | `#0A1628` | Headers, dark sections, primary brand color |
| **Primary Accent** | Cobalt Blue | `#2563EB` | Links, buttons, highlights |
| **Secondary Accent** | Slate | `#475569` | Subheadings, secondary text |
| **Background Light** | Off-White | `#FAFBFC` | Page backgrounds |
| **Background Dark** | Charcoal | `#1E293B` | Code blocks, dark mode |
| **Text Primary** | Near-Black | `#0F172A` | Body text |
| **Text Muted** | Cool Gray | `#94A3B8` | Captions, metadata |
| **Success** | Muted Green | `#059669` | Positive indicators (only if needed) |
| **Warning** | Muted Amber | `#D97706` | Alerts (only if needed) |

### What NOT to Use

- No bright/neon greens (signals retail/crypto)
- No gradients in the logo (signals startup-generic)
- No red/green as primary colors (signals trading app, not research)
- No purple or orange as accents (signals consumer/entertainment)

### Typography Recommendations

| Context | Font | Weight | Fallback |
|---------|------|--------|----------|
| **Headings / Display** | Inter | 600-700 | system-ui, sans-serif |
| **Body Text** | Inter | 400-500 | system-ui, sans-serif |
| **Code / Monospace** | JetBrains Mono | 400 | Menlo, Monaco, monospace |
| **Data / Tables** | JetBrains Mono | 400 | monospace |

**Rationale:**
- **Inter** is the standard for modern developer-facing products. Clean, geometric, excellent at all sizes, neutral personality.
- **JetBrains Mono** has ligatures and is designed for code. Using it for data tables signals technical precision.
- Both are free, open-source fonts (Google Fonts / JetBrains).

### Logo Concept Direction

The logo should communicate:

1. **Precision** — Sharp edges, exact geometry
2. **Computation** — Subtle nod to data structures or mathematical notation
3. **Openness** — Clean negative space, nothing hidden

**Concept directions to explore with a designer:**

- **Monogram mark**: Interlocking "Q" and "O" or a stylized "Q" with a mathematical element (sigma, integral, or bracket)
- **Geometric abstraction**: A grid or matrix pattern suggesting data/quantitative analysis
- **Typographic logo**: "Alpha Search" in a carefully set wordmark, no symbol needed — institutional trust through typography alone

**Logo usage rules:**
- Single-color reproduction must work (for print, stickers, monochrome)
- Must be legible at 32x32px (favicon, GitHub org avatar)
- Horizontal and vertical lockups needed
- Clear space: minimum 1x logo height on all sides

### GitHub Org Avatar

- 500x500px recommended (GitHub displays at various sizes)
- Use the primary mark on a solid `#0A1628` background
- Must be recognizable at 40x40px (commit avatars, issue comments)
- Consider a simplified version of the full logo for the avatar

### Favicon Strategy

| Size | Purpose |
|------|---------|
| 16x16 | Browser tab, legacy |
| 32x32 | Browser tab, standard |
| 180x180 | Apple touch icon |
| 192x192 | Android/PWA |
| 512x512 | PWA splash |

Use the primary mark or a simplified "Q" monogram.

---

## 7. Brand Voice & Tone

### Voice Characteristics

| Trait | Example |
|-------|---------|
| **Precise** | "The backtester evaluates 2.3M rows in 340ms." Not "It's super fast!" |
| **Humble** | "This approach builds on work by..." Not "We revolutionized..." |
| **Research-oriented** | "The strategy exhibits a Sharpe ratio of 1.4 under these assumptions." |
| **Developer-respectful** | Clear API docs, no condescension, no marketing fluff |
| **Transparent** | Open about limitations, assumptions, and methodology |

### Tone by Context

| Context | Tone |
|---------|------|
| Documentation | Neutral, instructive, comprehensive |
| GitHub Issues | Helpful, direct, technical |
| Blog / Research | Academic, measured, evidence-based |
| Social / Community | Friendly but professional |
| Error messages | Clear, actionable, never blaming |

### What to Avoid

- No "moon" language, no "rocket" emojis, no "to the moon"
- No financial advice framing — always "for research purposes only"
- No claims of profitability or guaranteed returns
- No comparison to "beating the market" — focus on methodology, not outcomes
- No urgency/scarcity tactics — this is infrastructure, not a product launch

---

## 8. Competitive Brand Positioning

| Product | Positioning | Alpha Search Differentiation |
|---------|-------------|------------------------|
| **QuantConnect** | Commercial platform, cloud backtesting | We are open-source, local-first, research-focused |
| **Zipline (Quantopian)** | Discontinued, was also platform-focused | We are actively maintained, modern Python, research-oriented |
| **Backtrader** | Open-source, but single-maintainer, aging | We are team-backed, modern architecture, agent-native |
| **VectorBT** | Open-source, performance-focused | We complement (can wrap) VectorBT; focus on research workflows |
| **Tradologics** | Commercial, no-code | We are code-first, open-source, developer-native |

**Key message**: Alpha Search is the open-source quantitative research toolkit that institutions and serious researchers use to build, test, and document investment strategies — with AI-native workflow integration.

---

*Document version: 1.0*
*Last updated: 2025-01-15*
*Next review: On domain purchase completion*
