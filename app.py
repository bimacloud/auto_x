import requests
import webbrowser
from urllib.parse import parse_qs, urlparse
from requests.auth import HTTPBasicAuth
import json
from bs4 import BeautifulSoup
import time
import random
import os
from datetime import datetime

# ✅ Ganti kredensial kamu
client_id = 'cXhHcFRYOGMwNkNYZG9hYzBkQjM6MTpjaQ'
client_secret = 'si3YVfU6fqYEnHNIehBxmtSlxHFDu7G2sc_k9nR6__D33Ls0wW'
redirect_uri = 'http://localhost:5000/callback'

token_file = "tokens.json"

def save_tokens(tokens):
    with open(token_file, "w") as f:
        json.dump(tokens, f)

def load_tokens():
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            return json.load(f)
    return None

def refresh_access_token(refresh_token):
    print("♻️ Refresh token...")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    response = requests.post("https://api.twitter.com/2/oauth2/token", data=data, auth=HTTPBasicAuth(client_id, client_secret))
    if response.status_code == 200:
        new_tokens = response.json()
        save_tokens(new_tokens)
        return new_tokens['access_token'], new_tokens.get('refresh_token', refresh_token)
    else:
        print("❌ Gagal refresh token:", response.text)
        exit()

# Token login
tokens = load_tokens()
if not tokens:
    authorize_url = (
        "https://twitter.com/i/oauth2/authorize"
        "?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&scope=tweet.read%20tweet.write%20users.read%20offline.access"
        "&state=randomstate123"
        "&code_challenge=challenge"
        "&code_challenge_method=plain"
    )

    print("\n🔗 Buka URL ini di browser untuk login dan otorisasi akun Twitter kamu:")
    webbrowser.open(authorize_url)

    redirect_response = input("\n📥 Paste URL yang kamu dapat setelah login: ")
    code = parse_qs(urlparse(redirect_response).query).get("code", [None])[0]

    if not code:
        print("❌ Gagal mengambil kode dari URL. Coba lagi.")
        exit()

    token_url = "https://api.twitter.com/2/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": "challenge"
    }
    response = requests.post(token_url, headers=headers, data=data, auth=HTTPBasicAuth(client_id, client_secret))
    if response.status_code != 200:
        print("❌ Gagal tukar kode:")
        print("Status:", response.status_code)
        print("Response:", response.text)
        exit()
    tokens = response.json()
    save_tokens(tokens)

access_token = tokens['access_token']
refresh_token = tokens.get('refresh_token')
print("\n✅ Access token diperoleh!")

# Header untuk API tweet
tweet_url = "https://api.twitter.com/2/tweets"
tweet_headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Load semua link
with open("list_detail_links.txt", "r") as file:
    all_links = [line.strip() for line in file if line.strip()]

# Load posted link
posted_links = set()
if os.path.exists("posted.txt"):
    with open("posted.txt", "r") as file:
        posted_links = set(line.strip() for line in file if line.strip())

# Log jumlah post harian
log_file = "posted_log.json"
today = datetime.now().strftime("%Y-%m-%d")
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        daily_log = json.load(f)
else:
    daily_log = {}

posted_today = daily_log.get(today, 0)
MAX_POSTS_PER_DAY = 15

if posted_today >= MAX_POSTS_PER_DAY:
    print("✅ Batas maksimal 15 post hari ini sudah tercapai. Lanjut besok.")
    exit()

# Filter link yang belum diposting
links_to_post = [link for link in all_links if link not in posted_links]

for i, link in enumerate(links_to_post):
    if posted_today >= MAX_POSTS_PER_DAY:
        print("✅ Batas maksimal 15 post hari ini sudah tercapai. Lanjut besok.")
        break

    try:
        print(f"\n🔍 Ambil metadata dari: {link}")
        page = requests.get(link, timeout=10)
        soup = BeautifulSoup(page.text, 'html.parser')

        title = soup.find("meta", property="og:title") or soup.find("title")
        description = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})

        title_text = title['content'] if title and title.has_attr('content') else (title.text if title else 'Tanpa judul')
        description_text = description['content'] if description and description.has_attr('content') else ''

        tweet_text = f"{title_text}\n{description_text}\n{link}"
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."

        payload = {"text": tweet_text}
        tweet_response = requests.post(tweet_url, headers=tweet_headers, data=json.dumps(payload))

        if tweet_response.status_code == 401:
            access_token, refresh_token = refresh_access_token(refresh_token)
            tweet_headers["Authorization"] = f"Bearer {access_token}"
            tweet_response = requests.post(tweet_url, headers=tweet_headers, data=json.dumps(payload))

        if tweet_response.status_code == 201:
            print(f"✅ Berhasil tweet: {link}")
            with open("posted.txt", "a") as posted_file:
                posted_file.write(link + "\n")
            posted_today += 1
            daily_log[today] = posted_today
            with open(log_file, "w") as logf:
                json.dump(daily_log, logf)
            save_tokens({"access_token": access_token, "refresh_token": refresh_token})
        else:
            print(f"❌ Gagal tweet {link}")
            print("Status:", tweet_response.status_code)
            print("Response:", tweet_response.text)

    except Exception as e:
        print(f"\n⚠️ Error saat memproses: {link}")
        print("Error:", e)

    if posted_today < MAX_POSTS_PER_DAY:
        if i == 0:
            delay = 15 * 60
            print("⏳ Delay 15 menit setelah tweet pertama...")
        else:
            delay = random.randint(11, 25) * 60
            print(f"⏳ Delay random {delay // 60} menit sebelum tweet berikutnya...")
        time.sleep(delay)

print("\n🚀 Selesai eksekusi hari ini.")
