from pydantic import BaseModel, Field
from typing import List, Optional

# 1. The deepest level: Lab Batches (e.g., A1, A2, A3)
class Batch(BaseModel):
    name: str = Field(..., description="Name of the batch, e.g., 'A1'")
    lab_room: str = Field(..., description="Room allocated for the lab, e.g., 'L1'")
    faculty: str = Field(..., description="Faculty member assigned to this lab batch")

# 2. The Subject Level
class Subject(BaseModel):
    name: str = Field(..., description="Name of the subject, e.g., 'Physics'")
    has_lab: bool = Field(..., description="True if the subject includes practical lab sessions")
    theory_faculty: str = Field(..., description="Faculty member assigned for theory lectures")
    
    # We set a default of 3 theory lectures per week, but the LLM can override this based on user text constraints
    theory_lectures_per_week: int = Field(default=3, description="Number of theory hours per week")
    
    # Batches are optional because not every subject has a lab (has_lab = False)
    batches: Optional[List[Batch]] = Field(default=None, description="List of lab batches if has_lab is True")

# 3. The Division Level
class Division(BaseModel):
    name: str = Field(..., description="Name of the division, e.g., 'FY_A'")
    theory_room: str = Field(..., description="The main classroom for all theory lectures, e.g., 'S501'")
    subjects: List[Subject] = Field(..., description="List of subjects taught to this division")

# 4. The Top Level: The Full Request Payload
class TimetableRequest(BaseModel):
    year: str = Field(..., description="The academic year, e.g., 'FY', 'SY', or 'TY'")
    divisions: List[Division] = Field(..., description="List of all divisions being scheduled")
    
    # Optional field to catch the plain-text rules typed by the user in the UI
    special_constraints: str = Field(default="", description="Any custom rules in plain text")