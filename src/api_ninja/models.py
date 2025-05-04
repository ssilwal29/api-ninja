from pydantic import BaseModel, Field
from typing import List, Optional


class ApiCallModel(BaseModel):
    method: str
    path: str
    payload_description: str
    headers_description: str
    expected_status: int
    response_check: str


class GoalModel(BaseModel):
    goal: str
    steps: List[ApiCallModel]


class EvaluationResult(BaseModel):
    status: str = Field(..., description="PASS or FAIL")
    reason: str = Field(..., description="Why the test passed or failed")
    suggestion: Optional[str] = Field(
        None, description="How to fix the issue if failed"
    )


class FlowModel(BaseModel):
    id: str
    description: str
    expectations: str
    notes: str
