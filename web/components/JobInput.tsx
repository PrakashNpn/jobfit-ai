"use client";

import { type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { ApiError, fetchJob } from "@/lib/api";
import { SAMPLE_JOB } from "@/lib/sample";
import type { FetchedJob } from "@/lib/types";

import Spinner from "./Spinner";
import { btnLink } from "./ui";

type Props = {
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
  /** Shown at the right of the bottom row, e.g. the "Check my fit" button. */
  action?: ReactNode;
};

/** True when the box holds a single link rather than a job description. */
export function looksLikeLink(text: string): boolean {
  const t = text.trim();
  return /^(https?:\/\/)?[\w.-]+\.[a-z]{2,}\/\S*$/i.test(t) && !/\s/.test(t);
}

export default function JobInput({ value, onChange, disabled, action }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<FetchedJob | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  // Grow with the text (up to max-h, then scroll) instead of showing a resize grip.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

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
    <div className="space-y-3">
      <div className="relative">
        <textarea
          ref={box}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onPaste={handlePaste}
          disabled={disabled || loading}
          rows={5}
          aria-label="Job posting"
          placeholder={"Paste a JobsDB job link, or the full job description…\n\ne.g. https://th.jobsdb.com/job/95320999"}
          className="block max-h-[26rem] min-h-[7.5rem] w-full resize-none bg-transparent text-[15px] leading-relaxed text-ink placeholder:text-muted/70 focus:outline-none disabled:opacity-60"
        />
        {loading && (
          <div
            role="status"
            aria-live="polite"
            className="absolute inset-0 flex items-center justify-center gap-2 rounded-xl bg-surface/85 text-sm font-semibold text-brand"
          >
            <Spinner className="h-5 w-5" />
            Loading the job from JobsDB…
          </div>
        )}
      </div>

      {isLink && !loading && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-brand-soft px-3 py-2 text-sm text-ink">
          <span>That looks like a link.</span>
          <button type="button" onClick={() => load(value)} className="rounded-lg bg-brand px-3 py-1 font-semibold text-brand-ink hover:brightness-110">
            Load job details
          </button>
        </div>
      )}

      {loaded && (
        <p className="text-xs text-good">
          ✓ Loaded from JobsDB: <span className="font-semibold">{loaded.title}</span>
          {loaded.company ? ` · ${loaded.company}` : ""}.{" "}
          <a href={loaded.url} target="_blank" rel="noreferrer" className="underline">
            View original
          </a>
          . Check the text above, then continue.
        </p>
      )}

      {error && <p className="text-sm text-bad">{error}</p>}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <p className="text-xs text-muted">
          JobsDB links load automatically.{" "}
          <button type="button" onClick={() => handleChange(SAMPLE_JOB)} className={btnLink}>
            Try a sample job
          </button>
        </p>
        {action}
      </div>
    </div>
  );
}
