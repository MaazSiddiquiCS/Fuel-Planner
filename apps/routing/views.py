from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.routing.clients.routing_provider import (
    LocationNotFoundError,
    RoutingProviderClient,
    RoutingProviderError,
)
from apps.routing.serializers import (
    RoutePlanRequestSerializer,
    RoutePlanResponseSerializer,
)
from apps.routing.services.fuel_optimization import (
    FuelOptimizationError,
    FuelOptimizationService,
)
from apps.routing.services.route_planning import RoutePlanningService


class RoutePlanAPIView(APIView):
    def post(self, request):
        request_serializer = RoutePlanRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        try:
            route_planning_service = RoutePlanningService(
                routing_client=RoutingProviderClient(
                    api_key=settings.OPENROUTESERVICE_API_KEY,
                ),
                fuel_optimization_service=FuelOptimizationService(),
            )
            result = route_planning_service.plan_route(
                start_location=request_serializer.validated_data["start_location"],
                finish_location=request_serializer.validated_data["finish_location"],
            )
        except LocationNotFoundError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (RoutingProviderError, FuelOptimizationError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_serializer = RoutePlanResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
