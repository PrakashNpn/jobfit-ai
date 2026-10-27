"use client";

import { useState } from "react";

import { ApiError, streamCoverLetter } from "@/lib/api";

import Spinner from "./Spinner";
import { btnPrimary, inputCls } from "./ui";

type Props = {
  resumeText: string;
  jobText: string;
  onUsed: () => void;
};

export default function CoverLetter({ resumeText, jobText, onUsed }: Props) {
  const [name, setName] = useState("");
  const [letter, setLetter] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setStreaming(true);
    setError(null);
    setLetter("");
    try {
      const final = await streamCoverLetter(resumeText, jobText, name, setLetter);
      setLetter(final);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setStreaming(false);
      onUsed();
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const waitingForFirstWords = streaming && !letter;

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          aria-label="Your name"
          className={`${inputCls} sm:flex-1`}
        />
        <button type="button" onClick={generate} disabled={streaming} aria-busy={streaming} className={btnPrimary}>
          {streaming ? (
            <>
              <Spinner />
              Writing your letter…
            </>
          ) : letter ? (
            "Write another version"
          ) : (
            "Write my cover letter"
          )}
        </button>
      </div>

      {error && <p className="text-sm text-bad">{error}</p>}

      {waitingForFirstWords && (
        <div role="status" aria-live="polite" className="space-y-3 rounded-xl border border-line p-5">
          <p className="text-sm text-muted">Starting your letter…</p>
          <div className="space-y-2.5 motion-safe:animate-pulse">
            {["w-1/3", "w-full", "w-11/12", "w-full", "w-4/5"].map((width, i) => (
              <div key={i} className={`h-2.5 rounded bg-surface-2 ${width}`} />
            ))}
          </div>
        </div>
      )}

      {streaming && letter && (
        <div
          aria-live="off"
          data-testid="cover-letter-streaming"
          className="whitespace-pre-wrap rounded-xl border border-brand/30 bg-surface p-5 text-sm leading-relaxed text-ink"
        >
          {letter}
          <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 bg-brand motion-safe:animate-pulse" />
        </div>
      )}

      {letter && !streaming && (
        <div className="relative">
          <textarea
            value={letter}
            onChange={(e) => setLetter(e.target.value)}
            rows={14}
            aria-label="Cover letter"
            className={`${inputCls} p-5 leading-relaxed`}
          />
          <button
            type="button"
            onClick={copy}
            className="absolute right-3 top-3 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-semibold text-ink hover:bg-surface-2"
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <p className="mt-1.5 text-xs text-muted">You can edit the letter here. Check every claim before you send it.</p>
        </div>
      )}
    </div>
  );
}
