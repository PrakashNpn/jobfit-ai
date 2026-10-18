import type { FetchedJob, FitReport, Resume, Usage } from "./types";

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

export function analyze(resumeText: string, jobText: string): Promise<FitReport> {
  return postJson<FitReport>("/analyze", { resume_text: resumeText, job_text: jobText });
}

export async function writeCoverLetter(
  resumeText: string,
  jobText: string,
  candidateName: string,
): Promise<string> {
  const data = await postJson<{ cover_letter: string }>("/cover-letter", {
    resume_text: resumeText,
    job_text: jobText,
    candidate_name: candidateName.trim() || null,
  });
  return data.cover_letter;
}

export function getUsage(): Promise<Usage> {
  return request<Usage>("/usage", { method: "GET" });
}
