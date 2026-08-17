from app.agent.graph import story_graph
from app.schemas import StoryResponse


async def run_story_pipeline(title: str, recipient_email: str) -> StoryResponse:
    result = await story_graph.ainvoke({"title": title, "recipient_email": recipient_email})
    return StoryResponse(
        title=title,
        story=result["story"],
        db_status=result["db_status"],
        db_tool_used=result.get("db_tool_used"),
        email_status=result["email_status"],
        email_tool_used=result.get("email_tool_used"),
    )
