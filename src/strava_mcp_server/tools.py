from .strava_client import StravaClient


def get_strava_activities(limit: int = 30):
    client = StravaClient()
    activities = client.get_activities(limit=limit)
    return [
        {
            "id": activity.id,
            "name": activity.name,
            "type": activity.type,
            "distance": float(activity.distance or 0),
            "moving_time": activity.moving_time.total_seconds() if activity.moving_time else 0,
            "elapsed_time": activity.elapsed_time.total_seconds() if activity.elapsed_time else 0,
            "elevation_gain": float(activity.total_elevation_gain or 0),
            "start_date_local": activity.start_date_local.isoformat() if activity.start_date_local else None,
        }
        for activity in activities
    ]


def get_strava_activity(activity_id: int):
    client = StravaClient()
    activity = client.get_activity(activity_id)
    return {
        "id": activity.id,
        "name": activity.name,
        "type": activity.type,
        "distance": float(activity.distance or 0),
        "moving_time": activity.moving_time.total_seconds() if activity.moving_time else 0,
        "elapsed_time": activity.elapsed_time.total_seconds() if activity.elapsed_time else 0,
        "elevation_gain": float(activity.total_elevation_gain or 0),
        "start_date_local": activity.start_date_local.isoformat() if activity.start_date_local else None,
        "average_speed": float(activity.average_speed or 0),
        "max_speed": float(activity.max_speed or 0),
        "average_heartrate": float(activity.average_heartrate or 0),
        "max_heartrate": float(activity.max_heartrate or 0),
        "suffer_score": getattr(activity, "suffer_score", None),
        "kudos_count": getattr(activity, "kudos_count", None),
    }


def get_strava_stats():
    client = StravaClient()
    stats = client.get_stats()
    if not stats:
        return {}
    return {
        "recent_ride_totals": stats.recent_ride_totals.to_dict() if stats.recent_ride_totals else None,
        "recent_run_totals": stats.recent_run_totals.to_dict() if stats.recent_run_totals else None,
        "ytd_ride_totals": stats.ytd_ride_totals.to_dict() if stats.ytd_ride_totals else None,
        "ytd_run_totals": stats.ytd_run_totals.to_dict() if stats.ytd_run_totals else None,
        "all_ride_totals": stats.all_ride_totals.to_dict() if stats.all_ride_totals else None,
        "all_run_totals": stats.all_run_totals.to_dict() if stats.all_run_totals else None,
    }
