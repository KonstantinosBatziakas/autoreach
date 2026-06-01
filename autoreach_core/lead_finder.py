"""
Google Maps Places API lead discovery.
"""
import requests
import time


def find_businesses(city: str, business_type: str, api_key: str) -> list[dict]:
    query = f"{business_type} in {city}"
    url   = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    results = []
    params  = {"query": query, "key": api_key}

    while True:
        resp = requests.get(url, params=params, timeout=10).json()
        for place in resp.get("results", []):
            details = _get_details(place.get("place_id", ""), api_key)
            results.append({
                "name":    place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "phone":   details.get("phone", ""),
                "website": details.get("website", ""),
                "email":   "",
            })
        token = resp.get("next_page_token")
        if not token:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    return results


def _get_details(place_id: str, api_key: str) -> dict:
    if not place_id:
        return {}
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={"place_id": place_id, "fields": "formatted_phone_number,website", "key": api_key},
        timeout=10,
    ).json().get("result", {})
    return {
        "phone":   resp.get("formatted_phone_number", ""),
        "website": resp.get("website", ""),
    }
