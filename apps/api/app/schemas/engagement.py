"""Engagement API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class DailyGoalRequest(BaseModel):
    goal_type: str
    goal_date: date | None = None


class GoalStepRequest(BaseModel):
    step_id: str


class NotificationPreferencesUpdate(BaseModel):
    preferences: dict[str, bool] = Field(default_factory=dict)


class GuidedAnswerRequest(BaseModel):
    category: str
    key: str
    value: Any
    verification_status: str | None = None


class RetentionActionRequest(BaseModel):
    action: str  # keep | archive | delete_now | export
    confirmation: str | None = None  # required "DELETE" for delete_now
