import httpx
import json
import os
from fastmcp import FastMCP

# Get configuration from environment
GRAPHQL_URL = os.getenv("GRAPHQL_URL", "http://127.0.0.1:54321/graphql/v1")
api_token = os.getenv("SERVICE_API_TOKEN", "")
port = int(os.getenv("GRAPHQL_PORT", "8001"))

# Build auth headers
headers = {"Content-Type": "application/json"}
if api_token:
    headers["Authorization"] = f"Bearer {api_token}"

client = httpx.AsyncClient(headers=headers)

mcp = FastMCP("GraphQL MCP Server")

# Standard introspection query to fully describe the schema
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          description
          type { kind name ofType { kind name ofType { kind name } } }
          defaultValue
        }
        type { kind name ofType { kind name ofType { kind name } } }
        isDeprecated
        deprecationReason
      }
      inputFields {
        name
        description
        type { kind name ofType { kind name ofType { kind name } } }
        defaultValue
      }
      interfaces { name }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes { name }
    }
  }
}
"""


def _resolve_type_name(type_ref: dict) -> str:
    """Recursively resolve a GraphQL TypeRef to a human-readable string."""
    if type_ref is None:
        return "Unknown"
    kind = type_ref.get("kind", "")
    if kind == "NON_NULL":
        return f"{_resolve_type_name(type_ref.get('ofType'))}!"
    if kind == "LIST":
        return f"[{_resolve_type_name(type_ref.get('ofType'))}]"
    return type_ref.get("name", "Unknown")


async def _run_graphql(query: str, variables: dict | None = None) -> dict:
    """Send a GraphQL request and return the parsed JSON response."""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    response = await client.post(GRAPHQL_URL, json=payload)
    response.raise_for_status()
    return response.json()


@mcp.tool
async def introspect_schema() -> dict:
    """
    Retrieve the full GraphQL schema via introspection.
    Returns all types, fields, queries, mutations and their signatures.
    Call this to get a raw, exhaustive view of the API schema.
    """
    result = await _run_graphql(INTROSPECTION_QUERY)
    if "errors" in result:
        raise ValueError(f"GraphQL introspection errors: {result['errors']}")
    return result.get("data", {})


@mcp.tool
async def list_operations() -> dict:
    """
    List all available GraphQL queries and mutations with their arguments
    and return types, skipping built-in introspection types.
    Call this first to discover what operations are available.
    Returns:
        A dict with 'queries' and 'mutations' lists, each item containing:
        name, description, return_type, and args (name, type, description, default_value).
    """
    result = await _run_graphql(INTROSPECTION_QUERY)
    if "errors" in result:
        raise ValueError(f"GraphQL errors: {result['errors']}")

    schema = result.get("data", {}).get("__schema", {})
    types_by_name = {t["name"]: t for t in schema.get("types", []) if t.get("name")}

    def _format_fields(type_name: str | None) -> list[dict]:
        if not type_name or type_name not in types_by_name:
            return []
        return [
            {
                "name": f["name"],
                "description": f.get("description") or "",
                "return_type": _resolve_type_name(f.get("type")),
                "args": [
                    {
                        "name": a["name"],
                        "type": _resolve_type_name(a.get("type")),
                        "description": a.get("description") or "",
                        "default_value": a.get("defaultValue"),
                    }
                    for a in f.get("args") or []
                ],
                "is_deprecated": f.get("isDeprecated", False),
                "deprecation_reason": f.get("deprecationReason"),
            }
            for f in types_by_name[type_name].get("fields") or []
        ]

    query_type = (schema.get("queryType") or {}).get("name")
    mutation_type = (schema.get("mutationType") or {}).get("name")
    subscription_type = (schema.get("subscriptionType") or {}).get("name")

    queries = _format_fields(query_type)
    mutations = _format_fields(mutation_type)
    subscriptions = _format_fields(subscription_type)

    return {
        "query_count": len(queries),
        "mutation_count": len(mutations),
        "subscription_count": len(subscriptions),
        "queries": queries,
        "mutations": mutations,
        "subscriptions": subscriptions,
    }


@mcp.tool
async def get_type_details(type_name: str) -> dict:
    """
    Get the full definition of a specific GraphQL type (object, input, enum, union, etc.).
    Use list_operations or introspect_schema first to find type names.

    Args:
        type_name: The exact GraphQL type name (e.g. 'User', 'CreateUserInput').
    """
    query = """
    query TypeDetails($name: String!) {
      __type(name: $name) {
        kind
        name
        description
        fields(includeDeprecated: true) {
          name
          description
          type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
          args {
            name
            description
            type { kind name ofType { kind name ofType { kind name } } }
            defaultValue
          }
          isDeprecated
          deprecationReason
        }
        inputFields {
          name
          description
          type { kind name ofType { kind name ofType { kind name } } }
          defaultValue
        }
        enumValues(includeDeprecated: true) {
          name
          description
          isDeprecated
          deprecationReason
        }
        interfaces { name }
        possibleTypes { name }
      }
    }
    """
    result = await _run_graphql(query, variables={"name": type_name})
    if "errors" in result:
        raise ValueError(f"GraphQL errors: {result['errors']}")
    type_info = (result.get("data") or {}).get("__type")
    if not type_info:
        raise ValueError(f"Type '{type_name}' not found in schema. "
                         "Use list_operations to discover available types.")
    return type_info


@mcp.tool
async def execute_query(query: str, variables: str = "{}") -> dict:
    """
    Execute a GraphQL query and return the data payload.
    Use list_operations first to know the available queries and their arguments.

    Args:
        query: Full GraphQL query string.
               Example: '{ users { id name email } }'
               Example with args: 'query($id: ID!) { user(id: $id) { id name } }'
        variables: JSON-encoded variables object.
                   Example: '{"id": "42"}'
    """
    try:
        vars_dict: dict | None = json.loads(variables) if variables.strip() not in ("", "{}") else None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in variables: {exc}") from exc

    result = await _run_graphql(query, variables=vars_dict)
    if "errors" in result:
        raise ValueError(f"GraphQL errors: {result['errors']}")
    return result.get("data") or {}


@mcp.tool
async def execute_mutation(mutation: str, variables: str = "{}") -> dict:
    """
    Execute a GraphQL mutation and return the data payload.
    Use list_operations first to know the available mutations and their arguments.

    Args:
        mutation: Full GraphQL mutation string.
                  Example: 'mutation($name: String!) { createUser(name: $name) { id name } }'
        variables: JSON-encoded variables object.
                   Example: '{"name": "Alice"}'
    """
    try:
        vars_dict: dict | None = json.loads(variables) if variables.strip() not in ("", "{}") else None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in variables: {exc}") from exc

    result = await _run_graphql(mutation, variables=vars_dict)
    if "errors" in result:
        raise ValueError(f"GraphQL mutation errors: {result['errors']}")
    return result.get("data") or {}


if __name__ == "__main__":
    mcp.run("streamable-http", port=port)
