from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class RoutingClient(Protocol):
    def get_route(self, start_location: Any, finish_location: Any) -> Any:
        ...


class FuelOptimizationService(Protocol):
    def optimize(self, route: Any) -> Any:
        ...


@dataclass(frozen=True)
class RoutePlanningResult:
    distance_miles: float
    duration_seconds: float
    geometry: dict[str, Any]
    fuel_stops: list[dict[str, Any]]
    total_fuel_cost: Decimal


class RoutePlanningService:
    def __init__(
        self,
        routing_client: RoutingClient,
        fuel_optimization_service: FuelOptimizationService,
    ):
        self.routing_client = routing_client
        self.fuel_optimization_service = fuel_optimization_service

    def plan_route(
        self,
        start_location: Any,
        finish_location: Any,
    ) -> RoutePlanningResult:
        route = self.routing_client.get_route(
            start_location=start_location,
            finish_location=finish_location,
        )
        fuel_plan = self.fuel_optimization_service.optimize(route)

        return RoutePlanningResult(
            distance_miles=route.distance_miles,
            duration_seconds=route.duration_seconds,
            geometry=route.geometry,
            fuel_stops=fuel_plan.fuel_stops,
            total_fuel_cost=fuel_plan.total_fuel_cost,
        )
