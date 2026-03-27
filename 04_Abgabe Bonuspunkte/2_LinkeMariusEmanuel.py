import scrapy
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..items import AirbnbAdvancedVscodeItem
import time


# ─────────────────────────────────────────────────────────────────────────────
# KONFIGURATION: Zeiträume und Ausgabedateien hier anpassen
# Jeder Eintrag definiert einen Event mit URL und zugehöriger CSV-Ausgabedatei
# ─────────────────────────────────────────────────────────────────────────────
PERIODS = [
    {
        'event':       'OpenAir St. Gallen',
        'output_file': 'openair_results.csv',
        'url': (
            'https://www.airbnb.ch/s/St.-Gallen/homes'
            '?refinement_paths%5B%5D=%2Fhomes'
            '&flexible_trip_lengths%5B%5D=one_week'
            '&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01'
            '&price_filter_input_type=2&channel=EXPLORE&zoom_level=12'
            '&search_type=autocomplete_click'
            '&location_bb=Qj4gt0EYfyBCPZSjQRNmOA%3D%3D'
            '&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a'
            '&date_picker_type=calendar&checkin=2026-06-25&checkout=2026-06-28'
        ),
    },
    {
        'event':       'OLMA',
        'output_file': 'olma_results.csv',
        'url': (
            'https://www.airbnb.ch/s/St.-Gallen/homes'
            '?refinement_paths%5B%5D=%2Fhomes'
            '&flexible_trip_lengths%5B%5D=one_week'
            '&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01'
            '&price_filter_input_type=2&channel=EXPLORE&zoom_level=12'
            '&search_type=autocomplete_click'
            '&location_bb=Qj4gt0EYfyBCPZSjQRNmOA%3D%3D'
            '&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a'
            '&date_picker_type=calendar&checkin=2026-10-08&checkout=2026-10-18'
        ),
    },
]


class GetdataSpider(scrapy.Spider):
    name = "getdata"
    allowed_domains = ["www.airbnb.ch"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Selenium Setup: Chrome wird headless (unsichtbar) gestartet
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')           # Auskommentiert: Chrome wird sichtbar geöffnet
        options.add_argument('--no-sandbox')         # Erforderlich auf manchen Servern
        options.add_argument('--disable-dev-shm-usage')  # Verhindert Speicherprobleme
        # webdriver-manager lädt den passenden ChromeDriver automatisch herunter
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def closed(self, _reason):
        # Scrapy ruft closed() garantiert auf — auch bei Exceptions
        self.driver.quit()

    def start_requests(self):
        # Statt start_urls verwenden wir start_requests(), damit wir pro URL
        # Metadaten (output_file) an die parse()-Methode übergeben können
        for period in PERIODS:
            self.logger.info(f"Starte Crawl für: {period['event']} → {period['output_file']}")
            yield scrapy.Request(
                url=period['url'],
                callback=self.parse,
                # cb_kwargs übergibt Argumente direkt an parse()
                cb_kwargs={'output_file': period['output_file']},
            )

    def parse(self, response, output_file):
        # Teile der Pipeline mit, in welche Datei dieser Lauf geschrieben wird
        self.current_output_file = output_file

        # Selenium öffnet die URL im Browser (JavaScript wird ausgeführt)
        self.driver.get(response.url)

        # Warte bis die ersten Listing-Titel geladen sind (max. 10 Sekunden)
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="listing-card-title"]'))
            )
        except Exception as e:
            self.logger.error(f"Fehler beim Laden der Seite ({output_file}): {e}")
            return

        page_count = 0
        max_pages = 10  # Sicherheitslimit gegen Endlosschleifen

        while page_count < max_pages:
            # Alle Listing-Titel der aktuellen Seite sammeln
            title_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="listing-card-title"]')
            self.logger.info(f"{output_file} — Seite {page_count + 1}: {len(title_elements)} Listings gefunden")

            for title_element in title_elements:
                item = AirbnbAdvancedVscodeItem()

                # --- TITEL ---
                # data-testid="listing-card-title" → z.B. "Zimmer in St. Gallen"
                item['title'] = title_element.text

                # --- KARTEN-CONTAINER ermitteln ---
                # Gehe im DOM nach oben bis zum <li>-Element (Wurzel der Listing-Karte)
                try:
                    card_container = title_element.find_element(By.XPATH, 'ancestor::li[1]')
                except Exception:
                    try:
                        card_container = title_element.find_element(By.XPATH, 'ancestor::div[5]')
                    except Exception:
                        card_container = title_element

                # --- UNTERTITEL ---
                # data-testid="listing-card-name" → z.B. "Das Haus mit dem Schwein"
                try:
                    subtitle_element = card_container.find_element(
                        By.CSS_SELECTOR, '[data-testid="listing-card-name"]'
                    )
                    item['subtitle'] = subtitle_element.text
                except Exception:
                    item['subtitle'] = None

                # --- PREIS & RABATTPREIS ---
                # data-testid="price-availability-row" enthält den gesamten Preisbereich
                # Fall 1 (Rabatt):  aria-label = "139 CHF Gesamtpreis, ursprünglich 169 CHF"
                # Fall 2 (kein Rabatt): <span> enthält direkt "198 CHF Gesamtpreis"
                try:
                    price_container = card_container.find_element(
                        By.CSS_SELECTOR, '[data-testid="price-availability-row"]'
                    )

                    # Suche alle <span>-Elemente mit aria-label im Preis-Container
                    aria_spans = price_container.find_elements(By.XPATH, './/span[@aria-label]')

                    discount_found = False
                    for span in aria_spans:
                        aria_label = span.get_attribute('aria-label') or ''
                        if 'ursprünglich' in aria_label:
                            # Rabattfall: parse beide Preise aus dem aria-label
                            match = re.search(
                                r'([\d\s]+)\s*CHF\s*Gesamtpreis,\s*ursprünglich\s*([\d\s]+)\s*CHF',
                                aria_label
                            )
                            if match:
                                item['price'] = match.group(1).strip() + ' CHF'
                                item['discount_price'] = match.group(2).strip() + ' CHF'
                                discount_found = True
                                break

                    if not discount_found:
                        # Kein Rabatt: erster <span> mit "CHF" im Text
                        price_span = price_container.find_element(
                            By.XPATH, './/span[contains(text(),"CHF")]'
                        )
                        item['price'] = price_span.text
                        item['discount_price'] = None

                except Exception:
                    item['price'] = None
                    item['discount_price'] = None

                yield item

            # --- PAGINATION ---
            try:
                next_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[aria-label="Weiter"]'))
                )
                next_button.click()
                # Warte bis die alten Titel nicht mehr im DOM sind (Seitenwechsel erkannt)
                WebDriverWait(self.driver, 10).until(
                    EC.staleness_of(title_elements[0]) if title_elements
                    else EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="listing-card-title"]'))
                )
                page_count += 1
                time.sleep(1)  # Kurze Pause nach dem Seitenwechsel
            except Exception as e:
                self.logger.info(f"Keine weitere Seite für {output_file}: {e}")
                break
