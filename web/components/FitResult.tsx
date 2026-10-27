import type { FitReport, JobPosting, Verdict } from "@/lib/types";

import { Eyebrow, FlagTag, ScoreRing, VerdictPill } from "./ui";

const VERDICT_TEXT: Record<Verdict, string> = {
  strong: "Strong match: apply",
  possible: "Possible match: apply and address the gaps",
  weak: "Weak match: probably skip",
};

function formatSalary(job: JobPosting): string {
  const fmt = (n: number) => `฿${n.toLocaleString()}`;
  const { salary_min_thb: min, salary_max_thb: max } = job;
  if (min && max) return `${fmt(min)} – ${fmt(max)} / month`;
  if (min) return `From ${fmt(min)} / month`;
  if (max) return `Up to ${fmt(max)} / month`;
  return "Not stated";
}

type Tone = "plain" | "good" | "bad";

function Row({ label, value, tone = "plain" }: { label: string; value: string; tone?: Tone }) {
  const color = { plain: "text-ink", good: "text-good", bad: "text-bad" }[tone];
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 border-b border-dashed border-line py-2 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className={`font-medium ${color}`}>{value}</dd>
    </div>
  );
}

function Chips({ items, tone }: { items: string[]; tone: "good" | "warn" }) {
  const cls = tone === "good" ? "bg-good-soft text-good ring-good/20" : "bg-warn-soft text-warn ring-warn/25";
  if (!items.length) return <p className="text-sm text-muted">None</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((s) => (
        <li key={s} className={`rounded-full px-2.5 py-0.5 text-[13px] font-medium ring-1 ${cls}`}>
          {s}
        </li>
      ))}
    </ul>
  );
}

export default function FitResult({ report }: { report: FitReport }) {
  const { job, match, verdict, verdict_reason } = report;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <ScoreRing score={match.fit_score} size={104} />
        <div className="min-w-0 space-y-2">
          <Eyebrow>Assessment</Eyebrow>
          <p className="font-display text-xl font-bold leading-snug tracking-tight text-ink">
            {job.title}
            {job.company && <span className="font-semibold text-muted"> · {job.company}</span>}
          </p>
          <VerdictPill verdict={verdict} label={VERDICT_TEXT[verdict]} />
          <p className="text-[15px] leading-relaxed text-ink">{verdict_reason}</p>
        </div>
      </div>

      <dl className="rounded-xl border border-line bg-surface-2/40 px-4 py-1">
        <Row label="Salary" value={formatSalary(job)} />
        <Row label="Location" value={job.location ?? "Not stated"} />
        <Row label="Work type" value={job.work_type ?? "Not stated"} />
        <Row label="Experience" value={job.min_years_experience != null ? `${job.min_years_experience}+ years` : "Not stated"} />
        <Row label="Thai required" value={job.thai_language_required ? "Yes" : "No"} tone={job.thai_language_required ? "bad" : "good"} />
        <Row label="English required" value={job.english_required ? "Yes" : "No"} />
      </dl>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Eyebrow>Skills you have</Eyebrow>
          <Chips items={match.matching_skills} tone="good" />
        </div>
        <div className="space-y-2">
          <Eyebrow>Skills to work on</Eyebrow>
          <Chips items={match.missing_skills} tone="warn" />
        </div>
      </div>

      {match.red_flags.length > 0 && (
        <div className="space-y-2 rounded-xl border border-bad/25 bg-bad-soft/60 p-4">
          <Eyebrow className="!text-bad">Watch out for</Eyebrow>
          <ul className="flex flex-wrap gap-1.5">
            {match.red_flags.map((f) => (
              <FlagTag key={f}>{f}</FlagTag>
            ))}
          </ul>
        </div>
      )}

      <p className="text-sm leading-relaxed text-muted">{match.summary}</p>
    </div>
  );
}
