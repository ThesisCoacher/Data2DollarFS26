"""
Airbnb Spider – Suchergebnisse für St. Gallen (OpenAir / OLMA)
===============================================================
Dieser Spider extrahiert Listing-Titel und Preise aus den Airbnb-Suchergebnissen.
Er nutzt die Selenium-Middleware, um die JavaScript-gerenderte Seite zu laden,
und navigiert über Pagination durch mehrere Ergebnisseiten.

Verwendung (über run_scraper.py oder direkt):
    scrapy crawl airbnb -a event=openair -a nachname=Muster -a vorname=Max
"""

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import scrapy
from airbnb_scraper.items import AirbnbItem


class AirbnbSpider(scrapy.Spider):
    """
    Scrapy-Spider für Airbnb-Suchergebnisse in St. Gallen.

    Unterstützt zwei Events:
        - 'openair'  → 25.–28. Juni 2026
        - 'olma'     → 08.–18. Oktober 2026

    Sammelt bis zu 100 Listings mit Titel und Preisen.
    """

    name = 'airbnb'

    # --- Such-URLs für die beiden Events ---
    EVENT_URLS = {
        'openair': (
            'https://www.airbnb.ch/s/St.-Gallen/homes'
            '?refinement_paths%5B%5D=%2Fhomes'
            '&date_picker_type=calendar'
            '&checkin=2026-06-25'
            '&checkout=2026-06-28'
            '&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A'
            '&search_type=autocomplete_click'
        ),
        'olma': (
            'https://www.airbnb.ch/s/St.-Gallen/homes'
            '?refinement_paths%5B%5D=%2Fhomes'
            '&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A'
            '&date_picker_type=calendar'
            '&checkin=2026-10-08'
            '&checkout=2026-10-18'
            '&search_type=user_map_move'
            '&query=St.%20Gallen'
        ),
    }

    # Anzahl Listings pro Airbnb-Suchergebnis-Seite (Stand 2024/2025: ca. 18)
    ITEMS_PER_PAGE = 18

    def __init__(self, event='openair', nachname='Nachname', vorname='Vorname',
                 max_listings=100, *args, **kwargs):
        """
        Spider-Initialisierung mit Kommandozeilen-Argumenten.

        Args:
            event:        'openair' oder 'olma'
            nachname:     Nachname für den Ausgabedateinamen
            vorname:      Vorname für den Ausgabedateinamen
            max_listings: Maximale Anzahl zu sammelnder Listings (Standard: 100)
        """
        super().__init__(*args, **kwargs)

        self.event = event.lower()
        self.nachname = nachname
        self.vorname = vorname
        self.max_listings = int(max_listings)

        # Zähler für gesammelte Listings
        self.collected_count = 0

        # Event-URL validieren
        if self.event not in self.EVENT_URLS:
            raise ValueError(
                f"Unbekanntes Event: '{self.event}'. "
                f"Verfügbare Events: {list(self.EVENT_URLS.keys())}"
            )

        self.logger.info(
            f"Spider konfiguriert: Event='{self.event}', "
            f"Max={self.max_listings} Listings, "
            f"Ausgabe: 2_{self.nachname}{self.vorname}_{self.event}.[json|csv]"
        )

    # -------------------------------------------------------------------------
    # Start-Requests: Erste Seite laden
    # -------------------------------------------------------------------------
    def start_requests(self):
        """Erste Suchergebnis-Seite als Scrapy-Request senden."""
        start_url = self.EVENT_URLS[self.event]

        yield scrapy.Request(
            url=start_url,
            callback=self.parse,
            # meta={'selenium': True} → Selenium-Middleware aktivieren
            meta={'selenium': True, 'page_number': 1},
            dont_filter=True
        )

    # -------------------------------------------------------------------------
    # Hauptparse-Methode: Listings extrahieren
    # -------------------------------------------------------------------------
    def parse(self, response):
        """
        Parsed eine Airbnb-Suchergebnis-Seite.

        1. Findet alle Listing-Karten auf der Seite
        2. Extrahiert Titel und Preise aus jeder Karte
        3. Navigiert zur nächsten Seite, falls nötig
        """
        page_number = response.meta.get('page_number', 1)
        self.logger.info(
            f"=== Seite {page_number} wird geparst "
            f"(bisher {self.collected_count}/{self.max_listings} Listings) ==="
        )

        # --- Listing-Karten finden ---
        # Primärer Selektor: Schema.org itemListElement (stabil über Airbnb-Updates)
        listings = response.css('div[itemprop="itemListElement"]')

        # Fallback: Airbnb-eigenes data-testid Attribut
        if not listings:
            listings = response.css('div[data-testid="card-container"]')
            self.logger.info("Fallback-Selektor 'card-container' verwendet.")

        # Zweiter Fallback: generische Listing-Karten mit role="group"
        if not listings:
            listings = response.css('div[role="group"][aria-labelledby]')
            self.logger.info("Fallback-Selektor 'role=group' verwendet.")

        self.logger.info(f"Gefundene Listing-Karten auf Seite {page_number}: {len(listings)}")

        if not listings:
            self.logger.warning(
                "KEINE Listings gefunden! Mögliche Ursachen:\n"
                "  - Airbnb blockiert den Zugriff (Anti-Bot)\n"
                "  - HTML-Struktur hat sich geändert\n"
                "  - Seite wurde nicht vollständig geladen"
            )
            # Debug: Seiteninhalt analysieren
            page_text = response.css('body::text').getall()
            if page_text:
                self.logger.debug(f"Seiteninhalt (Auszug): {' '.join(page_text[:5])}")
            return

        # --- Jedes Listing verarbeiten ---
        for listing in listings:
            # Abbruch, wenn Maximum erreicht
            if self.collected_count >= self.max_listings:
                self.logger.info(f"Maximum von {self.max_listings} Listings erreicht. Fertig!")
                return

            item = self._extract_listing_data(listing, page_number)
            if item:
                self.collected_count += 1
                item['nummer'] = self.collected_count
                yield item

        # --- Pagination: Nächste Seite laden ---
        if self.collected_count < self.max_listings:
            next_url = self._find_next_page_url(response)
            if next_url:
                self.logger.info(f"Navigiere zu Seite {page_number + 1}...")
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={'selenium': True, 'page_number': page_number + 1},
                    dont_filter=True
                )
            else:
                self.logger.info(
                    f"Keine weitere Seite gefunden. "
                    f"Insgesamt {self.collected_count} Listings gesammelt."
                )

    # -------------------------------------------------------------------------
    # Datenextraktion: Ein einzelnes Listing parsen
    # -------------------------------------------------------------------------
    def _extract_listing_data(self, listing, page_number):
        """
        Extrahiert Titel und Preise aus einer einzelnen Listing-Karte.

        Args:
            listing:     Scrapy-Selector des Listing-Containers
            page_number: Aktuelle Seitennummer

        Returns:
            AirbnbItem oder None (wenn keine Daten extrahiert werden konnten)
        """
        item = AirbnbItem()

        # --- 1. Titel extrahieren ---
        titel = self._extract_title(listing)
        if not titel:
            self.logger.debug("Listing übersprungen: Kein Titel gefunden.")
            return None

        # --- 2. Preise extrahieren ---
        preis_rabatt = self._extract_discount_price(listing)
        preis_original = self._extract_original_price(listing)

        # --- 3. Item zusammensetzen ---
        item['titel'] = titel
        item['preis_original'] = preis_original
        item['preis_rabatt'] = preis_rabatt
        item['event'] = self.event
        item['seite'] = page_number

        self.logger.debug(
            f"Listing: '{titel}' | Rabatt: {preis_rabatt} | Original: {preis_original}"
        )

        return item

    def _extract_title(self, listing):
        """
        Listing-Titel mit mehreren Selektor-Strategien extrahieren.

        Die Selektoren sind in der Reihenfolge ihrer Zuverlässigkeit sortiert.
        Falls der erste nicht greift, wird der nächste versucht.
        """
        # Strategie 1: data-testid Attribut (am stabilsten)
        title = listing.css('div[data-testid="listing-card-title"]::text').get()

        # Strategie 2: title-ID im Schema.org-Markup
        if not title:
            title_id = listing.css('[aria-labelledby]::attr(aria-labelledby)').get()
            if title_id:
                title = listing.css(f'#{title_id}::text').get()

        # Strategie 3: meta-Tag mit itemprop="name"
        if not title:
            title = listing.css('meta[itemprop="name"]::attr(content)').get()

        # Strategie 4: Erstes <div> innerhalb der Karte mit kurzem Text
        if not title:
            all_texts = listing.css('div::text').getall()
            # Titel ist typischerweise ein kurzer, nicht-leerer Text
            for text in all_texts:
                cleaned = text.strip()
                if cleaned and len(cleaned) > 3 and not cleaned.startswith('CHF'):
                    title = cleaned
                    break

        return title.strip() if title else None

    def _extract_discount_price(self, listing):
        """
        Rabattpreis extrahieren (der tatsächlich angezeigte, günstigere Preis).

        Selektor basiert auf der vom Benutzer identifizierten CSS-Klasse.
        HINWEIS: Airbnb verwendet generierte Klassennamen (z.B. 'u1opajno'),
        die sich bei Updates ändern können. Falls der Selektor nicht greift,
        muss die aktuelle Klasse im Browser-Inspektor nachgeschaut werden.
        """
        # Primär: Vom Benutzer identifizierte Klasse
        price = listing.css('span.u1opajno::text').get()

        # Fallback: Versuche den Preis über die Struktur zu finden
        # Der Rabattpreis ist typischerweise der ERSTE Preis-Span im Listing
        if not price:
            price_spans = listing.css('span._tyxjp1::text').getall()
            if price_spans:
                price = price_spans[0]

        return self._clean_price(price)

    def _extract_original_price(self, listing):
        """
        Originalpreis extrahieren (durchgestrichener Preis vor Rabatt).

        HINWEIS: Nicht alle Listings haben einen Rabattpreis.
        In diesem Fall gibt es keinen "Originalpreis".
        """
        # Primär: Vom Benutzer identifizierte Klasse
        price = listing.css('span.u174bpcy::text').get()

        # Fallback: Durchgestrichener Preis hat oft text-decoration: line-through
        if not price:
            price = listing.css('span[style*="line-through"]::text').get()

        return self._clean_price(price)

    # -------------------------------------------------------------------------
    # Pagination: URL der nächsten Seite ermitteln
    # -------------------------------------------------------------------------
    def _find_next_page_url(self, response):
        """
        URL der nächsten Ergebnisseite ermitteln.

        Strategie 1: "Weiter"-Link im gerenderten HTML finden
        Strategie 2: URL manuell mit items_offset-Parameter konstruieren
        """
        # Strategie 1: <a>-Tag mit dem Weiter-Button suchen
        # Airbnb verwendet aria-label="Weiter" (deutsch) oder "Next" (englisch)
        next_link = response.css('a[aria-label="Weiter"]::attr(href)').get()
        if not next_link:
            next_link = response.css('a[aria-label="Next"]::attr(href)').get()
        if not next_link:
            next_link = response.css('a[aria-label="Nächste"]::attr(href)').get()

        if next_link:
            # Relativen Link in absolute URL umwandeln
            full_url = response.urljoin(next_link)
            self.logger.info(f"Weiter-Link gefunden: {full_url[:80]}...")
            return full_url

        # Strategie 2: URL mit items_offset manuell konstruieren
        self.logger.info("Kein Weiter-Link gefunden. Konstruiere nächste URL manuell.")
        return self._construct_next_url(response.url)

    def _construct_next_url(self, current_url):
        """
        Nächste Seiten-URL manuell konstruieren.

        Airbnb verwendet den Parameter 'items_offset' für Pagination:
            Seite 1: kein Offset (items_offset=0)
            Seite 2: items_offset=18
            Seite 3: items_offset=36
            usw.
        """
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Aktuellen Offset bestimmen
        current_offset = int(params.get('items_offset', ['0'])[0])
        next_offset = current_offset + self.ITEMS_PER_PAGE

        # Neuen Offset setzen
        params['items_offset'] = [str(next_offset)]

        # URL wieder zusammenbauen
        # urlencode mit doseq=True, weil parse_qs Listen erstellt
        new_query = urlencode(params, doseq=True)
        next_url = urlunparse(parsed._replace(query=new_query))

        return next_url

    # -------------------------------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------------------------------
    @staticmethod
    def _clean_price(price_text):
        """
        Preis-Text bereinigen.

        Entfernt:
            - Non-breaking spaces (\\xa0 → normales Leerzeichen)
            - Führende/nachfolgende Leerzeichen
            - "Nacht"-Suffix

        Beispiel: '436\\xa0CHF' → '436 CHF'
        """
        if not price_text:
            return ''
        cleaned = price_text.replace('\xa0', ' ').strip()
        # "pro Nacht" oder "Nacht" entfernen, falls angehängt
        cleaned = re.sub(r'\s*(pro\s+)?Nacht$', '', cleaned).strip()
        return cleaned
