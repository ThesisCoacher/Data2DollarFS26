#!/usr/bin/env python3
"""
airbnb_scraper_sg_okt2026.py

Scrapy + Selenium scraper for Airbnb search results.
Location : St. Gallen
Check-in : 2026-10-08
Check-out : 2026-10-18
Pages     : 6 (manually provided cursor-based URLs)
Output    : airbnb_results_sg_okt2026.csv (max 100 listings, name + price)

Usage:
    python airbnb_scraper_sg_okt2026.py
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
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException

from webdriver_manager.chrome import ChromeDriverManager

# ------------ Konfiguration ------------
OUTPUT_FILE  = "airbnb_results_sg_okt2026.csv"
MAX_LISTINGS = 100
WAIT_TIMEOUT = 18     # sec – WebDriverWait timeout
SCROLL_PAUSE = 2.0    # sec between scrolls (unused but kept for consistency)
USER_AGENT   = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 6 pages supplied by the user (St. Gallen, 08.10.–18.10.2026)
START_URLS = [
    # Seite 1
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=3"
    "&channel=EXPLORE&search_mode=regular_search"
    "&source=structured_search_input_header&search_type=unknown",

    # Seite 2
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&pagination_search=true"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxOCwidmVyc2lvbiI6MX0%3D",

    # Seite 3
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjozNiwidmVyc2lvbiI6MX0%3D",

    # Seite 4
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo1NCwidmVyc2lvbiI6MX0%3D",

    # Seite 5
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo3MiwidmVyc2lvbiI6MX0%3D",

    # Seite 6
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo5MCwidmVyc2lvbiI6MX0%3D",

    # Seite 7
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMDgsInZlcnNpb24iOjF9",

    # Seite 8
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMjYsInZlcnNpb24iOjF9",

    # Seite 9
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxNDQsInZlcnNpb24iOjF9",

    # Seite 10
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxNjIsInZlcnNpb24iOjF9",

    # Seite 11
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxODAsInZlcnNpb24iOjF9",

    # Seite 12
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxOTgsInZlcnNpb24iOjF9",

    # Seite 13
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoyMTYsInZlcnNpb24iOjF9",

    # Seite 14
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoyMzQsInZlcnNpb24iOjF9",

    # Seite 15
    "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
    "&refinement_paths%5B%5D=%2Fhomes"
    "&checkin=2026-10-08&checkout=2026-10-18"
    "&date_picker_type=calendar&query=St.%20Gallen"
    "&flexible_trip_lengths%5B%5D=one_week"
    "&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01"
    "&price_filter_input_type=2&price_filter_num_nights=10"
    "&channel=EXPLORE&source=structured_search_input_header"
    "&pagination_search=true"
    "&federated_search_session_id=f6b8b275-83e5-401d-b0c9-e8ff2f79d818"
    "&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoyNTIsInZlcnNpb24iOjF9",
]


# ------------ Hilfsfunktionen ------------
def clean_price(text: str):
    """Normalize a raw price string, e.g. 'CHF 1'230 Gesamtpreis' → '1230 CHF'."""
    if not text:
        return None
    text = text.replace("\xa0", " ").replace("'", "").strip()
    m = re.search(r"([0-9]+(?:[,.][0-9]+)?)\s*(CHF|Fr\.?|SFr\.?)", text, re.IGNORECASE)
    if m:
        amount = m.group(1).replace(",", ".")
        return f"{amount} CHF"
    m2 = re.search(r"([0-9]+(?:[,.][0-9]+)?)", text)
    if m2:
        return m2.group(1)
    return text


# ------------ Scrapy Spider ------------
class AirbnbSgOktSpider(scrapy.Spider):
    name = "airbnb_sg_okt2026"
    custom_settings = {
        "FEEDS": {
            OUTPUT_FILE: {
                "format": "csv",
                "encoding": "utf8",
                "fields": ["name", "price"],
                "overwrite": True,
            }
        },
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 1,
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_listings = MAX_LISTINGS
        self.collected = 0
        self.seen_ids: set = set()
        self.driver = None
        self.wait = None

    # ---- WebDriver lifecycle ----
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_opened(self, spider):
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
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium WebDriver beendet.")
            except Exception as exc:
                self.logger.warning("Fehler beim Beenden des WebDrivers: %s", exc)

    # ---- Scrapy requests ----
    def start_requests(self):
        for url in START_URLS:
            self.logger.info("Enqueue URL: %s", url[:80] + "…")
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)

    def parse(self, response):
        """Load the page with Selenium, extract listings from embedded JSON."""
        if self.collected >= self.max_listings:
            return

        url = response.url
        self.logger.info("Lade Seite via Selenium: %s", url[:80] + "…")
        self.driver.get(url)

        # Wait for SSR content to arrive
        time.sleep(WAIT_TIMEOUT * 0.4)   # ~7 s

        page_source = self.driver.page_source
        items = self._extract_from_embedded_json(page_source)
        self.logger.info("Listings im JSON gefunden: %d", len(items))

        new_count = 0
        for itm in items:
            if self.collected >= self.max_listings:
                break
            room_id = itm.get("unique_id")
            name    = itm.get("name")

            # Deduplicate ONLY by unique room ID (numeric Airbnb listing ID).
            # Do NOT deduplicate by name — many different listings share generic
            # names like "Wohnung in St. Gallen" but have different prices/IDs.
            if room_id:
                if room_id in self.seen_ids:
                    continue
                self.seen_ids.add(room_id)

            price = itm.get("price")
            if not name and not price:
                continue

            self.collected += 1
            new_count += 1
            yield OrderedDict([
                ("name",  name),
                ("price", price),
            ])

        self.logger.info(
            "Neue Items von dieser Seite: %d | Gesamt: %d / %d",
            new_count, self.collected, self.max_listings,
        )

    # ---- JSON extraction (same strategy as original scraper) ----
    def _extract_from_embedded_json(self, page_source: str) -> list:
        """Find 'StaySearchResult' in the page source and parse the surrounding JSON array."""
        results = []
        anchor = '"StaySearchResult"'
        idx = page_source.find(anchor)
        if idx == -1:
            self.logger.warning("'StaySearchResult' nicht in Seite gefunden – evtl. blockiert?")
            return results

        # Walk back to the opening '[' of the surrounding array
        start = page_source.rfind("[", 0, idx)
        if start == -1:
            return results

        # Find the matching closing ']'
        depth, end = 0, None
        for i in range(start, len(page_source)):
            ch = page_source[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if not end:
            return results

        try:
            arr = json.loads(page_source[start:end])
        except json.JSONDecodeError:
            return results

        for obj in arr:
            if not isinstance(obj, dict):
                continue
            try:
                # ---- Name ----
                # Priority: use the specific listing title (= <meta itemprop="name">),
                # NOT the generic category label ("Wohnung in St. Gallen").
                # 1. demandStayListing > description > name (most specific)
                # 2. nameLocalized (top-level, same specific title)
                # 3. title (fallback: generic type label, e.g. "Wohnung in St. Gallen")
                name = None
                ds_for_name = obj.get("demandStayListing")
                if isinstance(ds_for_name, dict):
                    ds_desc = ds_for_name.get("description")
                    if isinstance(ds_desc, dict):
                        ds_name = ds_desc.get("name")
                        if isinstance(ds_name, dict):
                            name = ds_name.get("localizedStringWithTranslationPreference")
                if not name:
                    nl = obj.get("nameLocalized")
                    if isinstance(nl, dict):
                        name = nl.get("localizedStringWithTranslationPreference")
                if not name:
                    name = obj.get("title")  # generic fallback only

                # ---- Price ----
                price = None
                sd = obj.get("structuredDisplayPrice") or {}
                if isinstance(sd, dict):
                    primary = sd.get("primaryLine") or {}
                    if isinstance(primary, dict):
                        raw_price = primary.get("price") or primary.get("accessibilityLabel")
                        price = clean_price(raw_price) if raw_price else None

                # ---- Unique ID (Base64-encoded DemandStayListing) ----
                unique_id = None
                ds = obj.get("demandStayListing")
                if isinstance(ds, dict):
                    did = ds.get("id")
                    if isinstance(did, str):
                        try:
                            padded  = did + "=" * (-len(did) % 4)
                            decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                            m = re.search(r":(\d+)$", decoded)
                            if m:
                                unique_id = m.group(1)
                        except Exception:
                            pass
                        if not unique_id:
                            m = re.search(r"(\d{5,})", did)
                            if m:
                                unique_id = m.group(1)
                if not unique_id:
                    pid = obj.get("propertyId")
                    if pid:
                        unique_id = str(pid)

                if name or price:
                    results.append({
                        "name":      name,
                        "price":     price,
                        "unique_id": unique_id,
                    })
            except Exception:
                continue

        return results


# ------------ Entry point ------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    process = CrawlerProcess()
    process.crawl(AirbnbSgOktSpider)
    process.start()
    print(f"\n✅  Fertig! Ergebnisse gespeichert in: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
