from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.routing.clients.routing_provider import LocationNotFoundError
from apps.routing.views import RoutePlanAPIView


class RoutePlanAPIViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(OPENROUTESERVICE_API_KEY="test-key")
    def test_returns_400_for_unresolvable_location(self):
        request = self.factory.post(
            "/api/routes/plan/",
            {
                "start_location": "nowhere in usa",
                "finish_location": "Chicago, IL",
            },
            format="json",
        )

        with patch(
            "apps.routing.views.RoutePlanningService.plan_route",
            side_effect=LocationNotFoundError("Could not geocode location: nowhere in usa"),
        ):
            response = RoutePlanAPIView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Could not geocode location: nowhere in usa")