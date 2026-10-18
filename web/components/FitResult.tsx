import type { FitReport, JobPosting, Verdict } from "@/lib/types";

const VERDICT: Record<Verdict, { label: string; badge: string; ring: string }> = {
  strong: { label: "Strong match: apply", badge: "bg-emerald-100 text-emerald-800", ring: "text-emerald-600" },
  possible: { label: "Possible match: apply and address the gaps", badge: "bg-amber-100 text-amber-800", ring: "text-amber-500" },
  weak: { label: "Weak match: probably skip", badge: "bg-rose-100 text-rose-800", ring: "text-rose-600" },
};

function formatSalary(job: JobPosting): string {
  const fmt = (n: number) => `฿${n.toLocaleString()}`;
  const { salary_min_thb: min, salary_max_thb: max } = job;
  if (min && max) return `${fmt(min)} – ${fmt(max)} / month`;
  if (min) return `From ${fmt(min)} / month`;
  if (max) return `Up to ${fmt(max)} / month`;
  return "Not stated";
}

function ScoreRing({ score, className }: { score: number; className: string }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <div className="relative h-28 w-28 shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={radius} className="fill-none stroke-slate-200" strokeWidth="10" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          className={`fill-none stroke-current ${className}`}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-slate-900">{clamped}</span>
        <span className="text-xs text-slate-500">/ 100</span>
      </div>
    </div>
  );
}

function Fact({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-sm font-medium ${warn ? "text-rose-700" : "text-slate-900"}`}>{value}</p>
    </div>
  );
}

function SkillList({ title, items, tone }: { title: string; items: string[]; tone: "good" | "gap" }) {
  const chip = tone === "good" ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : "bg-amber-50 text-amber-900 ring-amber-200";
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-900">{title}</h4>
      {items.length ? (
        <ul className="flex flex-wrap gap-2">
          {items.map((s) => (
            <li key={s} className={`rounded-full px-3 py-1 text-sm ring-1 ${chip}`}>
              {s}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">None</p>
      )}
    </div>
  );
}

export default function FitResult({ report }: { report: FitReport }) {
  const { job, match, verdict, verdict_reason } = report;
  const v = VERDICT[verdict];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <ScoreRing score={match.fit_score} className={v.ring} />
        <div className="space-y-2">
          <p className="text-sm text-slate-500">
            {job.title}
            {job.company ? ` · ${job.company}` : ""}
          </p>
          <span className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${v.badge}`}>{v.label}</span>
          <p className="text-slate-700">{verdict_reason}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Fact label="Salary" value={formatSalary(job)} />
        <Fact label="Location" value={job.location ?? "Not stated"} />
        <Fact label="Work type" value={job.work_type ?? "Not stated"} />
        <Fact
          label="Experience"
          value={job.min_years_experience != null ? `${job.min_years_experience}+ years` : "Not stated"}
        />
        <Fact label="Thai required" value={job.thai_language_required ? "Yes" : "No"} warn={job.thai_language_required} />
        <Fact label="English required" value={job.english_required ? "Yes" : "No"} />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <SkillList title="✅ Skills you have" items={match.matching_skills} tone="good" />
        <SkillList title="⚠️ Skills to work on" items={match.missing_skills} tone="gap" />
      </div>

      {match.red_flags.length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <h4 className="mb-2 text-sm font-semibold text-rose-900">🚩 Watch out for</h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-rose-900">
            {match.red_flags.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-sm text-slate-600">{match.summary}</p>
    </div>
  );
}
