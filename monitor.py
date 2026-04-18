import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CHECK_INTERVAL_MINUTES = 180
KEYWORDS = ["superb"]  # case-insensitive

SEEN_FILE = "seen_ids.json"
STATS_FILE = "stats.json"

SOURCES = [
    {
        "name": "auksjonen.no",
        "url": "https://www.auksjonen.no/auksjoner/bruktbil/skoda",
        "type": "html",
        "base_url": "https://www.auksjonen.no",
    },
    {
        "name": "stadssalg.no",
        "url": "https://www.stadssalg.no/items?filter_by=category:Kj%C3%B8ret%C3%B8y::subCategory:Personbil::brand:SKODA",
        "type": "playwright",
        "base_url": "https://www.stadssalg.no",
    },
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}


# --- PERSISTENCE ---

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"total_checks": 0, "last_heartbeat": None}


def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)


# --- TELEGRAM ---

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logging.info("Telegram notification sent.")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")


# --- FETCHERS ---

def fetch_html(source):
    results = []
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if "/auksjon/" not in href:
                continue
            title = link.get_text(separator=" ", strip=True)
            if any(kw in title.lower() for kw in KEYWORDS):
                listing_id = href.split("?")[0].rstrip("/")
                full_url = f"{source['base_url']}{href}" if href.startswith("/") else href
                results.append({"id": listing_id, "title": title, "url": full_url, "source": source["name"]})
    except Exception as e:
        logging.error(f"[{source['name']}] HTML fetch error: {e}")
    return results


def fetch_playwright(source):
    results = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(source["url"], wait_until="networkidle", timeout=30000)
            # Wait for listings to load
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if "/items/" not in href:
                continue
            title = link.get_text(separator=" ", strip=True)
            if not title or len(title) < 3:
                # Try parent element text
                title = link.parent.get_text(separator=" ", strip=True)[:120] if link.parent else href
            if any(kw in title.lower() for kw in KEYWORDS):
                listing_id = href.split("?")[0].rstrip("/")
                full_url = f"{source['base_url']}{href}" if href.startswith("/") else href
                results.append({"id": listing_id, "title": title, "url": full_url, "source": source["name"]})
    except ImportError:
        logging.warning("playwright not installed, skipping stadssalg.no")
    except Exception as e:
        logging.error(f"[{source['name']}] Playwright fetch error: {e}")
    return results


def fetch_listings(source):
    if source["type"] == "html":
        items = fetch_html(source)
    elif source["type"] == "playwright":
        items = fetch_playwright(source)
    else:
        items = []

    # Deduplicate
    seen_local = set()
    unique = []
    for item in items:
        if item["id"] not in seen_local:
            seen_local.add(item["id"])
            unique.append(item)
    return unique


# --- HEARTBEAT ---

def maybe_send_heartbeat(stats):
    now = datetime.now()
    last = stats.get("last_heartbeat")
    if last:
        last_dt = datetime.fromisoformat(last)
        if now - last_dt < timedelta(hours=24):
            return
    send_telegram(
        f"💚 <b>Монітор живий!</b>\n"
        f"Перевірок зроблено: {stats['total_checks']}\n"
        f"Слідкую за: {', '.join(s['name'] for s in SOURCES)}\n"
        f"Ключові слова: {', '.join(KEYWORDS)}\n"
        f"⏰ {now.strftime('%d.%m.%Y %H:%M')}"
    )
    stats["last_heartbeat"] = now.isoformat()


# --- MAIN LOOP ---

def check(seen, stats):
    logging.info("Checking all sources...")
    new_count = 0

    for source in SOURCES:
        listings = fetch_listings(source)
        logging.info(f"[{source['name']}] Found {len(listings)} matching listings")

        for listing in listings:
            if listing["id"] not in seen:
                logging.info(f"NEW: {listing['title']} ({listing['source']})")
                message = (
                    f"🚗 <b>Нове оголошення!</b>\n\n"
                    f"📍 <b>{listing['source']}</b>\n"
                    f"<b>{listing['title']}</b>\n\n"
                    f"🔗 {listing['url']}\n\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                send_telegram(message)
                seen.add(listing["id"])
                new_count += 1

    stats["total_checks"] += 1
    if new_count == 0:
        logging.info("No new listings.")

    return seen, stats


def main():
    logging.info("=== Skoda Superb Monitor started ===")

    # Install playwright browsers if needed
    try:
        import subprocess
        subprocess.run(["playwright", "install", "chromium", "--with-deps"],
                       capture_output=True, timeout=120)
        logging.info("Playwright chromium ready.")
    except Exception as e:
        logging.warning(f"Playwright install skipped: {e}")

    send_telegram(
        f"✅ <b>Монітор запущено!</b>\n"
        f"Слідкую за Skoda Superb на:\n"
        f"• auksjonen.no\n"
        f"• stadssalg.no\n\n"
        f"Перевірка кожні {CHECK_INTERVAL_MINUTES} хв."
    )

    seen = load_seen()
    stats = load_stats()

    while True:
        seen, stats = check(seen, stats)
        save_seen(seen)
        maybe_send_heartbeat(stats)
        save_stats(stats)
        logging.info(f"Sleeping {CHECK_INTERVAL_MINUTES} min...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
