import requests
from typing import Optional, Dict, Any, List
from datetime import datetime


class TurtoparAPI:
    def __init__(self, base_url: str = "https://api.turtopar.uz/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to the API endpoint"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "data": []
            }

    def get_all_locations(self, with_children: bool = True) -> Dict[str, Any]:
        """
        Get all available locations (countries and cities)

        Args:
            with_children: Include child locations (cities under countries)

        Returns:
            Full JSON response with all locations
        """
        params = {}
        if with_children:
            params['with_child'] = 1

        return self._make_request("locations", params)

    def get_origin_locations(self) -> Dict[str, Any]:
        """
        Get available origin locations (departure cities in Uzbekistan)

        Returns:
            Full JSON response with origin locations
        """
        return self._make_request("locations/origin-locations")

    def search_tours(self,
                     origin_location_id: Optional[int] = None,
                     destination_location_id: Optional[int] = None,
                     departure_date: Optional[str] = None,
                     return_date: Optional[str] = None,
                     min_price: Optional[int] = None,
                     max_price: Optional[int] = None,
                     currency: Optional[str] = None,
                     sort_by: Optional[str] = None,
                     page: int = 1,
                     per_page: int = 16) -> Dict[str, Any]:
        """
        Search tours with comprehensive filters

        Args:
            origin_location_id: ID of departure city
            destination_location_id: ID of destination city
            departure_date: Date in DD.MM.YYYY format
            return_date: Return date in DD.MM.YYYY format
            min_price: Minimum price filter
            max_price: Maximum price filter
            currency: Currency code (USD, UZS, etc.)
            sort_by: Sort option (price_asc, price_desc, date_asc, date_desc)
            page: Page number for pagination
            per_page: Items per page

        Returns:
            Full JSON response with tour search results
        """
        params = {}

        if origin_location_id:
            params['origin_location_child_id'] = origin_location_id
        if destination_location_id:
            params['destination_location_child_id'] = destination_location_id
        if departure_date:
            params['origin_date'] = departure_date
        if return_date:
            params['return_date'] = return_date
        if min_price:
            params['min_price'] = min_price
        if max_price:
            params['max_price'] = max_price
        if currency:
            params['currency'] = currency
        if sort_by:
            params['sort'] = sort_by
        if page != 1:
            params['page'] = page
        if per_page != 16:
            params['per_page'] = per_page

        return self._make_request("tours", params)

    def find_tours_by_names(self,
                            origin_city_name: str,
                            destination_city_name: str,
                            departure_date: Optional[str] = None,
                            sort_by: str = "price_asc") -> Dict[str, Any]:
        """
        Find tours by city names (helper function)

        Args:
            origin_city_name: Name of departure city (e.g., "Toshkent")
            destination_city_name: Name of destination city (e.g., "Dubay")
            departure_date: Date in DD.MM.YYYY format
            sort_by: Sort option

        Returns:
            Full JSON response with tour search results
        """
        # Get all locations to find IDs
        locations = self.get_all_locations()

        origin_id = None
        destination_id = None

        if locations.get('success'):
            for country in locations['data']:
                if 'children' in country:
                    for city in country['children']:
                        if city['name'].lower() == origin_city_name.lower():
                            origin_id = city['id']
                        if city['name'].lower() == destination_city_name.lower():
                            destination_id = city['id']

        if not origin_id or not destination_id:
            return {
                "success": False,
                "error": f"Could not find city IDs for {origin_city_name} or {destination_city_name}",
                "data": []
            }

        return self.search_tours(
            origin_location_id=origin_id,
            destination_location_id=destination_id,
            departure_date=departure_date,
            sort_by=sort_by
        )

    def get_tours_to_dubai_from_tashkent(self,
                                         departure_date: Optional[str] = None,
                                         sort_by: str = "price_asc") -> Dict[str, Any]:
        """
        Quick helper to get Dubai tours from Tashkent

        Args:
            departure_date: Date in DD.MM.YYYY format
            sort_by: Sort option

        Returns:
            Full JSON response with Dubai tour results
        """
        return self.search_tours(
            origin_location_id=3,  # Toshkent
            destination_location_id=13,  # Dubai
            departure_date=departure_date,
            sort_by=sort_by
        )


# Example usage functions
def main():
    """Example usage of the TurtoparAPI class"""

    api = TurtoparAPI()

    # Get all locations
    print("=== ALL LOCATIONS ===")
    locations = api.get_all_locations()
    print(f"Success: {locations['success']}")
    print(f"Number of countries: {len(locations['data']) if locations['success'] else 0}")

    # Get origin locations
    print("\n=== ORIGIN LOCATIONS ===")
    origins = api.get_origin_locations()
    print(f"Success: {origins['success']}")
    print(f"Number of origin cities: {len(origins['data']) if origins['success'] else 0}")

    # Search tours from Tashkent to Dubai
    print("\n=== TOURS TASHKENT TO DUBAI ===")
    tours = api.get_tours_to_dubai_from_tashkent(
        departure_date="30.08.2025",
        sort_by="price_asc"
    )
    print(f"Success: {tours['success']}")
    print(f"Number of tours found: {tours['links']['count'] if tours['success'] else 0}")

    # Search by city names
    print("\n=== SEARCH BY CITY NAMES ===")
    tours_by_name = api.find_tours_by_names(
        origin_city_name="Toshkent",
        destination_city_name="Istanbul",
        departure_date="30.08.2025"
    )
    print(f"Success: {tours_by_name['success']}")

    # Advanced filtered search
    print("\n=== ADVANCED FILTERED SEARCH ===")
    filtered_tours = api.search_tours(
        origin_location_id=3,  # Tashkent
        destination_location_id=13,  # Dubai
        departure_date="01.09.2025",
        min_price=300,
        max_price=600,
        currency="USD",
        sort_by="price_asc"
    )
    print(f"Success: {filtered_tours['success']}")
    print(f"Tours in price range: {filtered_tours['links']['count'] if filtered_tours['success'] else 0}")

    return {
        'locations': locations,
        'origins': origins,
        'tours': tours,
        'tours_by_name': tours_by_name,
        'filtered_tours': filtered_tours
    }


if __name__ == "__main__":
    results = main()

    # Print first tour example if available
    if results['tours']['success'] and results['tours']['data']:
        print("\n=== EXAMPLE TOUR ===")
        first_tour = results['tours']['data'][0]
        print(f"Name: {first_tour['name']}")
        print(f"Price: {first_tour['price']} {first_tour['currency']}")
        print(f"Duration: {first_tour['days']} days / {first_tour['nights']} nights")
        print(f"Dates: {first_tour['from_date']} - {first_tour['to_date']}")