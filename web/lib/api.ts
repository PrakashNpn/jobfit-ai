import type { FetchedJob, FitReport, JobSearchResult, Resume, Usage } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("Can't reach the JobFit AI server. Is it running?");
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res));
  }
  return res.json() as Promise<T>;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    // FastAPI validation errors come back as a list
    if (Array.isArray(body.detail)) {
      const field = body.detail[0]?.loc?.at(-1);
      if (field === "job_text") return "The job posting looks too short or too long.";
      if (field === "resume_text") return "Your resume looks too short or too long.";
    }
  } catch {
    // fall through
  }
  return `Something went wrong (error ${res.status}). Please try again.`;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function parseResume(file: File): Promise<Resume> {
  const form = new FormData();
  form.append("file", file);
  const data = await request<{ filename: string; text: string }>("/resume/parse", {
    method: "POST",
    body: form,
  });
  return { filename: data.filename, text: data.text };
}

export function fetchJob(url: string): Promise<FetchedJob> {
  return postJson<FetchedJob>("/job/fetch", { url });
}

/**
 * Smart job search. The server streams one JSON object per line: progress messages while it works,
 * then the result (or an error). `onProgress` receives each progress message.
 */
export async function searchJobs(
  resumeText: string,
  location: string,
  onProgress: (message: string) => void,
): Promise<JobSearchResult> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/jobs/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text: resumeText, location }),
    });
  } catch {
    throw new ApiError("Can't reach the JobFit AI server. Is it running?");
  }
  if (!res.ok || !res.body) throw new ApiError(await errorMessage(res));

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (value) buffer += value;
    const lines = buffer.split("\n");
    buffer = done ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "progress") onProgress(event.message);
      else if (event.type === "error") throw new ApiError(event.message);
      else if (event.type === "result") return event.data as JobSearchResult;
    }
    if (done) break;
  }
  throw new ApiError("The search ended without a result. Please try again.");
}

export function analyze(resumeText: string, jobText: string): Promise<FitReport> {
  return postJson<FitReport>("/analyze", { resume_text: resumeText, job_text: jobText });
}

/**
 * Stream a cover letter: `onText` receives the full text so far each time a new piece arrives.
 * Resolves with the finished letter.
 */
export async function streamCoverLetter(
  resumeText: string,
  jobText: string,
  candidateName: string,
  onText: (textSoFar: string) => void,
): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/cover-letter/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: resumeText,
        job_text: jobText,
        candidate_name: candidateName.trim() || null,
      }),
    });
  } catch {
    throw new ApiError("Can't reach the JobFit AI server. Is it running?");
  }
  if (!res.ok || !res.body) {
    throw new ApiError(await errorMessage(res));
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let text = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    text += value;
    onText(text);
  }
  return text.trim();
}

export function getUsage(): Promise<Usage> {
  return request<Usage>("/usage", { method: "GET" });
}

/**
 * Ping the API until it answers. Free hosting can put the API to sleep; calling this as soon as
 * the page opens starts it waking while the visitor is still adding their resume.
 */
export async function wakeServer(maxWaitMs = 90_000): Promise<boolean> {
  const deadline = Date.now() + maxWaitMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
      if (res.ok) return true;
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  return false;
}
