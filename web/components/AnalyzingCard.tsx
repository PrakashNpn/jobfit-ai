"use client";

import { useEffect, useState } from "react";

import Spinner from "./Spinner";

const STEPS = [
  "Reading the job posting…",
  "Comparing it with your resume…",
  "Checking for red flags…",
  "Writing your verdict…",
];
const STEP_MS = 2500;

/** Shown while the fit check runs (about 10 seconds). */
export default function AnalyzingCard() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), STEP_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <section
      role="status"
      aria-live="polite"
      className="rounded-2xl border border-indigo-200 bg-white p-6 shadow-sm"
    >
      <div className="flex items-center gap-3 text-indigo-700">
        <Spinner className="h-5 w-5" />
        <p className="font-medium">{STEPS[step]}</p>
      </div>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-indigo-100">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-[2500ms] ease-linear"
          style={{ width: `${((step + 1) / STEPS.length) * 90}%` }}
        />
      </div>

      <ul className="mt-4 space-y-1.5 text-sm">
        {STEPS.map((label, i) => (
          <li key={label} className={i <= step ? "text-slate-700" : "text-slate-400"}>
            {i < step ? "✓" : i === step ? "•" : "○"} {label.replace("…", "")}
          </li>
        ))}
      </ul>

      <p className="mt-4 text-xs text-slate-500">This usually takes about 10 seconds.</p>
    </section>
  );
}
