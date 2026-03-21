"""
Airbnb Multi-URL Scraper für St. Gallen
Scraps alle URLs und speichert Ergebnisse in eine CSV
"""

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def scrape_airbnb_listings(driver, url):
    """Scrapes a single Airbnb URL for names and prices"""
    
    print(f"\n  Loading URL (with cursor)...")
    driver.get(url)
    
    print(f"  Waiting for page load...")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="listing-card-name"]'))
        )
    except:
        print(f"  ⚠ Timeout waiting for listings")
        return []
    
    time.sleep(2)
    print(f"  ✓ Page loaded")

    listings = []
    scroll_count = 0
    max_scrolls = 15
    plateaus = 0

    while scroll_count < max_scrolls:
        # Get name elements
        name_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="listing-card-name"]')
        # Get price elements
        price_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="price-availability-row"] .u1opajno')
        
        existing = {l['name'] for l in listings}
        added = 0
        
        # Match names and prices
        for i in range(min(len(name_elements), len(price_elements))):
            name = name_elements[i].text.strip()
            price = price_elements[i].text.strip()
            
            if name and price and name not in existing:
                listings.append({'name': name, 'price': price})
                existing.add(name)
                added += 1
        
        if added == 0:
            plateaus += 1
            if plateaus >= 2:
                print(f"  Extracted: {len(listings)} listings")
                break
        else:
            plateaus = 0
            print(f"  +{added} listings (total: {len(listings)})")
        
        # Scroll
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(2)
        scroll_count += 1
    
    return listings

def scrape_all_urls(urls):
    """Scrapes all URLs and combines results"""
    
    print("\n" + "="*80)
    print("AIRBNB MULTI-URL SCRAPER - ST. GALLEN")
    print("="*80)
    
    # Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        all_listings = []
        
        for idx, url in enumerate(urls, 1):
            print(f"\n[{idx}/{len(urls)}] Scraping page...")
            
            page_listings = scrape_airbnb_listings(driver, url)
            all_listings.extend(page_listings)
            
            if idx < len(urls):
                time.sleep(2)  # Delay between pages
        
        # Remove duplicates by name
        seen = set()
        unique_listings = []
        for listing in all_listings:
            if listing['name'] not in seen:
                unique_listings.append(listing)
                seen.add(listing['name'])
        
        print("\n" + "="*80)
        print(f"✓ COMPLETE: {len(unique_listings)} unique listings")
        print("="*80 + "\n")
        
        return unique_listings

    finally:
        driver.quit()

def save_to_csv(listings, filename='airbnb_listings_combined.csv'):
    """Save to CSV"""
    if not listings:
        print("No listings to save")
        return
    
    df = pd.DataFrame(listings)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"✓ Saved: {filename}\n")

if __name__ == "__main__":
    urls = [
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjowLCJ2ZXJzaW9uIjoxfQ%3D%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxOCwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjozNiwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo1NCwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo3MiwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0Ijo5MCwidmVyc2lvbiI6MX0%3D",
        "https://www.airbnb.ch/s/St.-Gallen/homes?refinement_paths%5B%5D=%2Fhomes&acp_id=9fe5b8a4-1a6e-42b5-8cfa-a6262680585a&date_picker_type=calendar&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2026-04-01&monthly_length=3&monthly_end_date=2026-07-01&price_filter_input_type=2&channel=EXPLORE&checkin=2026-10-08&checkout=2026-10-18&source=structured_search_input_header&price_filter_num_nights=10&zoom_level=11&query=St.%20Gallen&place_id=ChIJoR85ryDimkcRmxnF_e9vd4A&pagination_search=true&federated_search_session_id=14617e07-a8ef-4f84-a9a8-3e5219760b9e&cursor=eyJzZWN0aW9uX29mZnNldCI6MCwiaXRlbXNfb2Zmc2V0IjoxMDgsInZlcnNpb24iOjF9",
    ]
    
    listings = scrape_all_urls(urls)
    save_to_csv(listings)
