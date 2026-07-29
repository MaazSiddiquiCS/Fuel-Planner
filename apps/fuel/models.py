from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.db.models import Q


class FuelStation(models.Model):
    truckstop_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    retail_price = models.DecimalField(max_digits=6, decimal_places=3)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    location = models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fuel_stations"
        constraints = [
            models.CheckConstraint(
                condition=Q(retail_price__gt=0),
                name="fuel_station_retail_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True)
                | Q(latitude__gte=-90, latitude__lte=90),
                name="fuel_station_latitude_valid",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True)
                | Q(longitude__gte=-180, longitude__lte=180),
                name="fuel_station_longitude_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["state"], name="fuel_station_state_idx"),
            models.Index(fields=["retail_price"], name="fuel_station_price_idx"),
            models.Index(
                fields=["state", "retail_price"],
                name="fuel_station_state_price_idx",
            ),
        ]
        ordering = ["state", "city", "name"]

    def save(self, *args, **kwargs):
        if self.latitude is not None and self.longitude is not None:
            self.location = Point(float(self.longitude), float(self.latitude), srid=4326)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})"
