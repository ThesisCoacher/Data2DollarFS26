import scrapy
import json
import pandas as pd

class GetdataSpider(scrapy.Spider):
    name = "getdata"
    allowed_domains = ["www.airbnb.ch"]

    # OLMA URLs (6 Seiten)
    start_urls = [
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&search_mode=regular_search&location_bb=Qj4gt0EYfyBCPZSjQRNmOA%3D%3D&source=structured_search_input_header&search_type=autocomplete_click",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&source=structured_search_input_header&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&federated_search_session_id=87be7f09-bbd2-41f3-91e3-b22cf5fd0d9f&pagination_search=true&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxOCwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&source=structured_search_input_header&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=87be7f09-bbd2-41f3-91e3-b22cf5fd0d9f&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjozNiwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&source=structured_search_input_header&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=87be7f09-bbd2-41f3-91e3-b22cf5fd0d9f&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo1NCwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&source=structured_search_input_header&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=87be7f09-bbd2-41f3-91e3-b22cf5fd0d9f&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo3MiwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&date_picker_type=calendar&adults=1&flexible_trip_lengths%5B%5D=one_week&price_filter_input_type=2&price_filter_num_nights=10&channel=EXPLORE&monthly_start_date=2026-04-01&monthly_end_date=2026-07-01&monthly_length=3&checkin=2026-10-08&checkout=2026-10-18&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&source=structured_search_input_header&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=87be7f09-bbd2-41f3-91e3-b22cf5fd0d9f&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo5MCwidmVyc2lvbiI6MX0%3D"
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
        },
        'DOWNLOAD_DELAY': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listings = []

    def _find_search_results(self, obj):
        """Rekursiv nach searchResults-Array suchen."""
        if isinstance(obj, dict):
            if "searchResults" in obj and isinstance(obj["searchResults"], list):
                return obj["searchResults"]
            for v in obj.values():
                result = self._find_search_results(v)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_search_results(item)
                if result is not None:
                    return result
        return None

    def parse(self, response):
        self.logger.info(f"Parsing: {response.url[:80]}... (Status: {response.status})")

        script_data = response.css('script#data-deferred-state-0::text').get()
        if not script_data:
            self.logger.warning(f"Kein data-deferred-state-0 gefunden auf: {response.url[:80]}")
            return

        try:
            data = json.loads(script_data)
        except json.JSONDecodeError:
            self.logger.warning("JSON konnte nicht geparst werden")
            return

        search_results = self._find_search_results(data)
        if not search_results:
            self.logger.warning("Keine searchResults im JSON gefunden")
            return

        count = 0
        for result in search_results:
            if result.get("__typename") != "StaySearchResult":
                continue

            # Name: nameLocalized.localizedStringWithTranslationPreference
            name = ""
            name_loc = result.get("nameLocalized")
            if name_loc:
                name = name_loc.get("localizedStringWithTranslationPreference", "")
            if not name:
                # Fallback: demandStayListing.description.name
                dsl = result.get("demandStayListing", {})
                desc = dsl.get("description", {})
                name_obj = desc.get("name", {})
                if isinstance(name_obj, dict):
                    name = name_obj.get("localizedStringWithTranslationPreference", "")

            # Preis: structuredDisplayPrice.primaryLine
            price = ""
            sdp = result.get("structuredDisplayPrice", {})
            primary = sdp.get("primaryLine", {})
            typename = primary.get("__typename", "")
            if "Discounted" in typename:
                price = primary.get("discountedPrice", "")
            else:
                price = primary.get("price", "")

            if name and price:
                self.listings.append({
                    'name': name,
                    'price': price,
                    'event': 'OLMA'
                })
                count += 1

        self.logger.info(f"Extrahiert: {count} Listings auf dieser Seite")

    def closed(self, reason):
        try:
            existing_df = pd.read_csv('airbnb_stgallen.csv')
            if 'event' in existing_df.columns:
                oasg_df = existing_df[existing_df['event'] == 'OASG'].copy()
            else:
                oasg_df = existing_df.copy()
                oasg_df['event'] = 'OASG'
        except FileNotFoundError:
            oasg_df = pd.DataFrame()

        olma_df = pd.DataFrame(self.listings)
        combined_df = pd.concat([oasg_df, olma_df], ignore_index=True)
        combined_df.to_csv('airbnb_stgallen.csv', index=False)
        self.logger.info(f"Gespeichert: {len(oasg_df)} OASG + {len(olma_df)} OLMA = {len(combined_df)} total")
