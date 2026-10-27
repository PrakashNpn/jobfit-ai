/**
 * README screenshots. Skipped in normal runs; regenerate with:
 *   SCREENSHOTS=1 npx playwright test screenshots --project=desktop
 */
import { expect, test } from "@playwright/test";

import { REPORT, mockApi } from "./fixtures";

test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to regenerate README screenshots");

const OUT = "../docs";

const LETTER = `Dear Hiring Team,

I am applying for the AI Engineer role at Nimbus Rentals. I have four years of full-stack experience with TypeScript, React and Node.js, and for the past year I have focused on LLM features, which matches the AI tools you want to build for renters and your support team.

At Fictional Learning Co., I added a RAG chatbot that answers student questions from the course catalogue, and automated weekly reporting with n8n, saving the operations team about 4 hours per week.

I would welcome the chance to discuss how I can help Nimbus Rentals.

Best regards,
Alex Tan`;

function saved(id: string, daysAgo: number, title: string, company: string, location: string, score: number, verdict: string, thai = false) {
  return {
    id,
    savedAt: new Date(Date.now() - daysAgo * 86_400_000).toISOString(),
    jobText: `${title} at ${company}`,
    report: {
      ...REPORT,
      verdict,
      job: { ...REPORT.job, title, company, location, thai_language_required: thai },
      match: { ...REPORT.match, fit_score: score },
    },
  };
}

test("README screenshots", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mockApi(page);
  await page.route("http://localhost:8999/cover-letter/stream", (route) =>
    route.fulfill({ body: LETTER, contentType: "text/plain; charset=utf-8" }),
  );
  await page.goto("/");
  await page.evaluate((jobs) => {
    localStorage.clear();
    localStorage.setItem("jobfit.history", JSON.stringify(jobs));
  }, [
    saved("a", 1, "Full Stack Web Application Developer", "EVEANDBOY", "Bangkok", 84, "strong"),
    saved("b", 2, "Senior Backend Engineer (Go)", "Lanna Logistics", "Chiang Mai", 18, "weak", true),
    saved("c", 3, "Frontend Engineer", "RENDY Innovation", "Pathum Wan, Bangkok", 78, "possible"),
  ]);
  await page.reload();
  await page.screenshot({ path: `${OUT}/screenshot-home.png` });

  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("button", { name: "Try a sample job" }).click();
  await page.getByRole("button", { name: "Check my fit" }).click();
  await page.getByPlaceholder("Your name (optional)").fill("Alex Tan");
  await page.getByRole("button", { name: /Write my cover letter/ }).click();
  await expect(page.getByLabel("Cover letter")).toHaveValue(/Alex Tan/);

  await page.locator("section", { hasText: "Your fit" }).screenshot({ path: `${OUT}/screenshot-result.png` });
  await page.locator("section", { hasText: "Cover letter" }).last().screenshot({ path: `${OUT}/screenshot-cover-letter.png` });
  await page.locator("#my-jobs").screenshot({ path: `${OUT}/screenshot-my-jobs.png` });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("section", { hasText: "Your fit" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/screenshot-mobile.png` });
});

test("README screenshot: Find jobs for me", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1250 });
  await mockApi(page);
  const job = (n: number, title: string, company: string, location: string, posted: string, score: number,
               verdict: string, reason: string, deal: string[] = []) => ({
    url: `https://th.jobsdb.com/job/9547${n}`, site: "th.jobsdb.com", title, company, location, posted,
    fit_score: score, verdict, reason, deal_breakers: deal, summary: title,
  });
  const result = {
    location_label: "Bangkok, Thailand", pages_read: ["https://th.jobsdb.com/full-stack-developer-jobs"], pages_skipped: 1, index_results: 0,
    plan: { roles: ["Full Stack Developer", "AI Engineer"], seniority: "mid-level", location_label: "Bangkok, Thailand",
            country_code: "th", job_sites: ["th.jobsdb.com", "jobthai.com", "linkedin.com"] },
    jobs: [
      job(1, "Full-Stack Developer (Next.js / Node.js)", "Lumen Labs", "Sathon, Bangkok (Hybrid)", "1 day ago", 86, "strong", "Your Next.js, TypeScript and Node.js work matches every core requirement."),
      job(2, "AI Engineer (LLM Applications)", "Kite Analytics", "Pathum Wan, Bangkok", "2 days ago", 80, "strong", "Your RAG chatbot and Claude agent work fit this LLM role closely."),
      job(3, "Full Stack Developer (Golang/React)", "Harbour Tech", "Chatuchak, Bangkok", "3 days ago", 58, "possible", "Strong React fit; Go would be new, so show how fast you learn.", ["Go required"]),
      job(4, "Senior Java Developer", "Meridian Insurance", "Din Daeng, Bangkok", "5 days ago", 22, "weak", "This role needs Java and 8+ years, which your resume doesn't show.", ["Java required", "8+ years"]),
    ],
    search_links: [
      { role: "Full Stack Developer", site: "th.jobsdb.com", url: "https://www.google.com/search?q=a" },
      { role: "Full Stack Developer", site: "jobthai.com", url: "https://www.google.com/search?q=b" },
    ],
  };
  const lines = [
    "Reading your resume and choosing job titles and job sites…",
    "Looking for Full Stack Developer and AI Engineer jobs in Bangkok, Thailand on th.jobsdb.com, jobthai.com, linkedin.com",
    "Searching: Full Stack Developer jobs Bangkok jobsdb",
    "Searching: AI Engineer jobs Bangkok jobsdb",
    "Found 4 job lists and 0 single postings. Reading the lists…",
    "Scoring 30 jobs against your resume…",
  ].map((message) => ({ type: "progress", message }));
  await page.route("http://localhost:8999/jobs/search", (route) =>
    route.fulfill({ body: [...lines, { type: "result", data: result }].map((l) => JSON.stringify(l)).join("\n") + "\n", contentType: "application/x-ndjson" }),
  );
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("tab", { name: /Find jobs for me/ }).click();
  await page.getByLabel(/Where do you want to work/).fill("Bangkok");
  await page.getByRole("button", { name: /Find jobs for me/ }).click();
  await expect(page.getByTestId("job-search-results")).toBeVisible();
  await expect(page.getByRole("button", { name: "Find jobs for me" })).toBeEnabled();
  await page.waitForTimeout(300); // let the button's fade-in finish
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${OUT}/screenshot-find-jobs.png` });
});
