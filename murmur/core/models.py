from pydantic import BaseModel, Field

class ChangeLine(BaseModel):
    file: str
    line_number: int = Field(ge=1)
    content: str

class DetectionResult(BaseModel):
    file: str
    line_number: int
    rule_id: str
    severity: str
    hashed_secret: str
    masked_secret: str