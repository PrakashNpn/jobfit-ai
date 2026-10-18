"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AnalyzingCard from "@/components/AnalyzingCard";
import CoverLetter from "@/components/CoverLetter";
import FitResult from "@/components/FitResult";
import JobInput, { looksLikeLink } from "@/components/JobInput";
import ResumeInput from "@/components/ResumeInput";
import Spinner from "@/components/Spinner";
import { ApiError, analyze, getUsage } from "@/lib/api";
import type { FitReport, Resume, Usage } from "@/lib/types";

const RESUME_KEY = "jobfit.resume";

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

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="mb-4 flex items-center gap-3 text-lg font-semibold text-slate-900">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-sm text-white">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function Home() {
  const [resume, setResume] = useState<Resume | null>(null);
  const [jobText, setJobText] = useState("");
  const [report, setReport] = useState<FitReport | null>(null);
  const [analyzedJob, setAnalyzedJob] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const refreshUsage = useCallback(() => {
    getUsage().then(setUsage).catch(() => setUsage(null));
  }, []);

  // Restore the resume saved in this browser, and show today's usage.
  useEffect(() => {
    const saved = loadResume();
    if (saved) setResume(saved); // eslint-disable-line react-hooks/set-state-in-effect
    refreshUsage();
  }, [refreshUsage]);

  function updateResume(next: Resume | null) {
    setResume(next);
    saveResume(next);
  }

  const outOfAnalyses = usage?.remaining === 0;
  const jobIsLink = looksLikeLink(jobText);
  const canAnalyze = !!resume && jobText.trim().length >= 20 && !jobIsLink && !loading && !outOfAnalyses;

  async function runAnalysis() {
    if (!resume) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const result = await analyze(resume.text, jobText);
      setReport(result);
      setAnalyzedJob(jobText);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
      refreshUsage();
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 py-10 sm:py-14">
      <header className="space-y-3 text-center">
        <p className="text-sm font-semibold tracking-wide text-indigo-600">JOBFIT AI</p>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Is this job a good fit for you?
        </h1>
        <p className="mx-auto max-w-xl text-slate-600">
          Paste a job posting. In about 10 seconds, see your fit score, the skills you have and the ones you&apos;re
          missing, any red flags, and get a tailored cover letter.
        </p>
      </header>

      <Step n={1} title="Your resume">
        <ResumeInput resume={resume} onChange={updateResume} />
      </Step>

      <Step n={2} title="The job posting">
        <JobInput value={jobText} onChange={setJobText} disabled={loading} />
      </Step>

      <div className="space-y-2 text-center">
        <button
          type="button"
          onClick={runAnalysis}
          disabled={!canAnalyze}
          aria-busy={loading}
          className={`inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3.5 text-base font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:cursor-not-allowed sm:w-auto ${loading ? "" : "disabled:opacity-40"}`}
        >
          {loading ? (
            <>
              <Spinner className="h-5 w-5" />
              Checking your fit…
            </>
          ) : (
            "Check my fit"
          )}
        </button>
        {!resume && <p className="text-sm text-slate-500">Add your resume to get started.</p>}
        {resume && jobIsLink && (
          <p className="text-sm text-slate-500">Click “Load job details” first, so we can read the job from the link.</p>
        )}
        {usage?.limit != null && (
          <p className="text-sm text-slate-500">
            {outOfAnalyses
              ? "You've used all your free analyses for today. Come back tomorrow!"
              : `${usage.remaining} of ${usage.limit} free analyses left today`}
          </p>
        )}
        {error && <p className="text-sm font-medium text-red-600">{error}</p>}
      </div>

      {loading && <AnalyzingCard />}

      {report && resume && !loading && (
        <div ref={resultRef} className="space-y-6 scroll-mt-6">
          <Step n={3} title="Your fit">
            <FitResult report={report} />
          </Step>
          <Step n={4} title="Cover letter">
            <CoverLetter resumeText={resume.text} jobText={analyzedJob} onUsed={refreshUsage} />
          </Step>
        </div>
      )}

      <footer className="pt-6 text-center text-sm text-slate-500">
        Your resume stays in your browser. It is sent only when you click a button and is never stored.
        <br />
        Built with Next.js, FastAPI, LangChain and Claude ·{" "}
        <a href="https://github.com/PrakashNpn/jobfit-ai" className="font-medium text-indigo-600 hover:underline">
          Source on GitHub
        </a>
      </footer>
    </main>
  );
}
