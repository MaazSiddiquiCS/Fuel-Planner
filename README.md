# Fuel Planner API

Backend assessment project: a Django REST API that returns route information,
route geometry, cost-effective fuel stops, and estimated fuel cost for US routes.

## What It Does

- Accepts a start and finish location in the USA.
- Returns route distance, travel time, and GeoJSON geometry.
- Recommends fuel stops along the route.
- Estimates total fuel cost using 10 MPG and a 500-mile vehicle range.

## Architecture

Request flow:

```text
RoutePlanAPIView
  -> RoutePlanningService
  -> RoutingProviderClient
  -> FuelOptimizationService
  -> FuelStation Django ORM queries
```

The view handles HTTP only. Serializers validate and serialize data. Routing API
logic is isolated in `RoutingProviderClient`. Fuel-stop selection lives in
`FuelOptimizationService`.

## Provider Choices

- OpenRouteService is used for start/end geocoding and route directions.
- The Directions API is called once per route request.
- Fuel station coordinates are enriched offline with the US Census Batch Geocoder.
- PostgreSQL + PostGIS stores station data and powers the route-proximity query.

PostGIS is required at runtime, and the Docker Compose setup includes it for local
review and demo use.

## Requirements

- Python 3.12 or newer
- Docker Desktop with Docker Compose
- An OpenRouteService API key

## Local Setup With a Virtual Environment

1. Create a virtual environment.

```bash
python -m venv .venv
```

2. Activate it.

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

3. Install the project.

```bash
pip install --upgrade pip
pip install -e .
```

4. Create your local environment file.

Copy [.env.example](.env.example) to [.env](.env) and set your real
`OPENROUTESERVICE_API_KEY`.

5. Run migrations.

```bash
python manage.py migrate
```

6. Import the fuel station CSV.

```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

7. Geocode the station records.

```bash
python manage.py geocode_fuel_stations --limit 10000
```

8. Start the API with Uvicorn.

```bash
uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000
```

9. Run the tests.

```bash
python -m unittest discover
```

## Setup With Docker

1. Make sure Docker Desktop is running.
2. Create [.env](.env) from [.env.example](.env.example) and set
   `OPENROUTESERVICE_API_KEY`.
3. Build and start the stack.

```bash
docker compose up --build
```

4. In another terminal, run migrations inside the web container.

```bash
docker compose run --rm web python manage.py migrate
```

5. Import the CSV inside the container.

```bash
docker compose run --rm web python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

6. Geocode the stations inside the container.

```bash
docker compose run --rm web python manage.py geocode_fuel_stations --limit 10000
```

7. Open the API at `http://localhost:8000/api/routes/plan/`.

The web container now runs Uvicorn, so Docker and local virtualenv usage behave
consistently.

## Environment Variables

Local [.env](.env) values:

```text
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

POSTGRES_DB=fuel_planner
POSTGRES_USER=fuel_planner
POSTGRES_PASSWORD=fuel_planner
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

OPENROUTESERVICE_API_KEY=your-openrouteservice-api-key
```

## API

Endpoint:

```text
POST /api/routes/plan/
```

Request:

```json
{
  "start_location": "New York, NY",
  "finish_location": "Chicago, IL"
}
```

Response shape:

```json
{
  "distance_miles": 790.4,
  "duration_seconds": 43800.0,
  "geometry": {
    "type": "LineString",
    "coordinates": []
  },
  "fuel_stops": [],
  "total_fuel_cost": "245.80"
}
```

Example request with curl:

```bash
curl -X POST http://localhost:8000/api/routes/plan/ \
  -H "Content-Type: application/json" \
  -d '{
    "start_location": "New York, NY",
    "finish_location": "Chicago, IL"
  }'
```

## Fuel Optimization Heuristic

The optimizer uses a practical take-home heuristic:

1. Read the GeoJSON route geometry.
2. Query geocoded fuel stations within a small distance of the route geometry.
3. Estimate each station's nearest distance along the route.
4. Step through the trip in 500-mile legs and pick the cheapest reachable station in each leg.
5. Calculate gallons using 10 MPG and sum estimated cost for the selected legs.

This is fast for an 8k-row station dataset and easy to explain in a short Loom.
In a production system, this could evolve further with starting-fuel state,
detour-time constraints, truck restrictions, and preferred brands.
