"""
Reviews_Scraper
-----------------------------
Flow:
  Option A — City name:
    1. Enter city name
    2. How many hotels to scrape
    3. How many reviews per hotel
    4. Saves: {City}_Hotels.json
              All_Reviews_Dir/{Hotel_Name}.json

  Option B — Hotel URL:
    1. Enter hotel URL
    2. How many reviews
    3. Saves: All_Reviews_Dir/{Hotel_Name}.json
"""

import requests
import json
import time
from datetime import datetime
import re
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = "All_Reviews_Dir"

# ── COOKIES (update when expired) ────────────────────────────────────────────
#load cookies.json into cookies
with open("cookies.json", "r", encoding="utf-8") as f:
    _raw = json.load(f)
cookies = {c["name"]: c["value"] for c in _raw}

headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    'origin': 'https://www.tripadvisor.com',
    'sec-ch-ua': '"Chromium";v="149", "Not)A;Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'same-origin',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
}

GRAPHQL_URL = 'https://www.tripadvisor.com/data/graphql/ids'
BATCH_SIZE  = 10


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def ask_int(prompt: str, min_val: int = 0) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if val >= min_val:
                return val
        except ValueError:
            pass
        print(f"  ❌ Please enter a number ({min_val} or more).")


def safe_filename(name: str, max_len: int = 60) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)[:max_len]


def save_json(data, filepath: str):
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _d(obj, *keys, default=None):
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
    return obj if obj is not None else default


# ══════════════════════════════════════════════════════════════
# PHASE 3 — Scrape reviews for a hotel
# ══════════════════════════════════════════════════════════════

def fetch_reviews_page(location_id: int, hotel_url: str, offset: int, limit: int) -> list:
    headers['referer'] = hotel_url
    payload = [{
        'variables': {
            'locationId':           location_id,
            'filters':              [{'axis': 'LANGUAGE', 'selections': ['en']}],
            'limit':                limit,
            'offset':               offset,
            'sortType':             None,
            'sortBy':               'SERVER_DETERMINED',
            'language':             'en',
            'doMachineTranslation': True,
            'photosPerReviewLimit': 3,
        },
        'extensions': {'preRegisteredQueryId': 'ef1a9f94012220d3'},
    }]
    try:
        resp = requests.post(GRAPHQL_URL, cookies=cookies, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            log.warning(f"HTTP {resp.status_code}")
            return []
        return resp.json()[0]['data']['ReviewsProxy_getReviewListPageForLocation'][0]['reviews']
    except Exception as e:
        log.warning(f"Review fetch error: {e}")
        return []


def clean_review(r: dict, hotel: dict) -> dict:
    user     = r.get('userProfile') or {}
    owner    = r.get('ownerResponse') or {}
    trip     = r.get('tripInfo') or {}
    hometown = ((user.get('hometown') or {}).get('location') or {}).get('additionalNames', {})
    return {
        'hotel_name':         hotel.get('name'),
        'hotel_url':          hotel.get('url'),
        'hotel_rating':       hotel.get('rating'),
        'hotel_review_count': hotel.get('reviewCount'),
        'hotel_address':      hotel.get('address'),
        'hotel_city':         hotel.get('city'),
        'hotel_award':        hotel.get('award'),
        'hotel_median_price': hotel.get('medianPrice'),
        'review_id':          r.get('id'),
        'rating':             r.get('rating'),
        'title':              r.get('title'),
        'text':               r.get('text'),
        'published_date':     r.get('publishedDate'),
        'language':           r.get('originalLanguage'),
        'helpful_votes':      r.get('helpfulVotes'),
        'trip_type':          trip.get('tripType'),
        'stay_date':          trip.get('stayDate'),
        'reviewer_name':      user.get('displayName'),
        'reviewer_id':        user.get('userId'),
        'reviewer_hometown':  hometown.get('long'),
        'reviewer_contributions': (user.get('contributionCounts') or {}).get('sumAllUgc'),
        # 'owner_response':      owner.get('text'),
        # 'owner_response_date': owner.get('publishedDate'),
        # 'owner_name':          (owner.get('userProfile') or {}).get('displayName'),
    }


def scrape_reviews(hotel: dict, max_reviews: int) -> list:
    all_reviews = []
    offset      = 0
    location_id = hotel.get('locationId') or hotel.get('location_id')

    print(f"\n  🏨  {hotel['name']}")
    print(f"      ⭐ {hotel.get('rating', 'N/A')}  |  {hotel.get('reviewCount', '?')} total reviews  |  fetching: {'all' if max_reviews == 0 else max_reviews}")

    while True:
        remaining = (max_reviews - len(all_reviews)) if max_reviews > 0 else BATCH_SIZE
        batch     = min(BATCH_SIZE, remaining)

        print(f"      📄 offset={offset:4d} | batch={batch}...", end=" ", flush=True)
        raw = fetch_reviews_page(location_id, hotel['url'], offset, batch)

        if not raw:
            print("no results.")
            break

        all_reviews.extend([clean_review(r, hotel) for r in raw])
        print(f"✓ got {len(raw)}  (total so far: {len(all_reviews)})")

        if len(raw) < batch:
            print("      ✅ Last page reached.")
            break
        if max_reviews > 0 and len(all_reviews) >= max_reviews:
            print("      ✅ Review limit reached.")
            break

        offset += batch
        time.sleep(random.uniform(1.5, 2.5))

    return all_reviews


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  TripAdvisor Scraper")
    print("=" * 60)
    print("\n  [1] Scrape by city name")
    print("  [2] Scrape by hotel URL")

    while True:
        choice = input("\n> Enter 1 or 2: ").strip()
        if choice in ('1', '2'):
            break
        print("  ❌ Enter 1 or 2.")

    # ──────────────────────────────────────────────────────────
    # PATH A — City name
    # ──────────────────────────────────────────────────────────
    if choice == '1':
        city_name = input("\n🌍 Enter city name:\n> ").strip()
        if not city_name:
            print("❌ No city entered.")
            return

        
        # Scrape all hotels
        from hotels_scraper import scrape_all_city_hoetls

        # all_hotels = scrape_all_city_hoetls(city_info['geoId'], city_name)
        all_hotels = scrape_all_city_hoetls(city_name)
        if not all_hotels:
            print(f"\n❌ No hotels found for {city_name}.")
            print("   → Cookies may have expired. Re-export from Cookie-Editor.")
            return

        # Display hotel list
        print(f"\n{'─'*60}")
        print(f"  Found {len(all_hotels)} hotels in {city_name}")
        print(f"{'─'*60}")
        print(f"  {'#':<4} {'Name':<40} {'⭐':>5}  {'Reviews':>8}")
        print(f"  {'─'*4} {'─'*40} {'─'*5}  {'─'*8}")
        for i, h in enumerate(all_hotels, 1):
            rating  = f"{h['rating']:.1f}" if h.get('rating') else '  N/A'
            reviews = str(h.get('reviewCount') or '?')
            print(f"  {i:<4} {h['name']:<40} {rating:>5}  {reviews:>8}")

        # How many hotels to scrape
        num_hotels = ask_int(f"\n📋 How many hotels to scrape? (1–{len(all_hotels)}, 0 = all):\n> ")
        if num_hotels == 0 or num_hotels >= len(all_hotels):
            selected_hotels = all_hotels
        else:
            selected_hotels = all_hotels[:num_hotels]

        # Save hotels JSON
        safe_city   = safe_filename(city_name)
        hotels_file = f"{safe_city}_Hotels.json"
        save_json(selected_hotels, hotels_file)
        print(f"\n  💾 Hotels saved → {hotels_file}")

        # How many reviews per hotel
        max_reviews = ask_int(f"\n📊 How many reviews per hotel? (0 = all):\n> ")

        # Scrape reviews for each hotel
        print(f"\n🚀 Scraping reviews for {len(selected_hotels)} hotel(s)...\n")
        failed = []

        for hotel in selected_hotels:
            reviews = scrape_reviews(hotel, max_reviews)
            if reviews:
                fname = os.path.join(OUTPUT_DIR, f"{safe_filename(hotel['name'])}.json")
                save_json(reviews, fname)
                print(f"      💾 Saved {len(reviews)} reviews → {fname}")
            else:
                failed.append(hotel['name'])
            time.sleep(random.uniform(1.0, 2.0))

        # Summary
        print(f"\n{'='*60}")
        print(f"  ✅ Done!")
        print(f"     City          : {city_name}")
        print(f"     Hotels file   : {hotels_file}")
        print(f"     Reviews dir   : {OUTPUT_DIR}/")
        print(f"     Hotels done   : {len(selected_hotels) - len(failed)}/{len(selected_hotels)}")
        if failed:
            print(f"     ⚠️  Failed     : {', '.join(failed)}")
            print(f"        → Re-export cookies from Cookie-Editor.")

    # ──────────────────────────────────────────────────────────
    # PATH B — Hotel URL
    # ──────────────────────────────────────────────────────────
    else:
        while True:
            url = input("\n🔗 Enter TripAdvisor hotel URL:\n> ").strip()
            if 'tripadvisor.com' in url and 'Hotel_Review' in url:
                break
            print("  ❌ Must be a TripAdvisor Hotel_Review URL.")

        # Parse location_id from URL
        match = re.search(r'Hotel_Review-g(\d+)-d(\d+)-Reviews-([^/?]+)', url)
        if not match:
            print("  ❌ Could not parse hotel URL.")
            return

        hotel_name_raw = match.group(3).replace('-', ' ').replace('_', ' ')
        hotel = {
            'locationId': int(match.group(2)),
            'geoId':      int(match.group(1)),
            'name':       hotel_name_raw,
            'url':        url.split('?')[0],
            'rating':     None, 'reviewCount': None,
            'address':    None, 'city':        None,
            'award':      None, 'medianPrice': None,
        }

        max_reviews = ask_int(f"\n How many reviews? (0 = all):\n> ")

        print(f"\n🚀 Scraping reviews...\n")
        reviews = scrape_reviews(hotel, max_reviews)

        if reviews:
            fname = os.path.join(OUTPUT_DIR, f"{safe_filename(hotel['name'])}.json")
            save_json(reviews, fname)
            print(f"\n   Saved {len(reviews)} reviews → {fname}")

            # Sample
            s = reviews[0]
            print(f"\n  📝 Sample:")
            print(f"     Reviewer : {s['reviewer_name']} ({s.get('reviewer_hometown') or '?'})")
            print(f"     Rating   : {s['rating']}/5  |  {s.get('trip_type')}  |  {s['published_date']}")
            print(f"     Title    : {s['title']}")
            print(f"     Text     : {str(s['text'])[:120]}...")
        else:
            print("\n No reviews scraped.")
            print("     → Cookies may have expired. Re-export from Cookie-Editor.")


if __name__ == "__main__":
    start_time = datetime.now()

    main()

    end_time = datetime.now()

    total_time = end_time - start_time

    print("Total Time:", total_time)