"use client";

import { useEffect, useState } from "react";

import { wakeServer } from "@/lib/api";

import Spinner from "./Spinner";

const SHOW_AFTER_MS = 2500;

type Status = "checking" | "waking" | "ready" | "ready-after-wait" | "down";

/**
 * Wakes the API when the page opens. Shows a banner only if that takes a while,
 * so a sleeping free-tier server looks like "starting", not "broken".
 */
export default function ServerStatus({ onReady }: { onReady?: () => void }) {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const slow = setTimeout(() => !cancelled && setStatus((s) => (s === "checking" ? "waking" : s)), SHOW_AFTER_MS);

    wakeServer().then((ok) => {
      if (cancelled) return;
      clearTimeout(slow);
      setStatus((s) => (!ok ? "down" : s === "waking" ? "ready-after-wait" : "ready"));
      if (ok) onReady?.();
    });

    return () => {
      cancelled = true;
      clearTimeout(slow);
    };
  }, [onReady]);

  useEffect(() => {
    if (status !== "ready-after-wait") return;
    const hide = setTimeout(() => setStatus("ready"), 4000);
    return () => clearTimeout(hide);
  }, [status]);

  if (status === "checking" || status === "ready") return null;

  const styles = {
    waking: "border-warn/30 bg-warn-soft text-warn",
    "ready-after-wait": "border-good/30 bg-good-soft text-good",
    down: "border-bad/30 bg-bad-soft text-bad",
  }[status];

  return (
    <div role="status" aria-live="polite" className={`border-b ${styles}`}>
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-sm font-medium sm:px-6">
        {status === "waking" && (
          <>
            <Spinner />
            <span>
              Starting the server. The free hosting plan sleeps when nobody&apos;s using it, so this can take up to a
              minute. You can add your resume in the meantime.
            </span>
          </>
        )}
        {status === "ready-after-wait" && <span>✓ Server is ready.</span>}
        {status === "down" && <span>The server isn&apos;t responding right now. Please try again in a few minutes.</span>}
      </div>
    </div>
  );
}
