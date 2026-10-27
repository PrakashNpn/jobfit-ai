// Fictional examples so visitors can try the app in one click.

import type { FitReport } from "./types";

export const SAMPLE_JOB = `AI Engineer — Nimbus Rentals (fictional)

Location: Bangkok (hybrid, 3 days in office)
Salary: 45,000 – 60,000 THB per month
Type: Full-time

About the role
Nimbus Rentals runs a marketplace for renting equipment. You will build AI features that help renters find the right equipment and help our support team answer questions faster.

Requirements
- 2+ years of software development experience
- Python and FastAPI
- Experience with LLM APIs (Claude, OpenAI or Gemini)
- Retrieval-augmented generation and vector databases (pgvector, Pinecone or similar)
- Good written and spoken English

Nice to have
- LangChain or LlamaIndex
- Docker and CI/CD
- Experience with marketplaces or booking systems

Thai language is not required.`;

export const SAMPLE_RESUME = {
  filename: "sample-resume (Alex Tan, fictional).md",
  text: `Alex Tan — Full-Stack Developer
Bangkok, Thailand

Summary
Full-stack developer with 4 years of experience building web applications with TypeScript, React, Next.js and Node.js. For the last year I have focused on LLM features: retrieval-augmented chatbots, document summarization and workflow automation with n8n.

Skills
Frontend: TypeScript, React, Next.js, Tailwind CSS
Backend: Node.js, Express, Python (scripting), REST APIs
Data: PostgreSQL, MongoDB, Redis
AI: Claude API, OpenAI API, RAG, prompt engineering, n8n
DevOps: Docker, GitHub Actions, Vercel, Linux
Languages: English (fluent), Thai (basic)

Experience
Full-Stack Developer — Fictional Learning Co., Bangkok (2025 – present)
- Built a course-search platform in Next.js and PostgreSQL used by internal staff and students.
- Added a RAG chatbot that answers student questions using the course catalogue.
- Automated weekly reporting with n8n, saving the operations team about 4 hours per week.

Web Developer — Sample Digital Agency, Yangon (2022 – 2025)
- Delivered 15+ client websites with React and Node.js.
- Integrated two payment gateways and a shipping-rate API for e-commerce clients.`,
};

/** Shown faded before the first check, so visitors see what a report looks like. */
export const EXAMPLE_REPORT: FitReport = {
  verdict: "strong",
  verdict_reason: "Your LLM and RAG projects match the core of this role. Lead with them in your cover letter.",
  job: {
    title: "AI Engineer",
    company: "Nimbus Rentals (example)",
    location: "Bangkok (hybrid)",
    work_type: "Full-time",
    salary_min_thb: 45000,
    salary_max_thb: 60000,
    min_years_experience: 2,
    required_skills: ["Python", "FastAPI", "LLM APIs", "RAG"],
    nice_to_have_skills: ["Docker"],
    thai_language_required: false,
    english_required: true,
    summary: "Builds AI features for a rental marketplace.",
  },
  match: {
    fit_score: 81,
    matching_skills: ["LLM APIs", "RAG", "pgvector", "Docker"],
    missing_skills: ["LangChain"],
    red_flags: [],
    summary: "A strong fit on AI skills; LangChain is a nice-to-have you can pick up quickly.",
  },
};
