import type { Metadata } from 'next';
import Link from 'next/link';
import RevealOnScroll from '@/components/RevealOnScroll';
import { getActiveCoupons } from '@/lib/data';

export const metadata: Metadata = {
  title: 'AnyaDeals — Curated Finds for Life, Tech & Wellness',
  description:
    'Cut through the noise. AnyaDeals curates only the best deals, wellness picks, and tech essentials — verified and editorially approved.',
};

const TRENDING_CARDS = [
  {
    id: 'iherb-coupon-stack',
    category: 'WELLNESS',
    title: 'Wellness Hacks: How to stack codes for 20% off at iHerb.',
    excerpt:
      'Layer a Rewards Code with official promos for max savings on supplements shipped to the EU and Balkans.',
    href: '/coupons/iherb',
    featured: true,
    readTime: '4 min read',
  },
  {
    id: 'tech-picks-march',
    category: 'TECH',
    title: 'The 5 tech buys worth every cent in March 2026.',
    excerpt:
      'From budget earbuds to a home office monitor that won\'t break your back or your bank.',
    href: '#deals',
    featured: false,
    readTime: '6 min read',
  },
  {
    id: 'morning-rituals',
    category: 'WELLNESS',
    title: 'Morning rituals that actually move the needle.',
    excerpt:
      'Science-backed routines from sleep scheduling to cold-exposure. No gimmicks, just results.',
    href: '#deals',
    featured: false,
    readTime: '5 min read',
  },
  {
    id: 'deals-roundup',
    category: 'DEALS',
    title: 'This week\'s silent deals: what\'s trending below the fold.',
    excerpt:
      'Flash sales, loyalty cashback stacks, and quiet product drops our readers keep requesting.',
    href: '#deals',
    featured: false,
    readTime: '3 min read',
  },
];

export default function HomePage() {
  const activeCoupons = getActiveCoupons();
  return (
    <>
      {/* ─── HERO ─────────────────────────────────────────── */}
      <section
        className="relative min-h-screen flex items-end pb-16 md:pb-24 pt-32 overflow-hidden"
        aria-label="Hero section"
      >
        {/* Background typography — decorative, aria-hidden */}
        <div
          className="absolute inset-0 select-none pointer-events-none overflow-hidden flex items-center"
          aria-hidden="true"
        >
          <span
            className="font-editorial font-bold leading-none text-ink/[0.04]"
            style={{ fontSize: 'clamp(6.5rem, 18vw, 16.5rem)', whiteSpace: 'nowrap', letterSpacing: '-0.04em' }}
          >
            ANYA
          </span>
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-6 md:px-12 w-full">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-12 lg:gap-0 items-end">

            {/* ── Text Column ── */}
            <div className="max-w-3xl relative z-20">
              {/* Superlabel */}
              <RevealOnScroll delay={0}>
                <p className="text-xs uppercase tracking-[0.2em] text-signal font-medium font-sans mb-6">
                  Editorial Picks · March 2026
                </p>
              </RevealOnScroll>

              {/* Main headline — deliberately massive and staggered alignment */}
              <RevealOnScroll delay={80}>
                <h1 className="headline-xl mb-2">
                  Curated finds
                </h1>
              </RevealOnScroll>
              <RevealOnScroll delay={160}>
                <h1
                  className="headline-xl mb-2 ml-4 md:ml-16 italic text-ink-muted"
                  style={{ WebkitTextStrokeWidth: '1px', WebkitTextStrokeColor: 'currentColor' }}
                >
                  for life,
                </h1>
              </RevealOnScroll>
              <RevealOnScroll delay={240}>
                <h1 className="headline-xl mb-10">
                  tech{' '}
                  <span className="text-signal">{'&'}</span>{' '}
                  wellness.
                </h1>
              </RevealOnScroll>

              <RevealOnScroll delay={360}>
                <p className="text-lg md:text-xl text-ink-muted font-sans font-light max-w-xl leading-relaxed border-l-2 border-signal pl-4 bg-cream/10 backdrop-blur-[2px]">
                  We strip out the noise. Every deal, code, and product on AnyaDeals
                  is personally tested or verified — saving you hours and real money.
                </p>
              </RevealOnScroll>

              <RevealOnScroll delay={440}>
                <div className="flex flex-wrap items-center gap-4 mt-10">
                  <Link
                    href="/coupons/iherb"
                    id="hero-cta-iherb"
                    className="
                      inline-flex items-center gap-2
                      bg-signal text-cream
                      px-8 py-4 text-sm font-semibold uppercase tracking-widest
                      hover:-translate-y-0.5 hover:shadow-[4px_4px_0_#0F0D0B]
                      transition-all duration-200 cursor-pointer
                    "
                  >
                    Stack iHerb Codes
                    <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                      <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="square" />
                    </svg>
                  </Link>
                  <Link
                    href="/coupons/iherb"
                    id="hero-cta-deals"
                    className="
                      inline-flex items-center gap-2
                      border border-ink text-ink
                      px-8 py-4 text-sm font-semibold uppercase tracking-widest
                      hover:bg-ink hover:text-cream
                      transition-all duration-200 cursor-pointer
                    "
                  >
                    Browse All Deals
                  </Link>
                </div>
              </RevealOnScroll>
            </div>

            {/* ── Image Column — pushed to far right, bleeds past grid ── */}
            <RevealOnScroll
              delay={200}
              className="
                relative lg:absolute lg:-right-64 lg:bottom-0
                h-[700px] lg:h-[1665px] w-full lg:w-[1200px]
                flex items-end justify-center lg:justify-end
                pointer-events-none z-10
              "
            >
              {/* Decorative accent block behind image */}
              <div
                className="absolute bottom-0 right-64 w-96 h-96 border border-signal/10 -z-10"
                aria-hidden="true"
              />
              <img
                src="/anya-hero.png"
                alt="Anya — your daily curator"
                className="h-full w-auto object-contain object-bottom drop-shadow-[0_48px_96px_rgba(15,13,11,0.35)] scale-126 origin-bottom opacity-95"
                loading="eager"
              />
            </RevealOnScroll>
          </div>
        </div>

        {/* Thin horizontal rule at the bottom */}
        <div className="absolute bottom-0 left-0 right-0 h-px bg-ink/10" aria-hidden="true" />
      </section>

      {/* Active Coupons Banner */}
      <div className="max-w-7xl mx-auto px-6 md:px-12 py-8">
        <Link
          href="/coupons/iherb"
          className="block bg-signal/5 border border-signal/20 p-4 text-center text-sm text-ink hover:bg-signal/10 transition-colors"
        >
          <span className="font-semibold text-signal">{activeCoupons.length} verified iHerb codes active</span>
          {' '}— Stack them now →
        </Link>
      </div>

      {/* ─── TRENDING PICKS ──────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 py-20 md:py-28" aria-label="Trending picks">
        <RevealOnScroll>
          <div className="flex items-baseline gap-4 mb-12">
            <h2 className="headline-md font-editorial">Trending Picks</h2>
            <span className="text-xs uppercase tracking-[0.18em] text-ink-muted/60 font-sans">
              March 2026
            </span>
          </div>
        </RevealOnScroll>

        {/* Card Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-0 border border-ink/10">
          {TRENDING_CARDS.map((card, i) => (
            <RevealOnScroll key={card.id} delay={i * 80}>
              <Link
                href={card.href}
                id={`card-${card.id}`}
                className={`
                  group block h-full border-b md:border-b-0
                  ${i < 3 ? 'md:border-r' : ''}
                  border-ink/10
                  p-8 md:p-7 lg:p-8
                  relative overflow-hidden cursor-pointer
                  transition-all duration-200
                  hover:bg-ink hover:text-cream
                  ${card.featured ? 'ring-1 ring-inset ring-signal/50' : ''}
                `}
                aria-label={card.title}
              >
                {/* Featured badge */}
                {card.featured && (
                  <span className="absolute top-0 right-0 bg-signal text-cream text-[10px] uppercase tracking-widest font-semibold px-3 py-1">
                    Featured
                  </span>
                )}

                {/* Category label */}
                <p className="text-[10px] uppercase tracking-[0.22em] text-signal font-medium mb-4 font-sans group-hover:text-signal-light transition-colors duration-200">
                  {card.category}
                </p>

                {/* Title */}
                <h3 className="font-editorial text-lg font-semibold leading-snug mb-3 group-hover:text-cream transition-colors duration-200">
                  {card.title}
                </h3>

                {/* Excerpt */}
                <p className="text-sm text-ink-muted font-sans font-light leading-relaxed mb-6 group-hover:text-cream/70 transition-colors duration-200">
                  {card.excerpt}
                </p>

                {/* Read link */}
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-muted group-hover:text-signal-light transition-colors duration-200">
                  <span>Read</span>
                  <svg className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform duration-200" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="square" />
                  </svg>
                  <span className="ml-auto font-normal normal-case tracking-normal text-ink-muted/50 group-hover:text-cream/40 transition-colors duration-200">
                    {card.readTime}
                  </span>
                </div>

                {/* Hover state decorative corner */}
                <div
                  className="absolute bottom-0 right-0 w-16 h-16 border-t border-l border-signal/0 group-hover:border-signal/30 transition-colors duration-300"
                  aria-hidden="true"
                />
              </Link>
            </RevealOnScroll>
          ))}
        </div>
      </section>
    </>
  );
}
