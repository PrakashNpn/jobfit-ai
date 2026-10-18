"use client";

import { useRef, useState } from "react";

import { ApiError, parseResume } from "@/lib/api";
import { SAMPLE_RESUME } from "@/lib/sample";
import type { Resume } from "@/lib/types";

type Props = {
  resume: Resume | null;
  onChange: (resume: Resume | null) => void;
};

export default function ResumeInput({ resume, onChange }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [pasted, setPasted] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      onChange(await parseResume(file));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't read that file.");
    } finally {
      setLoading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (resume) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-emerald-900">✓ {resume.filename}</p>
          <p className="text-sm text-emerald-800">
            {resume.text.length.toLocaleString()} characters · saved in this browser only
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-sm font-medium text-emerald-900 hover:bg-emerald-100"
        >
          Change resume
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1 text-sm font-medium w-fit">
        {(["upload", "paste"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-md px-3 py-1.5 ${mode === m ? "bg-white shadow-sm text-slate-900" : "text-slate-600 hover:text-slate-900"}`}
          >
            {m === "upload" ? "Upload file" : "Paste text"}
          </button>
        ))}
      </div>

      {mode === "upload" ? (
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={loading}
          className="flex w-full flex-col items-center gap-1 rounded-xl border-2 border-dashed border-slate-300 bg-white px-4 py-8 text-slate-600 hover:border-indigo-400 hover:bg-indigo-50/40 disabled:opacity-60"
        >
          <span className="font-medium text-slate-900">
            {loading ? "Reading your resume…" : "Choose your resume"}
          </span>
          <span className="text-sm">PDF, Markdown or text · up to 5 MB</span>
        </button>
      ) : (
        <div className="space-y-2">
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={8}
            placeholder="Paste the text of your resume here…"
            className="w-full rounded-xl border border-slate-300 bg-white p-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
          <button
            type="button"
            disabled={pasted.trim().length < 20}
            onClick={() => onChange({ filename: "Pasted resume", text: pasted.trim() })}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Use this resume
          </button>
        </div>
      )}

      <input
        ref={fileInput}
        type="file"
        accept=".pdf,.md,.txt"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {error && <p className="text-sm text-red-600">{error}</p>}

      <p className="text-sm text-slate-500">
        No resume handy?{" "}
        <button
          type="button"
          onClick={() => onChange(SAMPLE_RESUME)}
          className="font-medium text-indigo-600 hover:underline"
        >
          Use a sample resume
        </button>
      </p>
    </div>
  );
}
