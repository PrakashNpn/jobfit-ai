/** JobFit AI mark: a briefcase with a check, plus the wordmark. */
export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-ink" />
      <path d="M12 10.5V9a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1.5" fill="none" className="stroke-bg" strokeWidth="2" />
      <rect x="6.5" y="10.5" width="19" height="14" rx="2.5" fill="none" className="stroke-bg" strokeWidth="2" />
      <path d="m11.5 17.5 3 3 6-6" fill="none" className="stroke-brand" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      <span className="font-display text-[17px] font-extrabold tracking-tight text-ink">JobFit AI</span>
    </span>
  );
}
