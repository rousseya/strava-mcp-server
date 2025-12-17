#!/usr/bin/env python3
"""
OAuth flow to get Strava tokens with activity:read_all and activity:write scopes.
Run this script and follow the instructions.
"""

import http.server
import urllib.parse
import webbrowser
from stravalib.client import Client

CLIENT_ID = "177196"
CLIENT_SECRET = "408ae9b86190b43bafb9209c6e5f081841d3d9b7"
REDIRECT_URI = "http://localhost:8000/authorized"

client = Client()

# Generate authorization URL with required scopes (including write for updating activities)
auth_url = client.authorization_url(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    scope=["read", "activity:read_all", "activity:write", "profile:read_all"]
)

print(f"\n1. Opening browser to authorize...\n")
print(f"   If it doesn't open, go to:\n   {auth_url}\n")
webbrowser.open(auth_url)

# Simple HTTP server to capture the callback
class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            code = params["code"][0]
            print(f"2. Got authorization code!")
            
            # Exchange code for tokens
            try:
                tokens = client.exchange_code_for_token(
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                    code=code
                )
                
                access_token = tokens["access_token"]
                refresh_token = tokens["refresh_token"]
                
                print(f"\n✅ SUCCESS! Update your .env and mcp.json with these tokens:\n")
                print(f"STRAVA_ACCESS_TOKEN={access_token}")
                print(f"STRAVA_REFRESH_TOKEN={refresh_token}")
                
                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <html><body style="font-family: sans-serif; padding: 40px;">
                <h1>Success!</h1>
                <p>Tokens received. Check your terminal for the new tokens.</p>
                <p>You can close this window.</p>
                </body></html>
                """)
                
                # Signal to stop the server
                self.server.tokens = tokens
                
            except Exception as e:
                print(f"\n❌ Error exchanging code: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            error = params.get("error", ["Unknown"])[0]
            print(f"\n❌ Authorization failed: {error}")
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

print("3. Waiting for Strava callback on http://localhost:8000 ...")
print("   (Press Ctrl+C to cancel)\n")

server = http.server.HTTPServer(("localhost", 8000), OAuthHandler)
server.tokens = None

# Handle one request
server.handle_request()

if server.tokens:
    print("\n" + "="*50)
    print("Copy these to your .env file and mcp.json:")
    print("="*50)
    print(f'STRAVA_ACCESS_TOKEN={server.tokens["access_token"]}')
    print(f'STRAVA_REFRESH_TOKEN={server.tokens["refresh_token"]}')
