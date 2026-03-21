# -*- coding: utf-8 -*-
"""
Airbnb St. Gallen – Scrapy + Selenium Scraper
==============================================
Architektur:
  • AirbnbItem          – Scrapy Item (Dataklasse)
  • SeleniumMiddleware  – rendert JS-Seiten via Chrome, gibt HtmlResponse zurück
  • CsvPipeline         – Scrapy-Pipeline, schreibt CSV am Ende
  • AirbnbSpider        – Scrapy Spider (start_requests → parse → Pagination)

Wichtigster Fix gegenüber Vorversion:
  → Suchoberfläche wird NICHT mehr per Selenium bedient (war fragil).
  → Such-URL wird direkt konstruiert → kein "Suchoberfläche konnte nicht
    geöffnet werden"-Fehler mehr.
"""

import csv
import re
import time
import logging
from pathlib import Path
from urllib.parse import urlencode, urljoin

import scrapy
from scrapy import Field, Item
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse
from scrapy.utils.project import get_project_settings

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─── Konfiguration ────────────────────────────────────────────────────────────
MAX_RESULTS_PER_PERIOD = 100
OUTPUT_FILENAME        = "airbnb_st_gallen_200.csv"
SEARCH_BASE_URL        = "https://www.airbnb.ch/s/St.-Gallen/homes"

PERIODS = [
    {"label": "OpenAir St.Gallen", "checkin": "2026-06-25", "checkout": "2026-06-28"},
    {"label": "OLMA",              "checkin": "2026-10-08", "checkout": "2026-10-18"},
]


# ─── URL-Builder (ersetzt die gesamte Suchoberflächen-Steuerung) ──────────────
def build_search_url(period: dict, items_offset: int = 0) -> str:
    """
    Baut die Airbnb-Such-URL direkt, ohne die UI zu bedienen.
    items_offset steuert die Pagination (0, 18, 36, …).
    """
    params = {
        "checkin":                   period["checkin"],
        "checkout":                  period["checkout"],
        "adults":                    "1",
        "tab_id":                    "home_tab",
        "refinement_paths[]":        "/homes",
        "query":                     "St. Gallen",
        "items_offset":              str(items_offset),
        "section_offset":            "0",
        "source":                    "structured_search_input_header",
        "search_type":               "autocomplete_click",
    }
    return SEARCH_BASE_URL + "?" + urlencode(params)


# ─── Scrapy Item ──────────────────────────────────────────────────────────────
class AirbnbItem(Item):
    zeitraum    = Field()
    position    = Field()
    name        = Field()
    gesamtpreis = Field()
    aktionspreis= Field()
    listing_url = Field()


# ─── CSV Pipeline ─────────────────────────────────────────────────────────────
class CsvPipeline:
    FIELDNAMES = ["zeitraum", "position", "name", "gesamtpreis", "aktionspreis", "listing_url"]

    def open_spider(self, spider):
        self.path = Path(spider.settings.get("CSV_OUTPUT_PATH", OUTPUT_FILENAME))
        self.file = open(self.path, "w", newline="", encoding="utf-8-sig")
        self.writer = csv.DictWriter(self.file, fieldnames=self.FIELDNAMES)
        self.writer.writeheader()
        self.counters = {}          # label → Zähler
        logger.info(f"CSV geöffnet: {self.path}")

    def process_item(self, item, spider):
        self.writer.writerow(dict(item))
        return item

    def close_spider(self, spider):
        self.file.close()
        logger.info(f"✅ CSV gespeichert: {self.path}")


# ─── Selenium Middleware ──────────────────────────────────────────────────────
class SeleniumMiddleware:
    """
    Scrapy Downloader-Middleware:
    Fängt jeden Request ab, rendert die Seite mit Chrome/Selenium,
    und gibt eine fertige HtmlResponse zurück.
    """

    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--lang=de-CH")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        logger.info("SeleniumMiddleware: Chrome gestartet.")

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        logger.info(f"Selenium lädt: {request.url[:100]}")
        self.driver.get(request.url)
        self._dismiss_popups()
        self._wait_for_cards()
        self._scroll_and_load()
        body = self.driver.page_source
        # Nächste-Seite-URL für Pagination aus HTML
        next_url = self._get_next_page_url()
        return HtmlResponse(
            url=self.driver.current_url,
            body=body,
            encoding="utf-8",
            request=request,
            # Übergib next_url als Metadaten an Spider
            flags=[next_url] if next_url else [],
        )

    def _dismiss_popups(self):
        xpaths = [
            "//button[contains(.,'Alle akzeptieren')]",
            "//button[contains(.,'Accept all')]",
            "//button[contains(.,'Nur notwendige')]",
            "//button[@aria-label='Schliessen']",
            "//button[@aria-label='Close']",
        ]
        for xp in xpaths:
            try:
                btn = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                btn.click()
                time.sleep(1)
                return
            except Exception:
                pass

    def _wait_for_cards(self):
        selectors = [
            "div[data-testid='property-card']",
            "div[itemprop='itemListElement']",
        ]
        for sel in selectors:
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                return
            except TimeoutException:
                pass
        logger.warning("Timeout: Keine Karten gefunden.")

    def _scroll_and_load(self):
        last, stable = 0, 0
        for _ in range(40):
            cards = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='property-card']")
            if not cards:
                cards = self.driver.find_elements(By.CSS_SELECTOR, "div[itemprop='itemListElement']")
            self.driver.execute_script("window.scrollBy(0, 2400);")
            time.sleep(1.8)
            try:
                more = self.driver.find_element(By.XPATH, "//button[contains(.,'Mehr anzeigen')]")
                more.click()
                time.sleep(2)
            except Exception:
                pass
            current = len(cards)
            stable = (stable + 1) if current == last else 0
            last = current
            if stable >= 5:
                break

    def _get_next_page_url(self) -> str:
        """Liest den 'Weiter'-Link aus der gerenderten Seite."""
        next_xpaths = [
            "//a[@aria-label='Weiter']",
            "//a[contains(@aria-label,'Weiter')]",
            "//a[@aria-label='Next']",
            "//a[contains(@aria-label,'Next')]",
        ]
        for xp in next_xpaths:
            try:
                el = self.driver.find_element(By.XPATH, xp)
                href = el.get_attribute("href")
                if href:
                    return href
            except Exception:
                pass
        return ""

    def spider_closed(self, spider):
        try:
            self.driver.quit()
            logger.info("SeleniumMiddleware: Chrome geschlossen.")
        except Exception:
            pass


# ─── Scrapy Spider ────────────────────────────────────────────────────────────
class AirbnbSpider(scrapy.Spider):
    name = "airbnb_stgallen"
    custom_settings = {
        "ITEM_PIPELINES":             {"__main__.CsvPipeline": 300},
        "DOWNLOADER_MIDDLEWARES":     {"__main__.SeleniumMiddleware": 543},
        "ROBOTSTXT_OBEY":             False,
        "CONCURRENT_REQUESTS":        1,
        "DOWNLOAD_DELAY":             3,
        "LOG_LEVEL":                  "WARNING",
        "CSV_OUTPUT_PATH":            str(Path(__file__).resolve().parent / OUTPUT_FILENAME),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Zähler & gesehene URLs je Zeitraum
        self._state = {
            p["label"]: {"count": 0, "seen": set()} for p in PERIODS
        }

    def start_requests(self):
        for period in PERIODS:
            url = build_search_url(period, items_offset=0)
            logger.info(f"\n{'='*55}")
            logger.info(f"START: {period['label']}  →  {url[:80]}")
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={"period": period, "offset": 0},
                dont_filter=True,
            )

    def parse(self, response):
        period   = response.meta["period"]
        offset   = response.meta["offset"]
        label    = period["label"]
        state    = self._state[label]

        logger.info(f"\n── {label} | Offset {offset} | bisher {state['count']} Einträge ──")

        # Karten aus gerendertem HTML parsen
        cards = response.css("div[data-testid='property-card']")
        if not cards:
            cards = response.css("div[itemprop='itemListElement']")
        logger.info(f"   Karten auf Seite: {len(cards)}")

        page_new = 0
        for card in cards:
            if state["count"] >= MAX_RESULTS_PER_PERIOD:
                break

            url = self._extract_url(card)
            if not url or url in state["seen"]:
                continue
            state["seen"].add(url)
            state["count"] += 1

            name         = self._extract_name(card)
            gesamt, aktion = self._extract_prices(card)

            item = AirbnbItem(
                zeitraum    = label,
                position    = state["count"],
                name        = name,
                gesamtpreis = gesamt,
                aktionspreis= aktion,
                listing_url = url,
            )
            logger.info(f"   {state['count']:03d} | {name[:45]:<45} | {gesamt:<14} | {aktion}")
            yield item
            page_new += 1

        logger.info(f"   Neue Einträge: {page_new} | Total: {state['count']}")

        # Pagination: nächste Seite?
        if state["count"] < MAX_RESULTS_PER_PERIOD:
            # Methode 1: next_url aus Selenium-Flags
            next_url = response.flags[0] if response.flags else ""
            # Methode 2: Link aus HTML
            if not next_url:
                next_url = response.css(
                    "a[aria-label='Weiter']::attr(href), "
                    "a[aria-label='Next']::attr(href)"
                ).get("")
            # Methode 3: items_offset hochzählen
            if not next_url and page_new > 0:
                new_offset = offset + 18
                next_url = build_search_url(period, items_offset=new_offset)

            if next_url and page_new > 0:
                logger.info(f"   → Nächste Seite: {next_url[:80]}")
                yield scrapy.Request(
                    next_url,
                    callback=self.parse,
                    meta={"period": period, "offset": offset + 18},
                    dont_filter=True,
                )
            else:
                logger.info(f"   → Keine weitere Seite für {label}.")

    # ── Extraktions-Helfer ────────────────────────────────────────────────────
    @staticmethod
    def _extract_url(card) -> str:
        href = card.css("a[href*='/rooms/']::attr(href)").get("")
        return href.split("?")[0] if href else ""

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").replace("\u00a0", " ").strip())

    def _extract_name(self, card) -> str:
        for sel in [
            "[data-testid='listing-card-name']::text",
            "[data-testid='listing-card-title']::text",
            "div.t1gpcl1t::text",
        ]:
            name = card.css(sel).get("")
            if name.strip():
                return self._normalize(name)

        ignore = [
            r"^Neu$", r"^\d+[,.]?\d*\s*\(\d+\)$", r"^SUPERHOST$",
            r"^Gäste-Favorit$", r"^CHF\s?[\d'.,]+", r"^\d+\s+Nächte?$",
        ]
        for line in card.css("*::text").getall():
            line = self._normalize(line)
            if line and not any(re.search(p, line, re.I) for p in ignore):
                return line
        return ""

    def _extract_prices(self, card):
        price_re = re.compile(
            r"(CHF\s?[\d'.,]+(?:\.\-)?|[\d'.,]+(?:\.\-)?\s?CHF)", re.I
        )
        all_prices, struck, current = [], [], []
        total = []

        for el in card.css("*"):
            text = self._normalize(" ".join(el.css("::text").getall()))
            if not text:
                continue
            matches = price_re.findall(text)
            if not matches:
                continue
            lower = text.lower()
            # Detektion Durchgestrichen via Attribut/Klasse (CSS-Parsing)
            cls  = " ".join(el.attrib.get("class", "").lower().split())
            tag  = el.root.tag.upper() if hasattr(el, "root") else ""
            is_struck = "strikethrough" in cls or "line-through" in cls or tag in {"S", "DEL"}
            is_total  = any(k in lower for k in ("gesamt", "total", "insgesamt"))

            for p in matches:
                p = self._normalize(p)
                all_prices.append(p)
                if is_total:
                    total.append(p)
                if is_struck:
                    struck.append(p)
                else:
                    current.append(p)

        def unique(lst):
            out, seen = [], set()
            for v in lst:
                if v and v not in seen:
                    seen.add(v); out.append(v)
            return out

        all_prices = unique(all_prices)
        struck     = unique(struck)
        current    = unique(current)
        total      = unique(total)

        gesamt = total[-1] if total else (all_prices[-1] if len(all_prices) >= 2 else (all_prices[0] if all_prices else ""))
        aktion = ""
        if struck and current:
            non_struck = [p for p in current if p not in set(struck)]
            if non_struck:
                aktion = non_struck[0]
        if not aktion and len(all_prices) >= 2:
            aktion = all_prices[0]

        return gesamt, aktion


# ─── Entry Point ──────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("  Airbnb St. Gallen Scraper – Scrapy + Selenium")
    print("="*55)
    for p in PERIODS:
        print(f"  • {p['label']:25s}  {p['checkin']} → {p['checkout']}")
    print(f"  • Max pro Zeitraum: {MAX_RESULTS_PER_PERIOD}")
    print(f"  • Output: {OUTPUT_FILENAME}")
    print("="*55 + "\n")

    process = CrawlerProcess(settings={})
    process.crawl(AirbnbSpider)
    process.start()


if __name__ == "__main__":
    main()