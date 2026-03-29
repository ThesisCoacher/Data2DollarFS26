# airbnb_crawler/spiders/airbnb_spider.py

import scrapy
import json
import time
import csv
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


URLS = [
    {
        "event":    "Openair St. Gallen",
        "category": "Openair (25.06.2026 - 28.06.2026)",
        "checkin":  "2026-06-25",
        "checkout": "2026-06-28",
        "url": (
            "https://www.airbnb.ch/s/St.-Gallen/homes"
            "?refinement_paths%5B%5D=%2Fhomes"
            "&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
            "&date_picker_type=calendar"
            "&checkin=2026-06-25"
            "&checkout=2026-06-28"
            "&search_type=autocomplete_click"
        ),
    },
    {
        "event":    "OLMA",
        "category": "OLMA (08.10.2026 - 18.10.2026)",
        "checkin":  "2026-10-08",
        "checkout": "2026-10-18",
        "url": (
            "https://www.airbnb.ch/s/St.-Gallen/homes"
            "?refinement_paths%5B%5D=%2Fhomes"
            "&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A"
            "&date_picker_type=calendar"
            "&checkin=2026-10-08"
            "&checkout=2026-10-18"
            "&search_type=unknown"
        ),
    },
]

MAX_LISTINGS = 100

CSV_FIELDNAMES = [
    "category",
    "name",
    "original_price",
    "discounted_price",
    "price_per_night",
]


def parse_price_value(price_str):
    """
    Extrahiert den numerischen Wert aus einem Preis-String.
    "628 CHF" → 628.0 | "1'234 CHF" → 1234.0
    Gibt None zurück wenn kein Wert gefunden wird.
    """
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d.,]", "", price_str)
    cleaned = re.sub(r"[.,'](?=\d{3}(?:[.,]|$))", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def calc_nights(checkin: str, checkout: str) -> int:
    """Berechnet die Anzahl Nächte zwischen Check-in und Check-out."""
    fmt = "%Y-%m-%d"
    return (datetime.strptime(checkout, fmt) - datetime.strptime(checkin, fmt)).days


def find_similar_container(driver):
    """
    Sucht den 'Ähnliche Reisedaten'-Container.
    Wird in _extract_listings() verwendet um Karten auszuschliessen.
    """
    for sel in [
        '[data-testid="stays-paginated-search-results-similar-dates"]',
        '[data-testid="similar-dates-section"]',
    ]:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel)
        except NoSuchElementException:
            pass

    try:
        heading = driver.find_element(
            By.XPATH,
            "//*[contains(text(), 'ähnlichen Reisedaten') "
            "or contains(text(), 'similar dates') "
            "or contains(text(), 'available for similar')]"
        )
        return heading.find_element(
            By.XPATH,
            "./ancestor::section | ./ancestor::div[@data-section-id]"
        )
    except NoSuchElementException:
        pass

    return None


class AirbnbSpider(scrapy.Spider):
    name = "airbnb_spider"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Auskommentieren zum Debuggen
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--lang=de-CH")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait   = WebDriverWait(self.driver, 15)
        self.all_results = []
        self.seen = set()

    async def start(self):
        """Einzelner Dummy-Request – Selenium navigiert selbst sequenziell."""
        yield scrapy.Request(
            url="https://www.airbnb.ch",
            callback=self.parse_all,
            dont_filter=True,
        )

    def parse_all(self, response):
        """Iteriert sequenziell durch alle Events."""
        for entry in URLS:
            nights = calc_nights(entry["checkin"], entry["checkout"])
            yield from self._scrape_event(entry, nights)

    def _scrape_event(self, entry, nights):
        """Scrapt alle Seiten für ein Event und yieldet die Listings."""
        event = entry["event"]
        self.logger.info(f"Starte Scraping für: {event} ({nights} Nächte)")
        self.driver.get(entry["url"])
        time.sleep(4)

        self._close_cookie_banner()

        listings = []
        page = 1

        while len(listings) < MAX_LISTINGS:
            self.logger.info(
                f"[{event}] Seite {page} – bisher {len(listings)} Inserate"
            )

            try:
                self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, '[data-testid="card-container"]')
                    )
                )
            except TimeoutException:
                self.logger.warning(f"Timeout auf Seite {page} – breche ab")
                break

            self._scroll_down()

            # Debug-Logging
            all_c  = self.driver.find_elements(
                By.CSS_SELECTOR, '[data-testid="card-container"]'
            )
            next_b = self.driver.find_elements(
                By.CSS_SELECTOR,
                'a[aria-label="Weiter"][href*="pagination_search=true"]'
            )
            self.logger.info(
                f"  DEBUG → Karten auf Seite total: {len(all_c)} | "
                f"Korrekter 'Weiter'-Button gefunden: {len(next_b) > 0}"
            )

            page_listings = self._extract_listings(entry, nights)
            listings.extend(page_listings)
            self.logger.info(f"  → {len(page_listings)} neue Inserate gefunden")

            if len(listings) >= MAX_LISTINGS:
                listings = listings[:MAX_LISTINGS]
                break

            if not self._go_to_next_page():
                self.logger.info("Kein gültiger 'Weiter'-Button – fertig")
                break

            page += 1
            time.sleep(3)

        self.logger.info(
            f"[{event}] Insgesamt {len(listings)} Inserate gesammelt"
        )
        self.all_results.extend(listings)
        yield from listings

    def _close_cookie_banner(self):
        selectors = [
            '[data-testid="accept-btn"]',
            'button[aria-label*="Accept"]',
            'button[aria-label*="Akzeptieren"]',
        ]
        for selector in selectors:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                btn.click()
                time.sleep(1)
                return
            except NoSuchElementException:
                continue

    def _scroll_down(self):
        for _ in range(5):
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(0.8)
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

    def _extract_listings(self, entry, nights):
        """Extrahiert Listings und filtert Karten innerhalb der 'Ähnliche Reisedaten'-Sektion."""
        results  = []
        category = entry["category"]

        all_cards = self.driver.find_elements(
            By.CSS_SELECTOR, '[data-testid="card-container"]'
        )

        # Ähnliche-Reisedaten-Container finden und Karten darin ausschliessen
        excluded_cards    = set()
        similar_container = find_similar_container(self.driver)

        if similar_container:
            try:
                similar_cards = similar_container.find_elements(
                    By.CSS_SELECTOR, '[data-testid="card-container"]'
                )
                for sc in similar_cards:
                    excluded_cards.add(sc.id)
                self.logger.info(
                    f"  Ähnliche-Reisedaten-Sektion: "
                    f"{len(excluded_cards)} Karten ausgeschlossen"
                )
            except Exception as e:
                self.logger.warning(f"Fehler beim Filtern ähnlicher Karten: {e}")
        else:
            self.logger.info("  Keine Ähnliche-Reisedaten-Sektion gefunden")

        cards = [c for c in all_cards if c.id not in excluded_cards]

        self.logger.info(
            f"  Karten total: {len(all_cards)} | "
            f"ausgeschlossen: {len(excluded_cards)} | "
            f"verarbeitet: {len(cards)}"
        )

        for card in cards:
            name       = self._get_name(card)
            orig_price = self._get_original_price(card)
            disc_price = self._get_discount_price(card)

            if not name:
                continue

            # Rabattpreis = Gesamtpreis → durch Nächte teilen
            # Originalpreis = bereits pro Nacht → direkt übernehmen
            price_per_night = None
            if disc_price:
                total = parse_price_value(disc_price)
                if total and nights > 0:
                    price_per_night = round(total / nights, 2)
            elif orig_price:
                price_per_night = parse_price_value(orig_price)

            dedup_key = (category, name, price_per_night)
            if dedup_key in self.seen:
                self.logger.debug(f"Duplikat übersprungen: {name} | {price_per_night}")
                continue
            self.seen.add(dedup_key)

            results.append(
                {
                    "category":         category,
                    "name":             name,
                    "original_price":   orig_price,
                    "discounted_price": disc_price,
                    "price_per_night":  price_per_night,
                }
            )

        return results

    def _get_name(self, card):
        for sel in [
            '[data-testid="listing-card-name"]',
            '[data-testid="listing-card-title"]',
        ]:
            try:
                el   = card.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                continue
        return None

    def _get_original_price(self, card):
        for sel in [
            "span.sjwpj0z",
            "span[aria-label*='pro Nacht']",
            "span[aria-label*='per night']",
        ]:
            try:
                el   = card.find_element(By.CSS_SELECTOR, sel)
                text = el.text.replace("\xa0", " ").strip()
                if text:
                    return text
            except NoSuchElementException:
                continue

        try:
            spans = card.find_elements(
                By.XPATH,
                ".//span[contains(text(), 'CHF') "
                "and not(contains(text(), 'Gesamt')) "
                "and not(contains(text(), 'total'))]"
            )
            for span in spans:
                text = span.text.replace("\xa0", " ").strip()
                if text:
                    return text
        except Exception:
            pass

        return None

    def _get_discount_price(self, card):
        try:
            el   = card.find_element(By.CSS_SELECTOR, "span.u1opajno")
            text = el.text.replace("\xa0", " ").strip()
            if text:
                return text
        except NoSuchElementException:
            pass

        try:
            btn = card.find_element(
                By.XPATH,
                ".//button[.//span[contains(text(),'Gesamtpreis') "
                "or contains(text(),'total')]]",
            )
            for span in btn.find_elements(By.TAG_NAME, "span"):
                text = span.text.replace("\xa0", " ").strip()
                if text and "CHF" in text \
                        and "Gesamtpreis" not in text \
                        and "total" not in text.lower():
                    return text
        except NoSuchElementException:
            pass

        return None

    def _go_to_next_page(self):
        """
        Klickt den Haupt-Pagination-'Weiter'-Button.
        Identifiziert ihn eindeutig via pagination_search=true im href –
        der Similar-Dates-Button hat dieses Attribut nie.
        """
        try:
            btn = self.driver.find_element(
                By.CSS_SELECTOR,
                'a[aria-label="Weiter"][href*="pagination_search=true"]'
            )

            if not btn.is_enabled():
                self.logger.info(
                    "  Pagination-Button deaktiviert – letzte Seite erreicht"
                )
                return False

            try:
                first_card = self.driver.find_element(
                    By.CSS_SELECTOR, '[data-testid="card-container"]'
                )
            except NoSuchElementException:
                first_card = None

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", btn
            )
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", btn)
            self.logger.info(
                "  Korrekter Pagination-Button geklickt (pagination_search=true)"
            )

            # Warten bis alte Karte stale wird → neue Seite geladen
            if first_card:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.staleness_of(first_card)
                    )
                    self.logger.info("  Neue Seite erkannt (stale element)")
                except TimeoutException:
                    self.logger.warning(
                        "  Stale-Check fehlgeschlagen – fahre trotzdem fort"
                    )

            # Warten bis neue Karten im DOM sind
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '[data-testid="card-container"]')
                    )
                )
            except TimeoutException:
                self.logger.warning(
                    "  Keine neuen Karten nach Seitenwechsel gefunden"
                )

            time.sleep(2)
            return True

        except NoSuchElementException:
            self.logger.info(
                "  Kein Pagination-Button (pagination_search=true) gefunden "
                "– letzte Seite"
            )
            return False
        except Exception as e:
            self.logger.warning(f"  Klick fehlgeschlagen: {e}")
            return False

    def closed(self, reason):
        self.driver.quit()

        # CSV mit UTF-8-BOM für Excel-Kompatibilität
        if self.all_results:
            with open(
                "2_InauenLennyMin.csv", "w", newline="", encoding="utf-8-sig"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()
                writer.writerows(self.all_results)

        self.logger.info(
            f"Fertig! {len(self.all_results)} Inserate in CSV gespeichert."
        )