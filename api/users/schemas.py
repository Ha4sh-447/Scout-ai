from typing import Optional
from pydantic import BaseModel, EmailStr


class SettingsUpdate(BaseModel):
    interval_hours: Optional[int] = None
    search_queries: Optional[list[str]] = None
    location: Optional[str] = None
    resume_summary: Optional[str] = None
    notification_email: Optional[EmailStr] = None
    is_scheduler_active: Optional[bool] = None

class SettingsResponse(BaseModel):
    interval_hours: int
    search_queries: list[str]
    location: str
    resume_summary: Optional[str]
    notification_email: Optional[str]
    is_scheduler_active: Optional[bool]

    class Config:
        from_attributes = True

class ResumeUploadResponse(BaseModel):
    resume_id: str
    chunks_stored: int
    full_resume_stored: bool
    message: str

class SessionUpdate(BaseModel):
    storage_state: dict
