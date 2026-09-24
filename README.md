# University Alert Bot

Scans Rajasthan university and recruitment portals for new notices, writes a Hindi post with Gemini, publishes it on the [UniExam Dose blog](https://reactorgano.blogspot.com) by email, and alerts the Telegram channel [@examsathialert](https://t.me/examsathialert) (and optionally WhatsApp).

- **Runs:** every 30 minutes on GitHub Actions (`.github/workflows/monitor.yml`), and from Actions → *University Notice Auto-Poster* → *Run workflow*.
- **Portals:** `TARGET_PORTALS` in `auto_poster.py`.
- **Only real notices:** document links (PDF, DOC…) or notice-like titles; menu and navigation links are skipped.
- **History:** `posted_notices.json` (links already handled) and `notice_attempts.json` (retry counts), committed back by the workflow. A notice that fails in 3 separate runs is skipped.
- **Limits:** at most 2 posts per run, saving history after each post.
- **Problems** (Gemini or Gmail failures, every portal unreachable) are reported to a private Telegram chat, at most every 3 hours.
- **Secrets:** see `.env.example`.

## Baseline run

After a long pause, run the workflow once with **Baseline only** ticked. It marks every link currently on the portals as seen and posts nothing, so only notices published after that are posted.

## Try it locally without posting anything

```bash
pip install -r requirements.txt
DRY_RUN=1 python auto_poster.py          # PowerShell: $env:DRY_RUN=1; python auto_poster.py
```

It lists the notices it would post and changes no files.

## Known issue

Some government sites (RPSC, RSMSSB, and at times the University of Rajasthan) don't respond to GitHub's servers, which are outside India. The log shows `Error reading …` for them; those portals' notices are missed until the bot runs from a server in India.
