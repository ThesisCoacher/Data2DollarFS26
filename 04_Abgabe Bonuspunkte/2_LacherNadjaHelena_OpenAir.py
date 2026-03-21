import time
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def scrape_url(driver, url):
    """Scrape single URL and return listings"""
    try:
        print(f"Loading URL...")
        driver.get(url)
        
        # Wait for listings to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="listing-card-name"]'))
        )
        time.sleep(3)
        
        # Scroll to load all listings
        for i in range(5):
            driver.execute_script("window.scrollBy(0, 2500);")
            time.sleep(2)
        
        # Extract listings
        name_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="listing-card-name"]')
        print(f"  Found {len(name_elements)} listings on this page")
        
        listings = []
        for name_elem in name_elements:
            try:
                name = name_elem.text.strip()
                
                # Find price
                price = ""
                parent = name_elem
                for _ in range(10):
                    try:
                        parent = parent.find_element(By.XPATH, "..")
                        all_spans = parent.find_elements(By.XPATH, ".//span")
                        for span in all_spans:
                            text = span.text.strip()
                            if 'CHF' in text:
                                match = re.search(r'(\d+[\d\'\.]*)\s*CHF', text)
                                if match:
                                    price = match.group(0) + " CHF"
                                    break
                        if price:
                            break
                    except:
                        break
                
                if price:
                    listings.append({'name': name, 'price': price})
            except:
                continue
        
        return listings
        
    except Exception as e:
        print(f"  Error: {e}")
        return []

# URLs to scrape
urls = [
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjowLCJ2ZXJzaW9uIjoxfQ%3D%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxOCwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjozNiwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo1NCwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo3MiwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo5MCwidmVyc2lvbiI6MX0%3D",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMDgsInZlcnNpb24iOjF9",
    "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-06-25&checkout=2026-06-28&source=structured_search_input_header&price_filter_num_nights=3&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=05150688-cd88-479e-9664-965eba90d7e2&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMjYsInZlcnNpb24iOjF9",
]

print("="*80)
print("AIRBNB ST. GALLEN SCRAPER - MULTI-PAGE")
print("="*80)

# Initialize Chrome
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--start-maximized')
options.add_argument('--disable-gpu')

try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
except:
    print("Chrome failed, trying Edge...")
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    from selenium.webdriver.edge.service import Service as EdgeService
    service = EdgeService(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=webdriver.EdgeOptions())

try:
    all_listings = []
    seen_names = set()
    
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}] Scraping page {idx}...")
        page_listings = scrape_url(driver, url)
        
        # Add only new listings
        for listing in page_listings:
            if listing['name'] not in seen_names:
                all_listings.append(listing)
                seen_names.add(listing['name'])
        
        print(f"  Added {len([l for l in page_listings if l['name'] in seen_names])} new listings")
        time.sleep(2)  # Wait between requests
    
    # Save to CSV
    print(f"\n{'='*80}")
    print(f"✓ TOTAL: {len(all_listings)} unique listings extracted")
    print(f"{'='*80}")
    
    if all_listings:
        df = pd.DataFrame(all_listings)
        csv_filename = 'airbnb_listings_stgallen_complete.csv'
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n✓ Saved to: {csv_filename}")
        print(f"  Rows: {len(df)} listings + 1 header\n")
    else:
        print("\nNo listings found!")

finally:
    driver.quit()
