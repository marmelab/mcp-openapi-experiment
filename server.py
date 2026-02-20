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
    route_maps=[
        RouteMap(
            mcp_type=MCPType.RESOURCE,
            methods=["GET"]
        )
    ]
)

@mcp.tool
async def list_api_resources() -> list[dict]:
    """
    List all available API resources with their URIs and descriptions.
    Call this tool to discover what data is accessible before reading it.
    Returns a list of resources with their URI, name, and description.
    """
    base_url = client.base_url.rstrip("/")
    resources = []
    for path, path_item in openapi_spec.get("paths", {}).items():
        if "get" in path_item:
            get_op = path_item["get"]
            uri = f"{base_url}{path}"
            parameters = [
                p["name"]
                for p in get_op.get("parameters", [])
                if p.get("in") == "query"
            ]
            resources.append({
                "uri": uri,
                "name": get_op.get("summary") or path,
                "description": get_op.get("description") or get_op.get("summary") or "",
                "filter_parameters": parameters,
            })
    return resources


@mcp.tool
async def read_api_resource(uri: str) -> str:
    """
    Read the content of an API resource by its URI.
    Use list_api_resources first to discover available resource URIs.
    You can append query parameters to filter results
    (e.g. http://localhost:54321/rest/v1/contacts?id=eq.42).

    Args:
        uri: The full URI of the resource to read, with optional query parameters.
    """
    response = await client.get(uri)
    response.raise_for_status()
    return response.text


if __name__ == "__main__":
    mcp.run('streamable-http')