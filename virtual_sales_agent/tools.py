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
# Complete transliteration mapping for all locations in your API
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
    'turkiya': 'турция',  # Main country name from your API
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
    'baa': 'оаэ',  # From your API "BAA"
    'uae': 'оаэ',
    'emirates': 'оаэ',

    # Egypt
    'misr': 'египет',  # From your API "Misr"
    'egypt': 'египет',

    # Thailand
    'tailand': 'таиланд',  # From your API "Tailand"
    'thailand': 'таиланд',

    # Malaysia
    'malayziya': 'малайзия',  # From your API "Malayziya"
    'malaysia': 'малайзия',

    # Indonesia
    'indoneziya': 'индонезия',  # From your API "Indoneziya"
    'indonesia': 'индонезия',

    # Maldives
    'maldiv orollari': 'мальдивы',  # From your API "Maldiv orollari"
    'maldiv': 'мальдивы',
    'maldives': 'мальдивы',
    'maldivy': 'мальдивы',

    # India
    'hindiston': 'индия',  # From your API "Hindiston"
    'india': 'индия',

    # Singapore
    'singapur': 'сингапур',  # From your API "Singapur"
    'singapore': 'сингапур',

    # China
    'xitoy': 'китай',  # From your API "Xitoy"
    'china': 'китай',
    'kitay': 'китай',

    # Georgia
    'gruziya': 'грузия',  # From your API "Gruziya"
    'georgia': 'грузия',

    # Vietnam
    'vetnam': 'вьетнам',  # From your API "Vetnam"
    'vietnam': 'вьетнам',

    # Azerbaijan
    'ozarbayjon': 'азербайджан',  # From your API "Ozarbayjon"
    'azerbayjan': 'азербайджан',
    'azerbaijan': 'азербайджан',

    # Qatar (already in English in API)
    'qatar': 'катар',
    'katar': 'катар',

    # Oman
    'ummon sultonligi': 'оман',  # From your API "Ummon Sultonligi"
    'ummon': 'оман',
    'oman': 'оман',

    # Sri Lanka (already mostly English)
    'shri lanka': 'шри-ланка',
    'sri lanka': 'шри-ланка',

    # Kazakhstan
    "qozog'iston": 'казахстан',  # From your API "Qozog'iston"
    'qozogiston': 'казахстан',
    'kazakhstan': 'казахстан',

    # Saudi Arabia
    'saudiya arabistoni': 'саудовская аравия',  # From your API "Saudiya Arabistoni"
    'saudiya': 'саудовская аравия',
    'saudi arabia': 'саудовская аравия',

    # Japan
    'yaponiya': 'япония',  # From your API "Yaponiya"
    'japan': 'япония',

    # === TURKEY CITIES ===
    'istanbul': 'стамбул',
    'marmaris': 'мармарис',
    'kappadokiya': 'каппадокия',
    'cappadocia': 'каппадокия',
    'antaliya': 'анталья',
    'antalya': 'анталья',
    'bodrum': 'бодрум',
    'bursa': 'бурса',
    'dalaman': 'даламан',
    'anqara': 'анкара',  # From your API "Anqara"
    'ankara': 'анкара',
    "sovg'a": 'белек',  # From your API "Sovg'a" -> Belek
    'belek': 'белек',
    'side': 'сиде',
    'izmir': 'измир',
    'kushadasi': 'кушадасы',
    'trabzon': 'трабзон',
    'kemer': 'кемер',
    'alanya': 'аланья',
    'fethiye': 'фетхие',

    # === UAE CITIES ===
    'dubay': 'дубай',  # From your API "Dubay"
    'dubai': 'дубай',
    'abu-dabi': 'абу-даби',  # From your API "Abu-Dabi"
    'abu dhabi': 'абу-даби',
    'sharja': 'шарджа',  # From your API "Sharja"
    'sharjah': 'шарджа',
    'ras-al-xayma': 'рас-эль-хайма',  # From your API "Ras-al-Xayma"
    'ras al khaimah': 'рас-эль-хайма',
    'fujeyra': 'фуджейра',  # From your API "Fujeyra"
    'fujairah': 'фуджейра',

    # === THAILAND CITIES ===
    'pxuket': 'пхукет',  # From your API "Pxuket"
    'phuket': 'пхукет',
    'bangkok': 'бангкок',
    'pattaya': 'паттайя',

    # === EGYPT CITIES ===
    'sharm al-shayx': 'шарм-эль-шейх',  # From your API "Sharm al-Shayx"
    'sharm el sheikh': 'шарм-эль-шейх',
    'hurghada': 'хургада',

    # === MALAYSIA CITIES ===
    'kuala-lumpur': 'куала-лумпур',
    'kuala lumpur': 'куала-лумпур',
    'penang': 'пенанг',
    'langkawi': 'лангкави',
    'ari atollari': 'атоллы ари',  # This seems misplaced in Malaysia data

    # === INDONESIA CITIES ===
    'bali': 'бали',
    'jakarta': 'джакарта',
    'gili trawangan': 'gili trawangan',  # Mixed language entry
    'denpasar': 'денпасар',

    # === MALDIVES CITIES ===
    'male': 'мале',
    'bodufoludo': 'бодафолуду',
    'feridu': 'фериду',
    'maldiva': 'мальдивы',  # Generic Maldives reference
    'todu': 'тодду',
    'shimoliy male atolli': 'north male atoll',  # From your API
    'north male atoll': 'north male atoll',

    # === INDIA CITIES ===
    'goa': 'гоа',
    'dehli': 'дели',  # From your API "Dehli"
    'delhi': 'дели',
    'mumbay': 'мумбаи',  # From your API "Mumbay"
    'mumbai': 'мумбаи',

    # === CHINA CITIES ===
    'pekin': 'пекин',  # From your API "Pekin"
    'beijing': 'пекин',
    'shanxay': 'шанхай',  # From your API "Shanxay"
    'shanghai': 'шанхай',
    'guanchjou': 'гуанчжоу',  # From your API "Guanchjou"
    'guangzhou': 'гуанчжоу',
    'xaynan': 'хайнань',  # From your API "Xaynan"
    'hainan': 'хайнань',
    'sanya': 'санья',

    # === GEORGIA CITIES ===
    'tbilisi': 'тбилиси',
    'borjomi': 'borjomi',  # Mixed entry

    # === VIETNAM CITIES ===
    'fukuok': 'фукуок',  # From your API "Fukuok"
    'phu quoc': 'фукуок',
    'nyachang': 'нячанг',  # From your API "Nyachang"
    'nha trang': 'nha trang',  # Mixed entry in your API
    'nha-trang': 'нячанг',
    'danang': 'дананг',
    'hoi an': 'hoi an',  # Mixed entry in your API
    'kamran': 'камрань',

    # === AZERBAIJAN CITIES ===
    'baku': 'баку',
    'naftalan': 'нафталан',
    'lenkoran': 'ленкорань',

    # === QATAR CITIES ===
    'doha': 'доха',
    'abu samra': 'абу самра',

    # === OMAN CITIES ===
    'maskat': 'маскат',  # From your API "Maskat"
    'muscat': 'маскат',
    'salala': 'салала',  # From your API "Salala"
    'salalah': 'салала',

    # === SRI LANKA CITIES ===
    'shri-lanka': 'шри-ланка',  # Generic reference
    'koggala': 'коггала',

    # === KAZAKHSTAN CITIES ===
    'shymkent': 'шымкент',

    # === SAUDI ARABIA CITIES ===
    'madina': 'медина',  # From your API "Madina"
    'medina': 'медина',
    'jidda': 'джедда',  # From your API "Jidda"
    'jeddah': 'джедда',
    'makka': 'мекка',  # From your API "Makka"
    'mecca': 'мекка',
    'makkah': 'мекка',

    # === JAPAN CITIES ===
    'tokio': 'токио',  # From your API "Tokio"
    'tokyo': 'токио',
    'fukuoka': 'фукуока',

    # === FRANCE CITIES ===
    'parij': 'париж',  # From your API "Parij"
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

    return variants


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


def find_location_by_name(location_name: str, location_type: str = "destination") -> Optional[Dict]:
    """Find location by name with transliteration support"""
    locations = get_origin_locations_data() if location_type == "origin" else get_locations_data()

    if not locations:
        print(f"❌ No {location_type} locations data available")
        return None

    search_variants = normalize_and_transliterate(location_name)
    print(f"🔍 Searching for {location_type}: '{location_name}'")
    print(f"   Search variants: {search_variants}")

    # Create list of all possible locations
    all_locations = []

    if location_type == "destination":
        for country in locations:
            # Add country itself
            country_variants = normalize_and_transliterate(country["name"])
            all_locations.append({
                "id": country["id"],
                "name": country["name"],
                "variants": country_variants,
                "type": "country",
                "data": country
            })

            # Add all cities in country
            for city in country.get("children", []):
                city_variants = normalize_and_transliterate(city["name"])
                all_locations.append({
                    "id": city["id"],
                    "name": city["name"],
                    "variants": city_variants,
                    "type": "city",
                    "data": city,
                    "country": country["name"]
                })
    else:  # origin
        for city in locations:
            city_variants = normalize_and_transliterate(city["name"])
            all_locations.append({
                "id": city["id"],
                "name": city["name"],
                "variants": city_variants,
                "type": "city",
                "data": city
            })

    # Try exact matches with all variants
    for search_variant in search_variants:
        for loc in all_locations:
            for loc_variant in loc["variants"]:
                if search_variant == loc_variant:
                    print(
                        f"✅ Exact match found: {loc['name']} (ID: {loc['id']}) via '{search_variant}' -> '{loc_variant}'")
                    return loc

    # Try partial matches
    for search_variant in search_variants:
        for loc in all_locations:
            for loc_variant in loc["variants"]:
                if search_variant in loc_variant or loc_variant in search_variant:
                    print(
                        f"✅ Partial match found: {loc['name']} (ID: {loc['id']}) via '{search_variant}' <-> '{loc_variant}'")
                    return loc

    print(f"❌ No match found for '{location_name}' with variants {search_variants}")
    return None


@tool
def get_tour_details(tour_slug: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific tour using its slug.
    This provides comprehensive tour details including hotels, pricing, schedules, and contact information.

    Args:
        tour_slug (str): The tour slug identifier (from search results)
    """
    try:
        print(f"🔍 Fetching detailed tour info for: {tour_slug}")

        response = requests.get(f"{TURTOPAR_API_BASE}/tours/view/{tour_slug}", timeout=15)
        print(f"📡 API Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"📊 API Response success: {data.get('success')}")

            if data.get("success"):
                tour_data = data.get("data", {})

                # Format the detailed information
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
            else:
                return {
                    "status": "error",
                    "message": "Tour details not found",
                    "tour_details": {}
                }
        else:
            return {
                "status": "error",
                "message": f"Failed to fetch tour details (HTTP {response.status_code})",
                "tour_details": {}
            }

    except Exception as e:
        print(f"💥 Tour details error: {str(e)}")
        return {
            "status": "error",
            "message": f"Error fetching tour details: {str(e)}",
            "tour_details": {}
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
    Search for tours based on criteria.
    """
    try:
        # Build API parameters
        params = {}

        print(f"🔍 DEBUG: Searching with parameters:")
        print(f"   origin_city: {origin_city}")
        print(f"   destination_place: {destination_place}")
        print(f"   departure_date: {departure_date}")
        print(f"   duration_days: {duration_days}")

        # Find origin location
        if origin_city:
            origin_loc = find_location_by_name(origin_city, "origin")
            if origin_loc:
                params["origin_location_child_id"] = origin_loc["id"]
                print(f"✅ Found origin: {origin_loc['name']} (ID: {origin_loc['id']})")

        # Find destination location
        destination_found = None
        if destination_place:
            dest_loc = find_location_by_name(destination_place, "destination")
            if dest_loc:
                params["destination_location_child_id"] = dest_loc["id"]
                destination_found = dest_loc
                print(f"✅ Found destination: {dest_loc['name']} (ID: {dest_loc['id']})")

        # Add other parameters
        if departure_date:
            params["origin_date"] = departure_date
        if sort_by:
            params["sort"] = sort_by

        print(f"🌐 API Request params: {params}")

        # Make API request
        response = requests.get(f"{TURTOPAR_API_BASE}/tours", params=params, timeout=15)
        print(f"📡 API Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"📊 API Response success: {data.get('success')}")

            if data.get("success"):
                tours = data.get("data", [])
                print(f"🎯 Found {len(tours)} tours from API")

                # Apply additional filters with proper null handling
                filtered_tours = tours
                if budget_max:
                    original_count = len(filtered_tours)
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("price") is not None and t.get("price", 0) <= budget_max]
                    print(f"💰 Budget filter: {original_count} -> {len(filtered_tours)} tours")

                if duration_days:
                    original_count = len(filtered_tours)
                    # Handle None values in days field
                    filtered_tours = [t for t in filtered_tours
                                      if t.get("days") is not None and abs(t.get("days", 0) - duration_days) <= 2]
                    print(f"📅 Duration filter: {original_count} -> {len(filtered_tours)} tours")

                # Log some example tours for debugging
                for i, tour in enumerate(filtered_tours[:3]):
                    tour_days = tour.get('days', 'N/A')
                    tour_price = tour.get('price', 'N/A')
                    tour_slug = tour.get('slug', 'no-slug')
                    print(
                        f"Tour {i + 1}: {tour.get('name', 'Unnamed')} - ${tour_price} - {tour_days} days - slug: {tour_slug}")

                return {
                    "status": "success",
                    "count": len(filtered_tours),
                    "tours": filtered_tours[:10],  # Return top 10
                    "search_params": params,
                    "has_more": len(filtered_tours) > 10,
                    "destination_found": destination_found["name"] if destination_found else None
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
def search_locations(query: str, location_type: str = "destination") -> Dict[str, Any]:
    """
    Search for locations by name. Useful when customer mentions a place name.

    Args:
        query (str): Location name to search for
        location_type (str): Either "origin" (departure cities) or "destination" (travel destinations)
    """
    result = find_location_by_name(query, location_type)

    if result:
        return {
            "status": "found",
            "location": {
                "id": result["id"],
                "name": result["name"],
                "type": result["type"],
                "country": result.get("country", ""),
                "data": result["data"]
            },
            "message": f"Found {result['name']}" + (f" in {result['country']}" if result.get('country') else "")
        }
    else:
        # Provide suggestions if no exact match
        locations = get_locations_data() if location_type == "destination" else get_origin_locations_data()
        suggestions = []

        if location_type == "destination":
            for country in locations[:5]:  # Top 5 countries
                suggestions.append(country["name"])
                suggestions.extend([city["name"] for city in country.get("children", [])[:2]])
        else:
            suggestions = [city["name"] for city in locations[:6]]

        return {
            "status": "not_found",
            "message": f"Could not find '{query}'. Popular destinations include: {', '.join(suggestions[:8])}",
            "suggestions": suggestions[:8]
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

    Args:
        interests (List[str]): Customer interests (beach, culture, adventure, luxury, family, etc.)
        budget_range (str): Budget category - budget, mid-range, luxury
        travel_style (str): Travel style - relaxation, adventure, cultural, romantic, family
        season (str): Preferred season - summer, winter, spring, autumn
        origin_city (str): Departure city
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

    # Season to destination mapping
    season_destinations = {
        "summer": ["Turkiya", "Gruziya", "Evropa"],
        "winter": ["BAA", "Tailand", "Indoneziya", "Maldiv orollari", "Misr"],
        "spring": ["Turkiya", "Gruziya", "BAA", "Vetnam"],
        "autumn": ["BAA", "Turkiya", "Gruziya", "Misr"]
    }

    # Budget to price mapping
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

        # Add seasonal recommendations
        if season:
            season_places = season_destinations.get(season.lower(), [])
            recommended_places.extend(season_places)

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
            "recommendations": sorted_tours[:8],
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