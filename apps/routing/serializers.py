from rest_framework import serializers


class RoutePlanRequestSerializer(serializers.Serializer):
    start_location = serializers.CharField(max_length=255)
    finish_location = serializers.CharField(max_length=255)


class FuelStopSerializer(serializers.Serializer):
    truckstop_id = serializers.CharField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    retail_price = serializers.DecimalField(max_digits=6, decimal_places=3)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_along_route_miles = serializers.FloatField()
    distance_from_route_miles = serializers.FloatField()
    gallons = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_cost = serializers.DecimalField(max_digits=12, decimal_places=2)


class RoutePlanResponseSerializer(serializers.Serializer):
    distance_miles = serializers.FloatField()
    duration_seconds = serializers.FloatField()
    geometry = serializers.JSONField()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
