import type { Metadata } from 'next';
import Link from 'next/link';
import RevealOnScroll from '@/components/RevealOnScroll';
import CouponTicket from '@/components/CouponTicket';
import { getActiveCoupons, getExpiredCoupons } from '@/lib/data';

export const metadata: Metadata = {
  title: 'How to Stack iHerb Discounts in March 2026 — AnyaDeals',
  description:
    'Learn how to stack iHerb\'s Rewards Code OFR0296 with official promo codes for up to 20% off supplements — with EU & Balkan shipping tips.',
};

const SUPPLEMENTS = [
  {
    id: 'magnesium-glycinate',
    name: 'Magnesium Glycinate',
    brand: 'Doctor\'s Best, 240ct',
    servings: 120,
    retailPerServing: 0.34,
    anyaPerServing: 0.27,
    retailTotal: 40.99,
    anyaTotal: 32.79,
    unit: 'serving',
  },
  {
    id: 'creatine-monohydrate',
    name: 'Creatine Monohydrate',
    brand: 'Optimum Nutrition, 1.32kg',
    servings: 264,
    retailPerServing: 0.11,
    anyaPerServing: 0.087,
    retailTotal: 29.99,
    anyaTotal: 22.99,
    unit: 'serving',
  },
];

export default function IHerbCouponsPage() {
  const activeCoupons = getActiveCoupons();
  const expiredCoupons = getExpiredCoupons();

  return (
    <article className="pt-28 pb-24" aria-label="iHerb discount stacking guide">

      {/* ─── EDITORIAL HEADER ──────────────────────────── */}
      <header className="max-w-7xl mx-auto px-6 md:px-12">
        <RevealOnScroll>
          <nav className="flex items-center gap-2 text-xs text-ink-muted font-sans mb-8" aria-label="Breadcrumb">
            <Link href="/" className="hover:text-ink transition-colors duration-200 cursor-pointer">Home</Link>
            <span aria-hidden="true">/</span>
            <Link href="/deals" className="hover:text-ink transition-colors duration-200 cursor-pointer">Deals</Link>
            <span aria-hidden="true">/</span>
            <span className="text-ink font-medium">iHerb Codes</span>
          </nav>
        </RevealOnScroll>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-12 items-start">
          <div>
            {/* Superlabel */}
            <RevealOnScroll delay={0}>
              <p className="text-xs uppercase tracking-[0.2em] text-signal font-medium font-sans mb-5">
                Wellness · Savings Guide
              </p>
            </RevealOnScroll>

            {/* Main title */}
            <RevealOnScroll delay={80}>
              <h1 className="headline-lg mb-6">
                How to Stack iHerb Discounts in{' '}
                <em className="not-italic text-signal">March 2026</em>:{' '}
                The Ultimate Guide.
              </h1>
            </RevealOnScroll>

            {/* Intro paragraph */}
            <RevealOnScroll delay={160}>
              <p className="text-lg text-ink-muted font-sans font-light leading-relaxed max-w-2xl border-l-2 border-signal pl-4">
                iHerb ships to 180+ countries with competitive EU and Balkan rates.
                For shoppers in Serbia, Croatia, Slovenia, and beyond, it remains the
                most affordable source for quality supplements. The trick? Layering
                a Rewards Code <em>first</em>, then applying an official promo code
                at checkout — letting iHerb automatically pick the better deal.
              </p>
            </RevealOnScroll>
          </div>

          {/* Trust badges column */}
          <RevealOnScroll delay={200} className="lg:pt-16">
            <div className="border border-ink/10 p-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 flex items-center justify-center border border-signal/30">
                  <svg className="w-4 h-4 text-signal" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M8 1l2 4 5 .7-3.5 3.4.8 5L8 12l-4.3 2.1.8-5L1 5.7 6 5z" strokeLinecap="square" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink uppercase tracking-wider font-sans">Verified by Anya</p>
                  <p className="text-xs text-ink-muted font-sans">Personally tested checkout flow</p>
                </div>
              </div>
              <div className="w-full h-px bg-ink/8" />
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 flex items-center justify-center border border-gold/30">
                  <svg className="w-4 h-4 text-gold" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <circle cx="8" cy="8" r="6" />
                    <path d="M8 5v3l2 1" strokeLinecap="square" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink uppercase tracking-wider font-sans">Updated Today</p>
                  <p className="text-xs text-ink-muted font-sans">14 March 2026, 10:44 CET</p>
                </div>
              </div>
              <div className="w-full h-px bg-ink/8" />
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 flex items-center justify-center border border-ink/20">
                  <svg className="w-4 h-4 text-ink-muted" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <rect x="2" y="4" width="12" height="9" />
                    <path d="M5 4V3a3 3 0 016 0v1" strokeLinecap="square" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink uppercase tracking-wider font-sans">EU & Balkan Shipping</p>
                  <p className="text-xs text-ink-muted font-sans">Ships to RS, HR, SI, MK, BA +</p>
                </div>
              </div>
            </div>
          </RevealOnScroll>
        </div>

        <div className="mt-12 border-t border-ink/10" />
      </header>

      {/* ─── STEP 1: REWARDS CODE ──────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-16" aria-labelledby="step1-heading">
        <RevealOnScroll>
          <div className="flex items-center gap-4 mb-8">
            <span className="font-editorial text-5xl font-bold text-ink/10 leading-none select-none" aria-hidden="true">01</span>
            <h2 id="step1-heading" className="headline-md font-editorial">
              Enter the Rewards Code <em className="italic not-italic text-signal">first.</em>
            </h2>
          </div>
        </RevealOnScroll>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-12 items-start">
          <RevealOnScroll delay={80}>
            <div className="space-y-5 text-base text-ink-muted font-sans font-light leading-relaxed">
              <p>
                The iHerb Rewards Program works differently from a standard promo code.
                When you enter a Rewards Code at checkout (in the &ldquo;Loyalty Credits&rdquo; or
                &ldquo;Referral&rdquo; field), it attaches a{' '}
                <strong className="font-semibold text-ink">5% discount</strong> to your cart as a
                loyalty reward — without conflicting with most official promotions.
              </p>
              <p>
                This is the baseline discount that stacks <em>on top</em> of any promotional
                code you apply in Step 2. Think of it as your foundation layer.
              </p>
              <p className="text-xs uppercase tracking-widest text-signal font-semibold font-sans pt-2">
                How to apply: Checkout → Loyalty Programs → Enter Code
              </p>
            </div>
          </RevealOnScroll>

          <RevealOnScroll delay={160}>
            <CouponTicket
              code="OFR0296"
              label="iHerb Rewards Code · Step 1 of 2"
              sublabel="Applies 5% loyalty discount · Enter in Referral Code field"
            />
          </RevealOnScroll>
        </div>
      </section>

      {/* ─── STEP 2: PROMO CODES ─────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-20" aria-labelledby="step2-heading">
        <RevealOnScroll>
          <div className="flex items-center gap-4 mb-8">
            <span className="font-editorial text-5xl font-bold text-ink/10 leading-none select-none" aria-hidden="true">02</span>
            <h2 id="step2-heading" className="headline-md font-editorial">
              Apply a Promo Code. iHerb picks the{' '}
              <em className="italic not-italic text-signal">best one.</em>
            </h2>
          </div>
        </RevealOnScroll>

        <RevealOnScroll delay={60}>
          <p className="text-base text-ink-muted font-sans font-light leading-relaxed border-l-2 border-ink/20 pl-4 max-w-2xl mb-10">
            iHerb uses a "best discount wins" logic at checkout. Enter any official promo code
            and the system will apply whichever discount is larger — the code or any existing
            sale price. The Rewards Code from Step 1 layers independently on top.
          </p>
        </RevealOnScroll>

        {/* Promo Code Table */}
        <RevealOnScroll delay={120}>
          <div className="border border-ink/10 overflow-auto">
            <table className="w-full text-sm font-sans" role="table" aria-label="Current iHerb promo codes">
              <thead>
                <tr className="border-b border-ink/10 bg-ink text-cream">
                  <th className="text-left px-6 py-4 text-xs uppercase tracking-widest font-semibold" scope="col">Code</th>
                  <th className="text-left px-6 py-4 text-xs uppercase tracking-widest font-semibold" scope="col">Type</th>
                  <th className="text-left px-6 py-4 text-xs uppercase tracking-widest font-semibold" scope="col">Discount</th>
                  <th className="text-left px-6 py-4 text-xs uppercase tracking-widest font-semibold" scope="col">Notes</th>
                  <th className="text-left px-6 py-4 text-xs uppercase tracking-widest font-semibold" scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {activeCoupons.map((coupon, i) => (
                  <tr
                    key={coupon.code}
                    className={`border-b border-ink/8 last:border-b-0 hover:bg-signal/5 transition-colors duration-150 cursor-default ${i % 2 === 0 ? 'bg-transparent' : 'bg-ink/[0.02]'}`}
                  >
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
            </table>
          </div>
        </RevealOnScroll>

        {expiredCoupons.length > 0 && (
          <details className="mt-6 border border-ink/10">
            <summary className="px-6 py-4 cursor-pointer text-sm font-semibold text-ink-muted hover:text-ink transition-colors select-none">
              Expired Codes ({expiredCoupons.length})
            </summary>
            <div className="border-t border-ink/10 overflow-auto">
              <table className="w-full text-sm font-sans">
                <tbody>
                  {expiredCoupons.map((coupon, i) => (
                    <tr key={coupon.code} className="border-b border-ink/8 last:border-b-0 opacity-50">
                      <td className="px-6 py-4">
                        <code className="font-editorial font-bold text-base tracking-wider text-ink">{coupon.code}</code>
                      </td>
                      <td className="px-6 py-4 text-ink-muted text-xs uppercase tracking-wider">{coupon.type}</td>
                      <td className="px-6 py-4 text-ink-muted">{coupon.discount}</td>
                      <td className="px-6 py-4 text-ink-muted">{coupon.notes || '—'}</td>
                      <td className="px-6 py-4">
                        <span className="inline-block px-2.5 py-0.5 text-[10px] uppercase tracking-wider font-semibold bg-ink-muted/20 text-ink-muted">
                          Expired
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </section>

      {/* ─── PRICE COMPARISON ────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-20" aria-labelledby="price-heading">
        <RevealOnScroll>
          <div className="flex items-center gap-4 mb-10">
            <span className="font-editorial text-5xl font-bold text-ink/10 leading-none select-none" aria-hidden="true">03</span>
            <h2 id="price-heading" className="headline-md font-editorial">
              Real savings,{' '}
              <em className="italic not-italic text-signal">per serving.</em>
            </h2>
          </div>
        </RevealOnScroll>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border border-ink/10">
          {SUPPLEMENTS.map((s, i) => (
            <RevealOnScroll key={s.id} delay={i * 120}>
              <div
                id={`supplement-${s.id}`}
                className={`p-10 ${i === 0 ? 'border-b md:border-b-0 md:border-r' : ''} border-ink/10 group`}
              >
                {/* Product header */}
                <p className="text-xs uppercase tracking-widest text-ink-muted font-sans mb-1 font-medium">{s.brand}</p>
                <h3 className="font-editorial text-2xl font-bold mb-8">{s.name}</h3>

                {/* Price comparison — the editorial centrepiece */}
                <div className="grid grid-cols-2 gap-4 mb-6" suppressHydrationWarning>
                  {/* Retail */}
                  <div className="border border-ink/10 p-5">
                    <p className="text-[10px] uppercase tracking-widest text-ink-muted font-sans font-medium mb-3">Retail Price</p>
                    <p className="font-editorial text-3xl font-bold text-ink-muted line-through decoration-signal">
                      {'$'}{s.retailTotal.toFixed(2)}
                    </p>
                    <p className="text-xs text-ink-muted/60 font-sans mt-1">
                      {'$'}{s.retailPerServing.toFixed(3)} / {s.unit}
                    </p>
                  </div>

                  {/* Anya stacked */}
                  <div className="border border-signal bg-ink p-5 relative overflow-hidden">
                    <p className="text-[10px] uppercase tracking-widest text-signal font-sans font-medium mb-3">Anya&apos;s Stacked Price</p>
                    <p className="font-editorial text-3xl font-bold text-cream">
                      {'$'}{s.anyaTotal.toFixed(2)}
                    </p>
                    <p className="text-xs text-cream/50 font-sans mt-1">
                      {'$'}{s.anyaPerServing.toFixed(3)} / {s.unit}
                    </p>
                    {/* Savings tag */}
                    <span className="absolute top-0 right-0 bg-signal text-cream text-[9px] uppercase tracking-widest font-bold px-2 py-1">
                      −{Math.round((1 - s.anyaTotal / s.retailTotal) * 100)}%
                    </span>
                  </div>
                </div>

                <p className="text-xs text-ink-muted font-sans font-light">
                  Savings based on stacking Rewards Code <strong className="font-semibold text-signal">OFR0296</strong> + best available promo.
                  Prices may vary by region.
                </p>
              </div>
            </RevealOnScroll>
          ))}
        </div>
      </section>

      {/* ─── CTA ─────────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-24" aria-label="Shop call to action">
        <RevealOnScroll>
          <div className="border border-ink p-10 md:p-16 flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
            <div>
              <h2 className="headline-md font-editorial mb-2">Ready to stack?</h2>
              <p className="text-base text-ink-muted font-sans font-light max-w-md">
                Open iHerb, build your cart, and apply codes in order. Anya&apos;s picks ship reliably to the EU &amp; Balkans.
              </p>
            </div>
            <a
              href="https://www.iherb.com/?rcode=OFR0296"
              id="cta-shop-iherb"
              target="_blank"
              rel="noopener noreferrer"
              className="
                flex-shrink-0 inline-flex items-center gap-3
                bg-signal text-cream
                px-10 py-5 text-sm font-semibold uppercase tracking-widest
                hover:-translate-y-0.5 hover:shadow-[4px_4px_0_#0F0D0B]
                transition-all duration-200 cursor-pointer
              "
            >
              Shop iHerb Now
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="square" />
              </svg>
            </a>
          </div>
        </RevealOnScroll>
      </section>

    </article>
  );
}
