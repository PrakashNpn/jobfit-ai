"use client";

import { useState } from "react";

import { ApiError, fetchJob } from "@/lib/api";
import { SAMPLE_JOB } from "@/lib/sample";
import type { FetchedJob } from "@/lib/types";

import Spinner from "./Spinner";

type Props = {
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
};

/** True when the box holds a single link rather than a job description. */
export function looksLikeLink(text: string): boolean {
  const t = text.trim();
  return /^(https?:\/\/)?[\w.-]+\.[a-z]{2,}\/\S*$/i.test(t) && !/\s/.test(t);
}

export default function JobInput({ value, onChange, disabled }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<FetchedJob | null>(null);

  async function load(url: string) {
    setLoading(true);
    setError(null);
    setLoaded(null);
    try {
      const job = await fetchJob(url.trim());
      onChange(job.text);
      setLoaded(job);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load that link. Please paste the job description.");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(text: string) {
    onChange(text);
    setError(null);
    if (loaded && text !== loaded.text) setLoaded(null);
  }

  function handlePaste(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    const pasted = e.clipboardData.getData("text");
    // Pasting a link into an empty box loads it straight away.
    if (!value.trim() && looksLikeLink(pasted)) {
      e.preventDefault();
      onChange(pasted.trim());
      load(pasted);
    }
  }

  const isLink = looksLikeLink(value);

  return (
    <div className="space-y-2">
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onPaste={handlePaste}
          disabled={disabled || loading}
          rows={10}
          placeholder={"Paste a JobsDB job link, or the full job description…\n\ne.g. https://th.jobsdb.com/job/95320999"}
          className="w-full rounded-xl border border-slate-300 bg-white p-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:bg-slate-50"
        />
        {loading && (
          <div
            role="status"
            aria-live="polite"
            className="absolute inset-0 flex items-center justify-center gap-2 rounded-xl bg-white/80 text-sm font-medium text-indigo-700"
          >
            <Spinner className="h-5 w-5" />
            Loading the job from JobsDB…
          </div>
        )}
      </div>

      {isLink && !loading && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-900">
          <span>That looks like a link.</span>
          <button
            type="button"
            onClick={() => load(value)}
            className="rounded-md bg-indigo-600 px-3 py-1 font-medium text-white hover:bg-indigo-500"
          >
            Load job details
          </button>
        </div>
      )}

      {loaded && (
        <p className="text-sm text-emerald-700">
          ✓ Loaded from JobsDB: <span className="font-medium">{loaded.title}</span>
          {loaded.company ? ` · ${loaded.company}` : ""}.{" "}
          <a href={loaded.url} target="_blank" rel="noreferrer" className="underline">
            View original
          </a>
          . Check the text above, then continue.
        </p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <p className="text-sm text-slate-500">
        JobsDB links load automatically. For LinkedIn and other sites, paste the description. Just looking?{" "}
        <button
          type="button"
          onClick={() => handleChange(SAMPLE_JOB)}
          className="font-medium text-indigo-600 hover:underline"
        >
          Try a sample job
        </button>
      </p>
    </div>
  );
}
