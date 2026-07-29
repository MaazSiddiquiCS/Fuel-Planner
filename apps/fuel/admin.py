from django.contrib import admin

from apps.fuel.models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = (
        "truckstop_id",
        "name",
        "city",
        "state",
        "retail_price",
        "latitude",
        "longitude",
    )
    list_filter = ("state",)
    search_fields = ("truckstop_id", "name", "address", "city")
