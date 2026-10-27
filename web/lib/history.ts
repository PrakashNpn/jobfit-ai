import type { FitReport } from "./types";

/** One analysed job, kept in this browser's localStorage (never sent to the server). */
export type SavedJob = {
  id: string;
  savedAt: string; // ISO date
  jobText: string;
  report: FitReport;
};

const KEY = "jobfit.history";
const MAX_JOBS = 30;

export function loadHistory(): SavedJob[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as SavedJob[]) : [];
  } catch {
    return [];
  }
}

function persist(jobs: SavedJob[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(jobs));
  } catch {
    // storage full or unavailable: history just isn't remembered
  }
}

/** Add an analysis to the top of the list. Re-analysing the same posting replaces the old entry. */
export function addToHistory(jobs: SavedJob[], jobText: string, report: FitReport): SavedJob[] {
  const entry: SavedJob = {
    id: crypto.randomUUID(),
    savedAt: new Date().toISOString(),
    jobText,
    report,
  };
  const next = [entry, ...jobs.filter((j) => j.jobText.trim() !== jobText.trim())].slice(0, MAX_JOBS);
  persist(next);
  return next;
}

export function removeFromHistory(jobs: SavedJob[], id: string): SavedJob[] {
  const next = jobs.filter((j) => j.id !== id);
  persist(next);
  return next;
}

export function clearHistory(): SavedJob[] {
  persist([]);
  return [];
}
