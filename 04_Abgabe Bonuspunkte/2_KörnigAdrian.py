from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urlencode, urljoin

import scrapy
from scrapy import Selector
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from airbnb_stgallen.helpers.parsing import first_non_empty_text, normalize_price
from airbnb_stgallen.helpers.selenium_utils import (
    build_chrome_driver,
    dismiss_cookie_banner,
    small_human_pause,
)
from airbnb_stgallen.items import AirbnbListingItem


class AirbnbStGallenSpider(scrapy.Spider):
    name = "airbnb_stgallen"
    allowed_domains = ["airbnb.ch", "www.airbnb.ch"]
    start_urls = ["https://www.airbnb.ch/"]

    EVENTS = [
        {
            "event_name": "OpenAir St. Gallen",
            "checkin_date": "2026-06-25",
            "checkout_date": "2026-06-28",
        },
        {
            "event_name": "OLMA",
            "checkin_date": "2026-10-08",
            "checkout_date": "2026-10-18",
        },
    ]

    LISTING_CARD_XPATH = (
        "//div[@itemprop='itemListElement']"
        " | //div[@data-testid='card-container']"
        " | //article[.//a[contains(@href, '/rooms/')]]"
    )

    def __init__(
        self,
        *args,
        listing_limit: int = 100,
        combined_output: str | None = None,
        event_output_dir: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.listing_limit = int(listing_limit or os.getenv("AIRBNB_LISTING_LIMIT", "100"))
        self.combined_output = combined_output
        self.event_output_dir = event_output_dir
        self.max_event_retries = int(os.getenv("AIRBNB_MAX_EVENT_RETRIES", "3"))
        self.max_scrolls = int(os.getenv("AIRBNB_MAX_SCROLLS", "80"))
        self.max_stalled_scrolls = int(os.getenv("AIRBNB_MAX_STALLED_SCROLLS", "6"))
        self.max_scrolls_per_page = int(os.getenv("AIRBNB_MAX_SCROLLS_PER_PAGE", "10"))
        self.max_stalled_scrolls_per_page = int(os.getenv("AIRBNB_MAX_STALLED_SCROLLS_PER_PAGE", "2"))
        self.scroll_pause_min = float(os.getenv("AIRBNB_SCROLL_PAUSE_MIN", "1.2"))
        self.scroll_pause_max = float(os.getenv("AIRBNB_SCROLL_PAUSE_MAX", "2.4"))
        self.headless = os.getenv("AIRBNB_HEADLESS", "true").lower() == "true"
        self._driver = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        if spider.combined_output:
            crawler.settings.set(
                "FEEDS",
                {
                    spider.combined_output: {
                        "format": "csv",
                        "encoding": "utf8",
                        "overwrite": True,
                    }
                },
                priority="spider",
            )
        if spider.event_output_dir:
            crawler.settings.set("EVENT_OUTPUT_DIR", spider.event_output_dir, priority="spider")
        return spider

    def parse(self, response, **kwargs):
        for event in self.EVENTS:
            yield from self._collect_event_listings(event)

    def closed(self, reason):
        if self._driver:
            self._driver.quit()
            self._driver = None

    def _collect_event_listings(self, event: Dict[str, str]) -> Iterable[AirbnbListingItem]:
        event_name = event["event_name"]
        checkin_date = event["checkin_date"]
        checkout_date = event["checkout_date"]
        source_url = self._build_search_url(checkin_date, checkout_date)

        for attempt in range(1, self.max_event_retries + 1):
            try:
                self.logger.info(
                    "Event '%s': attempt %s/%s, loading %s",
                    event_name,
                    attempt,
                    self.max_event_retries,
                    source_url,
                )
                self._ensure_driver()
                self._driver.get(source_url)
                dismiss_cookie_banner(self._driver)
                self._wait_for_initial_cards()
                items = self._collect_paginated_items(
                    event_name=event_name,
                    checkin_date=checkin_date,
                    checkout_date=checkout_date,
                )
                self.logger.info(
                    "Event '%s': extracted %s listings (target=%s)",
                    event_name,
                    len(items),
                    self.listing_limit,
                )
                for item in items:
                    yield item
                return
            except Exception as exc:
                self.logger.warning(
                    "Event '%s': attempt %s failed: %s",
                    event_name,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if attempt == self.max_event_retries:
                    self.logger.error(
                        "Event '%s': all retries failed. Skipping this event.",
                        event_name,
                    )
                else:
                    self._recreate_driver()

    def _collect_paginated_items(
        self,
        event_name: str,
        checkin_date: str,
        checkout_date: str,
    ) -> List[AirbnbListingItem]:
        results: List[AirbnbListingItem] = []
        seen_urls: Set[str] = set()
        scraped_at = datetime.now(timezone.utc).isoformat()
        page_number = 1

        while len(results) < self.listing_limit:
            self.logger.info(
                "Event '%s': processing page %s (collected=%s/%s)",
                event_name,
                page_number,
                len(results),
                self.listing_limit,
            )
            self._scroll_until_limit(
                max_scrolls_override=self.max_scrolls_per_page,
                max_stalled_scrolls_override=self.max_stalled_scrolls_per_page,
            )
            page_source = self._driver.page_source
            new_items = self._extract_items_from_html(
                page_source=page_source,
                event_name=event_name,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                seen_urls=seen_urls,
                start_rank=len(results) + 1,
                scraped_at=scraped_at,
            )

            if new_items:
                results.extend(new_items)
                self.logger.info(
                    "Event '%s': page %s added %s unique listings (total=%s)",
                    event_name,
                    page_number,
                    len(new_items),
                    len(results),
                )
                if len(results) >= self.listing_limit:
                    break

            if not self._go_to_next_results_page(expected_current_page=page_number):
                self.logger.info(
                    "Event '%s': no further results page found after page %s",
                    event_name,
                    page_number,
                )
                break
            page_number += 1

        return results[: self.listing_limit]

    def _build_search_url(self, checkin_date: str, checkout_date: str) -> str:
        params = {
            "query": "St. Gallen, Switzerland",
            "checkin": checkin_date,
            "checkout": checkout_date,
            "adults": 1,
            "source": "structured_search_input_header",
            "search_type": "autocomplete_click",
            "price_filter_input_type": 0,
            "channel": "EXPLORE",
        }
        return f"https://www.airbnb.ch/s/St.-Gallen--Switzerland/homes?{urlencode(params)}"

    def _wait_for_initial_cards(self) -> None:
        wait = WebDriverWait(self._driver, 25)
        wait.until(EC.presence_of_element_located((By.XPATH, self.LISTING_CARD_XPATH)))

    def _scroll_until_limit(
        self,
        max_scrolls_override: Optional[int] = None,
        max_stalled_scrolls_override: Optional[int] = None,
    ) -> None:
        seen = 0
        stalled_rounds = 0
        previous_height = self._driver.execute_script("return document.body.scrollHeight")
        max_scrolls = max_scrolls_override if max_scrolls_override is not None else self.max_scrolls
        max_stalled = (
            max_stalled_scrolls_override
            if max_stalled_scrolls_override is not None
            else self.max_stalled_scrolls
        )

        for _ in range(max_scrolls):
            current_count = self._count_visible_listing_cards(self._driver.page_source)
            if current_count >= self.listing_limit:
                break

            self._driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            small_human_pause(self.scroll_pause_min, self.scroll_pause_max)

            try:
                WebDriverWait(self._driver, 8).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") > previous_height
                    or self._count_visible_listing_cards(d.page_source) > current_count
                )
            except TimeoutException:
                pass

            new_height = self._driver.execute_script("return document.body.scrollHeight")
            new_count = self._count_visible_listing_cards(self._driver.page_source)

            if new_height == previous_height and new_count <= seen:
                stalled_rounds += 1
            else:
                stalled_rounds = 0

            seen = max(seen, new_count)
            previous_height = new_height
            if stalled_rounds >= max_stalled:
                break

    def _count_visible_listing_cards(self, html: str) -> int:
        selector = Selector(text=html)
        cards = selector.xpath(self.LISTING_CARD_XPATH)
        return len(cards)

    def _extract_items_from_html(
        self,
        page_source: str,
        event_name: str,
        checkin_date: str,
        checkout_date: str,
        seen_urls: Set[str],
        start_rank: int,
        scraped_at: str,
    ) -> List[AirbnbListingItem]:
        selector = Selector(text=page_source)
        cards = selector.xpath(self.LISTING_CARD_XPATH)

        results: List[AirbnbListingItem] = []

        for card in cards:
            if start_rank + len(results) - 1 >= self.listing_limit:
                break

            listing_relative_url = first_non_empty_text(
                card,
                [
                    ".//a[contains(@href, '/rooms/')][1]/@href",
                    ".//a[contains(@href, '/rooms')][1]/@href",
                ],
            )
            source_url = (
                urljoin("https://www.airbnb.ch", listing_relative_url) if listing_relative_url else ""
            )
            if source_url and source_url in seen_urls:
                continue
            if source_url:
                seen_urls.add(source_url)

            listing_name = first_non_empty_text(
                card,
                [
                    ".//div[@data-testid='listing-card-title']//text()",
                    ".//meta[@itemprop='name']/@content",
                    ".//h3//text()",
                    ".//h2//text()",
                    ".//a[contains(@href, '/rooms')][1]/@aria-label",
                ],
            )

            price_raw = first_non_empty_text(
                card,
                [
                    ".//*[@data-testid='price-availability-row']//text()",
                    ".//*[contains(text(), 'CHF')]/text()",
                    ".//*[contains(text(), 'Fr')]/text()",
                    ".//*[contains(text(), 'EUR')]/text()",
                    ".//*[contains(text(), 'USD')]/text()",
                    ".//*[contains(text(), '$')]/text()",
                ],
            )

            price_value, currency = normalize_price(price_raw)
            rank = start_rank + len(results)

            item = AirbnbListingItem(
                event_name=event_name,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                listing_rank=rank,
                listing_name=listing_name,
                price_per_night_raw=price_raw,
                price_per_night_value=price_value,
                currency=currency,
                source_url=source_url,
                scraped_at=scraped_at,
            )
            results.append(item)

        return results

    def _go_to_next_results_page(self, expected_current_page: int) -> bool:
        prev_url = self._driver.current_url
        next_page = expected_current_page + 1

        if self._click_page_number(next_page, prev_url):
            return True
        if self._click_next_arrow(prev_url):
            return True
        return False

    def _click_page_number(self, target_page: int, prev_url: str) -> bool:
        page_str = str(target_page)
        page_num_xpaths = [
            f"//nav//*[self::a or self::button][normalize-space(text())='{page_str}']",
            f"//button[@aria-label='{page_str}' or contains(@aria-label, 'Seite {page_str}') or contains(@aria-label, 'Page {page_str}')]",
            f"//a[@aria-label='{page_str}' or contains(@aria-label, 'Seite {page_str}') or contains(@aria-label, 'Page {page_str}')]",
        ]

        for xpath in page_num_xpaths:
            try:
                elem = WebDriverWait(self._driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self._safe_click(elem)
                if self._wait_for_page_change(prev_url, target_page=target_page):
                    return True
            except TimeoutException:
                continue
            except (ElementClickInterceptedException, ElementNotInteractableException):
                continue

        return False

    def _click_next_arrow(self, prev_url: str) -> bool:
        next_arrow_xpaths = [
            "//nav//*[self::a or self::button][contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'next')]",
            "//nav//*[self::a or self::button][contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ','abcdefghijklmnopqrstuvwxyzäöü'), 'weiter')]",
            "//nav//*[self::a or self::button][contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ','abcdefghijklmnopqrstuvwxyzäöü'), 'nächste')]",
            "//nav//*[self::a or self::button][contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ','abcdefghijklmnopqrstuvwxyzäöü'), 'naechste')]",
            "//nav//*[self::a or self::button][@data-testid='pagination-next-button']",
        ]

        for xpath in next_arrow_xpaths:
            try:
                elem = WebDriverWait(self._driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self._safe_click(elem)
                if self._wait_for_page_change(prev_url, target_page=None):
                    return True
            except TimeoutException:
                continue
            except (ElementClickInterceptedException, ElementNotInteractableException):
                continue

        return False

    def _wait_for_page_change(self, prev_url: str, target_page: Optional[int]) -> bool:
        try:
            WebDriverWait(self._driver, 12).until(
                lambda d: d.current_url != prev_url
                or self._get_active_page_number() == target_page
                or self._url_page_index(d.current_url) != self._url_page_index(prev_url)
            )
            self._wait_for_initial_cards()
            return True
        except TimeoutException:
            return False

    def _get_active_page_number(self) -> Optional[int]:
        active_xpaths = [
            "//nav//*[(@aria-current='page' or @aria-selected='true') and (self::a or self::button)]",
            "//nav//*[contains(@class,'active') and (self::a or self::button)]",
        ]
        for xpath in active_xpaths:
            try:
                elem = self._driver.find_element(By.XPATH, xpath)
                text = (elem.text or "").strip()
                if text.isdigit():
                    return int(text)
            except NoSuchElementException:
                continue
            except Exception:
                continue
        return None

    @staticmethod
    def _url_page_index(url: str) -> Optional[int]:
        match = re.search(r"(?:items_offset|pagination_searching_offset)=(\d+)", url)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _safe_click(self, element) -> None:
        try:
            self._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except Exception:
            pass
        try:
            element.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            self._driver.execute_script("arguments[0].click();", element)

    def _ensure_driver(self) -> None:
        if self._driver is None:
            self._driver = build_chrome_driver(headless=self.headless)

    def _recreate_driver(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
            except WebDriverException:
                pass
        self._driver = build_chrome_driver(headless=self.headless)
