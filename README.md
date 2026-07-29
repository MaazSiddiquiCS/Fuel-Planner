# Fuel Planner API

Backend assessment project: a Django REST API that returns route information, route
geometry, cost-effective fuel stops, and estimated fuel cost for US routes.

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

## Setup

Create a virtual environment, install dependencies, and configure environment
variables from `.env.example`.

Required environment variables:

```text
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_HOST
POSTGRES_PORT
OPENROUTESERVICE_API_KEY
```

Run migrations:

```bash
python manage.py migrate
```

Import the fuel station CSV:

```bash
python manage.py import_fuel_stations fuel-prices-for-be-assessment.csv
```

Enrich station coordinates:

```bash
python manage.py geocode_fuel_stations --limit 10000
```

Start the API:

```bash
python manage.py runserver
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

## Fuel Optimization Heuristic

The optimizer uses a practical take-home heuristic:

1. Read the GeoJSON route geometry.
2. Query geocoded fuel stations within a small distance of the route geometry.
3. Estimate each station's nearest distance along the route.
4. Solve for the cheapest feasible station path under the 500-mile range limit.
5. Calculate gallons using 10 MPG and sum estimated cost for the selected legs.

This is fast for an 8k-row station dataset and easy to explain in a short Loom.
In a production system, this could evolve further with starting-fuel state,
detour-time constraints, truck restrictions, and preferred brands.
