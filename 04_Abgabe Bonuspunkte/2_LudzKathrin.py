import re
import time
from urllib.parse import urljoin

import scrapy
from scrapy.selector import Selector

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager


class AirbnbChallenge2Spider(scrapy.Spider):
    name = "airbnb_challenge2"
    allowed_domains = ["airbnb.com", "www.airbnb.com"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 2,
        "LOG_LEVEL": "INFO",
    }

    target_pages = [
        {
            "event": "Openair",
            "checkin": "2026-06-25",
            "checkout": "2026-06-28",
            "url": "https://www.airbnb.com/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-06-25&checkout=2026-06-28&date_picker_type=calendar&search_type=unknown&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&search_mode=regular_search&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&source=structured_search_input_header"
        },
        {
            "event": "OLMA",
            "checkin": "2026-10-08",
            "checkout": "2026-10-18",
            "url": "https://www.airbnb.com/s/St.-Gallen/homes?place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&refinement_paths%5B%5D=%2Fhomes&checkin=2026-10-08&checkout=2026-10-18&date_picker_type=calendar&search_type=unknown&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&search_mode=regular_search&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&source=structured_search_input_header"
        }
    ]

    def start_requests(self):
        for page in self.target_pages:
            yield scrapy.Request(
                url=page["url"],
                callback=self.parse,
                meta=page,
                dont_filter=True
            )

    def parse(self, response):
        event = response.meta["event"]
        checkin = response.meta["checkin"]
        checkout = response.meta["checkout"]
        url = response.meta["url"]

        driver = None

        try:
            driver = self._build_driver()
            self.logger.info(f"Öffne Suchseite für {event}")
            driver.get(url)

            self._handle_cookie_banner(driver)
            self._wait_for_search_results(driver)

            results = []
            seen_listing_urls = set()
            max_pages = 15

            for page_number in range(1, max_pages + 1):
                self.logger.info(f"{event}: verarbeite Suchergebnisseite {page_number}")

                self._wait_for_search_results(driver)
                time.sleep(2)
                sel = Selector(text=driver.page_source)
                cards = self._extract_listing_cards(sel)

                self.logger.info(f"{event}: {len(cards)} Karten auf Seite {page_number} gefunden")

                for card in cards:
                    listing_url = self._extract_listing_url(card)
                    displayed_price_raw = self._extract_price_raw(card)

                    if not listing_url:
                        continue

                    if listing_url in seen_listing_urls:
                        continue

                    seen_listing_urls.add(listing_url)

                    results.append(
                        {
                            "event": event,
                            "checkin": checkin,
                            "checkout": checkout,
                            "listing_url": listing_url,
                            "displayed_price_raw": displayed_price_raw,
                        }
                    )

                    if len(results) >= 100:
                        break

                if len(results) >= 100:
                    break

                moved = self._go_to_next_results_page(driver)
                if not moved:
                    self.logger.info(f"{event}: keine weitere Ergebnisseite gefunden")
                    break

                time.sleep(3)

            self.logger.info(f"{event}: {len(results)} Listings aus Suchergebnissen gesammelt")

            enriched_results = []
            for i, item in enumerate(results[:100], start=1):
                self.logger.info(f"{event}: lese Detailseite {i}/{min(len(results), 100)}")
                exact_name = self._extract_exact_title_from_detail_page(driver, item["listing_url"])

                enriched_results.append(
                    {
                        "event": item["event"],
                        "checkin": item["checkin"],
                        "checkout": item["checkout"],
                        "name": exact_name,
                        "displayed_price_raw": item["displayed_price_raw"],
                        "listing_url": item["listing_url"],
                    }
                )

            for item in enriched_results:
                yield item

        except Exception as exc:
            self.logger.error(f"Fehler bei {event}: {exc}")
        finally:
            if driver:
                driver.quit()

    def _build_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1600,2200")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--lang=en-US")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        return driver

    def _handle_cookie_banner(self, driver):
        possible_xpaths = [
            "//button[contains(., 'Accept')]",
            "//button[contains(., 'accept')]",
            "//button[contains(., 'Alle akzeptieren')]",
            "//button[contains(., 'Akzeptieren')]",
            "//button[contains(., 'OK')]",
            "//button[contains(., 'Agree')]",
            "//button[contains(., 'I agree')]"
        ]

        for xpath in possible_xpaths:
            try:
                button = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                time.sleep(1)
                self.logger.info("Cookie-Banner bestätigt.")
                return
            except Exception:
                continue

    def _wait_for_search_results(self, driver):
        locators = [
            (By.CSS_SELECTOR, 'div[itemprop="itemListElement"]'),
            (By.CSS_SELECTOR, 'div[data-testid="card-container"]'),
            (By.CSS_SELECTOR, 'a[href*="/rooms/"]'),
            (By.TAG_NAME, "body")
        ]

        for locator in locators:
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located(locator)
                )
                return
            except TimeoutException:
                continue

    def _extract_listing_cards(self, selector):
        candidates = [
            'div[itemprop="itemListElement"]',
            'div[data-testid="card-container"]',
            'article',
            'div[role="group"]'
        ]

        for css in candidates:
            cards = selector.css(css)
            if len(cards) >= 5:
                return cards

        return []

    def _extract_listing_url(self, card):
        href = card.css('a[href*="/rooms/"]::attr(href)').get()
        if not href:
            href = card.xpath('.//a[contains(@href, "/rooms/")]/@href').get()

        if href:
            return urljoin("https://www.airbnb.com", href)

        return None

    def _extract_price_raw(self, card):
        """
        Bevorzugt den aktuell angezeigten reduzierten Preis.
        Falls ein 'total'-Preis vorhanden ist, wird dieser bevorzugt.
        Durchgestrichene Altpreise werden ignoriert.
        """
        visible_text_nodes = card.xpath(
            './/*[not(self::del) and not(ancestor::del) and not(self::s) and not(ancestor::s) and not(self::strike) and not(ancestor::strike)]/text()'
        ).getall()

        visible_texts = [self._clean_text(t) for t in visible_text_nodes if self._clean_text(t)]
        visible_joined = " | ".join(visible_texts)

        total_match = self._find_best_price_with_context(visible_joined, prefer_total=True)
        if total_match:
            return total_match

        normal_match = self._find_best_price_with_context(visible_joined, prefer_total=False)
        if normal_match:
            return normal_match

        attribute_candidates = card.xpath('.//@aria-label').getall() + card.xpath('.//@content').getall()
        for value in attribute_candidates:
            cleaned = self._clean_text(value)
            if cleaned and "CHF" in cleaned.upper():
                match = self._find_best_price_with_context(cleaned, prefer_total=True) or \
                        self._find_best_price_with_context(cleaned, prefer_total=False)
                if match:
                    return match

        return None

    def _find_best_price_with_context(self, text, prefer_total=False):
        """
        Findet Preisangaben robust und bevorzugt je nach Bedarf:
        - bei prefer_total=True zuerst Preise mit 'total'
        - ansonsten den wahrscheinlich aktuell sichtbaren Preis
        """
        if not text:
            return None

        normalized = text.replace("\u202f", " ").replace("\xa0", " ")
        normalized = normalized.replace("’", "'").replace("‘", "'")

        patterns = [
            r'((?:CHF)\s?[0-9]{1,3}(?:[\'.,][0-9]{3})*(?:[.,][0-9]{2})?)',
            r'([0-9]{1,3}(?:[\'.,][0-9]{3})*(?:[.,][0-9]{2})?\s?(?:CHF))',
        ]

        matches = []
        for pattern in patterns:
            for m in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                full_match = self._clean_text(m.group(1))
                start, end = m.span()

                left_context = normalized[max(0, start - 30):start].lower()
                right_context = normalized[end:min(len(normalized), end + 30)].lower()
                context = left_context + " " + right_context

                matches.append(
                    {
                        "price": full_match,
                        "context": context
                    }
                )

        if not matches:
            return None

        if prefer_total:
            total_matches = [m for m in matches if "total" in m["context"]]
            if total_matches:
                return total_matches[-1]["price"]

        filtered = []
        for m in matches:
            ctx = m["context"]
            if "original" in ctx or "before" in ctx:
                continue
            filtered.append(m)

        if filtered:
            return filtered[-1]["price"]

        return matches[-1]["price"]

    def _go_to_next_results_page(self, driver):
        current_url = driver.current_url

        next_xpath_candidates = [
            "//a[@aria-label='Next']",
            "//a[@aria-label='Weiter']",
            "//button[@aria-label='Next']",
            "//button[@aria-label='Weiter']",
            "//a[contains(@href, 'items_offset=')]"
        ]

        for xpath in next_xpath_candidates:
            try:
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                driver.execute_script("arguments[0].click();", next_button)
                WebDriverWait(driver, 15).until(lambda d: d.current_url != current_url)
                return True
            except Exception:
                continue

        try:
            page_links = driver.find_elements(By.XPATH, "//a[normalize-space(text()) and number(normalize-space(text()))=number(normalize-space(text()))]")
            for link in page_links:
                try:
                    label = link.text.strip()
                    if label and label.isdigit():
                        href = link.get_attribute("href")
                        current_page_match = re.search(r'items_offset=(\d+)', current_url)
                        next_page_match = re.search(r'items_offset=(\d+)', href or "")

                        if href and href != current_url:
                            if current_page_match and next_page_match:
                                if int(next_page_match.group(1)) > int(current_page_match.group(1)):
                                    driver.execute_script("arguments[0].click();", link)
                                    time.sleep(3)
                                    return True
                            elif not current_page_match:
                                driver.execute_script("arguments[0].click();", link)
                                time.sleep(3)
                                return True
                except Exception:
                    continue
        except Exception:
            pass

        return False

    def _extract_exact_title_from_detail_page(self, driver, listing_url):
        try:
            driver.get(listing_url)
            time.sleep(2)

            title_selectors = [
                (By.CSS_SELECTOR, "h1"),
                (By.XPATH, "//h1"),
                (By.XPATH, "//meta[@property='og:title']")
            ]

            for by, locator in title_selectors:
                try:
                    if by == By.XPATH and locator == "//meta[@property='og:title']":
                        element = driver.find_element(by, locator)
                        content = element.get_attribute("content")
                        cleaned = self._clean_title(content)
                        if cleaned:
                            return cleaned
                    else:
                        element = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((by, locator))
                        )
                        text = element.text or element.get_attribute("textContent")
                        cleaned = self._clean_title(text)
                        if cleaned:
                            return cleaned
                except Exception:
                    continue

            cleaned = self._clean_title(driver.title)
            if cleaned:
                return cleaned

        except Exception:
            pass

        return None

    def _clean_title(self, value):
        value = self._clean_text(value)
        if not value:
            return None

        value = re.sub(r"\s*-\s*Airbnb.*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*\|\s*Airbnb.*$", "", value, flags=re.IGNORECASE)
        return value

    @staticmethod
    def _clean_text(value):
        if not value:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        return value if value else None

