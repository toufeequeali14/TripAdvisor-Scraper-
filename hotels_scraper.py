# hotels_scraper.py

"""
TripAdvisor Hotels GraphQL Scraper — City Name Edition
-------------------------------------------------
Resolves city name → geoId via three methods (in order):
  1. Built-in lookup table for ~60 major cities (instant, no request needed)
  2. TripAdvisor TypeAheadJson REST endpoint (lightweight, no cookies needed)
  3. TripAdvisor GraphQL typeahead (preRegisteredQueryId: 26d0f65a5b5e49b9)

Then scrapes Hotels / Restaurants / Attractions with full details.
"""

import json
import re
import time
import random
import logging
from typing import Optional
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

#load cookies.json into COOKIES
with open("cookies.json", "r", encoding="utf-8") as f:
    _raw = json.load(f)

COOKIES = {c["name"]: c["value"] for c in _raw}

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "content-type": "application/json",
    "origin": "https://www.tripadvisor.com",
    "pragma": "no-cache",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "same-origin",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
}

GRAPHQL_URL = "https://www.tripadvisor.com/data/graphql/ids"

PLACE_TYPE_LABELS = {
    "ACCOMMODATION": "Hotels",
    "RESTAURANT":    "Restaurants",
    "ATTRACTION":    "Attractions",
}

AWARD_LABELS = {
    "COE": "Travellers' Choice",
    "TOA": "Travellers' Choice Best of the Best",
}

KNOWN_CITIES: dict = {
    # Pakistan
    "islamabad":   293960,
    "lahore":      293974,
    "karachi":     293961,
    "peshawar":    294007,
    "multan":      294003,
    "faisalabad":  293964,
    "rawalpindi":  1940768,
    "quetta":      294011,
    # UK
    "london":      186338,
    "manchester":  187069,
    "edinburgh":   186525,
    "birmingham":  186345,
    "glasgow":     186534,
    "liverpool":   186454,
    "bristol":     186359,
    "oxford":      186472,
    "cambridge":   186461,
    # USA
    "new york":      60763,
    "new york city": 60763,
    "los angeles":   32655,
    "chicago":       35805,
    "san francisco": 60713,
    "miami":         34439,
    "las vegas":     45963,
    "orlando":       34515,
    "washington":    28754,
    "washington dc": 28754,
    "boston":        60745,
    "seattle":       60878,
    "denver":        33388,
    "austin":        30184,
    "nashville":     55229,
    "new orleans":   60864,
    # Europe
    "paris":       187147,
    "rome":        187791,
    "barcelona":   187497,
    "madrid":      187514,
    "amsterdam":   188553,
    "berlin":      187323,
    "vienna":      190454,
    "prague":      274707,
    "budapest":    274887,
    "lisbon":      188578,
    "athens":      189400,
    "istanbul":    297953,
    "dubai":       295424,
    "venice":      187870,
    "florence":    187895,
    "milan":       187849,
    "zurich":      188045,
    "copenhagen":  189554,
    "stockholm":   189850,
    "oslo":        190449,
    "helsinki":    189670,
    "brussels":    188643,
    "porto":       193840,
    "seville":     187443,
    # Asia
    "tokyo":        298184,
    "osaka":        298946,
    "kyoto":        298946,
    "bangkok":      293916,
    "singapore":    294265,
    "hong kong":    294217,
    "beijing":      294212,
    "shanghai":     308745,
    "seoul":        255951,
    "delhi":        304551,
    "mumbai":       304554,
    "bali":         306822,
    "kuala lumpur": 294230,
    "jakarta":      294229,
    # Middle East & Africa
    "abu dhabi":  295391,
    "doha":       294007,
    "riyadh":     298456,
    "cairo":      294200,
    "cape town":  312659,
    "marrakech":  297998,
    # Americas
    "toronto":       77808,
    "vancouver":     55895,
    "montreal":      77399,
    "mexico city":   150585,
    "cancun":        149823,
    "buenos aires":  312741,
    "rio de janeiro": 303506,
    "sao paulo":     303374,
    "lima":          312578,
    "sydney":        255060,
    "melbourne":     255100,
    "auckland":      255104,
}


# ══════════════════════════════════════════════════════════════
# HTTP CLIENT
# ══════════════════════════════════════════════════════════════

class TripAdvisorClient:
    def __init__(self, cookies: dict, delay_range: tuple = (1.2, 2.8)):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.cookies.update(cookies)
        self.delay_range = delay_range

    def post(self, payload: list, referer: str = "https://www.tripadvisor.com/") -> Optional[list]:
        self.session.headers["referer"] = referer
        try:
            time.sleep(random.uniform(*self.delay_range))
            resp = self.session.post(GRAPHQL_URL, json=payload, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            log.error(f"HTTP {e.response.status_code} — refresh cookies")
            return None
        except Exception as e:
            log.error(f"Request error: {e}")
            return None

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            time.sleep(random.uniform(*self.delay_range))
            resp = self.session.get(url, timeout=20, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as e:
            log.debug(f"GET {url} failed: {e}")
            return None


# ══════════════════════════════════════════════════════════════
# CITY → GEO ID RESOLUTION
# ══════════════════════════════════════════════════════════════

def resolve_city(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
    """
    Resolves city name to geoId. Tries three methods in order:
      1. Built-in lookup table
      2. TypeAheadJson REST endpoint
      3. GraphQL typeahead
    """
    normalized = city_name.strip().lower()

    # Method 1: built-in table
    if normalized in KNOWN_CITIES:
        geo_id = KNOWN_CITIES[normalized]
        log.info(f"Resolved via lookup table → {city_name} (geoId: {geo_id})")
        return {"geoId": geo_id, "name": city_name, "canonical": city_name}

    # Partial match
    for key, geo_id in KNOWN_CITIES.items():
        if normalized in key or key in normalized:
            log.info(f"Partial match '{key}' → {city_name} (geoId: {geo_id})")
            return {"geoId": geo_id, "name": city_name, "canonical": city_name}

    log.info(f"'{city_name}' not in lookup table, trying TypeAheadJson ...")

    # Method 2: TypeAheadJson REST endpoint
    result = _resolve_via_typeahead_rest(client, city_name)
    if result:
        return result

    # Method 3: GraphQL typeahead
    log.info("Trying GraphQL typeahead ...")
    result = _resolve_via_graphql(client, city_name)
    if result:
        return result

    log.error(
        f"Could not resolve '{city_name}'.\n"
        f"  → Try a different spelling, or add it manually:\n"
        f"      KNOWN_CITIES['{normalized}'] = <geoId>\n"
        f"  → Find the geoId in any TripAdvisor URL for that city:\n"
        f"      https://www.tripadvisor.com/Tourism-g<GEOID>-..."
    )
    return None


def _resolve_via_typeahead_rest(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
    url = (
        "https://www.tripadvisor.com/TypeAheadJson"
        f"?action=API&uiOrigin=GEOSCOPED_SEARCH_INPUT"
        f"&query={requests.utils.quote(city_name)}"
        f"&max=5&types=geo&returnMeta=true"
    )
    try:
        resp = client.get(url, headers={**HEADERS, "content-type": "text/html"})
        if not resp:
            return None
        data    = resp.json()
        results = data.get("results") or []
        for r in results:
            details     = r.get("details") or {}
            location_id = details.get("locationId") or details.get("DETAILS_GEO_ID")
            if not location_id:
                value = r.get("value", "")
                m = re.search(r"g(\d+)", value)
                if m:
                    location_id = int(m.group(1))
            if location_id:
                name      = r.get("value") or city_name
                parent    = details.get("LONG_ONLY_PARENT") or details.get("longOnlyParent")
                canonical = f"{name}, {parent}" if parent else name
                log.info(f"TypeAheadJson → {canonical} (geoId: {location_id})")
                return {"geoId": int(location_id), "name": name, "canonical": canonical}
    except Exception as e:
        log.debug(f"TypeAheadJson failed: {e}")
    return None


def _resolve_via_graphql(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
    payload = [
        {
            "variables": {
                "query": city_name,
                "limit": 5,
                "scope": "WORLDWIDE",
                "locale": "en-US",
                "types": ["GEO"],
            },
            "extensions": {"preRegisteredQueryId": "26d0f65a5b5e49b9"},
        }
    ]
    response = client.post(payload)
    if not response:
        return None
    try:
        results = (
            response[0]
            .get("data", {})
            .get("Typeahead_autocomplete", {})
            .get("results", [])
        )
        for r in results:
            details     = r.get("details") or {}
            location_id = details.get("locationId")
            if not location_id:
                tracking = r.get("trackingKey", "")
                if ":" in tracking:
                    try:
                        location_id = int(tracking.split(":")[1])
                    except ValueError:
                        pass
            if location_id:
                name      = details.get("localizedName") or r.get("value") or city_name
                parent    = _d(details, "localizedAdditionalNames", "longOnlyParent")
                canonical = f"{name}, {parent}" if parent else name
                log.info(f"GraphQL typeahead → {canonical} (geoId: {location_id})")
                return {"geoId": int(location_id), "name": name, "canonical": canonical}
    except Exception as e:
        log.debug(f"GraphQL typeahead parse error: {e}")
    return None


# ══════════════════════════════════════════════════════════════
# POI SCRAPING
# ══════════════════════════════════════════════════════════════

def build_payload(geo_id: int) -> list:
    return [
        {
            "variables": {"geoId": geo_id},
            "extensions": {"preRegisteredQueryId": "0dd6d968ca719dae"},
        }
    ]


def extract(response_data: list) -> list:
    results = []
    if not response_data:
        return results

    for query_result in response_data:
        themes_list = (
            (query_result.get("data") or {})
            .get("Themes_getThemesAndLocationsForGeo") or []
        )
        for theme_entry in themes_list:
            place_types = (
                (theme_entry.get("locationsForSelectedTheme") or {})
                .get("locationsForPlaceTypes") or []
            )
            for pt_block in place_types:
                raw_type   = pt_block.get("placeType", "UNKNOWN")
                type_label = PLACE_TYPE_LABELS.get(raw_type, raw_type.title())
                for loc in (pt_block.get("locations") or []):
                    li  = loc.get("locationInformation") or {}
                    poi = _parse_location(li, type_label)
                    if poi:
                        results.append(poi)

    seen, unique = set(), []
    for item in results:
        key = item.get("locationId") or item.get("name")
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _parse_location(li: dict, type_label: str) -> Optional[dict]:
    name = li.get("name") or _d(li, "locationV2", "names", "name")
    if not name:
        return None

    rs           = li.get("reviewSummary") or {}
    rating       = rs.get("rating")
    review_count = rs.get("reviewCount")

    url = _d(li, "route", "url")
    if url and url.startswith("/"):
        url = f"https://www.tripadvisor.com{url}"

    url_template = _d(li, "thumbnail", "photoSizeDynamic", "urlTemplate")
    photo_url    = url_template.replace("{width}", "400").replace("{height}", "300") if url_template else None
    median_rate  = _d(li, "hotelPrice", "hotel", "details", "medianMetaRate")
    address      = _d(li, "locationV2", "contact", "streetAddress", "fullAddress")
    parent_geo   = _d(li, "locationV2", "hierarchy", "parentGeo", "names", "longParentAbbreviated")
    award_raw    = _d(li, "locationV2", "bestAwardForActiveYearV2", "awardType")
    award_year   = _d(li, "locationV2", "bestAwardForActiveYearV2", "year")
    award        = f"{AWARD_LABELS.get(award_raw, award_raw)} {award_year}" if award_raw else None

    return {
        "locationId":  li.get("locationId"),
        "name":        name,
        "type":        type_label,
        "rating":      rating,
        "reviewCount": review_count,
        "award":       award,
        "address":     address,
        "city":        parent_geo,
        "medianPrice": median_rate,
        "photoUrl":    photo_url,
        "url":         url,
    }


def _d(obj, *keys, default=None):
    for k in keys:
        if obj is None:
            return default
        if isinstance(obj, list):
            try:
                obj = obj[int(k)]
            except (IndexError, ValueError, TypeError):
                return default
        elif isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return default
    return obj if obj is not None else default


# ══════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════

def scrape_all_city_hoetls(city_name: str):
    if not COOKIES:
        log.warning("COOKIES dict is empty — may be blocked by DataDome.")

    client    = TripAdvisorClient(COOKIES)
    city_info = resolve_city(client, city_name)
    if not city_info:
        return None

    geo_id         = city_info["geoId"]
    city_canonical = city_info["canonical"]

    log.info(f"Fetching POIs for {city_canonical} (geoId={geo_id}) ...")

    response = client.post(
        build_payload(geo_id),
        referer=f"https://www.tripadvisor.com/Tourism-g{geo_id}-Vacations.html",
    )
    if not response:
        log.error("No response received.")
        return None

    results = extract(response)
    if not results:
        log.warning("0 results extracted.")
        return None

    for r in results:
        r["queryCity"] = city_canonical
        # r["geoId"]     = geo_id

    return results


if __name__ == "__main__":
    city_name = input("Enter city name: ")
    results   = scrape_all_city_hoetls(city_name)
    if results:
        print(f"\nFetched {len(results)} results.")





















# # hotels_scraper.py

# """
# TripAdvisor GraphQL Scraper — City Name Edition
# -------------------------------------------------
# Resolves city name → geoId via three methods (in order):
#   1. Built-in lookup table for ~60 major cities (instant, no request needed)
#   2. TripAdvisor TypeAheadJson REST endpoint (lightweight, no cookies needed)
#   3. TripAdvisor GraphQL typeahead (preRegisteredQueryId: 26d0f65a5b5e49b9)

# Then scrapes Hotels / Restaurants / Attractions with full details.

# Usage:
#     python tripadvisor_scraper.py --city "London"
#     python tripadvisor_scraper.py --city "Lahore" --output lahore.json
#     python tripadvisor_scraper.py --city "Dubai" --playwright
#     python tripadvisor_scraper.py --list-cities          # show built-in cities
# """

# import argparse
# import json
# import re
# import time
# import random
# import logging
# from typing import Optional
# import requests

# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# log = logging.getLogger(__name__)

# COOKIES: dict = {
#     # Paste fresh cookies here if not using --playwright
#     # "TAUnique": "...", "TASID": "...", "datadome": "...",
#     # "TASession": "...", "TASSK": "...", "PAC": "...", "TART": "...", "__vt": "...",
# }

# HEADERS = {
#     "accept": "*/*",
#     "accept-language": "en-US,en;q=0.9",
#     "cache-control": "no-cache",
#     "content-type": "application/json",
#     "origin": "https://www.tripadvisor.com",
#     "pragma": "no-cache",
#     "sec-fetch-dest": "empty",
#     "sec-fetch-mode": "same-origin",
#     "sec-fetch-site": "same-origin",
#     "user-agent": (
#         "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/149.0.0.0 Safari/537.36"
#     ),
# }

# GRAPHQL_URL = "https://www.tripadvisor.com/data/graphql/ids"

# PLACE_TYPE_LABELS = {
#     "ACCOMMODATION": "Hotels",
#     "RESTAURANT":    "Restaurants",
#     "ATTRACTION":    "Attractions",
# }

# AWARD_LABELS = {
#     "COE": "Travellers' Choice",
#     "TOA": "Travellers' Choice Best of the Best",
# }

# # ---------------------------------------------------------------------------
# # Built-in geoId lookup table — covers ~60 major cities worldwide
# # Source: TripAdvisor URL patterns e.g. Tourism-g186338 = London
# # ---------------------------------------------------------------------------
# KNOWN_CITIES: dict = {
#     # Pakistan
#     "islamabad":   293960,
#     "lahore":      293974,
#     "karachi":     293961,
#     "peshawar":    294007,
#     "multan":      294003,
#     "faisalabad":  293964,
#     "rawalpindi":  1940768,
#     "quetta":      294011,
#     # UK
#     "london":      186338,
#     "manchester":  187069,
#     "edinburgh":   186525,
#     "birmingham":  186345,
#     "glasgow":     186534,
#     "liverpool":   186454,
#     "bristol":     186359,
#     "oxford":      186472,
#     "cambridge":   186461,
#     # USA
#     "new york":    60763,
#     "new york city": 60763,
#     "los angeles": 32655,
#     "chicago":     35805,
#     "san francisco": 60713,
#     "miami":       34439,
#     "las vegas":   45963,
#     "orlando":     34515,
#     "washington":  28754,
#     "washington dc": 28754,
#     "boston":      60745,
#     "seattle":     60878,
#     "denver":      33388,
#     "austin":      30184,
#     "nashville":   55229,
#     "new orleans": 60864,
#     # Europe
#     "paris":       187147,
#     "rome":        187791,
#     "barcelona":   187497,
#     "madrid":      187514,
#     "amsterdam":   188553,
#     "berlin":      187323,
#     "vienna":      190454,
#     "prague":      274707,
#     "budapest":    274887,
#     "lisbon":      188578,
#     "athens":      189400,
#     "istanbul":    297953,
#     "dubai":       295424,
#     "venice":      187870,
#     "florence":    187895,
#     "milan":       187849,
#     "zurich":      188045,
#     "copenhagen":  189554,
#     "stockholm":   189850,
#     "oslo":        190449,
#     "helsinki":    189670,
#     "brussels":    188643,
#     "porto":       193840,
#     "seville":     187443,
#     # Asia
#     "tokyo":       298184,
#     "osaka":       298946,
#     "kyoto":       298946,
#     "bangkok":     293916,
#     "singapore":   294265,
#     "hong kong":   294217,
#     "beijing":     294212,
#     "shanghai":    308745,
#     "seoul":       255951,
#     "delhi":       304551,
#     "mumbai":      304554,
#     "bali":        306822,
#     "kuala lumpur": 294230,
#     "jakarta":     294229,
#     # Middle East & Africa
#     "abu dhabi":   295391,
#     "doha":        294007,
#     "riyadh":      298456,
#     "cairo":       294200,
#     "cape town":   312659,
#     "marrakech":   297998,
#     # Americas
#     "toronto":     77808,
#     "vancouver":   55895,
#     "montreal":    77399,
#     "mexico city": 150585,
#     "cancun":      149823,
#     "buenos aires": 312741,
#     "rio de janeiro": 303506,
#     "sao paulo":   303374,
#     "lima":        312578,
#     "sydney":      255060,
#     "melbourne":   255100,
#     "auckland":    255104,
# }


# # ---------------------------------------------------------------------------
# # HTTP client
# # ---------------------------------------------------------------------------

# class TripAdvisorClient:
#     def __init__(self, cookies: dict, delay_range: tuple = (1.2, 2.8)):
#         self.session = requests.Session()
#         self.session.headers.update(HEADERS)
#         self.session.cookies.update(cookies)
#         self.delay_range = delay_range

#     def post(self, payload: list, referer: str = "https://www.tripadvisor.com/") -> Optional[list]:
#         self.session.headers["referer"] = referer
#         try:
#             time.sleep(random.uniform(*self.delay_range))
#             resp = self.session.post(GRAPHQL_URL, json=payload, timeout=20)
#             resp.raise_for_status()
#             return resp.json()
#         except requests.HTTPError as e:
#             log.error(f"HTTP {e.response.status_code} — refresh cookies or use --playwright")
#             return None
#         except Exception as e:
#             log.error(f"Request error: {e}")
#             return None

#     def get(self, url: str, **kwargs) -> Optional[requests.Response]:
#         try:
#             time.sleep(random.uniform(*self.delay_range))
#             resp = self.session.get(url, timeout=20, **kwargs)
#             resp.raise_for_status()
#             return resp
#         except Exception as e:
#             log.debug(f"GET {url} failed: {e}")
#             return None


# # ---------------------------------------------------------------------------
# # City → geoId resolution (3 methods)
# # ---------------------------------------------------------------------------

# def resolve_city(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
#     """
#     Resolves city name to geoId. Tries three methods in order:
#       1. Built-in lookup table
#       2. TypeAheadJson REST endpoint
#       3. GraphQL typeahead
#     """
#     normalized = city_name.strip().lower()

#     # --- Method 1: built-in table ---
#     if normalized in KNOWN_CITIES:
#         geo_id = KNOWN_CITIES[normalized]
#         log.info(f"Resolved via lookup table → {city_name} (geoId: {geo_id})")
#         return {"geoId": geo_id, "name": city_name, "canonical": city_name}

#     # Partial match (e.g. "new york city" → "new york")
#     for key, geo_id in KNOWN_CITIES.items():
#         if normalized in key or key in normalized:
#             log.info(f"Partial match '{key}' → {city_name} (geoId: {geo_id})")
#             return {"geoId": geo_id, "name": city_name, "canonical": city_name}

#     log.info(f"'{city_name}' not in lookup table, trying TypeAheadJson ...")

#     # --- Method 2: TypeAheadJson REST endpoint ---
#     result = _resolve_via_typeahead_rest(client, city_name)
#     if result:
#         return result

#     # --- Method 3: GraphQL typeahead ---
#     log.info("Trying GraphQL typeahead ...")
#     result = _resolve_via_graphql(client, city_name)
#     if result:
#         return result

#     log.error(
#         f"Could not resolve '{city_name}'.\n"
#         f"  → Try a different spelling, or add it manually:\n"
#         f"      KNOWN_CITIES['{normalized}'] = <geoId>\n"
#         f"  → Find the geoId in any TripAdvisor URL for that city:\n"
#         f"      https://www.tripadvisor.com/Tourism-g<GEOID>-..."
#     )
#     return None


# def _resolve_via_typeahead_rest(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
#     """
#     Hits the lightweight TypeAheadJson endpoint — works without session cookies.
#     Returns geo results with locationId.
#     """
#     url = (
#         "https://www.tripadvisor.com/TypeAheadJson"
#         f"?action=API&uiOrigin=GEOSCOPED_SEARCH_INPUT"
#         f"&query={requests.utils.quote(city_name)}"
#         f"&max=5&types=geo&returnMeta=true"
#     )
#     try:
#         resp = client.get(url, headers={**HEADERS, "content-type": "text/html"})
#         if not resp:
#             return None
#         data = resp.json()
#         results = data.get("results") or []
#         for r in results:
#             details    = r.get("details") or {}
#             location_id = details.get("locationId") or details.get("DETAILS_GEO_ID")
#             if not location_id:
#                 # parse from "value" e.g. "g186338" or tracking key
#                 value = r.get("value", "")
#                 m = re.search(r"g(\d+)", value)
#                 if m:
#                     location_id = int(m.group(1))
#             if location_id:
#                 name   = r.get("value") or city_name
#                 parent = details.get("LONG_ONLY_PARENT") or details.get("longOnlyParent")
#                 canonical = f"{name}, {parent}" if parent else name
#                 log.info(f"TypeAheadJson → {canonical} (geoId: {location_id})")
#                 return {"geoId": int(location_id), "name": name, "canonical": canonical}
#     except Exception as e:
#         log.debug(f"TypeAheadJson failed: {e}")
#     return None


# def _resolve_via_graphql(client: TripAdvisorClient, city_name: str) -> Optional[dict]:
#     """GraphQL autocomplete — requires a valid session."""
#     payload = [
#         {
#             "variables": {
#                 "query": city_name,
#                 "limit": 5,
#                 "scope": "WORLDWIDE",
#                 "locale": "en-US",
#                 "types": ["GEO"],
#             },
#             "extensions": {"preRegisteredQueryId": "26d0f65a5b5e49b9"},
#         }
#     ]
#     response = client.post(payload)
#     if not response:
#         return None
#     try:
#         results = (
#             response[0]
#             .get("data", {})
#             .get("Typeahead_autocomplete", {})
#             .get("results", [])
#         )
#         for r in results:
#             details     = r.get("details") or {}
#             location_id = details.get("locationId")
#             if not location_id:
#                 tracking = r.get("trackingKey", "")
#                 if ":" in tracking:
#                     try:
#                         location_id = int(tracking.split(":")[1])
#                     except ValueError:
#                         pass
#             if location_id:
#                 name   = details.get("localizedName") or r.get("value") or city_name
#                 parent = _d(details, "localizedAdditionalNames", "longOnlyParent")
#                 canonical = f"{name}, {parent}" if parent else name
#                 log.info(f"GraphQL typeahead → {canonical} (geoId: {location_id})")
#                 return {"geoId": int(location_id), "name": name, "canonical": canonical}
#     except Exception as e:
#         log.debug(f"GraphQL typeahead parse error: {e}")
#     return None


# # ---------------------------------------------------------------------------
# # POI scraping
# # ---------------------------------------------------------------------------

# def build_payload(geo_id: int) -> list:
#     return [
#         {
#             "variables": {"geoId": geo_id},
#             "extensions": {"preRegisteredQueryId": "0dd6d968ca719dae"},
#         }
#     ]


# def extract(response_data: list) -> list:
#     results = []
#     if not response_data:
#         return results

#     for query_result in response_data:
#         themes_list = (
#             (query_result.get("data") or {})
#             .get("Themes_getThemesAndLocationsForGeo") or []
#         )
#         for theme_entry in themes_list:
#             place_types = (
#                 (theme_entry.get("locationsForSelectedTheme") or {})
#                 .get("locationsForPlaceTypes") or []
#             )
#             for pt_block in place_types:
#                 raw_type   = pt_block.get("placeType", "UNKNOWN")
#                 type_label = PLACE_TYPE_LABELS.get(raw_type, raw_type.title())
#                 for loc in (pt_block.get("locations") or []):
#                     li  = loc.get("locationInformation") or {}
#                     poi = _parse_location(li, type_label)
#                     if poi:
#                         results.append(poi)

#     seen, unique = set(), []
#     for item in results:
#         key = item.get("locationId") or item.get("name")
#         if key not in seen:
#             seen.add(key)
#             unique.append(item)
#     return unique


# def _parse_location(li: dict, type_label: str) -> Optional[dict]:
#     name = li.get("name") or _d(li, "locationV2", "names", "name")
#     if not name:
#         return None

#     rs           = li.get("reviewSummary") or {}
#     rating       = rs.get("rating")
#     review_count = rs.get("reviewCount")

#     url = _d(li, "route", "url")
#     if url and url.startswith("/"):
#         url = f"https://www.tripadvisor.com{url}"

#     url_template = _d(li, "thumbnail", "photoSizeDynamic", "urlTemplate")
#     photo_url    = url_template.replace("{width}", "400").replace("{height}", "300") if url_template else None
#     median_rate  = _d(li, "hotelPrice", "hotel", "details", "medianMetaRate")
#     address      = _d(li, "locationV2", "contact", "streetAddress", "fullAddress")
#     parent_geo   = _d(li, "locationV2", "hierarchy", "parentGeo", "names", "longParentAbbreviated")
#     award_raw    = _d(li, "locationV2", "bestAwardForActiveYearV2", "awardType")
#     award_year   = _d(li, "locationV2", "bestAwardForActiveYearV2", "year")
#     award        = f"{AWARD_LABELS.get(award_raw, award_raw)} {award_year}" if award_raw else None

#     return {
#         "locationId":  li.get("locationId"),
#         "name":        name,
#         "type":        type_label,
#         "rating":      rating,
#         "reviewCount": review_count,
#         "award":       award,
#         "address":     address,
#         "city":        parent_geo,
#         "medianPrice": median_rate,
#         "photoUrl":    photo_url,
#         "url":         url,
#     }


# def _d(obj, *keys, default=None):
#     for k in keys:
#         if obj is None:
#             return default
#         if isinstance(obj, list):
#             try:
#                 obj = obj[int(k)]
#             except (IndexError, ValueError, TypeError):
#                 return default
#         elif isinstance(obj, dict):
#             obj = obj.get(k)
#         else:
#             return default
#     return obj if obj is not None else default


# # ---------------------------------------------------------------------------
# # Playwright
# # ---------------------------------------------------------------------------

# def harvest_cookies(city_name: str) -> dict:
#     try:
#         from playwright.sync_api import sync_playwright
#     except ImportError:
#         raise RuntimeError("Run: pip install playwright && playwright install chromium")

#     url = f"https://www.tripadvisor.com/Search?q={requests.utils.quote(city_name)}"
#     log.info(f"Harvesting cookies via Playwright ...")
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         ctx  = browser.new_context(user_agent=HEADERS["user-agent"], locale="en-US")
#         page = ctx.new_page()
#         page.goto(url, wait_until="networkidle", timeout=30000)
#         time.sleep(3)
#         cookies = {c["name"]: c["value"] for c in ctx.cookies()}
#         browser.close()
#     log.info(f"Harvested {len(cookies)} cookies")
#     return cookies


# # ---------------------------------------------------------------------------
# # Output
# # ---------------------------------------------------------------------------

# def print_results(results: list, city_canonical: str):
#     by_type: dict = {}
#     for r in results:
#         by_type.setdefault(r["type"], []).append(r)

#     print(f"\n{'='*65}")
#     print(f"  TripAdvisor — {city_canonical}")
#     print(f"{'='*65}")
#     for type_label, items in by_type.items():
#         print(f"\n{type_label} ({len(items)})")
#         print(f"  {'Name':<38} {'Rating':>6}  {'Reviews':>8}  Award")
#         print(f"  {'-'*38} {'------':>6}  {'--------':>8}  -----")
#         for item in items:
#             rating  = f"{item['rating']:.1f}" if item.get("rating") else "  N/A"
#             reviews = str(item["reviewCount"]) if item.get("reviewCount") else "?"
#             award   = item.get("award") or ""
#             print(f"  {item['name']:<38} {rating:>6}  {reviews:>8}  {award}")


# def scrape_all_city_hoetls(city_name: str):
#     parser = argparse.ArgumentParser(description="TripAdvisor scraper — city name edition")
#     parser.add_argument("--city", help='City name, e.g. "London" or "Dubai"')
#     parser.add_argument("--playwright", action="store_true")
#     parser.add_argument("--output", default=None)
#     parser.add_argument("--save-raw", action="store_true")
#     parser.add_argument("--list-cities", action="store_true", help="Print all built-in cities and exit")
#     args = parser.parse_args()

#     # ----------------------------
#     # list cities mode
#     # ----------------------------
#     # if args.list_cities:
#     #     print(f"\n{len(KNOWN_CITIES)} built-in cities:\n")
#     #     for city, geo_id in sorted(KNOWN_CITIES.items()):
#     #         print(f"  {city:<25} geoId: {geo_id}")
#     #     return

#     # # ----------------------------
#     # # interactive fallback input
#     # # ----------------------------
#     # if not args.city:
#     #     args.city = input("Enter city name: ").strip()

#     # if not args.city:
#     #     parser.error("City name is required")

#     args.city = city_name

#     # ----------------------------
#     # rest of your logic
#     # ----------------------------
#     output_file = args.output or f"{args.city.lower().replace(' ', '_')}.json"

#     cookies = harvest_cookies(args.city) if args.playwright else COOKIES
#     if not cookies:
#         log.warning("COOKIES dict is empty — may be blocked by DataDome.")

#     client = TripAdvisorClient(cookies)

#     city_info = resolve_city(client, args.city)
#     if not city_info:
#         return

#     geo_id = city_info["geoId"]
#     city_canonical = city_info["canonical"]

#     log.info(f"Fetching POIs for {city_canonical} (geoId={geo_id}) ...")

#     response = client.post(
#         build_payload(geo_id),
#         referer=f"https://www.tripadvisor.com/Tourism-g{geo_id}-Vacations.html",
#     )

#     if args.save_raw:
#         with open("raw_debug.json", "w", encoding="utf-8") as f:
#             json.dump(response, f, indent=2)
#         log.info("Raw response → raw_debug.json")

#     if not response:
#         log.error("No response received.")
#         return

#     results = extract(response)
#     if not results:
#         log.warning("0 results extracted — try --save-raw to inspect the response.")
#         return

#     print_results(results, city_canonical)

#     for r in results:
#         r["queryCity"] = city_canonical
#         r["geoId"] = geo_id

#     # output_file = args.output or f"{args.city.lower().replace(' ', '_')}.json"

#     # with open(output_file, "w", encoding="utf-8") as f:
#     #     json.dump(results, f, indent=2, ensure_ascii=False)

#     # log.info(f"Saved {len(results)} records → {output_file}")

#     return results


# if __name__ == "__main__":

#     city_name = input("Enter city name: ")
#     scrape_all_city_hoetls(city_name)
