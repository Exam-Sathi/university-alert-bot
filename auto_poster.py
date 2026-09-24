import os
import re
import json
import html
import time
import smtplib
import urllib.parse
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urljoin
import urllib3
import requests
from bs4 import BeautifulSoup

# Some government portals have broken HTTPS certificates, so certificate checks are skipped for them.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= SECRETS & CONFIGURATION =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")
SENDER_GMAIL = os.environ.get("SENDER_GMAIL")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

WHATSAPP_INSTANCE_ID = os.environ.get("WHATSAPP_INSTANCE_ID")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN")

# Failure reports go to a private admin Telegram chat (optional).
ADMIN_TELEGRAM_BOT_TOKEN = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_CHAT_ID = (os.environ.get("ADMIN_TELEGRAM_CHAT_ID") or "").strip()

# DRY_RUN=1 lists what would be posted without calling Gemini, email or Telegram, and changes no files.
DRY_RUN = os.environ.get("DRY_RUN") == "1"
# BASELINE=1 marks every link currently on the portals as already seen, without posting.
# Run it once when switching to this bot so only notices published after that get posted.
BASELINE = os.environ.get("BASELINE") == "1"

WEBSITE_DOMAIN = "https://www.uniexamdose.com"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029Vb8wG4W4o7qDPLg0JZ2L"
HISTORY_FILE = "posted_notices.json"
ATTEMPTS_FILE = "notice_attempts.json"
MAX_POSTS_PER_RUN = 2
MAX_FAILURES_PER_RUN = 2
MAX_ATTEMPTS = 3              # a notice that fails in 3 separate runs is skipped for good
ADMIN_ALERT_EVERY_SECONDS = 3 * 60 * 60

# ================= TARGET PORTALS =================
TARGET_PORTALS = [
    # 1. PDUSU (शेखावाटी यूनिवर्सिटी सीकर)
    {"uni": "PDUSU Sikar", "label": "PDUSU", "type": "Academics", "url": "https://shekhauni.ac.in/Home/Academics"},
    {"uni": "PDUSU Sikar", "label": "PDUSU", "type": "Examination", "url": "https://shekhauni.ac.in/Home/Examination"},
    {"uni": "PDUSU Sikar", "label": "PDUSU, Result", "type": "Result", "url": "https://result26.shekhauniexam.in/RESULTS.aspx"},

    # 2. Rajasthan University (राजस्थान यूनिवर्सिटी, जयपुर)
    {"uni": "Rajasthan University (RU)", "label": "RU Jaipur", "type": "Circular", "url": "https://www.uniraj.ac.in/index.php?mid=196&cirid=4"},
    {"uni": "Rajasthan University (RU)", "label": "RU Jaipur, Examination", "type": "Examination", "url": "https://www.uniraj.ac.in/index.php?mid=196&cirid=3"},

    # 3. MGSU (महाराजा गंगा सिंह यूनिवर्सिटी, बीकानेर)
    {"uni": "MGSU Bikaner", "label": "MGSU, Examination", "type": "Examination", "url": "https://www.mgsubikaner.ac.in/notification/examination"},
    {"uni": "MGSU Bikaner", "label": "MGSU", "type": "Student Update", "url": "https://www.mgsubikaner.ac.in/notification/student-update"},

    # 4. RRBMU (मत्स्य यूनिवर्सिटी, अलवर)
    {"uni": "RRBMU Alwar", "label": "RRBMU", "type": "Latest Update", "url": "https://www.rrbmuniv.ac.in/LatestUpdateMore.php?link=0"},

    # 5. RPSC (राजस्थान लोक सेवा आयोग)
    {"uni": "RPSC", "label": "RPSC", "type": "News & Press Note", "url": "https://rpsc.rajasthan.gov.in/"},

    # 6. RSSB / RSMSSB (राजस्थान कर्मचारी चयन बोर्ड)
    {"uni": "RSMSSB", "label": "RSMSSB", "type": "News & Notice", "url": "https://rssb.rajasthan.gov.in/news"},
    {"uni": "RSMSSB", "label": "RSMSSB, Recruitment", "type": "Advertisement", "url": "https://rssb.rajasthan.gov.in/advertisements"},

    # 7. UPSC (संघ लोक सेवा आयोग)
    {"uni": "UPSC", "label": "UPSC", "type": "Recruitment Advertisement", "url": "https://www.upsc.gov.in/recruitment/recruitment-advertisement"},

    # 8. SSC (कर्मचारी चयन आयोग)
    {"uni": "SSC", "label": "SSC", "type": "Notice Board", "url": "https://ssc.gov.in/home/notice-board"},
]

# ================= WHICH LINKS COUNT AS NOTICES =================
# Old versions took every link with a long title, so menus and footers were posted as "notices".
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xls", ".xlsx")
SKIP_PATH_WORDS = re.compile(r"(sitemap|gallery|tender|login|contact|about|privacy|disclaimer|feedback|rti)", re.IGNORECASE)
NOTICE_WORDS = re.compile(
    r"\b(notices?|notifications?|results?|exams?|examinations?|schedule|time ?table|date ?sheet|admit|admissions?|"
    r"circulars?|advertisements?|advt|recruitment|vacanc(y|ies)|syllabus|merit|answer ?key|cut ?off|interviews?|"
    r"declared|revised|press ?note|scholarships?|applications?|last ?date|extension|counsell?ing|practicals?|"
    r"re-?evaluation|revaluation|provisional|model ?answer|objections?|shortlist(ed)?)\b",
    re.IGNORECASE,
)
HINDI_NOTICE_WORDS = ["सूचना", "परीक्षा", "परिणाम", "विज्ञप्ति", "भर्ती", "प्रवेश", "समय सारणी", "आवेदन", "अधिसूचना", "परिपत्र"]


def looks_like_notice(title, url):
    lowered = url.lower()
    if lowered.startswith(("javascript:", "mailto:", "tel:")):
        return False
    path = lowered.split("?")[0].split("#")[0]
    if path.endswith(DOCUMENT_EXTENSIONS):
        return True
    if SKIP_PATH_WORDS.search(path):
        return False
    return bool(NOTICE_WORDS.search(title)) or any(word in title for word in HINDI_NOTICE_WORDS)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except ValueError:
                return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def academic_session(today=None):
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}-{start + 1}"


def fetch_notices_from_portal(portal):
    """Returns the portal's notice links, or None if the portal couldn't be read."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(portal["url"], headers=headers, timeout=20, verify=False)
        if res.status_code != 200:
            print(f"⚠️ {portal['uni']} ({portal['url']}): HTTP {res.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error reading {portal['uni']} ({portal['url']}): {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    notices = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = a["href"].strip()
        if not href or href.startswith("#") or len(title) < 12:
            continue
        full_url = urljoin(portal["url"], href)
        if not looks_like_notice(title, full_url):
            continue
        notices.append({
            "title": title,
            "url": full_url,
            "uni": portal["uni"],
            "label": portal["label"],
            "type": portal["type"],
        })
    return notices


def generate_ai_post(notice):
    """100% SEO-Optimized Post via Gemini"""
    from google import genai  # imported here so DRY_RUN works without the package

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    आप UniExamDose (राजस्थान का अग्रणी शिक्षा व भर्ती पोर्टल - www.uniexamdose.com) के शीर्ष SEO विशेषज्ञ और संपादक हैं।
    संस्था/आयोग: {notice['uni']}
    श्रेणी: {notice['type']}
    नोटिस शीर्षक: {notice['title']}
    डाउनलोड लिंक: {notice['url']}

    Google Search में #1 रैंक करने के लिए 100% SEO-Optimized हिंदी HTML ब्लॉग पोस्ट लिखें:

    [MANDATORY SEO STRUCTURE]:
    1. INTRODUCTION (SEO Meta Snippet): 120-150 शब्दों में आकर्षक विवरण जिसमें मुख्य कीवर्ड्स (Exam, Result, Notice, Time Table, Date) स्वाभाविक रूप से आएं।
    2. OVERVIEW TABLE: एक सुंदर, स्वच्छ HTML टेबल (Table with border-collapse) जिसमें:
       - Board / University: {notice['uni']}
       - Notice Type: {notice['type']}
       - Session: {academic_session()}
       - Category: Latest Official Update
       - Official Website: UniExamDose Guide
    3. KEY HIGHLIGHTS (H2): मुख्य नियम, तिथियां और महत्वपूर्ण बिंदु (Bullet points में)।
    4. STEP-BY-STEP CHECK PROCESS (H2): छात्र या अभ्यर्थी इस नोटिस/रिजल्ट को कैसे चेक करें (Numbered List 1, 2, 3)।
    5. BIG CALL-TO-ACTION DOWNLOAD BUTTON:
       <div style="text-align:center;margin:30px 0;">
         <a href="{notice['url']}" target="_blank" rel="noopener nofollow" style="background:#1d4ed8;color:#ffffff;padding:16px 34px;border-radius:30px;text-decoration:none;font-weight:800;font-size:1.15rem;display:inline-block;box-shadow:0 5px 20px rgba(29,78,216,0.35);transition:0.3s;">📥 आधिकारिक नोटिस / रिजल्ट पीडीएफ डाउनलोड करें &#8594;</a>
       </div>
    6. FREQUENTLY ASKED QUESTIONS (H2): छात्रों द्वारा पूछे जाने वाले 3 सामान्य सवाल और उनके सटीक उत्तर (FAQ Schema Ready)।
    7. SEO TAGS & KEYWORDS (H3): 10-15 ट्रेंडिंग सर्च कीवर्ड्स कॉमा लगाकर लिखें।
    8. SOCIAL INVITE:
       <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:16px;text-align:center;margin-top:25px;">
         <p style="margin:0 0 8px;font-weight:700;color:#166534;">🔔 सबसे तेज़ अपडेट पाने के लिए हमारे चैनल जॉइन करें:</p>
         <a href="{WHATSAPP_CHANNEL_URL}" target="_blank" style="background:#16a34a;color:#fff;padding:8px 18px;border-radius:20px;text-decoration:none;font-weight:700;display:inline-block;margin:4px;">📲 Join WhatsApp Channel</a>
       </div>

    शुद्ध HTML कोड दें। Markdown backticks (```) बिल्कुल न लगाएं।
    """
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty post")
    return re.sub(r"^```(?:html)?\s*|\s*```$", "", text)


def publish_to_blogger(notice, html_content):
    """Blogger पर पोस्ट पब्लिश करना (SEO Labels के साथ). Raises if it fails."""
    if not (BLOGGER_EMAIL and SENDER_GMAIL and GMAIL_APP_PASS):
        raise RuntimeError("Blogger email secrets (BLOGGER_EMAIL, SENDER_GMAIL, GMAIL_APP_PASS) are missing")

    title = f"[{notice['uni']}] {notice['title']} - Latest Update & Download"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SENDER_GMAIL
    msg["To"] = BLOGGER_EMAIL

    # SEO Tags & Labels
    labels = f"Notice, {notice['label']}, UniExamDose, Official Update"
    full_html = html_content + f"<br/><br/><p style='color:#64748b;font-size:0.8rem;'>Labels: {labels}</p>"
    msg.attach(MIMEText(full_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(SENDER_GMAIL, GMAIL_APP_PASS)
        server.sendmail(SENDER_GMAIL, BLOGGER_EMAIL, msg.as_string())
    print(f"✅ Blogger पर सफलतापूर्वक पोस्ट हुआ: {title}")


def get_website_search_link(notice):
    """वेबसाइट पर छात्र को भेजने के लिए डायरेक्ट लिंक"""
    search_term = notice['title'][:35].strip()
    encoded = urllib.parse.quote_plus(search_term)
    return f"{WEBSITE_DOMAIN}/search?q={encoded}"


def send_telegram_alert(notice):
    """Telegram अलर्ट - छात्र सीधे UniExamDose वेबसाइट पर आएगा"""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("⚠️ Telegram Secrets missing.")
        return

    safe_uni = html.escape(notice.get('uni', 'UniExamDose'))
    safe_title = html.escape(notice.get('title', 'Update'))
    website_url = get_website_search_link(notice)

    message = (
        f"🚨 <b>{safe_uni} ताज़ा अपडेट जारी!</b>\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        f"📝 पूरी जानकारी, मुख्य नियम व आधिकारिक डाउनलोड लिंक UniExamDose वेबसाइट पर उपलब्ध है:\n\n"
        f"🔗 <b>यहाँ क्लिक करके पढ़ें व डाउनलोड करें:</b>\n"
        f"👉 {website_url}\n\n"
        f"🌐 <i>पोर्टल: UniExamDose (सबसे तेज़ शिक्षा समाचार)</i>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=12)
        if res.json().get("ok"):
            print("✅ Telegram पर अलर्ट भेजा गया (UniExamDose Website Link)!")
        else:
            print(f"❌ Telegram Error: {res.json().get('description')}")
    except Exception as e:
        print(f"Telegram error: {e}")


def send_whatsapp_alert(notice):
    """WhatsApp Channel अलर्ट - छात्र सीधे UniExamDose वेबसाइट पर आएगा"""
    if not (WHATSAPP_INSTANCE_ID and WHATSAPP_API_TOKEN):
        return

    website_url = get_website_search_link(notice)

    message = (
        f"🚨 *{notice['uni']} ताज़ा अपडेट जारी!*\n\n"
        f"📌 *{notice['title']}*\n\n"
        f"📝 पूरी जानकारी, मुख्य बिंदु व PDF डाउनलोड लिंक वेबसाइट पर देखें:\n"
        f"👉 {website_url}\n\n"
        f"📲 *Join WhatsApp Channel:* {WHATSAPP_CHANNEL_URL}\n"
        f"🌐 _UniExamDose Portal_"
    )

    url = f"https://api.green-api.com/waInstance{WHATSAPP_INSTANCE_ID}/sendMessage/{WHATSAPP_API_TOKEN}"
    payload = {
        "chatId": "0029Vb8wG4W4o7qDPLg0JZ2L@newsletter",
        "message": message
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ WhatsApp Channel पर अलर्ट भेजा गया (UniExamDose Website Link)!")
        else:
            print(f"❌ WhatsApp API Status: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"WhatsApp error: {e}")


def notify_admin(text):
    """Sends a problem report to the admin Telegram bot. Never raises."""
    if not (ADMIN_TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_TELEGRAM_CHAT_ID, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=12,
        )
    except Exception as e:
        print(f"Admin alert error: {e}")


def main():
    history = load_json(HISTORY_FILE, [])
    attempts = load_json(ATTEMPTS_FILE, {})
    seen = set(history)

    print("🔍 सभी यूनिवर्सिटी व भर्ती आयोगों को स्कैन किया जा रहा है...")
    notices, urls, failed_portals = [], set(), 0
    for portal in TARGET_PORTALS:
        found = fetch_notices_from_portal(portal)
        if found is None:
            failed_portals += 1
            continue
        for notice in found:
            if notice["url"] not in urls:  # the same link can appear on several pages
                urls.add(notice["url"])
                notices.append(notice)

    new_notices = [n for n in notices if n["url"] not in seen]
    print(f"कुल नोटिस लिंक्स: {len(notices)} | नए नोटिस: {len(new_notices)} | पढ़ नहीं पाए पोर्टल: {failed_portals}")

    if DRY_RUN:
        for n in new_notices[:50]:
            print(f"  [{n['uni']} / {n['type']}] {n['title'][:90]}\n      {n['url']}")
        print("DRY_RUN: nothing was posted and no files were changed.")
        return

    if BASELINE:
        history.extend(n["url"] for n in new_notices)
        save_json(HISTORY_FILE, history)
        save_json(ATTEMPTS_FILE, attempts)
        print(f"BASELINE: marked {len(new_notices)} current links as seen. Nothing was posted.")
        return

    posted, failed, errors = 0, [], []
    for notice in new_notices:
        if posted >= MAX_POSTS_PER_RUN or len(failed) >= MAX_FAILURES_PER_RUN:
            break
        print(f"\n🚀 SEO पोस्ट तैयार हो रही है: [{notice['uni']}] {notice['title']}")
        try:
            post_html = generate_ai_post(notice)
            publish_to_blogger(notice, post_html)
        except Exception as e:
            print(f"❌ पोस्ट नहीं हुआ: {e}")
            failed.append(notice)
            errors.append(f"• {html.escape(notice['uni'])}: {html.escape(notice['title'][:70])}\n  {html.escape(str(e)[:200])}")
            continue

        posted += 1
        history.append(notice["url"])
        seen.add(notice["url"])
        attempts.pop(notice["url"], None)
        save_json(HISTORY_FILE, history)  # saved after every post, so a later crash can't cause duplicates
        send_telegram_alert(notice)
        send_whatsapp_alert(notice)

    # Only count failures against a notice when something else worked this run; if everything
    # failed (bad key, Gmail down), the problem isn't the notice, so it stays in the queue.
    if posted and failed:
        for notice in failed:
            count = attempts.get(notice["url"], 0) + 1
            if count >= MAX_ATTEMPTS:
                history.append(notice["url"])
                attempts.pop(notice["url"], None)
                errors.append(f"  ↳ skipped for good after {MAX_ATTEMPTS} failed runs: {html.escape(notice['title'][:70])}")
            else:
                attempts[notice["url"]] = count
    if failed_portals == len(TARGET_PORTALS):
        errors.append("• Could not read any portal (network problem or every site is down).")

    if errors and time.time() - attempts.get("__last_admin_alert__", 0) > ADMIN_ALERT_EVERY_SECONDS:
        notify_admin(f"⚠️ <b>Notice bot problems</b>\nPosted {posted}, waiting {len(new_notices) - posted}\n\n" + "\n".join(errors))
        attempts["__last_admin_alert__"] = time.time()

    save_json(HISTORY_FILE, history)
    save_json(ATTEMPTS_FILE, attempts)
    print(f"✨ टास्क पूरा हुआ! पोस्ट हुए: {posted} | बाकी नए नोटिस: {len(new_notices) - posted}")


if __name__ == "__main__":
    main()
