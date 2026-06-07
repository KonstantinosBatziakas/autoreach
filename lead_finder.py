import os
import time
import requests
from db import get_db

_PLACES_TEXT_URL   = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
_PLACES_DETAIL_URL = 'https://maps.googleapis.com/maps/api/place/details/json'


def _api_key() -> str:
    key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    if not key:
        raise ValueError(
            'GOOGLE_MAPS_API_KEY is not set. '
            'Add it in Render → Environment or your .env file.'
        )
    return key


def get_place_details(place_id: str, api_key: str) -> dict:
    try:
        resp = requests.get(
            _PLACES_DETAIL_URL,
            params={'place_id': place_id, 'fields': 'formatted_phone_number,website', 'key': api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get('result', {})
        return {
            'phone':   data.get('formatted_phone_number', ''),
            'website': data.get('website', ''),
        }
    except Exception as exc:
        print(f'[lead_finder] place details error for {place_id}: {exc}')
        return {'phone': '', 'website': ''}


def find_businesses(city: str, business_type: str) -> list[dict]:
    api_key = _api_key()
    query = f'{business_type} in {city}'
    print(f"[lead_finder] Searching for '{business_type}' in '{city}'…")

    results = []
    params = {'query': query, 'key': api_key}

    while True:
        try:
            resp = requests.get(_PLACES_TEXT_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(f'Google Maps API request failed: {exc}') from exc

        status = data.get('status')
        if status not in ('OK', 'ZERO_RESULTS'):
            error_msg = data.get('error_message', status)
            raise RuntimeError(f'Google Maps API error: {error_msg}')

        for place in data.get('results', []):
            place_id = place.get('place_id')
            details  = get_place_details(place_id, api_key) if place_id else {}
            results.append({
                'name':    place.get('name', ''),
                'address': place.get('formatted_address', ''),
                'phone':   details.get('phone', ''),
                'website': details.get('website', ''),
                'email':   '',
            })

        next_token = data.get('next_page_token')
        if not next_token:
            break
        time.sleep(2)  # Google requires a short delay before using next_page_token
        params = {'pagetoken': next_token, 'key': api_key}

    save_to_db(results)
    print(f'[lead_finder] Saved {len(results)} businesses to database.')
    return results


def save_to_db(businesses: list[dict]):
    """Insert new businesses, skipping duplicates by name."""
    db = get_db()
    try:
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
                'INSERT INTO businesses (name, address, phone, website, email, stage, notes) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (name, b.get('address', ''), b.get('phone', ''), b.get('website', ''),
                 b.get('email', ''), 'New', '')
            )
            existing_names.add(name.lower())
            inserted += 1
        db.commit()
        print(f'[lead_finder] Inserted {inserted} new businesses.')
    finally:
        db.close()


if __name__ == '__main__':
    city  = input('Enter city: ')
    btype = input('Enter business type: ')
    find_businesses(city, btype)
