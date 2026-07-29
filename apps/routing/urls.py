from django.urls import path

from apps.routing.views import RoutePlanAPIView


urlpatterns = [
    path("plan/", RoutePlanAPIView.as_view(), name="route-plan"),
]
