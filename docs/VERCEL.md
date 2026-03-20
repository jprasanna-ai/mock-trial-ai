# Deploying the frontend on Vercel

The **Next.js app** lives in `frontend/`. The Vercel project **`mock-trial-ai`** must use:

| Setting | Value |
|--------|--------|
| **Root Directory** | `frontend` |
| **Framework** | Next.js (auto-detected) |

Environment variables (Production, Preview, Development):

- `NEXT_PUBLIC_API_URL` — e.g. `https://mock-trial-ai.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

---

## Recommended: deploy from GitHub

1. Connect the repo **jprasanna-ai/mock-trial-ai** to the **mock-trial-ai** Vercel project.
2. Set **Root Directory** to `frontend`.
3. Push to `main` — Vercel builds and deploys automatically.

This is the most reliable path and does not depend on local CLI git author checks.

---

## CLI deploy (optional)

Run commands from the **repository root** (not inside `frontend/`), so Vercel’s **Root Directory = `frontend`** is applied once (avoid `frontend/frontend` errors).

```bash
cd mock-trial-ai
npx vercel link --yes --project mock-trial-ai
npx vercel --prod
```

### If you see: “Git author … must have access to the team”

Vercel ties CLI deployments to the **git author email** on your latest commit. Fix one of:

1. **Vercel → Team → Members** — invite the same email as `git config user.email`, or  
2. Set git email to match your Vercel account:  
   `git config user.email "you@your-vercel-email.com"`  
   then make a new commit and run `vercel --prod` again.

---

## Local link file

The `.vercel/` directory is **gitignored**. It only stores which project the CLI is linked to; do not commit it.

After `vercel link` from the repo root, `.vercel/project.json` should show `"projectName":"mock-trial-ai"`.
