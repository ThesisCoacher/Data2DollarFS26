# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import csv
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import certifi
import requests


class BionetzchPipeline:
    """Export scraped items to a CSV file and enrich with geocoding (lat/lon).

    Output:
      - stores_raw.csv  (raw + enrichment columns)
      - geocode_cache.json (persistent cache to avoid repeated lookups)

    Notes:
      - Nominatim has usage policies (rate limiting, identifying User-Agent). Keep requests low.
      - This pipeline applies a conservative delay between *uncached* geocoding calls.
      - If your network blocks HTTPS interception (common on corp Wi-Fi/VPN), you may still see
        SSL errors; see README notes / environment fixes.
    """

    # Conservative delay for uncached calls (seconds). Increase if you hit 429/usage limits.
    GEOCODE_DELAY_S = 1.2

    # Nominatim endpoint
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

    def open_spider(self, spider):
        self.file_path = os.path.join(os.getcwd(), "stores_raw.csv")
        self.file = open(self.file_path, "w", newline="", encoding="utf-8")
        self.writer = None

        # Cache file so re-runs don't hammer the API
        self.cache_path = os.path.join(os.getcwd(), "geocode_cache.json")
        self.cache: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f) or {}
            except Exception:
                # If cache is corrupted, start fresh (do not crash the crawl)
                self.cache = {}

        # Track last uncached call time for rate limiting
        self._last_call_ts = 0.0

        # Identify your requests (recommended by Nominatim).
        # Optionally set via settings: NOMINATIM_USER_AGENT
        ua = getattr(spider.settings, "get", lambda k, d=None: d)("NOMINATIM_USER_AGENT", None)
        self.user_agent = ua or "bionetzch-scraper/1.0 (contact: add-your-email)"

    def close_spider(self, spider):
        # Persist cache
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if hasattr(self, "file") and not self.file.closed:
            self.file.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Build geocode query from whatever fields exist
        query = self._build_geocode_query(adapter)

        lat, lon, status = None, None, "skipped"
        if query:
            lat, lon, status = self._geocode_with_cache(query)

        # Add enrichment columns (always present)
        adapter["geocode_query"] = query or ""
        adapter["geocode_status"] = status
        adapter["lat"] = lat if lat is not None else ""
        adapter["lon"] = lon if lon is not None else ""

        # Initialize writer with header on first item
        if self.writer is None:
            fieldnames = list(adapter.keys())
            # Ensure deterministic order for the enrichment fields at the end
            for extra in ["geocode_query", "geocode_status", "lat", "lon"]:
                if extra not in fieldnames:
                    fieldnames.append(extra)
            self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
            self.writer.writeheader()

        self.writer.writerow(adapter.asdict())
        return item

    def _build_geocode_query(self, adapter: ItemAdapter) -> Optional[str]:
        """Create a robust geocoding query from common field names.

        Tries multiple variants (DE/FR/EN) because the scraped data may not be uniform.
        """

        def pick(*keys: str) -> str:
            for k in keys:
                v = adapter.get(k)
                if v is None:
                    continue
                v = str(v).strip()
                if v:
                    return v
            return ""

        # Common patterns
        name = pick("name", "Name", "title", "Titel", "store", "shop")
        street = pick("street", "Street", "strasse", "Strasse", "Straße", "adresse", "Adresse", "address", "Address")
        zip_code = pick("zip", "ZIP", "plz", "PLZ", "postcode", "Postcode")
        city = pick("city", "City", "ort", "Ort", "ville", "Ville")
        canton = pick("canton", "Canton", "kanton", "Kanton")

        # If we have nothing usable, skip
        if not any([street, zip_code, city, canton, name]):
            return None

        parts = []
        # Prefer precise address; otherwise fall back to city
        if street:
            parts.append(street)
        if zip_code:
            parts.append(zip_code)
        if city:
            parts.append(city)
        elif canton:
            parts.append(canton)

        # Safety: if only name is present, do not geocode (too ambiguous)
        if not any([street, zip_code, city, canton]) and name:
            return None

        # Constrain to Switzerland
        parts.append("Switzerland")

        return ", ".join([p for p in parts if p])

    def _geocode_with_cache(self, query: str) -> Tuple[Optional[float], Optional[float], str]:
        # Cache hit
        if query in self.cache:
            hit = self.cache[query]
            lat = hit.get("lat")
            lon = hit.get("lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon), "cached"
            return None, None, hit.get("status", "cached-miss")

        # Rate limit (only for uncached calls)
        now = time.time()
        delta = now - self._last_call_ts
        if delta < self.GEOCODE_DELAY_S:
            time.sleep(self.GEOCODE_DELAY_S - delta)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            # Slight bias to Switzerland results, while still using free text
            "countrycodes": "ch",
        }

        try:
            resp = requests.get(
                self.NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=20,
                verify=certifi.where(),
            )
            self._last_call_ts = time.time()

            if resp.status_code == 429:
                # Too many requests
                self.cache[query] = {"status": "rate-limited"}
                return None, None, "rate-limited"

            resp.raise_for_status()
            data = resp.json() or []
            if not data:
                self.cache[query] = {"status": "not-found"}
                return None, None, "not-found"

            lat = float(data[0].get("lat"))
            lon = float(data[0].get("lon"))
            self.cache[query] = {"lat": lat, "lon": lon, "status": "ok"}
            return lat, lon, "ok"

        except requests.exceptions.SSLError:
            # Network/cert issue: store as miss so we don't loop forever
            self.cache[query] = {"status": "ssl-error"}
            return None, None, "ssl-error"
        except Exception:
            self.cache[query] = {"status": "error"}
            return None, None, "error"
