# AnyaDeals Site

Next.js static site for displaying verified iHerb coupon codes.

## Commands

| Command            | Action                                |
| :----------------- | :------------------------------------ |
| `npm install`      | Install dependencies                  |
| `npm run dev`      | Start dev server at `localhost:3000`   |
| `npm run build`    | Build static export to `out/`         |
| `npm test`         | Run Vitest test suite                 |
| `npm run test:watch` | Run tests in watch mode             |
| `npm run lint`     | Run Next.js linter                    |

## Pages

- `/` — Homepage with hero, trending picks, active coupon count
- `/coupons/iherb` — Coupon stacking guide with live codes from pipeline
- `/about` — How it works, affiliate disclosure
- `/dashboard` — Pipeline job status and stats

## Data

The `data/` directory contains JSON files written by the backend pipeline:

- `coupons.json` — Validated coupon codes (written by validator service)
- `dashboard.json` — Pipeline status and stats (written by orchestrator)
- `posts.json` — Social media post log (written by poster service)
- `research.json` — Raw research output (written by researcher service)

These files are committed to git. The orchestrator pushes changes to trigger Cloudflare Pages rebuild.

## Testing

52 tests across 4 files covering data layer contracts, component behavior, and JSON schema validation. See `docs/REDESIGN-GUIDE.md` for details.
