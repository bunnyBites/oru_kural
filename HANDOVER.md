# Oru Kural — Handover Readiness Assessment

**Date:** June 2026  
**Branch:** `feature/v4-multi-source-` (not yet merged to `main`)  
**Verdict:** Not ready to hand over yet — 5 blockers + 3 polish items below.

---

## What IS production-ready

| Area | Status |
|---|---|
| Data pipeline (X, Reddit, CM events, grievances) | Fully automated, runs Mon + Thu via GitHub Actions |
| AI categorization + clustering | Gemini 2.5 Flash, incremental, deduplicated |
| Rust/Axum backend | Rate limiting, structured logging, request IDs, gzip/brotli, 504 timeout guards |
| Dioxus WASM frontend | 3 tabs, dark mode, Tamil/English toggle, skeleton loading, error banners, retry |
| Deployment | Fly.io (backend) + Vercel (frontend), health checks, auto-deploy on push |
| Observability | `scrape_runs` table, GitHub Actions step-level logs, `X-Request-Id` correlation |
| Security | RLS on all Supabase tables, anon key for reads only, service role never in frontend/backend |
| Cost | ~$5–7/month total after X API v2 migration |

---

## Blockers — fix before handover

### B1 · Merge `feature/v4-multi-source-` → `main`
The entire v4 work (Tamil UI, twscrape migration, grievance scraper, migration 010) lives on the feature branch. `main` is stale. The CM IT team receiving a repo URL will clone `main`.

**Action:** raise a PR, squash-merge, delete the feature branch.

---

### B2 · Custom domain (M9 — still TODO)
The app currently lives at a Vercel-generated URL. Handing over a `.vercel.app` URL to a government IT team is a credibility issue — they will expect a proper domain.

**Options (cheapest first):**
1. Subdomain of an existing domain you own — add `CNAME orukural.<yourdomain> → cname.vercel-dns.com` in your DNS registrar. Zero cost.
2. New `orukural.in` — Cloudflare Registrar, ~₹270/year.
3. Ask the CM IT team to point their own subdomain (e.g. `signals.tnega.gov.in`) — they likely prefer this for a government-facing tool.

**Vercel side:** Settings → Domains → Add → copy CNAME value shown.

---

### B3 · Update README — stale phase table + stale cron description
The README still says:
- Phase 5 (Multilingual) = "Planned" — it is **Done** (Tamil toggle shipped in v4)
- Automation section says "Weekly pipeline runs every Monday" — it is now **twice-weekly** (Mon + Thu)
- Phase 4 (Signal expansion) should note grievance scraper is Done; Reddit OAuth is the only open item

**Action:** 10-minute README pass to sync these.

---

### B4 · No operations runbook for the CM IT team
The README is a developer setup guide. An IT team receiving this needs a separate one-page ops document covering:
- How to trigger a manual scrape (GitHub Actions → Run workflow)
- How to check if the last scrape succeeded (Supabase → `scrape_runs` table, or Actions logs)
- What to do when the dashboard shows no new issues (run `cluster_issues.py` manually)
- How to rotate secrets (Supabase key, Gemini key, X Bearer Token)
- Monthly cost breakdown and where to pay (X API credits, Fly.io, Gemini)
- Who to contact for code-level issues (you)

---

### B5 · GitHub Actions failure notification goes nowhere
The workflow's `Notify on failure` step only echoes to the Actions log — nobody gets an email or Slack/Teams message. If a Monday scrape silently fails, the dashboard data goes stale without anyone knowing.

**Quick fix:** replace the echo with a GitHub Actions email notification or a `curl` to a webhook (Teams/Slack).  
**Best fix for government context:** send a failure email via `dawidd6/action-send-mail` action to a monitored mailbox the CM IT team owns.

---

## Polish — not blockers but recommended

### P1 · `scrape_runs` table is not visible in the UI
The pipeline faithfully writes to `scrape_runs` after every run, but there is no way to see it without Supabase dashboard access. A simple "Last updated: 2 days ago" timestamp in the Stats tab footer would tell any visitor (including the CM IT team) that the data is live.

**Effort:** ~1–2 hours (one backend `/meta` endpoint + one line in the Stats panel).

---

### P2 · Reddit still uses unauthenticated JSON fallback (T-11)
This is rate-limited and can break silently. The `continue-on-error: true` flag means the pipeline doesn't fail, but Reddit signals stop arriving. Reddit API credentials take a few days to approve — apply now so it is ready.

**Action:** apply at [reddit.com/prefs/apps](https://reddit.com/prefs/apps), then wire up `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` in `scrape_reddit.py` as described in T-11.

---

### P3 · No screenshot / demo in README
A civic tech tool being handed to a government team needs a visual first impression. The README has zero screenshots. A single GIF or two screenshots (Issues Board + CM Activity tab) would dramatically improve the first impression.

---

## Recommended order of work

| # | Task | Status |
|---|---|---|
| 1 | Fix README stale sections (B3) | ✅ Done |
| 2 | Write ops runbook for IT team (B4) | ✅ Done → `OPS_RUNBOOK.md` |
| 3 | Add GitHub Actions failure email (B5) | ✅ Done → `dawidd6/action-send-mail`, needs 3 secrets set |
| 4 | Add "last updated" to Stats tab UI (P1) | ✅ Done → `/meta` endpoint + Stats panel footer |
| 5 | Set up custom domain (B2) | ⏳ Pending — add CNAME in DNS registrar, then Vercel Settings → Domains |
| 6 | Add screenshots to README (P3) | ✅ Done — 4 screenshots in `docs/screenshots/`, hero + side-by-side + stats layout |
| 7 | Merge feature branch → main (B1) | ⏳ Pending — raise PR when all above are done |
| 8 | ~~Apply for Reddit API credentials (P2)~~ | ✅ Closed — unauthenticated fallback is sufficient |

**Remaining active work: ~1 hour** (domain + screenshots + merge).

---

## What you can tell the CM IT team today

Even before completing the above, here is what you can demonstrate right now:

- Live dashboard at the Vercel URL
- Twice-weekly automated scraping, fully hands-off
- Tamil/English toggle — citizens can read issues in their language
- ~$5–7/month total running cost, no proprietary infrastructure
- All source code on GitHub, MIT-licensable
- One-command local setup (they can self-host if needed)

The project is technically solid. It just needs a clean merge, a domain, and enough documentation that the IT team can operate it without calling you.
