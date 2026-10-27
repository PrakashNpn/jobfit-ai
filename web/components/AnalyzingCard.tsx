"use client";

import { useEffect, useState } from "react";

import Spinner from "./Spinner";
import { Panel } from "./ui";

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
    <Panel role="status" aria-live="polite">
      <div className="flex items-center gap-3 font-semibold text-brand">
        <Spinner className="h-5 w-5" />
        <p>{STEPS[step]}</p>
      </div>
      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-brand transition-all duration-[2500ms] ease-linear"
          style={{ width: `${((step + 1) / STEPS.length) * 90}%` }}
        />
      </div>
      <ul className="mt-4 grid gap-1.5 text-sm sm:grid-cols-2">
        {STEPS.map((label, i) => (
          <li key={label} className={i <= step ? "text-ink" : "text-muted/60"}>
            <span className={i < step ? "text-good" : ""}>{i < step ? "✓" : i === step ? "•" : "○"}</span>{" "}
            {label.replace("…", "")}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-muted">This usually takes about 10 seconds.</p>
    </Panel>
  );
}
