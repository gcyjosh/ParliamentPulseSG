"""
ParliamentPulse SG — Working Scraper
======================================
Uses the real searchResult API endpoint discovered from the parliament website.
Mimics a real browser so the server doesn't block us.

HOW TO RUN:
  cd ~/Desktop/simple-parliament-v4
  /opt/homebrew/bin/python3 scraper.py

Output: data/hansard.json
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path

# ── Settings ──────────────────────────────────────────────────────────────────
OUTPUT_FILE   = Path("data/hansard.json")
CHECKPOINT    = Path("data/.checkpoint.json")
DELAY_SECONDS = 2
RESULTS_PER_PAGE = 20

# We want data from 2020 to now
START_YEAR = 2020
END_YEAR   = datetime.now().year

# The real endpoint discovered from the browser
URL = "https://sprs.parl.gov.sg/search/searchResult"

# Exact headers copied from your browser — this makes us look human
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://sprs.parl.gov.sg",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "referer": "https://sprs.parl.gov.sg/search/#/result",
}

# Types of readings we want
WANTED_TYPES = [
    "bill", "question", "ministerial statement",
    "motion", "adjournment"
]

# Search keywords matching our 18 YouGov concerns
CONCERN_KEYWORDS = [
    "cost of living",
    "housing HDB",
    "healthcare MediShield",
    "job security employment",
    "education schools",
    "mental health",
    "public transport MRT",
    "climate environment",
    "aging elderly seniors",
    "immigration foreign workers",
    "income inequality wages",
    "scam cybersecurity",
    "CPF retirement",
    "racial harmony",
    "youth families childcare",
    "crime safety",
    "POFMA freedom speech",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_checkpoint():
    if CHECKPOINT.exists():
        data = json.loads(CHECKPOINT.read_text())
        print(f"Resuming — {len(data)} searches already done")
        return set(data)
    return set()

def save_checkpoint(done):
    CHECKPOINT.write_text(json.dumps(list(done)))

def load_existing():
    if OUTPUT_FILE.exists():
        data = json.loads(OUTPUT_FILE.read_text())
        print(f"Loaded {len(data)} existing readings")
        return data, {r["id"] for r in data}
    return [], set()

def save_data(readings):
    OUTPUT_FILE.write_text(json.dumps(readings, ensure_ascii=False, indent=2))

def is_wanted(text):
    text = (text or "").lower()
    return any(t in text for t in WANTED_TYPES)

def build_payload(keyword, year, start_index):
    """Build the POST request body."""
    return {
        "keyword": keyword,
        "fromday": "01",
        "frommonth": "01",
        "fromyear": str(year),
        "today": "31",
        "tomonth": "12",
        "toyear": str(year),
        "dateRange": "* TO NOW",
        "reportContent": "with all the words",
        "parliamentNo": "",          # empty = all parliaments
        "selectedSort": "date_dt desc",
        "portfolio": [],
        "mpName": "",
        "rsSelected": "",
        "lang": "",
        "startIndex": str(start_index),
        "endIndex": str(start_index + RESULTS_PER_PAGE - 1),
        "titleChecked": "false",
        "footNoteChecked": "false",
        "ministrySelected": [],
    }

def fetch_page(keyword, year, start_index):
    """Fetch one page of results."""
    payload = build_payload(keyword, year, start_index)
    try:
        r = requests.post(URL, headers=HEADERS, json=payload, timeout=20)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  ⚠ HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"  ⚠ Error: {e}")
        return None

def parse_results(data):
    """Extract readings from an API response."""
    if not data:
        return [], 0

    # If the API returned a list directly, use it as items
    if isinstance(data, list):
        items = data
        total = len(data)
    else:
        # Get total count
        total = (
            data.get("total") or
            data.get("totalResults") or
            data.get("count") or 0
        )
        if isinstance(total, dict):
            total = total.get("value", 0)

        # Get result items
        items = (
            data.get("result") or
            data.get("results") or
            data.get("hits") or
            data.get("data") or []
        )
        if isinstance(items, dict):
            items = items.get("hits", [])

    readings = []
    for item in items:
        # Handle nested _source (Elasticsearch style)
        if "_source" in item:
            item = item["_source"]

        title = (
            item.get("title") or
            item.get("subjectMatter") or
            item.get("subject") or ""
        )
        item_type = (
            item.get("type") or
            item.get("hansardType") or
            item.get("contentType") or ""
        )
        text = (
            item.get("content") or
            item.get("text") or
            item.get("body") or
            item.get("speeches") or ""
        )
        if isinstance(text, list):
            text = "\n\n".join(
                s.get("content", s) if isinstance(s, dict) else str(s)
                for s in text
            )

        date = (
            item.get("sittingDate") or
            item.get("date") or
            item.get("date_dt") or ""
        )

        reading_id = (
            item.get("id") or
            item.get("_id") or
            f"{date}_{len(readings)}"
        )

        readings.append({
            "id": str(reading_id),
            "date": str(date),
            "title": title.strip(),
            "type": item_type.strip(),
            "speaker": (
                item.get("primaryMemberName") or
                item.get("memberName") or
                item.get("speaker") or ""
            ),
            "ministry": (
                item.get("ministryName") or
                item.get("ministry") or ""
            ),
            "text": str(text).strip(),
            "word_count": len(str(text).split()),
            "concern_keyword": "",  # filled in during scraping
            "scraped_at": datetime.now().isoformat(),
        })

    return readings, int(total)

# ── Main Scraper ──────────────────────────────────────────────────────────────
def scrape():
    Path("data").mkdir(exist_ok=True)
    done_searches  = load_checkpoint()
    all_readings, seen_ids = load_existing()
    total_new = 0

    for keyword in CONCERN_KEYWORDS:
        for year in range(START_YEAR, END_YEAR + 1):
            search_key = f"{keyword}_{year}"
            if search_key in done_searches:
                continue

            print(f"\n🔍 '{keyword}' — {year}")
            start_index = 0
            keyword_total = 0

            while True:
                data = fetch_page(keyword, year, start_index)
                time.sleep(DELAY_SECONDS)

                if not data:
                    break

                readings, total = parse_results(data)

                if not readings:
                    break

                # Add new readings (skip duplicates)
                for r in readings:
                    if r["id"] not in seen_ids:
                        r["concern_keyword"] = keyword
                        all_readings.append(r)
                        seen_ids.add(r["id"])
                        total_new += 1
                        keyword_total += 1

                print(f"  Page {start_index//RESULTS_PER_PAGE + 1}: "
                      f"{len(readings)} results (total: {total})")

                # Check if there are more pages
                start_index += RESULTS_PER_PAGE
                if start_index >= total or start_index >= 200:
                    # Cap at 200 per keyword/year to be polite
                    break

            print(f"  ✓ {keyword_total} new readings saved")
            done_searches.add(search_key)
            save_checkpoint(done_searches)
            save_data(all_readings)

    print(f"\n✅ Done!")
    print(f"   New readings saved: {total_new}")
    print(f"   Total in file:      {len(all_readings)}")
    print(f"   File: {OUTPUT_FILE.resolve()}")
    print()
    print("Next step — run the summariser:")
    print("  /opt/homebrew/bin/python3 summarise.py")

if __name__ == "__main__":
    print("ParliamentPulse SG — Scraper v4")
    print("Searching parliament by YouGov concern keywords (2020–now)")
    print()
    try:
        scrape()
    except KeyboardInterrupt:
        print("\nStopped! Progress saved — run again to resume.")
