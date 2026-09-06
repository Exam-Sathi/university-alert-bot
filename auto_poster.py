import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
from google import genai

# Configuration & Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BLOGGER_EMAIL = os.environ.get("BLOGGER_EMAIL")       # Step 1 वाली सीक्रेट ब्लॉगर ईमेल
SENDER_GMAIL = os.environ.get("SENDER_GMAIL")         # आपका Gmail
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS")     # Gmail App Password (16 अक्षर का)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HISTORY_FILE = "posted_notices.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_latest_university_notices():
    """
    उदाहरण: PDUSU Sikar की वेबसाइट से ताज़ा नोटिस निकालना
    (ज़रूरत पड़ने पर इस URL और क्लास को दूसरी यूनिवर्सिटी के हिसाब से बदला जा सकता है)
    """
    url = "https://shekhauni.ac.in/news"  # यूनिवर्सिटी का नोटिफिकेशन पेज
    headers = {"User-Agent": "Mozilla/5.0"}
    notices = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # यूनिवर्सिटी के लिंक्स और नोटिस ढूँढना
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link["href"]
                # अगर लिंक में result, exam, timetable, syllabus या notice का ज़िक्र हो
                keywords = ["result", "exam", "time table", "admit", "notice", "syllabus", "परीक्षा", "परिणाम"]
                if any(k in text.lower() for k in keywords) and len(text) > 10:
                    full_url = href if href.startswith("http") else "https://shekhauni.ac.in/" + href.lstrip("/")
                    notices.append({"title": text, "url": full_url})
    except Exception as e:
        print(f"Error scraping notices: {e}")
        
    return notices[:5]  # टॉप 5 ताज़ा नोटिस

def generate_post_content(title, notice_url):
    """Google Gemini AI से आकर्षक और छात्रोपयोगी पोस्ट तैयार करवाना"""
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    आप Exam Sathi (राजस्थान का प्रतिष्ठित छात्र पोर्टल) के कंटेंट लेखक हैं।
    यूनिवर्सिटी से यह नया नोटिस आया है:
    शीर्षक: {title}
    नोटिस/डाउनलोड लिंक: {notice_url}

    कृपया इसके लिए एक आकर्षक HTML ब्लॉग पोस्ट तैयार करें।
    शर्तें:
    1. भाषा: सरल हिंदी (Hinglish/Hindi) जो छात्रों को आसानी से समझ आए।
    2. इसमें शामिल करें:
       - महत्वपूर्ण हाइलाइट्स (Bullet points में)।
       - रिजल्ट या नोटिस कैसे चेक/डाउनलोड करें (Step-by-step)।
       - एक सुंदर और बड़ा डाउनलोड बटन: <a href="{notice_url}" style="background:#1d4ed8;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;margin:15px 0;">📥 डाउनलोड नोटिस / रिजल्ट चेक करें</a>
       - डिस्क्लेमर कि छात्र आधिकारिक वेबसाइट से भी पुष्टि करें।
    3. केवल शुद्ध HTML कोड दें (कोई markdown ```html न लगाएं)।
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def publish_to_blogger(title, html_content):
    """Blogger की सीक्रेट ईमेल पर पोस्ट भेजना"""
    if not (BLOGGER_EMAIL and SENDER_GMAIL and GMAIL_APP_PASS):
        print("Email configuration missing. Skipping Blogger post.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SENDER_GMAIL
    msg["To"] = BLOGGER_EMAIL

    # पोस्ट में लेबल्स जोड़ना
    post_html = html_content + "<br/><br/><p>Labels: Result, Notice, PDUSU</p>"
    msg.attach(MIMEText(post_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_GMAIL, GMAIL_APP_PASS)
            server.sendmail(SENDER_GMAIL, BLOGGER_EMAIL, msg.as_string())
        print(f"✅ Published on Blogger: {title}")
        return True
    except Exception as e:
        print(f"❌ Failed to publish on Blogger: {e}")
        return False

def send_telegram_alert(title, notice_url):
    """टेलीग्राम चैनल पर तुरंत सूचना भेजना"""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    message = (
        f"🚨 <b>नया यूनिवर्सिटी अपडेट!</b>\n\n"
        f"📌 <b>{title}</b>\n\n"
        f"🔗 तुरंत चेक करें और डाउनलोड करें:\n"
        f"👉 {notice_url}\n\n"
        f"🌐 <i>पोर्टल: Exam Sathi</i>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
        print("✅ Telegram notification sent!")
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    history = load_history()
    notices = get_latest_university_notices()
    
    for notice in notices:
        title = notice["title"]
        url = notice["url"]
        
        # अगर यह नोटिस पहले पब्लिश नहीं हुआ है
        if url not in history:
            print(f"📢 नया नोटिस मिला: {title}")
            
            # 1. AI से पोस्ट बनवाना
            post_content = generate_post_content(title, url)
            
            # 2. Blogger पर पब्लिश करना
            published = publish_to_blogger(title, post_content)
            
            # 3. Telegram पर भेजना
            send_telegram_alert(title, url)
            
            # 4. हिस्ट्री में सेव करना (ताकि दोबारा पोस्ट न हो)
            history.append(url)
            save_history(history)
            
            # एक बार में 1-2 ताज़ा पोस्ट ही डालें ताकि स्पैम न लगे
            break

if __name__ == "__main__":
    main()
