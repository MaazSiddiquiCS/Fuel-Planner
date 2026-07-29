from dataclasses import dataclass
from typing import Any

import requests


class RoutingProviderError(Exception):
    """Raised when the routing provider cannot return a usable route."""


class LocationNotFoundError(RoutingProviderError):
    """Raised when a user-provided location cannot be resolved in the USA."""


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RouteResult:
    distance_miles: float
    duration_seconds: float
    geometry: dict[str, Any]


class RoutingProviderClient:
    BASE_URL = "https://api.openrouteservice.org"
    DIRECTIONS_PATH = "/v2/directions/{profile}/geojson"
    GEOCODE_PATH = "/geocode/search"
    METERS_PER_MILE = 1609.344

    def __init__(
        self,
        api_key: str,
        profile: str = "driving-car",
        timeout_seconds: int = 10,
    ):
        if not api_key:
            raise RoutingProviderError("OpenRouteService API key is not configured.")

        self.api_key = api_key
        self.profile = profile
        self.timeout_seconds = timeout_seconds

    def get_route(
        self,
        start_location: str | Coordinates | tuple[float, float],
        finish_location: str | Coordinates | tuple[float, float],
    ) -> RouteResult:
        start_coordinates = self._resolve_coordinates(start_location)
        finish_coordinates = self._resolve_coordinates(finish_location)

        response_data = self._post_directions(start_coordinates, finish_coordinates)
        return self._parse_route_response(response_data)

    def _resolve_coordinates(
        self,
        location: str | Coordinates | tuple[float, float],
    ) -> Coordinates:
        if isinstance(location, Coordinates):
            return location

        if isinstance(location, tuple):
            latitude, longitude = location
            return Coordinates(latitude=float(latitude), longitude=float(longitude))

        if isinstance(location, str):
            return self._geocode(location)

        raise RoutingProviderError("Location must be an address string or coordinates.")

    def _geocode(self, query: str) -> Coordinates:
        query = query.strip()

        if not query:
            raise LocationNotFoundError("Location query cannot be empty.")

        try:
            response = requests.get(
                f"{self.BASE_URL}{self.GEOCODE_PATH}",
                headers=self._headers,
                params={
                    "text": query,
                    "boundary.country": "USA",
                    "size": 1,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RoutingProviderError("Geocoding provider timed out.") from exc
        except requests.RequestException as exc:
            raise RoutingProviderError("Geocoding provider request failed.") from exc

        data = self._parse_json_response(response)
        features = data.get("features") or []

        if not features:
            raise LocationNotFoundError(f"Could not geocode location: {query}")

        coordinates = features[0].get("geometry", {}).get("coordinates")

        if not self._is_coordinate_pair(coordinates):
            raise RoutingProviderError("Geocoding provider returned invalid coordinates.")

        longitude, latitude = coordinates
        return Coordinates(latitude=float(latitude), longitude=float(longitude))

    def _post_directions(
        self,
        start_coordinates: Coordinates,
        finish_coordinates: Coordinates,
    ) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.BASE_URL}{self.DIRECTIONS_PATH.format(profile=self.profile)}",
                headers=self._headers,
                json={
                    "coordinates": [
                        self._to_ors_coordinates(start_coordinates),
                        self._to_ors_coordinates(finish_coordinates),
                    ],
                    "instructions": False,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RoutingProviderError("Routing provider timed out.") from exc
        except requests.RequestException as exc:
            raise RoutingProviderError("Routing provider request failed.") from exc

        return self._parse_json_response(response)

    def _parse_route_response(self, data: dict[str, Any]) -> RouteResult:
        features = data.get("features") or []

        if not features:
            raise RoutingProviderError("Routing provider returned no routes.")

        route = features[0]
        summary = route.get("properties", {}).get("summary", {})
        geometry = route.get("geometry")

        distance_meters = summary.get("distance")
        duration_seconds = summary.get("duration")

        if distance_meters is None or duration_seconds is None or not geometry:
            raise RoutingProviderError("Routing provider returned an invalid route.")

        return RouteResult(
            distance_miles=round(float(distance_meters) / self.METERS_PER_MILE, 2),
            duration_seconds=float(duration_seconds),
            geometry=geometry,
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Accept": "application/json, application/geo+json",
            "Content-Type": "application/json",
        }

    def _to_ors_coordinates(self, coordinates: Coordinates) -> list[float]:
        return [coordinates.longitude, coordinates.latitude]

    def _is_coordinate_pair(self, value: Any) -> bool:
        return (
            isinstance(value, list)
            and len(value) == 2
            and all(isinstance(item, int | float) for item in value)
        )

    def _parse_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RoutingProviderError("Routing provider returned invalid JSON.") from exc
