import type { Metadata } from 'next';
import './globals.css';
import NavBar from '@/components/NavBar';
import { Libre_Bodoni, Public_Sans, Tenor_Sans } from 'next/font/google';

const libreBodoni = Libre_Bodoni({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-libre-bodoni',
});

const publicSans = Public_Sans({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-public-sans',
});

const tenorSans = Tenor_Sans({
  weight: '400',
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-tenor-sans',
});

export const metadata: Metadata = {
  title: 'AnyaDeals — Curated Finds for Life, Tech & Wellness',
  description:
    'Cut through the noise. Every deal, code, and product verified — saving you hours and real money.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${libreBodoni.variable} ${publicSans.variable} ${tenorSans.variable}`}>
      <head>
        <meta name="impact-site-verification" content="dd95fe28-f76e-4c91-ad0b-47d7a8a0ed38" />
      </head>
      <body className="bg-cream font-sans antialiased">
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(i,m,p,a,c,t){c.ire_o=p;c[p]=c[p]||function(){(c[p].a=c[p].a||[]).push(arguments)};t=a.createElement(m);var z=a.getElementsByTagName(m)[0];t.async=1;t.src=i;z.parentNode.insertBefore(t,z)})('https://utt.impactcdn.com/P-A7113349-2d32-42ee-93d3-f386188cbac81.js','script','impactStat',document,window);impactStat('transformLinks');impactStat('trackImpression');`,
          }}
        />
        <NavBar />
        <main>{children}</main>
        <footer className="border-t border-ink/10 mt-24 py-12 px-6 md:px-12">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div>
              <span className="font-brand text-xl uppercase tracking-[0.3em] font-medium text-ink">
                AnyaDeals
              </span>
              <p className="text-ink-muted text-sm mt-2 font-sans">
                Curated finds for life, tech & wellness.
              </p>
            </div>
            <nav className="flex gap-6 text-sm text-ink-muted font-sans" aria-label="Footer navigation">
              <a href="/" className="hover:text-signal transition-colors duration-200 cursor-pointer">Home</a>
              <a href="/coupons/iherb" className="hover:text-signal transition-colors duration-200 cursor-pointer">Coupons</a>
              <a href="/about" className="hover:text-signal transition-colors duration-200 cursor-pointer">About</a>
              <a href="/about#disclosure" className="hover:text-signal transition-colors duration-200 cursor-pointer">Affiliate Disclosure</a>
            </nav>
            <p className="text-xs text-ink-muted/60 font-sans">
              © 2026 AnyaDeals. All rights reserved.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
