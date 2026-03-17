import re
import time

import scrapy

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class AirbnbChallengeSpider(scrapy.Spider):
    name = "airbnb_challenge_2"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "LOG_LEVEL": "INFO",
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 2,
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    SEARCH_TARGETS = [
        {
            "label": "2026-06-25_to_2026-06-28",
            "url": "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&location_bb=Qj4gt0EYfyBCPZSjQRNmOA%3D%3D&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&checkin=2026-06-25&checkout=2026-06-28&adults=1&search_type=autocomplete_click",
        },
        {
            "label": "2026-10-08_to_2026-10-18",
            "url": "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&checkin=2026-10-08&checkout=2026-10-18&adults=1&search_type=unknown&query=St.%20Gallen&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&search_mode=regular_search&disable_auto_translation=true&price_filter_input_type=2&price_filter_num_nights=3&channel=EXPLORE&source=structured_search_input_header",
        },
    ]

    MAX_LISTINGS_PER_SEARCH = 100
    MAX_SCROLL_ROUNDS = 15
    MAX_PAGINATION_ROUNDS = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.driver = self._build_driver()

    def _build_driver(self):
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1700,2600")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--lang=de-CH")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(90)
            return driver
        except WebDriverException as exc:
            raise RuntimeError("Chrome WebDriver konnte nicht gestartet werden.") from exc

    def start_requests(self):
        for target in self.SEARCH_TARGETS:
            yield scrapy.Request(
                url=target["url"],
                callback=self.parse_search_results,
                dont_filter=True,
                meta={
                    "label": target["label"],
                    "source_url": target["url"],
                },
            )

    def parse_search_results(self, response):
        label = response.meta["label"]
        source_url = response.meta["source_url"]

        self.logger.info("Lade Airbnb-Suchseite: %s", label)
        self.driver.get(source_url)

        self._handle_cookie_banner()
        self._wait_for_results()

        collected_items = []
        seen_room_ids = set()
        position = 0

        for page_round in range(1, self.MAX_PAGINATION_ROUNDS + 1):
            self.logger.info("Bearbeite %s | Runde %s", label, page_round)

            self._scroll_results_page()

            room_links = self._get_room_links()
            self.logger.info("Gefundene Room-Links: %s", len(room_links))

            new_items_this_round = 0

            for link in room_links:
                try:
                    href = link.get_attribute("href")
                except StaleElementReferenceException:
                    continue

                if not href or "/rooms/" not in href:
                    continue

                listing_url = href.split("?")[0]
                room_id = self._extract_room_id(listing_url)

                if not room_id:
                    continue
                if room_id in seen_room_ids:
                    continue
                seen_room_ids.add(room_id)

                card = self._get_card_root(link)
                if card is None:
                    continue

                card_data = self._collect_card_data(card)
                if not card_data["lines"]:
                    continue

                listing_name = self._extract_listing_name(card_data)
                price_info = self._extract_total_price_info(card_data)

                position += 1
                item = {
                    "search_label": label,
                    "position": position,
                    "listing_name": listing_name,
                    "total_price": price_info["total_price"],
                    "currency": price_info["currency"],
                    "displayed_price_text": price_info["displayed_price_text"],
                    "listing_url": listing_url,
                }

                collected_items.append(item)
                new_items_this_round += 1

                if len(collected_items) >= self.MAX_LISTINGS_PER_SEARCH:
                    break

            self.logger.info(
                "Neue Unterkünfte in dieser Runde: %s | Gesamt: %s",
                new_items_this_round,
                len(collected_items),
            )

            if len(collected_items) >= self.MAX_LISTINGS_PER_SEARCH:
                break

            if not self._go_to_next_results_page():
                self.logger.info("Keine weitere Seite gefunden.")
                break

        self.logger.info(
            "Extraktion abgeschlossen für %s: %s Datensätze",
            label,
            len(collected_items),
        )

        for item in collected_items[: self.MAX_LISTINGS_PER_SEARCH]:
            yield item

    def _handle_cookie_banner(self):
        possible_xpaths = [
            '//button[contains(., "Alle akzeptieren")]',
            '//button[contains(., "Akzeptieren")]',
            '//button[contains(., "Accept all")]',
            '//button[contains(., "Accept")]',
            '//button[contains(., "Nur notwendige")]',
            '//button[contains(., "Only necessary")]',
        ]

        for xpath in possible_xpaths:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                time.sleep(1)
                return
            except Exception:
                continue

    def _wait_for_results(self):
        wait = WebDriverWait(self.driver, 30)
        locators = [
            (By.CSS_SELECTOR, 'a[href*="/rooms/"]'),
            (By.TAG_NAME, "main"),
            (By.TAG_NAME, "body"),
        ]

        last_exception = None
        for locator in locators:
            try:
                wait.until(EC.presence_of_element_located(locator))
                time.sleep(3)
                return
            except TimeoutException as exc:
                last_exception = exc

        raise TimeoutException("Keine Airbnb-Suchergebnisse gefunden.") from last_exception

    def _scroll_results_page(self):
        stable_rounds = 0
        previous_count = 0

        for scroll_round in range(1, self.MAX_SCROLL_ROUNDS + 1):
            current_count = len(self._get_room_links())
            self.logger.info("Scroll-Runde %s | Room-Links: %s", scroll_round, current_count)

            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

            time.sleep(2.5)

            new_count = len(self._get_room_links())

            if new_count <= previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0

            previous_count = new_count

            if stable_rounds >= 2:
                break

    def _get_room_links(self):
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/rooms/"]')
        except Exception:
            return []

    def _extract_room_id(self, url):
        if not url:
            return None
        match = re.search(r"/rooms/(\d+)", url)
        return match.group(1) if match else None

    def _get_card_root(self, link_element):
        try:
            card = self.driver.execute_script(
                """
                const link = arguments[0];
                let el = link;

                while (el && el !== document.body) {
                    const text = (el.innerText || '').trim();
                    const roomLinks = el.querySelectorAll('a[href*="/rooms/"]').length;

                    if (
                        text.length >= 40 &&
                        (
                            text.includes('CHF') ||
                            text.toLowerCase().includes('gesamtpreis') ||
                            text.toLowerCase().includes('stornierung') ||
                            roomLinks <= 3
                        )
                    ) {
                        return el;
                    }
                    el = el.parentElement;
                }

                return link.parentElement || link;
                """,
                link_element,
            )
            return card
        except Exception:
            return None

    def _collect_card_data(self, card):
        data = {
            "inner_text": "",
            "text_content": "",
            "lines": [],
        }

        try:
            data["inner_text"] = self.driver.execute_script(
                "return (arguments[0].innerText || '').trim();",
                card,
            ) or ""
        except Exception:
            pass

        try:
            data["text_content"] = self.driver.execute_script(
                "return (arguments[0].textContent || '').trim();",
                card,
            ) or ""
        except Exception:
            pass

        lines = []
        seen = set()

        for raw in self._split_lines(data["inner_text"]) + self._split_lines(data["text_content"]):
            cleaned = self._normalize_line(raw)
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            lines.append(cleaned)

        data["lines"] = lines
        return data

    def _extract_listing_name(self, card_data):
        lines = card_data["lines"]

        # 1) Optimalfall:
        #    "Zimmer in St. Gallen" -> nächste sinnvolle Zeile = echter Name
        for idx, line in enumerate(lines):
            if self._looks_like_type_location_line(line):
                for next_line in lines[idx + 1:]:
                    if self._is_valid_listing_name(next_line):
                        return next_line

        # 2) Fallback:
        #    nimm die erste sinnvolle Zeile, die kein Typ/Ort ist
        for line in lines:
            if self._is_valid_listing_name(line):
                return line

        return None

    def _extract_total_price_info(self, card_data):
        lines = card_data["lines"]

        # 1) Bevorzugt Zeilen mit "Gesamtpreis"
        total_lines = [line for line in lines if "gesamtpreis" in line.lower() and "chf" in line.lower()]

        # 2) Dann CHF-Zeilen mit Wörter wie "für", "Nächte", "gesamt"
        secondary_lines = [
            line for line in lines
            if "chf" in line.lower() and (
                "für" in line.lower()
                or "nacht" in line.lower()
                or "nächte" in line.lower()
                or "gesamt" in line.lower()
            )
        ]

        # 3) Letzter Fallback: beliebige CHF-Zeilen
        fallback_lines = [line for line in lines if "chf" in line.lower()]

        candidate_groups = [total_lines, secondary_lines, fallback_lines]

        for group in candidate_groups:
            if not group:
                continue

            best_line = self._pick_best_price_line(group)
            best_price = self._extract_best_price_from_line(best_line)

            if best_price is not None:
                return {
                    "total_price": best_price,
                    "currency": "CHF",
                    "displayed_price_text": best_line,
                }

        return {
            "total_price": None,
            "currency": None,
            "displayed_price_text": None,
        }

    def _pick_best_price_line(self, lines):
        # Bevorzuge "Gesamtpreis", dann Zeilen mit höherem CHF-Betrag
        scored = []

        for line in lines:
            lower = line.lower()
            amounts = self._extract_all_amounts(line)
            max_amount = max(amounts) if amounts else 0

            score = 0
            if "gesamtpreis" in lower:
                score += 1000
            if "gesamt" in lower:
                score += 100
            if "für" in lower and ("nacht" in lower or "nächte" in lower):
                score += 50
            if "chf" in lower:
                score += 10

            score += max_amount
            scored.append((score, line))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _extract_best_price_from_line(self, line):
        amounts = self._extract_all_amounts(line)
        if not amounts:
            return None

        lower = line.lower()

        # In einer Zeile wie "628 CHF 436 CHF Gesamtpreis"
        # soll 436 genommen werden, also der Betrag direkt vor "Gesamtpreis".
        if "gesamtpreis" in lower:
            before_total = re.search(
                r"([0-9]{1,3}(?:['’\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)\s*CHF\s*Gesamtpreis",
                line,
                flags=re.IGNORECASE,
            )
            if before_total:
                parsed = self._normalize_price_number(before_total.group(1))
                if parsed is not None:
                    return parsed

            after_total = re.search(
                r"Gesamtpreis\s*[:\-]?\s*CHF\s*([0-9]{1,3}(?:['’\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)",
                line,
                flags=re.IGNORECASE,
            )
            if after_total:
                parsed = self._normalize_price_number(after_total.group(1))
                if parsed is not None:
                    return parsed

            # Falls Gesamtpreis in derselben Zeile ist, aber nicht direkt matcht:
            # nimm den letzten CHF-Betrag der Zeile.
            return amounts[-1]

        # Sonst bei mehreren Beträgen den letzten/höher priorisierten nehmen
        return amounts[-1]

    def _extract_all_amounts(self, text):
        if not text:
            return []

        pattern = re.compile(
            r"""
            (?:
                CHF\s*
                (?P<after>[0-9]{1,3}(?:['’\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)
            )
            |
            (?:
                (?P<before>[0-9]{1,3}(?:['’\s.,][0-9]{3})*(?:[.,][0-9]{1,2})?)
                \s*CHF
            )
            """,
            flags=re.IGNORECASE | re.VERBOSE,
        )

        amounts = []
        for match in pattern.finditer(text):
            raw_value = match.group("after") or match.group("before")
            normalized = self._normalize_price_number(raw_value)
            if normalized is not None:
                amounts.append(normalized)

        return amounts

    def _looks_like_type_location_line(self, text):
        lower = text.lower().strip()

        prefixes = [
            "zimmer in ",
            "wohnung in ",
            "unterkunft in ",
            "apartment in ",
            "ferienunterkunft in ",
            "loft in ",
            "haus in ",
            "studio in ",
            "privatzimmer in ",
            "hotelzimmer in ",
            "tiny house in ",
            "room in ",
            "home in ",
            "house in ",
        ]
        return any(lower.startswith(prefix) for prefix in prefixes)

    def _is_valid_listing_name(self, text):
        if not text:
            return False

        lower = text.lower()

        if len(text) < 4:
            return False

        if re.fullmatch(r"\d+(?:[.,]\d+)?", text):
            return False

        if not re.search(r"[A-Za-zÄÖÜäöüÀ-ÿ]", text):
            return False

        if self._looks_like_type_location_line(text):
            return False

        blocked_exact = {
            "Gäste-Favorit",
            "Beliebter Gäste-Favorit",
            "Superhost",
            "Neu",
            "Wishlist",
        }
        if text in blocked_exact:
            return False

        blocked_contains = [
            "gesamtpreis",
            "chf",
            "bewertung",
            "bewertungen",
            "rezension",
            "rezensionen",
            "schlafzimmer",
            "schlafzimmern",
            "bett",
            "betten",
            "bad",
            "bäder",
            "gastgeber",
            "kostenlose stornierung",
            "zahle heute",
            "nacht",
            "nächte",
            "gäste-favorit",
            "superhost",
        ]
        if any(token in lower for token in blocked_contains):
            return False

        if re.search(r"\d+[.,]\d+\s*\(\d+\)", text):
            return False

        return True

    def _go_to_next_results_page(self):
        old_url = self.driver.current_url
        old_source = self.driver.page_source

        next_button_xpaths = [
            '//a[@rel="next"]',
            '//button[@rel="next"]',
            '//a[contains(@aria-label, "Nächste")]',
            '//a[contains(@aria-label, "Weiter")]',
            '//a[contains(@aria-label, "Next")]',
            '//button[contains(@aria-label, "Nächste")]',
            '//button[contains(@aria-label, "Weiter")]',
            '//button[contains(@aria-label, "Next")]',
            '//a[normalize-space(text())=">"]',
            '//button[normalize-space(text())=">"]',
            '//a[normalize-space(text())="›"]',
            '//button[normalize-space(text())="›"]',
            '//a[normalize-space(text())="→"]',
            '//button[normalize-space(text())="→"]',
        ]

        for xpath in next_button_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        if not element.is_displayed() or not element.is_enabled():
                            continue

                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            element,
                        )
                        time.sleep(1)

                        try:
                            element.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", element)

                        try:
                            WebDriverWait(self.driver, 12).until(
                                lambda d: d.current_url != old_url or d.page_source != old_source
                            )
                        except TimeoutException:
                            pass

                        time.sleep(3)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        return False

    def _normalize_line(self, text):
        text = self._clean_text(text)
        if not text:
            return None

        text = re.sub(r"\s*[·•|]\s*", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        # störende UI-Texte etwas glätten
        text = re.sub(r"\bPreisaufschlüsselung anzeigen\b", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\bWishlist\b", "", text, flags=re.IGNORECASE).strip()

        return self._clean_text(text)

    @staticmethod
    def _split_lines(value):
        if not value:
            return []

        raw_lines = re.split(r"[\n\r]+", value)
        cleaned_lines = []

        for line in raw_lines:
            line = re.sub(r"\s+", " ", str(line)).strip()
            if line:
                cleaned_lines.append(line)

        return cleaned_lines

    @staticmethod
    def _normalize_price_number(raw_value):
        if raw_value is None:
            return None

        normalized = str(raw_value).strip()
        normalized = (
            normalized
            .replace("’", "")
            .replace("'", "")
            .replace("\u00A0", "")
            .replace(" ", "")
        )

        if "," in normalized and "." in normalized:
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")
        elif normalized.count(",") == 1 and len(normalized.split(",")[-1]) in (1, 2):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")

        try:
            value = float(normalized)
            if value.is_integer():
                return int(value)
            return value
        except ValueError:
            return None

    @staticmethod
    def _clean_text(value):
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        return cleaned if cleaned else None

    def closed(self, reason):
        if getattr(self, "driver", None):
            self.driver.quit()