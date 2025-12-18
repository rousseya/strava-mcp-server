---
title: Strava MCP Server
emoji: 🏃
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
app_port: 7860
---

# Strava MCP Server

A comprehensive MCP server that exposes Strava activities, athlete performance stats, and activity management tools. Uses `uv` for dependency management.

## Features

- 📊 **Activity retrieval** — Get your latest activities with detailed metrics
- 📈 **Performance stats** — Access ride/run totals (recent, YTD, lifetime)
- 🏷️ **Activity renaming** — Detect and rename activities with generic names
- 🗺️ **Reverse geocoding** — Automatically convert GPS coordinates to city names
- ⚡ **E-bike detection** — Find MTB activities that might be e-bike rides
- 🔐 **Secure deployment** — Bearer token authentication for HF Spaces

## Setup

1) Install dependencies with uv

```bash
uv sync
```

2) Configure Strava API credentials

### Create a Strava App

1. Go to <https://www.strava.com/settings/api>
2. Click "Create an App" (or use an existing one)
3. Fill in the required fields:
   - **Application Name**: e.g., "My MCP Server"
   - **Category**: Choose any
   - **Club**: Leave empty
   - **Website**: Can be `http://localhost`
   - **Authorization Callback Domain**: `localhost`
4. After creation, note your **Client ID** and **Client Secret**

### Get OAuth Tokens

The access token from the Strava settings page only has `read` scope. To access activities and modify them, you need tokens with `activity:read_all` and `activity:write` scopes.

Run the included OAuth helper:

```bash
uv run python scripts/get_tokens.py
```

This will:
1. Open your browser to Strava's authorization page
2. Ask you to authorize the app with the required scopes
3. Capture the callback and exchange the code for tokens
4. Print the new `access_token` and `refresh_token`

### Create the .env file

Create a `.env` file in the project root with your credentials:

```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_ACCESS_TOKEN=access_token_from_oauth
STRAVA_REFRESH_TOKEN=refresh_token_from_oauth
```

> **Note**: The server automatically refreshes expired access tokens using the refresh token. The refresh token itself is long-lived and rarely changes.

### Manual Token Generation (Alternative)

If the helper script doesn't work, you can get tokens manually:

1. Open this URL in your browser (replace `YOUR_CLIENT_ID`):
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=read,activity:read_all,activity:write,profile:read_all
   ```

2. Authorize the app. You'll be redirected to `http://localhost/?code=AUTHORIZATION_CODE`

3. Copy the `code` parameter from the URL

4. Exchange the code for tokens using curl:
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=AUTHORIZATION_CODE \
     -d grant_type=authorization_code
   ```

5. The response contains your `access_token` and `refresh_token`

3) Run the server

```bash
uv run strava-mcp-server
```

Or run as a module:

```bash
uv run python -m strava_mcp_server
```

4) Test the tools

```bash
uv run pytest tests/ -v
```

## VS Code MCP Integration

Add to your `mcp.json`:

```json
{
  "servers": {
    "strava": {
      "type": "stdio",
      "command": "wsl",
      "args": [
        "/path/to/.venv/bin/python",
        "-m",
        "strava_mcp_server"
      ],
      "env": {
        "STRAVA_CLIENT_ID": "your_client_id",
        "STRAVA_CLIENT_SECRET": "your_client_secret",
        "STRAVA_ACCESS_TOKEN": "your_access_token",
        "STRAVA_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

## Available Tools

### 📊 Activity & Stats

| Tool | Description |
|------|-------------|
| `get_activities` | Get latest activities (default limit 30) |
| `get_activity` | Get detailed info for a specific activity |
| `get_stats` | Get athlete ride/run totals (recent, YTD, lifetime) |

### 🏷️ Activity Renaming

| Tool | Description |
|------|-------------|
| `detect_generic_named_activities` | Find activities with generic names ("Trail le midi", "Morning Run"...) |
| `get_activity_details_for_naming` | Get comprehensive info (location, effort, terrain) to suggest a better name |
| `rename_activity` | Rename an activity with a custom name |

### ⚡ E-bike Management

| Tool | Description |
|------|-------------|
| `detect_ebike_activities` | Find MTB activities that might be e-bike rides (based on cadence, effort ratio) |
| `fix_ebike_activity` | Change activity type from MTB to E-MTB |
| `update_activity_type` | Update any activity's sport type |

### 🗺️ Location Features

The server uses **reverse geocoding** (Nominatim/OpenStreetMap) to automatically convert GPS coordinates to location names:
- City, suburb, county, state, country
- Full address from coordinates
- Works even when Strava doesn't provide location data

### 💡 AI Prompt

| Prompt | Description |
|--------|-------------|
| `suggest_activity_name` | Guidelines for AI to suggest creative activity names based on location, effort, and terrain |

---

## 🚀 Deploy on Hugging Face Spaces

Deploy this MCP server to Hugging Face Spaces for use with Mistral AI or other MCP-compatible clients.

### 1) Create a Hugging Face Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose:
   - **Space name**: `strava-mcp-server`
   - **SDK**: Docker
   - **Visibility**: Private (recommended for personal use)
3. Clone the Space repo or link your GitHub repo

### 2) Update Strava App Settings

Update your Strava app's **Authorization Callback Domain**:

1. Go to <https://www.strava.com/settings/api>
2. Edit your app
3. Change **Authorization Callback Domain** to:
   ```
   your-username-strava-mcp-server.hf.space
   ```

### 3) Configure Secrets

In your HF Space settings, add these secrets:

| Secret Name | Value |
|-------------|-------|
| `STRAVA_CLIENT_ID` | Your Strava Client ID |
| `STRAVA_CLIENT_SECRET` | Your Strava Client Secret |
| `STRAVA_ACCESS_TOKEN` | Access token from OAuth helper script |
| `STRAVA_REFRESH_TOKEN` | Refresh token from OAuth helper script |
| `SPACE_URL` | `https://your-username-strava-mcp-server.hf.space` |
| `SECRET_KEY` | Random string for session encryption |
| `API_TOKEN` | (Optional) Bearer token to secure the MCP endpoint |

> **Note**: Since HF Spaces can't be used as OAuth callback domain, generate tokens locally with `scripts/get_tokens.py` and add them as secrets.

### 4) Deploy

Push your code to the Space. The Dockerfile will build and deploy automatically.

### 5) Connect Your Strava Account

1. Visit your Space URL: `https://your-username-strava-mcp-server.hf.space`
2. Click **"Connect with Strava"**
3. Authorize the app
4. You're connected! ✅

### 6) Use with Mistral AI or MCP Clients

Your MCP server endpoint is:
```
https://your-username-strava-mcp-server.hf.space/mcp/sse
```

#### Mistral AI (Le Chat)

Add the MCP server in Mistral's settings using the SSE endpoint above.

#### VS Code with HTTP MCP

```json
{
  "servers": {
    "strava": {
      "type": "http",
      "url": "https://your-username-strava-mcp-server.hf.space/mcp/sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

> **Note**: If you set an `API_TOKEN` secret, include it in the `Authorization` header.

### Local Development (HF Mode)

To test the HF Spaces version locally:

```bash
# Set environment variables
export STRAVA_CLIENT_ID=your_client_id
export STRAVA_CLIENT_SECRET=your_client_secret
export SPACE_URL=http://localhost:7860

# Run the app
uv run python app.py
```

Then visit http://localhost:7860 and click "Connect with Strava".

---

## Development

### Run tests

```bash
uv run pytest tests/ -v
```

### Lint and format

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Dependencies

- **mcp** — Model Context Protocol SDK
- **stravalib** — Strava API client
- **geopy** — Reverse geocoding (GPS → city names)
- **fastapi** — Web framework for HF Spaces deployment
- **python-dotenv** — Environment variable management

## Example Usage

### Detect activities with generic names

```python
from strava_mcp_server.main import detect_generic_named_activities

activities = detect_generic_named_activities(limit=20)
for a in activities:
    print(f'{a["current_name"]} @ {a["location"]}')
# Output:
# Trail le midi @ Biot, Provence-Alpes-Côte d'Azur, France
# Sortie VTT le matin @ Montauroux, Provence-Alpes-Côte d'Azur, France
```

### Get detailed info for renaming

```python
from strava_mcp_server.main import get_activity_details_for_naming

details = get_activity_details_for_naming(16721355080)
print(f'City: {details["location"]["city"]}')
print(f'Suburb: {details["location"]["suburb"]}')
print(f'Elevation: {details["metrics"]["elevation_gain_m"]}m')
print(f'Effort: {details["effort"]["effort_level"]}')
# Output:
# City: Biot
# Suburb: Sophia Antipolis
# Elevation: 248m
# Effort: easy
```

## License

MIT