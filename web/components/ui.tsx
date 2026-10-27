import type { ComponentProps, ReactNode } from "react";

import type { Verdict } from "@/lib/types";

export const btnPrimary =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-brand-ink " +
  "shadow-[0_6px_18px_-4px_var(--brand)] transition hover:brightness-110 active:translate-y-px " +
  "disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted/70 disabled:shadow-none disabled:ring-1 disabled:ring-line";

export const btnSecondary =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm " +
  "font-semibold text-ink transition hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50";

export const btnLink = "font-semibold text-brand underline-offset-2 hover:underline";

export const inputCls =
  "w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-muted/70 " +
  "transition focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15 disabled:bg-surface-2";

export function Panel({ className = "", ...props }: ComponentProps<"section">) {
  return <section className={`rounded-2xl border border-line bg-surface p-5 shadow-panel sm:p-6 ${className}`} {...props} />;
}

export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`text-[11px] font-semibold uppercase tracking-[0.08em] text-muted ${className}`}>{children}</p>;
}

export function PanelTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 className="font-display text-lg font-bold tracking-tight text-ink">{children}</h2>
      {aside}
    </div>
  );
}

export function scoreTone(score: number): "good" | "warn" | "bad" {
  if (score >= 70) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

const TONE_STROKE = { good: "stroke-good", warn: "stroke-warn", bad: "stroke-bad" } as const;

/** A circular fit score. `size` is the diameter in pixels. */
export function ScoreRing({ score, size = 56 }: { score: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const big = size >= 90;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={radius} className="fill-none stroke-surface-2" strokeWidth="9" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          className={`fill-none ${TONE_STROKE[scoreTone(clamped)]}`}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-mono font-semibold tabular-nums text-ink ${big ? "text-3xl" : "text-base"}`}>{clamped}</span>
        {big && <span className="text-xs text-muted">/ 100</span>}
      </div>
    </div>
  );
}

const VERDICT_PILL: Record<Verdict, { label: string; className: string }> = {
  strong: { label: "Strong fit", className: "bg-good-soft text-good" },
  possible: { label: "Possible", className: "bg-warn-soft text-warn" },
  weak: { label: "Weak fit", className: "bg-bad-soft text-bad" },
};

export function VerdictPill({ verdict, label }: { verdict: Verdict; label?: string }) {
  const v = VERDICT_PILL[verdict];
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${v.className}`}>
      {label ?? v.label}
    </span>
  );
}

export function FlagTag({ children }: { children: ReactNode }) {
  return (
    <li className="rounded-full bg-bad-soft px-2.5 py-0.5 text-xs font-medium text-bad ring-1 ring-bad/25">🚩 {children}</li>
  );
}

/** A faded, non-interactive example of a result, shown before the visitor has one of their own. */
export function ExamplePreview({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section aria-label={label}>
      <p className="mb-3 flex items-center gap-2 text-xs text-muted">
        <span className="rounded-full bg-surface px-2.5 py-0.5 font-semibold uppercase tracking-[0.08em] text-muted ring-1 ring-line">
          {label}
        </span>
        What you&apos;ll get, using a fictional resume
      </p>
      <div inert className="select-none opacity-70 [mask-image:linear-gradient(to_bottom,black_50%,transparent)]">
        {children}
      </div>
    </section>
  );
}
