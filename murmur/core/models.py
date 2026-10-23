# murmur/core/models.py
from pydantic import BaseModel, Field


class ChangeLine(BaseModel):
    file: str
    line_number: int = Field(ge=1)
    content: str
    commit_sha: str | None = None
    author: str | None = None
    commit_ts: str | None = None


class DetectionResult(BaseModel):
    file: str
    line_number: int
    rule_id: str
    severity: str
    hashed_secret: str
    masked_secret: str
    confidence: str = "medium"
    commit_sha: str | None = None
    author: str | None = None
    commit_ts: str | None = None
