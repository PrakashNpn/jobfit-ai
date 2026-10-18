# JobFit AI: web app

The Next.js + Tailwind front end for JobFit AI. See the [main README](../README.md) for the full project.

```bash
cp .env.example .env.local   # points the app at the API (default http://localhost:8000)
npm install
npm run dev                  # http://localhost:3000
```

The API must be running too (`uvicorn app.main:app --reload` in the project root).

| File | What it does |
|---|---|
| `app/page.tsx` | The single page: resume → job posting → result → cover letter |
| `components/ResumeInput.tsx` | Upload or paste a resume; kept in the browser's localStorage |
| `components/FitResult.tsx` | Fit score, verdict, key facts, skills and red flags |
| `components/CoverLetter.tsx` | Generates, edits and copies a cover letter |
| `lib/api.ts` | Calls to the FastAPI backend, with friendly error messages |
