from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.config import settings
from app.llm.factory import get_llm_provider
from app.mcp.client import call_tool, list_tools
from app.mcp.resolver import map_arguments, select_tool

STORY_PROMPT = (
    "Write an engaging short story (roughly 300-500 words) titled '{title}'. "
    "Return only the story text, no preamble."
)

DB_KEYWORDS = ["save", "store", "create", "insert", "persist", "write", "story", "record"]
DB_TABLE_NAME = "stories"
DB_TABLE_COLUMNS = {"title": "TEXT", "content": "TEXT"}
DB_FIELD_ALIASES = {
    "table": ["table", "collection", "entity"],
    "title": ["title", "name", "subject"],
    "content": ["content", "story", "body", "text"],
}
DB_CREATE_TABLE_KEYWORDS = ["create", "table"]
DB_TABLE_MISSING_HINTS = ["does not exist", "no such table", "doesn't exist", "not found"]

EMAIL_KEYWORDS = ["send", "email", "mail", "notify", "message"]
EMAIL_FIELD_ALIASES = {
    "to": ["to", "recipient", "recipient_email", "email"],
    "subject": ["subject", "title"],
    "body": ["body", "content", "message", "text"],
}


def _flatten(exc: BaseException) -> str:
    """Unwraps nested ExceptionGroups (raised by anyio task groups) down to
    the innermost message, so callers see the real failure instead of an
    opaque 'unhandled errors in a TaskGroup'."""
    sub_exceptions = getattr(exc, "exceptions", None)
    while sub_exceptions:
        exc = sub_exceptions[0]
        sub_exceptions = getattr(exc, "exceptions", None)
    return str(exc)


async def generate_story(state: AgentState) -> AgentState:
    llm = get_llm_provider()
    prompt = STORY_PROMPT.format(title=state["title"])
    story = await llm.generate(prompt)
    return {"story": story}


async def _create_table_if_missing(tools: list[dict], server_url: str) -> None:
    create_tool = select_tool(tools, DB_CREATE_TABLE_KEYWORDS)
    args = map_arguments(
        create_tool,
        {"table": ["table", "collection", "entity"], "columns": ["columns", "fields", "schema"]},
        {"table": DB_TABLE_NAME, "columns": DB_TABLE_COLUMNS},
    )
    await call_tool(server_url, create_tool["name"], args)


async def store_story(state: AgentState) -> AgentState:
    try:
        db_url = settings.db_mcp_server_url
        tools = await list_tools(db_url)
        tool = select_tool(tools, DB_KEYWORDS)
        args = map_arguments(
            tool,
            DB_FIELD_ALIASES,
            {"table": DB_TABLE_NAME, "title": state["title"], "content": state["story"]},
        )
        try:
            await call_tool(db_url, tool["name"], args)
        except RuntimeError as insert_exc:
            if not any(hint in str(insert_exc).lower() for hint in DB_TABLE_MISSING_HINTS):
                raise
            await _create_table_if_missing(tools, db_url)
            await call_tool(db_url, tool["name"], args)
        return {"db_status": "saved", "db_tool_used": tool["name"]}
    except Exception as exc:  # noqa: BLE001 - surface failure to the caller
        return {"db_status": f"failed: {_flatten(exc)}", "db_tool_used": None}


async def send_email(state: AgentState) -> AgentState:
    try:
        tools = await list_tools(settings.email_mcp_server_url)
        tool = select_tool(tools, EMAIL_KEYWORDS)
        args = map_arguments(
            tool,
            EMAIL_FIELD_ALIASES,
            {
                "to": state["recipient_email"],
                "subject": state["title"],
                "body": state["story"],
            },
        )
        await call_tool(settings.email_mcp_server_url, tool["name"], args)
        return {"email_status": "sent", "email_tool_used": tool["name"]}
    except Exception as exc:  # noqa: BLE001 - surface failure to the caller
        return {"email_status": f"failed: {_flatten(exc)}", "email_tool_used": None}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("generate_story", generate_story)
    graph.add_node("store_story", store_story)
    graph.add_node("send_email", send_email)

    graph.set_entry_point("generate_story")
    graph.add_edge("generate_story", "store_story")
    graph.add_edge("store_story", "send_email")
    graph.add_edge("send_email", END)

    return graph.compile()


story_graph = build_graph()
