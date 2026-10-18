// Mirrors the backend's Pydantic models in app/schemas.py

export type JobPosting = {
  title: string;
  company: string | null;
  location: string | null;
  work_type: string | null;
  salary_min_thb: number | null;
  salary_max_thb: number | null;
  min_years_experience: number | null;
  required_skills: string[];
  nice_to_have_skills: string[];
  thai_language_required: boolean;
  english_required: boolean;
  summary: string;
};

export type MatchResult = {
  fit_score: number;
  matching_skills: string[];
  missing_skills: string[];
  red_flags: string[];
  summary: string;
};

export type Verdict = "strong" | "possible" | "weak";

export type FitReport = {
  job: JobPosting;
  match: MatchResult;
  verdict: Verdict;
  verdict_reason: string;
};

export type Usage = {
  limit: number | null;
  used: number;
  remaining: number | null;
};

export type Resume = {
  filename: string;
  text: string;
};

export type FetchedJob = {
  url: string;
  title: string;
  company: string | null;
  location: string | null;
  work_type: string | null;
  salary: string | null;
  text: string;
};
