import type { Page } from "@playwright/test";

export const REPORT = {
  verdict: "possible",
  verdict_reason: "You match the core stack, so apply, but address the FastAPI gap.",
  job: {
    title: "AI Engineer",
    company: "Nimbus Rentals",
    location: "Bangkok",
    work_type: "Full-time",
    salary_min_thb: 45000,
    salary_max_thb: 60000,
    min_years_experience: 2,
    required_skills: ["Python", "FastAPI", "RAG"],
    nice_to_have_skills: [],
    thai_language_required: false,
    english_required: true,
    summary: "Builds AI features for a rental marketplace.",
  },
  match: {
    fit_score: 72,
    matching_skills: ["RAG", "LLM APIs"],
    missing_skills: ["FastAPI"],
    red_flags: ["Python is listed only as scripting"],
    summary: "Good LLM experience; Python depth is the main gap.",
  },
};

export const LETTER = "Dear Hiring Team,\n\nI am applying for the AI Engineer role.\n\nBest regards,\nThi Han";

type MockOptions = { analyzeStatus?: number; analyzeDetail?: string; sleepingHealthChecks?: number };

/** Replace every backend call with a canned response. */
export async function mockApi(page: Page, options: MockOptions = {}) {
  const calls: string[] = [];
  await page.route("http://localhost:8999/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push(path);
    if (path === "/health") {
      // Simulate a sleeping free-tier server: fail the first N checks.
      if ((options.sleepingHealthChecks ?? 0) > calls.filter((c) => c === "/health").length - 1) {
        return route.abort("connectionrefused");
      }
      return route.fulfill({ json: { status: "ok" } });
    }
    if (path === "/usage") return route.fulfill({ json: { limit: 5, used: 0, remaining: 5 } });
    if (path === "/analyze") {
      if (options.analyzeStatus) {
        return route.fulfill({ status: options.analyzeStatus, json: { detail: options.analyzeDetail } });
      }
      return route.fulfill({ json: REPORT });
    }
    if (path === "/cover-letter/stream") {
      return route.fulfill({ body: LETTER, contentType: "text/plain; charset=utf-8" });
    }
    if (path === "/jobs/search") {
      const { location } = route.request().postDataJSON();
      const plan = {
        roles: ["Full Stack Developer", "AI Engineer"], seniority: "mid-level", location_label: location,
        country_code: null, job_sites: ["th.jobsdb.com", "jobthai.com", "linkedin.com"],
      };
      const found = (url: string, title: string, company: string, score: number, verdict: string, deal: string[]) => ({
        url, site: new URL(url).hostname, title, company, location: "Bangkok", posted: "2 days ago",
        fit_score: score, verdict, reason: `Reason for ${title}.`, deal_breakers: deal, summary: `${title} at ${company}.`,
      });
      const result = {
        location_label: location, plan, pages_read: ["https://th.jobsdb.com/full-stack-developer-jobs"], pages_skipped: 1,
        index_results: 0,
        jobs: location === "Nowhere" ? [] : [
          found("https://th.jobsdb.com/job/95470451", "Full-Stack Developer", "Lawcluster", 84, "strong", []),
          found("https://www.jobthai.com/th/company/job/1905143", "Java Developer", "BigCorp", 25, "weak", ["Java required", "8+ years"]),
        ],
        search_links: [{ role: "Full Stack Developer", site: "th.jobsdb.com", url: "https://www.google.com/search?q=x" }],
      };
      const lines = [
        { type: "progress", message: "Reading your resume and choosing job titles and job sites…" },
        { type: "progress", message: "Searching: Full Stack Developer jobs Bangkok" },
        { type: "result", data: result },
      ];
      return route.fulfill({ body: lines.map((l) => JSON.stringify(l)).join("\n") + "\n", contentType: "application/x-ndjson" });
    }
    if (path === "/job/fetch") {
      const { url } = route.request().postDataJSON();
      if (!String(url).includes("jobsdb.com")) {
        return route.fulfill({
          status: 422,
          json: { detail: "We can read JobsDB links. For other sites, please paste the job description." },
        });
      }
      return route.fulfill({
        json: {
          url: "https://th.jobsdb.com/job/95333770",
          title: "AI Engineer",
          company: "RENDY INNOVATION Co., Ltd.",
          location: "Pathum Wan, Bangkok",
          work_type: "Full time",
          salary: "฿40,000 – ฿50,000 per month",
          text: "AI Engineer\nRENDY INNOVATION Co., Ltd.\nPathum Wan, Bangkok\n\nBuild AI agent workflows with Claude.",
        },
      });
    }
    return route.fulfill({ status: 404, json: { detail: "not mocked" } });
  });
  return calls;
}
