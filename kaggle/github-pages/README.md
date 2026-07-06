# GitHub Pages deploy for AI-PTCG (frontend)

This publishes the React/Vite frontend as a static site on GitHub Pages via a
GitHub Actions workflow. **Two small changes**, provided two ways:

- `AI-PTCG-github-pages.patch` — apply with `git apply`, or
- `files/` — the changed files at their real paths, to copy in by hand.

Changed files:
- `.github/workflows/pages.yml` *(new)* — build + deploy workflow.
- `frontend/vite.config.js` *(1 line)* — `base: process.env.VITE_BASE || '/'`,
  so assets resolve under `/<repo>/` on Pages while local dev/Render stay at `/`.

## Apply and push
From the root of your `AI-PTCG` clone (branch `main`):

    git apply /path/to/AI-PTCG-github-pages.patch
    # — or — cp -r /path/to/files/. .

    git add .github/workflows/pages.yml frontend/vite.config.js
    git commit -m "Add GitHub Pages deploy for the frontend"
    git push origin main

## One-time GitHub settings (required)
1. **Enable Pages via Actions:** Settings → Pages → Build and deployment →
   Source → **GitHub Actions**.
2. **Point the frontend at your backend:** Settings → Secrets and variables →
   Actions → **Variables** → New repository variable →
   `VITE_API_BASE = https://<your-backend>.onrender.com`

The workflow runs on push (and via "Run workflow"). When it finishes, the site
is at **https://<your-username>.github.io/AI-PTCG/**.

## Important — this is honest about what Pages can and can't do
GitHub Pages serves **static files only**. The app needs the FastAPI backend
(`backend/`, already deployable via the repo's `render.yaml`). So:

- Deploy the backend first (Render, per the existing blueprint) and copy its
  HTTPS URL into the `VITE_API_BASE` repo Variable above. Without it the UI
  loads but every API call fails, and the app's boot screen will sit on
  "waking server" while it polls `/api/health`.
- The backend must allow the Pages origin (CORS) —
  `https://<your-username>.github.io`.

## If you rename the repo or use a custom domain
Edit `VITE_BASE` in `pages.yml`: use `/<new-repo-name>/` for a project site, or
`/` for a custom domain / user site.
