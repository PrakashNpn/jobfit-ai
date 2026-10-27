"use client";

import { useRef, useState } from "react";

import { ApiError, parseResume } from "@/lib/api";
import { SAMPLE_RESUME } from "@/lib/sample";
import type { Resume } from "@/lib/types";

import Spinner from "./Spinner";
import { btnLink, btnSecondary, inputCls } from "./ui";

/** The saved resume, shown compactly in the top bar. */
export function ResumeChip({ resume, onChange }: { resume: Resume; onChange: (resume: Resume | null) => void }) {
  const kind = resume.filename.toLowerCase().endsWith(".pdf") ? "PDF" : "TXT";
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-3 text-[13px]">
      <span className="grid h-6 shrink-0 place-items-center rounded-full bg-brand-soft px-2 font-mono text-[10px] font-semibold text-brand">
        {kind}
      </span>
      <span title={`${resume.text.length.toLocaleString()} characters · saved in this browser only`} className="min-w-0 max-w-[7rem] truncate font-medium text-ink sm:max-w-[14rem]">
        {resume.filename}
      </span>
      <button type="button" onClick={() => onChange(null)} className="shrink-0 font-semibold text-brand hover:underline">
        Change
      </button>
    </div>
  );
}

/** Upload or paste a resume (shown until one is saved). */
export default function ResumeInput({ onChange }: { onChange: (resume: Resume) => void }) {
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

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 rounded-xl bg-surface-2 p-1 text-sm">
        {(["upload", "paste"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-lg px-3 py-1.5 font-medium transition ${mode === m ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"}`}
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
          className="flex w-full flex-col items-center gap-1 rounded-xl border-2 border-dashed border-line bg-surface-2/50 px-4 py-5 text-muted transition hover:border-brand hover:bg-brand-soft/40 disabled:opacity-60"
        >
          <span className="flex items-center gap-2 font-semibold text-ink">
            {loading && <Spinner />}
            {loading ? "Reading your resume…" : "Choose your resume"}
          </span>
          <span className="text-xs">PDF, Markdown or text · up to 5 MB</span>
        </button>
      ) : (
        <div className="space-y-2">
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={7}
            placeholder="Paste the text of your resume here…"
            className={inputCls}
          />
          <button
            type="button"
            disabled={pasted.trim().length < 20}
            onClick={() => onChange({ filename: "Pasted resume", text: pasted.trim() })}
            className={`${btnSecondary} w-full`}
          >
            Use this resume
          </button>
        </div>
      )}

      <input ref={fileInput} type="file" accept=".pdf,.md,.txt" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} />

      {error && <p className="text-sm text-bad">{error}</p>}

      <p className="text-xs text-muted">
        No resume handy?{" "}
        <button type="button" onClick={() => onChange(SAMPLE_RESUME)} className={btnLink}>
          Use a sample resume
        </button>
      </p>
    </div>
  );
}
