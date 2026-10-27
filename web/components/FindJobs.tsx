"use client";

import { useState } from "react";

import { ApiError, searchJobs } from "@/lib/api";
import type { FoundJob, JobSearchResult, SearchLink } from "@/lib/types";

import Spinner from "./Spinner";
import { ExamplePreview, FlagTag, ScoreRing, VerdictPill, btnPrimary, inputCls } from "./ui";

const SUGGESTIONS = ["Bangkok", "Singapore", "Dubai", "Remote"];

// Fictional, shown faded before the first search so visitors see what they'll get.
const EXAMPLE_JOBS: FoundJob[] = [
  {
    url: "#example-1", site: "th.jobsdb.com", title: "Full-Stack Developer (Next.js / Node.js)", company: "Lumen Labs (example)",
    location: "Sathon, Bangkok", posted: "1 day ago", fit_score: 86, verdict: "strong",
    reason: "Your Next.js, TypeScript and Node.js work matches every core requirement.", deal_breakers: [], summary: "",
  },
  {
    url: "#example-2", site: "th.jobsdb.com", title: "Full Stack Developer (Golang/React)", company: "Harbour Tech (example)",
    location: "Chatuchak, Bangkok", posted: "3 days ago", fit_score: 58, verdict: "possible",
    reason: "Strong React fit; Go would be new, so show how fast you learn.", deal_breakers: ["Go required"], summary: "",
  },
];

export type JobSearch = ReturnType<typeof useJobSearch>;

/** State shared by the search form (left column), the results (right column) and the hero stats. */
export function useJobSearch(resumeText: string | null) {
  const [location, setLocation] = useState("");
  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<JobSearchResult | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSearch = !!resumeText && location.trim().length >= 2 && !loading;

  async function search() {
    if (!resumeText || !canSearch) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(["Starting your search…"]);
    const started = performance.now();
    try {
      const data = await searchJobs(resumeText, location.trim(), (m) => setProgress((p) => [...p, m]));
      setResult(data);
      setSeconds(Math.round((performance.now() - started) / 1000));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return { location, setLocation, progress, result, seconds, loading, error, canSearch, search, hasResume: !!resumeText };
}

export function FindJobsForm({ state }: { state: JobSearch }) {
  const { location, setLocation, loading, canSearch, search, error, hasResume } = state;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        search();
      }}
      className="space-y-3"
    >
      <label htmlFor="job-location" className="sr-only">
        Where do you want to work? Any city, country or &ldquo;Remote&rdquo;.
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="job-location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          disabled={loading}
          placeholder="Where do you want to work? Any city, country or “Remote”"
          maxLength={80}
          className={`${inputCls} py-3 text-[15px] sm:flex-1`}
        />
        <button type="submit" disabled={!canSearch} aria-busy={loading} className={btnPrimary}>
          {loading ? (
            <>
              <Spinner /> Searching…
            </>
          ) : (
            "Find jobs for me"
          )}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 border-t border-line pt-3 text-[13px]">
        <span className="mr-1 text-xs text-muted">Try</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={loading}
            onClick={() => setLocation(s)}
            className={`rounded-full border px-3 py-0.5 transition ${location === s ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line text-muted hover:border-muted hover:text-ink"}`}
          >
            {s}
          </button>
        ))}
      </div>
      {!hasResume && <p className="text-xs text-muted">Add your resume first.</p>}
      {error && (
        <p role="alert" className="text-sm font-medium text-bad">
          {error}
        </p>
      )}
    </form>
  );
}

function ProgressChips({ messages, done }: { messages: string[]; done: boolean }) {
  if (done) {
    // Once the search is over the steps are detail, not news: fold them away.
    return (
      <details className="text-xs text-muted">
        <summary className="cursor-pointer font-medium hover:text-ink">
          How JobFit searched ({messages.length} steps)
        </summary>
        <ul className="mt-2 space-y-1 pl-4">
          {messages.map((m, i) => (
            <li key={`${i}-${m}`}>
              <span className="text-good">✓</span> {m}
            </li>
          ))}
        </ul>
      </details>
    );
  }
  return (
    <div role="status" aria-live="polite" className="space-y-2">
      <ul className="flex flex-wrap gap-2">
        {messages.map((m, i) => {
          const current = i === messages.length - 1 && !done;
          return (
            <li
              key={`${i}-${m}`}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs leading-snug ${
                current ? "border-brand/40 bg-brand-soft text-brand" : "border-line bg-surface text-muted"
              }`}
            >
              {current ? <Spinner className="h-3 w-3" /> : <span className="text-good">✓</span>}
              <span>{m}</span>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-muted">A smart search usually takes 15–45 seconds.</p>
    </div>
  );
}

function SearchLinks({ links }: { links: SearchLink[] }) {
  const roles = [...new Set(links.map((l) => l.role))];
  return (
    <details className="rounded-2xl border border-line bg-surface px-5 py-3 text-sm shadow-panel">
      <summary className="cursor-pointer font-semibold text-ink">Search more on the job boards</summary>
      <ul className="mt-3 space-y-2">
        {roles.map((role) => (
          <li key={role} className="flex flex-wrap items-center gap-2">
            <span className="min-w-36 font-medium text-ink">{role}</span>
            {links
              .filter((l) => l.role === role)
              .map((l) => (
                <a
                  key={l.url}
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-line px-2.5 py-1 font-medium text-muted hover:border-brand hover:text-brand"
                >
                  {l.site} ↗
                </a>
              ))}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** One result, as in the Clarity mock-up: ring on the left, details in the middle, verdict and actions on the right. */
function JobCard({ job, onCheckFit }: { job: FoundJob; onCheckFit: () => void }) {
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-3 rounded-2xl border border-line bg-surface px-4 py-4 shadow-panel transition hover:border-brand/40 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:px-5">
      <ScoreRing score={job.fit_score} size={56} />
      <div className="min-w-0 space-y-1">
        <p className="font-display text-[16px] font-bold leading-snug text-ink">{job.title}</p>
        <p className="text-[13px] text-muted">
          {[job.company, job.location, job.posted, job.site].filter(Boolean).join(" · ")}
        </p>
        <p className="text-sm text-ink">{job.reason}</p>
        {job.deal_breakers.length > 0 && (
          <ul className="flex flex-wrap gap-1.5 pt-1">
            {job.deal_breakers.map((d) => (
              <FlagTag key={d}>{d}</FlagTag>
            ))}
          </ul>
        )}
      </div>
      <div className="col-span-2 flex items-center justify-between gap-3 sm:col-span-1 sm:flex-col sm:items-end sm:justify-center sm:gap-2">
        <VerdictPill verdict={job.verdict} />
        <div className="flex items-center gap-4 text-[13px] font-semibold">
          <a href={job.url} target="_blank" rel="noreferrer" className="text-muted hover:text-ink">
            Apply ↗
          </a>
          <button type="button" onClick={onCheckFit} className="text-brand hover:underline">
            Full fit check →
          </button>
        </div>
      </div>
    </li>
  );
}

export function FindJobsResults({ state, onCheckFit }: { state: JobSearch; onCheckFit: (job: FoundJob) => void }) {
  const { progress, result, loading, seconds } = state;
  const [hideDealBreakers, setHideDealBreakers] = useState(false);
  const shown = result?.jobs.filter((j) => !hideDealBreakers || j.deal_breakers.length === 0) ?? [];

  if (!loading && !result) {
    return (
      <ExamplePreview label="Example results">
        <ul className="grid gap-3">
          {EXAMPLE_JOBS.map((job) => (
            <JobCard key={job.url} job={job} onCheckFit={() => {}} />
          ))}
        </ul>
      </ExamplePreview>
    );
  }

  return (
    <div className="grid gap-4">
      {loading && <ProgressChips messages={progress} done={false} />}

      {result && (
        <div className="grid gap-4" data-testid="job-search-results">
          {result.jobs.length > 0 ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <p className="text-muted">
                  <span className="font-semibold text-ink">{result.jobs.length} current jobs</span> in{" "}
                  {result.location_label}
                  {seconds ? ` · found in ${seconds}s` : ""} · best fit first
                </p>
                <label className="flex items-center gap-2 text-muted">
                  <input
                    type="checkbox"
                    checked={hideDealBreakers}
                    onChange={(e) => setHideDealBreakers(e.target.checked)}
                    className="h-4 w-4 rounded border-line accent-[var(--brand)]"
                  />
                  Hide jobs with deal-breakers
                </label>
              </div>
              <ul className="grid gap-3">
                {shown.map((job) => (
                  <JobCard key={job.url} job={job} onCheckFit={() => onCheckFit(job)} />
                ))}
              </ul>
              {shown.length === 0 && <p className="text-sm text-muted">Every job here has a deal-breaker.</p>}
              <p className="text-xs text-muted">
                Searched for {result.plan.roles.join(", ")} ({result.plan.seniority}) on {result.plan.job_sites.join(", ")}.
              </p>
              {progress.length > 1 && <ProgressChips messages={progress} done />}
            </>
          ) : (
            <div className="rounded-2xl border border-warn/30 bg-warn-soft p-5 text-sm text-warn">
              No current jobs could be found for {result.location_label} this time. Many job sites block automated
              reading, so try a nearby city, or use the job-board searches below.
            </div>
          )}

          <SearchLinks links={result.search_links} />
        </div>
      )}
    </div>
  );
}
