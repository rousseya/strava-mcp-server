"""
Strava MCP Server for Hugging Face Spaces deployment.
Provides OAuth2 flow and MCP tools via SSE transport.
"""

import os
import secrets
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer
from geopy.geocoders import Nominatim
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: F401
from starlette.responses import JSONResponse
from stravalib.client import Client

load_dotenv()

# Configuration
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
SPACE_URL = os.getenv("SPACE_URL", "http://localhost:7860")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
API_TOKEN = os.getenv("API_TOKEN")  # Token for MCP authentication

# Security
security = HTTPBearer(auto_error=False)

# Initialize geocoder for reverse geocoding (GPS -> city name)
_geocoder = Nominatim(user_agent="strava-mcp-server")

# In-memory token storage (for demo; use database in production)
user_tokens: dict[str, dict] = {}

# FastAPI app
app = FastAPI(
    title="Strava MCP Server",
    description="MCP Server for Strava activities and stats",
)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# MCP Server
mcp = FastMCP(
    "strava",
    host="0.0.0.0",
    port=7860,
)

# Configure allowed hosts for SSE validation
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "rousseya-strava-mcp-server.hf.space",
]


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


def get_strava_client(access_token: str) -> Client:
    """Create a Strava client with the given access token."""
    client = Client()
    client.access_token = access_token
    return client


def to_seconds(duration):
    """Convert stravalib Duration to seconds."""
    if duration is None:
        return 0
    if hasattr(duration, "total_seconds"):
        return duration.total_seconds()
    return int(duration)


# ============== OAuth2 Endpoints ==============


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with OAuth link."""
    session_id = request.session.get("session_id")
    is_authenticated = session_id and session_id in user_tokens

    if is_authenticated:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Strava MCP Server</title></head>
        <body style="font-family: sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
            <h1>✅ Connected to Strava!</h1>
            <p>Your MCP server is ready. Use the SSE endpoint:</p>
            <pre style="background: #f0f0f0; padding: 10px;">{SPACE_URL}/mcp/sse</pre>
            <p><a href="/logout">Disconnect</a></p>
        </body>
        </html>
        """

    return """
    <!DOCTYPE html>
    <html>
    <head><title>Strava MCP Server</title></head>
    <body style="font-family: sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
        <h1>🏃 Strava MCP Server</h1>
        <p>Connect your Strava account to use this MCP server with AI assistants.</p>
        <a href="/auth" style="display: inline-block; background: #fc4c02; color: white; 
           padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
            Connect with Strava
        </a>
        <h2>Available Tools</h2>
        <ul>
            <li><strong>get_activities</strong> — Get your latest activities</li>
            <li><strong>get_activity</strong> — Get details for a specific activity</li>
            <li><strong>get_stats</strong> — Get your ride/run totals</li>
            <li><strong>detect_generic_named_activities</strong> — Find generic names</li>
            <li><strong>get_activity_details_for_naming</strong> — Get naming info</li>
            <li><strong>rename_activity</strong> — Rename an activity</li>
        </ul>
    </body>
    </html>
    """


@app.get("/auth")
async def auth(request: Request):
    """Start OAuth2 flow - redirect to Strava authorization."""
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="STRAVA_CLIENT_ID not configured")

    # Generate session ID
    session_id = secrets.token_urlsafe(32)
    request.session["session_id"] = session_id

    # Build Strava authorization URL
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": f"{SPACE_URL}/auth/callback",
        "response_type": "code",
        "scope": "read,activity:read_all,profile:read_all",
        "state": session_id,
    }
    auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"

    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """OAuth2 callback - exchange code for tokens."""
    if error:
        return HTMLResponse(
            f"""
            <html><body style="font-family: sans-serif; padding: 40px;">
            <h1>❌ Authorization Failed</h1>
            <p>Error: {error}</p>
            <a href="/">Try again</a>
            </body></html>
            """,
            status_code=400,
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Verify state matches session
    session_id = request.session.get("session_id")
    if not state or state != session_id:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for tokens
    try:
        client = Client()
        tokens = client.exchange_code_for_token(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            code=code,
        )

        # Store tokens
        user_tokens[session_id] = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": tokens.get("expires_at"),
        }

        return RedirectResponse(url="/")

    except Exception as e:
        return HTMLResponse(
            f"""
            <html><body style="font-family: sans-serif; padding: 40px;">
            <h1>❌ Token Exchange Failed</h1>
            <p>Error: {str(e)}</p>
            <a href="/">Try again</a>
            </body></html>
            """,
            status_code=500,
        )


@app.get("/logout")
async def logout(request: Request):
    """Clear session and tokens."""
    session_id = request.session.get("session_id")
    if session_id and session_id in user_tokens:
        del user_tokens[session_id]
    request.session.clear()
    return RedirectResponse(url="/")


# ============== MCP Tools ==============


def get_current_client() -> Client:
    """Get Strava client for the current session (or use env tokens)."""
    # Check for stored tokens first
    for tokens in user_tokens.values():
        if tokens.get("access_token"):
            client = Client()
            client.access_token = tokens["access_token"]
            client.refresh_token = tokens.get("refresh_token")

            # Auto-refresh if needed
            if CLIENT_ID and CLIENT_SECRET and tokens.get("refresh_token"):
                try:
                    new_tokens = client.refresh_access_token(
                        client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        refresh_token=tokens["refresh_token"],
                    )
                    if new_tokens:
                        client.access_token = new_tokens.get("access_token", client.access_token)
                        tokens["access_token"] = client.access_token
                except Exception:
                    pass

            return client

    # Fall back to environment tokens
    access_token = os.getenv("STRAVA_ACCESS_TOKEN")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated. Visit / to connect Strava.")

    client = Client()
    client.access_token = access_token
    client.refresh_token = refresh_token

    if CLIENT_ID and CLIENT_SECRET and refresh_token:
        try:
            new_tokens = client.refresh_access_token(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=refresh_token,
            )
            if new_tokens:
                client.access_token = new_tokens.get("access_token", client.access_token)
        except Exception:
            pass

    return client


@mcp.tool()
def get_activities(limit: int = 30) -> list[dict]:
    """Get the latest Strava activities.

    Args:
        limit: Maximum number of activities to return (default 30).

    Returns:
        List of activity summaries with id, name, type, distance, time, elevation, and date.
    """
    client = get_current_client()
    activities = list(client.get_activities(limit=limit))
    return [
        {
            "id": activity.id,
            "name": activity.name,
            "type": str(activity.type),
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
    client = get_current_client()
    activity = client.get_activity(activity_id)
    return {
        "id": activity.id,
        "name": activity.name,
        "type": str(activity.type),
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
    client = get_current_client()
    athlete = client.get_athlete()
    if not athlete:
        return {}

    stats = client.get_athlete_stats(athlete.id)
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


# Generic activity names to detect (French and English)
GENERIC_ACTIVITY_NAMES = [
    # French patterns - Time of day
    "Trail en soirée",
    "Trail le midi",
    "Trail dans l'après-midi",
    "Trail matinal",
    "Course en soirée",
    "Course le midi",
    "Course dans l'après-midi",
    "Course matinale",
    "Sortie vélo en soirée",
    "Sortie vélo le midi",
    "Sortie vélo dans l'après-midi",
    "Vélo en soirée",
    "Vélo le midi",
    "Vélo dans l'après-midi",
    "Vélo matinal",
    "Randonnée en soirée",
    "Randonnée le midi",
    "Randonnée dans l'après-midi",
    "Marche en soirée",
    "Marche le midi",
    "Marche dans l'après-midi",
    # English patterns - Time of day
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
    "Afternoon Hike",
    "Evening Hike",
    "Morning Trail Run",
    "Afternoon Trail Run",
    "Evening Trail Run",
    # Generic day patterns
    "Activité",
    "Activity",
    "Workout",
    "Exercise",
    "Training",
    "Sortie",
    "Balade",
    "Promenade",
    # E-bike patterns
    "E-Bike Ride",
    "Sortie vélo électrique",
    "VAE",
]


@mcp.tool()
def detect_generic_named_activities(limit: int = 50) -> list[dict]:
    """Detect activities that have generic names and could benefit from renaming.

    Args:
        limit: Maximum number of activities to scan (default 50).

    Returns:
        List of activities with generic names, including id, current name, type, and date.
    """
    client = get_current_client()
    activities = list(client.get_activities(limit=limit))

    generic_activities = []
    for activity in activities:
        name = activity.name
        # Check if the name matches any generic pattern (case-insensitive)
        is_generic = any(
            generic.lower() in name.lower() or name.lower() in generic.lower()
            for generic in GENERIC_ACTIVITY_NAMES
        )

        if is_generic:
            # Get start coordinates for reverse geocoding
            start_latlng = getattr(activity, "start_latlng", None)
            location_city = None
            location_state = None
            location_country = None

            # Try reverse geocoding with GPS coordinates
            if start_latlng:
                try:
                    lat = start_latlng.lat
                    lon = start_latlng.lon
                    if lat and lon:
                        geo = reverse_geocode(lat, lon)
                        location_city = geo.get("city")
                        location_state = geo.get("state")
                        location_country = geo.get("country")
                except Exception:
                    pass

            # Build location string
            location_parts = [p for p in [location_city, location_state, location_country] if p]
            location = ", ".join(location_parts) if location_parts else "Lieu inconnu"

            generic_activities.append(
                {
                    "id": activity.id,
                    "name": name,
                    "type": str(activity.type),
                    "location": location,
                    "distance": float(activity.distance or 0),
                    "elevation_gain": float(activity.total_elevation_gain or 0),
                    "start_date_local": (
                        activity.start_date_local.isoformat() if activity.start_date_local else None
                    ),
                }
            )

    return generic_activities


@mcp.tool()
def get_activity_details_for_naming(activity_id: int) -> dict:
    """Get comprehensive activity details to help suggest a better name.

    This tool provides all relevant information about an activity that can be used
    to generate a creative and meaningful name based on location, effort, and performance.

    Args:
        activity_id: The Strava activity ID.

    Returns:
        Detailed activity information including location, performance metrics, and effort data.
    """
    client = get_current_client()
    activity = client.get_activity(activity_id)

    # Extract location info from Strava
    start_latlng = getattr(activity, "start_latlng", None)
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

    # Calculate performance metrics
    distance_km = float(activity.distance or 0) / 1000
    elevation_gain = float(activity.total_elevation_gain or 0)
    moving_time_seconds = to_seconds(activity.moving_time)

    # Calculate pace/speed
    if moving_time_seconds > 0 and distance_km > 0:
        if str(activity.type) in ["Run", "Trail Run", "TrailRun", "Walk", "Hike"]:
            # Pace in min/km
            pace_seconds = moving_time_seconds / distance_km
            pace_minutes = int(pace_seconds // 60)
            pace_secs = int(pace_seconds % 60)
            pace = f"{pace_minutes}:{pace_secs:02d} min/km"
        else:
            # Speed in km/h
            speed = (distance_km / moving_time_seconds) * 3600
            pace = f"{speed:.1f} km/h"
    else:
        pace = "N/A"

    # Effort indicators
    avg_hr = float(activity.average_heartrate or 0) if activity.average_heartrate else None
    max_hr = float(activity.max_heartrate or 0) if activity.max_heartrate else None
    suffer_score = getattr(activity, "suffer_score", None)

    # Elevation profile
    elevation_per_km = elevation_gain / distance_km if distance_km > 0 else 0

    return {
        "id": activity.id,
        "current_name": activity.name,
        "type": str(activity.type),
        "location": location,
        "location_city": location_city,
        "location_state": location_state,
        "location_country": location_country,
        "suburb": geo_info.get("suburb"),
        "county": geo_info.get("county"),
        "full_address": geo_info.get("full_address"),
        "distance_km": round(distance_km, 2),
        "elevation_gain_m": round(elevation_gain, 0),
        "elevation_per_km": round(elevation_per_km, 1),
        "moving_time_minutes": round(moving_time_seconds / 60, 1),
        "pace_or_speed": pace,
        "average_heartrate": avg_hr,
        "max_heartrate": max_hr,
        "suffer_score": suffer_score,
        "start_date_local": (
            activity.start_date_local.isoformat() if activity.start_date_local else None
        ),
        "description": getattr(activity, "description", None),
    }


@mcp.tool()
def rename_activity(activity_id: int, new_name: str) -> dict:
    """Rename a Strava activity.

    Args:
        activity_id: The Strava activity ID to rename.
        new_name: The new name for the activity.

    Returns:
        Updated activity information with the new name.
    """
    client = get_current_client()

    # Update the activity name using stravalib
    updated = client.update_activity(activity_id, name=new_name)

    return {
        "id": updated.id,
        "name": updated.name,
        "type": str(updated.type),
        "message": f"Activity renamed to: {updated.name}",
    }


# Mount MCP SSE transport with custom host validation and authentication


@mcp.prompt()
def suggest_activity_name() -> str:
    """Prompt template to help AI suggest creative activity names."""
    return """Tu es un assistant pour renommer les activités Strava.
Voici comment suggérer un bon nom:

## Critères pour un bon nom d'activité

### 1. Lieu géographique
- Utilise le nom de la ville, région ou lieu emblématique
- Exemples: "Les crêtes du Vercors", "Boucle autour du lac d'Annecy", "Trail des Calanques"

### 2. Type d'activité et terrain
- Mentionne le type de terrain (forêt, montagne, côte, urbain)
- Exemples: "Escapade en forêt de Fontainebleau", "Montée vers le Col du Galibier"

### 3. Effort et performance
- Pour les sorties intenses: utilise des mots comme "Challenge", "Défi", "Sprint", "Tempo"
- Pour les sorties longues: "Exploration", "Grande boucle", "Traversée"
- Pour les sorties faciles: "Balade", "Récupération", "Découverte"

### 4. Conditions météo ou saison (si pertinent)
- "Trail sous la pluie", "Sortie au lever du soleil", "Course hivernale"

### 5. Éléments mémorables
- Dénivelé important: "Ascension de 1000m+", "Les 3 cols"
- Distance notable: "Semi-marathon des vignes", "Century ride"

## Exemples de transformation

| Nom générique | Données | Suggestion |
|---------------|---------|------------|
| "Trail le midi" | Grenoble, 15km, 800m D+ | "Les balcons de Chartreuse" |
| "Course matinale" | Paris, 10km, plat | "Boucle des quais de Seine" |
| "Vélo en soirée" | Nice, 50km, 600m D+ | "Coucher de soleil sur l'Estérel" |
| "Morning Run" | Lyon, 8km, Parc | "Tour du Parc de la Tête d'Or" |

## Instructions

1. Utilise `detect_generic_named_activities` pour trouver les activités à renommer
2. Utilise `get_activity_details_for_naming` pour obtenir les détails de chaque activité
3. Propose 2-3 suggestions de noms basées sur les critères ci-dessus
4. Demande confirmation avant de renommer avec `rename_activity`

Garde les noms courts (3-6 mots) et évocateurs!"""


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to verify Bearer token for MCP endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth if no API_TOKEN is configured (open access)
        if not API_TOKEN:
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header.replace("Bearer ", "")
        if token != API_TOKEN:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API token"},
            )

        return await call_next(request)


mcp_app = mcp.sse_app()
mcp_app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
mcp_app.add_middleware(AuthMiddleware)
app.mount("/mcp", mcp_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)
