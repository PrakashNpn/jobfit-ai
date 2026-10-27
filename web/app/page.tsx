"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AnalyzingCard from "@/components/AnalyzingCard";
import CoverLetter from "@/components/CoverLetter";
import { FindJobsForm, FindJobsResults, useJobSearch } from "@/components/FindJobs";
import FitResult from "@/components/FitResult";
import JobHistory from "@/components/JobHistory";
import JobInput, { looksLikeLink } from "@/components/JobInput";
import Logo from "@/components/Logo";
import ResumeInput, { ResumeChip } from "@/components/ResumeInput";
import ServerStatus from "@/components/ServerStatus";
import Spinner from "@/components/Spinner";
import { Eyebrow, ExamplePreview, Panel, PanelTitle, btnPrimary } from "@/components/ui";
import { ApiError, analyze, fetchJob, getUsage } from "@/lib/api";
import { EXAMPLE_REPORT } from "@/lib/sample";
import { type SavedJob, addToHistory, clearHistory, loadHistory, removeFromHistory } from "@/lib/history";
import type { FitReport, FoundJob, Resume, Usage } from "@/lib/types";

const RESUME_KEY = "jobfit.resume";
const GITHUB_URL = "https://github.com/PrakashNpn/jobfit-ai";

type Mode = "check" | "find";

function loadResume(): Resume | null {
  try {
    const raw = localStorage.getItem(RESUME_KEY);
    return raw ? (JSON.parse(raw) as Resume) : null;
  } catch {
    return null;
  }
}

function saveResume(resume: Resume | null) {
  try {
    if (resume) localStorage.setItem(RESUME_KEY, JSON.stringify(resume));
    else localStorage.removeItem(RESUME_KEY);
  } catch {
    // storage unavailable (private mode): the resume just won't be remembered
  }
}

function EmptyResult() {
  return (
    <ExamplePreview label="Example report">
      <Panel>
        <FitResult report={EXAMPLE_REPORT} />
      </Panel>
    </ExamplePreview>
  );
}

export default function Home() {
  const [resume, setResume] = useState<Resume | null>(null);
  const [mode, setMode] = useState<Mode>("check");
  const [jobText, setJobText] = useState("");
  const [report, setReport] = useState<FitReport | null>(null);
  const [analyzedJob, setAnalyzedJob] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [history, setHistory] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const jobSearch = useJobSearch(resume?.text ?? null);

  const refreshUsage = useCallback(() => {
    getUsage().then(setUsage).catch(() => setUsage(null));
  }, []);

  // Restore what's saved in this browser, and show today's usage.
  useEffect(() => {
    const saved = loadResume();
    if (saved) setResume(saved); // eslint-disable-line react-hooks/set-state-in-effect
    setHistory(loadHistory());
    refreshUsage();
  }, [refreshUsage]);

  function updateResume(next: Resume | null) {
    setResume(next);
    saveResume(next);
  }

  function scrollToResult() {
    setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  const outOfAnalyses = usage?.remaining === 0;
  const jobIsLink = looksLikeLink(jobText);
  const canAnalyze = !!resume && jobText.trim().length >= 20 && !jobIsLink && !loading && !outOfAnalyses;

  async function runAnalysis(text: string = jobText) {
    if (!resume) return;
    setLoading(true);
    setError(null);
    setReport(null);
    scrollToResult();
    try {
      const result = await analyze(resume.text, text);
      const nextHistory = addToHistory(history, text, result);
      setHistory(nextHistory);
      setActiveId(nextHistory[0].id);
      setReport(result);
      setAnalyzedJob(text);
      scrollToResult();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
      refreshUsage();
    }
  }

  /** "Full fit check" on a search result: use the full posting where we can read it, else the card. */
  async function checkFoundJob(job: FoundJob) {
    setMode("check");
    const cardText = [job.title, job.company, [job.location, job.posted].filter(Boolean).join(" · "), "", job.summary]
      .filter((line) => line !== null)
      .join("\n");
    let text = cardText;
    if (/(^|\.)jobsdb\.com$/.test(new URL(job.url).hostname)) {
      setJobText(job.url);
      try {
        text = (await fetchJob(job.url)).text;
      } catch {
        // fall back to the card text
      }
    }
    setJobText(text);
    runAnalysis(text);
  }

  function openSaved(job: SavedJob) {
    setMode("check");
    setReport(job.report);
    setAnalyzedJob(job.jobText);
    setJobText(job.jobText);
    setActiveId(job.id);
    setError(null);
    scrollToResult();
  }

  function removeSaved(id: string) {
    setHistory((h) => removeFromHistory(h, id));
    if (id === activeId) {
      setActiveId(null);
      setReport(null);
    }
  }

  const usageNote =
    usage?.limit != null
      ? outOfAnalyses
        ? "No free analyses left today"
        : `${usage.remaining} of ${usage.limit} free today`
      : null;

  const checkButton = (
    <div className="flex w-full flex-col-reverse items-center gap-2 sm:w-auto sm:flex-row sm:gap-4">
      {usageNote && <span className={`text-xs ${outOfAnalyses ? "font-medium text-bad" : "text-muted"}`}>{usageNote}</span>}
      <button type="button" onClick={() => runAnalysis()} disabled={!canAnalyze} aria-busy={loading} className={`${btnPrimary} w-full sm:w-auto`}>
        {loading ? (
          <>
            <Spinner className="h-4 w-4" />
            Checking your fit…
          </>
        ) : (
          "Check my fit"
        )}
      </button>
    </div>
  );

  return (
    <div className="flex flex-1 flex-col">
      <nav className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Logo />
          <div className="flex min-w-0 items-center gap-5 text-sm font-medium text-muted">
            {history.length > 0 && (
              <a href="#my-jobs" className="hidden hover:text-ink sm:inline">
                My jobs <span className="font-mono tabular-nums text-ink">{history.length}</span>
              </a>
            )}
            {resume && <ResumeChip resume={resume} onChange={updateResume} />}
            <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hidden font-semibold text-ink hover:text-brand sm:inline">
              GitHub
            </a>
          </div>
        </div>
      </nav>
      <ServerStatus onReady={refreshUsage} />

      <main className="mx-auto grid w-full max-w-4xl flex-1 content-start gap-8 px-4 pb-16 pt-10 sm:px-6 sm:pt-16">
        <header className="mx-auto max-w-2xl space-y-3 text-center">
          <h1 className="text-balance font-display text-3xl font-extrabold tracking-tight text-ink sm:text-5xl sm:leading-[1.05]">
            Find the jobs worth applying to.
          </h1>
          <p className="text-balance text-[15px] leading-relaxed text-muted sm:text-base">
            Check any job against your resume in about 10 seconds, or let JobFit search a location and rank every
            posting by how well it fits you.
          </p>
        </header>

        <section aria-label="Start" className="overflow-hidden rounded-2xl border border-line bg-surface shadow-panel">
          {!resume && (
            <div className="space-y-3 border-b border-line bg-surface-2/40 p-5 sm:p-6">
              <Eyebrow>Step 1 · Your resume</Eyebrow>
              <ResumeInput onChange={updateResume} />
            </div>
          )}

          <div role="tablist" aria-label="Mode" className="flex gap-6 border-b border-line px-5 sm:px-6">
            {(
              [
                ["check", "Check a job"],
                ["find", "Find jobs for me"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => setMode(value)}
                className={`-mb-px border-b-2 py-3.5 text-sm font-semibold transition ${mode === value ? "border-brand text-ink" : "border-transparent text-muted hover:text-ink"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-5 sm:p-6">
            {mode === "check" ? (
              <div className="space-y-2">
                <JobInput value={jobText} onChange={setJobText} disabled={loading} action={checkButton} />
                {resume && jobIsLink && (
                  <p className="text-xs text-muted">Click “Load job details” first, so we can read the job from the link.</p>
                )}
                {error && (
                  <p role="alert" className="text-sm font-medium text-bad">
                    {error}
                  </p>
                )}
              </div>
            ) : (
              <FindJobsForm state={jobSearch} />
            )}
          </div>
        </section>

        <div ref={resultRef} className="grid min-w-0 scroll-mt-24 gap-6">
          {mode === "find" ? (
            <FindJobsResults state={jobSearch} onCheckFit={checkFoundJob} />
          ) : loading ? (
            <AnalyzingCard />
          ) : report && resume ? (
            <>
              <Panel>
                <PanelTitle>Your fit</PanelTitle>
                <FitResult report={report} />
              </Panel>
              <Panel>
                <PanelTitle>Cover letter</PanelTitle>
                <CoverLetter key={activeId ?? analyzedJob} resumeText={resume.text} jobText={analyzedJob} onUsed={refreshUsage} />
              </Panel>
            </>
          ) : (
            <EmptyResult />
          )}

          {history.length > 0 && (
            <Panel id="my-jobs" className="scroll-mt-24">
              <PanelTitle>My jobs</PanelTitle>
              <JobHistory
                jobs={history}
                activeId={activeId}
                onOpen={openSaved}
                onRemove={removeSaved}
                onClear={() => {
                  setHistory(clearHistory());
                  setActiveId(null);
                }}
              />
            </Panel>
          )}
        </div>
      </main>

      <footer className="border-t border-line bg-surface/70">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted sm:px-6">
          <p>Your resume and saved jobs stay in your browser. They&apos;re sent only for an analysis and never stored.</p>
          <p>
            Built with Next.js, FastAPI and Claude ·{" "}
            <a href={GITHUB_URL} className="font-semibold text-brand hover:underline">
              Source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
