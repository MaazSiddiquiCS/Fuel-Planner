from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.routing.services.fuel_optimization import (
    CandidateStation,
    FuelOptimizationService,
)


class FuelOptimizationServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = FuelOptimizationService()
        self.route = SimpleNamespace(
            distance_miles=900.0,
            geometry={
                "type": "LineString",
                "coordinates": [[-100.0, 30.0], [-95.0, 35.0]],
            },
        )

    def test_optimize_prefers_the_cheapest_feasible_station_path(self):
        candidates = [
            CandidateStation(
                id=1,
                truckstop_id="1",
                name="Midpoint Fuel",
                address="1 Route",
                city="Testville",
                state="TX",
                retail_price=Decimal("4.500"),
                latitude=31.0,
                longitude=-99.0,
                distance_along_route_miles=250.0,
                distance_from_route_miles=1.0,
            ),
            CandidateStation(
                id=2,
                truckstop_id="2",
                name="Cheaper Fuel",
                address="2 Route",
                city="Testville",
                state="TX",
                retail_price=Decimal("3.000"),
                latitude=32.0,
                longitude=-98.0,
                distance_along_route_miles=450.0,
                distance_from_route_miles=1.0,
            ),
        ]

        with patch.object(
            self.service,
            "_find_candidate_stations",
            return_value=candidates,
        ):
            plan = self.service.optimize(self.route)

        self.assertEqual([stop["truckstop_id"] for stop in plan.fuel_stops], ["2"])
        self.assertEqual(plan.total_fuel_cost, Decimal("135.00"))

    def test_optimize_returns_empty_plan_for_short_route_without_stops(self):
        short_route = SimpleNamespace(
            distance_miles=300.0,
            geometry={
                "type": "LineString",
                "coordinates": [[-100.0, 30.0], [-99.0, 31.0]],
            },
        )

        with patch.object(
            self.service,
            "_find_candidate_stations",
            return_value=[],
        ):
            plan = self.service.optimize(short_route)

        self.assertEqual(plan.fuel_stops, [])
        self.assertEqual(plan.total_fuel_cost, Decimal("0.00"))