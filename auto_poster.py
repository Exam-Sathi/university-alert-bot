import os
import json
import html
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urljoin
import urllib3
import requests
from bs4 import BeautifulSoup
from google import genai

# SSL Warnings disable
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= SECRETS & CONFIGURATION =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")
SENDER_GMAIL = os.environ.get("SENDER_GMAIL")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

WHATSAPP_INSTANCE_ID = os.environ.get("WHATSAPP_INSTANCE_ID")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN")

WEBSITE_DOMAIN = "https://reactorgano.blogspot.com"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029Vb8wG4W4o7qDPLg0JZ2L"
HISTORY_FILE = "posted_notices.json"
MAX_POSTS_PER_RUN = 2

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

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def fetch_notices_from_portal(portal):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    notices = []
    try:
        res = requests.get(portal["url"], headers=headers, timeout=20, verify=False)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                title = a.get_text(strip=True)
                href = a["href"].strip()
                ignore_list = ["home", "about", "contact", "login", "sitemap", "gallery", "tenders", "javascript:", "#"]
                if not href or any(ign in href.lower() for ign in ignore_list):
                    continue
                if len(title) >= 12:
                    full_url = urljoin(portal["url"], href)
                    notices.append({
                        "title": title,
                        "url": full_url,
                        "uni": portal["uni"],
                        "label": portal["label"],
                        "type": portal["type"]
                    })
    except Exception as e:
        print(f"⚠️ Error reading {portal['uni']} ({portal['url']}): {e}")
    return notices

def generate_ai_post(notice):
    """100% SEO-Optimized Post via Gemini 3.6 Flash"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    आप Exam Sathi (राजस्थान का अग्रणी शिक्षा व भर्ती पोर्टल - reactorgano.blogspot.com) के शीर्ष SEO विशेषज्ञ और संपादक हैं।
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
       - Session: 2025-2026
       - Category: Latest Official Update
       - Official Website: Exam Sathi Guide
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
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    return response.text

def publish_to_blogger(notice, html_content):
    """Blogger पर पोस्ट पब्लिश करना (SEO Labels के साथ)"""
    if not (BLOGGER_EMAIL and SENDER_GMAIL and GMAIL_APP_PASS):
        print("❌ Email credentials missing. Skipping post.")
        return False

    title = f"[{notice['uni']}] {notice['title']} - Latest Update & Download"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SENDER_GMAIL
    msg["To"] = BLOGGER_EMAIL

    # SEO Tags & Labels
    labels = f"Notice, {notice['label']}, Exam Sathi, Official Update"
    full_html = html_content + f"<br/><br/><p style='color:#64748b;font-size:0.8rem;'>Labels: {labels}</p>"
    msg.attach(MIMEText(full_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_GMAIL, GMAIL_APP_PASS)
            server.sendmail(SENDER_GMAIL, BLOGGER_EMAIL, msg.as_string())
        print(f"✅ Blogger पर सफलतापूर्वक पोस्ट हुआ: {title}")
        return True
    except Exception as e:
        print(f"❌ Blogger एरर: {e}")
        return False

def get_website_search_link(notice):
    """वेबसाइट पर छात्र को भेजने के लिए डायरेक्ट लिंक"""
    # सर्च क्वेरी ताकि छात्र सीधे आपकी वेबसाइट के पोस्ट पर पहुंचे
    search_term = notice['title'][:35].strip()
    encoded = urllib.parse.quote_plus(search_term)
    return f"{WEBSITE_DOMAIN}/search?q={encoded}"

def send_telegram_alert(notice):
    """Telegram अलर्ट - छात्र सीधे Exam Sathi वेबसाइट पर आएगा"""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("⚠️ Telegram Secrets missing.")
        return

    safe_uni = html.escape(notice.get('uni', 'Exam Sathi'))
    safe_title = html.escape(notice.get('title', 'Update'))
    website_url = get_website_search_link(notice)

    message = (
        f"🚨 <b>{safe_uni} ताज़ा अपडेट जारी!</b>\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        f"📝 पूरी जानकारी, मुख्य नियम व आधिकारिक डाउनलोड लिंक Exam Sathi वेबसाइट पर उपलब्ध है:\n\n"
        f"🔗 <b>यहाँ क्लिक करके पढ़ें व डाउनलोड करें:</b>\n"
        f"👉 {website_url}\n\n"
        f"🌐 <i>पोर्टल: Exam Sathi (सबसे तेज़ शिक्षा समाचार)</i>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=12)
        if res.json().get("ok"):
            print("✅ Telegram पर अलर्ट भेजा गया (Exam Sathi Website Link)!")
        else:
            print(f"❌ Telegram Error: {res.json().get('description')}")
    except Exception as e:
        print(f"Telegram error: {e}")

def send_whatsapp_alert(notice):
    """WhatsApp Channel अलर्ट - छात्र सीधे Exam Sathi वेबसाइट पर आएगा"""
    if not (WHATSAPP_INSTANCE_ID and WHATSAPP_API_TOKEN):
        return

    website_url = get_website_search_link(notice)

    message = (
        f"🚨 *{notice['uni']} ताज़ा अपडेट जारी!*\n\n"
        f"📌 *{notice['title']}*\n\n"
        f"📝 पूरी जानकारी, मुख्य बिंदु व PDF डाउनलोड लिंक वेबसाइट पर देखें:\n"
        f"👉 {website_url}\n\n"
        f"📲 *Join WhatsApp Channel:* {WHATSAPP_CHANNEL_URL}\n"
        f"🌐 _Exam Sathi Portal_"
    )
    
    url = f"https://api.green-api.com/waInstance{WHATSAPP_INSTANCE_ID}/sendMessage/{WHATSAPP_API_TOKEN}"
    payload = {
        "chatId": "0029Vb8wG4W4o7qDPLg0JZ2L@newsletter",
        "message": message
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ WhatsApp Channel पर अलर्ट भेजा गया (Exam Sathi Website Link)!")
        else:
            print(f"❌ WhatsApp API Status: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"WhatsApp error: {e}")

def main():
    history = load_history()
    all_notices = []

    print("🔍 सभी यूनिवर्सिटी व भर्ती आयोगों को स्कैन किया जा रहा है...")
    for portal in TARGET_PORTALS:
        notices = fetch_notices_from_portal(portal)
        all_notices.extend(notices)

    new_notices = [n for n in all_notices if n["url"] not in history]
    print(f"कुल मिले लिंक्स: {len(all_notices)} | नए नोटिस: {len(new_notices)}")

    posts_to_publish = new_notices[:MAX_POSTS_PER_RUN]

    for notice in posts_to_publish:
        print(f"\n🚀 SEO पोस्ट तैयार हो रही है: [{notice['uni']}] {notice['title']}")
        post_html = generate_ai_post(notice)
        published = publish_to_blogger(notice, post_html)
        if published:
            send_telegram_alert(notice)
            send_whatsapp_alert(notice)

    for n in all_notices:
        if n["url"] not in history:
            history.append(n["url"])
            
    save_history(history)
    print("✨ टास्क पूरा हुआ!")

if __name__ == "__main__":
    main()
