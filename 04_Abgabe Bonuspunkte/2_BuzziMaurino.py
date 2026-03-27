"""
Airbnb St. Gallen Webscraper mit Selenium & Scrapy-Integration
Ein robuster Scraper für Airbnb-Unterkünfte mit Pagination und Filtering.

Autor: Webscraper
Datum: 2026
Version: 2.0
"""

import csv
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from selenium import webdriver  # noqa: F401
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager  # noqa: F401
from bs4 import BeautifulSoup


# Konfiguriere Logging für besseres Debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AirbnbScraper:
    """
    Scraper für Airbnb Unterkünfte in St. Gallen.
    Extrahiert Name, Preis und handhabt Pagination sowie Filterung.
    Unterstützt mehrere Zeiträume/Events.
    """

    def __init__(self, headless: bool = True, delay: float = 2.0):
        """
        Initialisiere den Scraper.

        Args:
            headless: Starte Browser im Headless-Modus (ohne GUI)
            delay: Wartezeit zwischen Interaktionen in Sekunden
        """
        # Zwei Zeiträume mit Events
        self.urls = [
            {
                "url": (
                    "https://www.airbnb.ch/s/St.-Gallen--Schweiz/homes?"
                    "refinement_paths%5B%5D=%2Fhomes&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&"
                    "location=St.+Gallen%2C+Schweiz&checkin=2026-06-25&checkout=2026-06-28&"
                    "date_picker_type=calendar&adults=1&children=0"
                ),
                "event": "Openair",
                "target_listings": 100
            },
            {
                "url": (
                    "https://www.airbnb.ch/s/St.-Gallen--Schweiz/homes?"
                    "refinement_paths%5B%5D=%2Fhomes&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&"
                    "location=St.+Gallen%2C+Schweiz&checkin=2026-10-08&checkout=2026-10-18&"
                    "date_picker_type=calendar&adults=1&children=0"
                ),
                "event": "Olma",
                "target_listings": 100
            }
        ]
        self.current_event: str = ""
        self.driver = None
        self.wait = None
        self.headless = headless
        self.delay = delay
        self.listings: List[Dict[str, str]] = []
        
    def setup_driver(self) -> None:
        """Initialisiere den Selenium WebDriver mit automatischem Treiber-Management."""
        logger.info("Starte Chrome WebDriver...")
        
        options = webdriver.ChromeOptions()
        
        if self.headless:
            options.add_argument("--headless")
        
        # Weitere Chrome-Optionen für Stabilität
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Verwende webdriver-manager für automatisches Treiber-Management
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Setze implizites Timeout (wartet auf Elemente)
        self.driver.implicitly_wait(10)
        
        # WebDriverWait für explizite Waits
        self.wait = WebDriverWait(self.driver, 15)
        
        logger.info("WebDriver erfolgreich initialisiert")
    
    def close_driver(self) -> None:
        """Schließe den WebDriver."""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver geschlossen")
    
    def is_available_at_similar_dates(self, listing_element) -> bool:
        """
        Prüfe, ob die Unterkunft mit 'An ähnlichen Reisedaten verfügbar' markiert ist.
        Diese Unterkünfte werden ausgeschlossen.

        Args:
            listing_element: Das BeautifulSoup-Element der Unterkunft

        Returns:
            True wenn markiert, False sonst
        """
        try:
            # Suche nach dem Badge mit "An ähnlichen Reisedaten verfügbar"
            badge_text = listing_element.get_text()
            return "An ähnlichen Reisedaten verfügbar" in badge_text
        except Exception as e:
            logger.debug(f"Fehler beim Prüfen des Verfügbarkeitsstatus: {e}")
            return False

    def extract_price_from_listing(self, container) -> str:
        """
        Extrahiere Preis aus verschiedenen Quellen.
        Versuche normale Preis-Spans und versteckte Preise in Buttons (für Rabatt-Angebote).

        Args:
            container: BeautifulSoup-Element der Unterkunft

        Returns:
            Preis als String, oder "N/A" wenn nicht gefunden
        """
        price = "N/A"

        # Versuche 1: Normale Preis-Span (class="u174bpcy")
        price_span = container.find("span", class_="u174bpcy")
        if price_span:
            price_text = price_span.get_text(strip=True)
            # Extrahiere numerischen Wert (z.B. "198" aus "198 CHF")
            price = price_text.split()[0] if price_text else "N/A"
            if price != "N/A":
                return price

        # Versuche 2: Versteckter Preis im Button (Rabatt-Angebot)
        # Suche nach Button mit aria-expanded="false" und aria-haspopup="dialog"
        try:
            price_button = container.find(
                "button",
                attrs={"role": "button", "aria-expanded": "false",
                       "aria-haspopup": "dialog"}
            )
            if price_button:
                # Finde den span mit der Preisklasse "u1opajno" innerhalb des Buttons
                price_span_in_button = price_button.find("span", class_="u1opajno")
                if price_span_in_button:
                    price_text = price_span_in_button.get_text(strip=True)
                    # Entferne Whitespace-Zeichen und extrahiere Zahl
                    price_clean = price_text.replace("\xa0", "").strip()
                    # Extrahiere numerischen Wert (z.B. "1030" aus "1'030 CHF")
                    price_numeric = "".join(c for c in price_clean if c.isdigit())
                    if price_numeric:
                        price = price_numeric
        except Exception as e:
            logger.debug(f"Fehler beim Extrahieren des versteckten Preises: {e}")

        return price
    
    def extract_listings_from_page(self) -> int:
        """
        Extrahiere alle Unterkünfte von der aktuellen Seite.
        Schließe Unterkünfte mit 'An ähnlichen Reisedaten verfügbar' aus.

        Returns:
            Anzahl der extrahierten Unterkünfte
        """
        logger.info("Extrahiere Listings von aktueller Seite...")

        # Warte bis Listing-Karten geladen sind
        try:
            self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "[data-testid='card-container']")
                )
            )
        except TimeoutException:
            logger.warning("Listings haben nicht geladen")
            return 0

        # Lese den Seiten-HTML
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Finde alle Listing-Container
        # Jede Unterkunft ist in einem div mit data-testid="card-container"
        listing_containers = soup.find_all("div",
                                            attrs={"data-testid": "card-container"})

        logger.info(f"Gefundene Listing-Container: {len(listing_containers)}")

        count = 0
        for container in listing_containers:
            try:
                # Prüfe auf Ausschlusskriterium
                if self.is_available_at_similar_dates(container):
                    logger.debug(
                        "Überspringe Unterkunft: 'An ähnlichen Reisedaten verfügbar'"
                    )
                    continue

                # Extrahiere echten Unterkunftsnamen
                # Der Name ist im span mit data-testid="listing-card-name"
                name = "N/A"

                # Suche nach dem Name-Element
                name_span = container.find(
                    "span", attrs={"data-testid": "listing-card-name"}
                )
                if name_span:
                    name = name_span.get_text(strip=True)

                # Fallback: Versuche aria-label zu finden
                if name == "N/A":
                    img_div = container.find("div", attrs={"role": "img"})
                    if img_div and img_div.get("aria-label"):
                        aria_label = img_div.get("aria-label")
                        # aria-label Format: "Unterkunftsname. 1 Schlafzimmer.
                        # 5 Bewertungen. 198 CHF pro Nacht."
                        # Extrahiere nur den Namen (vor dem ersten Punkt)
                        name = (aria_label.split(".")[0].strip()
                                if "." in aria_label else aria_label)

                # Extrahiere Preis mit verbesserter Logik
                price = self.extract_price_from_listing(container)

                # Speichere Listing mit Event-Information
                if name != "N/A":
                    self.listings.append({
                        "name": name,
                        "price_chf": price,
                        "event": self.current_event,
                        "extraction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    logger.info(
                        f"✓ Extrahiert: {name} - {price} CHF ({self.current_event})"
                    )
                    count += 1

            except StaleElementReferenceException:
                logger.warning("Stale Element - überspringen")
                continue
            except Exception as e:
                logger.warning(f"Fehler beim Extrahieren eines Listings: {e}")
                continue

        logger.info(f"Seite extrahiert: {count} neue Listings")
        return count
    
    def click_next_button(self) -> bool:
        """
        Klicke auf den "Weiter"-Button für Pagination.
        
        Returns:
            True wenn Button geklickt wurde, False wenn keine weitere Seite verfügbar
        """
        try:
            # Finde den "Weiter"-Button (aria-label enthält "Weiter")
            next_button = self.driver.find_element(
                By.XPATH,
                "//a[contains(@aria-label, 'Weiter')]"
            )
            
            # Prüfe, ob Button sichtbar und aktiviert ist
            if next_button.is_displayed() and next_button.is_enabled():
                logger.info("Klicke auf 'Weiter'-Button...")
                next_button.click()
                
                # Warte auf neue Seite zu laden
                time.sleep(self.delay)
                self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "[data-testid='listing-card-title']")
                    )
                )
                logger.info("✓ Nächste Seite geladen")
                return True
            else:
                logger.info("Kein 'Weiter'-Button verfügbar - Ende der Pagination")
                return False
                
        except NoSuchElementException:
            logger.info("Keine weitere Seite verfügbar")
            return False
        except TimeoutException:
            logger.warning("Timeout beim Warten auf neue Seite")
            return False
        except Exception as e:
            logger.error(f"Fehler beim Button-Klick: {e}")
            return False
    
    def scrape(self, max_pages: int = 10) -> List[Dict[str, str]]:
        """
        Hauptmethode zum Scrapen für alle konfigurierten URLs/Events.

        Args:
            max_pages: Maximale Anzahl der Seiten pro Event zum Scrapen

        Returns:
            Liste der extrahierten Unterkünfte aus allen Events
        """
        try:
            self.setup_driver()

            # Scrape für jedes konfigurierte Event
            for url_config in self.urls:
                self.current_event = url_config["event"]
                min_listings = url_config["target_listings"]
                url = url_config["url"]

                logger.info(f"\n\n{'='*60}")
                logger.info(f"Starte Scrapen für Event: {self.current_event}")
                logger.info(
                    f"Ziel: min. {min_listings} Unterkünfte, max {max_pages} Seiten"
                )
                logger.info(f"{'='*60}")

                self.driver.get(url)

                # Scrape erste Seite
                self.extract_listings_from_page()

                # Scrape weitere Seiten mit Pagination bis Ziel erreicht
                for page_num in range(1, max_pages):
                    logger.info(f"\n--- {self.current_event} Seite {page_num + 1} ---")

                    # Überprüfe, ob minimales Ziel für dieses Event erreicht ist
                    event_listings = [l for l in self.listings
                                      if l["event"] == self.current_event]
                    if len(event_listings) >= min_listings:
                        logger.info(
                            f"Minimales Ziel von {min_listings} "
                            f"für {self.current_event} erreicht!"
                        )
                        break

                    # Versuche nächste Seite zu öffnen
                    if not self.click_next_button():
                        logger.info("Pagination beendet")
                        break

                    # Extrahiere Listings von neuer Seite
                    self.extract_listings_from_page()

            logger.info(f"\n\n=== Gesamt Scraping abgeschlossen ===")
            logger.info(f"Gesamte extrahierte Unterkünfte: {len(self.listings)}")

            # Zusammenfassung pro Event
            for event_name in [cfg["event"] for cfg in self.urls]:
                event_count = len([l for l in self.listings
                                   if l["event"] == event_name])
                logger.info(f"{event_name}: {event_count} Unterkünfte")

            return self.listings

        except Exception as e:
            logger.error(f"Kritischer Fehler während des Scrapens: {e}")
            return self.listings
        finally:
            self.close_driver()
    
    def save_to_csv(self, filename: str = "airbnb_listings.csv") -> None:
        """
        Speichere extrahierte Daten in CSV-Datei.

        Args:
            filename: Name der Ausgabedatei
        """
        if not self.listings:
            logger.warning("Keine Daten zum Speichern")
            return

        try:
            filepath = Path(filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ["name", "price_chf", "event", "extraction_date"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(self.listings)

            logger.info(f"✓ Daten gespeichert in: {filepath.absolute()}")

        except IOError as e:
            logger.error(f"Fehler beim Speichern der CSV: {e}")
    
    def save_to_json(self, filename: str = "airbnb_listings.json") -> None:
        """
        Speichere extrahierte Daten in JSON-Datei.
        
        Args:
            filename: Name der Ausgabedatei
        """
        if not self.listings:
            logger.warning("Keine Daten zum Speichern")
            return
        
        try:
            filepath = Path(filename)
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(self.listings, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ JSON gespeichert in: {filepath.absolute()}")
            
        except IOError as e:
            logger.error(f"Fehler beim Speichern der JSON: {e}")


def main():
    """Hauptfunktion - führe den Scraper aus."""

    # Erstelle Scraper-Instanz
    scraper = AirbnbScraper(headless=False, delay=2.0)

    # Führe Scraping durch (100 Unterkünfte pro Event, max 10 Seiten pro Event)
    listings = scraper.scrape(max_pages=10)

    # Speichere Ergebnisse im selben Ordner wie das Skript
    if listings:
        script_dir = Path(__file__).parent
        csv_path = script_dir / "airbnb_st_gallen_listings.csv"
        json_path = script_dir / "airbnb_st_gallen_listings.json"

        scraper.save_to_csv(str(csv_path))
        scraper.save_to_json(str(json_path))

        # Zeige Zusammenfassung
        print(f"\n{'='*50}")
        print(f"Scraping abgeschlossen!")
        print(f"Gesamte Unterkünfte: {len(listings)}")
        print(f"{'='*50}\n")

        # Zeige Zusammenfassung nach Events
        for event_name in ["Openair", "Olma"]:
            event_listings = [l for l in listings if l["event"] == event_name]
            print(f"{event_name}: {len(event_listings)} Unterkünfte")

        print("\nErste 10 Unterkünfte:")
        for i, listing in enumerate(listings[:10], 1):
            print(
                f"{i}. {listing['name']} - {listing['price_chf']} CHF "
                f"({listing['event']})"
            )
    else:
        print("Keine Unterkünfte extrahiert")


if __name__ == "__main__":
    main()
