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
KEYWORDS = ["superb"]

SEEN_FILE = "seen_ids.json"
STATS_FILE = "stats.json"

SOURCES = [
    {
        "name": "auksjonen.no",
        "url": "https://www.auksjonen.no/auksjoner/bruktbil/skoda",
        "link_pattern": "/auksjon/",
        "base_url": "https://www.auksjonen.no",
    },
    {
        "name": "stadssalg.no",
        "url": "https://www.stadssalg.no/items?filter_by=category:Kj%C3%B8ret%C3%B8y::subCategory:Personbil::brand:SKODA",
        "link_pattern": "/items/",
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


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


def fetch_listings(source):
    results = []
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a", href=True)
        seen_local = set()

        for link in links:
            href = link["href"]
            if source["link_pattern"] not in href:
                continue

            title = link.get_text(separator=" ", strip=True)
            if not title or len(title) < 5:
                continue

            if not any(kw in title.lower() for kw in KEYWORDS):
                continue

            listing_id = href.split("?")[0].rstrip("/")
            if listing_id in seen_local:
                continue
            seen_local.add(listing_id)

            full_url = (
                f"{source['base_url']}{href}"
                if href.startswith("/")
                else href
            )
            results.append({
                "id": listing_id,
                "title": title,
                "url": full_url,
                "source": source["name"],
            })

    except Exception as e:
        logging.error(f"[{source['name']}] Error: {e}")

    return results


def maybe_send_heartbeat(stats):
    now = datetime.now()
    last = stats.get("last_heartbeat")
    if last:
        if now - datetime.fromisoformat(last) < timedelta(hours=24):
            return
    send_telegram(
        f"💚 <b>Монітор живий!</b>\n"
        f"Перевірок зроблено: {stats['total_checks']}\n"
        f"Інтервал: кожні {CHECK_INTERVAL_MINUTES} хв.\n"
        f"⏰ {now.strftime('%d.%m.%Y %H:%M')}"
    )
    stats["last_heartbeat"] = now.isoformat()


def check(seen, stats):
    logging.info("--- Starting check ---")
    new_count = 0

    for source in SOURCES:
        listings = fetch_listings(source)
        logging.info(f"[{source['name']}] Found {len(listings)} matching listings")

        for listing in listings:
            if listing["id"] not in seen:
                logging.info(f"NEW: {listing['title']}")
                send_telegram(
                    f"🚗 <b>Нове оголошення!</b>\n\n"
                    f"📍 <b>{listing['source']}</b>\n"
                    f"<b>{listing['title']}</b>\n\n"
                    f"🔗 {listing['url']}\n\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                seen.add(listing["id"])
                new_count += 1

    stats["total_checks"] += 1
    logging.info(f"Done. New: {new_count}. Total checks: {stats['total_checks']}")
    return seen, stats


def main():
    logging.info("=== Skoda Superb Monitor started ===")

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
