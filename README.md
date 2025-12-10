# Strava MCP Server

A minimal MCP server that exposes Strava activities and athlete performance stats. Uses `uv` for dependency management.

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

The access token from the Strava settings page only has `read` scope. To access activities, you need tokens with `activity:read_all` scope.

Run the included OAuth helper:

```bash
uv run python get_tokens.py
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
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=read,activity:read_all,profile:read_all
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
uv run python test_tools.py
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

## Available tools

- `get_activities` — latest activities (default limit 30)
- `get_activity` — details for a specific activity id
- `get_stats` — athlete ride/run totals (recent, YTD, lifetime)