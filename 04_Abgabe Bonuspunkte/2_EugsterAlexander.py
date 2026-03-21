import re
import time

import scrapy
from scrapy.crawler import CrawlerProcess

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class AirbnbStGallenSpider(scrapy.Spider):
    """
    Scrapy + Selenium Spider für Airbnb St. Gallen.
    Ziel:
    - für zwei Zeiträume je die ersten 100 Unterkünfte extrahieren
    - Name
    - Preis pro Nacht
    """

    name = "airbnb_stgallen"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "LOG_LEVEL": "INFO",
        "FEEDS": {
            str(BASE_DIR / "airbnb_stgallen_results.json"): {
                "format": "json",
                "encoding": "utf8",
                "indent": 2,
                "overwrite": True,
            },
            str(BASE_DIR / "airbnb_stgallen_results.csv"): {
                "format": "csv",
                "encoding": "utf8",
                "overwrite": True,
            },
        },
    }

    SEARCH_PAGES = [
        {
            "event_name": "OpenAir St.Gallen",
            "checkin": "2026-06-25",
            "checkout": "2026-06-28",
            "base_url": "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&adults=1&guests=1&search_type=AUTOSUGGEST",
        },
        {
            "event_name": "OLMA",
            "checkin": "2026-10-08",
            "checkout": "2026-10-18",
            "base_url": "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-10-08&checkout=2026-10-18&date_picker_type=calendar&adults=1&guests=1&search_type=unknown&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&search_mode=regular_search&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&source=structured_search_input_header",
        },
    ]

    MAX_RESULTS = 110

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1600,3000")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--lang=de-CH")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)

    def closed(self, reason):
        if hasattr(self, "driver"):
            self.driver.quit()

    def start_requests(self):
        """
        Startet einen Scrapy-Request pro Zeitraum.
        Die eigentliche Extraktion läuft dann mit Selenium.
        """
        for search_page in self.SEARCH_PAGES:
            yield scrapy.Request(
                url=search_page["base_url"],
                callback=self.parse_with_selenium,
                meta=search_page,
                dont_filter=True,
            )

    def parse_with_selenium(self, response):
        event_name = response.meta["event_name"]
        checkin = response.meta["checkin"]
        checkout = response.meta["checkout"]
        url = response.url

        self.logger.info(f"Starte Verarbeitung für {event_name}: {url}")

        try:
            self.driver.get(url)
        except WebDriverException as exc:
            self.logger.error(f"Seite konnte nicht geladen werden: {exc}")
            return

        self.accept_cookies_if_present()

        aggregated_listings = self.collect_listings_across_pages(target_count=self.MAX_RESULTS)

        if not aggregated_listings:
            self.logger.warning(
                "Keine Listings gefunden. Vermutlich müssen die Selektoren/Heuristiken angepasst werden."
            )
            return

        for listing in aggregated_listings:
            rank = listing.get("rank")
            if rank and rank > self.MAX_RESULTS:
                break

            yield {
                "event_name": event_name,
                "city": "St. Gallen",
                "checkin": checkin,
                "checkout": checkout,
                "rank": rank,
                "name": listing.get("name"),
                "gesamtpreis": listing.get("gesamtpreis"),
                "originalpreis": listing.get("originalpreis"),
                "aktionspreis": listing.get("aktionspreis"),
                "raw_card_text": listing.get("raw_card_text"),
                "listing_url": listing.get("listing_url"),
                "source_search_url": url,
            }

    def accept_cookies_if_present(self):
        """
        Versucht gängige Cookie-Buttons zu klicken.
        Bei Airbnb variieren Sprache und DOM-Struktur.
        """
        possible_xpaths = [
            "//button[contains(., 'Akzeptieren')]",
            "//button[contains(., 'Alle akzeptieren')]",
            "//button[contains(., 'Accept')]",
            "//button[contains(., 'Accept all')]",
            "//button[contains(., 'OK')]",
        ]

        for xpath in possible_xpaths:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                time.sleep(1)
                self.logger.info("Cookie-Banner akzeptiert.")
                return
            except Exception:
                continue

    def wait_for_initial_results(self):
        """
        Wartet darauf, dass erste room-Links sichtbar sind.
        """
        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/rooms/')]"))
            )
        except TimeoutException:
            self.logger.warning("Keine room-Links innerhalb des Timeouts gefunden.")

    def collect_listings_across_pages(self, target_count=100, max_pages=15):
        """
        Sammelt Listings über mehrere Airbnb-Ergebnisseiten hinweg.
        Vorgehen:
        - aktuelle Seite laden
        - bis ans Ende scrollen
        - Listings extrahieren
        - auf den Weiter-Pfeil klicken
        - wiederholen, bis target_count erreicht ist oder keine nächste Seite existiert
        """
        self.wait_for_initial_results()

        seen_urls = set()
        aggregated_listings = []
        current_page = 1
        seen_listing_keys = set()

        while current_page <= max_pages and len(aggregated_listings) < target_count:
            self.logger.info(f"Verarbeite Ergebnisseite {current_page}.")

            self.scroll_current_page_to_bottom()
            listings = self.extract_cards_via_javascript()

            if not listings:
                self.logger.warning(f"Keine Listings auf Seite {current_page} extrahiert.")
            else:
                for listing in listings:
                    listing_url = listing.get("listing_url")
                    listing_key = listing.get("listing_key") or listing_url

                    if not listing_url or not listing_key:
                        continue

                    if listing_key in seen_listing_keys or listing_url in seen_urls:
                        continue

                    listing["rank"] = len(aggregated_listings) + 1
                    seen_listing_keys.add(listing_key)
                    seen_urls.add(listing_url)
                    aggregated_listings.append(listing)

                    if len(aggregated_listings) >= target_count:
                        break

            self.logger.info(
                f"Bisher gesammelt: {len(aggregated_listings)} eindeutige Listings nach Seite {current_page}."
            )

            if len(aggregated_listings) >= target_count:
                break

            moved_to_next_page = self.go_to_next_results_page(current_page)
            if not moved_to_next_page:
                self.logger.info("Keine weitere Ergebnisseite gefunden.")
                break

            current_page += 1
            time.sleep(2)
            self.wait_for_initial_results()

        return aggregated_listings[:target_count]

    def scroll_current_page_to_bottom(self, max_rounds=20):
        """
        Scrollt die aktuelle Ergebnisseite bis nach unten, damit alle Cards der Seite geladen werden.
        """
        previous_height = 0

        for round_number in range(max_rounds):
            room_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/rooms/')]")
            self.logger.info(
                f"Seite wird gescrollt, Runde {round_number + 1}: {len(room_links)} room-Links sichtbar."
            )

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == previous_height:
                break
            previous_height = new_height

    def go_to_next_results_page(self, current_page):
        """
        Klickt auf den Weiter-Pfeil der Airbnb-Pagination.
        Es werden mehrere robuste XPaths versucht, da Airbnb die DOM-Struktur ändern kann.
        """
        next_button_xpaths = [
            "//a[@aria-label='Weiter']",
            "//a[@aria-label='Next']",
            "//button[@aria-label='Weiter']",
            "//button[@aria-label='Next']",
            "//a[.//div[text()='›']]",
            "//button[.//div[text()='›']]",
            "//a[contains(@href, 'items_offset')]",
        ]

        current_room_links = len(self.driver.find_elements(By.XPATH, "//a[contains(@href, '/rooms/') ]"))

        for xpath in next_button_xpaths:
            try:
                next_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", next_button)

                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(By.XPATH, "//a[contains(@href, '/rooms/') ]")) != current_room_links
                    or f"items_offset=" in d.current_url
                    or f"page={current_page + 1}" in d.current_url
                )
                self.logger.info(f"Wechsel auf Ergebnisseite {current_page + 1} erfolgreich.")
                return True
            except Exception:
                continue

        return False

    def extract_cards_via_javascript(self):
        """
        Extrahiert Listing-Daten möglichst robust direkt im Browser.
        Wir verlassen uns nicht auf fragile Airbnb-Klassennamen, sondern auf:
        - room-Links
        - nächstliegenden Container
        - sichtbaren Text im Container
        - Preis via Regex
        """
        script = r"""
        function cleanText(text) {
            if (!text) return "";
            return text.replace(/\s+/g, " ").trim();
        }

        function findCardContainer(anchor) {
            let node = anchor;
            for (let i = 0; i < 8 && node; i++) {
                const text = cleanText(node.innerText || "");
                if (text.length > 30) {
                    return node;
                }
                node = node.parentElement;
            }
            return anchor.parentElement || anchor;
        }
        function buildListingKey(url) {
            if (!url) return null;
            const roomIdMatch = String(url).match(/\/rooms\/(\d+)/i);
            if (roomIdMatch) {
                return `room_${roomIdMatch[1]}`;
            }
            return String(url).split("?")[0];
        }

        function extractPriceInfo(text) {
            if (!text) {
                return {
                    gesamtpreis: null,
                    originalpreis: null,
                    aktionspreis: null
                };
            }

            const lines = text
                .split("\n")
                .map(line => cleanText(line))
                .filter(line => line.length > 0);

            const priceRegex = /([\d'.,]+)\s?(CHF|Fr\.?)/gi;

            function extractPricesFromLine(line) {
                return [...line.matchAll(priceRegex)].map(match => match[1]);
            }

            const totalPriceLines = lines.filter(line => /gesamtpreis/i.test(line));
            if (totalPriceLines.length > 0) {
                const pricesOnTotalLines = totalPriceLines.flatMap(extractPricesFromLine);
                if (pricesOnTotalLines.length >= 2) {
                    return {
                        gesamtpreis: pricesOnTotalLines[pricesOnTotalLines.length - 1],
                        originalpreis: pricesOnTotalLines[pricesOnTotalLines.length - 2],
                        aktionspreis: pricesOnTotalLines[pricesOnTotalLines.length - 1]
                    };
                }
                if (pricesOnTotalLines.length === 1) {
                    const allPrices = lines.flatMap(extractPricesFromLine);
                    const totalPrice = pricesOnTotalLines[0];
                    const allButLastMatching = allPrices.filter(price => price !== totalPrice);
                    return {
                        gesamtpreis: totalPrice,
                        originalpreis: allButLastMatching.length > 0 ? allButLastMatching[allButLastMatching.length - 1] : null,
                        aktionspreis: allButLastMatching.length > 0 ? totalPrice : null
                    };
                }
            }

            const allPrices = lines.flatMap(extractPricesFromLine);
            if (allPrices.length >= 2) {
                return {
                    gesamtpreis: allPrices[allPrices.length - 1],
                    originalpreis: allPrices[allPrices.length - 2],
                    aktionspreis: allPrices[allPrices.length - 1]
                };
            }
            if (allPrices.length === 1) {
                return {
                    gesamtpreis: allPrices[0],
                    originalpreis: null,
                    aktionspreis: null
                };
            }

            return {
                gesamtpreis: null,
                originalpreis: null,
                aktionspreis: null
            };
        }

        function normalizePrice(rawPrice) {
            if (!rawPrice) return null;
            let cleaned = String(rawPrice);
            cleaned = cleaned.replace(/CHF|Fr\.?/gi, "");
            cleaned = cleaned.replace(/\s+/g, "");
            cleaned = cleaned.replace(/'/g, "");
            cleaned = cleaned.replace(/,/g, ".");
            cleaned = cleaned.trim();

            const numeric = parseFloat(cleaned);
            if (isNaN(numeric)) return null;
            return numeric;
        }

        function extractNameFromText(text) {
            if (!text) return null;

            const lines = text
                .split("\n")
                .map(line => cleanText(line))
                .filter(line => line.length > 0);

            const blacklistPatterns = [
                /^neu$/i,
                /^guest favourite$/i,
                /^gäste-favorit$/i,
                /^superhost$/i,
                /^durchschnittliche bewertung:/i,
                /^bewertung/i,
                /^\d+[\d.,()\s]*(von|\/)\s*5/i,
                /^\d+(?:[.,]\d+)?\s*\(\d+\)$/i,
                /CHF/i,
                /pro nacht/i,
                /nächte/i,
                /gesamtpreis/i,
                /^\d{1,2}\.\s*bis\s*\d{1,2}\./i,
                /^\d{1,2}\.\s*juni/i,
                /^\d{1,2}\.\s*okt/i,
                /^zahle heute/i,
                /^kostenlose stornierung/i,
                /^preisaufschlüsselung anzeigen/i,
                /^private:r gastgeber:in$/i,
                /^privatzimmer$/i,
                /^zimmer in /i,
                /^wohnung in /i,
                /^unterkunft in /i,
                /^loft in /i,
                /^hotel in /i,
                /^eigentumswohnung in /i
            ];

            function isBlacklisted(line) {
                return blacklistPatterns.some(pattern => pattern.test(line));
            }

            for (let i = 0; i < lines.length - 1; i++) {
                const current = lines[i];
                const next = lines[i + 1];

                if (
                    /^(zimmer|wohnung|unterkunft|loft|hotel|eigentumswohnung) in /i.test(current) &&
                    !isBlacklisted(next)
                ) {
                    return next;
                }
            }

            for (let i = 0; i < lines.length - 2; i++) {
                const a = lines[i];
                const b = lines[i + 1];
                const c = lines[i + 2];

                if (!isBlacklisted(a) && !isBlacklisted(b) && !isBlacklisted(c)) {
                    return b;
                }
            }

            for (const line of lines) {
                if (!isBlacklisted(line) && line.length >= 5) {
                    return line;
                }
            }

            return lines.length > 0 ? lines[0] : null;
        }

        const anchors = Array.from(document.querySelectorAll('a[href*="/rooms/"]'));
        const results = [];
        const seenListingKeys = new Set();

        for (const anchor of anchors) {
            const href = anchor.getAttribute("href");
            const absoluteUrl = href ? new URL(href, location.origin).href : null;
            const listingKey = buildListingKey(absoluteUrl);

            if (!absoluteUrl || !listingKey || seenListingKeys.has(listingKey)) {
                continue;
            }

            const card = findCardContainer(anchor);
            if (!card) {
                continue;
            }

            seenListingKeys.add(listingKey);

            const rawCardText = card.innerText || "";
            const rawText = cleanText(rawCardText);
            const rawPrices = extractPriceInfo(rawCardText);
            const gesamtpreis = normalizePrice(rawPrices.gesamtpreis);
            const originalpreis = normalizePrice(rawPrices.originalpreis);
            const aktionspreis = normalizePrice(rawPrices.aktionspreis);

            const listingAnchor = card.querySelector('a[href*="/rooms/"]') || anchor;
            const listingHref = listingAnchor.getAttribute("href");
            const listingAbsoluteUrl = listingHref ? new URL(listingHref, location.origin).href : absoluteUrl;
            const finalListingKey = buildListingKey(listingAbsoluteUrl) || listingKey;

            const name = extractNameFromText(rawCardText);

            results.push({
                position_on_page: results.length + 1,
                listing_key: finalListingKey,
                name: name,
                raw_card_text: rawText,
                gesamtpreis: gesamtpreis,
                originalpreis: originalpreis,
                aktionspreis: aktionspreis,
                listing_url: listingAbsoluteUrl
            });
        }

        return results;
        """

        try:
            results = self.driver.execute_script(script)
        except Exception as exc:
            self.logger.error(f"JavaScript-Extraktion fehlgeschlagen: {exc}")
            return []

        # Python-seitige Nachbereinigung
        cleaned_results = []
        for item in results:
            listing_url = item.get("listing_url")
            listing_key = item.get("listing_key")
            if not listing_url:
                continue

            name = self.clean_name(item.get("name"))
            gesamtpreis = item.get("gesamtpreis")
            originalpreis = item.get("originalpreis")
            aktionspreis = item.get("aktionspreis")
            raw_text = item.get("raw_card_text")
            position_on_page = item.get("position_on_page")

            if not name:
                name = raw_text[:120].strip() if raw_text else None

            cleaned_results.append({
                "position_on_page": position_on_page,
                "listing_key": listing_key,
                "name": name,
                "gesamtpreis": gesamtpreis,
                "originalpreis": originalpreis,
                "aktionspreis": aktionspreis,
                "raw_card_text": raw_text,
                "listing_url": listing_url,
            })

        return cleaned_results

    @staticmethod
    def clean_name(name):
        if not name:
            return None
        name = re.sub(r"\s+", " ", name).strip()
        name = re.sub(r"^[\-–|:,;]+", "", name).strip()
        if len(name) < 3:
            return None
        return name


if __name__ == "__main__":
    process = CrawlerProcess()
    process.crawl(AirbnbStGallenSpider)
    process.start()