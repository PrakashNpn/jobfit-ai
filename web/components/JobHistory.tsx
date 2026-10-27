"use client";

import { useState } from "react";

import type { SavedJob } from "@/lib/history";

import { ScoreRing, VerdictPill } from "./ui";

type SortKey = "recent" | "score";

type Props = {
  jobs: SavedJob[];
  activeId: string | null;
  onOpen: (job: SavedJob) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export default function JobHistory({ jobs, activeId, onOpen, onRemove, onClear }: Props) {
  const [sort, setSort] = useState<SortKey>("recent");
  const [confirming, setConfirming] = useState(false);

  const sorted =
    sort === "score" ? [...jobs].sort((a, b) => b.report.match.fit_score - a.report.match.fit_score) : jobs;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-muted">
          {jobs.length} job{jobs.length === 1 ? "" : "s"} checked · saved in this browser only
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-muted">
            Sort
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              className="rounded-lg border border-line bg-surface px-2 py-1 text-sm text-ink"
            >
              <option value="recent">Most recent</option>
              <option value="score">Best fit</option>
            </select>
          </label>
          {confirming ? (
            <span className="flex items-center gap-2">
              <button type="button" onClick={() => { onClear(); setConfirming(false); }} className="font-semibold text-bad hover:underline">
                Remove all
              </button>
              <button type="button" onClick={() => setConfirming(false)} className="text-muted hover:text-ink">
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" onClick={() => setConfirming(true)} className="text-muted hover:text-bad">
              Clear all
            </button>
          )}
        </div>
      </div>

      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
        {sorted.map((job) => {
          const { report } = job;
          const active = job.id === activeId;
          return (
            <li key={job.id} className={`flex items-center gap-3 px-3 py-3 transition sm:px-4 ${active ? "bg-brand-soft/60" : "bg-surface hover:bg-surface-2/60"}`}>
              <ScoreRing score={report.match.fit_score} size={44} />
              <button type="button" onClick={() => onOpen(job)} className="min-w-0 flex-1 text-left">
                <p className="truncate font-semibold text-ink">{report.job.title}</p>
                <p className="truncate text-xs text-muted">
                  {[report.job.company, report.job.location, formatDate(job.savedAt)].filter(Boolean).join(" · ")}
                </p>
              </button>
              <span className="hidden sm:inline">
                <VerdictPill verdict={report.verdict} />
              </span>
              {report.job.thai_language_required && (
                <span className="hidden shrink-0 rounded-full bg-bad-soft px-2.5 py-0.5 text-xs font-semibold text-bad sm:inline">Thai</span>
              )}
              <button
                type="button"
                onClick={() => onRemove(job.id)}
                aria-label={`Remove ${report.job.title}`}
                className="shrink-0 rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-bad"
              >
                ✕
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
