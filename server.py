import httpx
from fastmcp import FastMCP
from fastmcp.server.openapi import RouteMap, MCPType
import json
import os

# Get API token from environment
api_token = os.getenv("SERVICE_API_TOKEN", "")

# Create an HTTP client for your API with authentication headers
client = httpx.AsyncClient(
    base_url="http://localhost:54321/rest/v1/",
    headers={
        "apikey": f"{api_token}",
        "Authorization": f"Bearer {api_token}"
    }
)

# Load your OpenAPI spec 
with open("openapi_spec.json") as f:
    openapi_spec = json.load(f)

# Create the MCP server with route mappings
mcp = FastMCP.from_openapi(
    openapi_spec=openapi_spec,
    client=client,
    name="My API Server",
)

if __name__ == "__main__":
    mcp.run('streamable-http')