import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="FuelStation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("truckstop_id", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("address", models.CharField(max_length=255)),
                ("city", models.CharField(max_length=120)),
                ("state", models.CharField(max_length=2)),
                ("retail_price", models.DecimalField(decimal_places=3, max_digits=6)),
                (
                    "latitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                    ),
                ),
                (
                    "longitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                    ),
                ),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True,
                        geography=True,
                        null=True,
                        spatial_index=True,
                        srid=4326,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "fuel_stations",
                "ordering": ["state", "city", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="fuelstation",
            constraint=models.CheckConstraint(
                condition=models.Q(("retail_price__gt", 0)),
                name="fuel_station_retail_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="fuelstation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("latitude__isnull", True))
                    | models.Q(("latitude__gte", -90), ("latitude__lte", 90))
                ),
                name="fuel_station_latitude_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="fuelstation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("longitude__isnull", True))
                    | models.Q(("longitude__gte", -180), ("longitude__lte", 180))
                ),
                name="fuel_station_longitude_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["state"], name="fuel_station_state_idx"),
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["retail_price"], name="fuel_station_price_idx"),
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(
                fields=["state", "retail_price"],
                name="fuel_station_state_price_idx",
            ),
        ),
    ]
