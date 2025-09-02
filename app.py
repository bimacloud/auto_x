# -*- coding: utf-8 -*-
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

# =========================
# Kredensial OAuth2 PKCE (ASLI ANDA – TIDAK DIUBAH)
# =========================
client_id = 'amZtWC1KSnRZdHV3NEk4M1N1X0M6MTpjaQ'
client_secret = 'InvHSvAoMdGxr6ZZGleWKAzSgTtp58P8Y2Xlg2NYwuBRgY9eqg'
redirect_uri = 'http://localhost:5000/callback'

token_file = "tokens.json"

# =========================
# OPSIONAL: Kredensial OAuth1.0a (untuk upload gambar v1.1)
# set lewat ENV kalau ingin foto pasti tampil
# export X_API_KEY=... X_API_SECRET=... X_ACCESS_TOKEN=... X_ACCESS_SECRET=...
# =========================
X_API_KEY       = os.getenv("X_API_KEY")
X_API_SECRET    = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN  = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

HAS_OAUTH1 = all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET])

# =========================
# Konstanta umum
# =========================
AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL     = "https://api.twitter.com/2/oauth2/token"
TWEET_URL_V2  = "https://api.x.com/2/tweets"
UPLOAD_MEDIA  = "https://upload.twitter.com/1.1/media/upload.json"

SCOPE = "tweet.read tweet.write users.read offline.access"

MAX_TWEET   = 280
TCO_URL_LEN = 23   # panjang URL menurut t.co
SEP = "\n"
ELLIPSIS = "…"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"

# Files
LINKS_FILE   = "list_detail_links.txt"
POSTED_FILE  = "posted.txt"
LOG_FILE     = "posted_log.json"
MAX_POSTS_PER_DAY = 15

# =========================
# Util token (OAuth2 PKCE)
# =========================
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
    response = requests.post(TOKEN_URL, data=data, auth=HTTPBasicAuth(client_id, client_secret))
    if response.status_code == 200:
        new_tokens = response.json()
        save_tokens(new_tokens)
        return new_tokens['access_token'], new_tokens.get('refresh_token', refresh_token)
    else:
        print("❌ Gagal refresh token:", response.text)
        raise SystemExit(1)

def ensure_tokens():
    tokens = load_tokens()
    if tokens:
        return tokens

    code_verifier = "challenge"
    authorize_url = (
        f"{AUTHORIZE_URL}"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=tweet.read%20tweet.write%20users.read%20offline.access"
        f"&state=randomstate123"
        f"&code_challenge=challenge"
        f"&code_challenge_method=plain"
    )
    print("\n🔗 Buka URL ini di browser untuk login & authorize X:")
    print(authorize_url)
    try:
        webbrowser.open(authorize_url)
    except:
        pass

    redirect_response = input("\n📥 Paste URL redirect setelah login: ").strip()
    code = parse_qs(urlparse(redirect_response).query).get("code", [None])[0]
    if not code:
        print("❌ Kode otorisasi tidak ditemukan.")
        raise SystemExit(1)

    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(TOKEN_URL, headers=headers, data=data, auth=HTTPBasicAuth(client_id, client_secret))
    if resp.status_code != 200:
        print("❌ Gagal tukar code → token")
        print("Status:", resp.status_code)
        print("Response:", resp.text)
        raise SystemExit(1)

    tokens = resp.json()
    save_tokens(tokens)
    return tokens

# =========================
# Ambil meta halaman
# =========================
def fetch_page_meta(url):
    try:
        res = requests.get(url, timeout=12, headers={"User-Agent": UA}, allow_redirects=True)
        res.raise_for_status()
    except Exception as e:
        print(f"⚠️ Gagal fetch halaman: {url} — {e}")
        return {"title": "", "description": "", "image_url": ""}

    soup = BeautifulSoup(res.text, 'html.parser')

    def pick(*specs):
        for sel, attr in specs:
            tag = soup.select_one(sel)
            if tag:
                if attr == "content" and tag.has_attr("content"):
                    v = tag["content"].strip()
                    if v: return v
                if attr == "text" and tag.text:
                    v = tag.get_text(strip=True)
                    if v: return v
        return ""

    title = pick(
        ('meta[property="og:title"]', 'content'),
        ('meta[name="twitter:title"]', 'content'),
        ('title', 'text'),
    )
    desc  = pick(
        ('meta[property="og:description"]', 'content'),
        ('meta[name="twitter:description"]', 'content'),
        ('meta[name="description"]', 'content'),
    )
    img   = pick(
        ('meta[property="og:image:secure_url"]', 'content'),
        ('meta[property="og:image"]', 'content'),
        ('meta[name="twitter:image:src"]', 'content'),
        ('meta[name="twitter:image"]', 'content'),
    )

    return {"title": title or "", "description": desc or "", "image_url": img or ""}

# =========================
# Compose tweet: URL selalu utuh
# =========================
def compose_tweet_text(title, description, url):
    base_title = (title or "").strip()
    base_desc  = (description or "").strip()

    parts = [p for p in [base_title, base_desc] if p]
    body = SEP.join(parts)

    budget = MAX_TWEET - TCO_URL_LEN - len(SEP)  # sisakan 1 newline + URL
    if len(body) > budget:
        body = body[:max(0, budget - len(ELLIPSIS))].rstrip() + ELLIPSIS

    return f"{body}{SEP}{url}" if body else url

# =========================
# Upload media (opsional, OAuth1)
# =========================
def upload_media_oauth1(image_url):
    if not HAS_OAUTH1:
        return None  # tidak tersedia, biar fallback teks

    try:
        img_resp = requests.get(image_url, headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
        img_resp.raise_for_status()
        if "image" not in img_resp.headers.get("content-type", "").lower():
            print(f"⚠️ Bukan konten image: {img_resp.headers.get('content-type')}")
            return None
    except Exception as e:
        print(f"⚠️ Gagal ambil gambar: {e}")
        return None

    from requests_oauthlib import OAuth1
    oauth1 = OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)

    files = {"media": img_resp.content}
    r = requests.post(UPLOAD_MEDIA, files=files, auth=oauth1, timeout=60)
    if r.status_code != 200:
        print(f"⚠️ Upload media gagal: {r.status_code} — {r.text}")
        return None

    media_id = r.json().get("media_id_string")
    return media_id

# =========================
# Tweet (v2) — dua mode:
# 1) pakai Bearer (OAuth2 PKCE) untuk teks
# 2) pakai OAuth1 untuk tweet+media (biar konsisten dgn media/upload)
# =========================
def tweet_text_only(access_token, text):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"text": text}
    resp = requests.post(TWEET_URL_V2, headers=headers, json=payload, timeout=60)
    return resp

def tweet_with_media_oauth1(text, media_ids):
    from requests_oauthlib import OAuth1
    oauth1 = OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
    payload = {"text": text, "media": {"media_ids": media_ids}}
    resp = requests.post(TWEET_URL_V2, json=payload, auth=oauth1, timeout=60)
    return resp

# =========================
# Main
# =========================
def main():
    # OAuth2 PKCE tokens (tetap seperti punya Anda)
    tokens = ensure_tokens()
    access_token = tokens['access_token']
    refresh_token = tokens.get('refresh_token')

    # muat link
    if not os.path.exists(LINKS_FILE):
        print(f"❌ File link tidak ditemukan: {LINKS_FILE}")
        return
    with open(LINKS_FILE, "r") as f:
        all_links = [line.strip() for line in f if line.strip()]

    posted_links = set()
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            posted_links = set(line.strip() for line in f if line.strip())

    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                daily_log = json.load(f)
        except:
            daily_log = {}
    else:
        daily_log = {}
    posted_today = int(daily_log.get(today, 0))

    if posted_today >= MAX_POSTS_PER_DAY:
        print("✅ Batas maksimal 15 post hari ini sudah tercapai. Lanjut besok.")
        return

    links_to_post = [link for link in all_links if link not in posted_links]

    for i, link in enumerate(links_to_post):
        if posted_today >= MAX_POSTS_PER_DAY:
            print("✅ Batas maksimal 15 post hari ini sudah tercapai. Lanjut besok.")
            break

        try:
            print(f"\n🔍 Ambil meta: {link}")
            meta = fetch_page_meta(link)
            tweet_text = compose_tweet_text(meta["title"], meta["description"], link)

            # Coba upload media kalau kredensial OAuth1 lengkap & ada image_url
            media_ids = []
            if HAS_OAUTH1 and meta["image_url"]:
                mid = upload_media_oauth1(meta["image_url"])
                if mid:
                    media_ids.append(mid)

            # Kirim tweet:
            if media_ids:
                # tweet dengan media menggunakan OAuth1 (konsisten dengan upload)
                resp = tweet_with_media_oauth1(tweet_text, media_ids)
            else:
                # teks-only pakai Bearer token (OAuth2 PKCE Anda)
                resp = tweet_text_only(access_token, tweet_text)

                # kalau token kadaluwarsa → refresh sekali
                if resp.status_code == 401:
                    access_token, refresh_token = refresh_access_token(refresh_token)
                    resp = tweet_text_only(access_token, tweet_text)

            if resp.status_code in (200, 201):
                print(f"✅ Berhasil tweet: {link}")
                with open(POSTED_FILE, "a") as pf:
                    pf.write(link + "\n")
                posted_today += 1
                daily_log[today] = posted_today
                with open(LOG_FILE, "w") as lf:
                    json.dump(daily_log, lf)
                # simpan token terbaru (OAuth2)
                save_tokens({"access_token": access_token, "refresh_token": refresh_token})
            else:
                print(f"❌ Gagal tweet {link}")
                print("Status:", resp.status_code)
                try:
                    print("Response:", resp.json())
                except:
                    print("Response(raw):", resp.text)

        except Exception as e:
            print(f"⚠️ Error saat memproses: {link}")
            print("Error:", e)

        # Jeda
        if posted_today < MAX_POSTS_PER_DAY:
            if i == 0:
                delay = 15 * 60
                print("⏳ Delay 15 menit setelah tweet pertama…")
            else:
                delay = random.randint(11, 25) * 60
                print(f"⏳ Delay random {delay // 60} menit sebelum tweet berikutnya…")
            time.sleep(delay)

    print("\n🚀 Selesai eksekusi hari ini.")

if __name__ == "__main__":
    main()
