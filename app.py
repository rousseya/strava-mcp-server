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


# Mount MCP SSE transport with custom host validation and authentication


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
