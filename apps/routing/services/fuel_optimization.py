from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt
from typing import Any

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import LineString
from django.contrib.gis.measure import D

from apps.fuel.models import FuelStation
from apps.routing.constants import FUEL_EFFICIENCY_MPG, MAX_VEHICLE_RANGE_MILES, SEARCH_RADIUS_MILES


class FuelOptimizationError(Exception):
    """Raised when fuel stops cannot be calculated from available station data."""


@dataclass(frozen=True)
class CandidateStation:
    id: int
    truckstop_id: str
    name: str
    address: str
    city: str
    state: str
    retail_price: Decimal
    latitude: float
    longitude: float
    distance_along_route_miles: float
    distance_from_route_miles: float


@dataclass(frozen=True)
class FuelPlan:
    fuel_stops: list[dict[str, Any]]
    total_fuel_cost: Decimal


@dataclass(frozen=True)
class RouteNode:
    kind: str
    distance_along_route_miles: float
    price: Decimal
    station: CandidateStation | None = None


class FuelOptimizationService:
    def optimize(self, route: Any) -> FuelPlan:
        coordinates = self._extract_coordinates(route.geometry)
        route_distances = self._calculate_cumulative_distances(coordinates)
        candidates = self._find_candidate_stations(
            coordinates,
            route_distances,
        )

        if route.distance_miles <= MAX_VEHICLE_RANGE_MILES and not candidates:
            return FuelPlan(fuel_stops=[], total_fuel_cost=Decimal("0.00"))

        path = self._find_optimal_path(
            candidates=sorted(
                candidates,
                key=lambda station: station.distance_along_route_miles,
            ),
            total_distance_miles=route.distance_miles,
        )

        return self._build_fuel_plan(path)

    def _extract_coordinates(self, geometry):
        if geometry.get("type") != "LineString":
            raise FuelOptimizationError("Route geometry must be a GeoJSON LineString.")

        coordinates = geometry.get("coordinates") or []

        if len(coordinates) < 2:
            raise FuelOptimizationError("Route geometry must contain at least 2 points.")

        return [(float(latitude), float(longitude)) for longitude, latitude in coordinates]

    def _calculate_cumulative_distances(self, coordinates):
        distances = [0.0]

        for index in range(1, len(coordinates)):
            distances.append(
                distances[-1]
                + self._haversine_miles(coordinates[index - 1], coordinates[index])
            )

        return distances

    def _find_candidate_stations(self, coordinates, route_distances):
        route_line = LineString(
            [(longitude, latitude) for latitude, longitude in coordinates],
            srid=4326,
        )

        stations = FuelStation.objects.filter(
            location__isnull=False,
            location__distance_lte=(route_line, D(mi=SEARCH_RADIUS_MILES)),
        ).annotate(
            distance_from_route=Distance("location", route_line),
        ).only(
            "id",
            "truckstop_id",
            "name",
            "address",
            "city",
            "state",
            "retail_price",
            "latitude",
            "longitude",
        )

        candidates = []

        for station in stations:
            projected = self._project_station_onto_route(
                station_latitude=float(station.latitude),
                station_longitude=float(station.longitude),
                coordinates=coordinates,
                route_distances=route_distances,
            )

            candidates.append(
                CandidateStation(
                    id=station.id,
                    truckstop_id=station.truckstop_id,
                    name=station.name,
                    address=station.address,
                    city=station.city,
                    state=station.state,
                    retail_price=station.retail_price,
                    latitude=float(station.latitude),
                    longitude=float(station.longitude),
                    distance_along_route_miles=projected["distance_along_route_miles"],
                    distance_from_route_miles=station.distance_from_route.mi,
                )
            )

        return candidates

    def _find_optimal_path(self, candidates, total_distance_miles):
        nodes = [
            RouteNode(
                kind="start",
                distance_along_route_miles=0.0,
                price=Decimal("0"),
            ),
            *[
                RouteNode(
                    kind="station",
                    distance_along_route_miles=station.distance_along_route_miles,
                    price=station.retail_price,
                    station=station,
                )
                for station in candidates
            ],
            RouteNode(
                kind="destination",
                distance_along_route_miles=total_distance_miles,
                price=Decimal("0"),
            ),
        ]

        best_costs: list[Decimal | None] = [None] * len(nodes)
        previous_nodes: list[int | None] = [None] * len(nodes)
        best_costs[0] = Decimal("0")

        for index, current_node in enumerate(nodes[:-1]):
            current_cost = best_costs[index]

            if current_cost is None:
                continue

            next_index = index + 1
            while next_index < len(nodes):
                next_node = nodes[next_index]
                distance_delta = (
                    next_node.distance_along_route_miles
                    - current_node.distance_along_route_miles
                )

                if distance_delta > MAX_VEHICLE_RANGE_MILES:
                    break

                transition_cost = self._calculate_transition_cost(
                    current_node=current_node,
                    next_node=next_node,
                )
                candidate_cost = current_cost + transition_cost

                if best_costs[next_index] is None or candidate_cost < best_costs[next_index]:
                    best_costs[next_index] = candidate_cost
                    previous_nodes[next_index] = index

                next_index += 1

        if best_costs[-1] is None:
            raise FuelOptimizationError(
                "No fuel station is available within the vehicle range."
            )

        path = []
        current_index: int | None = len(nodes) - 1

        while current_index is not None:
            path.append(nodes[current_index])
            current_index = previous_nodes[current_index]

        return list(reversed(path))

    def _calculate_transition_cost(self, current_node, next_node):
        if current_node.kind == "start":
            return Decimal("0")

        segment_miles = Decimal(
            str(
                next_node.distance_along_route_miles
                - current_node.distance_along_route_miles
            )
        )
        return segment_miles / Decimal(str(FUEL_EFFICIENCY_MPG)) * current_node.price

    def _build_fuel_plan(self, path):
        fuel_stops = []
        total_cost = Decimal("0")

        for index, current_node in enumerate(path[:-1]):
            if current_node.kind != "station":
                continue

            next_node = path[index + 1]
            leg_miles = Decimal(
                str(
                    next_node.distance_along_route_miles
                    - current_node.distance_along_route_miles
                )
            )
            gallons = leg_miles / Decimal(str(FUEL_EFFICIENCY_MPG))
            estimated_cost = (gallons * current_node.price).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            total_cost += estimated_cost
            station = current_node.station

            fuel_stops.append(
                {
                    "truckstop_id": station.truckstop_id,
                    "name": station.name,
                    "address": station.address,
                    "city": station.city,
                    "state": station.state,
                    "retail_price": station.retail_price,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "distance_along_route_miles": round(
                        station.distance_along_route_miles,
                        2,
                    ),
                    "distance_from_route_miles": round(
                        station.distance_from_route_miles,
                        2,
                    ),
                    "gallons": gallons.quantize(Decimal("0.01")),
                    "estimated_cost": estimated_cost,
                }
            )

        return FuelPlan(
            fuel_stops=fuel_stops,
            total_fuel_cost=total_cost.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            ),
        )

    def _project_station_onto_route(
        self,
        station_latitude,
        station_longitude,
        coordinates,
        route_distances,
    ):
        best_distance_from_route = float("inf")
        best_distance_along_route = 0.0

        for index in range(1, len(coordinates)):
            start = coordinates[index - 1]
            end = coordinates[index]
            segment_projection = self._project_point_to_segment(
                point=(station_latitude, station_longitude),
                start=start,
                end=end,
            )

            if segment_projection["distance_from_segment"] < best_distance_from_route:
                segment_length = route_distances[index] - route_distances[index - 1]
                best_distance_from_route = segment_projection["distance_from_segment"]
                best_distance_along_route = (
                    route_distances[index - 1]
                    + segment_projection["fraction_along_segment"] * segment_length
                )

        return {
            "distance_along_route_miles": best_distance_along_route,
            "distance_from_route_miles": best_distance_from_route,
        }

    def _project_point_to_segment(self, point, start, end):
        origin_latitude = radians(point[0])
        point_x, point_y = self._to_local_miles(point, origin_latitude)
        start_x, start_y = self._to_local_miles(start, origin_latitude)
        end_x, end_y = self._to_local_miles(end, origin_latitude)

        segment_x = end_x - start_x
        segment_y = end_y - start_y
        segment_length_squared = segment_x**2 + segment_y**2

        if segment_length_squared == 0:
            fraction = 0.0
        else:
            fraction = (
                ((point_x - start_x) * segment_x + (point_y - start_y) * segment_y)
                / segment_length_squared
            )
            fraction = max(0.0, min(1.0, fraction))

        closest_x = start_x + fraction * segment_x
        closest_y = start_y + fraction * segment_y

        return {
            "fraction_along_segment": fraction,
            "distance_from_segment": sqrt(
                (point_x - closest_x) ** 2 + (point_y - closest_y) ** 2
            ),
        }

    def _to_local_miles(self, coordinate, origin_latitude):
        latitude, longitude = coordinate
        x = radians(longitude) * cos(origin_latitude) * 3958.7613
        y = radians(latitude) * 3958.7613
        return x, y

    def _haversine_miles(self, start, end):
        start_latitude, start_longitude = start
        end_latitude, end_longitude = end
        radius_miles = 3958.7613

        delta_latitude = radians(end_latitude - start_latitude)
        delta_longitude = radians(end_longitude - start_longitude)

        a = (
            sin(delta_latitude / 2) ** 2
            + cos(radians(start_latitude))
            * cos(radians(end_latitude))
            * sin(delta_longitude / 2) ** 2
        )
        return 2 * radius_miles * asin(sqrt(a))
