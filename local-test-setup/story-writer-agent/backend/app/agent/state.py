from typing import TypedDict


class AgentState(TypedDict, total=False):
    title: str
    recipient_email: str
    story: str
    db_status: str
    db_tool_used: str | None
    email_status: str
    email_tool_used: str | None
