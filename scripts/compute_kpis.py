
import csv
import json
import math
from pathlib import Path


# ============================================================
# 1. ASSUMPTIONS
# ============================================================

TONNES_PER_1000_RESIDENTS_PER_YEAR = 50
CO2_FACTOR_KG_PER_TONNE_KM = 0.10

TRANSPORT_COST_EUR_PER_TONNE_KM = 0.12
STORAGE_COST_EUR_PER_TONNE_YEAR = 40

BASELINE_WAREHOUSES = ["Paris", "Lyon", "Lille"]


# ============================================================
# 2. PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

CITIES_FILE = ROOT / "data" / "cities.csv"
OUTPUT_DIR = ROOT / "docs" / "data"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 3. LOAD CITY DATA
# ============================================================

with open(CITIES_FILE, newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    cities = []
    for row in reader:
        cities.append({
            "city": row["city"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "population": int(row["population"]),
            "role": row["role"],
        })


# ============================================================
# 4. DISTANCE CALCULATION
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points
    on Earth, in kilometres.
    """

    earth_radius_km = 6371

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_km * c


def find_nearest_warehouse(city, warehouses):
    """Find the nearest active warehouse for a city."""

    distances = []

    for warehouse in warehouses:
        distance = haversine(
            city["lat"],
            city["lon"],
            warehouse["lat"],
            warehouse["lon"],
        )

        distances.append((warehouse, distance))

    return min(distances, key=lambda item: item[1])


# ============================================================
# 5. ASSIGN CITIES TO WAREHOUSES
# ============================================================

def assign_cities(warehouses):
    """
    Assign every city to its nearest warehouse.
    Calculate its demand, distance and emissions.
    """

    assignments = []

    for city in cities:
        warehouse, distance = find_nearest_warehouse(
            city,
            warehouses,
        )

        tonnes = (
            city["population"]
            / 1000
            * TONNES_PER_1000_RESIDENTS_PER_YEAR
        )

        co2_kg = (
            tonnes
            * distance
            * CO2_FACTOR_KG_PER_TONNE_KM
        )

        assignments.append({
            "city": city["city"],
            "lat": city["lat"],
            "lon": city["lon"],
            "population": city["population"],
            "role": city["role"],
            "warehouse": warehouse["city"],
            "distance_km": round(distance, 1),
            "tonnes": tonnes,
            "co2_kg": co2_kg,
            "is_warehouse": city["city"] in [
                w["city"] for w in warehouses
            ],
        })

    return assignments


# ============================================================
# 6. CO2 DASHBOARD DATA
# ============================================================

baseline_warehouses = [
    city for city in cities
    if city["city"] in BASELINE_WAREHOUSES
]

baseline_assignments = assign_cities(baseline_warehouses)

total_co2 = sum(
    item["co2_kg"] for item in baseline_assignments
)

total_tonnes = sum(
    item["tonnes"] for item in baseline_assignments
)

network_co2_per_tonne = (
    total_co2 / total_tonnes if total_tonnes else 0
)


# CO2 by warehouse

co2_by_warehouse = []

for warehouse in baseline_warehouses:
    assigned = [
        item for item in baseline_assignments
        if item["warehouse"] == warehouse["city"]
    ]

    warehouse_co2 = sum(
        item["co2_kg"] for item in assigned
    )

    warehouse_tonnes = sum(
        item["tonnes"] for item in assigned
    )

    co2_per_tonne = (
        warehouse_co2 / warehouse_tonnes
        if warehouse_tonnes else 0
    )

    co2_by_warehouse.append({
        "warehouse": warehouse["city"],
        "total_co2_kg": round(warehouse_co2),
        "total_tonnes": round(warehouse_tonnes, 1),
        "co2_kg_per_tonne": round(co2_per_tonne, 2),
    })


# Top 10 highest-emission routes

top_co2_links = sorted(
    [
        item for item in baseline_assignments
        if item["distance_km"] > 0
    ],
    key=lambda item: item["co2_kg"],
    reverse=True,
)[:10]

co2_top_links = [
    {
        "city": item["city"],
        "warehouse": item["warehouse"],
        "distance_km": item["distance_km"],
        "co2_kg": round(item["co2_kg"]),
    }
    for item in top_co2_links
]


co2_data = {
    "total_co2_kg": round(total_co2),
    "co2_kg_per_tonne_network_avg": round(
        network_co2_per_tonne, 2
    ),
    "by_warehouse": co2_by_warehouse,
    "top_links": co2_top_links,
    "all_cities": [
        {
            **item,
            "co2_kg": round(item["co2_kg"]),
        }
        for item in baseline_assignments
    ],
    "assumptions": {
        "co2_factor_kg_per_tonne_km":
            CO2_FACTOR_KG_PER_TONNE_KM,
        "tonnes_per_1000_residents_per_year":
            TONNES_PER_1000_RESIDENTS_PER_YEAR,
    },
}


# ============================================================
# 7. COST DASHBOARD DATA
# ============================================================

cost_by_warehouse = []

for warehouse in baseline_warehouses:
    assigned = [
        item for item in baseline_assignments
        if item["warehouse"] == warehouse["city"]
    ]

    warehouse_tonnes = sum(
        item["tonnes"] for item in assigned
    )

    transport_cost = sum(
        item["tonnes"]
        * item["distance_km"]
        * TRANSPORT_COST_EUR_PER_TONNE_KM
        for item in assigned
    )

    storage_cost = (
        warehouse_tonnes
        * STORAGE_COST_EUR_PER_TONNE_YEAR
    )

    total_cost = transport_cost + storage_cost

    cost_per_tonne = (
        total_cost / warehouse_tonnes
        if warehouse_tonnes else 0
    )

    cost_by_warehouse.append({
        "warehouse": warehouse["city"],
        "total_tonnes": round(warehouse_tonnes, 1),
        "transport_cost_eur": round(transport_cost),
        "storage_cost_eur": round(storage_cost),
        "total_cost_eur": round(total_cost),
        "cost_eur_per_tonne": round(cost_per_tonne, 2),
    })


# Top 10 most expensive transport routes

top_cost_links = sorted(
    [
        item for item in baseline_assignments
        if item["distance_km"] > 0
    ],
    key=lambda item: (
        item["tonnes"]
        * item["distance_km"]
        * TRANSPORT_COST_EUR_PER_TONNE_KM
    ),
    reverse=True,
)[:10]

cost_top_links = [
    {
        "city": item["city"],
        "warehouse": item["warehouse"],
        "distance_km": item["distance_km"],
        "transport_cost_eur": round(
            item["tonnes"]
            * item["distance_km"]
            * TRANSPORT_COST_EUR_PER_TONNE_KM
        ),
    }
    for item in top_cost_links
]


cost_data = {
    "by_warehouse": cost_by_warehouse,
    "top_links": cost_top_links,
    "assumptions": {
        "cost_eur_per_tonne_km":
            TRANSPORT_COST_EUR_PER_TONNE_KM,
        "storage_cost_eur_per_tonne_year":
            STORAGE_COST_EUR_PER_TONNE_YEAR,
    },
}


# ============================================================
# 8. NETWORK SCENARIO ANALYSIS
# ============================================================

def evaluate_scenario(scenario_name, warehouse_names):
    """Evaluate a possible warehouse network configuration."""

    warehouses = [
        city for city in cities
        if city["city"] in warehouse_names
    ]

    assignments = assign_cities(warehouses)

    total_population = sum(
        item["population"] for item in assignments
    )

    weighted_distance = sum(
        item["distance_km"] * item["population"]
        for item in assignments
    )

    average_distance = (
        weighted_distance / total_population
        if total_population else 0
    )

    maximum_distance = max(
        item["distance_km"] for item in assignments
    )

    return {
        "scenario": scenario_name,
        "warehouses": warehouse_names,
        "avg_distance_km_population_weighted":
            round(average_distance, 2),
        "max_distance_km": round(maximum_distance, 1),
    }, assignments


# Four possible network configurations

scenario_definitions = [
    ("baseline - current network", ["Paris", "Lyon", "Lille"]),
    ("open Bordeaux", ["Paris", "Lyon", "Lille", "Bordeaux"]),
    ("open Marseille", ["Paris", "Lyon", "Lille", "Marseille"]),
    ("close Lille", ["Paris", "Lyon"]),
]

scenario_results = []
scenario_assignments = {}

for scenario_name, warehouse_names in scenario_definitions:
    result, assignments = evaluate_scenario(
        scenario_name,
        warehouse_names,
    )

    scenario_results.append(result)
    scenario_assignments[scenario_name] = assignments


# Sort scenarios from best to worst:
# lower population-weighted distance is better.

scenario_results.sort(
    key=lambda item: item[
        "avg_distance_km_population_weighted"
    ]
)

baseline_scenario_name = "baseline - current network"

baseline_map = [
    {
        "city": item["city"],
        "lat": item["lat"],
        "lon": item["lon"],
        "warehouse": item["warehouse"],
    }
    for item in scenario_assignments[baseline_scenario_name]
]

best_scenario = scenario_results[0]
best_alternative_name = best_scenario["scenario"]

best_alternative_map = [
    {
        "city": item["city"],
        "lat": item["lat"],
        "lon": item["lon"],
        "warehouse": item["warehouse"],
    }
    for item in scenario_assignments[best_alternative_name]
]


network_data = {
    "scenarios": scenario_results,
    "baseline_map": baseline_map,
    "best_alternative_map": best_alternative_map,
    "best_alternative_name": best_alternative_name,
}


# ============================================================
# 9. WRITE JSON FILES
# ============================================================

def save_json(filename, data):
    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Generated: {output_path.relative_to(ROOT)}")


save_json("co2.json", co2_data)
save_json("cost.json", cost_data)
save_json("network.json", network_data)


# ============================================================
# 10. PRINT SUMMARY
# ============================================================

print("\n========== CO2 SUMMARY ==========")
print(f"Total network CO2: {total_co2:,.0f} kg/year")
print(
    "Average CO2 per tonne:",
    f"{network_co2_per_tonne:.2f} kg",
)

for item in co2_by_warehouse:
    print(
        item["warehouse"],
        f"{item['total_co2_kg']:,} kg CO2/year",
        f"({item['co2_kg_per_tonne']} kg/tonne)",
    )


print("\n========== COST SUMMARY ==========")

for item in cost_by_warehouse:
    print(
        item["warehouse"],
        f"Transport: {item['transport_cost_eur']:,} EUR",
        f"Storage: {item['storage_cost_eur']:,} EUR",
        f"Total: {item['total_cost_eur']:,} EUR",
    )


print("\n========== NETWORK SCENARIOS ==========")

for item in scenario_results:
    print(
        item["scenario"],
        f"{item['avg_distance_km_population_weighted']} km",
        f"(max: {item['max_distance_km']} km)",
    )

print("\nBest alternative:", best_alternative_name)
print("\nAll dashboard data files generated successfully.")
