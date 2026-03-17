"""
Web scraper for https://books.toscrape.com/

Extracts the following fields for every book across all pages:
  - name         : Book title
  - url          : Absolute URL of the book detail page
  - scrape_date  : Date the scraper was run (YYYY-MM-DD)
  - description  : Product description from the detail page
  - price        : Book price (e.g. "£51.77")
  - tax          : Tax amount (e.g. "£0.00")
  - availability : Availability text (e.g. "In stock (22 available)")
  - upc          : Universal Product Code (UPC number)
  - rating       : Star rating of the book (e.g. 3)

Libraries used: requests, BeautifulSoup
Output: books_data.json  +  books_data.csv
"""

import csv
import json
import time
import logging
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ─────────────────────────── Configuration ───────────────────────────────────

BASE_URL = "https://books.toscrape.com/"

# Polite delay between HTTP requests (seconds)
REQUEST_DELAY = 0.5

# Output file names
OUTPUT_JSON = "books_data.json"
OUTPUT_CSV = "books_data.csv"

# Fields written to CSV (order matters)
CSV_FIELDS = ["name", "url", "scrape_date", "description",
              "price", "tax", "availability", "upc", "rating"]

# ─────────────────────────── Logging setup ───────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────── HTTP helper ─────────────────────────────────────


def get_soup(url: str, session: requests.Session) -> BeautifulSoup:

    response = session.get(url, timeout=15)
    response.raise_for_status()       # raises HTTPError

    response.encoding = "utf-8"  # ensure correct encoding for BeautifulSoup
    return BeautifulSoup(response.text, "html.parser")

# ─────────────────────────── Pagination ──────────────────────────────────────


def iter_listing_pages(session: requests.Session):

    # The first listing page has a different URL pattern from subsequent pages
    current_url = BASE_URL

    while current_url:
        log.info("Fetching listing page: %s", current_url)
        soup = get_soup(current_url, session)
        page_url = current_url

        # Look for the "next" button; its <a> href gives the relative next URL
        next_btn = soup.select_one("li.next > a")
        if next_btn:
            # Resolve the relative href against the current page URL so that
            # both "catalogue/page-2.html" and "page-2.html" work correctly
            current_url = urljoin(current_url, next_btn["href"])
            time.sleep(REQUEST_DELAY)
        else:
            current_url = None    # No more pages → stop the loop

        yield soup, page_url

# ─────────────────────────── Book URLs ───────────────────────────────────────


def extract_book_urls(listing_soup: BeautifulSoup, page_url: str) -> list[str]:

    urls = []
    for article in listing_soup.select("article.product_pod"):
        # The <a> href is relative to the catalogue directory
        relative_href = article.select_one("h3 > a")["href"]
        absolute_url = urljoin(page_url, relative_href)
        urls.append(absolute_url)
    return urls

# ─────────────────────────── Detail page parsing ─────────────────────────────


RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_detail_page(url: str, session: requests.Session) -> dict:
    """
    Visit a single book detail page and return a dictionary with all
    required fields.
    """
    soup = get_soup(url, session)

    name = soup.select_one("div.product_main > h1").get_text(strip=True)
    rating_tag = soup.select_one("p.star-rating")
    rating = 0
    if rating_tag:
        classes = rating_tag.get("class", [])
        for cls in classes:
            if cls in RATING_MAP:
                rating = RATING_MAP[cls]
                break

    table_data = {}
    for row in soup.select("table.table-striped tr"):
        header = row.select_one("th").get_text(strip=True)
        value = row.select_one("td").get_text(strip=True)
        table_data[header] = value

    price = table_data.get("Price (excl. tax)", "N/A")
    tax = table_data.get("Tax", "N/A")
    upc = table_data.get("UPC", "N/A")
    availability = table_data.get("Availability", "N/A")

    desc_tag = soup.select_one("div#product_description ~ p")
    description = desc_tag.get_text(strip=True) if desc_tag else ""

    return {
        "name":         name,
        "url":          url,
        "scrape_date":  date.today().isoformat(),
        "description":  description,
        "price":        price,
        "tax":          tax,
        "availability": availability,
        "upc":          upc,
        "rating":       rating,
    }

# ─────────────────────────── Output helpers ──────────────────────────────────


def save_json(books: list[dict], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(books, fh, ensure_ascii=False, indent=2)
    log.info("JSON saved → %s  (%d records)", filepath, len(books))


def save_csv(books: list[dict], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(books)
    log.info("CSV  saved → %s  (%d records)", filepath, len(books))

# ─────────────────────────── Main orchestrator ───────────────────────────────


def main() -> None:
    log.info("Starting scraper for %s", BASE_URL)

    all_books: list[dict] = []

    # Use a Session so that TCP connections are reused across requests
    with requests.Session() as session:
        # Set a browser-like User-Agent to avoid being blocked
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; BooksScraper/1.0; "
                "+https://books.toscrape.com)"
            )
        })

        detail_urls: list[str] = []
        for page_soup, page_url in iter_listing_pages(session):
            urls = extract_book_urls(page_soup, page_url)
            detail_urls.extend(urls)
            log.info("  → %d book URLs collected so far", len(detail_urls))

        log.info("Total books discovered: %d", len(detail_urls))

        for idx, url in enumerate(detail_urls, start=1):
            log.info("[%d/%d] Scraping: %s", idx, len(detail_urls), url)
            try:
                book_data = parse_detail_page(url, session)
                all_books.append(book_data)
            except Exception as exc:
                log.error("  Failed to scrape %s: %s", url, exc)
            time.sleep(REQUEST_DELAY)

    save_json(all_books, OUTPUT_JSON)
    save_csv(all_books,  OUTPUT_CSV)

    log.info("Done! %d books scraped successfully.", len(all_books))


# ─────────────────────────── Entry point ─────────────────────────────────────

if __name__ == "__main__":
    main()
