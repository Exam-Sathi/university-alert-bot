# University Alert Bot

Scans Rajasthan university and recruitment portals for new notices, writes a Hindi post with Gemini, publishes it on the [UniExam Dose blog](https://reactorgano.blogspot.com) by email, and alerts the Telegram channel [@examsathialert](https://t.me/examsathialert) (and optionally WhatsApp).

- **Runs:** every 30 minutes on GitHub Actions (`.github/workflows/monitor.yml`), and from Actions → *University Notice Auto-Poster* → *Run workflow*.
- **Portals:** `TARGET_PORTALS` in `auto_poster.py`. Where a link only says "View" or "Click Here", the title comes from its table row. SSC's notice board is read from the API behind the page, because the page itself is built by JavaScript.
- **Only real notices:** document links (PDF, DOC…) or notice-like titles; menu and navigation links are skipped.
- **History:** `posted_notices.json` (links already handled) and `notice_attempts.json` (retry counts), committed back by the workflow. A notice that fails in 3 separate runs is skipped.
- **Portals that block GitHub** (RPSC, RSMSSB) are marked `india_only`. GitHub skips them; a computer in India runs `RUN_ON=india python auto_poster.py` every 30 minutes, which reads only those and keeps its own history in `posted_notices_india.json` and `notice_attempts_india.json`.
- **Limits:** at most 2 posts per run, saving history after each post.
- **Problems** (Gemini or Gmail failures, every portal unreachable) are reported to a private Telegram chat, at most every 3 hours.
- **Secrets:** see `.env.example`.

## Baseline run

After a long pause, run the workflow once with **Baseline only** ticked. It marks every link currently on the portals as seen and posts nothing, so only notices published after that are posted. It stops without saving if any portal can't be read, because that portal's old notices would otherwise be posted later.

Locally, `BASELINE=1 BASELINE_KEEP_DAYS=7` does the same but leaves notices dated in the last 7 days to be posted.

## Try it locally without posting anything

```bash
pip install -r requirements.txt
DRY_RUN=1 python auto_poster.py          # PowerShell: $env:DRY_RUN=1; python auto_poster.py
```

It lists the notices it would post and changes no files.

## Known issue

The University of Rajasthan and MGSU sites sometimes time out. The log shows `Error reading …`; their notices are picked up on a later run.
