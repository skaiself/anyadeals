import type { Metadata } from 'next';
import RevealOnScroll from '@/components/RevealOnScroll';

export const metadata: Metadata = {
  title: 'About — AnyaDeals',
  description: 'Learn about AnyaDeals and our deal curation process.',
};

export default function AboutPage() {
  return (
    <article className="pt-28 pb-24">
      {/* Header */}
      <header className="max-w-7xl mx-auto px-6 md:px-12">
        <RevealOnScroll>
          <p className="text-xs uppercase tracking-[0.2em] text-signal font-medium font-sans mb-5">About Us</p>
        </RevealOnScroll>
        <RevealOnScroll delay={80}>
          <h1 className="headline-lg mb-6">
            Every deal, verified.{' '}
            <em className="not-italic text-signal">No noise.</em>
          </h1>
        </RevealOnScroll>
        <RevealOnScroll delay={160}>
          <p className="text-lg text-ink-muted font-sans font-light leading-relaxed max-w-2xl border-l-2 border-signal pl-4">
            AnyaDeals started as a personal project to track the best iHerb supplement deals
            across Europe and the Balkans. What began as a spreadsheet of promo codes turned into
            an automated platform that discovers, validates, and publishes verified deals daily.
          </p>
        </RevealOnScroll>
        <div className="mt-12 border-t border-ink/10" />
      </header>

      {/* How It Works — 3-column grid with hover-invert */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-16">
        <RevealOnScroll>
          <h2 className="headline-md font-editorial mb-10">How It Works</h2>
        </RevealOnScroll>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-ink/10">
          {[
            { step: '01', title: 'Discover', desc: 'Our research service scans dozens of coupon sites, forums, and social media for new promo codes.' },
            { step: '02', title: 'Verify', desc: 'Every code is tested automatically through real checkout flows using residential proxies across multiple countries.' },
            { step: '03', title: 'Publish', desc: 'Only verified, working codes make it to the site. Expired codes are flagged and removed.' },
          ].map((item, i) => (
            <RevealOnScroll key={item.step} delay={i * 80}>
              <div className={`p-8 md:p-10 group hover:bg-ink hover:text-cream transition-all duration-200 ${i < 2 ? 'border-b md:border-b-0 md:border-r border-ink/10' : ''}`}>
                <span className="font-editorial text-4xl font-bold text-ink/10 leading-none select-none group-hover:text-cream/10 transition-colors" aria-hidden="true">{item.step}</span>
                <h3 className="font-editorial text-xl font-semibold mt-4 mb-3 group-hover:text-cream transition-colors">{item.title}</h3>
                <p className="text-sm text-ink-muted font-sans font-light leading-relaxed group-hover:text-cream/70 transition-colors">{item.desc}</p>
              </div>
            </RevealOnScroll>
          ))}
        </div>
      </section>

      {/* Affiliate Disclosure */}
      <section id="disclosure" className="max-w-7xl mx-auto px-6 md:px-12 mt-20">
        <RevealOnScroll>
          <h2 className="headline-md font-editorial mb-8">Affiliate Disclosure</h2>
        </RevealOnScroll>
        <RevealOnScroll delay={80}>
          <div className="border border-ink/10 p-8 md:p-10 space-y-4 text-ink-muted font-sans font-light leading-relaxed">
            <p>
              This site contains affiliate links. When you purchase through our links,
              we may earn a commission at no extra cost to you. This helps us keep the
              site running and continue verifying deals for you.
            </p>
            <p>
              We use iHerb&apos;s referral program (code: <strong className="font-semibold text-signal">OFR0296</strong>)
              and participate in the iHerb affiliate program via Impact. Our recommendations
              are based on genuine testing and verification — we only promote products
              and deals we believe offer real value.
            </p>
          </div>
        </RevealOnScroll>
      </section>

      {/* Contact */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-20">
        <RevealOnScroll>
          <h2 className="headline-md font-editorial mb-6">Contact</h2>
        </RevealOnScroll>
        <RevealOnScroll delay={80}>
          <p className="text-ink-muted font-sans font-light leading-relaxed">
            Have a deal tip or question? Reach out on{' '}
            <a href="#" className="text-signal font-medium hover:underline">Twitter/X</a> or{' '}
            <a href="#" className="text-signal font-medium hover:underline">Reddit</a>.
          </p>
        </RevealOnScroll>
      </section>
    </article>
  );
}
