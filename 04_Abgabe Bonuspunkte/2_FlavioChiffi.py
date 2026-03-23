"""Airbnb-Scrapy-Spider zur Erhebung von Listing-Daten für zwei Eventzeiträume.

Der Spider nutzt Selenium für das Rendern dynamischer Inhalte und extrahiert
strukturierte Felder pro Listing zur Speicherung in eine CSV-Datei.
"""

import scrapy
from scrapy.selector import Selector

from selenium import webdriver
from time import sleep
from random import uniform

# Befehle fürs Terminal
# cd BonusAufgabe02 -> in den Ordner wechseln, in dem sich die Scrapy-Projektdateien befinden
# del results.csv -> delete old csv file
# py -m scrapy crawl getData -o results.csv -> run the spider and save the results in a csv file

# NOTES:
# - In Settings wurden folgende änderungen vorgenommen:
#   - ROBOTSTXT_OBEY = False (da die Seite das Crawlen nicht erlaubt, aber wir es trotzdem tun wollen)
#   - FEED_EXPORT_ENCODING = "utf-8-sig" (um sicherzustellen, dass Umlaute korrekt in der CSV-Datei gespeichert werden)

class GetdataSpider(scrapy.Spider):
    """
    Spider, um Listing-Daten von Airbnb für St. Gallen zu sammeln.
    Es werden die ersten 100 Listings für zwei Ereigniszeiträume erhoben:

    - OpenAir (2026-06-25 bis 2026-06-28)
    - OLMA (2026-10-08 bis 2026-10-18)

    Attributes:
        name (str): Interner Scrapy-Name des Spiders.
        allowed_domains (list): Erlaubte Domains für das Crawlen.
        start_urls (list): Start-URLs für die beiden Ereigniszeiträume.

    Output-Felder:
        - event, listing_title, listing_subtitle
        - price_main, price_noDiscount, price_discount
        - effective_price, price_per_night

    Transparenz: ROBOTSTXT_OBEY = False, da Airbnb das Crawlen nicht erlaubt.
    Dies wurde bewusst so gewählt, um die Aufgabe zu erfüllen.
    """

    name = "getData"
    allowed_domains = ["www.airbnb.ch"]
    start_urls = [
        "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&search_type=unknown&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&search_mode=regular_search&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&source=structured_search_input_header",
        "https://www.airbnb.ch/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-10-08&checkout=2026-10-18&date_picker_type=calendar&search_type=AUTOSUGGEST"
        ]

    def init_driver(self):
        """Erstellt und konfiguriert den Selenium-WebDriver für Chrome.

        Es werden Optionen gesetzt, um den Ablauf ohne sichtbares Browserfenster
        auszuführen und typische Automatisierungsmerkmale zu reduzieren.

        Returns:
            webdriver.Chrome: Initialisierter Selenium-WebDriver.
        """
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")              # kein sichtbares Browserfenster
        chrome_options.add_argument("--window-size=1920,1080") # konsistente Fenstergrösse
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # versteckt Selenium-Erkennung
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) # weitere Maßnahme gegen Erkennung
        driver = webdriver.Chrome(options=chrome_options)
        return driver

    def get_event_from_url(self, url):
        """Leitet das Event aus der Airbnb-Such-URL ab.

        Args:
            url (str): Request-URL mit Datumsparametern.

        Returns:
            str: "OpenAir" für den OpenAir-Zeitraum, sonst "OLMA".
        """
        if "2026-06-25" in url:
            return "OpenAir"
        return "OLMA"

    def sleep_random(self, min_seconds, max_seconds):
        """Pausiert für eine zufällige Dauer innerhalb eines Intervalls.

        Args:
            min_seconds (float): Untere Grenze der Wartezeit in Sekunden.
            max_seconds (float): Obere Grenze der Wartezeit in Sekunden.
        """
        sleep(uniform(min_seconds, max_seconds))

    def compute_price_per_night(self, effective_price, event):
        """Berechnet den Preis pro Nacht aus dem extrahierten Gesamtpreis.

        Args:
            effective_price (str | None): Preistext aus dem Listing.
            event (str): Event-Kennung ("OpenAir" oder "OLMA").

        Returns:
            float | None: Preis pro Nacht oder None, falls keine valide
                Berechnung möglich ist.
        """
        # Wenn kein effektiver Preis vorhanden: price_per_night kann nicht berechnet werden
        if not effective_price:
            return None

        # Entferne alle non-digit Zeichen aus dem effektiven Preis
        digits_only = ''.join(filter(str.isdigit, effective_price))
        # Wenn nach dem Etnfernen aller non-digit Zeichen, digits_only leer ist, kann price_per_night nicht berechnet werden
        if not digits_only:
            return None

        # Berechne den Preis pro Nacht je nach Event
        if event == "OpenAir":
            return round(float(digits_only) / 3, 2)
        if event == "OLMA":
            return round(float(digits_only) / 10, 2)
        # Wenn das Event unbekannt ist, kann price_per_night nicht berechnet werden
        return None

    def extract_listing_data(self, card, event):
        """Extrahiert alle relevanten Felder aus einer einzelnen Listing-Karte.

        Args:
            card (Selector): Scrapy-Selector eines Listing-Containers.
            event (str): Event-Kennung für die Preisberechnung.

        Returns:
            dict: Strukturierter Datensatz mit Titel-, Preis- und Eventfeldern.
        """
        # Extrahiere den Titel
        listing_title = card.xpath(
            './/div[@data-testid="listing-card-title"]/text()'
            ).get()
        # Extrahiere den Untertitel
        listing_subtitle = card.xpath(
            './/*[@data-testid="listing-card-subtitle"]//span/text()'
            ).get()
        # Zeilenumbrüche und extra Leerzeichen entfernen
        if listing_subtitle:
            listing_subtitle = " ".join(listing_subtitle.split())
        # Extrahiere die Preise (je nachdem, ob es einen Rabatt gibt oder nicht)
        price_main = card.xpath(
            './/span[contains(@class, "u174bpcy")]/text()'
            ).get()
        price_noDiscount = card.xpath(
            './/span[contains(@class, "u1opajno")]/text()'
            ).get()
        price_discount = card.xpath(
            './/span[contains(@class, "sjwpj0z")]/text()'
            ).get()

        # Effektiver Preis: Rabattpreis wenn vorhanden, sonst Normalpreis
        effective_price = price_discount if price_discount else price_main
        # Preis pro Nacht berechnen
        price_per_night = self.compute_price_per_night(effective_price, event)

        return {
            "event": event,
            "listing_title": listing_title,
            "listing_subtitle": listing_subtitle,
            "price_main": price_main,
            "price_noDiscount": price_noDiscount,
            "price_discount": price_discount,
            "effective_price": effective_price,
            "price_per_night": price_per_night,
        }

    def go_to_next_page(self, driver):
        """Navigiert in den Suchergebnissen auf die nächste Seite.

        Args:
            driver (webdriver.Chrome): Aktiver Selenium-WebDriver.

        Returns:
            bool: True bei erfolgreichem Seitenwechsel, sonst False.
        """
        # Erst ganz nach unten scrollen damit der Next-Button geladen wird
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Kurze Pause, damit Elemente vollständig geladen sind
        self.sleep_random(1, 3)

        # Versuch, auf die nächste Ergebnisseite zu gehen
        try:
            next_button = driver.find_element(
                "xpath",
                "//a[@aria-label='Weiter' or aria-label='Next']"
            )
        except Exception:
            return False

        # Next-Button direkt in den sichtbaren Bereich scrollen
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            next_button
        )
        # Kurze Pause, damit der Button vollständig geladen ist
        self.sleep_random(1, 3)

        # Zufällige Pause + Klick
        self.sleep_random(3, 6)
        # Klick auf den Next-Button mit JavaScript, um mögliche Probleme mit Selenium zu umgehen
        driver.execute_script("arguments[0].click();", next_button)
        # Warte zufällig, damit die nächste Seite vollständig geladen ist
        self.sleep_random(2, 4)

        return True
    
    def parse(self, response):
        """Haupt-Parser für die Listing-Extraktion je Start-URL.

        Der Parser lädt die Seite mit Selenium, extrahiert bis zu 100 Listings,
        traversiert über Folgeseiten und gibt jeden Datensatz an Scrapy zurück.

        Args:
            response (scrapy.http.Response): Initiale Scrapy-Response der Start-URL.

        Yields:
            dict: Ein extrahierter und normalisierter Listing-Datensatz.
        """
        # Starte den Selenium WebDriver
        driver = self.init_driver()

        # Mit try-finally sicherstellen, dass der WebDriver am Ende geschlossen wird, auch wenn Fehler auftreten
        try:
            # Lade die Seite
            driver.get(response.url)

            # Wartet, damit die Seite vollständig geladen ist
            self.sleep_random(2, 5)

            # Bestimme welches Event
            event = self.get_event_from_url(response.url)

            collected_listings = 0

            while collected_listings < 100:
                # Erstelle einen Selector aus dem Seitenquelltext, um die Daten zu extrahieren
                selector = Selector(text=driver.page_source)

                # Alle angebotenen Unterkünfte auf der Seite finden
                cards = selector.xpath('//div[contains(@class, "g1qv1ctd")]')

                # Für jede Unterkunft
                for card in cards:
                    # Überprüfe, ob weniger als 100 listings gesammelt:
                    if collected_listings >= 100:
                        break
                    # Extrahiere die relevanten Daten aus der Karte
                    listing_data = self.extract_listing_data(card, event)

                    # Speichere die extrahierten Daten in einem Dictionary und yield es, damit es in der CSV-Datei gespeichert wird
                    yield listing_data

                    # Erhöhe die Anzahl der gesammelten Listings
                    collected_listings += 1

                # Navigiere zur nächsten Seite, wenn es noch nicht 100 Listings gibt
                if not self.go_to_next_page(driver):
                    break  # kein Next-Button mehr → while-Schleife beenden
        finally:
            # Schließe den WebDriver
            driver.quit()