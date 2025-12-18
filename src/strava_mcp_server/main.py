from geopy.geocoders import Nominatim
from mcp.server.fastmcp import FastMCP

from .strava_client import StravaClient

mcp = FastMCP("strava")

# Initialize geocoder for reverse geocoding (GPS -> city name)
_geocoder = Nominatim(user_agent="strava-mcp-server")


def reverse_geocode(lat: float, lon: float) -> dict:
    """Convert GPS coordinates to location name using Nominatim (OpenStreetMap).

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dict with city, state, country and full address
    """
    try:
        location = _geocoder.reverse((lat, lon), language="fr", exactly_one=True)
        if location and location.raw:
            address = location.raw.get("address", {})
            # Try different fields for city name
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
                or address.get("hamlet")
            )
            return {
                "city": city,
                "state": address.get("state"),
                "country": address.get("country"),
                "suburb": address.get("suburb"),
                "county": address.get("county"),
                "full_address": location.address,
            }
    except Exception:
        pass
    return {"city": None, "state": None, "country": None, "full_address": None}


# Liste des noms génériques à détecter
GENERIC_ACTIVITY_NAMES = [
    # Français
    "Trail le matin",
    "Trail le midi",
    "Trail dans l'après-midi",
    "Trail en soirée",
    "Trail en fin de journée",
    "Course le matin",
    "Course le midi",
    "Course dans l'après-midi",
    "Course en soirée",
    "Course en fin de journée",
    "Sortie vélo le matin",
    "Sortie vélo le midi",
    "Sortie vélo dans l'après-midi",
    "Sortie vélo en soirée",
    "Sortie vélo en fin de journée",
    "VTT le matin",
    "VTT le midi",
    "VTT dans l'après-midi",
    "VTT en soirée",
    "VTT en fin de journée",
    "Randonnée le matin",
    "Randonnée le midi",
    "Randonnée dans l'après-midi",
    "Randonnée en soirée",
    "Randonnée en fin de journée",
    "Marche le matin",
    "Marche le midi",
    "Marche dans l'après-midi",
    "Marche en soirée",
    "Marche en fin de journée",
    # English
    "Morning Run",
    "Lunch Run",
    "Afternoon Run",
    "Evening Run",
    "Night Run",
    "Morning Ride",
    "Lunch Ride",
    "Afternoon Ride",
    "Evening Ride",
    "Night Ride",
    "Morning Walk",
    "Lunch Walk",
    "Afternoon Walk",
    "Evening Walk",
    "Night Walk",
    "Morning Hike",
    "Lunch Hike",
    "Afternoon Hike",
    "Evening Hike",
    "Night Hike",
]


# ============== Prompts MCP ==============


@mcp.prompt()
def suggest_activity_name(
    activity_type: str,
    location: str,
    elevation_gain: float,
    distance_km: float,
    moving_time_min: float,
    suffer_score: int | None = None,
) -> str:
    """Prompt pour suggérer un nom créatif pour une activité Strava.

    Args:
        activity_type: Type d'activité (Run, TrailRun, Ride, MountainBikeRide, Hike, Walk)
        location: Lieu géographique (ville, région, montagne, parc, etc.)
        elevation_gain: Dénivelé positif en mètres
        distance_km: Distance en kilomètres
        moving_time_min: Temps de déplacement en minutes
        suffer_score: Score d'effort Strava (optionnel, 0-400+)
    """
    # Déterminer le niveau d'effort
    effort_description = ""
    if suffer_score is not None:
        if suffer_score < 50:
            effort_description = "sortie tranquille, récupération active"
        elif suffer_score < 100:
            effort_description = "effort modéré, endurance fondamentale"
        elif suffer_score < 150:
            effort_description = "effort soutenu, bonne intensité"
        elif suffer_score < 250:
            effort_description = "effort intense, séance difficile"
        else:
            effort_description = "effort maximal, dépassement de soi"

    # Calculer la vitesse/allure moyenne
    speed_kmh = distance_km / (moving_time_min / 60) if moving_time_min > 0 else 0
    pace_min_km = moving_time_min / distance_km if distance_km > 0 else 0

    return f"""Tu dois suggérer un nom créatif et mémorable pour une activité Strava.

**Informations sur l'activité :**
- Type : {activity_type}
- Lieu : {location}
- Distance : {distance_km:.1f} km
- Dénivelé positif : {elevation_gain:.0f} m
- Durée : {moving_time_min:.0f} minutes
- Vitesse moyenne : {speed_kmh:.1f} km/h (allure : {pace_min_km:.1f} min/km)
- Niveau d'effort : {effort_description if effort_description else "Non disponible"}

**Règles pour le nom :**
1. Court et percutant (3-6 mots maximum)
2. Évoque le lieu OU l'effort OU un moment marquant
3. Peut inclure un jeu de mots, une référence culturelle ou de l'humour
4. Évite les noms génériques comme "Course du matin" ou "Sortie vélo"

**Exemples de bons noms par type :**
- Trail/Run : "Pic Saint-Loup", "Crêtes au lever du soleil", "Intervalles infernaux"
- VTT : "Single track du Caroux", "Descente à Sète", "Boue et sueur"
- Vélo route : "Col de la Lozère", "Contre le Mistral", "100 bornes de bonheur"
- Randonnée : "Panorama Cévennes", "Sentier des douaniers", "Escapade forestière"

**Propose 3 suggestions de noms**, du plus descriptif au plus créatif."""


def to_seconds(duration):
    """Convert stravalib Duration to seconds."""
    if duration is None:
        return 0
    if hasattr(duration, "total_seconds"):
        return duration.total_seconds()
    # stravalib Duration stores seconds directly
    return int(duration)


@mcp.tool()
def get_activities(limit: int = 30) -> list[dict]:
    """Get the latest Strava activities.

    Args:
        limit: Maximum number of activities to return (default 30).

    Returns:
        List of activity summaries with id, name, type, distance, time, elevation, and date.
    """
    client = StravaClient()
    activities = client.get_activities(limit=limit)
    return [
        {
            "id": activity.id,
            "name": activity.name,
            "type": activity.type,
            "distance": float(activity.distance or 0),
            "moving_time": to_seconds(activity.moving_time),
            "elapsed_time": to_seconds(activity.elapsed_time),
            "elevation_gain": float(activity.total_elevation_gain or 0),
            "start_date_local": (
                activity.start_date_local.isoformat() if activity.start_date_local else None
            ),
        }
        for activity in activities
    ]


@mcp.tool()
def get_activity(activity_id: int) -> dict:
    """Get detailed information about a specific Strava activity.

    Args:
        activity_id: The Strava activity ID.

    Returns:
        Activity details including speed, heartrate, suffer score, and kudos.
    """
    client = StravaClient()
    activity = client.get_activity(activity_id)
    return {
        "id": activity.id,
        "name": activity.name,
        "type": activity.type,
        "distance": float(activity.distance or 0),
        "moving_time": to_seconds(activity.moving_time),
        "elapsed_time": to_seconds(activity.elapsed_time),
        "elevation_gain": float(activity.total_elevation_gain or 0),
        "start_date_local": (
            activity.start_date_local.isoformat() if activity.start_date_local else None
        ),
        "average_speed": float(activity.average_speed or 0),
        "max_speed": float(activity.max_speed or 0),
        "average_heartrate": (
            float(activity.average_heartrate or 0) if activity.average_heartrate else None
        ),
        "max_heartrate": (float(activity.max_heartrate or 0) if activity.max_heartrate else None),
        "suffer_score": getattr(activity, "suffer_score", None),
        "kudos_count": getattr(activity, "kudos_count", None),
    }


@mcp.tool()
def get_stats() -> dict:
    """Get athlete statistics including ride and run totals.

    Returns:
        Recent, year-to-date, and all-time totals for rides and runs.
    """
    client = StravaClient()
    stats = client.get_stats()
    if not stats:
        return {}

    def totals_to_dict(totals):
        if not totals:
            return None
        return {
            "count": totals.count,
            "distance": float(totals.distance or 0),
            "moving_time": totals.moving_time,
            "elapsed_time": totals.elapsed_time,
            "elevation_gain": float(totals.elevation_gain or 0),
        }

    return {
        "recent_ride_totals": totals_to_dict(stats.recent_ride_totals),
        "recent_run_totals": totals_to_dict(stats.recent_run_totals),
        "ytd_ride_totals": totals_to_dict(stats.ytd_ride_totals),
        "ytd_run_totals": totals_to_dict(stats.ytd_run_totals),
        "all_ride_totals": totals_to_dict(stats.all_ride_totals),
        "all_run_totals": totals_to_dict(stats.all_run_totals),
    }


@mcp.tool()
def fix_ebike_activity(activity_id: int) -> dict:
    """Fix a mountain bike activity incorrectly categorized as MTB instead of E-MTB.

    This tool changes the sport_type from 'MountainBikeRide' to 'EMountainBikeRide'.

    Args:
        activity_id: The Strava activity ID to fix.

    Returns:
        The updated activity details.
    """
    client = StravaClient()
    updated = client.update_activity(activity_id, sport_type="EMountainBikeRide")
    return {
        "id": updated.id,
        "name": updated.name,
        "type": str(updated.type),
        "sport_type": str(getattr(updated, "sport_type", None)),
        "distance": float(updated.distance or 0),
        "moving_time": to_seconds(updated.moving_time),
        "start_date_local": (
            updated.start_date_local.isoformat() if updated.start_date_local else None
        ),
        "message": "Activity successfully updated to E-Mountain Bike",
    }


@mcp.tool()
def detect_ebike_activities(
    limit: int = 30,
    effort_ratio_threshold: float = 4.5,
    min_elevation: float = 200.0,
) -> list[dict]:
    """Detect mountain bike activities that are likely e-bike based on performance analysis.

    Detection criteria (in order of reliability):
    1. Cadence data present: E-bikes typically have cadence sensors, regular MTBs often don't
    2. Low effort-to-climbing ratio: suffer_score / (elevation_gain / 100)

    Args:
        limit: Maximum number of activities to analyze (default 30).
        effort_ratio_threshold: Effort ratio below this is suspicious (default 4.5).
        min_elevation: Minimum elevation gain in meters to consider (default 200).

    Returns:
        List of suspicious activities with analysis details and recommendation.
    """
    client = StravaClient()
    activities = client.get_activities(limit=limit)

    suspicious = []
    for activity in activities:
        # Only analyze rides
        activity_type = str(activity.type) if activity.type else ""
        if "Ride" not in activity_type:
            continue

        # Skip if already marked as e-bike
        sport_type = getattr(activity, "sport_type", None)
        if sport_type and "E" in str(sport_type):
            continue

        elevation = float(activity.total_elevation_gain or 0)
        moving_time_sec = to_seconds(activity.moving_time)
        distance = float(activity.distance or 0)

        # Skip if not enough data to analyze
        if moving_time_sec < 600:
            continue

        # Get detailed activity for cadence and suffer score
        detailed = client.get_activity(activity.id)
        avg_cadence = getattr(detailed, "average_cadence", None)
        suffer_score = getattr(detailed, "suffer_score", None) or 0
        avg_hr = float(detailed.average_heartrate or 0) if detailed.average_heartrate else None
        avg_watts = getattr(detailed, "average_watts", None)

        # Calculate metrics
        speed_kmh = (distance / 1000) / (moving_time_sec / 3600) if moving_time_sec > 0 else 0

        # Key metric: effort per 100m of elevation gain
        effort_ratio = suffer_score / (elevation / 100) if elevation > 100 else None

        # Determine if suspicious
        is_suspicious = False
        reasons = []

        # PRIMARY INDICATOR: Cadence data present suggests e-bike (has cadence sensor)
        if avg_cadence is not None and avg_cadence > 0:
            is_suspicious = True
            reasons.append(
                f"Données de cadence présentes ({avg_cadence:.0f} rpm) - capteur de vélo électrique"
            )

        # SECONDARY INDICATOR: Low effort ratio with significant climbing
        is_low_effort = (
            elevation >= min_elevation
            and effort_ratio is not None
            and effort_ratio < effort_ratio_threshold
        )
        if is_low_effort:
            if not is_suspicious:
                is_suspicious = True
            reasons.append(f"Effort faible pour le dénivelé (ratio {effort_ratio:.1f})")

        if is_suspicious:
            start_date = activity.start_date_local
            suspicious.append(
                {
                    "id": activity.id,
                    "name": activity.name,
                    "date": start_date.isoformat() if start_date else None,
                    "type": activity_type,
                    "distance_km": round(distance / 1000, 1),
                    "elevation_gain": round(elevation, 0),
                    "moving_time_min": round(moving_time_sec / 60, 0),
                    "speed_kmh": round(speed_kmh, 1),
                    "average_cadence": round(avg_cadence, 0) if avg_cadence else None,
                    "suffer_score": suffer_score,
                    "effort_ratio": round(effort_ratio, 2) if effort_ratio else None,
                    "average_hr": round(avg_hr, 0) if avg_hr else None,
                    "average_watts": round(avg_watts, 0) if avg_watts else None,
                    "reasons": reasons,
                    "recommendation": "Probablement E-MTB - fix_ebike_activity()",
                }
            )

    return suspicious


@mcp.tool()
def update_activity_type(activity_id: int, sport_type: str) -> dict:
    """Update the sport type of a Strava activity.

    Args:
        activity_id: The Strava activity ID to update.
        sport_type: The new sport type. Common values:
            - 'Ride' (road cycling)
            - 'MountainBikeRide' (VTT)
            - 'EMountainBikeRide' (VTT électrique)
            - 'EBikeRide' (vélo électrique)
            - 'Run' (course à pied)
            - 'TrailRun' (trail)
            - 'Walk' (marche)
            - 'Hike' (randonnée)

    Returns:
        The updated activity details.
    """
    client = StravaClient()
    updated = client.update_activity(activity_id, sport_type=sport_type)
    return {
        "id": updated.id,
        "name": updated.name,
        "type": updated.type,
        "sport_type": getattr(updated, "sport_type", None),
        "distance": float(updated.distance or 0),
        "moving_time": to_seconds(updated.moving_time),
        "start_date_local": (
            updated.start_date_local.isoformat() if updated.start_date_local else None
        ),
        "message": f"Activity successfully updated to {sport_type}",
    }


@mcp.tool()
def detect_generic_named_activities(limit: int = 50) -> list[dict]:
    """Detect activities with generic auto-generated names that should be renamed.

    Generic names include patterns like:
    - "Trail le midi", "Course en soirée", "Morning Run", etc.

    Args:
        limit: Maximum number of activities to scan (default 50).

    Returns:
        List of activities with generic names, including location and effort data
        to help suggest better names.
    """
    client = StravaClient()
    activities = client.get_activities(limit=limit)

    generic_activities = []
    for activity in activities:
        name = activity.name or ""

        # Check if name matches a generic pattern
        is_generic = name.strip() in GENERIC_ACTIVITY_NAMES

        # Also check partial matches for common patterns
        if not is_generic:
            generic_patterns = [
                "le matin",
                "le midi",
                "l'après-midi",
                "en soirée",
                "en fin de journée",
                "Morning",
                "Lunch",
                "Afternoon",
                "Evening",
                "Night",
            ]
            for pattern in generic_patterns:
                if pattern.lower() in name.lower():
                    is_generic = True
                    break

        if is_generic:
            # Get detailed info for renaming suggestions
            detailed = client.get_activity(activity.id)

            # Extract location info
            start_latlng = getattr(detailed, "start_latlng", None)
            location_city = getattr(detailed, "location_city", None)
            location_state = getattr(detailed, "location_state", None)
            location_country = getattr(detailed, "location_country", None)

            # If no city from Strava, try reverse geocoding with GPS coordinates
            if not location_city and start_latlng:
                try:
                    lat = start_latlng.lat
                    lon = start_latlng.lon
                    if lat and lon:
                        geo = reverse_geocode(lat, lon)
                        location_city = geo.get("city")
                        location_state = location_state or geo.get("state")
                        location_country = location_country or geo.get("country")
                except Exception:
                    pass

            # Build location string
            location_parts = [p for p in [location_city, location_state, location_country] if p]
            location = ", ".join(location_parts) if location_parts else "Lieu inconnu"

            elevation = float(activity.total_elevation_gain or 0)
            distance = float(activity.distance or 0)
            moving_time_sec = to_seconds(activity.moving_time)
            suffer_score = getattr(detailed, "suffer_score", None)

            generic_activities.append(
                {
                    "id": activity.id,
                    "current_name": name,
                    "type": str(activity.type) if activity.type else None,
                    "sport_type": str(getattr(activity, "sport_type", None)),
                    "date": activity.start_date_local.isoformat()
                    if activity.start_date_local
                    else None,
                    "location": location,
                    "coordinates": [start_latlng.lat, start_latlng.lon] if start_latlng else None,
                    "distance_km": round(distance / 1000, 1),
                    "elevation_gain": round(elevation, 0),
                    "moving_time_min": round(moving_time_sec / 60, 0),
                    "suffer_score": suffer_score,
                    "suggestion": "Use suggest_activity_name prompt to generate a better name",
                }
            )

    return generic_activities


@mcp.tool()
def rename_activity(activity_id: int, new_name: str) -> dict:
    """Rename a Strava activity with a new custom name.

    Args:
        activity_id: The Strava activity ID to rename.
        new_name: The new name for the activity.

    Returns:
        The updated activity details confirming the rename.
    """
    client = StravaClient()
    updated = client.update_activity(activity_id, name=new_name)
    return {
        "id": updated.id,
        "name": updated.name,
        "previous_name": "Updated successfully",
        "type": str(updated.type) if updated.type else None,
        "sport_type": str(getattr(updated, "sport_type", None)),
        "distance_km": round(float(updated.distance or 0) / 1000, 1),
        "start_date_local": (
            updated.start_date_local.isoformat() if updated.start_date_local else None
        ),
        "message": f"Activity successfully renamed to '{new_name}'",
    }


@mcp.tool()
def get_activity_details_for_naming(activity_id: int) -> dict:
    """Get detailed activity information useful for suggesting a good name.

    Returns location, effort, terrain and performance data to help create
    a meaningful and memorable activity name.

    Args:
        activity_id: The Strava activity ID.

    Returns:
        Comprehensive activity details for name suggestion.
    """
    client = StravaClient()
    activity = client.get_activity(activity_id)

    # Extract all useful info for naming
    start_latlng = getattr(activity, "start_latlng", None)
    end_latlng = getattr(activity, "end_latlng", None)
    location_city = getattr(activity, "location_city", None)
    location_state = getattr(activity, "location_state", None)
    location_country = getattr(activity, "location_country", None)

    # If no city from Strava, try reverse geocoding with GPS coordinates
    geo_info = {}
    if start_latlng:
        try:
            lat = start_latlng.lat
            lon = start_latlng.lon
            if lat and lon:
                geo_info = reverse_geocode(lat, lon)
                if not location_city:
                    location_city = geo_info.get("city")
                location_state = location_state or geo_info.get("state")
                location_country = location_country or geo_info.get("country")
        except Exception:
            pass

    # Build location string
    location_parts = [p for p in [location_city, location_state, location_country] if p]
    location = ", ".join(location_parts) if location_parts else "Lieu inconnu"

    elevation = float(activity.total_elevation_gain or 0)
    distance = float(activity.distance or 0)
    moving_time_sec = to_seconds(activity.moving_time)
    elapsed_time_sec = to_seconds(activity.elapsed_time)

    # Calculate performance metrics
    speed_kmh = (distance / 1000) / (moving_time_sec / 3600) if moving_time_sec > 0 else 0
    pace_min_km = (moving_time_sec / 60) / (distance / 1000) if distance > 0 else 0
    elevation_per_km = elevation / (distance / 1000) if distance > 0 else 0

    # Determine activity characteristics
    is_hilly = elevation_per_km > 30  # More than 30m/km
    is_long = distance > 20000  # More than 20km
    is_fast = False

    activity_type = str(activity.type) if activity.type else ""
    if "Run" in activity_type and pace_min_km < 5 or "Ride" in activity_type and speed_kmh > 25:
        is_fast = True

    suffer_score = getattr(activity, "suffer_score", None)
    effort_level = "unknown"
    if suffer_score:
        if suffer_score < 50:
            effort_level = "easy"
        elif suffer_score < 100:
            effort_level = "moderate"
        elif suffer_score < 150:
            effort_level = "hard"
        elif suffer_score < 250:
            effort_level = "very_hard"
        else:
            effort_level = "extreme"

    return {
        "id": activity.id,
        "current_name": activity.name,
        "type": activity_type,
        "sport_type": str(getattr(activity, "sport_type", None)),
        "date": activity.start_date_local.isoformat() if activity.start_date_local else None,
        "day_of_week": activity.start_date_local.strftime("%A")
        if activity.start_date_local
        else None,
        "time_of_day": activity.start_date_local.strftime("%H:%M")
        if activity.start_date_local
        else None,
        "location": {
            "name": location,
            "city": location_city,
            "state": location_state,
            "country": location_country,
            "suburb": geo_info.get("suburb"),
            "county": geo_info.get("county"),
            "full_address": geo_info.get("full_address"),
            "start_coordinates": [start_latlng.lat, start_latlng.lon] if start_latlng else None,
            "end_coordinates": [end_latlng.lat, end_latlng.lon] if end_latlng else None,
        },
        "metrics": {
            "distance_km": round(distance / 1000, 2),
            "elevation_gain_m": round(elevation, 0),
            "elevation_per_km": round(elevation_per_km, 1),
            "moving_time_min": round(moving_time_sec / 60, 0),
            "elapsed_time_min": round(elapsed_time_sec / 60, 0),
            "average_speed_kmh": round(speed_kmh, 1),
            "pace_min_per_km": round(pace_min_km, 2),
        },
        "effort": {
            "suffer_score": suffer_score,
            "effort_level": effort_level,
            "average_heartrate": float(activity.average_heartrate)
            if activity.average_heartrate
            else None,
            "max_heartrate": float(activity.max_heartrate) if activity.max_heartrate else None,
        },
        "characteristics": {
            "is_hilly": is_hilly,
            "is_long": is_long,
            "is_fast": is_fast,
        },
        "naming_hints": {
            "use_location": location != "Lieu inconnu",
            "mention_elevation": elevation > 300,
            "mention_distance": is_long,
            "mention_effort": suffer_score and suffer_score > 100,
        },
    }


if __name__ == "__main__":
    mcp.run()
