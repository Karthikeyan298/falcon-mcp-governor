"""Runtime discovery helpers: given a list of MCP tools (name + description +
input_schema) advertised by a server, pick the tool that best matches an
intent and map our field names onto that tool's actual argument names.

This lets the agent work against MCP servers whose exact tool names/schemas
aren't known ahead of time.
"""

from typing import Any


def select_tool(tools: list[dict[str, Any]], keywords: list[str]) -> dict[str, Any]:
    if not tools:
        raise RuntimeError("MCP server exposed no tools")

    def score(tool: dict[str, Any]) -> int:
        haystack = f"{tool['name']} {tool['description']}".lower()
        return sum(1 for kw in keywords if kw in haystack)

    ranked = sorted(tools, key=score, reverse=True)
    best = ranked[0]
    if score(best) == 0:
        raise RuntimeError(
            f"No tool matched keywords {keywords}. "
            f"Available: {[t['name'] for t in tools]}. "
            "The required tool may be blocked by policy."
        )
    return best


_CONTAINER_ALIASES = ["data", "record", "fields", "payload", "values", "attributes"]


def _is_object_schema(schema: dict[str, Any]) -> bool:
    return schema.get("type") == "object" or "additionalProperties" in schema


def _coerce(value: Any, schema: dict[str, Any]) -> Any:
    if schema.get("type") == "array" and not isinstance(value, list):
        return [value]
    return value


def map_arguments(
    tool: dict[str, Any], field_aliases: dict[str, list[str]], values: dict[str, str]
) -> dict[str, Any]:
    """Maps canonical field names onto a tool's actual argument names.

    Handles two shapes MCP tools commonly use: flat top-level fields
    (e.g. `to`, `subject`, `body`) and a single nested "container" object
    (e.g. `create_record(table, data)` where unrelated fields belong inside
    `data`). Also coerces scalars into single-item lists when the target
    field is declared as an array.
    """
    properties: dict[str, Any] = tool.get("input_schema", {}).get("properties", {})
    prop_names = list(properties.keys())
    mapped: dict[str, Any] = {}
    unmapped: dict[str, Any] = {}

    for canonical, value in values.items():
        aliases = [canonical] + field_aliases.get(canonical, [])
        aliases_lower = [a.lower() for a in aliases]

        match = next((p for p in prop_names if p.lower() in aliases_lower), None)
        if not match:
            match = next(
                (
                    p
                    for p in prop_names
                    if any(a in p.lower() or p.lower() in a for a in aliases_lower)
                ),
                None,
            )
        if match:
            mapped[match] = _coerce(value, properties[match])
        else:
            unmapped[canonical] = value

    if unmapped:
        container = next(
            (
                p
                for p in prop_names
                if p not in mapped
                and _is_object_schema(properties[p])
                and p.lower() in _CONTAINER_ALIASES
            ),
            None,
        )
        if container:
            mapped[container] = unmapped

    return mapped
