# top of scraper.py
CACHE_SECONDS = 300  # 5 minutes
MONTH_CACHE = {}

import json
import re
from datetime import datetime, date, time
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


BASE_URL = "https://dcwashingtonweb.myvscloud.com/webtrac/web/search.html"

COURTS = ["Rose Park T Court 1", "Rose Park T Court 2"]

PARAMS = {
    "Action": "Start",
    "SubAction": "",
    "begintime": "08:00 am",
    "keyword": "",
    "keywordoption": "Match All",
    "location": "Rose Park Rec (DPR0360)",
    "frclass": "Tennis Court",
    "type": "",
    "frheadcount": "0",
    "blockstodisplay": "23",
    "display": "Detail",
    "module": "FR",
    "multiselectlist_value": "",
    "frwebsearch_buttonsearch": "yes",
}


def build_url(date_str):
    params = PARAMS.copy()
    params["date"] = date_str
    return f"{BASE_URL}?{urlencode(params)}"


def parse_slot_start_time(slot):
    match = re.search(
        r"^(\d{1,2}):(\d{2})\s*(am|pm)",
        slot.strip(),
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2))
    period = match.group(3).lower()

    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0

    return time(hour, minute)


def next_full_hour():
    now = datetime.now()

    if now.minute == 0 and now.second == 0:
        return time(now.hour, 0)

    next_hour = now.hour + 1

    if next_hour >= 24:
        return time(23, 59)

    return time(next_hour, 0)


def is_today(date_str):
    selected = datetime.strptime(date_str, "%m/%d/%Y").date()
    return selected == date.today()


def is_future_date(date_str):
    selected = datetime.strptime(date_str, "%m/%d/%Y").date()
    return selected > date.today()


def filter_relevant_unavailable_slots(unavailable, date_str):
    if is_future_date(date_str):
        return unavailable

    if not is_today(date_str):
        return []

    cutoff = next_full_hour()
    relevant = []

    for slot in unavailable:
        slot_start = parse_slot_start_time(slot)

        if slot_start and slot_start >= cutoff:
            relevant.append(slot)

    return relevant


def clean_slot(slot):
    return (
        slot.replace("Unavailable", "")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def parse_courts(html, date_str):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    results = []
    

    for i, court_name in enumerate(COURTS):
        start = text.find(court_name)

        if start == -1:
            results.append({
                "name": court_name,
                "error": "Court not found in page text",
                "booked": [],
                "unavailable_raw": [],
                "available": [],
            })
            continue

        next_start = (
            text.find(COURTS[i + 1], start + 1)
            if i + 1 < len(COURTS)
            else len(text)
        )

        section = text[start:next_start]

        unavailable_matches = re.findall(
            r"\d{1,2}:\d{2}\s*(?:am|pm)\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm)\s*Unavailable",
            section,
            flags=re.IGNORECASE,
        )

        unavailable = [clean_slot(slot) for slot in unavailable_matches]

        all_time_ranges = re.findall(
            r"\d{1,2}:\d{2}\s*(?:am|pm)\s*-\s*\d{1,2}:\d{2}\s*(?:am|pm)",
            section,
            flags=re.IGNORECASE,
        )

        available = [
            slot.strip()
            for slot in all_time_ranges
            if slot.strip() not in unavailable
        ]

        booked = filter_relevant_unavailable_slots(unavailable, date_str)

        results.append({
            "name": court_name,
            "booked": booked,
            "unavailable_raw": unavailable,
            "available": available,
        })

    return {
        "lastUpdated": datetime.now().isoformat(timespec="seconds"),
        "date": date_str,
        "courts": results,
    }


def create_browser_context(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
    )

    return browser, context


def fetch_html_with_page(page, url):
    print(f"Opening: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    return page.content()


def check_courts(date_str):
    url = build_url(date_str)

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        html = fetch_html_with_page(page, url)

        debug_path = Path(__file__).resolve().parents[1] / "data" / "debug_page.html"
        debug_path.parent.mkdir(exist_ok=True)
        debug_path.write_text(html, encoding="utf-8")

        browser.close()

    return parse_courts(html, date_str)


def check_month(year, month):
    cache_key = f"{year}-{month}"
    now = datetime.now()

    cached = MONTH_CACHE.get(cache_key)
    if cached:
        age = (now - cached["cached_at"]).total_seconds()
        if age < CACHE_SECONDS:
            return cached["data"]
    
    today = date.today()
    first_of_month = date(year, month, 1)

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    days_in_month = (next_month - first_of_month).days

    results = {}

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        for day_num in range(1, days_in_month + 1):
            current = date(year, month, day_num)

            if current < today:
                continue

            date_str = current.strftime("%m/%d/%Y")
            url = build_url(date_str)

            try:
                html = fetch_html_with_page(page, url)
                results[date_str] = parse_courts(html, date_str)
            except Exception as exc:
                results[date_str] = {
                    "lastUpdated": datetime.now().isoformat(timespec="seconds"),
                    "date": date_str,
                    "error": str(exc),
                    "courts": [],
                }

        browser.close()

    data = {
        "lastUpdated": datetime.now().isoformat(timespec="seconds"),
        "year": year,
        "month": month,
        "dates": results,
    }

    MONTH_CACHE[cache_key] = {
        "cached_at": now,
        "data": data,
    }

    return data


if __name__ == "__main__":
    data = check_month(2026, 5)
    print(json.dumps(data, indent=2))