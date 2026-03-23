import { useState } from 'react';

interface CouponTicketProps {
  code: string;
  label: string;
  sublabel: string;
}

export default function CouponTicket({ code, label, sublabel }: CouponTicketProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch {
      // fallback
    }
  };

  return (
    <button
      onClick={handleCopy}
      aria-label={`Copy coupon code ${code}`}
      className="coupon-ticket w-full text-left px-8 py-6 flex items-center justify-between gap-6 group"
    >
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-ink-muted font-sans mb-1 group-hover:text-cream/60 transition-colors duration-200">
          {label}
        </p>
        <p className="font-serif text-4xl md:text-5xl font-bold tracking-widest text-ink group-hover:text-cream transition-colors duration-200">
          {code}
        </p>
        <p className="text-xs text-ink-muted font-sans mt-1 group-hover:text-cream/60 transition-colors duration-200">
          {sublabel}
        </p>
      </div>
      <div className="flex-shrink-0 text-xs font-semibold uppercase tracking-widest flex flex-col items-center gap-1">
        {copied ? (
          <>
            <svg className="w-5 h-5 text-signal" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M4 10l4 4 8-8" strokeLinecap="square" strokeLinejoin="miter" />
            </svg>
            <span className="text-signal">Copied!</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5 text-ink-muted group-hover:text-cream transition-colors duration-200" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="7" y="7" width="10" height="10" rx="0" />
              <path d="M3 13V3h10" strokeLinecap="square" />
            </svg>
            <span className="text-ink-muted group-hover:text-cream transition-colors duration-200">Copy</span>
          </>
        )}
      </div>
    </button>
  );
}
