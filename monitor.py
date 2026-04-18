import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIG ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CHECK_INTERVAL_MINUTES = 30
SEARCH_URL = "https://www.auksjonen.no/auksjoner/bruktbil/skoda"
KEYWORDS = ["superb"]  # case-insensitive
SEEN_FILE = "seen_ids.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


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


def fetch_listings():
    results = []
    try:
        r = requests.get(SEARCH_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Find all auction listing cards/links
        # auksjonen.no uses <a> tags with href like /auksjon/bruktbil/...
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if "/auksjon/" not in href:
                continue
            title_el = link.get_text(separator=" ", strip=True)
            title = title_el if title_el else href

            # Check if any keyword matches
            if any(kw in title.lower() for kw in KEYWORDS):
                # Use href as unique ID
                listing_id = href.split("?")[0].rstrip("/")
                full_url = f"https://www.auksjonen.no{href}" if href.startswith("/") else href
                results.append({
                    "id": listing_id,
                    "title": title,
                    "url": full_url,
                })

    except Exception as e:
        logging.error(f"Error fetching listings: {e}")

    # Deduplicate by id
    seen_ids_local = set()
    unique = []
    for item in results:
        if item["id"] not in seen_ids_local:
            seen_ids_local.add(item["id"])
            unique.append(item)

    return unique


def check():
    logging.info("Checking auksjonen.no for Skoda Superb...")
    seen = load_seen()
    listings = fetch_listings()

    new_count = 0
    for listing in listings:
        if listing["id"] not in seen:
            logging.info(f"NEW listing found: {listing['title']}")
            message = (
                f"🚗 <b>Нове оголошення на auksjonen.no!</b>\n\n"
                f"<b>{listing['title']}</b>\n\n"
                f"🔗 {listing['url']}\n\n"
                f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            send_telegram(message)
            seen.add(listing["id"])
            new_count += 1

    if new_count == 0:
        logging.info("No new listings found.")

    save_seen(seen)


def main():
    logging.info("=== Auksjonen.no Skoda Superb Monitor started ===")
    logging.info(f"Checking every {CHECK_INTERVAL_MINUTES} minutes")

    # Send startup notification
    send_telegram(
        f"✅ <b>Монітор запущено!</b>\n"
        f"Слідкую за Skoda Superb на auksjonen.no\n"
        f"Перевірка кожні {CHECK_INTERVAL_MINUTES} хв."
    )

    while True:
        check()
        logging.info(f"Sleeping for {CHECK_INTERVAL_MINUTES} minutes...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
