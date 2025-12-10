import requests
import json

class MCPClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def list_tools(self):
        response = requests.get(f"{self.base_url}/tools")
        response.raise_for_status()
        return response.json()["tools"]

    def run_tool(self, tool_name, params=None):
        response = requests.post(f"{self.base_url}/tools/{tool_name}", json=params)
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    client = MCPClient("http://127.0.0.1:8000")

    print("Available tools:")
    tools = client.list_tools()
    for tool in tools:
        print(f"- {tool}")

    print("\nRunning tool 'strava.get_activities'...")
    result = client.run_tool("strava.get_activities")
    print("Result:")
    print(json.dumps(result, indent=2))
