# AnyaDeals Site Redesign Guide

Instructions for an AI agent (or human) to redesign the AnyaDeals frontend while keeping the backend pipeline functioning.

## What This Project Does

AnyaDeals is an automated iHerb coupon pipeline:

1. **Researcher** service scrapes coupon codes from the web
2. **Validator** service tests each code against iHerb checkout (Playwright + proxies)
3. **Orchestrator** commits validated results to GitHub, triggering a site rebuild
4. **Poster** service shares valid codes on Twitter/X and Reddit
5. **Static site** (Next.js) displays the verified codes to visitors

The site is a static export deployed to Cloudflare Pages. It reads JSON data at build time — it makes zero API calls at runtime.

---

## Critical Contract: Do Not Break These

### 1. Data files the pipeline writes to

The backend services write to these files via Docker volume mount (`./site/data:/data`):

| File | Written by | Purpose |
|------|-----------|---------|
| `/home/skaiself/repo/anyadeals/site/data/coupons.json` | Validator | Array of coupon objects |
| `/home/skaiself/repo/anyadeals/site/data/dashboard.json` | Orchestrator | Pipeline status + stats |
| `/home/skaiself/repo/anyadeals/site/data/posts.json` | Poster | Social media post log |
| `/home/skaiself/repo/anyadeals/site/data/research.json` | Researcher | Raw research output |

**DO NOT** rename, move, or restructure these files. The Python services write to `/data/` inside the container, which maps to `./site/data/` on the host.

### 2. Coupon JSON schema

Each coupon in `coupons.json` has this exact shape. Your data layer must handle all these fields:

```typescript
interface Coupon {
  code: string;              // e.g. "WELCOME25"
  type: string;              // e.g. "promo"
  discount: string;          // human-readable, e.g. "25% off first order"
  regions: string[];         // e.g. ["us", "de", "gb"]
  min_cart_value: number;    // minimum cart $ to apply
  status: 'valid' | 'expired' | 'region_limited' | 'invalid' | 'discovered';
  first_seen: string;        // ISO date, e.g. "2026-03-10"
  last_validated: string;    // ISO timestamp
  last_failed: string | null;
  fail_count: number;
  source: string;            // website it came from
  stackable_with_referral: boolean;
  notes: string;
}
```

### 3. Dashboard JSON schema

```typescript
interface Dashboard {
  affiliate_code: string;    // "OFR0296"
  jobs: {
    researcher: DashboardJob;
    validator: DashboardJob;
    poster: DashboardJob;
  };
  stats: {
    total_active_codes: number;
    total_expired_codes: number;
    total_posts_this_week: number;
    last_deploy: string;     // ISO timestamp
  };
}

interface DashboardJob {
  last_run: string;          // ISO timestamp
  status: 'success' | 'failure' | 'unknown';
  next_run: string;          // ISO timestamp
  last_error: string | null;
  [key: string]: unknown;    // extra fields like codes_found, codes_validated, posts_today
}
```

### 4. Git operations path

The orchestrator commits changes from `site/data/` (see `/home/skaiself/repo/anyadeals/services/orchestrator/git_ops.py`). If you move the data directory, the pipeline will silently stop deploying updates.

### 5. Static export

The site must be a static export (`output: 'export'` in Next.js config). No server-side rendering, no API routes, no dynamic routes. The site is hosted on Cloudflare Pages which only serves static files.

### 6. Affiliate integration

Impact.com tracking script is loaded in the root layout. The iHerb referral code is `OFR0296`. Both must be preserved.

---

## Project Structure

```
/home/skaiself/repo/anyadeals/
├── site/                                    # Frontend (YOUR REDESIGN TARGET)
│   ├── app/
│   │   ├── layout.tsx                       # Root layout, fonts, Impact.com script, NavBar, footer
│   │   ├── globals.css                      # Tailwind + brand CSS variables + reduced-motion
│   │   ├── page.tsx                         # Homepage: hero + trending picks + active coupon count
│   │   ├── coupons/iherb/page.tsx           # Coupon stacking guide: steps 1-2, promo table, price comparison
│   │   ├── about/page.tsx                   # About page, how-it-works, affiliate disclosure
│   │   └── dashboard/page.tsx               # Pipeline status dashboard
│   ├── components/
│   │   ├── CouponTicket.tsx                 # Click-to-copy coupon code button
│   │   ├── NavBar.tsx                       # Sticky header, mobile hamburger menu
│   │   ├── RevealOnScroll.tsx               # Intersection Observer fade-up animation
│   │   └── StatusIndicator.tsx              # Traffic-light job status display
│   ├── lib/
│   │   └── data.ts                          # Data loading: getCoupons, getActiveCoupons, getExpiredCoupons, getDashboard
│   ├── data/                                # AUTO-UPDATED by pipeline — DO NOT restructure
│   │   ├── coupons.json
│   │   ├── dashboard.json
│   │   ├── posts.json
│   │   └── research.json
│   ├── public/
│   │   ├── anya-hero.png                    # Hero image (character illustration)
│   │   ├── favicon.ico
│   │   ├── favicon.svg
│   │   └── robots.txt
│   ├── package.json
│   ├── next.config.js                       # Static export, trailing slashes, no image optimization
│   ├── tailwind.config.js                   # Brand colors, fonts, animations
│   ├── tsconfig.json
│   ├── vitest.config.ts                     # Test runner config
│   └── vitest.setup.ts                      # jest-dom matchers
│
├── services/                                # Backend — DO NOT MODIFY
│   ├── orchestrator/
│   │   ├── server.py                        # FastAPI (port 8080)
│   │   ├── scheduler.py                     # APScheduler cron jobs
│   │   ├── git_ops.py                       # Git commit + push to GitHub
│   │   ├── dashboard_writer.py              # Updates dashboard.json
│   │   └── service_client.py                # HTTP client for internal services
│   ├── researcher/
│   │   ├── server.py                        # FastAPI (port 8001)
│   │   ├── scraper.py                       # Web scrapers
│   │   └── claude_parser.py                 # Claude CLI for code extraction
│   ├── validator/
│   │   ├── server.py                        # FastAPI (port 8002)
│   │   ├── main.py                          # Playwright browser validation
│   │   └── httpx_validator.py               # HTTP-based validation with proxies
│   └── poster/
│       ├── server.py                        # FastAPI (port 8003)
│       ├── twitter_poster.py
│       ├── reddit_poster.py
│       └── image_generator.py
│
├── docker-compose.yml                       # All services + volume mounts
└── .env.example                             # Required environment variables
```

---

## Data Layer (Must Preserve or Replicate)

File: `/home/skaiself/repo/anyadeals/site/lib/data.ts`

This is the interface between the pipeline's JSON output and the site's pages. You may rewrite it but must keep the same function signatures and return types:

```typescript
getCoupons(): Coupon[]              // All coupons from coupons.json
getActiveCoupons(): Coupon[]        // status === 'valid' OR 'region_limited'
getExpiredCoupons(): Coupon[]       // status === 'expired'
getDashboard(): Dashboard           // Full dashboard object
```

The functions read from `data/` relative to `process.cwd()`. This works because Next.js static export resolves `process.cwd()` to the site root at build time.

---

## Pages and Their Data Dependencies

### Homepage (`/`)
- **Data**: `getActiveCoupons()` — displays count of active codes
- **Key elements**: Hero section with character image, trending picks grid, active coupon banner

### Coupons Page (`/coupons/iherb`)
- **Data**: `getActiveCoupons()` + `getExpiredCoupons()`
- **Key elements**: Step-by-step stacking guide (rewards code → promo code), coupon table, price comparison, CTA to iHerb with affiliate link

### About Page (`/about`)
- **Data**: None
- **Key elements**: How-it-works 3-step grid, affiliate disclosure, contact links

### Dashboard Page (`/dashboard`)
- **Data**: `getDashboard()`
- **Key elements**: 3 status indicators (researcher/validator/poster), 4 stat cards

---

## Design System (Current)

### Colors (CSS variables in globals.css)
- `--cream: #FAF8F5` — background
- `--ink: #0F0D0B` — primary text
- `--ink-muted: #3D3533` — secondary text
- `--signal: #EA580C` — accent/CTA (orange)
- `--gold: #D97706` — secondary accent

### Typography
- **Editorial**: Libre Bodoni (serif) — headlines, coupon codes, decorative numbers
- **Body**: Public Sans (sans-serif) — paragraphs, labels, UI text
- **Brand**: Tenor Sans — logo/brand mark

### Design Patterns
- Editorial/magazine aesthetic — large serif headlines, tight grids, hover-invert cards
- Borders over shadows — `border border-ink/10` for separation
- Hover-invert pattern — cards flip from light to dark on hover
- Coupon tickets — dashed border with punched-hole pseudo-elements
- Reduced motion support — `@media (prefers-reduced-motion: reduce)` disables animations

### Accessibility
- `aria-label` on all sections and interactive elements
- `aria-hidden="true"` on decorative elements
- Keyboard-navigable (no custom focus traps)
- `prefers-reduced-motion` respected in CSS and JS

---

## Running Tests to Verify Your Changes

### Install dependencies
```bash
cd /home/skaiself/repo/anyadeals/site
npm install
```

### Run all tests
```bash
npm test
```

### Run tests in watch mode
```bash
npm run test:watch
```

### Current test suite (52 tests across 4 files)

| File | Tests | What it verifies |
|------|-------|-----------------|
| `lib/data.test.ts` | 21 | Data loading, filtering, JSON schema contracts |
| `components/RevealOnScroll.test.tsx` | 16 | Scroll animation, SSR visibility, reduced motion |
| `components/CouponTicket.test.tsx` | 7 | Click-to-copy, accessibility, rendering |
| `components/StatusIndicator.test.tsx` | 8 | Status colors, error display, time formatting |

### What the tests guarantee

**Data contract tests** (`lib/data.test.ts`):
- `getCoupons()` returns the full array from `coupons.json`
- `getActiveCoupons()` returns ONLY `valid` and `region_limited` status
- `getExpiredCoupons()` returns ONLY `expired` status
- `getDashboard()` returns the full dashboard with jobs and stats
- The JSON schema matches what the Python services produce
- All 5 status values are handled correctly

**Component behavior tests**:
- `CouponTicket`: copies code to clipboard, shows feedback, has correct aria-label and id
- `StatusIndicator`: renders correct color per status, shows/hides error messages
- `RevealOnScroll`: SSR-visible by default, animates only below fold, respects reduced motion

### After your redesign, all 52 tests must still pass

If you change the data layer, update `lib/data.test.ts` to match.
If you change component APIs, update the corresponding test file.
If you add new components, write tests following the same patterns.

---

## Step-by-Step Redesign Process

1. **Read this document completely**
2. **Run `npm test`** — confirm all 52 tests pass before changing anything
3. **Do not touch** anything in `services/`, `docker-compose.yml`, or `site/data/`
4. **Keep `lib/data.ts`** or replicate its exact interface
5. **Redesign pages and components** as desired
6. **Run `npm test`** after each significant change
7. **Run `npm run build`** — confirm static export succeeds
8. **Verify** the build output in `out/` has all expected pages

### Build verification
```bash
npm run build
ls out/           # Should contain: index.html, coupons/, about/, dashboard/
ls out/coupons/iherb/  # Should contain: index.html
```

---

## What You Can Freely Change

- Visual design, layout, colors, typography, animations
- Component implementations (as long as tests pass or are updated)
- CSS framework (Tailwind, CSS modules, styled-components, etc.)
- Add new pages or components
- Hero image / illustrations
- Copy and content text

## What You Must Not Change

- `site/data/` directory — files are auto-generated by the pipeline
- `lib/data.ts` function signatures and return types (or update tests)
- Static export configuration
- Impact.com affiliate tracking script
- iHerb referral code `OFR0296`
- The fact that data is read at build time from JSON files (not fetched from APIs)
