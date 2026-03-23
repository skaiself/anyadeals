# AnyaDeals

Multi-category deal aggregator with automated iHerb coupon pipeline.

## Structure

```
anyadeals/
├── site/          # Astro static site (Cloudflare Pages)
├── services/      # Backend services (Docker Compose) — Plan B/C
└── scripts/       # Claude CLI wrappers — Plan C
```

## Development

```bash
cd site
npm install
npm run dev        # http://localhost:4321
npm run build      # Static output in dist/
```

## Deployment (Cloudflare Pages)

1. Go to Cloudflare Pages dashboard
2. Create new project → Connect to GitHub → Select `skaiself/anyadeals`
3. Build settings:
   - Build command: `cd site && npm run build`
   - Build output directory: `site/dist`
   - Root directory: `/`
4. Deploy

## Tech Stack

- **Frontend:** Astro 6 + Tailwind CSS 4 + React islands
- **Hosting:** Cloudflare Pages
- **Data:** JSON files in `site/src/data/` (auto-updated by backend pipeline)
