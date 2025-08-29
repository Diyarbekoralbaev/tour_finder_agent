import os
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv
from langchain_core.tools import tool
from difflib import get_close_matches

load_dotenv()

TURTOPAR_API_BASE = "https://api.turtopar.uz/api/v1"

# Cache for locations to avoid repeated API calls
_locations_cache = None
_origin_locations_cache = None

# Transliteration mapping for common location names
TRANSLITERATION_MAP = {
    # === UZBEKISTAN (Origin Cities) ===
    'toshkent': 'ташкент',
    'tashkent': 'ташкент',
    'samarqand': 'самарканд',
    'samarkand': 'самарканд',
    'buxoro': 'бухара',
    'bukhara': 'бухара',
    'xiva': 'хива',
    'khiva': 'хива',
    'namangan': 'наманган',
    "farg'ona": 'фергана',
    'fergana': 'фергana',
    'fargona': 'фергана',

    # === COUNTRIES ===
    # Turkey
    'turkiya': 'турция',
    'turkey': 'турция',
    'turtsiya': 'турция',

    # Uzbekistan
    "o'zbekiston": 'узбекистан',
    'ozbekiston': 'узбекистан',
    'uzbekistan': 'узбекистан',

    # France
    'fransiya': 'франция',
    'france': 'франция',

    # UAE
    'baa': 'оаэ',
    'uae': 'оаэ',
    'emirates': 'оаэ',

    # Egypt
    'misr': 'египет',
    'egypt': 'египет',

    # Thailand
    'tailand': 'таиланд',
    'thailand': 'таиланд',

    # Malaysia
    'malayziya': 'малайзия',
    'malaysia': 'малайзия',

    # Indonesia
    'indoneziya': 'индонезия',
    'indonesia': 'индонезия',

    # Maldives
    'maldiv orollari': 'мальдивы',
    'maldiv': 'мальдивы',
    'maldives': 'мальдивы',
    'maldivy': 'мальдивы',

    # India
    'hindiston': 'индия',
    'india': 'индия',

    # Singapore
    'singapur': 'сингапур',
    'singapore': 'сингапур',

    # China
    'xitoy': 'китай',
    'china': 'китай',
    'kitay': 'китай',

    # Georgia
    'gruziya': 'грузия',
    'georgia': 'грузия',

    # Vietnam
    'vetnam': 'вьетнам',
    'vietnam': 'вьетнам',

    # Azerbaijan
    'ozarbayjon': 'азербайджан',
    'azerbayjan': 'азербайджан',
    'azerbaijan': 'азербайджан',

    # Qatar
    'qatar': 'катар',
    'katar': 'катар',

    # Oman
    'ummon sultonligi': 'оман',
    'ummon': 'оман',
    'oman': 'оман',

    # Sri Lanka
    'shri lanka': 'шри-ланка',
    'sri lanka': 'шри-ланка',

    # Kazakhstan
    "qozog'iston": 'казахстан',
    'qozogiston': 'казахстан',
    'kazakhstan': 'казахстан',

    # Saudi Arabia
    'saudiya arabistoni': 'саудовская аравия',
    'saudiya': 'саудовская аравия',
    'saudi arabia': 'саудовская аравия',

    # Japan
    'yaponiya': 'япония',
    'japan': 'япония',

    # === CITY MAPPINGS ===
    # Turkey cities
    'istanbul': 'стамбул',
    'marmaris': 'мармарис',
    'kappadokiya': 'каппадокия',
    'cappadocia': 'каппадокия',
    'antaliya': 'анталья',
    'antalya': 'анталья',
    'bodrum': 'бодрум',
    'bursa': 'бурса',
    'dalaman': 'даламан',
    'anqara': 'анкара',
    'ankara': 'анкара',
    "sovg'a": 'белек',
    'belek': 'белек',
    'side': 'сиде',
    'izmir': 'измир',
    'kushadasi': 'кушадасы',
    'trabzon': 'трабзон',
    'kemer': 'кемер',
    'alanya': 'аланья',
    'fethiye': 'фетхие',

    # UAE cities
    'dubay': 'дубай',
    'dubai': 'дубай',
    'abu-dabi': 'абу-даби',
    'abu dhabi': 'абу-даби',
    'sharja': 'шарджа',
    'sharjah': 'шарджа',
    'ras-al-xayma': 'рас-эль-хайма',
    'ras al khaimah': 'рас-эль-хайма',
    'fujeyra': 'фуджейра',
    'fujairah': 'фуджейра',

    # Thailand cities
    'pxuket': 'пхукет',
    'phuket': 'пхукет',
    'bangkok': 'бангкок',
    'pattaya': 'паттайя',

    # Egypt cities
    'sharm al-shayx': 'шарм-эль-шейх',
    'sharm el sheikh': 'шарм-эль-шейх',
    'hurghada': 'хургада',

    # Malaysia cities
    'kuala-lumpur': 'куала-лумпур',
    'kuala lumpur': 'куала-лумпур',
    'penang': 'пенанг',
    'langkawi': 'лангкави',

    # Indonesia cities
    'bali': 'бали',
    'jakarta': 'джакарта',
    'denpasar': 'денпасар',

    # Maldives cities
    'male': 'мале',
    'bodufoludo': 'бодафолуду',
    'feridu': 'фериду',
    'todu': 'тодду',

    # India cities
    'goa': 'гоа',
    'dehli': 'дели',
    'delhi': 'дели',
    'mumbay': 'мумбаи',
    'mumbai': 'мумбаи',

    # China cities
    'pekin': 'пекин',
    'beijing': 'пекин',
    'shanxay': 'шанхай',
    'shanghai': 'шанхай',
    'guanchjou': 'гуанчжоу',
    'guangzhou': 'гуанчжоу',
    'xaynan': 'хайнань',
    'hainan': 'хайнань',
    'sanya': 'санья',

    # Vietnam cities
    'fukuok': 'фукуок',
    'phu quoc': 'фукуок',
    'nyachang': 'нячанг',
    'nha trang': 'нячанг',
    'nha-trang': 'нячанг',
    'danang': 'дананг',
    'hoi an': 'хойан',
    'kamran': 'камрань',

    # Azerbaijan cities
    'baku': 'баку',
    'naftalan': 'нафталан',
    'lenkoran': 'ленкорань',

    # Georgia cities
    'tbilisi': 'тбилиси',
    'borjomi': 'боржоми',

    # Other cities
    'doha': 'доха',
    'maskat': 'маскат',
    'muscat': 'маскат',
    'salala': 'салала',
    'salalah': 'салала',
    'tokio': 'токио',
    'tokyo': 'токио',
    'parij': 'париж',
    'paris': 'париж',
}


def normalize_and_transliterate(name: str) -> List[str]:
    """Normalize and provide transliteration variants for location name"""
    normalized = name.lower().strip()
    variants = [normalized]

    # Add transliterated version if available
    if normalized in TRANSLITERATION_MAP:
        variants.append(TRANSLITERATION_MAP[normalized])

    # Add reverse transliterations (Cyrillic -> Latin)
    reverse_map = {v: k for k, v in TRANSLITERATION_MAP.items()}
    if normalized in reverse_map:
        variants.append(reverse_map[normalized])

    return list(set(variants))  # Remove duplicates


def get_locations_data():
    """Get and cache all location data"""
    global _locations_cache
    if _locations_cache is None:
        try:
            response = requests.get(f"{TURTOPAR_API_BASE}/locations?with_child=1", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _locations_cache = data.get('data', [])
                    with open("locations_cache.json", "w", encoding="utf-8") as f:
                        json.dump(_locations_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error fetching locations: {e}")
            _locations_cache = []
    return _locations_cache or []


def get_origin_locations_data():
    """Get and cache origin location data"""
    global _origin_locations_cache
    if _origin_locations_cache is None:
        try:
            response = requests.get(f"{TURTOPAR_API_BASE}/locations/origin-locations", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _origin_locations_cache = data.get('data', [])
        except Exception as e:
            print(f"Error fetching origin locations: {e}")
            _origin_locations_cache = []
    return _origin_locations_cache or []


def find_location_comprehensive(location_name: str, location_type: str = "destination") -> Dict[str, Any]:
    """
    Comprehensive location finder that returns both exact matches and suggestions
    """
    locations = get_origin_locations_data() if location_type == "origin" else get_locations_data()

    if not locations:
        return {
            "exact_match": None,
            "country_match": None,
            "city_matches": [],
            "suggestions": []
        }

    search_variants = normalize_and_transliterate(location_name)
    print(f"🔍 Comprehensive search for {location_type}: '{location_name}'")
    print(f"   Search variants: {search_variants}")

    exact_match = None
    country_match = None
    city_matches = []
    all_countries = []
    all_cities = []

    if location_type == "destination":
        # Build comprehensive lists
        for country in locations:
            country_variants = normalize_and_transliterate(country["name"])
            country_info = {
                "id": country["id"],
                "name": country["name"],
                "variants": country_variants,
                "type": "country",
                "data": country,
                "cities": []
            }

            # Check for country match
            for search_variant in search_variants:
                for country_variant in country_variants:
                    if search_variant == country_variant:
                        country_match = country_info
                        exact_match = country_info
                    elif search_variant in country_variant or country_variant in search_variant:
                        if not country_match:
                            country_match = country_info

            # Process cities in this country
            for city in country.get("children", []):
                city_variants = normalize_and_transliterate(city["name"])
                city_info = {
                    "id": city["id"],
                    "name": city["name"],
                    "variants": city_variants,
                    "type": "city",
                    "data": city,
                    "country": country["name"],
                    "country_id": country["id"]
                }

                # Check for city match
                for search_variant in search_variants:
                    for city_variant in city_variants:
                        if search_variant == city_variant:
                            exact_match = city_info
                            city_matches.append(city_info)
                        elif search_variant in city_variant or city_variant in search_variant:
                            city_matches.append(city_info)

                all_cities.append(city_info)
                country_info["cities"].append(city_info)

            all_countries.append(country_info)

    else:  # origin locations
        for city in locations:
            city_variants = normalize_and_transliterate(city["name"])
            city_info = {
                "id": city["id"],
                "name": city["name"],
                "variants": city_variants,
                "type": "city",
                "data": city
            }

            for search_variant in search_variants:
                for city_variant in city_variants:
                    if search_variant == city_variant:
                        exact_match = city_info
                    elif search_variant in city_variant or city_variant in search_variant:
                        city_matches.append(city_info)

            all_cities.append(city_info)

    # Remove duplicates from city matches
    unique_city_matches = []
    seen_ids = set()
    for city in city_matches:
        if city["id"] not in seen_ids:
            unique_city_matches.append(city)
            seen_ids.add(city["id"])

    return {
        "exact_match": exact_match,
        "country_match": country_match,
        "city_matches": unique_city_matches,
        "all_countries": all_countries if location_type == "destination" else [],
        "all_cities": all_cities
    }


def search_tours_for_location(location_id: int, **search_params) -> Dict[str, Any]:
    """Search tours for a specific location ID"""
    try:
        params = {"destination_location_child_id": location_id}
        params.update(search_params)

        response = requests.get(f"{TURTOPAR_API_BASE}/tours", params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                tours = data.get("data", [])
                return {
                    "success": True,
                    "tours": tours,
                    "count": len(tours)
                }

        return {"success": False, "tours": [], "count": 0}
    except Exception as e:
        print(f"Error searching tours for location {location_id}: {e}")
        return {"success": False, "tours": [], "count": 0}


@tool
def search_tours(
        origin_city: Optional[str] = None,
        destination_place: Optional[str] = None,
        departure_date: Optional[str] = None,
        budget_max: Optional[int] = None,
        duration_days: Optional[int] = None,
        sort_by: str = "price_asc"
) -> Dict[str, Any]:
    """
    Intelligent tour search with hierarchical fallbacks.
    Searches for tours by destination with smart fallbacks.
    """
    try:
        search_params = {}

        # Handle origin city
        if origin_city:
            origin_result = find_location_comprehensive(origin_city, "origin")
            if origin_result["exact_match"]:
                search_params["origin_location_child_id"] = origin_result["exact_match"]["id"]
                print(f"✅ Found origin: {origin_result['exact_match']['name']}")

        # Add other parameters
        if departure_date:
            search_params["origin_date"] = departure_date
        if sort_by:
            search_params["sort"] = sort_by

        # Handle destination search with intelligent fallbacks
        if destination_place:
            location_result = find_location_comprehensive(destination_place, "destination")

            # Strategy 1: Try exact match first
            tours_found = []
            search_strategy = "none"
            searched_location = None

            if location_result["exact_match"]:
                exact_match = location_result["exact_match"]
                tours_result = search_tours_for_location(exact_match["id"], **search_params)

                if tours_result["success"] and tours_result["count"] > 0:
                    tours_found = tours_result["tours"]
                    search_strategy = f"exact_match_{exact_match['type']}"
                    searched_location = exact_match
                    print(f"✅ Found {len(tours_found)} tours for exact match: {exact_match['name']}")

            # Strategy 2: If no tours found and we matched a city, try the country
            if not tours_found and location_result["exact_match"] and location_result["exact_match"]["type"] == "city":
                country_id = location_result["exact_match"].get("country_id")
                if country_id:
                    tours_result = search_tours_for_location(country_id, **search_params)
                    if tours_result["success"] and tours_result["count"] > 0:
                        tours_found = tours_result["tours"]
                        search_strategy = "country_fallback"
                        # Find country info
                        for country in location_result["all_countries"]:
                            if country["id"] == country_id:
                                searched_location = country
                                break
                        print(f"✅ Found {len(tours_found)} tours in country fallback")

            # Strategy 3: If we matched a country but no tours, try its cities
            if not tours_found and location_result["country_match"]:
                country = location_result["country_match"]
                all_country_tours = []
                cities_with_tours = []

                for city in country["cities"]:
                    city_tours_result = search_tours_for_location(city["id"], **search_params)
                    if city_tours_result["success"] and city_tours_result["count"] > 0:
                        all_country_tours.extend(city_tours_result["tours"])
                        cities_with_tours.append(city["name"])

                if all_country_tours:
                    tours_found = all_country_tours
                    search_strategy = "cities_in_country"
                    searched_location = country
                    print(f"✅ Found {len(tours_found)} tours across cities in {country['name']}")

            # Strategy 4: Try city matches if nothing else worked
            if not tours_found and location_result["city_matches"]:
                for city in location_result["city_matches"][:3]:  # Try top 3 matches
                    city_tours_result = search_tours_for_location(city["id"], **search_params)
                    if city_tours_result["success"] and city_tours_result["count"] > 0:
                        tours_found = city_tours_result["tours"]
                        search_strategy = "similar_city"
                        searched_location = city
                        print(f"✅ Found {len(tours_found)} tours for similar city: {city['name']}")
                        break

            # Apply additional filters
            if tours_found:
                filtered_tours = tours_found

                if budget_max:
                    original_count = len(filtered_tours)
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("price") is not None and t.get("price", 0) <= budget_max]
                    print(f"💰 Budget filter: {original_count} -> {len(filtered_tours)} tours")

                if duration_days:
                    original_count = len(filtered_tours)
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("days") is not None and abs(t.get("days", 0) - duration_days) <= 2]
                    print(f"📅 Duration filter: {original_count} -> {len(filtered_tours)} tours")

                # Build suggestions for alternative locations
                suggestions = []
                if search_strategy == "country_fallback":
                    # Suggest specific cities in the country
                    country = searched_location
                    cities_with_tours = []
                    for city in country["cities"]:
                        city_tours_result = search_tours_for_location(city["id"], **search_params)
                        if city_tours_result["success"] and city_tours_result["count"] > 0:
                            cities_with_tours.append(city["name"])
                    suggestions = cities_with_tours[:5]

                return {
                    "status": "success",
                    "count": len(filtered_tours),
                    "tours": filtered_tours[:10],
                    "search_strategy": search_strategy,
                    "searched_location": searched_location["name"] if searched_location else None,
                    "searched_location_type": searched_location["type"] if searched_location else None,
                    "suggestions": suggestions,
                    "has_more": len(filtered_tours) > 10,
                    "message": _build_search_message(search_strategy, searched_location, len(filtered_tours),
                                                          destination_place)
                }
            else:
                # No tours found - provide helpful suggestions
                suggestions = []
                if location_result["country_match"]:
                    # Suggest cities in the matched country
                    suggestions = [city["name"] for city in location_result["country_match"]["cities"][:5]]
                elif location_result["city_matches"]:
                    # Suggest similar cities
                    suggestions = [city["name"] for city in location_result["city_matches"][:5]]
                else:
                    # Suggest popular destinations
                    popular_countries = ["Turkiya", "BAA", "Tailand", "Misr", "Gruziya"]
                    suggestions = popular_countries

                return {
                    "status": "no_tours_found",
                    "count": 0,
                    "tours": [],
                    "searched_for": destination_place,
                    "suggestions": suggestions,
                    "message": f"No tours found for '{destination_place}'. Try these destinations: {', '.join(suggestions)}"
                }

        else:
            # No destination specified, search all
            response = requests.get(f"{TURTOPAR_API_BASE}/tours", params=search_params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    tours = data.get("data", [])
                    return {
                        "status": "success",
                        "count": len(tours),
                        "tours": tours[:10],
                        "message": f"Found {len(tours)} tours available"
                    }

        return {
            "status": "error",
            "message": "Failed to search tours",
            "tours": [],
            "count": 0
        }

    except Exception as e:
        print(f"💥 Search error: {str(e)}")
        return {
            "status": "error",
            "message": f"Search error: {str(e)}",
            "tours": [],
            "count": 0
        }


@tool
def search_tours(
        origin_city: Optional[str] = None,
        destination_place: Optional[str] = None,
        departure_date: Optional[str] = None,
        budget_max: Optional[int] = None,
        duration_days: Optional[int] = None,
        sort_by: str = "price_asc"
) -> Dict[str, Any]:
    """
    Intelligent tour search with hierarchical fallbacks.
    Searches for tours by destination with smart fallbacks.
    """
    try:
        search_params = {}

        # Handle origin city
        if origin_city:
            origin_result = find_location_comprehensive(origin_city, "origin")
            if origin_result["exact_match"]:
                search_params["origin_location_child_id"] = origin_result["exact_match"]["id"]
                print(f"✅ Found origin: {origin_result['exact_match']['name']}")

        # Add other parameters
        if departure_date:
            search_params["origin_date"] = departure_date
        if sort_by:
            search_params["sort"] = sort_by

        # Handle destination search with intelligent fallbacks
        if destination_place:
            location_result = find_location_comprehensive(destination_place, "destination")

            # Strategy 1: Try exact match first (city or country)
            tours_found = []
            search_strategy = "none"
            searched_location = None
            original_location = None

            if location_result["exact_match"]:
                exact_match = location_result["exact_match"]
                original_location = exact_match
                tours_result = search_tours_for_location(exact_match["id"], **search_params)

                if tours_result["success"] and tours_result["count"] > 0:
                    tours_found = tours_result["tours"]
                    search_strategy = f"exact_match_{exact_match['type']}"
                    searched_location = exact_match
                    print(f"✅ Found {len(tours_found)} tours for exact match: {exact_match['name']}")

            # Strategy 2: If exact match was a city but no tours found, try the parent country
            if not tours_found and location_result["exact_match"] and location_result["exact_match"]["type"] == "city":
                city = location_result["exact_match"]
                country_id = city.get("country_id")
                country_name = city.get("country")

                if country_id:
                    print(f"🔄 No tours found for {city['name']}, trying parent country {country_name}")
                    tours_result = search_tours_for_location(country_id, **search_params)

                    if tours_result["success"] and tours_result["count"] > 0:
                        tours_found = tours_result["tours"]
                        search_strategy = "country_fallback_from_city"

                        # Find the country info from the results
                        for country in location_result["all_countries"]:
                            if country["id"] == country_id:
                                searched_location = country
                                break

                        print(f"✅ Found {len(tours_found)} tours for parent country: {country_name}")

            # Strategy 3: If we matched a country but no direct tours, search all cities in that country
            if not tours_found and location_result["exact_match"] and location_result["exact_match"][
                "type"] == "country":
                country = location_result["exact_match"]
                all_country_tours = []
                cities_with_tours = []

                print(f"🔍 Searching all cities in {country['name']}")
                for city in country.get("cities", []):
                    city_tours_result = search_tours_for_location(city["id"], **search_params)
                    if city_tours_result["success"] and city_tours_result["count"] > 0:
                        all_country_tours.extend(city_tours_result["tours"])
                        cities_with_tours.append(city["name"])

                if all_country_tours:
                    tours_found = all_country_tours
                    search_strategy = "cities_in_country"
                    searched_location = country
                    print(
                        f"✅ Found {len(tours_found)} tours across {len(cities_with_tours)} cities in {country['name']}")

            # Strategy 4: If we found similar cities, try the first few matches
            if not tours_found and location_result["city_matches"]:
                print(f"🔍 Trying similar city matches")
                for city in location_result["city_matches"][:3]:  # Try top 3 matches
                    city_tours_result = search_tours_for_location(city["id"], **search_params)
                    if city_tours_result["success"] and city_tours_result["count"] > 0:
                        tours_found = city_tours_result["tours"]
                        search_strategy = "similar_city"
                        searched_location = city
                        print(
                            f"✅ Found {len(tours_found)} tours for similar city: {city['name']} in {city.get('country', '')}")
                        break

            # Strategy 5: If we have a country match, try its cities
            if not tours_found and location_result["country_match"]:
                country = location_result["country_match"]
                all_country_tours = []
                cities_with_tours = []

                print(f"🔍 Trying cities in matched country {country['name']}")
                for city in country.get("cities", [])[:5]:  # Limit to first 5 cities
                    city_tours_result = search_tours_for_location(city["id"], **search_params)
                    if city_tours_result["success"] and city_tours_result["count"] > 0:
                        all_country_tours.extend(city_tours_result["tours"])
                        cities_with_tours.append(city["name"])

                if all_country_tours:
                    tours_found = all_country_tours
                    search_strategy = "country_match_cities"
                    searched_location = country
                    print(f"✅ Found {len(tours_found)} tours in {country['name']}")

            # Apply additional filters if tours found
            if tours_found:
                filtered_tours = tours_found

                if budget_max:
                    original_count = len(filtered_tours)
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("price") is not None and t.get("price", 0) <= budget_max]
                    print(f"💰 Budget filter: {original_count} -> {len(filtered_tours)} tours")

                if duration_days:
                    original_count = len(filtered_tours)
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("days") is not None and abs(t.get("days", 0) - duration_days) <= 2]
                    print(f"📅 Duration filter: {original_count} -> {len(filtered_tours)} tours")

                # Build intelligent suggestions based on search strategy
                suggestions = _build_intelligent_suggestions(
                    search_strategy, searched_location, original_location, location_result, search_params
                )

                return {
                    "status": "success",
                    "count": len(filtered_tours),
                    "tours": filtered_tours[:10],
                    "search_strategy": search_strategy,
                    "searched_location": searched_location["name"] if searched_location else None,
                    "searched_location_type": searched_location["type"] if searched_location else None,
                    "original_query": destination_place,
                    "suggestions": suggestions,
                    "has_more": len(filtered_tours) > 10,
                    "message": _build_search_message(search_strategy, searched_location, len(filtered_tours),
                                                     destination_place, original_location)
                }
            else:
                # No tours found anywhere - provide intelligent suggestions
                suggestions = _build_no_tours_suggestions(location_result, destination_place)

                return {
                    "status": "no_tours_found",
                    "count": 0,
                    "tours": [],
                    "searched_for": destination_place,
                    "suggestions": suggestions,
                    "message": f"No tours found for '{destination_place}'. Here are some alternatives: {', '.join(suggestions[:3])}"
                }

        else:
            # No destination specified, search all
            response = requests.get(f"{TURTOPAR_API_BASE}/tours", params=search_params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    tours = data.get("data", [])
                    return {
                        "status": "success",
                        "count": len(tours),
                        "tours": tours[:10],
                        "message": f"Found {len(tours)} tours available"
                    }

        return {
            "status": "error",
            "message": "Failed to search tours",
            "tours": [],
            "count": 0
        }

    except Exception as e:
        print(f"💥 Search error: {str(e)}")
        return {
            "status": "error",
            "message": f"Search error: {str(e)}",
            "tours": [],
            "count": 0
        }


def _build_intelligent_suggestions(search_strategy: str, searched_location: Dict, original_location: Dict,
                                   location_result: Dict, search_params: Dict) -> List[str]:
    """Build intelligent suggestions based on the search strategy and results"""
    suggestions = []

    if search_strategy == "country_fallback_from_city":
        # Original search was for a city (e.g., Bali), but we found tours for the country (Indonesia)
        # Suggest other cities in the same country
        country = searched_location
        cities_with_tours = []

        for city in country.get("cities", [])[:8]:  # Check more cities for better suggestions
            if city["name"] != original_location["name"]:  # Don't suggest the original city
                city_tours_result = search_tours_for_location(city["id"], **search_params)
                if city_tours_result["success"] and city_tours_result["count"] > 0:
                    cities_with_tours.append(city["name"])

        suggestions = cities_with_tours[:5]

    elif search_strategy in ["cities_in_country", "country_match_cities"]:
        # We found tours across multiple cities in a country
        country = searched_location
        suggestions = [city["name"] for city in country.get("cities", [])[:5]]

    elif search_strategy == "similar_city":
        # We found a similar city, suggest other cities in the same country
        city = searched_location
        country_name = city.get("country")
        if country_name:
            # Find other cities in the same country
            for country in location_result.get("all_countries", []):
                if country["name"] == country_name:
                    suggestions = [c["name"] for c in country["cities"][:4] if c["name"] != city["name"]]
                    break

    return suggestions


def _build_no_tours_suggestions(location_result: Dict, original_query: str) -> List[str]:
    """Build suggestions when no tours are found"""
    suggestions = []

    if location_result["exact_match"] and location_result["exact_match"]["type"] == "city":
        # User searched for a specific city, suggest other cities in the same country
        city = location_result["exact_match"]
        country_name = city.get("country")

        if country_name:
            # Find other cities in the same country
            for country in location_result.get("all_countries", []):
                if country["name"] == country_name:
                    other_cities = [c["name"] for c in country["cities"][:5] if c["name"] != city["name"]]
                    suggestions.extend(other_cities)
                    break

        # If still no suggestions, add the country itself
        if not suggestions and country_name:
            suggestions.append(country_name)

    elif location_result["country_match"]:
        # User searched for a country, suggest popular cities in that country
        country = location_result["country_match"]
        suggestions = [city["name"] for city in country["cities"][:5]]

    elif location_result["city_matches"]:
        # User search matched similar cities, suggest them
        suggestions = [city["name"] for city in location_result["city_matches"][:4]]
        # Add their countries too
        for city in location_result["city_matches"][:2]:
            if city.get("country") and city["country"] not in suggestions:
                suggestions.append(city["country"])

    # If still no suggestions, add popular destinations
    if not suggestions:
        suggestions = ["Turkiya", "BAA", "Tailand", "Misr", "Gruziya", "Indoneziya"]

    return suggestions[:6]  # Limit to 6 suggestions


def _build_search_message(search_strategy: str, searched_location: Dict, tour_count: int,
                          original_query: str, original_location: Dict = None) -> str:
    """Build a descriptive message about the search results"""
    if not searched_location:
        return f"Found {tour_count} tours"

    location_name = searched_location["name"]

    if search_strategy == "exact_match_city":
        return f"Found {tour_count} tours to {location_name}"
    elif search_strategy == "exact_match_country":
        return f"Found {tour_count} tours to {location_name}"
    elif search_strategy == "country_fallback_from_city":
        original_name = original_location["name"] if original_location else original_query
        return f"No specific tours to {original_name}, but found {tour_count} tours to {location_name}. Check the suggestions for specific cities."
    elif search_strategy == "cities_in_country":
        return f"Found {tour_count} tours across various cities in {location_name}"
    elif search_strategy == "country_match_cities":
        return f"Found {tour_count} tours in {location_name} (matched from your search)"
    elif search_strategy == "similar_city":
        return f"Found {tour_count} tours to {location_name} (similar to '{original_query}')"
    else:
        return f"Found {tour_count} tours"

# Keep the other existing tools unchanged
@tool
def get_tour_details(tour_slug: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific tour using its slug.
    """
    try:
        print(f"🔍 Fetching detailed tour info for: {tour_slug}")

        response = requests.get(f"{TURTOPAR_API_BASE}/tours/view/{tour_slug}", timeout=15)

        if response.status_code == 200:
            data = response.json()

            if data.get("success"):
                tour_data = data.get("data", {})

                tour_info = {
                    "status": "success",
                    "tour_details": {
                        "id": tour_data.get("id"),
                        "name": tour_data.get("name"),
                        "description": tour_data.get("description"),
                        "price": tour_data.get("price"),
                        "currency": tour_data.get("currency", "USD"),
                        "duration": {
                            "days": tour_data.get("days"),
                            "nights": tour_data.get("nights")
                        },
                        "dates": {
                            "from": tour_data.get("from_date"),
                            "to": tour_data.get("to_date")
                        },
                        "is_hot": tour_data.get("is_hot", False),
                        "images": tour_data.get("images", []),
                        "locations": tour_data.get("locations", [])
                    },
                    "hotels": [],
                    "organization": tour_data.get("organization", {}),
                    "contact_info": {
                        "responsible_person": tour_data.get("responsible_user", {}),
                        "organization": tour_data.get("organization", {}),
                        "contact_phone": tour_data.get("contact_phone")
                    },
                    "features": tour_data.get("features", []),
                    "facilities": tour_data.get("facilities", []),
                    "schedules": tour_data.get("schedules", []),
                    "meta_data": tour_data.get("meta_data", {})
                }

                # Extract hotel information
                for location in tour_data.get("locations", []):
                    for hotel in location.get("hotels", []):
                        tour_info["hotels"].append({
                            "name": hotel.get("hotel_name"),
                            "stars": hotel.get("stars"),
                            "price": hotel.get("price"),
                            "currency": hotel.get("currency", "USD"),
                            "nights": hotel.get("nights"),
                            "image": hotel.get("image"),
                            "features": hotel.get("features", []),
                            "location": hotel.get("location_name")
                        })

                return tour_info

        return {
            "status": "error",
            "message": "Tour details not found",
            "tour_details": {}
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error fetching tour details: {str(e)}",
            "tour_details": {}
        }


@tool
def get_tour_recommendations(
        interests: List[str],
        budget_range: Optional[str] = None,
        travel_style: Optional[str] = None,
        season: Optional[str] = None,
        origin_city: Optional[str] = "Toshkent"
) -> Dict[str, Any]:
    """
    Get personalized tour recommendations based on customer interests and preferences.
    """
    # Interest to destination mapping
    interest_destinations = {
        "beach": ["Antaliya", "Dubai", "Sharm al-Shayx", "Pxuket", "Bali", "Male"],
        "luxury": ["Dubai", "Abu-Dabi", "Parij", "Maldiv orollari"],
        "culture": ["Istanbul", "Buxoro", "Samarqand", "Parij", "Anqara"],
        "adventure": ["Kappadokiya", "Trabzon", "Gruziya", "Vetnam", "Xitoy"],
        "family": ["Antaliya", "Dubai", "Istanbul", "Tailand", "BAA"],
        "shopping": ["Dubai", "Istanbul", "Bangkok", "Kuala-Lumpur"],
        "food": ["Istanbul", "Bangkok", "Vetnam", "Malayziya"],
        "history": ["Turkiya", "Misr", "Gruziya", "Uzbekiston"],
        "romance": ["Parij", "Maldiv orollari", "Istanbul", "Bali"],
        "nature": ["Kappadokiya", "Gruziya", "Vetnam", "Malayziya", "Indoneziya"],
        "religious": ["Saudiya Arabistoni", "Turkiya", "Misr"],
        "wellness": ["Tailand", "Bali", "Gruziya", "Turkiya"]
    }

    budget_ranges = {
        "budget": (0, 500),
        "mid-range": (500, 1000),
        "luxury": (1000, 5000)
    }

    try:
        # Find recommended destinations based on interests
        recommended_places = []
        for interest in interests:
            interest_lower = interest.lower()
            for key, places in interest_destinations.items():
                if key in interest_lower or interest_lower in key:
                    recommended_places.extend(places)

        # Remove duplicates and get unique recommendations
        unique_places = list(set(recommended_places))

        # Search for tours to recommended destinations
        all_recommended_tours = []

        for place in unique_places[:5]:  # Limit to top 5 destinations
            search_result = search_tours(
                origin_city=origin_city,
                destination_place=place,
                sort_by="price_asc"
            )

            if search_result.get("status") == "success":
                tours = search_result.get("tours", [])

                # Apply budget filter
                if budget_range and budget_range.lower() in budget_ranges:
                    min_price, max_price = budget_ranges[budget_range.lower()]
                    tours = [t for t in tours if min_price <= t.get("price", 0) <= max_price]

                all_recommended_tours.extend(tours)

        # Sort by price and remove duplicates
        unique_tours = {tour["id"]: tour for tour in all_recommended_tours}.values()
        sorted_tours = sorted(unique_tours, key=lambda x: x.get("price", 0))

        return {
            "status": "success",
            "recommendations": list(sorted_tours)[:8],
            "based_on": {
                "interests": interests,
                "budget_range": budget_range,
                "travel_style": travel_style,
                "season": season
            },
            "recommended_destinations": unique_places[:5],
            "message": f"Found {len(sorted_tours)} tours matching your interests: {', '.join(interests)}"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Recommendation error: {str(e)}",
            "recommendations": []
        }


@tool
def get_popular_destinations() -> Dict[str, Any]:
    """Get list of popular travel destinations with brief descriptions."""
    popular_destinations = {
        "Turkiya": {
            "cities": ["Istanbul", "Antaliya", "Kappadokiya", "Bodrum"],
            "highlights": ["Rich history", "Beautiful beaches", "Affordable luxury", "Amazing cuisine"],
            "best_for": ["Culture", "Beach", "Family", "History"],
            "season": "March-November"
        },
        "BAA": {
            "cities": ["Dubai", "Abu-Dabi", "Sharja"],
            "highlights": ["Modern luxury", "Shopping", "Desert safari", "World-class hotels"],
            "best_for": ["Luxury", "Shopping", "Modern architecture", "Adventure"],
            "season": "October-April"
        },
        "Tailand": {
            "cities": ["Pxuket", "Bangkok", "Pattaya"],
            "highlights": ["Tropical paradise", "Thai massage", "Street food", "Temples"],
            "best_for": ["Beach", "Wellness", "Food", "Adventure"],
            "season": "November-March"
        },
        "Misr": {
            "cities": ["Sharm al-Shayx", "Hurghada"],
            "highlights": ["Red Sea diving", "Ancient history", "Affordable beach resort"],
            "best_for": ["Beach", "Diving", "History", "Budget"],
            "season": "September-May"
        },
        "Gruziya": {
            "cities": ["Tbilisi", "Batumi"],
            "highlights": ["Wine country", "Mountain beauty", "Friendly people", "Great food"],
            "best_for": ["Culture", "Nature", "Food", "Adventure"],
            "season": "April-October"
        },
        "Maldiv orollari": {
            "cities": ["Male", "Bodufoludo"],
            "highlights": ["Overwater bungalows", "Crystal clear waters", "Luxury resorts"],
            "best_for": ["Romance", "Luxury", "Beach", "Honeymoon"],
            "season": "November-April"
        }
    }

    return {
        "status": "success",
        "destinations": popular_destinations,
        "message": "Here are our most popular destinations with their highlights"
    }


@tool
def format_tour_details(tour_data: Dict[str, Any]) -> str:
    """Format tour information for easy reading."""
    tour = tour_data

    details = f"""
🌟 **{tour.get('name', 'Tour Package')}**
📍 **Destination:** {tour.get('locations', 'Multiple locations')}
🏢 **Operator:** {tour.get('organization_name', 'Tour Company')}

💰 **Price:** ${tour.get('price', 0)} USD
⏱️ **Duration:** {tour.get('days', 0)} days / {tour.get('nights', 0)} nights
📅 **Dates:** {tour.get('from_date', '')} - {tour.get('to_date', '')}
🆔 **Tour ID:** {tour.get('slug', 'N/A')}

📝 **Description:**
{tour.get('description', 'Full tour package with accommodation, transfers and guided tours.')}

✨ **Included Features:**"""

    features = tour.get('features', [])
    if features:
        for feature in features:
            details += f"\n• {feature.get('name', 'Tour service')}"
    else:
        details += "\n• Accommodation\n• Airport transfers\n• Tour guide\n• Selected meals"

    details += f"\n\n**📞 For more details and booking, use the tour slug: {tour.get('slug', 'contact-agent')}**"

    return details