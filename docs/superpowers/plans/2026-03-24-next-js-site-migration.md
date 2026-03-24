# Next.js Site Migration — Replace Astro with anyadaily Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the anyadeals Astro frontend with the anyadaily Next.js codebase, wired into the existing automated data pipeline (coupons.json, dashboard.json), deployed as a static export to Cloudflare Pages.

**Architecture:** Copy the anyadaily Next.js app into `anyadeals/site/`, enable static export (`output: 'export'`), replace hardcoded data with `fs.readFileSync` from `data/` directory (more robust than static imports for CI/CD), add missing pages (about, dashboard). Services remain untouched — they write JSON to the shared `/data` volume, git push triggers Cloudflare rebuild. Data files (`site/data/*.json`) MUST be committed to git (not gitignored) — the orchestrator's git-push triggers Cloudflare Pages rebuild.

**Important notes:**
- `site/data/*.json` are seed files committed to git. Pipeline services overwrite them, then orchestrator pushes to trigger rebuild.
- `site/public/` is NOT deleted during migration — existing favicons/robots.txt are intentionally preserved.
- anyadaily's `next.config.js` is NOT copied — a new one is created with `output: 'export'` added.
- Dead links to `/wellness`, `/tech`, `/deals` from anyadaily are removed during rebranding (Task 3-4).

**Tech Stack:** Next.js 15 + React 19 + Tailwind CSS 3 + TypeScript. Static export to Cloudflare Pages.

---

## File Structure

### Files to DELETE (entire Astro site)
- `site/src/` — All Astro source files
- `site/astro.config.mjs`
- `site/tsconfig.json` (replaced by Next.js tsconfig)
- `site/package.json` (replaced by Next.js package.json)
- `site/package-lock.json`

### Files to COPY from anyadaily (design source of truth)
- `app/layout.tsx` → `site/app/layout.tsx`
- `app/page.tsx` → `site/app/page.tsx`
- `app/globals.css` → `site/app/globals.css`
- `app/coupons/iherb/page.tsx` → `site/app/coupons/iherb/page.tsx`
- `components/NavBar.tsx` → `site/components/NavBar.tsx`
- `components/CouponTicket.tsx` → `site/components/CouponTicket.tsx`
- `components/RevealOnScroll.tsx` → `site/components/RevealOnScroll.tsx`
- `public/anya-hero.png` → `site/public/anya-hero.png`
- `tailwind.config.js` → `site/tailwind.config.js`
- `postcss.config.js` → `site/postcss.config.js`
- `tsconfig.json` → `site/tsconfig.json`

### Files to CREATE (new)
- `site/next.config.js` — With `output: 'export'` for static deploy (NOT copied from anyadaily — new file)
- `site/package.json` — Based on anyadaily, renamed to "anyadeals"
- `site/data/` — Pipeline JSON files (committed to git, overwritten by services)
- `site/app/about/page.tsx` — About page with affiliate disclosure section (editorial style)
- `site/app/dashboard/page.tsx` — Pipeline dashboard
- `site/components/StatusIndicator.tsx` — Dashboard job status card
- `site/lib/data.ts` — Typed data loading helpers using `fs.readFileSync` (server-only)

### Files to MODIFY
- `site/app/layout.tsx` — Rebrand "Anya Daily" → "AnyaDeals", update nav links
- `site/app/page.tsx` — Import coupon count from data, keep design
- `site/app/coupons/iherb/page.tsx` — Replace hardcoded PROMO_CODES with coupons.json import
- `site/components/NavBar.tsx` — Update nav links and brand name
- `docker-compose.yml` — Change volume mount from `./site/src/data:/data` to `./site/data:/data`

---

## Task 1: Scaffold Next.js site from anyadaily

**Files:**
- Delete: `site/src/`, `site/astro.config.mjs`, `site/package.json`, `site/package-lock.json`, `site/tsconfig.json`
- Copy: All anyadaily source files into `site/`
- Create: `site/next.config.js`, `site/package.json`

- [ ] **Step 1: Remove Astro site source (keep data/)**

```bash
cd /home/skaiself/repo/anyadeals
# Backup data files first
cp -r site/src/data /tmp/anyadeals-data-backup
# Remove Astro source
rm -rf site/src site/astro.config.mjs site/tsconfig.json site/package.json site/package-lock.json site/node_modules site/dist site/.astro
```

- [ ] **Step 2: Copy anyadaily source into site/**

```bash
cd /home/skaiself/repo/anyadeals
# Copy app, components, public, configs
cp -r /home/skaiself/repo/anyadaily/app site/
cp -r /home/skaiself/repo/anyadaily/components site/
cp -r /home/skaiself/repo/anyadaily/public site/
cp /home/skaiself/repo/anyadaily/tailwind.config.js site/
cp /home/skaiself/repo/anyadaily/postcss.config.js site/
cp /home/skaiself/repo/anyadaily/tsconfig.json site/
```

- [ ] **Step 3: Create next.config.js with static export**

```javascript
// site/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
```

- [ ] **Step 4: Create package.json**

```json
{
  "name": "anyadeals",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.2.3",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.31",
    "tailwindcss": "^3.4.17",
    "typescript": "^5"
  }
}
```

- [ ] **Step 5: Restore data directory and install deps**

```bash
cd /home/skaiself/repo/anyadeals
mkdir -p site/data
cp /tmp/anyadeals-data-backup/* site/data/
cd site && npm install
```

- [ ] **Step 6: Verify build works (unmodified anyadaily)**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
```
Expected: Build succeeds, `out/` directory created with static HTML.

- [ ] **Step 7: Commit scaffold**

```bash
git add -A site/
git commit -m "feat: replace Astro site with Next.js (anyadaily design)"
```

---

## Task 2: Create data loading helpers

**Files:**
- Create: `site/lib/data.ts`

- [ ] **Step 1: Create typed data loading module**

```typescript
// site/lib/data.ts
import { readFileSync } from 'fs';
import { join } from 'path';

export interface Coupon {
  code: string;
  type: string;
  discount: string;
  regions: string[];
  min_cart_value: number;
  status: 'valid' | 'expired' | 'region_limited' | 'invalid' | 'discovered';
  first_seen: string;
  last_validated: string;
  last_failed: string | null;
  fail_count: number;
  source: string;
  stackable_with_referral: boolean;
  notes: string;
}

export interface DashboardJob {
  last_run: string;
  status: 'success' | 'failure' | 'unknown';
  next_run: string;
  last_error: string | null;
  [key: string]: unknown;
}

export interface Dashboard {
  affiliate_code: string;
  jobs: {
    researcher: DashboardJob;
    validator: DashboardJob;
    poster: DashboardJob;
  };
  stats: {
    total_active_codes: number;
    total_expired_codes: number;
    total_posts_this_week: number;
    last_deploy: string;
  };
}

function readJson<T>(filename: string): T {
  const raw = readFileSync(join(process.cwd(), 'data', filename), 'utf-8');
  return JSON.parse(raw) as T;
}

export function getCoupons(): Coupon[] {
  return readJson<Coupon[]>('coupons.json');
}

export function getActiveCoupons(): Coupon[] {
  return getCoupons().filter(c => c.status === 'valid' || c.status === 'region_limited');
}

export function getExpiredCoupons(): Coupon[] {
  return getCoupons().filter(c => c.status === 'expired');
}

export function getDashboard(): Dashboard {
  return readJson<Dashboard>('dashboard.json');
}
```

Note: `fs.readFileSync` works in Next.js server components and at build time for static export. This avoids compile-time JSON module resolution issues in CI/CD.

- [ ] **Step 3: Verify build still passes**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add site/lib/ site/tsconfig.json
git commit -m "feat: add typed data loading helpers for pipeline JSON"
```

---

## Task 3: Rebrand layout and navbar

**Files:**
- Modify: `site/app/layout.tsx`
- Modify: `site/components/NavBar.tsx`

- [ ] **Step 1: Update layout.tsx**

Changes:
- Title: "Anya Daily" → "AnyaDeals"
- Description: Update to anyadeals tagline
- Brand references in footer

- [ ] **Step 2: Update NavBar.tsx**

Changes:
- Brand text: "Anya Daily" → "AnyaDeals"
- Nav links: `[Home, Coupons (/coupons/iherb), About (/about)]` (remove Wellness/Tech/Deals placeholder links)

- [ ] **Step 3: Update layout footer**

Add footer with same structure as anyadaily layout but with AnyaDeals branding. Links: Home (`/`), Coupons (`/coupons/iherb`), About (`/about`), Affiliate Disclosure (`/about#disclosure`). Note: affiliate disclosure is a section within the About page, not a separate page.

- [ ] **Step 4: Verify build and visual check**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build && npx serve out -p 4322
```
Check: localhost:4322 shows "AnyaDeals" branding, correct nav links.

- [ ] **Step 5: Commit**

```bash
git add site/app/layout.tsx site/components/NavBar.tsx
git commit -m "feat: rebrand layout and navbar to AnyaDeals"
```

---

## Task 4: Wire homepage to live coupon data

**Files:**
- Modify: `site/app/page.tsx`

- [ ] **Step 1: Update homepage to import coupon count and fix dead links**

Add at top of page.tsx:
```typescript
import { getActiveCoupons } from '@/lib/data';
```

Update the `TRENDING_CARDS` array:
- Keep the iHerb card (href: `/coupons/iherb`) — this page exists
- Update the other 3 cards' `href` values to point to `/about` or `#deals` (the `/wellness`, `/tech`, `/deals` pages don't exist and won't be created)
- Update "Browse All Deals" hero CTA href from `/deals` to `/coupons/iherb`

- [ ] **Step 2: Add active coupons banner section**

Between hero and trending picks, add:
```tsx
const activeCoupons = getActiveCoupons();
// ...
<div className="max-w-7xl mx-auto px-6 md:px-12 py-8">
  <Link href="/coupons/iherb" className="block bg-signal/5 border border-signal/20 p-4 text-center text-sm text-ink hover:bg-signal/10 transition-colors">
    <span className="font-semibold text-signal">{activeCoupons.length} verified iHerb codes active</span>
    {' '}— Stack them now →
  </Link>
</div>
```

- [ ] **Step 3: Verify build**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add site/app/page.tsx
git commit -m "feat: wire homepage coupon banner to live data"
```

---

## Task 5: Wire iHerb coupons page to live data

**Files:**
- Modify: `site/app/coupons/iherb/page.tsx`

- [ ] **Step 1: Replace hardcoded PROMO_CODES with coupons.json**

Remove the `PROMO_CODES` const. Import from data:
```typescript
import { getActiveCoupons, getExpiredCoupons } from '@/lib/data';
```

In the component:
```typescript
const activeCoupons = getActiveCoupons();
const expiredCoupons = getExpiredCoupons();
```

- [ ] **Step 2: Update the promo codes table**

Replace the hardcoded 3-row table with a dynamic table mapping `activeCoupons`:
```tsx
<tbody>
  {activeCoupons.map((coupon, i) => (
    <tr key={coupon.code} className={`border-b border-ink/8 last:border-b-0 hover:bg-signal/5 transition-colors duration-150 ${i % 2 === 0 ? 'bg-transparent' : 'bg-ink/[0.02]'}`}>
      <td className="px-6 py-4">
        <code className="font-editorial font-bold text-base tracking-wider text-ink">{coupon.code}</code>
      </td>
      <td className="px-6 py-4 text-ink-muted text-xs uppercase tracking-wider">{coupon.type}</td>
      <td className="px-6 py-4 font-semibold text-signal">{coupon.discount}</td>
      <td className="px-6 py-4 text-ink-muted">{coupon.notes || '—'}</td>
      <td className="px-6 py-4">
        <span className="inline-block px-2.5 py-0.5 text-[10px] uppercase tracking-wider font-semibold bg-ink text-cream">
          {coupon.status === 'valid' ? 'Active' : coupon.status}
        </span>
      </td>
    </tr>
  ))}
</tbody>
```

- [ ] **Step 3: Add expired codes collapsible section**

After the active codes table, add a `<details>` block for expired codes (same pattern as Astro version):
```tsx
{expiredCoupons.length > 0 && (
  <details className="mt-6 border border-ink/10">
    <summary className="px-6 py-4 cursor-pointer text-sm font-semibold text-ink-muted hover:text-ink transition-colors select-none">
      Expired Codes ({expiredCoupons.length})
    </summary>
    {/* ... render expired coupons */}
  </details>
)}
```

- [ ] **Step 4: Verify build**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add site/app/coupons/iherb/page.tsx
git commit -m "feat: wire iHerb page to live coupon data from pipeline"
```

---

## Task 6: Add about page

**Files:**
- Create: `site/app/about/page.tsx`

- [ ] **Step 1: Create about page with editorial styling**

Use the same editorial patterns from the anyadaily iHerb page — numbered steps, border-based cards, RevealOnScroll, serif headlines. Content: origin story, 3-step process (Discover/Verify/Publish), affiliate disclosure, contact.

Key sections:
- Header: "Every deal, verified. *No noise.*"
- How It Works: 3-column bordered grid (01 Discover, 02 Verify, 03 Publish) with hover-invert
- Affiliate Disclosure: bordered container
- Contact: links to Twitter/Reddit

- [ ] **Step 2: Verify build and check routing**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
ls out/about/index.html  # should exist
```

- [ ] **Step 3: Commit**

```bash
git add site/app/about/
git commit -m "feat: add about page with editorial design"
```

---

## Task 7: Add dashboard page

**Files:**
- Create: `site/app/dashboard/page.tsx`
- Create: `site/components/StatusIndicator.tsx`

- [ ] **Step 1: Create StatusIndicator component**

React client component showing job status with colored indicator dot, label, last run, next run, error.

- [ ] **Step 2: Create dashboard page**

Import dashboard.json via `getDashboard()`. Show:
- Pipeline Status: 3-column grid of StatusIndicator cards
- Stats: 4-column grid showing active codes, expired, posts this week, last deploy

Style with the editorial design system (bordered cards, serif headlines, signal color accents).

- [ ] **Step 3: Verify build**

```bash
cd /home/skaiself/repo/anyadeals/site && npm run build
ls out/dashboard/index.html  # should exist
```

- [ ] **Step 4: Commit**

```bash
git add site/app/dashboard/ site/components/StatusIndicator.tsx
git commit -m "feat: add pipeline dashboard page"
```

---

## Task 8: Update docker-compose volume mount

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update all volume mounts**

Change every occurrence of `./site/src/data:/data` to `./site/data:/data`:

```yaml
# In all 4 services: orchestrator, researcher, validator, poster
volumes:
  - ./site/data:/data
```

- [ ] **Step 2: Verify docker-compose config is valid**

```bash
cd /home/skaiself/repo/anyadeals && docker compose config --quiet
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: update data volume mount for Next.js site structure"
```

---

## Task 9: Final build verification and cleanup

**Files:**
- Verify: full static export, all pages render

- [ ] **Step 1: Clean build**

```bash
cd /home/skaiself/repo/anyadeals/site
rm -rf out .next node_modules
npm install
npm run build
```

- [ ] **Step 2: Verify all pages exist in static export**

```bash
ls out/index.html
ls out/coupons/iherb/index.html
ls out/about/index.html
ls out/dashboard/index.html
```
Expected: All 4 files exist.

- [ ] **Step 3: Visual check**

```bash
cd /home/skaiself/repo/anyadeals/site && npx serve out -p 4322
```
Check all pages at localhost:4322.

- [ ] **Step 4: Verify data pipeline integration**

Confirm that modifying `site/data/coupons.json` and rebuilding reflects changes in the iHerb page.

- [ ] **Step 5: Update .gitignore**

Ensure `site/out/`, `site/.next/`, `site/node_modules/` are in `.gitignore`.
**IMPORTANT:** `site/data/` must NOT be gitignored — the pipeline services write JSON here, then orchestrator commits and pushes to trigger Cloudflare Pages rebuild. These files must be tracked in git.

- [ ] **Step 6: Final commit**

```bash
git add .gitignore
git commit -m "chore: final cleanup for Next.js migration"
```
