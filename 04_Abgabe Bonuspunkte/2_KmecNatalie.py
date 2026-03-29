import re
import time
import scrapy
from scrapy.http import Request

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager


class AirbnbSpider(scrapy.Spider):
    name = "airbnb"
    allowed_domains = ["airbnb.com"]

    def __init__(self, period=None, limit=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.driver = None
        self.seen = set()
        self.limit = int(limit) if limit else 100  # Default 100, kann mit -a limit=20 überschrieben werden

        # Alle verfügbaren Suchzeiträume
        self.all_periods = {
            "june": (
                "https://www.airbnb.com/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&adults=2&guests=2&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&search_mode=regular_search&source=structured_search_input_header&search_type=unknown",
                3,
                "Juni 2026 (3 Nächte)",
            ),
            "october": (
                "https://www.airbnb.com/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&checkin=2026-10-08&checkout=2026-10-18&date_picker_type=calendar&adults=2&guests=2&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&search_mode=regular_search&source=structured_search_input_header&search_type=unknown",
                10,
                "Oktober 2026 (10 Nächte)",
            ),
        }

        # Setze den/die Suchzeitraum(e)
        if period and period.lower() in self.all_periods:
            self.search_periods = [self.all_periods[period.lower()]]
            self.logger.info(f"🎯 Verarbeite nur: {period.lower()}")
        else:
            self.search_periods = list(self.all_periods.values())
            self.logger.info("🎯 Verarbeite alle Zeiträume")

    def start_requests(self):
        for url, nights, period_name in self.search_periods:
            yield Request(
                url=url,
                callback=self.parse,
                meta={
                    "period_name": period_name,
                    "nights": nights,
                },
            )

    def _init_driver(self):
        """Starte einen neuen Selenium WebDriver."""
        chrome_options = Options()
        # Headless Mode aktiviert für schnelleres Scraping
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.logger.info("✅ Neuer Selenium WebDriver gestartet")

    def parse(self, response):
        period_name = response.meta["period_name"]
        nights = response.meta["nights"]
        max_listings_per_period = self.limit  # Nutze selbst gesetztes Limit (default 100)
        count = 0

        # Beende alten Driver und starte neuen (für jeden Zeitraum frisch)
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("✅ Alter WebDriver beendet")
            except Exception as e:
                self.logger.debug(f"Fehler beim Beenden des alten Drivers: {e}")
        
        self._init_driver()

        self.logger.info(f"🔍 Starte: {period_name} (Ziel: {max_listings_per_period} Listings)")
        self.logger.info(f"📱 Lade URL: {response.url[:80]}...")
        self.driver.get(response.url)
        
        # Warte auf Seite zu laden
        time.sleep(5)
        
        # Scrolle oben an
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        wait = WebDriverWait(self.driver, 30)

        try:
            # Warte bis Listings geladen sind (card-container)
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="card-container"]'))
            )
            self.logger.info(f"✅ Listings geladen für {period_name}")
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden von card-container: {str(e)[:100]}")
            return

        while count < max_listings_per_period:
            time.sleep(2)

            # Hauptcontainer: card-container
            card_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="card-container"]')
            self.logger.info(f"📍 Gefundene Kartenelemente: {len(card_elements)}")

            if not card_elements:
                self.logger.info("❌ Keine Kartenelemente gefunden")
                break

            for card in card_elements:
                if count >= max_listings_per_period:
                    break

                try:
                    # Name extrahieren: [data-testid="listing-card-name"]
                    listing_name = None
                    try:
                        name_el = card.find_element(By.CSS_SELECTOR, '[data-testid="listing-card-name"]')
                        listing_name = name_el.text.strip()
                    except:
                        # Fallback: [data-testid="listing-card-title"]
                        try:
                            name_el = card.find_element(By.CSS_SELECTOR, '[data-testid="listing-card-title"]')
                            listing_name = name_el.text.strip()
                        except:
                            pass

                    if not listing_name:
                        continue

                    # URL extrahieren: suche Link mit /rooms/
                    listing_url = None
                    try:
                        links = card.find_elements(By.XPATH, './/a[contains(@href, "/rooms/")]')
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "/rooms/" in href:
                                listing_url = href.split("?")[0]
                                break
                    except:
                        pass

                    if not listing_url:
                        continue

                    # Deduplizierung
                    dedupe_key = (period_name, listing_url)
                    if dedupe_key in self.seen:
                        continue

                    # Preis extrahieren: Versuche aria-label zuerst, dann Fallback für Juni
                    total_price = None
                    currency = "CHF"
                    
                    try:
                        # Strategie 1: aria-label Attribut (stabil über CSS-Klassen-Änderungen hinweg)
                        # Funktioniert für Oktober und andere Perioden
                        try:
                            price_span = card.find_element(
                                By.CSS_SELECTOR,
                                '[data-testid="price-availability-row"] span[aria-label]'
                            )
                            aria_label = price_span.get_attribute("aria-label").strip()
                            self.logger.debug(f"🔍 RAW ARIA-LABEL: {aria_label}")
                            total_price, currency = self._extract_total_price(aria_label)
                            
                            if total_price is not None:
                                self.logger.debug(f"✅ Preis via aria-label: {total_price} {currency}")
                        except:
                            # aria-label nicht vorhanden, versuche Fallback
                            pass
                        
                        # Strategie 2: Fallback auf sichtbaren Text vom price-availability-row
                        # Funktioniert für Juni und andere Perioden ohne aria-label
                        if total_price is None:
                            try:
                                price_row = card.find_element(
                                    By.CSS_SELECTOR,
                                    '[data-testid="price-availability-row"]'
                                )
                                price_text = price_row.text.strip()
                                self.logger.debug(f"🔍 FALLBACK TEXT: {price_text}")
                                total_price, currency = self._extract_total_price(price_text)
                                
                                if total_price is not None:
                                    self.logger.debug(f"✅ Preis via fallback text: {total_price} {currency}")
                            except:
                                pass
                        
                        if total_price is None:
                            # Keine Preisinformation gefunden
                            self.logger.debug(f"⚠️ Keine Preisinformation gefunden, überspringe Listing")
                            continue
                            
                    except Exception as e:
                        self.logger.debug(f"⚠️ Preis-Extraktion fehlgeschlagen: {str(e)[:50]}")
                        continue

                    # Deduplizierung bestätigen
                    self.seen.add(dedupe_key)
                    count += 1

                    self.logger.info(f"✨ [{count}] {listing_name} - {total_price} {currency}")

                    yield {
                        "search_period": period_name,
                        "listing_name": listing_name,
                        "total_price": total_price,
                        "currency": currency,
                        "nights": nights,
                        "source_url": listing_url,
                    }

                except Exception as e:
                    self.logger.debug(f"Fehler bei Listing in Karte: {e}")
                    continue

            if count >= max_listings_per_period:
                break

            # Pagination mit URL-Vergleich
            current_url = self.driver.current_url
            self.logger.info(f"📄 Aktuelle URL: {current_url[:80]}...")
            
            try:
                next_link = None
                
                # Suche Next-Button
                selectors = [
                    'a[aria-label="Next"]',
                    'a[aria-label="Weiter"]',
                ]
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            if el.is_displayed():
                                next_link = el
                                break
                        if next_link:
                            break
                    except:
                        continue
                
                if not next_link:
                    self.logger.info(f"✅ Keine weitere Seite mehr für {period_name}.")
                    break
                
                # Scrolle zu Button und klicke
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", next_link)
                self.logger.info(f"📌 Next-Button geklickt.")
                
                # Warte auf neue Listings
                time.sleep(2)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="card-container"]'))
                )
                
                # Prüfe URL-Änderung
                new_url = self.driver.current_url
                if new_url == current_url:
                    self.logger.info(f"✅ URL hat sich nicht geändert → Ende")
                    break
                
            except Exception as e:
                self.logger.info(f"✅ Pagination beendet: {str(e)[:50]}")
                break

        self.logger.info(f"🏁 Fertig: {period_name} - {count} Listings")

    def _extract_total_price(self, text):
        """
        Extrahiert den GESAMTPREIS aus der aria-label.
        
        Strategien (in Reihenfolge):
        1. Suche nach "total" oder "Gesamtpreis" - diese kennzeichnen den Gesamtpreis
        2. Falls nicht gefunden: Nimm den GRÖßTEN CHF-Wert
        """
        if not text:
            return None, "CHF"

        text = text.strip()

        if "CHF" not in text:
            return None, "CHF"

        # Normalisiere: Entferne ALLE Trennzeichen (Kommas, Apostrophes, Punkte, Leerzeichen, etc.)
        # Dies funktioniert für alle Unicode-Varianten von Apostrophes und Trennzeichen
        normalized_text = re.sub(r"[\s,.\-'`'''\u2019]", "", text)
        self.logger.debug(f"🔎 NORMALIZED: '{text}' -> '{normalized_text}'")

        # Strategie 1: Suche nach "CHFtotal" oder "CHFGesamtpreis" (nach Normalisierung)
        # Dies identifiziert den Gesamtpreis explizit
        for keyword in ["total", "Gesamtpreis", "gesamtpreis"]:
            pattern = r"(\d+)CHF" + re.escape(keyword)
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                self.logger.debug(f"✅ Parsed (({keyword}): {value} CHF from '{text}'")
                return value, "CHF"

        # Strategie 2: Finde ALLE CHF-Werte und nimm den GRÖßTEN
        matches = re.findall(r"(\d+)CHF", normalized_text, re.IGNORECASE)
        if matches:
            values = [float(m) for m in matches]
            largest_value = max(values)
            self.logger.debug(f"✅ Parsed (largest): {largest_value} CHF from '{text}'")
            return largest_value, "CHF"

        return None, "CHF"

    def closed(self, reason):
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("✅ WebDriver beendet")
            except Exception as e:
                self.logger.debug(f"Fehler beim Beenden des Drivers: {e}")
