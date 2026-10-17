# Aegis — Global Intelligence Terminal
!!APP is live on- https://aegis-intel-news.streamlit.app/

A runnable Python + Streamlit research dashboard for public-source news
monitoring, geopolitical reading, cybersecurity incident education, daily
briefings, and a persistent personal **Notes** workspace.

## Features
- **Overview** — headline KPIs, latest developments, and category coverage at a glance.
- **Geopolitics** — source-linked reporting, keyword filtering, and a structured
  worksheet for evidence, competing interpretations, transmission channels, and
  scenarios (deliberately framed as scenarios, not predictions).
- **Cyber Lab** — defensive incident case studies (2017–2024) covering impact,
  root cause, lessons, and a research starting point. A guided study path and a
  safety warning make clear this is for defensive learning only.
- **Global News** — 80+ configured public RSS/Atom feeds with category/publisher
  filters, search, timestamps, attribution, and URL/title-hash deduplication.
- **Daily Briefings** — extractive per-category roundups generated from the most
  recent cached entries. Key-free: no generative claims are invented.
- **Notes** *(new)* — a SQLite-backed workspace for observations, hypotheses,
  and source-linked reminders. Pin notes, tag them, filter by category, edit
  inline, delete with confirm, and export the whole notebook as Markdown.
- **Sources & Status** — full feed inventory, last-check errors, data-handling
  notes, and operational instructions.
- **Dynamic UI** — animated gradient background, glassmorphic cards with hover
  transitions, live UTC clock, pulsing status dots, animated refresh ring,
  color-coded category pills, custom scrollbar, and 60-second auto-refresh.

## Run locally

Python 3.10+ recommended, with internet access for public RSS/Atom endpoints.

### Windows (PowerShell)
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually http://localhost:8501.

## Notes workspace

The Notes page stores all entries in `data/news.db` (the same SQLite database
the articles use). Each note has:
- title and free-text content
- category (Tech / Politics / Intelligence / Business / Finance / Cyber / World / Personal / General)
- comma-separated tags
- pinned flag (sorted to the top)
- optional linked article URL
- created & updated timestamps (rendered as relative "x minutes ago")

Use the **Export Markdown** button to download the entire notebook as a `.md`
file at any time.

## Important limitations
1. 80+ public RSS/Atom endpoints are configured, but publishers change URLs,
   restrict access, rate-limit, or stop serving RSS. The Status page records
   errors; actual live-feed count varies.
2. The browser session triggers a rerun every minute. Fetching is parallel with
   per-feed timeouts, but a full refresh may still take longer than 60 seconds
   on slow networks. Polling cannot force publishers to publish new stories.
3. Briefings are extractive and use source-provided descriptions. This key-free
   edition does not call a generative AI model, independently fact-check
   stories, or generate verified causal predictions.
4. Category labels are keyword-based and can be wrong. Verify important claims
   against original and independent sources.
5. Geopolitics worksheet structures analysis; it does not automatically create
   verified impact assessments or calibrated forecasts.
6. Cyber case studies are high-level and defensive. CISA links are general
   research starting points and may not be the incident-specific primary report.
   Confirm details against primary sources.
7. The app requests publicly accessible feed endpoints only, does not bypass
   paywalls, and stores headlines/snippets/metadata/links rather than full
   articles. Respect publisher terms and rate limits.
8. Notes are stored in the local SQLite database. Back up `data/news.db` if you
   want to preserve them.

## Production improvements
Use a background polling worker, feed health history, an optional
source-grounded summarization model, a region/entity taxonomy, incident-specific
cyber references, automated tests, access control, and monitoring before public
deployment.
