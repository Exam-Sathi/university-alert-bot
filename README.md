# University Alert Bot

Scans Rajasthan university and recruitment portals for new notices, writes a Hindi post with Gemini, publishes it on the [UniExam Dose blog](https://reactorgano.blogspot.com) through the Blogger API, and alerts the Telegram channel [@examsathialert](https://t.me/examsathialert) (and optionally WhatsApp).

- **Runs:** every 30 minutes on one computer in India, from Windows Task Scheduler, through `tools/notice-bot-india.mjs` in the main repo. It used to run on GitHub Actions as well; that half was retired because RPSC and RSMSSB turn GitHub's servers away, and because publishing by email lost about a third of the posts it sent.
- **Portals:** `TARGET_PORTALS` in `auto_poster.py`. Where a link only says "View" or "Click Here", the title comes from its table row. SSC's notice board is read from the API behind the page, because the page itself is built by JavaScript.
- **Only real notices:** document links (PDF, DOC…) or notice-like titles; menu and navigation links are skipped.
- **History:** `posted_notices_india.json` (links already handled), `notice_attempts_india.json` (retry counts), `posted_titles_india.json` (so a notice re-uploaded under a new URL is not posted twice) and `pending_alerts_india.json` (alerts waiting for their post to exist). The runner commits them back. A notice that fails in 3 separate runs is skipped.
- **Publishing:** through the Blogger API when `BLOGGER_BLOG_ID` and the three `GOOGLE_OAUTH_*` values are set — it returns the post's address at once, so the alert can link to the notice itself. Without them it falls back to post-by-email, which is slower and drops posts silently.
- **Limits:** at most 2 posts per run, saving history after each post.
- **Problems** (Gemini or Gmail failures, every portal unreachable) are reported to a private Telegram chat, at most every 3 hours.
- **Secrets:** see `.env.example`.

## Baseline run

After a long pause, run `node tools/notice-bot-india.mjs --baseline` once. It marks every link currently on the portals as seen and posts nothing, so only notices published after that are posted. It stops without saving if any portal can't be read, because that portal's old notices would otherwise be posted later. `BASELINE_KEEP_DAYS=7` leaves notices dated in the last 7 days to be posted.

## Try it locally without posting anything

```bash
pip install -r requirements.txt
DRY_RUN=1 python auto_poster.py          # PowerShell: $env:DRY_RUN=1; python auto_poster.py
```

It lists the notices it would post and changes no files.

## Known issue

The University of Rajasthan and MGSU sites sometimes time out. The log shows `Error reading …`; their notices are picked up on a later run.
