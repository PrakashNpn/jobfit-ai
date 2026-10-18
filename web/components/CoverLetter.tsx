"use client";

import { useState } from "react";

import { ApiError, writeCoverLetter } from "@/lib/api";

type Props = {
  resumeText: string;
  jobText: string;
  onUsed: () => void;
};

export default function CoverLetter({ resumeText, jobText, onUsed }: Props) {
  const [name, setName] = useState("");
  const [letter, setLetter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setLetter(await writeCoverLetter(resumeText, jobText, name));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
      onUsed();
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(letter);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
        />
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          {loading ? "Writing…" : letter ? "Write another version" : "✉️ Write my cover letter"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {letter && (
        <div className="relative">
          <textarea
            value={letter}
            onChange={(e) => setLetter(e.target.value)}
            rows={14}
            className="w-full rounded-xl border border-slate-300 bg-white p-4 text-sm leading-relaxed focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
          <button
            type="button"
            onClick={copy}
            className="absolute right-3 top-3 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <p className="mt-1 text-xs text-slate-500">
            You can edit the letter here. Check every claim before you send it.
          </p>
        </div>
      )}
    </div>
  );
}
