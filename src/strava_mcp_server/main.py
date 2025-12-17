from mcp.server.fastmcp import FastMCP

from .strava_client import StravaClient

mcp = FastMCP("strava")


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
    """Fix a mountain bike activity that was incorrectly categorized as regular MTB instead of E-MTB.

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
    min_elevation: float = 300.0,
) -> list[dict]:
    """Detect mountain bike activities that are likely e-bike based on performance analysis.

    Uses effort-to-climbing ratio to identify activities where the effort is too low
    relative to the elevation gained. This is calculated as:
    effort_ratio = suffer_score / (elevation_gain / 100)

    A low effort ratio with significant climbing suggests e-bike assistance.

    Args:
        limit: Maximum number of activities to analyze (default 30).
        effort_ratio_threshold: Activities with effort ratio below this are suspicious (default 4.5).
        min_elevation: Minimum elevation gain in meters to consider (default 300).

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

        # Skip if not enough climbing to analyze
        if elevation < min_elevation or moving_time_sec < 600:
            continue

        # Get detailed activity for suffer score and watts
        detailed = client.get_activity(activity.id)
        suffer_score = getattr(detailed, "suffer_score", None) or 0
        avg_hr = float(detailed.average_heartrate or 0) if detailed.average_heartrate else None
        avg_watts = getattr(detailed, "average_watts", None)

        # Calculate metrics
        speed_kmh = (distance / 1000) / (moving_time_sec / 3600) if moving_time_sec > 0 else 0
        pente_moy = (elevation / distance * 100) if distance > 0 else 0

        # Key metric: effort per 100m of elevation gain
        effort_ratio = suffer_score / (elevation / 100) if elevation > 0 else 0

        # Determine if suspicious based on low effort ratio
        is_suspicious = False
        reasons = []

        # Low effort ratio is the primary indicator
        if effort_ratio > 0 and effort_ratio < effort_ratio_threshold:
            is_suspicious = True
            reasons.append(
                f"Effort faible pour le dénivelé (ratio {effort_ratio:.1f} < {effort_ratio_threshold})"
            )

        # High speed with steep terrain and low effort
        if speed_kmh > 14 and pente_moy > 2.0 and effort_ratio < 5.0:
            if not is_suspicious:
                is_suspicious = True
            reasons.append(
                f"Vitesse élevée ({speed_kmh:.1f} km/h) sur terrain pentu ({pente_moy:.1f}%)"
            )

        if is_suspicious:
            suspicious.append({
                "id": activity.id,
                "name": activity.name,
                "date": activity.start_date_local.isoformat() if activity.start_date_local else None,
                "type": activity_type,
                "distance_km": round(distance / 1000, 1),
                "elevation_gain": round(elevation, 0),
                "moving_time_min": round(moving_time_sec / 60, 0),
                "speed_kmh": round(speed_kmh, 1),
                "pente_moyenne_pct": round(pente_moy, 1),
                "suffer_score": suffer_score,
                "effort_ratio": round(effort_ratio, 2),
                "average_hr": round(avg_hr, 0) if avg_hr else None,
                "average_watts": round(avg_watts, 0) if avg_watts else None,
                "reasons": reasons,
                "recommendation": "Probablement VTT électrique - utiliser fix_ebike_activity() pour corriger",
            })

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


if __name__ == "__main__":
    mcp.run()
