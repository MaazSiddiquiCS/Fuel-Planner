import csv
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from apps.fuel.models import FuelStation


class Command(BaseCommand):
    help = "Enrich fuel stations with coordinates using the US Census Batch Geocoder."

    CENSUS_BATCH_URL = (
        "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10000,
            help="Maximum number of ungeocoded stations to submit.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of station records to update per bulk_update call.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=120,
            help="Census API request timeout in seconds.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        batch_size = options["batch_size"]
        timeout = options["timeout"]

        if limit <= 0:
            raise CommandError("--limit must be greater than zero.")

        stations = list(
            FuelStation.objects.filter(latitude__isnull=True, longitude__isnull=True)
            .order_by("id")[:limit]
        )

        if not stations:
            self.stdout.write(self.style.SUCCESS("No stations need geocoding."))
            return

        input_path = self._write_census_input(stations)

        try:
            rows = self._submit_batch(input_path, timeout)
        finally:
            input_path.unlink(missing_ok=True)

        stations_by_id = {station.truckstop_id: station for station in stations}
        matched_stations = []
        unmatched_count = 0

        for row in rows:
            station = stations_by_id.get(row["truckstop_id"])

            if station is None or not row["matched"]:
                unmatched_count += 1
                continue

            station.latitude = row["latitude"]
            station.longitude = row["longitude"]
            station.location = Point(
                float(row["longitude"]),
                float(row["latitude"]),
                srid=4326,
            )
            matched_stations.append(station)

        FuelStation.objects.bulk_update(
            matched_stations,
            ["latitude", "longitude", "location"],
            batch_size=batch_size,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Geocoding complete. "
                f"Submitted: {len(stations)}. "
                f"Updated: {len(matched_stations)}. "
                f"Unmatched: {unmatched_count}."
            )
        )

    def _write_census_input(self, stations):
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
        )

        with temporary_file:
            writer = csv.writer(temporary_file)
            for station in stations:
                writer.writerow(
                    [
                        station.truckstop_id,
                        station.address,
                        station.city,
                        station.state,
                        "",
                    ]
                )

        return Path(temporary_file.name)

    def _submit_batch(self, input_path, timeout):
        try:
            with input_path.open("rb") as address_file:
                response = requests.post(
                    self.CENSUS_BATCH_URL,
                    files={"addressFile": address_file},
                    data={"benchmark": "Public_AR_Current"},
                    timeout=timeout,
                )
                response.raise_for_status()
        except requests.Timeout as exc:
            raise CommandError("Census geocoder request timed out.") from exc
        except requests.RequestException as exc:
            raise CommandError(f"Census geocoder request failed: {exc}") from exc

        return list(self._parse_census_response(response.text.splitlines()))

    def _parse_census_response(self, lines):
        reader = csv.reader(lines)

        for row in reader:
            if len(row) < 6:
                continue

            truckstop_id = row[0].strip()
            matched = row[2].strip().lower() == "match"
            coordinates = row[5].strip()

            latitude = None
            longitude = None

            if matched and coordinates:
                latitude, longitude = self._parse_coordinates(coordinates)

            yield {
                "truckstop_id": truckstop_id,
                "matched": matched and latitude is not None and longitude is not None,
                "latitude": latitude,
                "longitude": longitude,
            }

    def _parse_coordinates(self, value):
        try:
            longitude, latitude = value.split(",", maxsplit=1)
            return Decimal(latitude.strip()), Decimal(longitude.strip())
        except (ValueError, InvalidOperation):
            return None, None
