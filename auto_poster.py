import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urljoin
import urllib3
import requests
from bs4 import BeautifulSoup
from google import genai

# सरकारी और यूनिवर्सिटी साइट्स के SSL एरर को रोकने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Secrets & Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")
SENDER_GMAIL = os.environ.get("SENDER_GMAIL")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HISTORY_FILE = "posted_notices.json"
MAX_POSTS_PER_RUN = 2  # एक रन में अधिकतम 2 पोस्ट्स ताकि ब्लॉग और जीमेल स्पैम न हों

# जिन-जिन यूनिवर्सिटी पेजों को ट्रैक करना है
TARGET_PORTALS = [
    # 1. PDUSU (शेखावाटी यूनिवर्सिटी सीकर)
    {"uni": "PDUSU Sikar", "label": "PDUSU", "type": "Academics", "url": "https://shekhauni.ac.in/Home/Academics"},
    {"uni": "PDUSU Sikar", "label": "PDUSU", "type": "Research", "url": "https://shekhauni.ac.in/Home/Research"},
    {"uni": "PDUSU Sikar", "label": "PDUSU", "type": "Examination", "url": "https://shekhauni.ac.in/Home/Examination"},
    {"uni": "PDUSU Sikar", "label": "PDUSU, Result", "type": "Result", "url": "https://result26.shekhauniexam.in/RESULTS.aspx"},

    # 2. Rajasthan University (राजस्थान यूनिवर्सिटी, जयपुर)
    {"uni": "Rajasthan University (RU)", "label": "RU Jaipur", "type": "Circular", "url": "https://www.uniraj.ac.in/index.php?mid=196&cirid=4"},
    {"uni": "Rajasthan University (RU)", "label": "RU Jaipur, Examination", "type": "Examination", "url": "https://www.uniraj.ac.in/index.php?mid=196&cirid=3"},
    {"uni": "Rajasthan University (RU)", "label": "RU Jaipur", "type": "Notification", "url": "https://www.uniraj.ac.in/index.php?mid=195"},

    # 3. MGSU (महाराजा गंगा सिंह यूनिवर्सिटी, बीकानेर)
    {"uni": "MGSU Bikaner", "label": "MGSU, Examination", "type": "Examination", "url": "https://www.mgsubikaner.ac.in/notification/examination"},
    {"uni": "MGSU Bikaner", "label": "MGSU", "type": "Colleges", "url": "https://www.mgsubikaner.ac.in/notification/colleges"},
    {"uni": "MGSU Bikaner", "label": "MGSU", "type": "Student Update", "url": "https://www.mgsubikaner.ac.in/notification/student-update"},

    # 4. RRBMU (मत्स्य यूनिवर्सिटी, अलवर)
    {"uni": "RRBMU Alwar", "label": "RRBMU", "type": "Latest Update", "url": "https://www.rrbmuniv.ac.in/LatestUpdateMore.php?link=0"},
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
    """यूनिवर्सिटी के पेज से लिंक्स और फाइल्स निकालना"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    notices = []
    try:
        res = requests.get(portal["url"], headers=headers, timeout=20, verify=False)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # सभी लिंक्स को स्कैन करना
            for a in soup.find_all("a", href=True):
                title = a.get_text(strip=True)
                href = a["href"].strip()
                
                # बेकार लिंक्स छोड़ना (Home, Login, Contact ইত্যাদি)
                ignore_list = ["home", "about", "contact", "login", "sitemap", "gallery", "tenders", "javascript:", "#"]
                if not href or any(ign in href.lower() for ign in ignore_list):
                    continue
                    
                # लिंक का टेक्स्ट कम से कम 12 अक्षर का होना चाहिए (ताकि अर्थपूर्ण नोटिस हो)
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
    """Gemini AI से सुंदर छात्रोपयोगी ब्लॉग पोस्ट बनवाना"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    आप Exam Sathi (राजस्थान का प्रतिष्ठित छात्र पोर्टल) के मुख्य संपादक हैं।
    यूनिवर्सिटी: {notice['uni']}
    श्रेणी: {notice['type']}
    नोटिस शीर्षक: {notice['title']}
    डाउनलोड/रिजल्ट लिंक: {notice['url']}

    कृपया इसके लिए एक बहुत ही उपयोगी, सुंदर और आकर्षक HTML ब्लॉग पोस्ट तैयार करें।
    ज़रूरी निर्देश:
    1. भाषा: सरल हिंदी (Hinglish/Hindi) जो कॉलेज छात्र आसानी से समझ सकें।
    2. मुख्य बातें:
       - यह नोटिस किसके बारे में है (संक्षेप में विवरण)।
       - महत्वपूर्ण बिंदु (Bullet points में)।
       - रिजल्ट या नोटिस कैसे देखें / डाउनलोड करें (Step-by-step)।
       - एक बड़ा और सुंदर बटन: <div style="text-align:center;margin:25px 0;"><a href="{notice['url']}" target="_blank" style="background:#1d4ed8;color:#ffffff;padding:14px 28px;border-radius:30px;text-decoration:none;font-weight:700;font-size:1.05rem;display:inline-block;box-shadow:0 4px 15px rgba(29,78,216,0.3);">📥 डाउनलोड नोटिस / रिजल्ट चेक करें &#8594;</a></div>
       - छात्रों के लिए सलाह कि वे आधिकारिक पोर्टल से भी जांच करें।
    3. कोई फालतू बात न लिखें। केवल शुद्ध HTML बॉडी कोड दें (```html टैग न लगाएं)।
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def publish_to_blogger(notice, html_content):
    """Blogger की सीक्रेट ईमेल पर पोस्ट पब्लिश करना"""
    if not (BLOGGER_EMAIL and SENDER_GMAIL and GMAIL_APP_PASS):
        print("❌ Email credentials missing. Skipping post.")
        return False

    title = f"[{notice['uni']}] {notice['title']}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SENDER_GMAIL
    msg["To"] = BLOGGER_EMAIL

    # Blogger Labels
    labels = f"Notice, {notice['label']}"
    full_html = html_content + f"<br/><br/><p style='color:#64748b;font-size:0.8rem;'>Labels: {labels}</p>"
    msg.attach(MIMEText(full_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_GMAIL, GMAIL_APP_PASS)
            server.sendmail(SENDER_GMAIL, BLOGGER_EMAIL, msg.as_string())
        print(f"✅ Blogger पर सफलतापूर्वक पोस्ट हुआ: {title}")
        return True
    except Exception as e:
        print(f"❌ Blogger पब्लिशिंग फेल: {e}")
        return False

def send_telegram_alert(notice):
    """टेलीग्राम चैनल पर अलर्ट भेजना"""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    message = (
        f"🚨 <b>{notice['uni']} ताज़ा अपडेट!</b>\n\n"
        f"📌 <b>{notice['title']}</b>\n\n"
        f"🔗 <b>चेक करें और डाउनलोड करें:</b>\n"
        f"👉 {notice['url']}\n\n"
        f"🌐 <i>पोर्टल: Exam Sathi</i>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
        print("✅ Telegram पर अलर्ट भेजा गया!")
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    history = load_history()
    is_first_run = len(history) == 0
    all_notices = []

    print("🔍 सभी 11 यूनिवर्सिटी पेजों को स्कैन किया जा रहा है...")
    for portal in TARGET_PORTALS:
        notices = fetch_notices_from_portal(portal)
        all_notices.extend(notices)

    new_notices = [n for n in all_notices if n["url"] not in history]
    print(f"कुल मिले लिंक्स: {len(all_notices)} | नए नोटिस: {len(new_notices)}")

    # अगर पहली बार बॉट चल रहा है, तो 2 ताज़ा नोटिस पोस्ट करें और बाकियों को हिस्ट्री में सेव कर लें
    posts_to_publish = new_notices[:MAX_POSTS_PER_RUN]

    for notice in posts_to_publish:
        print(f"\n🚀 नई पोस्ट तैयार हो रही है: [{notice['uni']}] {notice['title']}")
        
        # 1. AI से पोस्ट बनवाना
        post_html = generate_ai_post(notice)
        
        # 2. Blogger पर पब्लिश करना
        published = publish_to_blogger(notice, post_html)
        
        # 3. Telegram पर सूचना भेजना
        if published:
            send_telegram_alert(notice)

    # सभी प्राप्त नोटिसों को हिस्ट्री में सेव कर लें ताकि दोबारा न आएं
    for n in all_notices:
        if n["url"] not in history:
            history.append(n["url"])
            
    save_history(history)
    print("✨ टास्क पूरा हुआ!")

if __name__ == "__main__":
    main()
