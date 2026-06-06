import requests
import os
from dotenv import load_dotenv
from db import get_db

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def find_businesses(city, business_type):
    print(f"Searching for '{business_type}' in '{city}'...")
    query = f"{business_type} in {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    results = []
    params = {"query": query, "key": API_KEY}
    while True:
        response = requests.get(url, params=params).json()
        for place in response.get("results", []):
            place_id = place.get("place_id")
            details = get_place_details(place_id)
            results.append({
                "name":    place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "phone":   details.get("phone", ""),
                "website": details.get("website", ""),
                "email":   "",
            })
        next_page_token = response.get("next_page_token")
        if not next_page_token:
            break
        import time; time.sleep(2)
        params = {"pagetoken": next_page_token, "key": API_KEY}

    save_to_db(results)
    print(f"Saved {len(results)} businesses to database")
    return results

def get_place_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website",
        "key": API_KEY
    }
    data = requests.get(url, params=params).json().get("result", {})
    return {
        "phone":   data.get("formatted_phone_number", ""),
        "website": data.get("website", "")
    }

def save_to_db(businesses):
    """Insert new businesses, skipping any whose name already exists."""
    db = get_db()
    existing_names = {
        row[0].lower()
        for row in db.execute('SELECT name FROM businesses').fetchall()
    }
    inserted = 0
    for b in businesses:
        name = (b.get('name') or '').strip()
        if not name or name.lower() in existing_names:
            continue
        db.execute(
            'INSERT INTO businesses (name, address, phone, website, email, stage, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, b.get('address', ''), b.get('phone', ''), b.get('website', ''), b.get('email', ''), 'New', '')
        )
        existing_names.add(name.lower())
        inserted += 1
    db.commit()
    db.close()
    print(f"Inserted {inserted} new businesses into DB")

if __name__ == "__main__":
    city = input("Enter city: ")
    btype = input("Enter business type: ")
    find_businesses(city, btype)
