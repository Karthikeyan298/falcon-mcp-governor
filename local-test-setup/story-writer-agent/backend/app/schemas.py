from pydantic import BaseModel, EmailStr


class StoryRequest(BaseModel):
    title: str
    recipient_email: EmailStr


class StoryResponse(BaseModel):
    title: str
    story: str
    db_status: str
    db_tool_used: str | None = None
    email_status: str
    email_tool_used: str | None = None
