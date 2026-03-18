#!/usr/bin/env python3
"""
airbnb_scraper.py

Scrapy + Selenium scraper for Airbnb search results (St. Gallen example).
Saves up to max_listings results to CSV (default 100).

Usage:
    python airbnb_scraper.py

Notes:
- Use responsibly and check Airbnb Terms of Service and robots.txt before running at scale.
- Chrome must be installed for ChromeDriver to work; webdriver-manager will download a compatible driver automatically.
"""

import re
import time
import logging
import base64
from collections import OrderedDict
import json

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy import signals

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
)

# ------------ Konfiguration ------------
# Primary start URL (first page)
START_URL = "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&search_type=AUTOSUGGEST"
# If you want to supply additional page URLs (cursor-based pages), list them here.
# The user provided page-3..page-7 URLs; include them so the spider will fetch each page and parse embedded JSON from them.
ADDITIONAL_START_URLS = [
    # page 3..7 provided by user
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&pagination_search=true&federated_search_session_id=ce8b39f5-b991-4814-a51a-733be381414a&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjozNiwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&pagination_search=true&federated_search_session_id=ce8b39f5-b991-4814-a51a-733be381414a&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo1NCwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&pagination_search=true&federated_search_session_id=ce8b39f5-b991-4814-a51a-733be381414a&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo3MiwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&pagination_search=true&federated_search_session_id=ce8b39f5-b991-4814-a51a-733be381414a&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo5MCwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&pagination_search=true&federated_search_session_id=ce8b39f5-b991-4814-a51a-733be381414a&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMDgsInZlcnNpb24iOjF9",
]

# Combined list used by start_requests
START_URLS = [START_URL] + ADDITIONAL_START_URLS
OUTPUT_FILE = "airbnb_results.csv"
MAX_LISTINGS = 100  # stop after collecting this many listings
SCROLL_PAUSE = 2.0  # sec, time between scrolls (increased to allow more loading)
WAIT_TIMEOUT = 18   # WebDriverWait timeout in seconds (increased)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"


# ------------ Hilfsfunktionen ------------
def clean_price(text):
    """Extract a normalized price string from raw text, e.g. 'CHF 123 Gesamtpreis' -> '123 CHF'."""
    if not text:
        return None
    text = text.replace('\xa0', ' ').strip()
    m = re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(CHF|Fr|SFr|CHF)', text, flags=re.IGNORECASE)
    if m:
        amount = m.group(1).replace(',', '.')
        currency = m.group(2).upper()
        return f"{amount} {currency}"
    m2 = re.search(r'([0-9]+(?:[,.][0-9]+)?)', text)
    if m2:
        return m2.group(1)
    return text


# ------------ Scrapy Spider ------------
class AirbnbSpider(scrapy.Spider):
    name = "airbnb_sg"
    custom_settings = {
        "FEEDS": {
            OUTPUT_FILE: {
                "format": "csv",
                "encoding": "utf8",
                "fields": ["name", "price", "source_url"],
                "overwrite": True,
            }
        },
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 1,
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, start_url=START_URL, max_listings=MAX_LISTINGS, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_url = start_url
        self.max_listings = int(max_listings)
        self.collected = 0
        self.seen_ids = set()
        self.driver = None
        self.wait = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(AirbnbSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_opened(self, spider):
        """Start Selenium WebDriver (Chrome) when spider opens."""
        logging.getLogger("WDM").setLevel(logging.NOTSET)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={USER_AGENT}")
        options.add_argument("--window-size=1920,1080")

        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, WAIT_TIMEOUT)
            self.logger.info("Selenium WebDriver gestartet.")
        except WebDriverException as e:
            self.logger.error("Fehler beim Starten des WebDrivers: %s", e)
            raise

    def spider_closed(self, spider):
        """Close WebDriver when spider closes."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium WebDriver beendet.")
            except Exception as e:
                self.logger.warning("Fehler beim Beenden des WebDrivers: %s", e)

    def start_requests(self):
        for url in START_URLS:
            self.logger.info("Enqueue Start-URL: %s", url)
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        """Load each page URL with Selenium and extract listings from embedded JSON.

        Strategy:
        - Load the URL in Selenium (which renders the page server-side with embedded JSON).
        - Wait briefly for the page to settle.
        - Extract ALL StaySearchResult entries from the embedded JSON in the page source.
        - Deduplicate using the numeric room ID (extracted from DemandStayListing id or /rooms/<id>).
        - Yield items until MAX_LISTINGS is reached.
        """
        url = response.url
        if self.collected >= self.max_listings:
            return

        self.logger.info("Lade Seite via Selenium: %s", url)
        self.driver.get(url)

        # Wait for page content to load (body is always present)
        time.sleep(WAIT_TIMEOUT * 0.4)  # ~7 sec — enough for SSR content to arrive

        page_source = self.driver.page_source
        self.logger.info("Seite geladen, extrahiere eingebettetes JSON ...")

        items = self.extract_from_embedded_json(page_source)
        self.logger.info("Gefundene Listings im eingebetteten JSON: %d", len(items))

        new_count = 0
        for itm in items:
            if self.collected >= self.max_listings:
                break
            room_id = itm.get('unique_id')
            name = itm.get('name')
            # Deduplicate by room ID (primary) and name (fallback for same listing with different ID)
            if room_id and room_id in self.seen_ids:
                continue
            if name and name in self.seen_ids:
                continue
            if room_id:
                self.seen_ids.add(room_id)
            if name:
                self.seen_ids.add(name)
            price = itm.get('price')
            if not name and not price:
                continue
            self.collected += 1
            new_count += 1
            yield OrderedDict([
                ('name', name),
                ('price', price),
                ('source_url', itm.get('url')),
            ])

        self.logger.info("Neue Items von dieser Seite: %d | Gesamt gesammelt: %d", new_count, self.collected)

    def parse_listings_with_selector(self, sel):
        """Parse listings from a Scrapy selector of the full page."""
        listing_xpath_candidates = [
            "//div[@data-testid='property-card']",
            "//div[contains(@class,'_8ssblpx')]",
            "//div[@itemprop='itemListElement']",
            "//div[contains(@aria-labelledby,'listing')]",
        ]

        listings = []
        for xpath in listing_xpath_candidates:
            listings = sel.xpath(xpath)
            if listings and len(listings) > 0:
                self.logger.debug("Nutze Listing-XPath: %s (gefunden: %d)", xpath, len(listings))
                break

        if not listings:
            listings = sel.xpath("//div[contains(@class,'_1mzhry13') or contains(@class,'_fhph4u')]")
            self.logger.debug("Fallback listings length: %d", len(listings))

        for listing in listings:
            unique_id = None
            try:
                unique_id = listing.xpath(".//a/@href").get()
            except Exception:
                unique_id = None

            if unique_id and unique_id in self.seen_ids:
                continue

            name = listing.xpath(".//meta[@itemprop='name']/@content").get()
            if not name:
                name = listing.xpath(".//a//div[contains(@class,'_bzh5lkq') or contains(@class,'_1c2n35az')]/text()").get()
                if not name:
                    name = listing.xpath(".//div[contains(@class,'_1c2n35az')]/text()").get()

            price_text = listing.xpath(".//span[contains(., 'CHF') and contains(., 'Gesamtpreis')]/text()").get()
            if not price_text:
                price_text = listing.xpath(".//span[@data-testid='price']/text()").get()
            if not price_text:
                price_text = listing.xpath(".//span[contains(., 'CHF')]/text()").get()
            if not price_text:
                combined = " ".join(listing.xpath(".//text()").getall())
                if "CHF" in combined:
                    m = re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(CHF|Fr|SFr|CHF)', combined)
                    if m:
                        price_text = m.group(0)

            price_clean = clean_price(price_text) if price_text else None

            href = listing.xpath(".//a/@href").get()
            source_url = None
            if href:
                if href.startswith("http"):
                    source_url = href
                else:
                    source_url = "https://www.airbnb.ch" + href

            item = OrderedDict()
            item["name"] = name.strip() if name else None
            item["price"] = price_clean
            item["source_url"] = source_url

            if unique_id:
                self.seen_ids.add(unique_id)

            if not item["name"] and not item["price"]:
                continue

            if self.collected >= self.max_listings:
                break

            self.collected += 1
            yield item

    def extract_from_embedded_json(self, page_source):
        """Parse embedded JSON in the page_source to extract listing names, prices and ids.
        This looks for occurrences of 'StaySearchResult' and attempts to extract the surrounding
        JSON array. Returns a list of dicts with keys: name, price, url, unique_id.
        """
        results = []
        # Heuristic: find the first occurrence of "StaySearchResult" in the HTML
        anchor = '"StaySearchResult"'
        idx = page_source.find(anchor)
        if idx == -1:
            return results

        # find the opening '[' before idx
        start = page_source.rfind('[', 0, idx)
        if start == -1:
            return results

        # Find matching closing bracket
        depth = 0
        end = None
        for i in range(start, len(page_source)):
            ch = page_source[i]
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if not end:
            return results

        candidate = page_source[start:end]
        # Try to parse the candidate as JSON
        try:
            arr = json.loads(candidate)
        except Exception:
            # sometimes it's not pure JSON; attempt to extract objects containing StaySearchResult
            return results

        # iterate objects and extract fields
        for obj in arr:
            try:
                # extract name from structured places
                name = None
                if isinstance(obj, dict):
                    # nested typical paths
                    name = (obj.get('title') or
                            (obj.get('description') or {}).get('name') if isinstance(obj.get('description'), dict) else None)
                    # sometimes nameLocalized is present
                    if not name and 'nameLocalized' in obj and isinstance(obj['nameLocalized'], dict):
                        nl = obj['nameLocalized'].get('localizedStringWithTranslationPreference')
                        name = nl

                    price = None
                    sd = obj.get('structuredDisplayPrice') or {}
                    if isinstance(sd, dict):
                        primary = sd.get('primaryLine') or {}
                        price = primary.get('price') or primary.get('accessibilityLabel')

                    # listing id extraction
                    # The demandStayListing.id is Base64-encoded, e.g.:
                    #   "RGVtYW5kU3RheUxpc3Rpbmc6MTIzNDU2" -> "DemandStayListing:123456"
                    # We decode and extract the numeric part after the colon.
                    unique_id = None
                    ds = obj.get('demandStayListing')
                    if isinstance(ds, dict):
                        did = ds.get('id')
                        if isinstance(did, str):
                            try:
                                # pad base64 if necessary
                                padded = did + '=' * (-len(did) % 4)
                                decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
                                # decoded looks like "DemandStayListing:123456"
                                m = re.search(r':(\d+)$', decoded)
                                if m:
                                    unique_id = m.group(1)
                            except Exception:
                                pass
                            if not unique_id:
                                # fallback: just grab all digits
                                m = re.search(r'(\d{5,})', did)
                                if m:
                                    unique_id = m.group(1)
                    # fallback to propertyId
                    if not unique_id:
                        pid = obj.get('propertyId')
                        if pid:
                            unique_id = str(pid)

                    url = None
                    if unique_id:
                        url = f"https://www.airbnb.ch/rooms/{unique_id}"

                    if name or price:
                        results.append({
                            'name': name,
                            'price': price,
                            'url': url,
                            'unique_id': unique_id,
                        })
            except Exception:
                continue

        return results


def main():
    # Setup logging to console
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    process = CrawlerProcess()
    process.crawl(AirbnbSpider)
    process.start()


if __name__ == '__main__':
    main()
