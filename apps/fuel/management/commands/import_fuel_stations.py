import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.fuel.models import FuelStation


class Command(BaseCommand):
    help = "Import fuel stations from the assessment CSV file."

    REQUIRED_COLUMNS = {
        "Truckstop Name",
        "Address",
        "City",
        "State",
        "Retail Price",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the fuel station CSV file.")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of rows to insert per bulk_create call.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        batch_size = options["batch_size"]

        if batch_size <= 0:
            raise CommandError("--batch-size must be greater than zero.")

        imported_count = 0
        skipped_duplicate_count = 0
        skipped_invalid_count = 0
        seen_truckstop_ids = set()
        batch = []

        existing_truckstop_ids = set(
            FuelStation.objects.values_list("truckstop_id", flat=True)
        )

        try:
            csv_file = open(csv_path, newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(f"Could not open CSV file: {exc}") from exc

        with csv_file:
            reader = csv.DictReader(csv_file)
            self._validate_headers(reader.fieldnames)

            for row_number, row in enumerate(reader, start=2):
                station = self._build_station(row, row_number)

                if station is None:
                    skipped_invalid_count += 1
                    continue

                if (
                    station.truckstop_id in existing_truckstop_ids
                    or station.truckstop_id in seen_truckstop_ids
                ):
                    skipped_duplicate_count += 1
                    continue

                seen_truckstop_ids.add(station.truckstop_id)
                batch.append(station)

                if len(batch) >= batch_size:
                    imported_count += self._bulk_create(batch, batch_size)
                    batch.clear()

            if batch:
                imported_count += self._bulk_create(batch, batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                "Import complete. "
                f"Imported: {imported_count}. "
                f"Skipped duplicates: {skipped_duplicate_count}. "
                f"Skipped invalid rows: {skipped_invalid_count}."
            )
        )

    def _validate_headers(self, fieldnames):
        if fieldnames is None:
            raise CommandError("CSV file is empty.")

        headers = set(fieldnames)
        missing_columns = self.REQUIRED_COLUMNS - headers
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise CommandError(f"CSV file is missing required columns: {missing}")

        if "Truckstop ID" not in headers and "OPIS Truckstop ID" not in headers:
            raise CommandError(
                "CSV file is missing required column: Truckstop ID or OPIS Truckstop ID"
            )

    def _build_station(self, row, row_number):
        truckstop_id = self._clean(
            row.get("Truckstop ID") or row.get("OPIS Truckstop ID")
        )
        name = self._clean(row["Truckstop Name"])
        address = self._clean(row["Address"])
        city = self._clean(row["City"])
        state = self._clean(row["State"]).upper()
        retail_price = self._parse_price(row["Retail Price"])

        if not all([truckstop_id, name, address, city, state, retail_price]):
            self.stderr.write(f"Skipping row {row_number}: missing required data.")
            return None

        if len(state) != 2:
            self.stderr.write(f"Skipping row {row_number}: invalid state '{state}'.")
            return None

        return FuelStation(
            truckstop_id=truckstop_id,
            name=name,
            address=address,
            city=city,
            state=state,
            retail_price=retail_price,
        )

    def _parse_price(self, value):
        cleaned_value = self._clean(value).replace("$", "")

        try:
            price = Decimal(cleaned_value)
        except InvalidOperation:
            return None

        if price <= 0:
            return None

        return price

    def _bulk_create(self, stations, batch_size):
        created_stations = FuelStation.objects.bulk_create(
            stations,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        return len(created_stations)

    def _clean(self, value):
        return str(value or "").strip()
