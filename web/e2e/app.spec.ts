import { expect, test } from "@playwright/test";

import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
});

test("full flow: resume → job → fit report → cover letter → saved in My jobs", async ({ page }) => {
  await mockApi(page);
  await page.reload();

  const checkFit = page.getByRole("button", { name: "Check my fit" });
  await expect(checkFit).toBeDisabled();

  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await expect(page.getByText(/sample-resume/)).toBeVisible();
  await page.getByRole("button", { name: "Try a sample job" }).click();
  await checkFit.click();

  await expect(page.getByText("72", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Possible match: apply and address the gaps")).toBeVisible();
  await expect(page.getByText("฿45,000 – ฿60,000 / month")).toBeVisible();
  await expect(page.getByText("Python is listed only as scripting")).toBeVisible();

  await page.getByPlaceholder("Your name (optional)").fill("Thi Han");
  await page.getByRole("button", { name: /Write my cover letter/ }).click();
  await expect(page.getByLabel("Cover letter")).toHaveValue(/Best regards,\nThi Han/);

  const myJobs = page.locator("#my-jobs");
  await expect(myJobs.getByText("AI Engineer")).toBeVisible();
  await expect(myJobs.getByText(/1 job checked/)).toBeVisible();
});

test("saved jobs survive a reload and can be reopened", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("button", { name: "Try a sample job" }).click();
  await page.getByRole("button", { name: "Check my fit" }).click();
  await expect(page.locator("#my-jobs")).toBeVisible();

  await page.reload();
  await expect(page.getByText(/sample-resume/)).toBeVisible(); // resume remembered too
  await page.locator("#my-jobs").getByRole("button", { name: /^AI Engineer/ }).click();
  await expect(page.getByText("Possible match: apply and address the gaps")).toBeVisible();
});

test("pasting a JobsDB link loads the job description", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  const box = page.getByPlaceholder(/Paste a JobsDB job link/);
  await box.fill("https://th.jobsdb.com/job/95333770/apply?sol=abc");
  await page.getByRole("button", { name: "Load job details" }).click();

  await expect(box).toHaveValue(/Build AI agent workflows with Claude/);
  await expect(page.getByText(/Loaded from JobsDB/)).toBeVisible();
});

test("links from other sites get a friendly message", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  await page.getByPlaceholder(/Paste a JobsDB job link/).fill("https://www.linkedin.com/jobs/view/123/");
  await page.getByRole("button", { name: "Load job details" }).click();
  await expect(page.getByText(/For other sites, please paste the job description/)).toBeVisible();
});

test("API errors are shown to the user", async ({ page }) => {
  await mockApi(page, {
    analyzeStatus: 429,
    analyzeDetail: "You've used all 5 free analyses for today. Please come back tomorrow.",
  });
  await page.reload();
  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("button", { name: "Try a sample job" }).click();
  await page.getByRole("button", { name: "Check my fit" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /used all 5 free analyses/ })).toBeVisible();
});

test("the page fits the screen without sideways scrolling", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("a sleeping server shows a 'starting' banner, then clears it", async ({ page }) => {
  await mockApi(page, { sleepingHealthChecks: 2 });
  await page.reload();
  await expect(page.getByText(/Starting the server/)).toBeVisible();
  await expect(page.getByText("✓ Server is ready.")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Starting the server/)).toBeHidden();
});

test("Find jobs for me: any location, live progress, ranked jobs, deal-breaker filter, full fit check", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("tab", { name: /Find jobs for me/ }).click();
  await page.getByRole("button", { name: "Bangkok", exact: true }).click();
  await expect(page.getByLabel(/Where do you want to work/)).toHaveValue("Bangkok");
  await page.getByRole("button", { name: /Find jobs for me/ }).click();

  const results = page.getByTestId("job-search-results");
  await results.getByText(/How JobFit searched/).click();
  await expect(results.getByText("Searching: Full Stack Developer jobs Bangkok")).toBeVisible();
  await expect(results.getByText("2 current jobs")).toBeVisible();
  await expect(results.getByText("🚩 Java required")).toBeVisible();

  await page.getByLabel("Hide jobs with deal-breakers").check();
  await expect(results.getByText("Java Developer")).toBeHidden();

  await results.getByRole("button", { name: "Full fit check" }).click();
  await expect(page.getByText("Possible match: apply and address the gaps")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Check a job" })).toHaveAttribute("aria-selected", "true");
});

test("Find jobs explains when nothing could be found", async ({ page }) => {
  await mockApi(page);
  await page.reload();
  await page.getByRole("button", { name: "Use a sample resume" }).click();
  await page.getByRole("tab", { name: /Find jobs for me/ }).click();
  await page.getByLabel(/Where do you want to work/).fill("Nowhere");
  await page.getByRole("button", { name: /Find jobs for me/ }).click();
  await expect(page.getByText(/No current jobs could be found for Nowhere/)).toBeVisible();
});
